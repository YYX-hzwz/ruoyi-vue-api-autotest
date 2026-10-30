"""测试数据工厂：只负责造"合法基线"，非法值由用例显式覆盖。

原项目的问题是把模板写进 `data/users.json` 后，用例里再就地 `user_data["userName"] = ...`
——同一个 dict 被多处以不同方式篡改，读代码时要人肉跟踪它此刻是什么状态。
工厂模式把"生成"和"变体"分开：

    payload = user_payload()                      # 合法基线
    payload = user_payload(password="123")        # 只改一处，其余保持合法
"""

from __future__ import annotations

from typing import Any, Mapping

from framework.data import (
    load_json,
    unique_email,
    unique_name,
    unique_phone,
    unique_role_key,
    unique_role_name,
)

from .constants import (
    ADMIN_DEPT_ID,
    ADMIN_POST_ID,
    COMMON_ROLE_ID,
    STATUS_NORMAL,
)


def _template(file_name: str, key: str) -> dict[str, Any]:
    data = load_json(file_name)
    template = data.get(key)
    if not isinstance(template, dict):
        raise KeyError(f"data/{file_name}.json 缺少模板 {key!r}")
    return dict(template)


def user_payload(**overrides: Any) -> dict[str, Any]:
    """生成一个合法且唯一的新用户。

    唯一性三个字段全部随机，避免唯一索引冲突——这也是"固定数据跑第二遍就红"
    的根治方式。
    """
    payload = _template("users", "valid_user")
    payload.update(
        {
            "userName": unique_name("user"),
            "nickName": f"自动化用户{unique_name('', 6).lstrip('_')}",
            "password": "At@123456",
            "phonenumber": unique_phone(),
            "email": unique_email(),
            "sex": "0",
            "status": STATUS_NORMAL,
            "deptId": ADMIN_DEPT_ID,
            "postIds": [ADMIN_POST_ID],
            "roleIds": [COMMON_ROLE_ID],
        }
    )
    payload.update(overrides)
    return payload


def role_payload(**overrides: Any) -> dict[str, Any]:
    payload = _template("roles", "valid_role")
    payload.update(
        {
            "roleName": unique_role_name(),
            "roleKey": unique_role_key(),
            "roleSort": 10,
            "status": STATUS_NORMAL,
            "menuIds": [1, 103, 104],
        }
    )
    payload.update(overrides)
    return payload


def minimal_role(**overrides: Any) -> dict[str, Any]:
    """只带必填字段的角色，用于验证"服务端默认值"行为。"""
    base = {
        "roleName": unique_role_name(),
        "roleKey": unique_role_key(),
        "roleSort": 99,
        "status": STATUS_NORMAL,
    }
    base.update(overrides)
    return base


def patch(base: Mapping[str, Any], **changes: Any) -> dict[str, Any]:
    """不可变地派生一个新 payload（只传要改的字段）。"""
    merged = dict(base)
    merged.update(changes)
    return merged
