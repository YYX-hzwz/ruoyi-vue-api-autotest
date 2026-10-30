"""系统基础数据接口：字典、参数、公告、菜单、部门、岗位。

这些接口通常是"其他业务的前置条件"，单独提供一个 API 对象，
避免用例里到处手拼 URL。
"""

from __future__ import annotations

from framework.http import ApiResponse

from .base import BaseAPI, page_params


class SystemAPI(BaseAPI):
    prefix = "system"

    # ---- 字典 ----
    def dict_data(self, dict_type: str) -> ApiResponse:
        return self.http.get(self._path(f"dict/data/type/{dict_type}"))

    def dict_types(self, page_num: int = 1, page_size: int = 10) -> ApiResponse:
        return self.http.get(self._path("dict/type/list"), params=page_params(page_num, page_size))

    # ---- 参数配置 ----
    def config_list(self, page_num: int = 1, page_size: int = 5, config_key: str | None = None) -> ApiResponse:
        return self.http.get(
            self._path("config/list"),
            params=page_params(page_num, page_size, configKey=config_key),
        )

    def config_by_key(self, config_key: str) -> ApiResponse:
        return self.http.get(self._path(f"config/configKey/{config_key}"))

    # ---- 通知公告 ----
    def notice_list(self, page_num: int = 1, page_size: int = 5) -> ApiResponse:
        return self.http.get(self._path("notice/list"), params=page_params(page_num, page_size))

    # ---- 菜单 ----
    def menu_list(self) -> ApiResponse:
        return self.http.get(self._path("menu/list"))

    def menu_tree(self) -> ApiResponse:
        return self.http.get(self._path("menu/treeselect"))

    def role_menu_tree(self, role_id: int) -> ApiResponse:
        return self.http.get(self._path(f"menu/roleMenuTreeselect/{role_id}"))

    # ---- 部门 / 岗位 ----
    def dept_list(self) -> ApiResponse:
        return self.http.get(self._path("dept/list"))

    def post_list(self) -> ApiResponse:
        return self.http.get(self._path("post/list"))
