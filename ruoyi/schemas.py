"""RuoYi 响应契约（schema 化的"接口文档"）。

把契约写成代码，而不是散落在断言里的 `assert "rows" in body`：
- 后端改字段名/类型 → 这里立刻报出精确路径；
- 这份文件同时充当活文档，比 README 更不容易过期；
- 新增接口先在这里定义契约，再写用例，属于"契约先行"。

约定：**允许多余字段**（后端加字段是兼容演进），
只对"必需字段缺失 / 类型变化 / 枚举越界"报错。
"""

from __future__ import annotations

from framework.schema import S

CODE_OK = S.int(enum=[200])

# ---- 登录 ----
LOGIN_OK = {
    "code": CODE_OK,
    "msg": S.str(),
    "token": S.str(min_len=16),
}

CAPTCHA = {
    "code": CODE_OK,
    "captchaEnabled": S.bool(),
    "uuid": S.str(required=False),
    "img": S.str(required=False),
}

BIZ_RESULT = {
    "code": S.int(),
    "msg": S.str(),
}

# ---- 用户 ----
USER_ROW = {
    "userId": S.int(ge=1),
    "userName": S.str(min_len=1, max_len=30),
    "nickName": S.str(min_len=1),
    "status": S.str(enum=["0", "1"]),
}

USER_PAGE = {
    "code": CODE_OK,
    "msg": S.str(),
    "total": S.int(ge=0),
    "rows": S.list_of(USER_ROW),
}

USER_DETAIL = {
    "code": CODE_OK,
    "data": {
        "userId": S.int(ge=1),
        "userName": S.str(min_len=1),
        "roleIds": S.list_of(S.int(ge=1)),
    },
    "roleIds": S.list_of(S.int(ge=1), required=False),
    "postIds": S.list_of(S.int(ge=1), required=False),
}

# ---- 角色 ----
ROLE_ROW = {
    "roleId": S.int(ge=1),
    "roleName": S.str(min_len=1),
    "roleKey": S.str(min_len=1),
    "roleSort": S.int(ge=0),
    "status": S.str(enum=["0", "1"]),
}

ROLE_PAGE = {
    "code": CODE_OK,
    "msg": S.str(),
    "total": S.int(ge=0),
    "rows": S.list_of(ROLE_ROW),
}

ROLE_DETAIL = {
    "code": CODE_OK,
    "data": ROLE_ROW,
}

# ---- 当前用户 ----
GET_INFO = {
    "code": CODE_OK,
    "user": {
        "userId": S.int(ge=1),
        "userName": S.str(min_len=1),
        "nickName": S.str(min_len=1),
        "roles": S.list_of(S.str()),
    },
    "roles": S.list_of(S.str()),
    "permissions": S.list_of(S.str()),
}

ROUTERS = {
    "code": CODE_OK,
    "data": S.list_of(
        {
            "name": S.str(min_len=1),
            "path": S.str(min_len=1),
            "meta": {
                "title": S.str(min_len=1),
            },
        }
    ),
}

# ---- 字典 / 参数 / 公告 ----
DICT_DATA = {
    "code": CODE_OK,
    "data": S.list_of(
        {
            "dictLabel": S.str(min_len=1),
            "dictValue": S.str(min_len=1),
        }
    ),
}

CONFIG_PAGE = {
    "code": CODE_OK,
    "total": S.int(ge=0),
    "rows": S.list_of(
        {
            "configId": S.int(ge=1),
            "configKey": S.str(min_len=1),
            "configValue": S.str(),
        }
    ),
}

NOTICE_PAGE = {
    "code": CODE_OK,
    "total": S.int(ge=0),
    "rows": S.list_of(
        {
            "noticeId": S.int(ge=1),
            "noticeTitle": S.str(min_len=1),
        }
    ),
}

MENU_TREE = {
    "code": CODE_OK,
    "data": S.list_of(S.any()),
}

DEPT_LIST = {
    "code": CODE_OK,
    "data": S.list_of(
        {
            "deptId": S.int(ge=1),
            "deptName": S.str(min_len=1),
            "parentId": S.int(ge=0),
            "status": S.str(enum=["0", "1"]),
        }
    ),
}

DEPT_TREE = {
    "code": CODE_OK,
    "data": S.list_of(
        {
            "id": S.int(ge=1),
            "label": S.str(min_len=1),
        }
    ),
}

POST_PAGE = {
    "code": CODE_OK,
    "total": S.int(ge=0),
    "rows": S.list_of(S.any()),
}
