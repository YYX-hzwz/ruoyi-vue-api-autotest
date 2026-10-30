# 缺陷记录

> 环境：RuoYi-Vue 3.9.2 / JDK 17 / MySQL 8 / Redis 7
> 所有缺陷均绑定回归用例，见 `defects/registry.json`；`tests/test_09_meta.py` 会校验绑定关系。

缺陷状态说明：
- `open`：仍可复现，对应用例为 `xfail`
- `fixed`：已修复，对应用例应转为 `xpass`，此时需移除 `xfail` 标记
- `closed`：判定为非缺陷或无法复现（附判定依据）

---

## BUG-001 创建用户未校验密码长度

| 项 | 内容 |
|----|------|
| 级别 | 中 |
| 模块 | 用户管理 |
| 状态 | open |
| 回归用例 | `tests/test_08_defects.py::test_weak_password_rejected` |

**复现步骤**

```bash
# 1. 管理员登录取 token（略）
# 2. 以 3 位密码创建用户
curl -X POST 'http://localhost:8080/system/user' \
  -H 'Authorization: Bearer <token>' \
  -H 'Content-Type: application/json' \
  --data-raw '{"userName":"weak_pwd_demo","nickName":"弱口令","password":"123",
               "phonenumber":"13900001111","email":"weak@demo.local",
               "status":"0","deptId":103,"roleIds":[2]}'
```

**期望**：`{"code":500,"msg":"用户密码长度不能少于6位"}`（对标前端提示与口令策略要求）

**实际**：`{"code":200,"msg":"操作成功"}`，用户创建成功

**根因**：`SysUser` 实体对 `password` 字段没有长度/复杂度注解；`POST /system/user` 与
`PUT /system/user/resetPwd` 两条路径都不做校验，只靠前端表单拦截。

**影响**：绕过前端直接调接口即可创建弱口令账号，口令策略无法在服务端强制。
在等保/审计场景下属于明确的基线缺失。

**建议修复**：在服务端对新增与重置密码统一加长度与复杂度校验；同时补一条
"口令策略"单元测试，避免只修一个入口。

---

## BUG-002 普通角色用户可读取用户列表（越权）

| 项 | 内容 |
|----|------|
| 级别 | 高 |
| 模块 | 权限控制 |
| 状态 | open（根因待确认，见下文） |
| 回归用例 | `tests/test_08_defects.py::test_normal_user_cannot_list_users` |

**复现步骤**

1. 管理员创建一个用户，仅分配 `roleKey=common` 的角色（该角色的菜单权限不含"用户管理"）
2. 用该用户登录，取 token
3. `GET /system/user/list?pageNum=1&pageSize=10`

**期望**：`{"code":403,"msg":"没有权限，请联系管理员授权"}`（HTTP 200，业务码 403）

**实际**：`{"code":200,"total":2,"rows":[...]}`，返回全部用户（含手机号、邮箱）

**根因分析（两种可能，必须逐一排除后才好定性）**

| 假设 | 验证方法 | 判定依据 |
|------|----------|----------|
| (a) 接口缺少 `@PreAuthorize` 注解 | 读 `SysUserController#list` 是否有 `@PreAuthorize("@ss.hasPermi('system:user:list')")` | 有注解 → 排除 (a) |
| (b) 普通角色被误授予 `system:user:list` 菜单权限 | `SELECT rm.role_id, m.perms FROM sys_role_menu rm JOIN sys_menu m ON m.menu_id = rm.menu_id WHERE rm.role_id = <common_role_id> AND m.perms LIKE 'system:user%';` | 有记录 → 是配置问题，不是代码缺陷 |

**辅助证据（已采集）**：普通用户调用 `/getRouters` 时，返回的菜单树**不含**"用户管理"。
说明"菜单可见性"与"接口权限"用了两套来源且已经不一致——这正是需要定位的分歧点。

**影响**：横向越权，普通账号可枚举组织内全部用户信息，属于个人信息泄露。

**建议修复**
- 若为 (a)：补注解，并在 CI 里保留这条权限矩阵用例；
- 若为 (b)：回收菜单权限，并把"角色-权限"纳入配置变更评审。

> 面试追问"你怎么确定这是缺陷而不是配置问题"——答案就是上面这张假设-验证表。
> 没有做这个排除就断言"高危越权"，是上一版最大的方法论问题。

---

## BUG-003 角色状态字段未做枚举校验

| 项 | 内容 |
|----|------|
| 级别 | 低 |
| 模块 | 角色管理 |
| 状态 | open |
| 回归用例 | `tests/test_08_defects.py::test_invalid_role_status_rejected` |

**复现步骤**

```bash
curl -X POST 'http://localhost:8080/system/role' \
  -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' \
  --data-raw '{"roleName":"非法状态角色","roleKey":"bad_status_demo","roleSort":1,"status":"9"}'
```

**期望**：`{"code":500,"msg":"角色状态值非法"}`

**实际**：`{"code":200,"msg":"操作成功"}`，`sys_role.status = '9'`

**根因**：`SysRole.status` 没有 `@Pattern` / `@In` 之类枚举约束，仅靠前端下拉框限制。

**影响**：脏数据进入 `sys_role.status`。前端按字典渲染时会出现空白状态，
权限判断若按"非 0 即停用"处理会与"未定义"混淆。

**建议修复**：后端加枚举校验，或在持久层用字典表约束。

---

## 认知修正：验证码开关"不生效"

**结论：不是缺陷。**

上一版把这条记为中等缺陷，理由是"在 `application.yml` 里设置 `captchaEnabled: false` 后，
登录仍提示验证码失效"，并因此注释掉了后端的 `SysLoginService.validateCaptcha`——
**这是错误的处置方式**：改了被测源码，测试结论就无法迁移到线上，CI 也无法复现。

真实机制：

- `application.yml` 的 `ruoyi.captchaEnabled` 是**默认值**；
- 实际生效的是数据库 `sys_config` 表中 `sys.account.captchaEnabled`（见 `SysConfigService.selectCaptchaEnabled`）；
- 因此改配置文件"不生效"是设计如此，不是 bug。

正确做法（三选一，都不碰业务代码）：

| 方案 | 适用场景 | 配置 |
|------|----------|------|
| 测试库关闭开关 | 本地/CI | `docker/mysql/zz-test-env.sql` 已内置 UPDATE |
| 固定验证码 | 测试环境把验证码固定 | `AUTOTEST_CAPTCHA_CODE=1111` |
| 直连 Redis 取真码 | 生产同构环境 | `AUTOTEST_CAPTCHA_ENABLED=true` + `AUTOTEST_REDIS_URL=redis://...` |

框架的 `ruoyi/captcha.py` 按上述顺序自动选择，取不到时**明确报错**并给出三条出路，
而不是伪造一个验证码让用例"看起来通过"。

---

## 复盘：上一版的三个方法论问题

记录在这里，因为它比缺陷本身更值得复盘。

1. **把缺陷写成了通过**。`test_create_user_short_password` 里写的是
   `# 当前后端未校验密码长度，记录为缺陷，先让测试通过` → `assert code == 200`。
   于是报告 43/43 全绿，同时文档声称发现高危缺陷——自相矛盾。
   现在改为 `xfail`，报告如实显示 3 条红。
2. **用改源码换取可运行**。注释 `validateCaptcha` 让测试跑起来，代价是测试对象与上线版本不一致。
   现在改为配置化 + 三条取码路径。
3. **越权用例无法区分根因**。断言写成 `code == 500 or status == 403`，
   权限拦截、参数校验、数据库异常都能让它通过。现在断言具体 `code=403` + msg，
   并用管理员视角回查副作用。
