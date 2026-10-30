"""通用测试基础设施。

与 RuoYi 无关，可整体复制到其他项目：
- settings  配置
- http      HTTP 客户端（超时/重试/追踪/401 自动重登）
- trace     请求响应追踪
- logger    日志与脱敏
- schema    响应结构校验 DSL
- assertions 统一断言
- data      数据工厂
"""

from .assertions import (
    ApiAssertionError,
    eventually,
    expect_biz_error,
    expect_equal,
    expect_list_page,
    expect_ok,
    expect_perm_denied,
    expect_schema,
    expect_unauthorized,
)
from .http import ApiResponse, HttpClient, TransportError
from .settings import SETTINGS, Settings, load_settings

__all__ = [
    "ApiAssertionError",
    "ApiResponse",
    "HttpClient",
    "SETTINGS",
    "Settings",
    "TransportError",
    "eventually",
    "expect_biz_error",
    "expect_equal",
    "expect_list_page",
    "expect_ok",
    "expect_perm_denied",
    "expect_schema",
    "expect_unauthorized",
    "load_settings",
]
