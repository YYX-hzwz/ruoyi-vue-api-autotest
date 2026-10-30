"""统一日志。

- 控制台：只打 INFO 及以上，保持 pytest 输出干净
- 文件：reports/pytest.log，打 DEBUG 全量报文
- 敏感信息（token、密码）在落盘前脱敏
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .settings import REPORTS_DIR, SETTINGS

_SENSITIVE = re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]+")
_PASSWORD_FIELD = re.compile(r'("password"\s*:\s*")[^"]*(")', re.IGNORECASE)

_configured = False


def _scrub(message: str) -> str:
    message = _SENSITIVE.sub(r"\1***", message)
    return _PASSWORD_FIELD.sub(r"\1***\2", message)


class _ScrubFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        return _scrub(super().format(record))


def configure(log_dir: Path | None = None) -> None:
    """幂等初始化；重复调用不会叠加 handler。"""
    global _configured
    if _configured:
        return

    target_dir = log_dir or REPORTS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    formatter = _ScrubFormatter(
        fmt="%(asctime)s %(levelname)-7s %(name)-22s %(message)s",
        datefmt="%H:%M:%S",
    )

    file_handler = logging.FileHandler(target_dir / "pytest.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)

    root = logging.getLogger("autotest")
    root.setLevel(getattr(logging, SETTINGS.log_level, logging.INFO))
    root.addHandler(file_handler)
    root.addHandler(console)
    root.propagate = False

    _configured = True


def get_logger(name: str) -> logging.Logger:
    configure()
    return logging.getLogger(f"autotest.{name}")
