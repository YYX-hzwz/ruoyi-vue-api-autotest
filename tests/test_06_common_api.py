"""公共接口：字典、参数、公告、菜单树、部门树。

这些接口通常被前端多个页面复用，改动影响面大，但很少被单独测试——
属于"越基础越容易被漏测"的典型。
"""

from __future__ import annotations

import pytest

from framework.assertions import expect_biz_error, expect_ok, expect_schema
from ruoyi import schemas
from ruoyi.constants import DICT_NORMAL_DISABLE, DICT_USER_SEX


def test_dict_data_structure(system_api) -> None:
    payload = expect_schema(system_api.dict_data(DICT_NORMAL_DISABLE), schemas.DICT_DATA)
    values = {item["dictValue"] for item in payload["data"]}
    assert values == {"0", "1"}, f"sys_normal_disable 应只有 0/1，实际 {values}"


def test_dict_data_labels(system_api) -> None:
    payload = system_api.dict_data(DICT_NORMAL_DISABLE).json
    labels = {item["dictLabel"] for item in payload["data"]}
    assert {"正常", "停用"} <= labels


@pytest.mark.parametrize("dict_type", [DICT_USER_SEX, "sys_yes_no"], ids=["user-sex", "yes-no"])
def test_multiple_dict_types(system_api, dict_type: str) -> None:
    payload = expect_schema(system_api.dict_data(dict_type), schemas.DICT_DATA)
    assert payload["data"], f"{dict_type} 不应为空"


def test_unknown_dict_type_rejected(system_api) -> None:
    expect_biz_error(system_api.dict_data("not_exist_dict_type"), msg_contains="不存在")


def test_config_list_structure(system_api) -> None:
    payload = expect_schema(system_api.config_list(), schemas.CONFIG_PAGE)
    assert payload["total"] >= 1


def test_config_value_by_key(system_api) -> None:
    response = expect_ok(system_api.config_by_key("sys.user.initPassword"))
    assert response.msg, "RuoYi 把参数值放在 msg 字段里"


def test_unknown_config_key_rejected(system_api) -> None:
    expect_biz_error(system_api.config_by_key("no.such.key"), msg_contains="不存在")


def test_notice_list_structure(system_api) -> None:
    payload = expect_schema(system_api.notice_list(), schemas.NOTICE_PAGE)
    assert payload["total"] >= 1


def test_menu_list_returns_flat_menus(system_api) -> None:
    payload = expect_ok(system_api.menu_list()).json
    assert isinstance(payload["data"], list) and payload["data"]
    assert all("menuId" in menu and "menuName" in menu for menu in payload["data"])


def test_role_menu_tree_marks_granted_menus(system_api, role_factory) -> None:
    role = role_factory(menuIds=[1, 103, 104])
    payload = system_api.role_menu_tree(role.role_id).json
    checked = {int(value) for value in payload["data"]["checkedKeys"]}
    assert checked == {1, 103, 104}, "已授权菜单应被回显为勾选状态"
    assert payload["data"]["menus"], "菜单树不应为空"


def test_dept_list_structure(system_api) -> None:
    payload = expect_schema(system_api.dept_list(), schemas.DEPT_LIST)
    assert payload["data"]


def test_user_dept_tree_structure(user_api) -> None:
    payload = expect_schema(user_api.dept_tree(), schemas.DEPT_TREE)
    assert payload["data"]


def test_post_list_structure(system_api) -> None:
    payload = expect_schema(system_api.post_list(), schemas.POST_PAGE)
    assert payload["total"] >= 1


def test_role_option_select(role_api) -> None:
    payload = role_api.option_select().json
    assert payload["code"] == 200
    assert any(role["roleKey"] == "admin" for role in payload["data"])


def test_role_dept_tree_contract(role_api, role_factory) -> None:
    role = role_factory()
    payload = role_api.dept_tree(role.role_id).json
    assert payload["code"] == 200
    assert "checkedKeys" in (payload.get("data") or {})
