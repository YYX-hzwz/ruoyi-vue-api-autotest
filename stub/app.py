"""RuoYi-Vue 契约桩（Contract Stub）。

### 它是什么
一个**忠实模仿 RuoYi-Vue 3.8.x 接口契约**的本地服务：路径、字段名、
HTTP 语义（业务错误走 HTTP 200 + body.code）、权限拦截方式（code=403）、
分页结构（total/rows）全部对齐。

### 它不是什么
**它不是被测系统。** 它存在的理由只有三个：

1. **离线可跑**：拉不起 MySQL+Redis+后端时（比如没有网络、CI 只跑静态检查），
   框架和用例逻辑仍然可以被验证；
2. **缺陷生命周期可演示**：`AUTOTEST_STUB_REPRODUCE_BUGS` 打开时复现
   RuoYi 的已知缺陷（用例表现为 xfail），关闭时"修复"（用例转绿），
   一条命令就能演给面试官看；
3. **契约基准**：桩和 `ruoyi/schemas.py` 是同一套契约的两个侧面，
   谁偏离谁就是错的。

真实验收永远跑 `AUTOTEST_TARGET=real` + docker compose。
"""

from __future__ import annotations

import random
import re
import secrets
from functools import wraps
from typing import Any, Callable
from uuid import uuid4

from flask import Flask, Response, g, jsonify, request

from ruoyi.constants import (
    ADMIN_ROLE_ID,
    ADMIN_USER_ID,
    MSG_BAD_CREDENTIALS,
    MSG_CAPTCHA_WRONG,
    MSG_DUP_ROLE_KEY,
    MSG_PERM_DENIED,
    MSG_USER_DISABLED,
)

from .store import Store

MIN_PASSWORD_LEN = 6


class Bugs:
    """缺陷开关。True = 复现 RuoYi 的已知问题。"""

    def __init__(self, enabled: bool) -> None:
        self.weak_password = enabled
        self.missing_permission = enabled
        self.role_status_enum = enabled

    def as_dict(self) -> dict[str, bool]:
        return {
            "BUG-001-weak-password": self.weak_password,
            "BUG-002-user-list-permission": self.missing_permission,
            "BUG-003-role-status-enum": self.role_status_enum,
        }


