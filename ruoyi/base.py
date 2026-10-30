"""API 对象基类。

所有接口封装继承它，只做三件事：
1. 拼路径；
2. 调 HttpClient；
3. 返回 ApiResponse（**不做断言**）。

断言放在用例里，不放在 API 层。原因：API 层一旦内建断言，
就无法再用同一个方法去测"失败路径"——你会被迫写 `create_user_raw` 之类的
重复方法。这也正是原项目 `APIClient.login()` 里塞 `assert` 的坏处。
"""

from __future__ import annotations

from typing import Any, Mapping

from framework.http import ApiResponse, HttpClient


class BaseAPI:
    prefix: str = ""

    def __init__(self, http: HttpClient) -> None:
        self.http = http

    # ---- 路径 ----
    def _path(self, suffix: str = "") -> str:
        base = f"/{self.prefix.strip('/')}" if self.prefix else ""
        if not suffix:
            return base or "/"
        return f"{base}/{suffix.lstrip('/')}"

    @staticmethod
    def _ids(*values: int | str) -> str:
        """RuoYi 的批量删除用逗号拼接主键：/system/user/1,2,3"""
        return ",".join(str(value) for value in values)

    # ---- 通用请求 ----
    def get(self, suffix: str = "", **kwargs: Any) -> ApiResponse:
        return self.http.get(self._path(suffix), **kwargs)

    def post(self, suffix: str = "", **kwargs: Any) -> ApiResponse:
        return self.http.post(self._path(suffix), **kwargs)

    def put(self, suffix: str = "", **kwargs: Any) -> ApiResponse:
        return self.http.put(self._path(suffix), **kwargs)

    def delete(self, suffix: str = "", **kwargs: Any) -> ApiResponse:
        return self.http.delete(self._path(suffix), **kwargs)


def page_params(page_num: int = 1, page_size: int = 10, **filters: Any) -> dict[str, Any]:
    """RuoYi 分页参数是 pageNum/pageSize 驼峰，且过滤条件为空时不应出现在 query 里。"""
    params: dict[str, Any] = {"pageNum": page_num, "pageSize": page_size}
    for key, value in filters.items():
        if value is not None and value != "":
            params[key] = value
    return params


def as_body(payload: Mapping[str, Any]) -> dict[str, Any]:
    return dict(payload)
