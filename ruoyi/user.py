"""用户管理接口。

字段名严格对齐 RuoYi-Vue 3.8.x 的 `SysUserController`。
改动这里之前先确认后端版本，别用猜的。
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from framework.http import ApiResponse

from .base import BaseAPI, page_params


class UserAPI(BaseAPI):
    prefix = "system/user"

    # ---- 查询 ----
    def list(
        self,
        page_num: int = 1,
        page_size: int = 10,
        *,
        user_name: str | None = None,
        phonenumber: str | None = None,
        status: str | None = None,
        dept_id: int | None = None,
        begin_time: str | None = None,
        end_time: str | None = None,
    ) -> ApiResponse:
        params = page_params(
            page_num,
            page_size,
            userName=user_name,
            phonenumber=phonenumber,
            status=status,
            deptId=dept_id,
            beginTime=begin_time,
            endTime=end_time,
        )
        return self.http.get(self._path("list"), params=params)

    def get(self, user_id: int) -> ApiResponse:
        return self.http.get(self._path(str(user_id)))

    def auth_role_detail(self, user_id: int) -> ApiResponse:
        return self.http.get(self._path(f"authRole/{user_id}"))

    def dept_tree(self) -> ApiResponse:
        return self.http.get(self._path("deptTree"))

    # ---- 写操作 ----
    def create(self, payload: Mapping[str, Any]) -> ApiResponse:
        return self.http.post(self._path(), json_body=dict(payload))

    def update(self, payload: Mapping[str, Any]) -> ApiResponse:
        return self.http.put(self._path(), json_body=dict(payload))

    def delete(self, *user_ids: int) -> ApiResponse:  # type: ignore[override]
        return self.http.delete(self._path(self._ids(*user_ids)))

    def reset_password(self, user_id: int, password: str) -> ApiResponse:
        return self.http.put(
            self._path("resetPwd"),
            json_body={"userId": user_id, "password": password},
        )

    def change_status(self, user_id: int, status: str) -> ApiResponse:
        return self.http.put(
            self._path("changeStatus"),
            json_body={"userId": user_id, "status": status},
        )

    def assign_roles(self, user_id: int, role_ids: Sequence[int]) -> ApiResponse:
        """分配角色。

        注意 RuoYi 的签名是 `insertAuthRole(Long userId, Long[] roleIds)`，
        没有 `@RequestBody`，Spring 从 **query string** 绑定。
        用 JSON body 调这个接口在标准实现上会 400/500——
        原项目就是这么调的，却断言 200 通过，说明它跑的不是标准 RuoYi。
        """
        params: dict[str, Any] = {"userId": user_id}
        if role_ids:
            # RuoYi 侧是 Long[]，重复键是 Spring 的标准绑定方式
            params["roleIds"] = ",".join(str(item) for item in role_ids)
        return self.http.put(self._path("authRole"), params=params)
