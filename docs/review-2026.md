# RuoYi-Vue API 自动化测试 —— 项目评审与进阶路线

> **说明**：本文是**重构前**的评审记录，保留作为"发现问题 → 重构 → 验证"的对照材料。
> 文中列出的问题已在当前代码中全部修复，现状请见 [README](../README.md) 与 [architecture.md](architecture.md)。
> 其中"验证码开关"一条在重构后被判定为**非缺陷**（属认知误判），依据见 [defects.md](defects.md) 的"认知修正"一节。
> 文中引用的 `test_*.py:行号` 指重构前的文件，现已归档到仓库根目录的 `legacy/`。

> 评审日期：2026-10-25 ｜ 评审对象：`ruoyi-vue-api-autotest`（43 条用例，5 个测试文件）

---

## 一、结论先行

**这个项目目前是一个"接口调用脚本集合"，不是一个"自动化测试框架"。**

作为学习作品它交足了作业：覆盖了登录、用户、角色、公共接口四个模块，用了 fixture 管理前置数据，用 uuid 保证数据唯一性，还写了缺陷记录和测试方案，说明你已经理解了"测什么"和"怎么组织"。

但作为**求职主项目**，它证明的只有一件事：你会用 `requests + pytest` 发请求、断言 JSON。这个能力在 2019 年的 JD 里是加分项，在 2026 年的 JD 里是**地板线**。现在招测试岗/测开岗真正在筛的是：

- 能不能**设计**框架（分层、抽象、可扩展），而不是**堆**用例；
- 能不能**一键复现**（环境编排、CI 真跑、报告可下钻）；
- 能不能做**质量门禁**（红测试驱动修复），而不是生成一份绿色报告；
- 性能、契约、可观测性、AI 辅助这些差异化能力。

有 3 个问题会直接让面试官否定整个项目（详见第二节），必须先修。有 7 类工程问题会在 5 分钟内被看穿（第三节）。有一份按优先级排好的改法（第五节）。

---

## 二、三个致命问题（面试官会当场问倒你）

### 致命问题 1：报告 43/43 全绿，但项目声称发现了 4 个缺陷——这两件事不可能同时为真

我解析了 `report.html` 里嵌入的结果数据：**43 条全部 Passed，耗时 6 秒**。

而 `docs/defects.md` 写着"发现 4 个缺陷，含 1 个高危越权"。一个真正的自动化测试项目，发现缺陷之后的状态应该是**红色**的——缺陷必须被固化成一条会红的用例（或 `xfail`），这样修复后它变绿，才叫"回归防护"。

现在的做法是**把 bug 写进了断言里**，让它永远绿：

| 位置 | 代码 | 问题 |
|---|---|---|
| `test_user_extended.py:90-91` | `# 当前后端未校验密码长度，记录为缺陷，先让测试通过` → `assert code == 200` | 把"弱密码能创建"这个**缺陷**断言成了**正确行为** |
| `test_user_extended.py:121-125` | 函数名 `test_normal_user_cannot_access_user_list`，断言 `assert resp.json()["code"] == 200` | 函数名说"不能访问"，断言说"能访问"。名实不符，且把越权缺陷固化为通过 |
| `test_role_api.py:162-164` | `test_normal_user_cannot_list_roles` → `assert status_code == 200` | 同上，只校验 HTTP 层，等于没测 |
| `test_role_api.py:104-107` | `test_create_role_invalid_status` → `assert status_code == 200` | 非法枚举值，只要不 500 就算过，什么都没验证 |

**这是方法论级别的错误，不是写错了一行。** 它意味着这套测试的"绿"不携带任何质量信息——它只是记录了"被测系统当时确实这么干"。

面试官的原话大概会是：「你说你发现了高危越权，那你的用例为什么是绿的？」答不上来，前面所有内容都会被重新审视。

**正解**：用 `pytest.mark.xfail(strict=True)` + `pytest.mark.bug` 双标记。报告呈现 `39 passed, 4 xfailed`，并在 README 里画一条"缺陷发现 → 修复 → xfail 转 pass"的时间线。这一条改完，项目立刻从"脚本"变成"有闭环的质量实践"。

---

### 致命问题 2：测试能跑，是因为你改了被测系统的源码

`defects.md` 第 10 行写着：

> **解决方式**：已通过注释 `SysLoginService` 中 `validateCaptcha` 调用绕过

为了绕开验证码，你把后端业务代码注释掉了。这带来一个无法自洽的结论：

**你测的版本 ≠ 上线的版本，所以测试结论不可迁移，也无法在 CI 里复现。**

