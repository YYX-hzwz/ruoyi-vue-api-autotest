"""认证接口。"""

from __future__ import annotations

from framework.http import ApiResponse, HttpClient
from framework.settings import SETTINGS, Settings

from . import captcha
from .base import BaseAPI


class AuthAPI(BaseAPI):
    """登录、登出、当前用户信息。"""

    prefix = ""

    def __init__(self, http: HttpClient, settings: Settings | None = None) -> None:
        super().__init__(http)
        self.settings = settings or SETTINGS

    # ---- 验证码 ----
    def captcha_image(self) -> ApiResponse:
        return self.http.get("/captchaImage")

    # ---- 登录 ----
    def login(
        self,
        username: str | None = None,
        password: str | None = None,
        *,
        apply_token: bool = True,
    ) -> ApiResponse:
        """登录。成功时自动把 token 注入 HttpClient。

        `apply_token=False` 用于"错误口令"这类负向用例：不能让失败响应的
        空 token 覆盖掉当前客户端已有的凭据。
        """
        code, uuid = captcha.resolve(self.http, self.settings)
        payload = {
            "username": username if username is not None else self.settings.admin_user,
            "password": password if password is not None else self.settings.admin_pass,
            "code": code,
            "uuid": uuid,
        }
        response = self.http.post("/login", json_body=payload)
        if apply_token and response.code == 200:
            token = response.get("token")
            if isinstance(token, str) and token:
                self.http.set_token(token)
                self.http.on_unauthorized = self._relogin
        return response

    def _relogin(self) -> None:
        """401 时由 HttpClient 回调，重放请求前重新拿 token。"""
        self.http.set_token(None)
        response = self.login()
        if response.code != 200:
            raise RuntimeError(f"自动重新登录失败：{response.msg!r}")

    def authenticate(self) -> str:
        """登录并返回 token；失败直接抛错（供 fixture 使用）。"""
        response = self.login()
        token = response.get("token")
        if response.code != 200 or not token:
            raise RuntimeError(
                "管理员登录失败，后续用例无法执行。\n"
                f"  target={self.settings.target} base_url={self.http.base_url}\n"
                f"  HTTP {response.status_code} msg={response.msg!r}\n"
                f"  body={response.text[:400]}"
            )
        return token

    def logout(self) -> ApiResponse:
        return self.http.post("/logout")

    # ---- 当前用户 ----
    def get_info(self) -> ApiResponse:
        return self.http.get("/getInfo")

    def get_routers(self) -> ApiResponse:
        return self.http.get("/getRouters")


def login_as(
    http: HttpClient,
    username: str,
    password: str,
    settings: Settings | None = None,
) -> ApiResponse:
    """用一个独立 HttpClient 以指定账号登录（不污染管理员会话）。"""
    settings = settings or SETTINGS
    code, uuid = captcha.resolve(http, settings)
    return http.post(
        "/login",
        json_body={
            "username": username,
            "password": password,
            "code": code,
            "uuid": uuid,
        },
    )
