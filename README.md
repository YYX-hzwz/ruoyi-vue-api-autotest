# RuoYi-Vue 接口自动化测试框架

面向 [RuoYi-Vue](https://github.com/yangzongzhuan/RuoYi-Vue) 后台管理系统的接口自动化测试项目。148 条用例，按测试类型分层，已知缺陷以 `xfail` 固化，运行依赖仅 `requests` + `pytest` + `pytest-html`。

```bash
pip install -r requirements.txt
py -m pytest
```

无需数据库与后端：默认 `AUTOTEST_TARGET=stub` 会在随机端口启动内置契约桩。

产物：`reports/report.html`（用例与请求响应附件）、`reports/QUALITY.md`（质量看板）、`reports/summary.json`（机器可读）。

## 特性

- **分层结构**：通用测试基础设施与被测系统领域层分离，替换被测系统时框架层无需改动。
- **统一断言**：业务码、响应契约、分页关系、权限状态集中封装，失败信息包含请求、响应与可复现 cURL。
- **缺陷门禁**：已知缺陷绑定回归用例，以 `xfail` 标记；修复后自动转为 `xpass` 并提示移除标记。
- **套件自检**：22 条 meta test 检查硬编码、裸 `sleep`、缺陷与用例的绑定关系。
- **离线可运行**：内置契约桩，无外网、无数据库环境下可完成全量回归。

## 快速开始

### 环境要求

- Python 3.11+
- 仅运行契约桩：无需 MySQL / Redis / 后端
- 运行真实后端：Docker Desktop 与 RuoYi-Vue 源码（默认位于本项目上一级目录）

### 仅运行契约桩

```bash
pip install -r requirements.txt
cp .env.example .env          # Windows: copy .env.example .env
py -m pytest
```

### 运行真实 RuoYi 后端

```powershell
.\scripts\run-real.cmd              # 起 MySQL/Redis/后端 + 跑全量
.\scripts\run-real.cmd -InfraOnly   # 只起依赖，后端由 IDE 启动
.\scripts\run-real.cmd -Down        # 清理
```

Windows 默认禁止执行 `.ps1`（`about_Execution_Policies`），脚本提供 `.cmd` 包装，内部以 `-ExecutionPolicy Bypass` 调用同名 `.ps1`。如需直接运行 `.ps1`：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

手工方式：

```bash
docker compose -f docker/docker-compose.yml --env-file .env up -d mysql redis db-init
# 后端用 IDE 或 mvn -pl ruoyi-admin spring-boot:run
AUTOTEST_TARGET=real AUTOTEST_BASE_URL=http://localhost:8080 py -m pytest
```

详细步骤与排错见 [docs/run-real-backend.md](docs/run-real-backend.md)。

### 常用命令

```bash
py -m pytest -m contract          # 仅契约测试
py -m pytest -m permission        # 仅权限矩阵
py -m pytest -k user              # 按名称筛选
py -m pytest --collect-only -q    # 仅收集，检查用例集合
.\scripts\demo-defect-lifecycle.cmd   # 缺陷状态 xfail -> xpass 演示
```

## 配置

所有变量以 `AUTOTEST_` 为前缀，通过环境变量或 `.env` 提供；环境变量优先。配置在导入阶段完成校验，非法值直接抛出异常。

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AUTOTEST_TARGET` | `stub` | `stub` 使用内置契约桩；`real` 连接真实后端 |
| `AUTOTEST_BASE_URL` | `http://localhost:8080` | 真实后端地址 |
| `AUTOTEST_ADMIN_USER` / `AUTOTEST_ADMIN_PASS` | `admin` / `admin123` | 测试账号；`real` 模式下必须提供口令 |
| `AUTOTEST_CAPTCHA_ENABLED` | `false` | 后端是否开启验证码 |
| `AUTOTEST_CAPTCHA_CODE` | 空 | 固定验证码；为空时按桩接口、Redis 顺序取值 |
| `AUTOTEST_REDIS_URL` | `redis://localhost:6379/0` | 读取真实验证码时使用 |
| `AUTOTEST_HTTP_CONNECT_TIMEOUT` / `AUTOTEST_HTTP_READ_TIMEOUT` | `3` / `10` | 连接与读取超时（秒） |
| `AUTOTEST_HTTP_RETRIES` | `2` | GET 等幂等请求的重试次数 |
| `AUTOTEST_RUN_ID` | 空 | 并发执行时的数据命名空间 |
| `AUTOTEST_STUB_PORT` | `0` | 契约桩端口，`0` 表示自动分配 |
| `AUTOTEST_STUB_REPRODUCE_BUGS` | `true` | 契约桩是否复现已知缺陷 |
| `AUTOTEST_LOG_LEVEL` | `INFO` | 日志级别 |

## 项目结构

```
autotest/
├── framework/              通用测试基础设施（与 RuoYi 无关）
│   ├── settings.py         环境配置，导入期校验，不可变
│   ├── http.py             HttpClient：超时、重试、401 重登、请求追踪
│   ├── assertions.py       统一断言：expect_ok / expect_perm_denied / eventually
│   ├── schema.py           响应结构校验 DSL
│   ├── data.py             唯一数据工厂（uuid + 前缀）
│   ├── trace.py            请求响应追踪，写入 pytest-html 附件
│   └── logger.py           日志与敏感信息脱敏
├── ruoyi/                  被测系统领域层
│   ├── auth.py user.py role.py system.py   API Object：构造请求并返回响应
│   ├── schemas.py          接口契约
│   ├── factories.py        基线数据与覆写
│   ├── constants.py        枚举、文案、权限标识
│   └── cleanup.py          异常路径用例的兜底清理
├── tests/                  用例，按测试类型分层
│   ├── test_01_auth.py             认证与令牌
│   ├── test_02_user_crud.py        CRUD 与副作用回查
│   ├── test_03_user_validation.py  参数校验（数据驱动）
│   ├── test_04_role_crud.py        角色与引用完整性
│   ├── test_05_permission_matrix.py 权限矩阵
│   ├── test_06_common_api.py       公共接口
│   ├── test_07_contract.py         传输层契约
│   ├── test_08_defects.py          缺陷回归（xfail）
│   └── test_09_meta.py             套件自检
├── stub/                   契约桩（Flask，含缺陷开关）
├── defects/registry.json   缺陷登记表
├── docker/                 MySQL、Redis、后端编排与初始化 SQL
├── data/                   数据模板与参数化用例
├── docs/                   架构、测试方案、缺陷、真实环境
├── scripts/                辅助脚本
└── reports/                产物（gitignore）
```

## 设计说明

### 分层

`framework/` 不包含业务语义，`ruoyi/` 承载被测系统的路径、字段与契约，`tests/` 只负责编排与断言。接入其他系统时替换 `ruoyi/` 即可，`framework/` 无需修改。

### API Object 不做断言

API Object 仅构造请求并返回响应对象，断言集中在用例层。若在 API 方法内断言成功，则同一方法无法用于异常路径，需要为失败场景复制方法。

### 缺陷管理

已知缺陷固化在 `tests/test_08_defects.py`，并与 `defects/registry.json` 双向绑定，由 meta test 校验一致性。缺陷用例以 `xfail(strict=False)` 标记：缺陷存在时报告保持红色信号；修复后自动转为 `xpass`，会话结束时提示移除标记。使用 `strict=False` 是为了避免缺陷修复时 CI 因标记未清理而失败。

### 契约桩

`stub/` 是离线环境下的契约实现，用于验证框架与用例逻辑。对 RuoYi 的质量结论仅来自 `AUTOTEST_TARGET=real`，两者职责不同，不可互相替代。

### 依赖取舍

运行依赖限定为 `requests` + `pytest` + `pytest-html`。响应结构校验、配置加载、日志脱敏、报告附件均自行实现，以保证在无外网环境中可完整运行。替换为 Allure、pydantic 或 jsonschema 时，改动范围限于 `framework/`。

### 两项用例约束

- 分页断言校验 `total` 与当页行数的关系，而非仅 `len(rows) <= pageSize`：后者在后端忽略分页参数时同样成立。
- 删除类越权用例使用不存在的主键（如 `999999`），即使权限失效也不会破坏数据。

## 测试策略

| 层 | 文件 | 覆盖内容 | 典型断言 |
|----|------|----------|----------|
| 冒烟 | `test_01` | 登录链路、token 生效与失效 | 登录返回 token；登出后 401 |
| 功能 | `test_02/04/06` | CRUD、分页 | 写入后回查；`len(rows)` 与 `total` 一致 |
| 校验 | `test_03` | 非法输入、边界值 | 数据驱动 9 组非法值 + 30/31 边界 |
| 权限 | `test_05` | 横向越权、提权、401/403 区分 | 14 项矩阵；提权后以管理员视角回查 |
| 契约 | `test_07` | 字段改名、类型漂移、信封结构 | Content-Type、`code` 类型、分页信封 |
| 缺陷回归 | `test_08` | 已知问题不复发 | 3 条 xfail |

## 已知缺陷

| ID | 级别 | 问题 | 期望 | 现状 | 对应用例 |
|----|------|------|------|------|----------|
| BUG-001 | 中 | 创建用户未校验密码长度 | 拒绝 3 位密码 | 写入成功 | `test_08::test_weak_password_rejected` |
| BUG-002 | 高 | 普通角色可读用户列表 | `code=403` | 返回全部用户 | `test_08::test_normal_user_cannot_list_users` |
| BUG-003 | 低 | 角色 `status` 未做枚举校验 | 拒绝 `status=9` | 入库成功 | `test_08::test_invalid_role_status_rejected` |

全量执行时上述用例表现为 `xfail`；契约桩关闭缺陷复现（`AUTOTEST_STUB_REPRODUCE_BUGS=false`）后转为 `xpass`：

```bash
.\scripts\demo-defect-lifecycle.cmd
# 第 1 轮 144 passed / 3 xfailed
# 第 2 轮 144 passed / 3 xpassed
```

BUG-002 的判定涉及权限配置，排查过程见 [docs/defects.md](docs/defects.md)。

## 报告

- `report.html`：每条用例可展开「API 交互记录」（method、URL、状态码、耗时、请求体、响应体），失败时附带复现用 cURL。
- `QUALITY.md`：结果分布、模块分布、缺陷状态表。
- `summary.json`：机器可读，供 CI 判断缺陷状态。

失败信息示例：

```
ApiAssertionError: 期望业务码 403（无权限），实际 200（msg='查询成功'）

GET /system/user/list?pageNum=1&pageSize=10 -> HTTP 200 / code=200 / 3ms
msg='查询成功'
body={"code":200,"total":2,"rows":[...]}
```

## 性能基线

```bash
locust -f performance_test/locustfile.py --headless -t 3m --html reports/perf.html
```

- 业务断言：RuoYi 以 `HTTP 200 + code=500` 表达错误，仅校验状态码会漏判，脚本同时校验 `code`。
- 阶梯加压：10 → 30 → 60 并发，观察 TPS 拐点。
- SLA 门禁：`P95 > 800ms` 或失败率 > 1% 时退出码为 1。

## 验证状态

| 内容 | 状态 | 说明 |
|------|------|------|
| 契约桩全量用例 | 已验证 | 144 passed / 3 xfailed / 1 skipped |
| 缺陷状态流转 | 已验证 | 第二轮 144 passed / 3 xpassed |
| 报告生成（html / md / json） | 已验证 | 附件与质量看板均有内容 |
| 性能脚本可加载 | 已验证 | `locust --list` 通过；未执行压测 |
| docker compose | 未验证 | 本机 Docker 守护进程未启动 |
| GitHub Actions | 未验证 | 工作流未实际触发 |
| 真实 RuoYi 后端全量 | 部分验证 | 117 passed / 27 failed / 3 xfailed；失败项来自接口契约与权限模型差异，校准方法见 `docs/run-real-backend.md` |

## 文档

- [docs/architecture.md](docs/architecture.md)：模块职责与数据流
- [docs/test_plan.md](docs/test_plan.md)：测试范围与用例设计
- [docs/defects.md](docs/defects.md)：缺陷详情与排查过程
- [docs/run-real-backend.md](docs/run-real-backend.md)：真实环境搭建与排错

## 后续计划

Playwright UI 冒烟（接口造数 + 页面断言）、Testcontainers 隔离依赖、消息队列异步校验、在 GitHub Actions 中运行真实后端。
