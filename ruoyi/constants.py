"""RuoYi 领域常量。

集中定义，避免魔法值散落在用例里——最典型的就是 `roleIds=[2]`：
一旦目标环境的角色 ID 不是 2，全套权限用例会以"看起来通过"的方式失效。
"""

from __future__ import annotations

# ---- 状态枚举（RuoYi 用字符串 "0"/"1" 表示，不是布尔）----
STATUS_NORMAL = "0"
STATUS_DISABLED = "1"

# ---- 内置数据（RuoYi 初始化 SQL 的固定值）----
ADMIN_USER_ID = 1
ADMIN_ROLE_ID = 1
COMMON_ROLE_ID = 2
ADMIN_DEPT_ID = 103
ADMIN_POST_ID = 4

# ---- 超级管理员的权限标识 ----
ALL_PERMISSIONS = "*:*:*"

# ---- 常用字典类型 ----
DICT_NORMAL_DISABLE = "sys_normal_disable"
DICT_USER_SEX = "sys_user_sex"
DICT_YES_NO = "sys_yes_no"
DICT_SHOW_HIDE = "sys_show_hide"

# ---- 角色数据范围 ----
DATA_SCOPE_ALL = "1"
DATA_SCOPE_CUSTOM = "2"
DATA_SCOPE_DEPT = "3"
DATA_SCOPE_DEPT_AND_CHILD = "4"
DATA_SCOPE_SELF = "5"

# ---- 权限标识（用于权限矩阵用例）----
PERM_USER_LIST = "system:user:list"
PERM_USER_ADD = "system:user:add"
PERM_USER_EDIT = "system:user:edit"
PERM_USER_REMOVE = "system:user:remove"
PERM_ROLE_LIST = "system:role:list"
PERM_ROLE_ADD = "system:role:add"
PERM_ROLE_REMOVE = "system:role:remove"

# ---- 业务错误文案（断言依赖文案而非仅状态码，见 docs/defects.md）----
MSG_DUP_USERNAME = "用户账号已存在"
MSG_DUP_PHONE = "手机号码已存在"
MSG_DUP_EMAIL = "邮箱账号已存在"
MSG_DUP_ROLE_KEY = "角色权限已存在"
MSG_NOT_ALLOW_ADMIN_USER = "不允许操作超级管理员用户"
MSG_NOT_ALLOW_ADMIN_ROLE = "不允许操作超级管理员角色"
MSG_ROLE_IN_USE = "已分配,不能删除"
MSG_PERM_DENIED = "没有权限"
MSG_BAD_CREDENTIALS = "用户不存在/密码错误"
MSG_USER_DISABLED = "您的账号已停用"
MSG_CAPTCHA_WRONG = "验证码错误"
