"""框架运行时配置。

设计要点
--------
1. **配置只从环境变量读取**，代码里不出现任何地址、账号、密码字面量。
   `.env` 只是给本地开发用的便捷入口，生产/CI 直接用环境变量注入。
2. **启动即校验**。配错的地址、非法的超时值会在导入阶段就炸掉，
   而不是等某条用例跑到一半报一个看不懂的 ConnectionError。
3. **不可变**。Settings 是 frozen dataclass，运行期不允许被用例改掉——
   用例改配置是自动化测试里最隐蔽的相互污染来源。
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass
from typing import Mapping

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
REPORTS_DIR = ROOT / "reports"

_PREFIX = "AUTOTEST_"


def _parse_dotenv(path: pathlib.Path) -> dict[str, str]:
    """极简 .env 解析器：KEY=VALUE、# 注释、可选的成对引号。"""
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        result[key] = value
    return result


def _source() -> Mapping[str, str]:
    """真实环境变量优先于 .env，方便 CI 覆盖本地文件。"""
    merged = dict(_parse_dotenv(ENV_FILE))
    merged.update({k: v for k, v in os.environ.items() if k.startswith(_PREFIX)})
    return merged


def _bool(raw: str | None, *, default: bool) -> bool:
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"无法解析为布尔值: {raw!r}")


def _float(raw: str | None, *, default: float) -> float:
    if raw is None or raw == "":
        return default
    value = float(raw)
    if value <= 0:
        raise ValueError(f"超时必须是正数，收到 {value}")
    return value


def _int(raw: str | None, *, default: int) -> int:
    if raw is None or raw == "":
        return default
    return int(raw)


@dataclass(frozen=True, slots=True)
class Settings:
    target: str
    base_url: str
    admin_user: str
    admin_pass: str
    captcha_enabled: bool
    captcha_code: str
    redis_url: str
    connect_timeout: float
    read_timeout: float
    retries: int
    run_id: str
    stub_port: int
    stub_reproduce_bugs: bool
    log_level: str

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout, self.read_timeout)

    @property
    def is_stub(self) -> bool:
        return self.target == "stub"

    def describe(self) -> str:
        mode = "契约桩（非被测系统）" if self.is_stub else "真实后端"
        return (
            f"target={self.target}({mode}) base_url={self.base_url} "
            f"captcha={self.captcha_enabled} timeout={self.timeout} "
            f"retries={self.retries} run_id={self.run_id}"
        )


def load_settings() -> Settings:
    env = _source()

    def get(key: str, default: str | None = None) -> str | None:
        return env.get(f"{_PREFIX}{key}", default)

    target = (get("TARGET", "stub") or "stub").strip().lower()
    if target not in {"stub", "real"}:
        raise ValueError(f"AUTOTEST_TARGET 只能是 stub 或 real，收到 {target!r}")

    base_url = (get("BASE_URL", "http://localhost:8080") or "").rstrip("/")
    if target == "real" and not base_url.startswith(("http://", "https://")):
        raise ValueError(f"AUTOTEST_BASE_URL 必须是 http(s) 地址，收到 {base_url!r}")

    admin_user = get("ADMIN_USER", "admin") or "admin"
    admin_pass = get("ADMIN_PASS", "admin123") or ""
    if target == "real" and not admin_pass:
        raise ValueError("AUTOTEST_TARGET=real 时必须提供 AUTOTEST_ADMIN_PASS")

    run_id = (get("RUN_ID") or "").strip().strip("_")
    if not run_id:
        run_id = os.environ.get("PYTEST_XDIST_WORKER") or "local"

    return Settings(
        target=target,
        base_url=base_url,
        admin_user=admin_user,
        admin_pass=admin_pass,
        captcha_enabled=_bool(get("CAPTCHA_ENABLED"), default=False),
        captcha_code=(get("CAPTCHA_CODE") or "").strip(),
        redis_url=(get("REDIS_URL") or "").strip(),
        connect_timeout=_float(get("HTTP_CONNECT_TIMEOUT"), default=3.0),
        read_timeout=_float(get("HTTP_READ_TIMEOUT"), default=10.0),
        retries=_int(get("HTTP_RETRIES"), default=2),
        run_id=run_id,
        stub_port=_int(get("STUB_PORT"), default=0),
        stub_reproduce_bugs=_bool(get("STUB_REPRODUCE_BUGS"), default=True),
        log_level=(get("LOG_LEVEL", "INFO") or "INFO").upper(),
    )


SETTINGS = load_settings()