面试官会立刻追问："那这套东西在流水线上怎么跑？每次部署前手动去注释一行 Java？"——这是自动化测试最忌讳的"测试污染被测对象"。

而且它连带影响第 9 条缺陷的判断：你"发现"的验证码配置不生效，很可能根本不是缺陷——RuoYi 的验证码开关**设计上**就由 `sys_config` 表的 `sys.account.captchaEnabled` 控制（`application.yml` 里那个开关是给旧版本留的），你把它当 bug 记下来，反而暴露了对被测系统不够了解。

**正解**（按优先级）：
1. **测试专用 profile**：后端加 `application-test.yml`，或启动参数 `--spring.profiles.active=test`，在测试 profile 里关验证码。这是配置，不是改代码，可提交、可复现、可解释。
2. **不给后端动刀**：直接调 `/captchaImage` 拿 `uuid`，再走 Redis 拿真实验证码（RuoYi 把 code 存在 `captcha_codes:{uuid}` 里）。写一个 `get_captcha()` 工具函数，登录 fixture 自动带上。**这个方案最漂亮**，因为它一行业务代码都不碰，还能在面试里展开讲"我是怎么读源码定位验证码存储的"。
3. 退一步：Mock 掉验证码校验（`responses`/`respx`），但只用于**单元层**，接口层仍走真实环境。

---

### 致命问题 3：这套用例真的跑在 CI 上，有删掉管理员的风险

用例直接对着**真实的 admin 账号、真实的库**做 CRUD，并且有几条是在删固定 ID 的系统资源：

- `test_user_extended.py:132` → `client.delete("/system/user/1")`：删 **admin 用户**（id=1）
- `test_role_api.py:144` → `admin_client.delete("/system/role/1")`：删 **超级管理员角色**
- `test_role_api.py:171` → `normal_client.delete("/system/role/2")`：删 **普通角色**

现在没出事，只是因为 RuoYi 里"不允许删除超级管理员"这条业务规则挡住了（返回 500）。但你的断言是 `assert code == 500 or status_code == 403`——

**你无法区分"被权限拦住了"和"被业务规则拦住了"。** 也就是说这三条"越权测试"很可能是因为**别的原因**返回 500，而不是因为权限生效。它们通过了，但通过的理由是错的。

这类"通过理由错误"的测试比失败的测试更危险，因为它给你虚假的安全感。面试官只要问一句"你怎么确定这 500 是权限拦的、不是参数校验拦的？"，就露馅了。

**正解**：
- 删掉所有对固定 ID 的操作。改成"创建自己的资源 → 用它做越权测试 → 清理"。
- 断言升级为**语义断言**：校验 `msg` 包含具体文案（如 `"没有权限"`），或校验**副作用**（操作后回查资源仍然存在、`updateTime` 未变），而不是猜状态码。
- 测试库隔离：独立 schema + 每次跑之前 `flyway`/SQL dump 重置，或 Testcontainers。

---

## 三、工程问题清单

### A. 可运行性（最影响"别人 clone 下来能不能跑"）

| 问题 | 证据 |
|---|---|
| 无环境编排。README 只说"启动后端"，clone 者需要自己装 MySQL、导库、改配置、处理验证码 | `README.md:10-14` |
| 配置硬编码，无多环境支持 | `config.py:1-3`，`ADMIN_PASS = "admin123"` 明文入库 |
| `testpaths` 指向不存在的 `tests/`，pytest 只是警告后回退 | `pytest.ini:2`，运行时 `PytestConfigWarning: No files were found in testpaths` |
| 报告强绑在 `addopts` 里，缺 `pytest-html` 插件时连收集都失败 | `pytest.ini:4` |
| 所有请求**无 timeout**，后端一卡，CI 挂到超时 | `api_client.py:22-32`，全项目 0 处 timeout |
| 无日志。用例失败只有一行 AssertionError，**没有请求体、响应体、状态码**，线上排障等于盲猜 | 全项目 0 处 logging |

最后一条尤其致命：`pytest-html` 报告里每条用例的 log 都是 `No log output captured`。也就是说**测试失败时你拿不到现场**。一个不能自证失败原因的测试框架，价值打对折。

### B. 结构设计

