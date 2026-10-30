# 架构说明

> 目标读者：接手这个仓库的人（包括三个月后的自己）。
> 读完应该能回答：加一条新用例要动哪些文件？为什么这么分层？

---

## 1. 分层与职责

```
                    ┌──────────────────────────────────────┐
   tests/           │  用例：编排步骤 + 断言业务语义        │  唯一放 assert 的地方
                    └───────────────┬──────────────────────┘
                                    │ 只用领域对象，不碰 URL
                    ┌───────────────▼──────────────────────┐
   ruoyi/           │  领域层：API Object / 契约 / 工厂      │  知道 RuoYi 的一切
                    └───────────────┬──────────────────────┘
                                    │ 只用通用能力，不知道业务
                    ┌───────────────▼──────────────────────┐
   framework/       │  基础设施：HTTP / 断言 / schema / 配置 │  换项目可整体复用
                    └──────────────────────────────────────┘
```

| 层 | 可以做 | 绝对不做 |
|----|--------|----------|
| `tests/` | 编排、断言、准备数据（通过工厂） | 拼 URL、直接 `requests`、`time.sleep` |
| `ruoyi/` | 拼路径、构造 payload、定义响应契约 | `assert`（否则无法用它测失败路径） |
| `framework/` | 超时、重试、日志、追踪、结构校验 | 出现 "RuoYi"、"system/user" 等字样 |

这个边界由 `tests/test_09_meta.py` 用正则守护：用例里出现 `requests.get(`、`localhost:8080`、`roleIds=[2]`、`sleep(` 会直接失败。

---

## 2. 一次请求的完整链路

```
test_xxx(user_factory)
  │
  ├─ user_factory()                       # 造数据（唯一值）
  │    └─ factories.user_payload()        # data/users.json 模板 + uuid
  │
  ├─ user_api.create(payload)             # 领域层
  │    └─ BaseAPI.post()                  # 拼 /system/user
  │         └─ HttpClient.request()       # framework 层
  │              ├─ 注入 Bearer token
  │              ├─ timeout=(3,10)
  │              ├─ GET 失败重试（指数退避）
  │              ├─ 401 → on_unauthorized 重登一次并重放
  │              ├─ 记录 Exchange 到 RECORDER
  │              └─ 返回 ApiResponse
  │
  ├─ expect_ok(resp)                      # 断言 1：业务码
  ├─ expect_schema(resp, USER_PAGE)       # 断言 2：结构契约
  └─ eventually(lambda: list(...))        # 断言 3：副作用真的落库
       │
       └─ conftest.pytest_runtest_makereport
            └─ 把 RECORDER 里的所有 Exchange 写成报告附件
```

关键点：**每一层只依赖下一层**，没有反向依赖，也没有循环导入。

---

## 3. 三个核心机制

### 3.1 请求追踪（framework/trace.py）

`RECORDER` 是一个模块级列表。`_api_trace` 这个 autouse fixture 在每条用例开始时清空，
`pytest_runtest_makereport` 在用例结束时把它转成 pytest-html 的 `extras` 附件。

为什么不用日志文件？因为日志是"全量的、需要人肉筛的"，而附件是"跟着用例走的、
点开就能看的"。失败时多给的 cURL 让后端同学能原样复现，省掉一轮扯皮。

### 3.2 响应契约（ruoyi/schemas.py + framework/schema.py）

`S.int(enum=[200])` 这类声明式描述，`validate(payload, schema)` 返回**全部**错误（不是第一个），
错误信息带 JSONPath（`$.rows[0].userId`）。

默认允许后端**新增**字段（兼容演进），只在"删字段 / 改类型 / 枚举越界"时报错。
这个取舍很重要：否则后端加一个 `deptName` 字段，你的 148 条用例全部变红。

### 3.3 数据唯一性（framework/data.py）

所有生成值带 `at_` 前缀 + `uuid4` 片段。好处：
- 任意次重跑、任意 worker 并行都不撞唯一索引；
- 出事时能用 `like 'at_%'` 从库里精准捞出来清理。

---

## 4. 加一个新接口，要动哪些文件？

以「新增岗位管理 CRUD」为例：

1. `ruoyi/system.py` 加 `post_create / post_update / post_delete`（只拼路径）。
2. `ruoyi/schemas.py` 加 `POST_ROW / POST_PAGE`。
3. `ruoyi/factories.py` 加 `post_payload()`（唯一 `postCode`）。
4. `conftest.py` 加 `post_factory`（创建 + 自动清理）。
5. `tests/test_10_post_crud.py` 写用例。

**不需要**改 `framework/`。这就是分层的验收标准：如果加接口要改框架，说明抽象错了。

---

## 5. 配置与运行模式

| 变量 | 作用 | 默认 |
|------|------|------|
| `AUTOTEST_TARGET` | `stub` 内置契约桩 / `real` 真实后端 | `stub` |
| `AUTOTEST_BASE_URL` | 真实后端地址 | `http://localhost:8080` |
| `AUTOTEST_CAPTCHA_ENABLED` | 后端是否开验证码 | `false` |
| `AUTOTEST_CAPTCHA_CODE` / `AUTOTEST_REDIS_URL` | 开验证码时怎么取码 | 空 |
| `AUTOTEST_HTTP_RETRIES` | GET 重试次数 | `2` |

配置在 `framework/settings.py` 里**启动即校验**（地址格式、超时正数、real 模式必须有口令），
配错在 import 阶段就炸，不会等到第 30 条用例才报一个看不懂的 ConnectionError。

`Settings` 是 frozen dataclass：运行期不可变。用例改配置是自动化测试里最隐蔽的污染源。

---

## 6. 契约桩的定位（重要）

`stub/` 是一个**忠实模仿 RuoYi 3.9.x 契约**的 Flask 服务，但它不是被测系统。

它存在的三个理由：
1. **离线可跑**：没有 MySQL/Redis/后端时，框架和用例逻辑仍可被验证；
2. **缺陷生命周期可演示**：`AUTOTEST_STUB_REPRODUCE_BUGS=false` 一行切换"缺陷已修复"；
3. **契约基准**：桩 + `schemas.py` 是同一份契约的两个侧面，谁偏离谁错。

使用边界写死在运行时横幅里：目标为 `stub` 时，每次运行都会打印
「结果只能证明框架与用例逻辑正确，不能作为被测系统的质量结论」。

---

## 7. 已知的架构债

- `HttpClient.on_unauthorized` 只支持一个回调，多账号会话（管理员 + 普通用户）时由各自的
  `AuthAPI` 实例注册，目前够用，但如果引入第三种身份需要注意覆盖问题。
- `RECORDER` 是进程级单例，`pytest-xdist` 下每个 worker 独立进程所以安全；
  如果将来改成线程池并发执行用例，需要换成 `contextvars`。
- 契约桩与真实 RuoYi 的差异会随版本漂移，**每次升级 RuoYi 都要跑一遍 e2e job 校准**。
