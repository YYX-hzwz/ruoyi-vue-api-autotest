"""用户管理：参数校验（等价类 + 边界值，数据驱动）。

参数化数据放在 `data/cases/user_validation.json`，用例代码只负责"执行 + 断言"。
好处：新增一条非法输入不用改代码，改数据即可——这也是面试里
"你的用例怎么扩展"的标准答案。

这里刻意**不**把缺陷写成通过：弱口令的相关用例在 test_08_defects.py，
以 xfail 形式存在。
"""

from __future__ import annotations

from typing import Any

import pytest

from framework.assertions import expect_biz_error, expect_ok
from framework.data import load_cases, unique_name
from ruoyi.cleanup import delete_user_if_exists
from ruoyi.factories import user_payload

CASES = load_cases("cases/user_validation")


@pytest.mark.parametrize(
    "case",
    CASES,
    ids=[case["id"] for case in CASES],
)
def test_invalid_user_payload_rejected(user_api, case: dict[str, Any]) -> None:
    payload = user_payload(**case["overrides"])
    response = user_api.create(payload)
    try:
        expect_biz_error(response, msg_contains=case["expect"])
    finally:
        # 如果缺陷存在导致数据真的写进去了，这里兜底清理，不留垃圾
        if response.code == 200:
            delete_user_if_exists(user_api, payload["userName"])


# --------------------------------------------------------------------------
# 边界值：正好合法 / 超过 1
# --------------------------------------------------------------------------
def _exact_length_name(length: int) -> str:
    base = unique_name("u")
    return (base + "0123456789" * 4)[:length]


@pytest.mark.parametrize("length", [30, 31], ids=["30-accepted", "31-rejected"])
def test_username_length_boundary(user_api, length: int) -> None:
    payload = user_payload(userName=_exact_length_name(length))
    response = user_api.create(payload)
    try:
        if length <= 30:
            expect_ok(response)
        else:
            expect_biz_error(response, msg_contains="30")
    finally:
        if response.code == 200:
            delete_user_if_exists(user_api, payload["userName"])


@pytest.mark.parametrize("length", [30, 31], ids=["30-accepted", "31-rejected"])
def test_nickname_length_boundary(user_api, length: int) -> None:
    payload = user_payload(nickName="测" * length)
    response = user_api.create(payload)
    try:
        if length <= 30:
            expect_ok(response)
        else:
            expect_biz_error(response, msg_contains="30")
    finally:
        if response.code == 200:
            delete_user_if_exists(user_api, payload["userName"])


def test_email_length_over_limit_rejected(user_api) -> None:
    """51 字符邮箱：长度校验应优先于唯一性校验，且不能 500 崩溃。"""
    local = "a" * (51 - len("@example.com"))
    payload = user_payload(email=f"{local}@example.com")
    response = user_api.create(payload)
    try:
        expect_biz_error(response, msg_contains="50")
    finally:
        if response.code == 200:
            delete_user_if_exists(user_api, payload["userName"])


# --------------------------------------------------------------------------
# 注入类输入：不应导致 500，也不应被当成 SQL 片段执行
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "nickname",
    [
        "'; DROP TABLE sys_user; --",
        "<script>alert(1)</script>",
        "%_combined%",
        "emoji🧪测试",
    ],
    ids=["sql-injection", "xss", "like-wildcard", "emoji"],
)
def test_special_characters_are_stored_literally(user_api, nickname: str) -> None:
    """校验"特殊字符被原样存储"，而不是被拼接进 SQL 或直接导致 500。

    断言分两层：接口不 500；回读的昵称与写入完全一致（证明未被转义破坏）。
    """
    payload = user_payload(nickName=nickname)
    response = user_api.create(payload)
    try:
        expect_ok(response)
        detail = user_api.get(user_api.list(user_name=payload["userName"]).rows[0]["userId"])
        assert detail.json["data"]["nickName"] == nickname
    finally:
        if response.code == 200:
            delete_user_if_exists(user_api, payload["userName"])