def create_app(
    *,
    reproduce_bugs: bool = True,
    captcha_enabled: bool = False,
) -> Flask:
    app = Flask("ruoyi-stub")
    app.json.ensure_ascii = False

    store = Store()
    bugs = Bugs(reproduce_bugs)
    tokens: dict[str, int] = {}
    captchas: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 响应构造：与 RuoYi 的 AjaxResult 保持一致
    # ------------------------------------------------------------------
    def ok(data: Any = None, **extra: Any) -> Response:
        payload: dict[str, Any] = {"code": 200, "msg": "操作成功"}
        if data is not None:
            payload["data"] = data
        payload.update(extra)
        return jsonify(payload)

    def table(rows: list[dict[str, Any]], total: int) -> Response:
        return jsonify({"code": 200, "msg": "查询成功", "total": total, "rows": rows})

    def fail(msg: str, code: int = 500) -> Response:
        """业务失败统一 HTTP 200 + code，这是 RuoYi 的既有约定。"""
        return jsonify({"code": code, "msg": msg})

    def body() -> dict[str, Any]:
        payload = request.get_json(silent=True)
        if isinstance(payload, dict):
            return payload
        return request.form.to_dict()

    # ------------------------------------------------------------------
    # 鉴权
    # ------------------------------------------------------------------
    def current_user() -> dict[str, Any] | None:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return None
        token = header[len("Bearer ") :].strip()
        user_id = tokens.get(token)
        if user_id is None:
            return None
        return store.find_user(user_id)

    def require_auth(fn: Callable[..., Response]) -> Callable[..., Response]:
        @wraps(fn)
        def guard(*args: Any, **kwargs: Any) -> Response:
            user = current_user()
            if user is None:
                return fail("认证失败，无法访问系统资源", 401)
            g.user = user
            return fn(*args, **kwargs)

        return guard

    def require_perm(perm: str) -> Callable[[Callable[..., Response]], Callable[..., Response]]:
        def decorator(fn: Callable[..., Response]) -> Callable[..., Response]:
            @wraps(fn)
            def guard(*args: Any, **kwargs: Any) -> Response:
                perms = store.perms_of(g.user)
                allowed = "*:*:*" in perms or perm in perms
                # BUG-002：用户列表接口缺少权限注解，普通角色也能读
                if not allowed and bugs.missing_permission and perm == "system:user:list":
                    allowed = True
                if not allowed:
                    return fail(MSG_PERM_DENIED, 403)
                return fn(*args, **kwargs)

            return require_auth(guard)

        return decorator

    # ------------------------------------------------------------------
    # 认证
    # ------------------------------------------------------------------
    @app.post("/login")
    def login() -> Response:
        payload = body()
        username = str(payload.get("username") or "")
        password = str(payload.get("password") or "")

        if captcha_enabled:
            uuid = str(payload.get("uuid") or "")
            code = str(payload.get("code") or "")
            expected = captchas.pop(uuid, None)
            if expected is None:
                return fail("验证码已失效")
            if expected.lower() != code.lower():
                return fail(MSG_CAPTCHA_WRONG)

        user = store.find_user_by_name(username)
        if user is None or user["password"] != password:
            return fail(MSG_BAD_CREDENTIALS)
        if user["status"] != "0":
            return fail(MSG_USER_DISABLED)

        token = secrets.token_urlsafe(24)
        tokens[token] = user["userId"]
        return ok(token=token)

    @app.get("/captchaImage")
    def captcha_image() -> Response:
        if not captcha_enabled:
            return jsonify({"code": 200, "msg": "操作成功", "captchaEnabled": False, "uuid": "", "img": ""})
        uuid = uuid4().hex
        code = f"{random.randint(1000, 9999)}"
        captchas[uuid] = code
        return jsonify(
            {
                "code": 200,
                "msg": "操作成功",
                "captchaEnabled": True,
                "uuid": uuid,
                "img": "data:image/png;base64,stub",
            }
        )

    @app.post("/logout")
    @require_auth
    def logout() -> Response:
        header = request.headers.get("Authorization", "")
        tokens.pop(header[len("Bearer ") :].strip(), None)
        return ok()

    @app.get("/getInfo")
    @require_auth
    def get_info() -> Response:
        user = g.user
        role_keys = [
            r["roleKey"]
            for r in (store.find_role(rid) for rid in user.get("roleIds", []))
            if r is not None
        ]
        perms = sorted(store.perms_of(user))
        info = store.public_user(user)
        info["roles"] = role_keys
        info["admin"] = user["userId"] == ADMIN_USER_ID
        return jsonify(
            {
                "code": 200,
                "msg": "操作成功",
                "user": info,
                "roles": role_keys,
                "permissions": perms,
            }
        )

    @app.get("/getRouters")
    @require_auth
    def get_routers() -> Response:
        perms = store.perms_of(g.user)
        children = []
        for menu in store.menus:
            if menu["parentId"] != 1:
                continue
            visible = "*:*:*" in perms or not menu["perms"] or menu["perms"] in perms
            if not visible:
                continue
            children.append(
                {
                    "name": menu["menuName"],
                    "path": menu["path"],
                    "hidden": menu["visible"] != "0",
                    "component": menu["component"],
                    "meta": {"title": menu["menuName"], "icon": menu["icon"], "noCache": False, "link": None},
                }
            )
        data = [
            {
                "name": "System",
                "path": "/system",
                "hidden": False,
                "redirect": "noRedirect",
                "component": "Layout",
                "alwaysShow": True,
                "meta": {"title": "系统管理", "icon": "system", "noCache": False, "link": None},
                "children": children,
            }
        ]
        return ok(data)

    # ------------------------------------------------------------------
    # 用户
    # ------------------------------------------------------------------
    @app.get("/system/user/list")
    @require_perm("system:user:list")
    def user_list() -> Response:
        page_num = _int_arg("pageNum", 1)
        page_size = _int_arg("pageSize", 10)
        user_name = request.args.get("userName", "")
        phone = request.args.get("phonenumber", "")
        status = request.args.get("status", "")

        rows = list(store.users)
        if user_name:
            rows = [u for u in rows if user_name.lower() in u["userName"].lower()]
        if phone:
            rows = [u for u in rows if phone in u["phonenumber"]]
        if status:
            rows = [u for u in rows if u["status"] == status]

        page = store.paginate(rows, page_num, page_size)
        return table([store.public_user(u) for u in page], len(rows))

    @app.post("/system/user")
    @require_perm("system:user:add")
    def user_create() -> Response:
        payload = body()
        error = _validate_user(payload, bugs)
        if error:
            return fail(error)
        user, error = store.create_user(payload)
        if user is None:
            return fail(error)
        return ok()

    @app.put("/system/user")
    @require_perm("system:user:edit")
    def user_update() -> Response:
        payload = body()
        user_id = payload.get("userId")
        user = store.find_user(int(user_id)) if user_id is not None else None
        if user is None:
            return fail("用户不存在")
        # 局部更新时用"现值 + 补丁"做校验，否则缺 userName 会被误判为空
        error = _validate_user({**user, **payload}, bugs, existing=user)
        if error:
            return fail(error)
        with store.lock:
            for field in ("nickName", "email", "phonenumber", "sex", "status", "remark"):
                if field in payload:
                    user[field] = payload[field]
            if "roleIds" in payload:
                user["roleIds"] = list(payload["roleIds"])
            if "postIds" in payload:
                user["postIds"] = list(payload["postIds"])
            if payload.get("deptId"):
                user["deptId"] = payload["deptId"]
        return ok()

    @app.delete("/system/user/<string:ids>")
    @require_perm("system:user:remove")
    def user_delete(ids: str) -> Response:
        user_ids = _parse_ids(ids)
        deleted, error = store.delete_users(user_ids)
        if error:
            return fail(error)
        return ok() if deleted else fail("用户不存在")

    @app.get("/system/user/<int:user_id>")
    @require_perm("system:user:query")
    def user_detail(user_id: int) -> Response:
        user = store.find_user(user_id)
        if user is None:
            return fail("用户不存在")
        detail = store.public_user(user)
        return jsonify(
            {
                "code": 200,
                "msg": "操作成功",
                "data": detail,
                "roleIds": user.get("roleIds", []),
                "postIds": user.get("postIds", []),
            }
        )

    @app.put("/system/user/resetPwd")
    @require_perm("system:user:resetPwd")
    def user_reset_pwd() -> Response:
        payload = body()
        user = store.find_user(int(payload.get("userId") or 0))
        if user is None:
            return fail("用户不存在")
        user["password"] = str(payload.get("password") or "")
        return ok()

    @app.put("/system/user/changeStatus")
    @require_perm("system:user:edit")
    def user_change_status() -> Response:
        payload = body()
        user_id = int(payload.get("userId") or 0)
        if user_id == ADMIN_USER_ID:
            return fail("不允许操作超级管理员用户")
        user = store.find_user(user_id)
        if user is None:
            return fail("用户不存在")
        user["status"] = str(payload.get("status") or "0")
        return ok()

    @app.put("/system/user/authRole")
    @require_perm("system:user:edit")
    def user_auth_role() -> Response:
        payload = body()
        user_id = int(payload.get("userId") or request.args.get("userId") or 0)
        if user_id == ADMIN_USER_ID:
            return fail("不允许操作超级管理员用户")
        user = store.find_user(user_id)
        if user is None:
            return fail("用户不存在")
        raw_ids = payload.get("roleIds")
        if raw_ids is None:
            raw_ids = request.args.getlist("roleIds") or request.args.get("roleIds") or ""
        user["roleIds"] = _parse_ids_multi(raw_ids)
        return ok()

    @app.get("/system/user/authRole/<int:user_id>")
    @require_perm("system:user:query")
    def user_auth_role_detail(user_id: int) -> Response:
        user = store.find_user(user_id)
        if user is None:
            return fail("用户不存在")
        return jsonify(
            {
                "code": 200,
                "msg": "操作成功",
                "user": store.public_user(user),
                "roles": store.roles,
                "roleIds": user.get("roleIds", []),
            }
        )

    @app.get("/system/user/deptTree")
    @require_auth
    def user_dept_tree() -> Response:
        return ok(_dept_tree(store))

    # ------------------------------------------------------------------
    # 角色
    # ------------------------------------------------------------------
    @app.get("/system/role/list")
    @require_perm("system:role:list")
    def role_list() -> Response:
        page_num = _int_arg("pageNum", 1)
        page_size = _int_arg("pageSize", 10)
        role_name = request.args.get("roleName", "")
        role_key = request.args.get("roleKey", "")
        status = request.args.get("status", "")

        rows = list(store.roles)
        if role_name:
            rows = [r for r in rows if role_name in r["roleName"]]
        if role_key:
            rows = [r for r in rows if role_key in r["roleKey"]]
        if status:
            rows = [r for r in rows if r["status"] == status]

        page = store.paginate(rows, page_num, page_size)
        return table([_role_view(r) for r in page], len(rows))

    @app.post("/system/role")
    @require_perm("system:role:add")
    def role_create() -> Response:
        payload = body()
        error = _validate_role(payload, bugs)
        if error:
            return fail(error)
        role, error = store.create_role(payload)
        if role is None:
            return fail(f"新增角色'{payload.get('roleName')}'失败，{error or MSG_DUP_ROLE_KEY}")
        return ok()

    @app.put("/system/role")
    @require_perm("system:role:edit")
    def role_update() -> Response:
        payload = body()
        role = store.find_role(int(payload.get("roleId") or 0))
        if role is None:
            return fail("角色不存在")
        error = _validate_role({**role, **payload}, bugs, existing=role)
        if error:
            return fail(error)
        with store.lock:
            for field in ("roleName", "roleKey", "roleSort", "status", "remark", "dataScope"):
                if field in payload:
                    role[field] = payload[field]
            if "menuIds" in payload:
                role["menuIds"] = list(payload["menuIds"])
        return ok()

    @app.delete("/system/role/<string:ids>")
    @require_perm("system:role:remove")
    def role_delete(ids: str) -> Response:
        deleted, error = store.delete_roles(_parse_ids(ids))
        if error:
            return fail(error)
        return ok() if deleted else fail("角色不存在")

    @app.get("/system/role/<int:role_id>")
    @require_perm("system:role:query")
    def role_detail(role_id: int) -> Response:
        role = store.find_role(role_id)
        if role is None:
            return fail("角色不存在")
        return ok(_role_view(role))

    @app.put("/system/role/changeStatus")
    @require_perm("system:role:edit")
    def role_change_status() -> Response:
        payload = body()
        role_id = int(payload.get("roleId") or 0)
        if role_id == ADMIN_ROLE_ID:
            return fail("不允许操作超级管理员角色")
        role = store.find_role(role_id)
        if role is None:
            return fail("角色不存在")
        role["status"] = str(payload.get("status") or "0")
        return ok()

    @app.put("/system/role/dataScope")
    @require_perm("system:role:edit")
    def role_data_scope() -> Response:
        payload = body()
        role = store.find_role(int(payload.get("roleId") or 0))
        if role is None:
            return fail("角色不存在")
        role["dataScope"] = str(payload.get("dataScope") or "1")
        role["deptIds"] = list(payload.get("deptIds") or [])
        return ok()

    @app.get("/system/role/optionselect")
    @require_auth
    def role_option_select() -> Response:
        return ok([_role_view(r) for r in store.roles])

    @app.get("/system/role/deptTree/<int:role_id>")
    @require_auth
    def role_dept_tree(role_id: int) -> Response:
        role = store.find_role(role_id)
        if role is None:
            return fail("角色不存在")
        return ok({"checkedKeys": role.get("deptIds", []), "depts": _dept_tree(store)})

    # ------------------------------------------------------------------
    # 字典 / 参数 / 公告 / 菜单 / 部门 / 岗位
    # ------------------------------------------------------------------
    @app.get("/system/dict/data/type/<string:dict_type>")
    @require_auth
    def dict_data(dict_type: str) -> Response:
        items = store.dicts.get(dict_type)
        if items is None:
            return fail(f"字典类型{dict_type}不存在")
        return ok(items)

    @app.get("/system/dict/type/list")
    @require_perm("system:dict:list")
    def dict_types() -> Response:
        rows = [
            {"dictId": index + 1, "dictName": key, "dictType": key, "status": "0"}
            for index, key in enumerate(store.dicts)
        ]
        return table(rows, len(rows))

    @app.get("/system/config/list")
    @require_perm("system:config:list")
    def config_list() -> Response:
        page_num = _int_arg("pageNum", 1)
        page_size = _int_arg("pageSize", 5)
        rows = list(store.configs)
        if request.args.get("configKey"):
            rows = [c for c in rows if request.args["configKey"] in c["configKey"]]
        return table(store.paginate(rows, page_num, page_size), len(rows))

    @app.get("/system/config/configKey/<path:config_key>")
    @require_auth
    def config_by_key(config_key: str) -> Response:
        config = next((c for c in store.configs if c["configKey"] == config_key), None)
        if config is None:
            return fail("参数键名不存在")
        return jsonify({"code": 200, "msg": config["configValue"]})

    @app.get("/system/notice/list")
    @require_perm("system:notice:list")
    def notice_list() -> Response:
        page_num = _int_arg("pageNum", 1)
        page_size = _int_arg("pageSize", 5)
        return table(store.paginate(store.notices, page_num, page_size), len(store.notices))

    @app.get("/system/menu/list")
    @require_perm("system:menu:list")
    def menu_list() -> Response:
        return ok(list(store.menus))

    @app.get("/system/menu/treeselect")
    @require_perm("system:menu:list")
    def menu_tree() -> Response:
        return ok([{"id": m["menuId"], "label": m["menuName"], "children": []} for m in store.menus])

    @app.get("/system/menu/roleMenuTreeselect/<int:role_id>")
    @require_auth
    def role_menu_tree(role_id: int) -> Response:
        role = store.find_role(role_id)
        if role is None:
            return fail("角色不存在")
        menus = [{"id": m["menuId"], "label": m["menuName"], "children": []} for m in store.menus]
        return ok({"menus": menus, "checkedKeys": role.get("menuIds", [])})

    @app.get("/system/dept/list")
    @require_perm("system:dept:list")
    def dept_list() -> Response:
        return ok(
            [
                {
                    "deptId": d["deptId"],
                    "parentId": d["parentId"],
                    "deptName": d["deptName"],
                    "orderNum": d["orderNum"],
                    "status": d["status"],
                }
                for d in store.depts
            ]
        )

    @app.get("/system/post/list")
    @require_perm("system:post:list")
    def post_list() -> Response:
        return table(list(store.posts), len(store.posts))

    # ------------------------------------------------------------------
    # 桩自身的调试接口（真实后端不存在这些路由）
    # ------------------------------------------------------------------
    @app.get("/__stub/health")
    def stub_health() -> Response:
        return jsonify({"code": 200, "status": "ok", "bugs": bugs.as_dict()})

    @app.get("/__stub/captcha/<string:uuid>")
    def stub_captcha(uuid: str) -> Response:
        code = captchas.get(uuid)
        if code is None:
            return fail("验证码已失效")
        return jsonify({"code": 200, "code_value": code})

    @app.get("/__stub/bugs")
    def stub_bugs() -> Response:
        return jsonify({"code": 200, "bugs": bugs.as_dict()})

    @app.post("/__stub/reset")
    def stub_reset() -> Response:
        nonlocal store
        store = Store()
        app.extensions["store"] = store
        tokens.clear()
        captchas.clear()
        return jsonify({"code": 200, "msg": "已重置"})

    app.extensions["store"] = store
    app.extensions["bugs"] = bugs
    return app


