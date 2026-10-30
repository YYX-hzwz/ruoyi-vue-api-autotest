"""契约测试：不关心业务正确性，只关心"接口说话算不算数"。

和 `ruoyi/schemas.py` 的区别：
- schemas 校验**业务字段**（userId、roleKey 的取值/类型）；
- 这里校验**传输层信封**（Content-Type、code 类型、分页信封一致性）。

放在单独的 marker 下（`-m contract`）便于快速回归：
后端加了字段、改了序列化，这一类会最先红，且定位成本最低。
"""

from __future__ import annotations

from http import HTTPStatus

import pytest

from framework.schema import S, validate

pytestmark = pytest.mark.contract

# 管理员应当能成功访问的只读接口
READ_ENDPOINTS = [
    ("getInfo", "/getInfo"),
    ("getRouters", "/getRouters"),
    ("用户列表", "/system/user/list?pageNum=1&pageSize=1"),
    ("角色列表", "/system/role/list?pageNum=1&pageSize=1"),
    ("参数列表", "/system/config/list?pageNum=1&pageSize=1"),
    ("公告列表", "/system/notice/list?pageNum=1&pageSize=1"),
    ("菜单列表", "/system/menu/list"),
    ("部门列表", "/system/dept/list"),
    ("岗位列表", "/system/post/list"),
    ("字典数据", "/system/dict/data/type/sys_normal_disable"),
    ("字典类型", "/system/dict/type/list"),
    ("用户部门树", "/system/user/deptTree"),
    ("角色下拉", "/system/role/optionselect"),
]


@pytest.mark.parametrize(("name", "path"), READ_ENDPOINTS, ids=[name for name, _ in READ_ENDPOINTS])
def test_response_envelope(admin_http, name: str, path: str) -> None:
    response = admin_http.get(path)

    assert response.status_code == HTTPStatus.OK, f"{name} HTTP {response.status_code}"
    assert "application/json" in response.content_type, (
        f"{name} 的 Content-Type 不是 JSON：{response.content_type!r}"
    )

    errors = validate(response.json, {"code": S.int(enum=[200]), "msg": S.str()})
    assert not errors, f"{name} 信封不合法：{errors}"


PAGED_ENDPOINTS = [
    ("用户", "/system/user/list"),
    ("角色", "/system/role/list"),
    ("参数", "/system/config/list"),
    ("公告", "/system/notice/list"),
    ("岗位", "/system/post/list"),
]


@pytest.mark.parametrize(("name", "path"), PAGED_ENDPOINTS, ids=[name for name, _ in PAGED_ENDPOINTS])
def test_pagination_envelope_is_consistent(admin_http, name: str, path: str) -> None:
    """所有分页接口必须是同一套信封：total(int) + rows(list)。

    信封不一致意味着前端要为每个模块写一套解析逻辑，
    对自动化来说则意味着"每条用例都要单独适配"，维护成本翻倍。
    """
    payload = admin_http.get(f"{path}?pageNum=1&pageSize=2").json
    errors = validate(payload, {"total": S.int(ge=0), "rows": S.list_of(S.any())})
    assert not errors, f"{name} 分页信封不一致：{errors}"


def test_error_envelope(admin_http) -> None:
    """业务错误也必须是同一套信封，否则前端无法统一提示。"""
    response = admin_http.get("/system/user/999999")
    errors = validate(response.json, {"code": S.int(), "msg": S.str(min_len=1)})
    assert not errors, f"错误信封不合法：{errors}"


def test_unauthorized_envelope(anonymous) -> None:
    response = anonymous.get("/getInfo")
    errors = validate(response.json, {"code": S.int(enum=[401]), "msg": S.str(min_len=1)})
    assert not errors, f"401 信封不合法：{errors}"


def test_json_charset_preserves_chinese(admin_http) -> None:
    """中文不能变成 \\uXXXX 之外的乱码，也不能被截断。

    RuoYi 默认序列化会把中文转义成 \\uXXXX，这是合法 JSON；
    真正要防的是编码错乱导致前端显示问号。
    """
    payload = admin_http.get("/getInfo").json
    assert payload["user"]["nickName"], "昵称不应为空"
    assert "\ufffd" not in payload["user"]["nickName"], "出现替换字符，编码链路有问题"