| 问题 | 证据 |
|---|---|
| `conftest.py` 是空文件，共享能力为 0 | `conftest.py` 0 字节 |
| fixture 复制粘贴：`client` / `admin_client` / `normal_client` 在 4 个测试文件里重复定义了 **6 份** | `test_user_api.py:7`、`test_common_api.py:4`、`test_role_api.py:8,14`、`test_user_extended.py:7,13` |
| "创建普通用户 + 分配 role 2 + 登录"这段逻辑写了 **2 遍** | `test_role_api.py:14-42`、`test_user_extended.py:13-42` |
| 无 API 抽象层，URL 和 query string 在用例里手拼 | `test_user_api.py:29`、`test_role_api.py:59` 等 20+ 处 |
| 无响应模型校验。断言停留在 `code == 200` + 字段存在，**字段类型/必填/嵌套结构全不管** | 全项目 0 处 pydantic / jsonschema |
| `APIClient` 用裸 `requests.get`，不复用 `Session`，连接不复用；无重试、无 token 过期处理 | `api_client.py:22-32` |
| 在客户端里用 `assert` 做业务校验 | `api_client.py:17`——`assert` 在 `python -O` 下会被剥离，且库代码不该 assert |
| 无类型注解、无 docstring | 全部 `.py` |

### C. 测试数据

| 问题 | 证据 |
|---|---|
| 测试数据里全是**环境相关的魔法值**：`deptId: 103`、`postIds: [4]`、`roleIds: [2]` | `data/users.json:10-12` |
| 明文密码入库 | `data/users.json:5` |
| **完全没有参数化**。测试方案里写了等价类/边界值（`docs/test_plan.md`），但代码里一条 `@pytest.mark.parametrize` 都没有——每个用例写死一份数据 | 全项目 0 处 parametrize |
| 依赖真实库的存量数据。`test_get_role_list_pagination` 断言 `len(rows) <= 2`，**库是空的它也能过**——这条"分页测试"永远发现不了分页 bug | `test_role_api.py:78-81` |
| `test_get_user_list_invalid_page` 只断言 `status_code == 200`，`pageNum=0` 返回什么都算过 | `test_user_extended.py:115-118` |
| 清理不可靠：teardown 里 `client.delete(...)` 无断言，失败静默；用例中途 fail 时 fixture 的 yield 后代码仍会跑，但断言失败会跳过后续清理 | `test_user_api.py:41`、`test_role_api.py:68` |

### D. 仓库卫生

| 问题 | 证据 |
|---|---|
| **没有 `.gitignore`** | 根目录不存在该文件 |
| `__pycache__/` 已提交，还包含**已删除模块**的 `.pyc`（`test_user_api_extended.cpython-314-pytest-9.1.1.pyc`）——说明改过文件名但没清缓存 | `git ls-files` |
| 生成的 `report.html`（60 KB）入库 | `git ls-files` |
| `defects.md` 存在**两份**，内容还不一致（根目录 1530 字节 vs `docs/` 1183 字节，哈希不同），README 只链了其中一份 | `defects.md`、`docs/defects.md` |
| README 的项目结构图与实际文件名不符：写的是 `test_user_api_extended.py`，实际是 `test_user_extended.py`；且漏了 `performance_test/`、`.github/` | `README.md:38,45` |
| README 的用例数统计错误：写"登录 5 / 用户 19"，实际是"登录 4 / 用户 16"（3 条登录用例混在 `test_user_extended.py` 里） | `README.md:16-22` |
| Git 历史只有 2 个 commit，第二个 "feat: add 43 cases" 一次性提交全部内容。招聘方看 commit 历史判断工程习惯，这等于"没有过程" | `git log` |

### E. CI

`.github/workflows/ci.yml` 名字叫 Python Syntax Check，内容也确实只是语法检查：

```yaml
- run: python -m compileall .
- run: pytest --collect-only
```

**它从不执行测试。** 没有服务编排、没有报告产物上传、没有并行、没有 lint、没有覆盖率。这个 workflow 唯一能证明的是"代码没有语法错误"。

而在没有后端的情况下，`pytest --collect-only` 能过、`pytest` 会 43 条全红——所以它选择只收集不执行，这本身就是在回避"环境跑不起来"这个真问题。

### F. 性能测试

`performance_test/locustfile.py` 一共 16 行、1 个 task、`wait_time=between(1,3)`、无断言、无 SLA、无阶梯加压、无结果分析、无数据参数化（所有虚拟用户都用 admin 打同一个接口）。

按现在的规模，它更接近"locust 的 Hello World"。简历上写"做过性能测试"会被追问 TPS/RT/P99/瓶颈定位，现在一个都答不上来。

### G. 缺陷报告质量

`docs/defects.md` 的格式缺了缺陷报告最核心的几项：

- ❌ 环境（版本、commit、数据库）
- ❌ 复现步骤（curl 或 pytest 命令）
- ❌ 实际请求 / 实际响应
- ❌ 期望结果 vs 实际结果（对照的是哪条产品需求/权限矩阵）
- ❌ 优先级 / 影响面

