"""角色管理接口。"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from framework.http import ApiResponse

from .base import BaseAPI, page_params


class RoleAPI(BaseAPI):
    prefix = "system/role"

    # ---- 查询 ----
    def list(
        self,
        page_num: int = 1,
        page_size: int = 10,
        *,
        role_name: str | None = None,
        role_key: str | None = None,
        status: str | None = None,
    ) -> ApiResponse:
        params = page_params(
            page_num,
            page_size,
            roleName=role_name,
            roleKey=role_key,
            status=status,
        )
        return self.http.get(self._path("list"), params=params)

    def get(self, role_id: int) -> ApiResponse:
        return self.http.get(self._path(str(role_id)))

    def option_select(self) -> ApiResponse:
        return self.http.get(self._path("optionselect"))

    def dept_tree(self, role_id: int) -> ApiResponse:
        return self.http.get(self._path(f"deptTree/{role_id}"))

    # ---- 写操作 ----
    def create(self, payload: Mapping[str, Any]) -> ApiResponse:
        return self.http.post(self._path(), json_body=dict(payload))

    def update(self, payload: Mapping[str, Any]) -> ApiResponse:
        return self.http.put(self._path(), json_body=dict(payload))

    def delete(self, *role_ids: int) -> ApiResponse:  # type: ignore[override]
        return self.http.delete(self._path(self._ids(*role_ids)))

    def change_status(self, role_id: int, status: str) -> ApiResponse:
        return self.http.put(
            self._path("changeStatus"),
            json_body={"roleId": role_id, "status": status},
        )

    def set_data_scope(
        self,
        role_id: int,
        data_scope: str,
        dept_ids: Sequence[int] | None = None,
    ) -> ApiResponse:
        return self.http.put(
            self._path("dataScope"),
            json_body={
                "roleId": role_id,
                "dataScope": data_scope,
                "deptIds": list(dept_ids or []),
            },
        )
