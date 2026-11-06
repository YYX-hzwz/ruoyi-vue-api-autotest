"""清理辅助。

用例里"故意构造非法数据"时，如果缺陷存在，数据可能真的被写进去了。
异常路径用例自带兜底清理，避免每次执行在数据库中残留数据。
"""

from __future__ import annotations

from framework.logger import get_logger

from .user import UserAPI

logger = get_logger("cleanup")


def delete_user_if_exists(user_api: UserAPI, user_name: str) -> bool:
    """按用户名删除，找不到就当已清理。用于"负向用例意外成功"的兜底。"""
    try:
        rows = user_api.list(user_name=user_name, page_size=50).rows
        target = next((row for row in rows if row.get("userName") == user_name), None)
        if target is None:
            return False
        response = user_api.delete(int(target["userId"]))
        if response.code != 200:
            logger.warning("兜底清理用户 %s 失败: %s", user_name, response.msg)
            return False
        return True
    except Exception as exc:  # noqa: BLE001 - 清理永远不能掩盖用例本身的失败
        logger.warning("兜底清理用户 %s 异常: %r", user_name, exc)
        return False


def delete_role_if_exists(role_api, role_key: str) -> bool:
    try:
        rows = role_api.list(role_key=role_key, page_size=50).rows
        target = next((row for row in rows if row.get("roleKey") == role_key), None)
        if target is None:
            return False
        response = role_api.delete(int(target["roleId"]))
        if response.code != 200:
            logger.warning("兜底清理角色 %s 失败: %s", role_key, response.msg)
            return False
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("兜底清理角色 %s 异常: %r", role_key, exc)
        return False
