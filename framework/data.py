"""测试数据工厂与数据文件加载。

三条硬规则
----------
1. **数据必须唯一**。RuoYi 对 userName / phonenumber / email 建了唯一索引，
   固定数据跑第二遍就红。这里用 `uuid4` 保证任意次重跑、任意 worker 都不撞。
2. **数据必须可识别**。所有生成值统一带 `at_`（autotest）前缀，
   出事时能一眼从生产数据里捞出来清理。
3. **数据必须可覆盖**。工厂只给"合法基线"，用例需要非法值时显式 override，
   不允许在工厂里偷偷改语义。
"""

from __future__ import annotations

import json
import secrets
import uuid
from pathlib import Path
from typing import Any, Mapping

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PREFIX = "at_"


def load_json(name: str) -> Any:
    """读取 data/ 下的 JSON。传 `cases/user_validation` 自动补后缀。"""
    path = DATA_DIR / (name if name.endswith(".json") else f"{name}.json")
    if not path.is_file():
        raise FileNotFoundError(f"找不到数据文件: {path}")
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_cases(name: str, key: str = "cases") -> list[dict[str, Any]]:
    payload = load_json(name)
    cases = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(cases, list):
        raise ValueError(f"{name} 中缺少 {key!r} 列表")
    return cases


def unique_token(length: int = 8) -> str:
    return uuid.uuid4().hex[:length]


def unique_name(prefix: str = "user", max_len: int = 20) -> str:
    """生成符合 RuoYi 用户名长度限制且全局唯一的名字。"""
    suffix = unique_token(8)
    base = f"{PREFIX}{prefix}_{suffix}"
    return base[:max_len]


def unique_phone() -> str:
    """11 位手机号，1[3-9] 开头，避免撞上 RuoYi 的手机号唯一索引。"""
    head = secrets.choice("3456789")
    tail = "".join(secrets.choice("0123456789") for _ in range(9))
    return f"1{head}{tail}"


def unique_email(local: str | None = None) -> str:
    return f"{local or PREFIX + unique_token(6)}@autotest.local"


def unique_role_name() -> str:
    return f"{PREFIX}角色_{unique_token(6)}"


def unique_role_key() -> str:
    return f"{PREFIX}role_{unique_token(6)}"
