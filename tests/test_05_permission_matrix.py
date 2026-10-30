"""权限矩阵：用"普通角色"账号横向扫一遍所有受控接口。

为什么值得单独一个文件
----------------------
原项目的越权用例只有 3 条，而且断言是 `code == 500 or status == 403`——
只要接口因为任何原因失败就算通过。它既不能证明"权限生效"，也不能证明
"权限失效"，等于白写。

这里的做法：
1. **矩阵化**：受控接口 × 期望（允许/拒绝），一眼能看出覆盖面缺口；
2. **区分 401 与 403**：未认证是 401，已认证但无权限是 403，
   两者混为一谈会掩盖"token 失效"这类真问题；
3. **区分根因**：403 必须是"没有权限"，不能是"参数校验失败"碰巧也是 403。
"""

from __future__ import annotations

from typing import Any, Callable

import pytest

from framework.assertions import expect_ok, expect_perm_denied, expect_unauthorized
from ruoyi.factories import role_payload, user_payload

pytestmark = pytest.mark.permission


# --------------------------------------------------------------------------
# 矩阵：普通角色的权限边界
# --------------------------------------------------------------------------
MatrixCall = Callable[[Any], Any]

MATRIX: list[tuple[str, MatrixCall, bool]] = [
    # 读接口
    ("用户详情", lambda s: s.api.get(1), False),
    ("角色列表", lambda s: s.roles.list(), False),
    ("菜单列表", lambda s: s.system.menu_list(), False),
    ("参数列表", lambda s: s.system.config_list(), False),
    ("公告列表", lambda s: s.system.notice_list(), False),
    ("字典类型列表", lambda s: s.system.dict_types(), True),
    # 写接口：用不存在的主键，确保"即使权限判断失效也不会破坏数据"
    ("删除用户", lambda s: s.api.delete(999_999), False),
    ("创建用户", lambda s: s.api.create(user_payload()), False),
    ("创建角色", lambda s: s.roles.create(role_payload()), False),
    # 普通角色被授予的权限
    ("字典数据", lambda s: s.system.dict_data("sys_normal_disable"), True),
    ("部门列表", lambda s: s.system.dept_list(), True),
    ("岗位列表", lambda s: s.system.post_list(), True),
    ("当前用户信息", lambda s: s.auth.get_info(), True),
    ("路由菜单", lambda s: s.auth.get_routers(), True),
]


@pytest.mark.parametrize(
    ("endpoint", "call", "allowed"),
    MATRIX,
    ids=[f"{'allow' if allowed else 'deny'}-{endpoint}" for endpoint, _, allowed in MATRIX],
)
def test_permission_matrix(normal_session, endpoint: str, call: MatrixCall, allowed: bool) -> None:
    response = call(normal_session)
    if allowed:
        expect_ok(response)
    else:
        expect_perm_denied(response)


# --------------------------------------------------------------------------
# 401 与 403 必须区分
# --------------------------------------------------------------------------
def test_unauthenticated_gets_401_not_403(anonymous) -> None:
    expect_unauthorized(anonymous.get("/system/user/list"))


def test_authenticated_without_permission_gets_403(normal_session) -> None:
    expect_perm_denied(normal_session.roles.list())


# --------------------------------------------------------------------------
# 越权提级与信息暴露
# --------------------------------------------------------------------------
def test_normal_user_cannot_escalate_to_admin_role(normal_session, user_api, admin_role_id: int) -> None:
    """最常见的提权路径：改自己的角色。

    断言先看"被拒绝"，再用**管理员视角**回查角色有没有被改。
    如果只用普通账号自己回查，查不到（403）反而会让断言"因为错误的原因通过"。
    """
    user_id = int(normal_session.user["userId"])
    expect_perm_denied(normal_session.api.assign_roles(user_id, [admin_role_id]))

    detail = user_api.auth_role_detail(user_id).json or {}
    role_ids = [int(value) for value in detail.get("roleIds", [])]
    assert admin_role_id not in role_ids, f"提权成功：角色被改为 {role_ids}"


def test_normal_user_permissions_have_no_wildcard(normal_session) -> None:
    payload = normal_session.auth.get_info().json
    assert "*:*:*" not in payload["permissions"], "普通角色不应拥有通配权限"
    assert payload["user"]["userId"] == normal_session.user["userId"]


def test_normal_user_routers_hide_admin_menus(normal_session) -> None:
    """菜单可见性与接口权限必须一致。

    如果"路由里没有用户管理、但接口能调通"，说明权限模型存在两套来源
    （菜单权限 vs 接口注解）且已经不一致——这正是 BUG-002 的排查线索。
    """
    payload = normal_session.auth.get_routers().json
    titles: list[str] = []

    def walk(nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            title = (node.get("meta") or {}).get("title")
            if title:
                titles.append(str(title))
            walk(node.get("children") or [])

    walk(payload.get("data") or [])
    assert "用户管理" not in titles
    assert "角色管理" not in titles
