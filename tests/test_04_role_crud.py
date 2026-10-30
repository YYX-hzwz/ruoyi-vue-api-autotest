"""角色管理：CRUD、唯一性、状态、数据范围、菜单授权。"""

from __future__ import annotations

import pytest

from framework.assertions import expect_biz_error, expect_list_page, expect_ok, expect_schema
from ruoyi import schemas
from ruoyi.constants import ADMIN_ROLE_ID, DATA_SCOPE_DEPT_AND_CHILD, MSG_NOT_ALLOW_ADMIN_ROLE
from ruoyi.factories import minimal_role, role_payload

IN_USE_MSG = "已分配"


# --------------------------------------------------------------------------
# 查询
# --------------------------------------------------------------------------
def test_role_list_structure(role_api) -> None:
    expect_schema(role_api.list(), schemas.ROLE_PAGE)


def test_role_list_pagination_is_effective(role_api) -> None:
    """至少需要 2 个角色才能验证翻页；桩与 RuoYi 初始化数据都满足。"""
    rows = expect_list_page(role_api.list(page_num=1, page_size=1), expected_size=1)
    assert len(rows) == 1


def test_role_search_by_key(role_api, role_factory) -> None:
    role = role_factory()
    rows = role_api.list(role_key=role.payload["roleKey"]).rows
    assert [row["roleId"] for row in rows] == [role.role_id]


def test_role_detail_contract(role_api, role_factory) -> None:
    role = role_factory()
    payload = expect_schema(role_api.get(role.role_id), schemas.ROLE_DETAIL)
    assert payload["data"]["roleKey"] == role.payload["roleKey"]


def test_role_not_found(role_api) -> None:
    expect_biz_error(role_api.get(999_999), msg_contains="角色不存在")


# --------------------------------------------------------------------------
# 写操作
# --------------------------------------------------------------------------
def test_create_role_roundtrip(role_api, role_factory) -> None:
    role = role_factory()
    detail = role_api.get(role.role_id).json["data"]
    assert detail["roleName"] == role.payload["roleName"]
    assert detail["roleSort"] == role.payload["roleSort"]


def test_update_role_persists(role_api, role_factory) -> None:
    role = role_factory()
    new_name = "改名后的角色"
    expect_ok(role_api.update({**role.payload, "roleId": role.role_id, "roleName": new_name}))
    assert role_api.get(role.role_id).json["data"]["roleName"] == new_name


def test_update_nonexistent_role_rejected(role_api) -> None:
    payload = {**role_payload(), "roleId": 999_999}
    expect_biz_error(role_api.update(payload), msg_contains="角色不存在")


def test_delete_role_removes_it(role_api, role_factory) -> None:
    role = role_factory()
    expect_ok(role_api.delete(role.role_id))
    expect_biz_error(role_api.get(role.role_id), msg_contains="角色不存在")


def test_cannot_delete_super_admin_role(role_api) -> None:
    expect_biz_error(role_api.delete(ADMIN_ROLE_ID), msg_contains=MSG_NOT_ALLOW_ADMIN_ROLE)
    assert role_api.get(ADMIN_ROLE_ID).code == 200


def test_cannot_delete_role_assigned_to_user(role_api, role_factory, user_factory) -> None:
    """角色的删除必须校验引用关系，否则用户会挂着不存在的角色。"""
    role = role_factory()
    user_factory(roleIds=[role.role_id])

    expect_biz_error(role_api.delete(role.role_id), msg_contains=IN_USE_MSG)


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"roleName": ""}, "角色名称不能为空"),
        ({"roleKey": ""}, "权限字符不能为空"),
        ({"roleSort": None}, "角色顺序不能为空"),
    ],
    ids=["empty-name", "empty-key", "null-sort"],
)
def test_role_required_fields(role_api, overrides: dict, expected: str) -> None:
    payload = minimal_role(**overrides)
    response = role_api.create(payload)
    try:
        expect_biz_error(response, msg_contains=expected)
    finally:
        if response.code == 200:
            from ruoyi.cleanup import delete_role_if_exists

            delete_role_if_exists(role_api, payload["roleKey"])


def test_duplicate_role_key_rejected(role_api, role_factory) -> None:
    existing = role_factory()
    payload = role_payload(roleKey=existing.payload["roleKey"])
    expect_biz_error(role_api.create(payload), msg_contains="角色权限已存在")


def test_duplicate_role_name_rejected(role_api, role_factory) -> None:
    existing = role_factory()
    payload = role_payload(roleName=existing.payload["roleName"])
    expect_biz_error(role_api.create(payload), msg_contains="角色名称已存在")


# --------------------------------------------------------------------------
# 状态与数据范围
# --------------------------------------------------------------------------
@pytest.mark.parametrize("status", ["0", "1"], ids=["enable", "disable"])
def test_change_role_status_persists(role_api, role_factory, status: str) -> None:
    role = role_factory()
    expect_ok(role_api.change_status(role.role_id, status))
    assert role_api.get(role.role_id).json["data"]["status"] == status


def test_cannot_disable_super_admin_role(role_api) -> None:
    expect_biz_error(role_api.change_status(ADMIN_ROLE_ID, "1"), msg_contains=MSG_NOT_ALLOW_ADMIN_ROLE)


def test_data_scope_persists(role_api, role_factory) -> None:
    role = role_factory()
    expect_ok(role_api.set_data_scope(role.role_id, DATA_SCOPE_DEPT_AND_CHILD, [103]))
    assert role_api.get(role.role_id).json["data"]["dataScope"] == DATA_SCOPE_DEPT_AND_CHILD
