"""pytest 全局装配。

这一层只做"接线"，不放业务逻辑：
- 校验被测目标可达（不可达就立刻失败，而不是让 40 条用例各报一个 ConnectionError）
- 启动/关闭契约桩
- 提供已登录的 API 对象与数据工厂
- 把每条用例的请求响应挂进报告
- 会话结束时产出质量看板（reports/QUALITY.md + summary.json）
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest
import requests
from werkzeug.serving import make_server

from framework.assertions import expect_ok, eventually
from framework.http import HttpClient
from framework.logger import get_logger
from framework.settings import REPORTS_DIR, SETTINGS
from framework.trace import RECORDER
from ruoyi import AuthAPI, RoleAPI, SystemAPI, UserAPI, login_as
from ruoyi.factories import role_payload, user_payload

logger = get_logger("conftest")

DEFECT_REGISTRY = Path(__file__).resolve().parent / "defects" / "registry.json"


# ==========================================================================
# 契约桩
# ==========================================================================
class StubServer:
    """在后台线程里起一个真实端口的 Flask 服务。"""

    def __init__(self) -> None:
        from stub.app import create_app

        app = create_app(
            reproduce_bugs=SETTINGS.stub_reproduce_bugs,
            captcha_enabled=SETTINGS.captcha_enabled,
        )
        self._server = make_server("127.0.0.1", SETTINGS.stub_port, app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self.base_url = f"http://127.0.0.1:{self._server.server_port}"

    def start(self) -> str:
        self._thread.start()
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                response = requests.get(f"{self.base_url}/__stub/health", timeout=1)
                if response.status_code == 200:
                    return self.base_url
            except requests.RequestException:
                time.sleep(0.05)
        raise RuntimeError(f"契约桩启动超时: {self.base_url}")

    def stop(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)


# ==========================================================================
# 数据载体
# ==========================================================================
@dataclass
class CreatedUser:
    payload: dict[str, Any]
    user_id: int
    password: str

    @property
    def user_name(self) -> str:
        return str(self.payload["userName"])


@dataclass
class CreatedRole:
    payload: dict[str, Any]
    role_id: int


@dataclass
class Session:
    """一个独立登录会话（普通用户/管理员各一份）。"""

    http: HttpClient
    auth: AuthAPI
    api: UserAPI
    roles: RoleAPI
    system: SystemAPI
    user: dict[str, Any] = field(default_factory=dict)


# ==========================================================================
# 会话级装配
# ==========================================================================
def pytest_configure(config: pytest.Config) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    mode = "契约桩（非被测系统）" if SETTINGS.is_stub else "真实后端"
    banner = (
        "\n"
        "──────────────────────────────────────────────────────────────\n"
        f"  RuoYi API 自动化测试 · 目标：{mode}\n"
        f"  {SETTINGS.describe()}\n"
    )
    if SETTINGS.is_stub:
        banner += (
            "  [!] 当前跑的是契约桩，结果只能证明「框架与用例逻辑正确」，\n"
            "      不能作为被测系统的质量结论。真实验收请设置：\n"
            "      AUTOTEST_TARGET=real  AUTOTEST_BASE_URL=http://your-host:8080\n"
        )
    banner += "──────────────────────────────────────────────────────────────\n"
    print(banner)


@pytest.fixture(scope="session")
def base_url() -> Iterator[str]:
    if SETTINGS.is_stub:
        server = StubServer()
        url = server.start()
        logger.info("契约桩已启动: %s (缺陷复现=%s)", url, SETTINGS.stub_reproduce_bugs)
        yield url
        server.stop()
        logger.info("契约桩已关闭")
        return

    probe = f"{SETTINGS.base_url}/captchaImage"
    try:
        response = requests.get(probe, timeout=SETTINGS.timeout)
    except requests.RequestException as exc:
        pytest.exit(
            f"被测后端不可达：{probe}\n  {exc}\n"
            "  请确认服务已启动，或在 .env 中设置 AUTOTEST_BASE_URL",
            returncode=2,
        )
    if response.status_code >= 500:
        pytest.exit(f"被测后端健康检查失败（HTTP {response.status_code}）：{probe}", returncode=2)
    yield SETTINGS.base_url


@pytest.fixture(scope="session")
def admin_http(base_url: str) -> Iterator[HttpClient]:
    """管理员客户端，**创建即登录**。

    这里把登录放进 fixture 本身，而不是让 API 对象去"顺便依赖"登录 fixture：
    否则单独跑 `pytest -m contract` 时，没有任何用例触发登录，
    整个会话就会以 401 失败——这种隐藏耦合只有在跑子集时才会暴露。
    """
    client = HttpClient(base_url)
    AuthAPI(client).authenticate()
    yield client
    client.close()


@pytest.fixture(scope="session")
def admin_auth(admin_http: HttpClient) -> AuthAPI:
    return AuthAPI(admin_http)


@pytest.fixture(scope="session")
def user_api(admin_http: HttpClient) -> UserAPI:
    return UserAPI(admin_http)


@pytest.fixture(scope="session")
def role_api(admin_http: HttpClient) -> RoleAPI:
    return RoleAPI(admin_http)


@pytest.fixture(scope="session")
def system_api(admin_http: HttpClient) -> SystemAPI:
    return SystemAPI(admin_http)


# ==========================================================================
# 资源工厂（带清理）
# ==========================================================================
def find_user_id(user_api: UserAPI, user_name: str) -> int:
    """按用户名回查主键。

    RuoYi 的 POST /system/user 只返回 code 不返回 id，必须回查。
    用轮询而不是 sleep，避免主从延迟/事务可见性带来的偶发失败。
    """
    rows = eventually(
        lambda: user_api.list(user_name=user_name).rows,
        predicate=lambda items: any(item.get("userName") == user_name for item in items),
        timeout=5.0,
        description=f"用户 {user_name} 落库可见",
    )
    return int(next(item["userId"] for item in rows if item.get("userName") == user_name))


def find_role_id(role_api: RoleAPI, role_key: str) -> int:
    rows = eventually(
        lambda: role_api.list(role_key=role_key).rows,
        predicate=lambda items: any(item.get("roleKey") == role_key for item in items),
        timeout=5.0,
        description=f"角色 {role_key} 落库可见",
    )
    return int(next(item["roleId"] for item in rows if item.get("roleKey") == role_key))


@pytest.fixture
def user_factory(user_api: UserAPI) -> Iterator[Callable[..., CreatedUser]]:
    created: list[CreatedUser] = []

    def factory(**overrides: Any) -> CreatedUser:
        payload = user_payload(**overrides)
        expect_ok(user_api.create(payload), msg_contains="成功")
        record = CreatedUser(
            payload=payload,
            user_id=find_user_id(user_api, payload["userName"]),
            password=payload["password"],
        )
        created.append(record)
        return record

    yield factory

    # 清理失败只记录，不让 teardown 掩盖真实失败
    for record in reversed(created):
        try:
            response = user_api.delete(record.user_id)
            if response.code != 200:
                logger.warning("清理用户 %s 未成功: %s", record.user_name, response.msg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("清理用户 %s 异常: %r", record.user_name, exc)


@pytest.fixture
def role_factory(role_api: RoleAPI) -> Iterator[Callable[..., CreatedRole]]:
    created: list[CreatedRole] = []

    def factory(**overrides: Any) -> CreatedRole:
        payload = role_payload(**overrides)
        expect_ok(role_api.create(payload), msg_contains="成功")
        record = CreatedRole(payload=payload, role_id=find_role_id(role_api, payload["roleKey"]))
        created.append(record)
        return record

    yield factory

    for record in reversed(created):
        try:
            response = role_api.delete(record.role_id)
            if response.code != 200:
                logger.warning("清理角色 %s 未成功: %s", record.role_id, response.msg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("清理角色 %s 异常: %r", record.role_id, exc)


# ==========================================================================
# 权限相关
# ==========================================================================
@pytest.fixture(scope="session")
def common_role_id(role_api: RoleAPI) -> int:
    """按 roleKey 解析普通角色，而不是硬编码 id=2。

    硬编码 id 是原项目最大的可移植性缺陷：换一套初始化数据，
    全套权限用例会以"错误理由通过"。
    """
    rows = role_api.list(role_key="common", page_size=50).rows
    for row in rows:
        if row.get("roleKey") == "common":
            return int(row["roleId"])
    pytest.skip("目标环境中不存在 roleKey=common 的角色，跳过权限相关用例")
    raise AssertionError("unreachable")  # pragma: no cover


@pytest.fixture(scope="session")
def admin_role_id(role_api: RoleAPI) -> int:
    rows = role_api.list(role_key="admin", page_size=50).rows
    for row in rows:
        if row.get("roleKey") == "admin":
            return int(row["roleId"])
    pytest.skip("目标环境中不存在 roleKey=admin 的角色")
    raise AssertionError("unreachable")  # pragma: no cover


@pytest.fixture
def normal_session(
    base_url: str,
    common_role_id: int,
    user_factory: Callable[..., CreatedUser],
) -> Iterator[Session]:
    """创建一个普通角色用户并登录，返回独立会话。"""
    record = user_factory(roleIds=[common_role_id])
    http = HttpClient(base_url)
    try:
        response = login_as(http, record.user_name, record.password, SETTINGS)
        if response.code != 200:
            pytest.skip(f"普通用户登录失败（{response.msg}），环境可能未启用该账号策略")
        http.set_token(str(response.get("token")))
        yield Session(
            http=http,
            auth=AuthAPI(http),
            api=UserAPI(http),
            roles=RoleAPI(http),
            system=SystemAPI(http),
            user={"userName": record.user_name, "userId": record.user_id, "password": record.password},
        )
    finally:
        http.close()


@pytest.fixture
def anonymous(base_url: str) -> Iterator[HttpClient]:
    """未认证客户端，用于验证 401 与未登录暴露面。"""
    client = HttpClient(base_url)
    yield client
    client.close()


# ==========================================================================
# 追踪：每条用例开始清空、结束挂附件
# ==========================================================================
@pytest.fixture(autouse=True)
def _api_trace(request: pytest.FixtureRequest) -> Iterator[None]:
    RECORDER.start(request.node.nodeid)
    yield


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Iterator[None]:  # type: ignore[misc]
    """把本条用例的请求/响应写成 pytest-html 附件。"""
    outcome = yield
    report = outcome.get_result()

    if call.when != "call":
        return

    exchanges = RECORDER.drain()
    if not exchanges:
        return

    try:
        from pytest_html import extras  # type: ignore
    except ImportError:  # pragma: no cover
        return

    attachments = [
        extras.json(
            [exchange.as_dict() for exchange in exchanges],
            name=f"API 交互记录（{len(exchanges)} 次）",
        )
    ]
    if report.failed:
        curl = "\n\n".join(
            f"# {index + 1}\n{exchange.as_curl()}" for index, exchange in enumerate(exchanges)
        )
        attachments.append(extras.text(curl, name="复现用 cURL"))

    existing = getattr(report, "extras", [])
    report.extras = list(existing) + attachments


# ==========================================================================
# 质量看板
# ==========================================================================
_CASE_RESULTS: dict[str, dict[str, Any]] = {}


def _defect_id(item: pytest.Item) -> str | None:
    marker = item.get_closest_marker("defect")
    if marker and marker.args:
        return str(marker.args[0])
    return None


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when not in {"setup", "call"}:
        return
    outcome = report.outcome
    if hasattr(report, "wasxfail"):
        outcome = "xfailed" if report.outcome == "skipped" else "xpassed"
    # setup 阶段的 error 不应被后续 call 覆盖，但 skip 需要记录
    previous = _CASE_RESULTS.get(report.nodeid)
    if previous and previous.get("when") == "setup" and previous["outcome"] == "error":
        return
    _CASE_RESULTS[report.nodeid] = {
        "outcome": outcome,
        "duration": report.duration,
        "when": report.when,
    }


def _load_registry() -> list[dict[str, Any]]:
    if not DEFECT_REGISTRY.is_file():
        return []
    with DEFECT_REGISTRY.open(encoding="utf-8") as handle:
        return json.load(handle).get("defects", [])


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: pytest.Config) -> None:
    cases = [
        {
            "nodeid": nodeid,
            "outcome": info["outcome"],
            "duration": round(info["duration"], 3),
            "module": nodeid.split("::")[0],
        }
        for nodeid, info in sorted(_CASE_RESULTS.items())
    ]
    totals: dict[str, int] = {}
    for case in cases:
        totals[case["outcome"]] = totals.get(case["outcome"], 0) + 1

    defect_tests: dict[str, list[str]] = {}
    for item in getattr(config, "_autotest_items", []):
        defect = _defect_id(item)
        if defect:
            defect_tests.setdefault(defect, []).append(item.nodeid)

    registry = _load_registry()
    for defect in registry:
        declared = [defect["test"]] if defect.get("test") else []
        tests = defect_tests.get(defect["id"]) or declared
        outcomes = {_CASE_RESULTS.get(test, {}).get("outcome") for test in tests}
        if not tests:
            defect["observed"] = "未绑定用例"
        elif outcomes == {None}:
            # 只跑了子集（如 pytest -m contract），不算异常
            defect["observed"] = "本次未执行"
        elif outcomes == {"xfailed"}:
            defect["observed"] = "仍可复现（xfail）"
        elif outcomes and outcomes <= {"passed", "xfailed", "xpassed"}:
            defect["observed"] = "已修复（用例转绿）"
        elif "failed" in outcomes or "error" in outcomes:
            defect["observed"] = "用例失败：缺陷回归或断言过期"
        else:
            defect["observed"] = "状态未知"

    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "target": SETTINGS.target,
        "base_url": SETTINGS.base_url if not SETTINGS.is_stub else "stub(内置)",
        "totals": totals,
        "duration_seconds": round(sum(case["duration"] for case in cases), 2),
        "cases": cases,
        "defects": registry,
    }
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (REPORTS_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (REPORTS_DIR / "QUALITY.md").write_text(_render_quality(summary, defect_tests), encoding="utf-8")

    terminalreporter.write_sep("=", "质量摘要")
    order = ["passed", "failed", "error", "skipped", "xfailed", "xpassed"]
    line = "  ".join(f"{key}={totals.get(key, 0)}" for key in order if totals.get(key))
    terminalreporter.write_line(f"结果：{line or '无'}")
    if registry:
        terminalreporter.write_line("已知缺陷：")
        for defect in registry:
            terminalreporter.write_line(
                f"  {defect['id']} [{defect.get('severity', '-')}] {defect['title']} -> {defect['observed']}"
            )

    fixed = [defect["id"] for defect in registry if defect["observed"].startswith("已修复")]
    if fixed:
        terminalreporter.write_line("")
        terminalreporter.write_line(
            f"[!] {', '.join(fixed)} 已修复，请移除对应 xfail 标记，让用例进入长期回归。"
        )
    terminalreporter.write_line("产物：reports/report.html · reports/QUALITY.md · reports/summary.json")


def _render_quality(summary: dict[str, Any], defect_tests: dict[str, list[str]]) -> str:
    totals = summary["totals"]
    lines = [
        "# 质量看板",
        "",
        f"- 生成时间：{summary['generated_at']}",
        f"- 目标：`{summary['target']}` · `{summary['base_url']}`",
        f"- 用例总数：{len(summary['cases'])}，总耗时 {summary['duration_seconds']}s",
        "",
        "## 结果分布",
        "",
        "| 结果 | 数量 |",
        "|------|------|",
    ]
    for key in ["passed", "failed", "error", "skipped", "xfailed", "xpassed"]:
        if totals.get(key):
            lines.append(f"| {key} | {totals[key]} |")

    modules: dict[str, dict[str, int]] = {}
    for case in summary["cases"]:
        bucket = modules.setdefault(case["module"], {})
        bucket[case["outcome"]] = bucket.get(case["outcome"], 0) + 1
    lines += [
        "",
        "## 模块分布",
        "",
        "| 模块 | 通过 | 失败 | xfail | xpass | 跳过 |",
        "|------|------|------|-------|-------|------|",
    ]
    for module, bucket in sorted(modules.items()):
        lines.append(
            f"| {module} | {bucket.get('passed', 0)} | "
            f"{bucket.get('failed', 0) + bucket.get('error', 0)} | "
            f"{bucket.get('xfailed', 0)} | {bucket.get('xpassed', 0)} | "
            f"{bucket.get('skipped', 0)} |"
        )

    if summary["defects"]:
        lines += [
            "",
            "## 缺陷状态",
            "",
            "| 缺陷 | 级别 | 标题 | 当前观测 | 绑定用例 |",
            "|------|------|------|----------|----------|",
        ]
        for defect in summary["defects"]:
            declared = [defect["test"]] if defect.get("test") else []
            count = len(defect_tests.get(defect["id"]) or declared)
            lines.append(
                f"| {defect['id']} | {defect.get('severity', '-')} | {defect['title']} | "
                f"{defect['observed']} | {count} |"
            )

    return "\n".join(lines) + "\n"


def pytest_collection_modifyitems(
    session: pytest.Session,
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    config._autotest_items = items  # type: ignore[attr-defined]
