"""RuoYi 领域层：接口对象 + 数据工厂 + 响应契约。

分层的意义：`framework` 里没有任何 RuoYi 的字样，
换一个被测系统只需重写 `ruoyi/` 这一层，框架原样复用。
"""

from .auth import AuthAPI, login_as
from .role import RoleAPI
from .system import SystemAPI
from .user import UserAPI

__all__ = ["AuthAPI", "RoleAPI", "SystemAPI", "UserAPI", "login_as"]
