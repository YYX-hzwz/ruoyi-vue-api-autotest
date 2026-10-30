"""用户管理：CRUD、查询、分页、唯一性。

这里的每条用例都尽量做到"有副作用校验"：
写接口返回 200 之后，一定再读一次，确认数据真的变了。
只断言 `code == 200` 的用例，无法发现"返回成功但没落库"这类缺陷。
"""

from __future__ import annotations

import pytest

from framework.assertions import (
    expect_biz_error,
    expect_list_page,
    expect_ok,
    expect_schema,
)
from ruoyi import schemas
from ruoyi.constants import (
    ADMIN_USER_ID,
    MSG_DUP_EMAIL,
    MSG_DUP_PHONE,
    MSG_DUP_USERNAME,
    MSG_NOT_ALLOW_ADMIN_USER,
    STATUS_DISABLED,
    STATUS_NORMAL,
)
from ruoyi.factories import user_payload


# --------------------------------------------------------------------------
# 查询
# --------------------------------------------------------------------------
def test_user_list_structure(user_api) -> None:
    payload = expect_schema(user_api.list(page_num=1, page_size=10), schemas.USER_PAGE)
    assert payload["total"] >= 1, "初始化数据里至少有 admin 用户"


def test_user_list_pagination_is_effective(user_api) -> None:
    """分页测试必须能发现"后端忽略 pageSize"。

    老写法 `len(rows) <= page_size` 是假断言：后端返回全部数据时它依然成立。
    正确做法是同时校验 total 与页面长度的关系。
    """
    rows = expect_list_page(user_api.list(page_num=1, page_size=2), expected_size=2)
    assert len(rows) == 2, "total 大于 2 时应返回满页"


def test_user_list_second_page_differs_from_first(user_api) -> None:
    first = {row["userId"] for row in user_api.list(page_num=1, page_size=1).rows}
    second = {row["userId"] for row in user_api.list(page_num=2, page_size=1).rows}
    assert first and second, "至少需要 2 个用户才能验证翻页"
    assert first.isdisjoint(second), f"第 1 页与第 2 页出现重复数据: {first & second}"


def test_search_by_username_returns_exact_match(user_api, user_factory) -> None:
    record = user_factory(nickName="精确搜索目标")
    rows = user_api.list(user_name=record.user_name).rows
    assert [row["userId"] for row in rows] == [record.user_id]


def test_search_by_status_filters(user_api, user_factory) -> None:
    disabled = user_factory()
    expect_ok(user_api.change_status(disabled.user_id, STATUS_DISABLED))

    rows = user_api.list(status=STATUS_DISABLED, page_size=50).rows
    assert rows, "应至少有一个停用用户"
    assert all(row["status"] == STATUS_DISABLED for row in rows)


def test_search_by_unknown_name_returns_empty(user_api) -> None:
    response = user_api.list(user_name="definitely_no_such_user_at_all")
    expect_ok(response)
    assert response.rows == []
    assert response.total == 0


# --------------------------------------------------------------------------
# 写操作 + 副作用校验
# --------------------------------------------------------------------------
def test_create_user_roundtrip(user_api, user_factory) -> None:
    record = user_factory()
    detail = expect_schema(user_api.get(record.user_id), schemas.USER_DETAIL)

    assert detail["data"]["userName"] == record.user_name
    assert detail["data"]["nickName"] == record.payload["nickName"]
    assert detail["roleIds"] == record.payload["roleIds"]


def test_update_user_persists(user_api, user_factory) -> None:
    record = user_factory()
    nickname = "更新后的昵称"

    expect_ok(user_api.update({**record.payload, "userId": record.user_id, "nickName": nickname}))
    assert user_api.get(record.user_id).json["data"]["nickName"] == nickname


def test_update_nonexistent_user_rejected(user_api) -> None:
    payload = user_payload()
    payload["userId"] = 999_999
    expect_biz_error(user_api.update(payload))


def test_delete_user_removes_it(user_api, user_factory) -> None:
    record = user_factory()
    expect_ok(user_api.delete(record.user_id))

    assert user_api.list(user_name=record.user_name).rows == []
    expect_biz_error(user_api.get(record.user_id), msg_contains="用户不存在")


def test_delete_nonexistent_user_rejected(user_api) -> None:
    expect_biz_error(user_api.delete(999_999))


def test_cannot_delete_super_admin(user_api) -> None:
    """破坏性操作必须落在"期望被拒绝"的断言上，而不是赌它成功。

    原项目直接 `DELETE /system/user/1`，然后断言 500——它无法区分
    "被权限拦住"和"被业务规则拦住"，一旦权限真的失效就会删掉管理员。
    """
    expect_biz_error(user_api.delete(ADMIN_USER_ID), msg_contains=MSG_NOT_ALLOW_ADMIN_USER)

    # 反向确认：管理员还在
    assert user_api.get(ADMIN_USER_ID).code == 200


# --------------------------------------------------------------------------
# 唯一约束
# --------------------------------------------------------------------------
def test_duplicate_username_rejected(user_api, user_factory) -> None:
    existing = user_factory()
    payload = user_payload(userName=existing.user_name)
    expect_biz_error(user_api.create(payload), msg_contains=MSG_DUP_USERNAME)


def test_duplicate_phone_rejected(user_api, user_factory) -> None:
    existing = user_factory()
    payload = user_payload(phonenumber=existing.payload["phonenumber"])
    expect_biz_error(user_api.create(payload), msg_contains=MSG_DUP_PHONE)


def test_duplicate_email_rejected(user_api, user_factory) -> None:
    existing = user_factory()
    payload = user_payload(email=existing.payload["email"])
    expect_biz_error(user_api.create(payload), msg_contains=MSG_DUP_EMAIL)


# --------------------------------------------------------------------------
# 状态
# --------------------------------------------------------------------------
@pytest.mark.parametrize("status", [STATUS_DISABLED, STATUS_NORMAL], ids=["disable", "enable"])
def test_change_status_persists(user_api, user_factory, status: str) -> None:
    record = user_factory()
    expect_ok(user_api.change_status(record.user_id, status))
    assert user_api.get(record.user_id).json["data"]["status"] == status


def test_cannot_disable_super_admin(user_api) -> None:
    expect_biz_error(
        user_api.change_status(ADMIN_USER_ID, STATUS_DISABLED),
        msg_contains=MSG_NOT_ALLOW_ADMIN_USER,
    )