# ----------------------------------------------------------------------
# 辅助
# ----------------------------------------------------------------------
def _int_arg(name: str, default: int) -> int:
    raw = request.args.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _parse_ids(raw: str) -> list[int]:
    return [int(part) for part in re.split(r"[,\s]+", raw.strip()) if part.strip().isdigit()]


def _parse_ids_multi(raw: Any) -> list[int]:
    if isinstance(raw, (list, tuple)):
        values: list[int] = []
        for item in raw:
            values.extend(_parse_ids_multi(item))
        return values
    if isinstance(raw, int):
        return [raw]
    if isinstance(raw, str):
        return _parse_ids(raw)
    return []


def _role_view(role: dict[str, Any]) -> dict[str, Any]:
    return {
        "roleId": role["roleId"],
        "roleName": role["roleName"],
        "roleKey": role["roleKey"],
        "roleSort": role["roleSort"],
        "status": role["status"],
        "dataScope": role["dataScope"],
        "createTime": role["createTime"],
        "remark": role.get("remark", ""),
    }


def _dept_tree(store: Store) -> list[dict[str, Any]]:
    return [{"id": d["deptId"], "label": d["deptName"], "children": []} for d in store.depts]


def _validate_user(
    payload: dict[str, Any],
    bugs: Bugs,
    existing: dict[str, Any] | None = None,
) -> str | None:
    """对齐 RuoYi 实体上的校验注解。existing 不为空表示更新场景。"""
    name = str(payload.get("userName") or "").strip()
    nick = str(payload.get("nickName") or "").strip()
    email = str(payload.get("email") or "").strip()
    password = payload.get("password")

    if not name:
        return "用户账号不能为空"
    if not nick:
        return "用户昵称不能为空"
    phone = str(payload.get("phonenumber") or "").strip()
    if len(name) > 30:
        return "用户账号长度不能超过30个字符"
    if len(nick) > 30:
        return "用户昵称长度不能超过30个字符"
    if len(phone) > 11:
        return "手机号码长度不能超过11个字符"
    if len(email) > 50:
        return "邮箱长度不能超过50个字符"
    if email and not Store.valid_email(email):
        return "邮箱格式不正确"
    if password is not None and not bugs.weak_password and len(str(password)) < MIN_PASSWORD_LEN:
        return f"用户密码长度不能少于{MIN_PASSWORD_LEN}位"
    return None


def _validate_role(
    payload: dict[str, Any],
    bugs: Bugs,
    existing: dict[str, Any] | None = None,
) -> str | None:
    name = str(payload.get("roleName") or "").strip()
    key = str(payload.get("roleKey") or "").strip()
    if not name:
        return "角色名称不能为空"
    if not key:
        return "权限字符不能为空"
    if payload.get("roleSort") is None:
        return "角色顺序不能为空"
    status = payload.get("status")
    if status is not None:
        status = str(status)
        if status not in {"0", "1"} and not bugs.role_status_enum:
            return f"角色状态值非法：{status}"
    return None
