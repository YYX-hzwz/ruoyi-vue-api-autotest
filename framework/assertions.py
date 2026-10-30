"""统一断言。

核心原则：**断言要能说清"为什么错"**。

对比一下：
    # 反面教材：挂了只知道"不是 200"
    assert resp.json()["code"] == 200

    # 这里：失败时打印 method/url/HTTP/code/msg/响应体前 600 字
    expect_ok(resp)

另一个原则：**区分传输层错误和业务层错误**。RuoYi 大量使用
"HTTP 200 + body.code=500/403" 的表达方式，所以 `status_code == 200`
几乎不携带信息，真正的断言必须落在 `code` 和 `msg` 上。
"""

from __future__ import annotations

import time
from typing import Any, Callable, Mapping

from .http import ApiResponse
from .schema import Field, validate


class ApiAssertionError(AssertionError):
    """带响应上下文的断言失败。"""


def _fail(message: str, response: ApiResponse | None = None) -> None:
    detail = f"\n\n{response.summary()}" if response is not None else ""
    raise ApiAssertionError(f"{message}{detail}")


# --------------------------------------------------------------------------
# 成功路径
# --------------------------------------------------------------------------
def expect_ok(response: ApiResponse, *, msg_contains: str | None = None) -> ApiResponse:
    """断言业务成功：HTTP 2xx 且 body.code == 200。"""
    if not (200 <= response.status_code < 300):
        _fail(f"期望 HTTP 2xx，实际 {response.status_code}", response)
    if response.code != 200:
        _fail(f"期望业务码 200，实际 {response.code!r}（msg={response.msg!r}）", response)
    if msg_contains and msg_contains not in response.msg:
        _fail(f"期望 msg 包含 {msg_contains!r}，实际 {response.msg!r}", response)
    return response


def expect_schema(response: ApiResponse, schema: Mapping[str, Any] | Field) -> dict[str, Any]:
    """校验响应结构是否符合契约，返回解析后的 body。"""
    payload = response.json
    if not isinstance(payload, dict):
        _fail("响应不是合法的 JSON 对象", response)
    errors = validate(payload, schema)
    if errors:
        joined = "\n  - ".join(errors)
        _fail(f"响应结构与契约不符，共 {len(errors)} 处：\n  - {joined}", response)
    return payload  # type: ignore[return-value]


def expect_list_page(
    response: ApiResponse,
    *,
    expected_size: int | None = None,
    allow_empty: bool = True,
) -> list[dict[str, Any]]:
    """校验分页结构，并验证 size 参数真的生效。

    注意：`len(rows) <= size` 是**假断言**——后端彻底忽略分页参数时，
    它照样成立。这里同时校验 `total` 与页大小的关系，强迫后端暴露真实行为。
    """
    expect_ok(response)
    rows = response.rows
    total = response.total
    if total is None:
        _fail("分页响应缺少 total 字段", response)
    if expected_size is not None:
        if len(rows) > expected_size:
            _fail(f"分页失效：请求 pageSize={expected_size}，返回 {len(rows)} 条", response)
        if total > expected_size and len(rows) != expected_size:
            _fail(
                f"分页失效：total={total} > pageSize={expected_size}，"
                f"本页却返回 {len(rows)} 条（应为 {expected_size} 条）",
                response,
            )
    if not allow_empty and not rows and (total or 0) > 0:
        _fail(f"total={total} 但本页为空", response)
    return rows


# --------------------------------------------------------------------------
# 失败路径
# --------------------------------------------------------------------------
def expect_biz_error(
    response: ApiResponse,
    *,
    code: int = 500,
    msg_contains: str | None = None,
) -> ApiResponse:
    """断言业务失败。

    `msg_contains` 强烈建议传：只断言 `code == 500` 无法区分
    "被权限拦住" / "被参数校验拦住" / "数据库炸了"——三者都是 500，
    用例会以错误的理由通过。
    """
    if response.status_code >= 500:
        _fail(
            f"期望业务错误（HTTP 200 + code={code}），但服务端直接返回了 HTTP {response.status_code}",
            response,
        )
    if response.code != code:
        _fail(f"期望业务码 {code}，实际 {response.code!r}（msg={response.msg!r}）", response)
    if msg_contains and msg_contains not in response.msg:
        _fail(f"期望 msg 包含 {msg_contains!r}，实际 {response.msg!r}", response)
    return response


def expect_perm_denied(response: ApiResponse) -> ApiResponse:
    """断言权限被拒。

    RuoYi 的 `@PreAuthorize` 失败走 GlobalExceptionHandler，
    返回的是 **HTTP 200 + body.code=403**，不是 HTTP 403。
    这正是最初那批"越权用例"永远无法正确断言的根因。
    """
    if response.status_code == 401:
        _fail("期望 403 权限不足，实际 401 未认证（token 失效？）", response)
    if response.code != 403:
        _fail(
            f"期望业务码 403（无权限），实际 {response.code!r}（msg={response.msg!r}）",
            response,
        )
    return response


def expect_unauthorized(response: ApiResponse) -> ApiResponse:
    """断言未认证：RuoYi 返回 HTTP 200 + code=401。"""
    if response.code == 401:
        return response
    if response.status_code == 401:
        return response
    _fail(f"期望认证失败（code=401），实际 {response.code!r}", response)
    return response  # pragma: no cover


def expect_not_found(response: ApiResponse, *, msg_contains: str | None = None) -> ApiResponse:
    return expect_biz_error(response, code=500, msg_contains=msg_contains)


# --------------------------------------------------------------------------
# 副作用校验
# --------------------------------------------------------------------------
def eventually(
    probe: Callable[[], Any],
    *,
    predicate: Callable[[Any], bool] | None = None,
    timeout: float = 3.0,
    interval: float = 0.15,
    description: str = "条件",
) -> Any:
    """轮询直到条件成立，用于验证"写接口真的落库了"。

    为什么需要：只断言 `code == 200` 无法证明数据被写进去了。
    有的实现返回成功但没落库（事务回滚、异步队列丢消息），
    这种缺陷只有回查才能抓到。
    """
    deadline = time.monotonic() + timeout
    last: Any = None
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            last = probe()
            if predicate is None or predicate(last):
                return last
        except Exception as exc:  # noqa: BLE001 - 探针失败也要重试
            last_error = exc
        time.sleep(interval)
    if last_error is not None:
        raise ApiAssertionError(f"{description} 在 {timeout}s 内未满足，最后一次异常：{last_error!r}")
    raise ApiAssertionError(f"{description} 在 {timeout}s 内未满足，最后一次观测值：{last!r}")


def expect_equal(actual: Any, expected: Any, *, label: str = "值") -> None:
    if actual != expected:
        raise ApiAssertionError(f"{label} 不一致：期望 {expected!r}，实际 {actual!r}")