第 3 条"普通角色用户可访问用户列表"（高危）尤其经不起推敲：报告自己都写了"建议检查菜单权限配置"。**如果只是角色没配菜单权限，那就不是代码缺陷，是配置问题。** 你没有做权限矩阵验证（这个角色到底该有 `system:user:list` 吗？对照 `sys_menu` 里 role 2 的授权，跟 `SysUserController` 上的 `@PreAuthorize` 注解逐条比对），就把结论定成"高危越权"，风险很大。

---

## 四、面试官一定会问的 5 个问题

先想清楚怎么答，再动手改。这 5 个问题的答案，就是改进清单的验收标准。

1. **「你注释掉了后端的验证码校验才能登录，那这套测试在流水线上怎么跑？」**
   → 期待听到：测试 profile / 从 Redis 取真实验证码 / 一行业务代码都没改。

2. **「你的报告 43 条全绿，同时说发现了 1 个高危越权，这两件事怎么共存？」**
   → 期待听到：缺陷用 xfail 固化了，现在是 39 passed + 4 xfailed，修复后转 pass。

3. **「如果后端把 `/system/user/list` 的 `rows` 改名叫 `data`，你会红几条？能定位到原因吗？」**
   → 现在是：会红一片，且报告里只有 `KeyError: 'rows'`，没有响应体，定位靠猜。
   → 期待：schema 校验失败 + Allure 附件里有原始响应。

4. **「普通用户能查用户列表，你怎么排除是菜单权限没配，而不是代码缺陷？」**
   → 期待：对照 `sys_menu.perms` 与 `@PreAuthorize`，给出权限矩阵，并说明用什么证据链排除配置因素。

5. **「你的用例能并行跑吗？两条用例同时改同一个用户会怎样？」**
   → 现在是：共享真实库、固定 ID、无隔离，不能并行。
   → 期待：每条用例自建资源 + 独立命名空间 + xdist 可跑。

---

## 五、改进路线（按投入产出排序）

### P0 —— 两周内做完，先让项目"可信、可复现、不自相矛盾"

> 目标：任何人 clone 下来，一条命令起环境、一条命令出报告；报告里有一抹红。

1. **`docker-compose.yml` 编排被测系统**：MySQL + Redis + 后端镜像。`README` 改成三步：`docker compose up -d` → `cp .env.example .env` → `pytest`。**这一条决定项目是"能看"还是"能跑"。**
2. **配置外置**：`pydantic-settings` + `.env`，`API_URL` / `ADMIN_USER` / `ADMIN_PASS` 全部走环境变量，`config.py` 只做读取。密钥不进仓库。
3. **验证码正解**（见致命问题 2）：从 `/captchaImage` 拿 uuid → Redis 取 code → 登录。写进 `utils/captcha.py`，登录 fixture 自动调用。
4. **缺陷门禁化**：4 个缺陷转成 `@pytest.mark.xfail(strict=True, reason="BUG-003 越权")`。报告从"43 绿"变成"39 passed / 4 xfailed"，并在 README 加一段"缺陷生命周期"说明。**这是整个改造里最便宜、最加分的一步。**
5. **消灭破坏性用例**：删掉所有 `/system/user/1`、`/system/role/1`、`/system/role/2`。改为自建资源 + 语义断言（校验 `msg` 文案 + 副作用回查）。
6. **`conftest.py` 收敛**：4 份重复 fixture 收成 1 份，放 `pytest_plugins` 或 `conftest.py`；`client` 改为 `session` scope 复用登录态。
7. **基础工程卫生**：
   - 补 `.gitignore`（`__pycache__/`、`.pytest_cache/`、`*.html`、`.env`）；
   - `git rm -r --cached __pycache__ report.html`，把 `report.html` 改成 CI artifact 或 `--html=reports/`；
   - 删掉重复的 `defects.md`（保留 `docs/` 那份）；
   - 修 `pytest.ini` 的 `testpaths`；
   - README 的数字和结构图跟代码对齐。
8. **请求层加 timeout + 日志 + Session**：`APIClient` 用 `requests.Session`，`timeout=(3, 10)`，`response.raise_for_status()` 可选，每个请求用 `logging` 记录 method/url/status/耗时，失败时把请求响应挂到 `pytest` 报告的 `extra` 里。

### P1 —— 一个月内，拉开与"只会调接口"的差距

