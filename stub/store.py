"""契约桩的内存数据层。

数据按 RuoYi 初始化 SQL（ry_*.sql）的种子数据构造，字段名与后端实体一致，
这样"对着桩写出来的用例"换到真后端不需要改字段名。

只用内存 + 一把锁：桩的定位是"离线联调与 CI 冒烟"，不是高并发压测目标。
"""

from __future__ import annotations

import itertools
import re
import threading
from datetime import datetime
from typing import Any

from ruoyi.constants import (
    ADMIN_DEPT_ID,
    ADMIN_POST_ID,
    ADMIN_ROLE_ID,
    ADMIN_USER_ID,
    COMMON_ROLE_ID,
)

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Store:
    """最小可用的 RuoYi 数据仓库。"""

    def __init__(self) -> None:
        self.lock = threading.RLock()
        self._seed()

    # ------------------------------------------------------------------
    # 种子数据
    # ------------------------------------------------------------------
    def _seed(self) -> None:
        self.users: list[dict[str, Any]] = [
            {
                "userId": ADMIN_USER_ID,
                "deptId": ADMIN_DEPT_ID,
                "userName": "admin",
                "nickName": "若依",
                "email": "ry@163.com",
                "phonenumber": "15888888888",
                "sex": "1",
                "avatar": "",
                "password": "admin123",
                "status": "0",
                "delFlag": "0",
                "createTime": "2024-01-01 00:00:00",
                "remark": "管理员",
                "roleIds": [ADMIN_ROLE_ID],
                "postIds": [1],
            },
            {
                "userId": 2,
                "deptId": 105,
                "userName": "ry",
                "nickName": "若依",
                "email": "ry@qq.com",
                "phonenumber": "15666666666",
                "sex": "1",
                "avatar": "",
                "password": "admin123",
                "status": "0",
                "delFlag": "0",
                "createTime": "2024-01-01 00:00:00",
                "remark": "普通用户",
                "roleIds": [COMMON_ROLE_ID],
                "postIds": [2],
            },
        ]

        self.roles: list[dict[str, Any]] = [
            {
                "roleId": ADMIN_ROLE_ID,
                "roleName": "超级管理员",
                "roleKey": "admin",
                "roleSort": 1,
                "dataScope": "1",
                "menuCheckStrictly": True,
                "deptCheckStrictly": True,
                "status": "0",
                "delFlag": "0",
                "createTime": "2024-01-01 00:00:00",
                "remark": "超级管理员",
                "menuIds": [1],
            },
            {
                "roleId": COMMON_ROLE_ID,
                "roleName": "普通角色",
                "roleKey": "common",
                "roleSort": 2,
                "dataScope": "2",
                "menuCheckStrictly": True,
                "deptCheckStrictly": True,
                "status": "0",
                "delFlag": "0",
                "createTime": "2024-01-01 00:00:00",
                "remark": "普通角色",
                # 刻意只给"部门/岗位/字典"权限：用来验证越权拦截
                "menuIds": [1, 103, 104, 105],
            },
        ]

        self.menus: list[dict[str, Any]] = [
            self._menu(1, "系统管理", 0, 1, "system", None, "M", "", "system"),
            self._menu(100, "用户管理", 1, 1, "user", "system/user/index", "C", "system:user:list", "user"),
            self._menu(101, "角色管理", 1, 2, "role", "system/role/index", "C", "system:role:list", "peoples"),
            self._menu(102, "菜单管理", 1, 3, "menu", "system/menu/index", "C", "system:menu:list", "tree-table"),
            self._menu(103, "部门管理", 1, 4, "dept", "system/dept/index", "C", "system:dept:list", "tree"),
            self._menu(104, "岗位管理", 1, 5, "post", "system/post/index", "C", "system:post:list", "post"),
            self._menu(105, "字典管理", 1, 6, "dict", "system/dict/index", "C", "system:dict:list", "dict"),
            self._menu(106, "参数设置", 1, 7, "config", "system/config/index", "C", "system:config:list", "edit"),
            self._menu(107, "通知公告", 1, 8, "notice", "system/notice/index", "C", "system:notice:list", "message"),
        ]

        self.depts: list[dict[str, Any]] = [
            {"deptId": 100, "parentId": 0, "ancestors": "0", "deptName": "若依科技", "orderNum": 0, "leader": "若依", "phone": "15888888888", "email": "ry@qq.com", "status": "0"},
            {"deptId": 101, "parentId": 100, "ancestors": "0,100", "deptName": "深圳总公司", "orderNum": 1, "leader": "若依", "phone": "15888888888", "email": "ry@qq.com", "status": "0"},
            {"deptId": 103, "parentId": 101, "ancestors": "0,100,101", "deptName": "研发部门", "orderNum": 1, "leader": "若依", "phone": "15888888888", "email": "ry@qq.com", "status": "0"},
            {"deptId": 105, "parentId": 101, "ancestors": "0,100,101", "deptName": "测试部门", "orderNum": 2, "leader": "若依", "phone": "15888888888", "email": "ry@qq.com", "status": "0"},
        ]

        self.posts: list[dict[str, Any]] = [
            {"postId": 1, "postCode": "ceo", "postName": "董事长", "postSort": 1, "status": "0"},
            {"postId": 2, "postCode": "se", "postName": "项目经理", "postSort": 2, "status": "0"},
            {"postId": 3, "postCode": "hr", "postName": "人力资源", "postSort": 3, "status": "0"},
            {"postId": 4, "postCode": "user", "postName": "普通员工", "postSort": 4, "status": "0"},
        ]

        self.dicts: dict[str, list[dict[str, Any]]] = {
            "sys_normal_disable": [
                {"dictLabel": "正常", "dictValue": "0", "dictType": "sys_normal_disable", "dictSort": 1, "status": "0"},
                {"dictLabel": "停用", "dictValue": "1", "dictType": "sys_normal_disable", "dictSort": 2, "status": "0"},
            ],
            "sys_user_sex": [
                {"dictLabel": "男", "dictValue": "0", "dictType": "sys_user_sex", "dictSort": 1, "status": "0"},
                {"dictLabel": "女", "dictValue": "1", "dictType": "sys_user_sex", "dictSort": 2, "status": "0"},
                {"dictLabel": "未知", "dictValue": "2", "dictType": "sys_user_sex", "dictSort": 3, "status": "0"},
            ],
            "sys_yes_no": [
                {"dictLabel": "是", "dictValue": "Y", "dictType": "sys_yes_no", "dictSort": 1, "status": "0"},
                {"dictLabel": "否", "dictValue": "N", "dictType": "sys_yes_no", "dictSort": 2, "status": "0"},
            ],
        }

        self.configs: list[dict[str, Any]] = [
            {"configId": 1, "configName": "主框架页-默认皮肤样式名称", "configKey": "sys.index.skinName", "configValue": "skin-blue", "configType": "Y", "createTime": "2024-01-01 00:00:00"},
            {"configId": 2, "configName": "用户管理-账号初始密码", "configKey": "sys.user.initPassword", "configValue": "123456", "configType": "Y", "createTime": "2024-01-01 00:00:00"},
            {"configId": 3, "configName": "账号自助-验证码开关", "configKey": "sys.account.captchaEnabled", "configValue": "true", "configType": "Y", "createTime": "2024-01-01 00:00:00"},
        ]

        self.notices: list[dict[str, Any]] = [
            {"noticeId": 1, "noticeTitle": "温馨提醒：2018-07-01 若依新版本发布啦", "noticeType": "1", "status": "0", "content": "新版本发布", "createTime": "2024-01-01 00:00:00"},
            {"noticeId": 2, "noticeTitle": "维护通知：2018-07-01 若依系统凌晨维护", "noticeType": "2", "status": "0", "content": "系统维护", "createTime": "2024-01-01 00:00:00"},
        ]

        self._user_seq = itertools.count(100)
        self._role_seq = itertools.count(100)

    @staticmethod
    def _menu(
        menu_id: int,
        name: str,
        parent_id: int,
        order: int,
        path: str,
        component: str | None,
        menu_type: str,
        perms: str,
        icon: str,
    ) -> dict[str, Any]:
        return {
            "menuId": menu_id,
            "menuName": name,
            "parentId": parent_id,
            "orderNum": order,
            "path": path,
            "component": component,
            "isFrame": "1",
            "isCache": "0",
            "menuType": menu_type,
            "visible": "0",
            "status": "0",
            "perms": perms,
            "icon": icon,
        }

    # ------------------------------------------------------------------
    # 查询辅助
    # ------------------------------------------------------------------
    def find_user(self, user_id: int) -> dict[str, Any] | None:
        return next((u for u in self.users if u["userId"] == user_id), None)

    def find_user_by_name(self, user_name: str) -> dict[str, Any] | None:
        return next((u for u in self.users if u["userName"] == user_name), None)

    def find_role(self, role_id: int) -> dict[str, Any] | None:
        return next((r for r in self.roles if r["roleId"] == role_id), None)

    def find_role_by_key(self, role_key: str) -> dict[str, Any] | None:
        return next((r for r in self.roles if r["roleKey"] == role_key), None)

    def perms_of(self, user: dict[str, Any]) -> set[str]:
        perms: set[str] = set()
        for role_id in user.get("roleIds", []):
            role = self.find_role(role_id)
            if not role or role["status"] != "0":
                continue
            if role["roleKey"] == "admin":
                return {"*:*:*"}
            for menu_id in role.get("menuIds", []):
                menu = next((m for m in self.menus if m["menuId"] == menu_id), None)
                if menu and menu["perms"]:
                    perms.add(menu["perms"])
        return perms

    # ------------------------------------------------------------------
    # 用户 CRUD
    # ------------------------------------------------------------------
    def create_user(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        with self.lock:
            name = str(payload.get("userName") or "").strip()
            phone = str(payload.get("phonenumber") or "").strip()
            email = str(payload.get("email") or "").strip()
            if self.find_user_by_name(name):
                return None, "用户账号已存在"
            if phone and any(u["phonenumber"] == phone for u in self.users):
                return None, "手机号码已存在"
            if email and any(u["email"] == email for u in self.users):
                return None, "邮箱账号已存在"
            user = {
                "userId": next(self._user_seq),
                "deptId": payload.get("deptId") or ADMIN_DEPT_ID,
                "userName": name,
                "nickName": payload.get("nickName") or "",
                "email": email,
                "phonenumber": phone,
                "sex": payload.get("sex") or "0",
                "avatar": "",
                "password": payload.get("password") or "123456",
                "status": payload.get("status") or "0",
                "delFlag": "0",
                "createTime": _now(),
                "remark": payload.get("remark") or "",
                "roleIds": list(payload.get("roleIds") or []),
                "postIds": list(payload.get("postIds") or []),
            }
            self.users.append(user)
            return user, ""

    def delete_users(self, user_ids: list[int]) -> tuple[int, str]:
        with self.lock:
            if ADMIN_USER_ID in user_ids:
                return 0, "不允许操作超级管理员用户"
            deleted = 0
            for user_id in user_ids:
                user = self.find_user(user_id)
                if user:
                    self.users.remove(user)
                    deleted += 1
            return deleted, ""

    def create_role(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        with self.lock:
            key = str(payload.get("roleKey") or "").strip()
            name = str(payload.get("roleName") or "").strip()
            if self.find_role_by_key(key):
                return None, "角色权限已存在"
            if any(r["roleName"] == name for r in self.roles):
                return None, "角色名称已存在"
            role = {
                "roleId": next(self._role_seq),
                "roleName": name,
                "roleKey": key,
                "roleSort": int(payload.get("roleSort") or 0),
                "dataScope": str(payload.get("dataScope") or "1"),
                "menuCheckStrictly": True,
                "deptCheckStrictly": True,
                "status": str(payload.get("status") or "0"),
                "delFlag": "0",
                "createTime": _now(),
                "remark": payload.get("remark") or "",
                "menuIds": list(payload.get("menuIds") or []),
            }
            self.roles.append(role)
            return role, ""

    def delete_roles(self, role_ids: list[int]) -> tuple[int, str]:
        with self.lock:
            if ADMIN_ROLE_ID in role_ids:
                return 0, "不允许操作超级管理员角色"
            for role_id in role_ids:
                if any(role_id in user.get("roleIds", []) for user in self.users):
                    return 0, "已分配,不能删除"
            deleted = 0
            for role_id in role_ids:
                role = self.find_role(role_id)
                if role:
                    self.roles.remove(role)
                    deleted += 1
            return deleted, ""

    # ------------------------------------------------------------------
    # 工具
    # ------------------------------------------------------------------
    @staticmethod
    def public_user(user: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in user.items() if k != "password"}

    @staticmethod
    def paginate(items: list[Any], page_num: int, page_size: int) -> list[Any]:
        start = max(page_num - 1, 0) * max(page_size, 1)
        return items[start : start + max(page_size, 1)]

    @staticmethod
    def valid_email(value: str) -> bool:
        return bool(EMAIL_RE.match(value))
