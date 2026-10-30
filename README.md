# RuoYi-Vue 接口自动化测试框架

面向 [RuoYi-Vue](https://github.com/yangzongzhuan/RuoYi-Vue) 的接口自动化测试项目：**148 条用例、5 层测试策略、3 个缺陷以 xfail 固化、零第三方测试框架依赖**。

```bash
py -m pytest          # 不需要数据库、不需要起后端，10 秒内出报告
```

报告产物：`reports/report.html`（用例 + 请求响应附件）、`reports/QUALITY.md`（质量看板）、`reports/summary.json`（机器可读）。

---

## 1. 30 秒看结论

| 维度 | 现状 |
|------|------|
| 用例规模 | 148 条（含 14 项权限矩阵、15 条参数化校验、21 条契约断言） |
| 执行速度 | 全量约 4s（契约桩）/ 真实后端约 30s |
| 缺陷管理 | 3 个已知缺陷绑定回归用例，`xfail` 门禁，修复后自动提示转绿 |
| 可复现性 | 一条命令起环境（契约桩内置；真实后端用 docker compose） |
| 可诊断性 | 失败用例自动附「请求/响应 JSON + 可复制 cURL」 |
| 自检能力 | 22 条 meta test 守护"禁止硬编码 / 禁止裸 sleep / 缺陷必须绑定用例" |

---

## 2. 这个项目想证明什么

不是"我会用 requests 发请求"，而是四件面试里更值钱的事：

1. **能设计，而不是堆**。`framework/` 是通用测试基础设施（配置/HTTP/断言/契约/数据/追踪），`ruoyi/` 是被测系统领域层（API Object/工厂/契约/清理）。换一个被测系统，`framework/` 一行不用改。
2. **断言能抓住缺陷，而不是把缺陷写成通过**。见第 6 节：发现的问题被写成**会红**的用例，而不是 `assert code == 200  # 这是缺陷`。
3. **失败能自证原因**。每条用例的请求/响应都作为附件进报告，失败时直接给 cURL，后端同学能原样复现。
4. **质量可以被门禁化**。CI 里两轮跑：缺陷存在时 3 xfail，模拟修复后 3 xpass，说明"缺陷 → 用例 → 修复 → 回归"的链路是通的。

## 3. 也能看清它的边界

- 契约桩（`stub/`）**不是被测系统**，它只保证"框架与用例逻辑正确"。对 RuoYi 的质量结论必须来自 `AUTOTEST_TARGET=real`。这条边界在每次运行的横幅、README、报告里都写死了。
- 3 个缺陷的判定基于 RuoYi-Vue 3.9.2 的默认配置。换版本要重新确认（尤其 BUG-002 涉及权限配置，见 `docs/defects.md` 的排查方法）。
- 还没做：UI 层（Playwright）、接口加密/签名、消息队列异步校验、多租户数据隔离。这些在 `docs/学习路线.md` 的"下一步"里。

---

## 4. 快速开始

### 4.1 只跑框架（推荐先跑这个）

```bash
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
py -m pytest
```

不需要 MySQL、Redis、后端。`AUTOTEST_TARGET=stub` 会在随机端口起一个 RuoYi 契约桩。

### 4.2 跑真实 RuoYi 后端

需要 Docker Desktop + RuoYi-Vue 源码（默认认为源码在本项目的上一级）：

```powershell
.\scripts\run-real.cmd              # 起 MySQL/Redis/后端 + 跑全量
.\scripts\run-real.cmd -InfraOnly   # 只起依赖，后端用 IDE 起
.\scripts\run-real.cmd -Down        # 清理
```

> Windows 默认禁止运行 `.ps1`（`about_Execution_Policies`）。所以脚本都配了 `.cmd` 包装，
> 内部用 `-ExecutionPolicy Bypass` 调用同名 `.ps1`。想直接用 `.ps1` 就先执行：
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`。

手工方式：

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d mysql redis db-init
# 后端用 IDE 或 mvn -pl ruoyi-admin spring-boot:run
# 然后：
AUTOTEST_TARGET=real AUTOTEST_BASE_URL=http://localhost:8080 py -m pytest
```

细节与排错见 [docs/run-real-backend.md](docs/run-real-backend.md)。

### 4.3 常用命令

```bash
py -m pytest -m contract          # 只跑契约测试
py -m pytest -m permission        # 只跑权限矩阵
py -m pytest -k user              # 按名字筛
py -m pytest --collect-only -q    # 只收集，检查用例集合
.\scripts\demo-defect-lifecycle.cmd   # 缺陷红 -> 绿 演示
```

---

## 5. 工程结构

```
autotest/
├── framework/              通用测试基础设施（与 RuoYi 无关，可复用）
│   ├── settings.py         环境配置，启动即校验，不可变
│   ├── http.py             HttpClient：超时/重试/401 自动重登/请求追踪
│   ├── assertions.py       统一断言：expect_ok / expect_perm_denied / eventually
│   ├── schema.py           响应结构校验 DSL（零依赖替代 jsonschema/pydantic）
│   ├── data.py             唯一数据工厂（uuid + 前缀，可识别可清理）
│   ├── trace.py            请求响应追踪（挂进 pytest-html 附件）
│   └── logger.py           日志 + 敏感信息脱敏
├── ruoyi/                  被测系统领域层
│   ├── auth.py user.py role.py system.py   API Object：只发请求，不断言
│   ├── schemas.py          接口契约（活文档）
│   ├── factories.py        合法基线数据 + 覆写
│   ├── constants.py        枚举/文案/权限标识，杜绝魔法值
│   └── cleanup.py          负向用例的兜底清理
├── tests/                  用例（按测试类型分层，不是按接口分）
│   ├── test_01_auth.py           认证与令牌
│   ├── test_02_user_crud.py      CRUD + 副作用回查
│   ├── test_03_user_validation.py 参数校验（数据驱动）
│   ├── test_04_role_crud.py      角色 + 引用完整性
│   ├── test_05_permission_matrix.py 权限矩阵
│   ├── test_06_common_api.py     公共接口
│   ├── test_07_contract.py       传输层契约
│   ├── test_08_defects.py        缺陷回归（xfail）
│   └── test_09_meta.py           套件自检
├── stub/                   契约桩（Flask，含缺陷开关）
├── defects/registry.json   缺陷登记表（id 与用例绑定，meta test 校验）
├── docker/                 MySQL/Redis/后端编排 + 测试环境 SQL
├── data/                   数据模板与参数化用例
├── docs/                   架构、测试方案、缺陷、真实环境、学习路线
├── scripts/                一键脚本
└── reports/                产物（gitignore）
```

**为什么 API Object 里不断言？** 一旦 `create_user()` 内部写了 `assert code==200`，就无法再用它测"创建失败"的路径了，只能复制一个 `create_user_raw()`。断言放用例层，API 层只负责请求。

---

## 6. 发现的问题：3 个缺陷，3 条会红的用例

| ID | 级别 | 问题 | 期望 | 现状 | 对应用例 |
|----|------|------|------|------|----------|
| BUG-001 | 中 | 创建用户未校验密码长度 | 拒绝 3 位密码 | 写入成功 | `test_08::test_weak_password_rejected` |
| BUG-002 | 高 | 普通角色可读用户列表 | code=403 | 返回全部用户 | `test_08::test_normal_user_cannot_list_users` |
| BUG-003 | 低 | 角色 status 未做枚举校验 | 拒绝 status=9 | 入库成功 | `test_08::test_invalid_role_status_rejected` |

关键点：**这些用例现在跑出来是红色的（xfail），不是绿色的。** 完整报告里它们是 `3 xfailed`，而不是塞一句 `# 这是缺陷，先让它过`。修复后自动变成 `3 xpassed`，控制台提示"请移除 xfail 标记"。

```bash
.\scripts\demo-defect-lifecycle.cmd
# 第 1 轮 passed=144 xfailed=3
# 第 2 轮 passed=144 xpassed=3  -> [!] BUG-001, BUG-002, BUG-003 已修复，请移除 xfail 标记
```

另外记一笔：上一版把"验证码开关改配置不生效"当成缺陷记录了，实际是 RuoYi 的设计——开关真正由 `sys_config` 表控制。这类"认知修正"也写进了 `docs/defects.md`，因为它比多报一个假缺陷更能说明测试人员的判断力。

---

## 7. 测试策略：分五层，解决五类问题

| 层 | 文件 | 解决什么 | 典型断言 |
|----|------|----------|----------|
| 冒烟 | `test_01` | 登录链路通不通、token 生不生效 | 登录拿到 token、登出后 401 |
| 功能 | `test_02/04/06` | CRUD 是否正确、分页是否真生效 | 写入后回查、`len(rows)==pageSize` |
| 校验 | `test_03` | 非法输入是否被拦、边界是否正确 | 数据驱动 9 组非法值 + 30/31 边界 |
| 权限 | `test_05` | 横向越权、提权、401/403 区分 | 14 项矩阵；提权后用**管理员视角**回查 |
| 契约 | `test_07` | 字段改名/类型漂移/信封不一致 | Content-Type、code 类型、分页信封 |
| 缺陷回归 | `test_08` | 已知问题不复发 | 3 条 xfail |

两个刻意为之的设计：

- **分页断言不是 `len(rows) <= pageSize`**。后端完全忽略分页参数时这个断言照样成立。这里校验 `total > pageSize` 时本页必须满页。
- **越权用例不碰真实数据**。删除类越权用 `999999` 这种不存在的主键，即使权限失效也不会毁数据；确认"管理员没被删"用独立的正向断言。

---

## 8. 报告与可诊断性

- `report.html`：pytest-html，每条用例可展开「API 交互记录」（method/url/status/耗时/请求体/响应体），失败时额外附「复现用 cURL」。
- `QUALITY.md`：结果分布、模块分布、缺陷状态表。CI 里直接作为 artifact。
- `summary.json`：机器可读，CI 用它对"缺陷是否转绿"做门禁。

失败样例长这样：

```
ApiAssertionError: 期望业务码 403（无权限），实际 200（msg='查询成功'）

GET /system/user/list?pageNum=1&pageSize=10 -> HTTP 200 / code=200 / 3ms
msg='查询成功'
body={"code":200,"total":2,"rows":[...]}
```

不需要再去问后端"你当时返回了什么"。

---

## 9. 性能基线

```bash
locust -f performance_test/locustfile.py --headless -t 3m --html reports/perf.html
```

- 业务断言：RuoYi 的错误是 `HTTP 200 + code=500`，只看状态码会把一半失败算成成功，这里校验 `code`。
- 阶梯加压：10 → 30 → 60 并发，看 TPS 拐点。
- SLA 门禁：`P95 > 800ms` 或失败率 > 1% 时进程退出码为 1，可以直接挂 CI。

---

## 10. 验证状态（哪些跑过、哪些没跑过）

诚实标注，避免"README 写完就算做完"。

| 内容 | 状态 | 说明 |
|------|------|------|
| 契约桩全量用例 | ✅ 已在本机验证 | 144 passed / 3 xfailed / 1 skipped |
| 缺陷生命周期红→绿 | ✅ 已在本机验证 | 第二遍 144 passed / 3 xpassed |
| 报告生成（html/md/json） | ✅ 已在本机验证 | 附件与质量看板均有内容 |
| 性能脚本可加载 | ✅ 已用 `locust --list` 验证 | 未实跑压测（本机无后端） |
| docker compose | ⚠️ 未在本机验证 | 本机 Docker 守护进程未启动 |
| GitHub Actions | ⚠️ 未在本机验证 | 无网络，工作流未实际触发 |
| 真实 RuoYi 后端跑全量 | ⚠️ 未在本机验证 | 同上；按 `docs/run-real-backend.md` 首次执行时请留意 |

---

## 11. 设计取舍（面试会被问）

**为什么不用 pytest-allure / pydantic / jsonschema？**
本项目开发环境没有外网，装不了。于是把依赖压到 `requests + pytest + pytest-html`，schema 校验、配置加载、日志脱敏、报告附件全部手写（约 600 行）。取舍是：换来了"任何 Python 环境 clone 即跑"，代价是没有 Allure 的用例树和步骤分组。生产项目里我会直接上 Allure + pydantic——`framework/` 的接口边界就是为了让这个替换只影响一层。

**为什么要有契约桩？**
因为 CI 里起真后端成本太高（MySQL + Redis + Maven 构建 + 3 分钟启动），而如果 CI 因此只做 `compileall`，那等于没有自动化。桩让"框架和用例逻辑"每次提交都被验证；"被测系统真实行为"由手动触发的 e2e job 兜底。两者职责不同，不能互相替代。

**为什么 xfail 用 `strict=False`？**
`strict=True` 会在缺陷修复的瞬间把 CI 判红，逼迫"改 bug 的人"和"改用例的人"必须同一个提交。现实中往往不是同一个人。这里改成 `strict=False` + 会话结束主动提示，既不误伤 CI，也不会让 xfail 被遗忘。

**为什么 148 条而不是 40 条？**
用例数量不是目标。这里增长来自三处：权限矩阵（14）、参数化非法输入（15）、契约断言（13）。它们各自用**一个**测试函数覆盖一类问题，而不是复制粘贴。如果一个项目用例数是靠 copy-paste 涨上去的，那不是覆盖率高，是维护成本高。

---

## 12. 下一步

见 [docs/学习路线.md](docs/学习路线.md) 的"进阶"章节：Playwright UI 冒烟（API 造数 + UI 断言）、Testcontainers、消息队列异步校验、GitHub Actions 里跑真实后端。