9. **分层重构**（这一步是"框架设计能力"的证据）：
   ```
   apis/          user_api.py role_api.py login_api.py   # 只负责请求，返回 Response
   models/        user.py role.py                        # pydantic 校验响应结构
   assertions/    common.py                              # 统一断言：code / msg / schema / 副作用
   data/          users.yaml roles.yaml                   # 参数化数据源
   utils/         captcha.py db.py logger.py
   conftest.py    fixtures 全集
   ```
   `requests` 返回值统一进 pydantic 模型，字段改名会导致**结构校验失败并指出缺哪个字段**，而不是 `KeyError`。
10. **参数化落地**：把 `docs/test_plan.md` 里的等价类/边界值真正写成 `@pytest.mark.parametrize`（空值、超长、特殊字符、SQL 注入串、XSS 串、emoji、状态码边界 0/1/9）。用例数从 43 涨到 150+，但**代码量反而减少**——这个对比本身就是个好故事。
11. **Allure 报告**替代 pytest-html：`@allure.step` 拆步骤、请求/响应作为附件、失败自动截图（和 UI 层打通时才有）、按 feature/story 分组、缺陷链接到 issue。CI 里发布 `allure-report` 到 GitHub Pages。
12. **CI 真正跑起来**：GitHub Actions 用 `services:` 起 MySQL + Redis，`docker compose` 起后端，等健康检查通过后 `pytest -n 4`（`pytest-xdist`），上传 Allure artifact，PR 里贴结果摘要；加 `ruff` + `mypy` 作为 lint gate。
13. **契约测试**：`schemathesis` 直接吃后端的 OpenAPI（RuoYi 有 `/v3/api-docs`），自动生成上千条边界用例做模糊测试。**在面试里这一项非常加分**，因为它证明你会用工具做"覆盖率的数量级提升"，而不是手写。
14. **性能测试做到能给结论**：Locust 加阶梯加压（`--step-load` 或自定义 shape）、多场景混合权重、登录 token 缓存复用、SLA 断言（P95 < 500ms，错误率 < 1%）、跑出基线写进 README（"200 并发下 TPS 320，P99 480ms，瓶颈在 HikariCP 连接池"）。

### P2 —— 三到六个月，形成"质量体系"叙事（差异化）

15. **UI + API 混合分层**：Playwright 只做 5-10 条核心链路冒烟，**造数和断言全部走 API**（速度差 10 倍），这正好回应"API 测试解决了什么、UI 测试不可替代在哪"。
16. **数据治理**：pytest fixture 里用 DB 直连（或 testcontainers）做"精确造数 + 精确清理"，替代"调接口造数 + 搜列表找 ID"这种脆弱写法。现在 `test_user_api.py:29-36` 那种"创建后翻列表找 ID"的模式，分页一改就崩。
17. **AI 辅助（2026 年的差异化点）**：失败归因（把 traceback + 响应体丢给模型，输出"疑似后端字段改名"）、用例生成（从 OpenAPI 生成用例草稿，人工评审后入库）、日报自动汇总。落地一个最小闭环即可，重点是能讲清"AI 在质量流程里的位置"。
18. **一个轻量测试平台**：FastAPI + 简单前端，做用例管理 / 定时调度 / 执行看板 / 失败趋势。这是"测试开发"岗最硬的敲门砖——**能讲清楚"我从 0 搭过平台"的人，和"我用过平台"的人，是两个价位。**

---

## 六、简历该怎么写

**现在能写的（会被归到功能测试）：**
> 使用 pytest + requests 编写 RuoYi 后台 43 条接口自动化用例，覆盖登录、用户、角色等模块。

**改完 P0 + P1 后能写的：**
> 独立设计分层接口自动化框架（API Object + pydantic 结构校验 + 参数化数据驱动），docker-compose 一键拉起被测环境，GitHub Actions 在每次 PR 执行 180+ 条用例并发布 Allure 报告；以 `xfail` 做缺陷门禁，复现并跟踪 4 个缺陷（含 1 个越权，已修复转绿）；用 schemathesis 对 40+ 端点做契约测试；Locust 压测输出基线（200 并发 TPS 320 / P99 480ms）并定位连接池瓶颈。

差别不在技术栈，在**动词**：从"编写用例"变成"设计框架 / 门禁 / 发布 / 定位"。

---

## 七、一句话总结

这个项目现在最大的问题不是"用例太少"或"技术太旧"，而是**它的绿色不携带任何质量信息**——为了让报告好看，把缺陷写进了断言、把被测系统的源码注释掉了。先把这两件事反向修掉（缺陷变红、源码不碰），再把环境做成一条命令可复现，最后补上契约和性能，它就能从"课程作业"变成"能聊 40 分钟的工程作品"。
