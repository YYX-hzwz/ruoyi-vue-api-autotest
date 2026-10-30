# 跑真实 RuoYi 后端

> 契约桩能验证"框架对不对"，但**质量结论必须来自真实后端**。
> 这份文档是首次跑真实环境时最容易卡住的几个点。

---

## 1. 前置条件

| 依赖 | 版本 | 说明 |
|------|------|------|
| Docker Desktop | 任意近两年版本 | 提供 MySQL 8 + Redis 7；可选把后端也容器化 |
| RuoYi-Vue 源码 | 3.9.x | 需要 `sql/ry_*.sql` 和 `pom.xml` |
| Python | 3.10+ | 本机验证用的是 3.14 |
| JDK | 17 | RuoYi 3.9.x 要求；容器化方案不需要本机装 |

默认目录布局（本项目假设的）：

```
RuoYi-Vue/
├── pom.xml
├── sql/
└── autotest/          <- 本项目
```

如果不是这个布局，设置 `RUOYI_HOME` 指向源码根目录。

---

## 2. 方案 A：只把依赖容器化（推荐，最快）

后端用 IDE 跑，改代码即时生效，适合调试和写用例。

```powershell
cd autotest
copy .env.example .env
.\scripts\run-real.ps1 -InfraOnly
```

然后 IDEA 里启动 `ruoyi-admin` 的 `RuoYiApplication`，或者：

```bash
cd $RUOYI_HOME
mvn -pl ruoyi-admin -am spring-boot:run
```

确认后端起来：

```bash
curl http://localhost:8080/captchaImage
# {"code":200,"msg":"操作成功","captchaEnabled":false,"uuid":"","img":""}
```

`captchaEnabled:false` 是关键——`docker/mysql/zz-test-env.sql` 已经把
`sys.account.captchaEnabled` 改成 `false`。如果这里是 `true`，说明 db-init 没跑成功。

最后：

```powershell
.\scripts\run-tests.ps1 -Target real
```

---

## 3. 方案 B：全容器化（一条命令）

```powershell
.\scripts\run-real.ps1
```

等价于：

```bash
docker compose -f docker/docker-compose.yml --env-file .env --profile backend up -d --build --wait
```

首次构建要下载 Maven 依赖，通常 3~10 分钟。镜像基于 `maven:3.9-eclipse-temurin-17` +
`eclipse-temurin:17-jre`。

> ⚠️ 该方案在开发本机**未能验证**（Docker 守护进程不可用）。
> 首次执行如果失败，先看 `docker compose logs db-init` 和 `logs ruoyi`，常见问题见第 6 节。

---

## 4. 手工执行 SQL（不用 db-init 容器时）

`sql/ry_20260417.sql` 和 `sql/quartz.sql` 里**没有** `CREATE DATABASE` / `USE` 语句，
必须自己建库并指定库名，否则会报 "No database selected"：

```bash
mysql -h 127.0.0.1 -uroot -proot -e "CREATE DATABASE IF NOT EXISTS \`ry-vue\` DEFAULT CHARSET utf8mb4"
mysql -h 127.0.0.1 -uroot -proot ry-vue < sql/ry_20260417.sql
mysql -h 127.0.0.1 -uroot -proot ry-vue < sql/quartz.sql
mysql -h 127.0.0.1 -uroot -proot ry-vue < autotest/docker/mysql/zz-test-env.sql
```

---

## 5. 指向一个远端后端（不用 docker）

```bash
AUTOTEST_TARGET=real \
AUTOTEST_BASE_URL=http://10.0.0.8:8080 \
AUTOTEST_ADMIN_USER=admin \
AUTOTEST_ADMIN_PASS=****** \
AUTOTEST_CAPTCHA_ENABLED=true \
AUTOTEST_REDIS_URL=redis://10.0.0.9:6379/0 \
py -m pytest
```

注意：**不要**在远端环境跑删除类用例。默认用例都是自建数据 + 自清理，
但 `test_cannot_delete_super_admin` 这类会尝试删除 `userId=1`（会被后端拒绝）。
如果目标环境是共享测试库，先跟负责人确认。

---

## 6. 常见问题

### 6.1 登录返回"验证码已失效" / "验证码错误"

后端开了验证码，但框架没取到码。三选一：

```bash
# a) 测试库直接关掉（推荐）
mysql ... -e "UPDATE sys_config SET config_value='false' WHERE config_key='sys.account.captchaEnabled'"

# b) 测试环境把验证码固定成 1111
AUTOTEST_CAPTCHA_CODE=1111

# c) 直连 Redis 读 captcha_codes:{uuid}
AUTOTEST_REDIS_URL=redis://localhost:6379/0
```

注意 `pip install redis` 是方案 c 的前置；没装时框架会直接告诉你缺什么，不会静默失败。

### 6.2 报"被测后端不可达"并退出（returncode=2）

这是**故意**的快速失败。fixture 在会话开始就探活，避免 148 条用例各报一次
ConnectionError 把输出刷满。检查：

```bash
curl -i http://localhost:8080/captchaImage
```

### 6.3 权限矩阵全红 / 全绿

- 全红：`common` 角色不存在或菜单权限被回收过度。检查
  `role_api.list(role_key="common")` 是否有数据。
- 全绿（本该拒绝的也 200）：可能是 BUG-002 在真实环境复现了——这正是我们要的信号，
  去看报告里那条 `xfail` 是 `xfailed` 还是 `xpassed`。

### 6.4 用户创建报"手机号码已存在"

说明数据库里已有历史测试数据。本项目所有数据带 `at_` 前缀，可安全清理：

```sql
DELETE FROM sys_user WHERE user_name LIKE 'at_%';
DELETE FROM sys_role WHERE role_key LIKE 'at_role_%';
```

### 6.5 分页断言失败："total > pageSize 但本页却是 0 条"

真实 RuoYi 的 `pageNum` 从 1 开始，传 0 或负数行为未定义。
用例里只对合法页做严格断言，边界页只要求"不 5xx"。

---

## 7. 首次跑通后的建议动作

1. 把 `reports/report.html` 和 `reports/QUALITY.md` 存档，作为基线；
2. 对比桩环境与真实环境的 xfail 结果差异——差异就是"桩与真实后端的契约漂移"；
3. 若 BUG-002 在真实环境复现，按 `docs/defects.md` 的假设-验证表确认根因，再决定是提缺陷还是提配置变更。
