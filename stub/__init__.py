"""RuoYi 契约桩。

仅供离线联调、CI 冒烟、缺陷生命周期演示使用，**不是被测系统**。
真实测试请使用 `AUTOTEST_TARGET=real` 指向真实后端。
"""

from .app import create_app

__all__ = ["create_app"]
