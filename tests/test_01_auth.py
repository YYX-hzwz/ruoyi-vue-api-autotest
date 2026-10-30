"""认证模块：登录、登出、令牌、账号状态。

设计要点
--------
- 每条"失败路径"都断言 `msg` 文案，而不是只断言 `code != 200`。
  只比状态码的话，"权限不足 / 参数为空 / 数据库异常"三种截然不同的原因
  会都算通过——这是接口自动化里最常见的假通过。
- "改密码后要能登录"这类用例验证的是**副作用**，不是返回值。
"""

from __future__ import annotations

import pytest

from framework.assertions import (
    expect_biz_error,
    expect_ok,
    expect_schema,
    expect_unauthorized,
)
from framework.http import HttpClient
from framework.settings import SETTINGS
from ruoyi import AuthAPI, schemas
from ruoyi.auth import login_as
from ruoyi.constants import (
    MSG_BAD_CREDENTIALS,
    MSG_USER_DISABLED,
)


def test_admin_login_returns_token(admin_auth: AuthAPI) -> None:
    response = admin_auth.login()
    payload = expect_schema(response, schemas.LOGIN_OK)
    assert payload["token"], "登录成功但 token 为空"


def test_get_info_contract(admin_auth: AuthAPI) -> None:
    payload = expect_schema(admin_auth.get_info(), schemas.GET_INFO)
    assert payload["user"]["userName"] == SETTINGS.admin_user
    assert "*:*:*" in payload["permissions"], "超级管理员应拥有全部权限标识"


def test_get_routers_returns_menu_tree(admin_auth: AuthAPI) -> None:
    payload = expect_schema(admin_auth.get_routers(), schemas.ROUTERS)
    assert payload["data"], "管理员的路由不应为空"


def test_captcha_endpoint_contract(admin_auth: AuthAPI) -> None:
    payload = expect_schema(admin_auth.captcha_image(), schemas.CAPTCHA)
    if payload["captchaEnabled"]:
        assert payload["uuid"], "开启验证码时必须返回 uuid"


# --------------------------------------------------------------------------
# 失败路径
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("case_id", "username", "password", "expected_msg"),
    [
        ("错误口令", SETTINGS.admin_user, "definitely-wrong-pass", MSG_BAD_CREDENTIALS),
        ("用户不存在", "no_such_user_at", "whatever123", MSG_BAD_CREDENTIALS),
    ],
    ids=["wrong-password", "unknown-user"],
)
def test_login_rejects_invalid_credentials(
    anonymous: HttpClient,
    case_id: str,
    username: str,
    password: str,
    expected_msg: str,
) -> None:
    response = login_as(anonymous, username, password, SETTINGS)
    expect_biz_error(response, msg_contains=expected_msg)


@pytest.mark.parametrize(
    ("username", "password"),
    [("", SETTINGS.admin_pass), (SETTINGS.admin_user, "")],
    ids=["empty-username", "empty-password"],
)
def test_login_rejects_empty_credentials(
    anonymous: HttpClient,
    username: str,
    password: str,
) -> None:
    """空凭据绝不能换到 token。

    RuoYi 对空 username 的处理是"查不到用户 → 用户不存在/密码错误"，
    而不是参数校验失败，所以这里只断言"业务失败且没有 token"，
    不绑定具体文案——否则换一个版本就会误报。
    """
    response = login_as(anonymous, username, password, SETTINGS)
    expect_biz_error(response)
    assert not (response.json or {}).get("token"), "空凭据不应换到 token"


def test_access_without_token_is_unauthorized(anonymous: HttpClient) -> None:
    expect_unauthorized(anonymous.get("/getInfo"))


def test_access_with_forged_token_is_unauthorized(anonymous: HttpClient) -> None:
    anonymous.set_token("forged-token-that-does-not-exist")
    expect_unauthorized(anonymous.get("/getInfo"))


def test_logout_invalidates_token(base_url: str) -> None:
    """登出必须让旧 token 立刻失效，否则等同"退出登录不生效"。"""
    http = HttpClient(base_url)
    try:
        response = login_as(http, SETTINGS.admin_user, SETTINGS.admin_pass, SETTINGS)
        expect_ok(response)
        http.set_token(str(response.get("token")))

        expect_ok(AuthAPI(http).logout())
        expect_unauthorized(http.get("/getInfo"))
    finally:
        http.close()


# --------------------------------------------------------------------------
# 账号状态与口令
# --------------------------------------------------------------------------
def test_disabled_user_cannot_login(
    base_url: str,
    user_api,
    user_factory,
) -> None:
    record = user_factory()
    expect_ok(user_api.change_status(record.user_id, "1"), msg_contains="成功")

    http = HttpClient(base_url)
    try:
        response = login_as(http, record.user_name, record.password, SETTINGS)
        expect_biz_error(response, msg_contains=MSG_USER_DISABLED)
    finally:
        http.close()


def test_reset_password_takes_effect(base_url: str, user_api, user_factory) -> None:
    """验证的是副作用：新口令可用、旧口令失效。"""
    record = user_factory()
    new_password = "NewPass@2026"

    expect_ok(user_api.reset_password(record.user_id, new_password))

    with_new = HttpClient(base_url)
    with_old = HttpClient(base_url)
    try:
        expect_ok(login_as(with_new, record.user_name, new_password, SETTINGS))
        expect_biz_error(login_as(with_old, record.user_name, record.password, SETTINGS))
    finally:
        with_new.close()
        with_old.close()


def test_created_user_can_login(base_url: str, user_factory) -> None:
    """接口返回 200 不等于账号真的可登录——必须实测一次登录链路。"""
    record = user_factory()
    http = HttpClient(base_url)
    try:
        expect_ok(login_as(http, record.user_name, record.password, SETTINGS))
    finally:
        http.close()
