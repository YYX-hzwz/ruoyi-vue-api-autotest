"""RuoYi 接口性能基线（Locust）。

和"跑个 locust 截张图"的区别：
1. **业务断言**：RuoYi 的业务错误是 HTTP 200 + body.code=500，
   只看 HTTP 状态码会把一半的失败算成成功。这里对 code 做校验，
   失败会计入 fail_ratio 而不是静默通过。
2. **阶梯加压**：内置 StagesShape（30s→60s→90s 三档并发），
   用来观察 TPS 拐点和响应时间随并发的劣化曲线。
3. **SLA 门禁**：退出时校验 P95 与失败率，超标时 exit code = 1，
   可以直接挂进 CI 当作性能回归。

运行：
    locust -f performance_test/locustfile.py --headless -t 3m --html reports/perf.html
    # 指定目标
    LOCUST_HOST=http://127.0.0.1:8080 locust -f ... --headless -u 50 -r 5 -t 2m

环境变量：
    LOCUST_HOST       被测地址，默认 http://localhost:8080
    LOCUST_USER/PASS  登录账号，默认 admin/admin123
    SLA_P95_MS        P95 上限，默认 800
    SLA_FAIL_RATIO    失败率上限，默认 0.01
"""

from __future__ import annotations

import os

from locust import HttpUser, between, events, task

HOST = os.getenv("LOCUST_HOST", "http://localhost:8080")
USERNAME = os.getenv("LOCUST_USER", "admin")
PASSWORD = os.getenv("LOCUST_PASS", "admin123")
SLA_P95_MS = float(os.getenv("SLA_P95_MS", "800"))
SLA_FAIL_RATIO = float(os.getenv("SLA_FAIL_RATIO", "0.01"))


class RuoYiUser(HttpUser):
    """模拟登录后的后台用户：读多写少。"""

    host = HOST
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        with self.client.post(
            "/login",
            json={"username": USERNAME, "password": PASSWORD, "code": "", "uuid": ""},
            name="POST /login",
            catch_response=True,
        ) as response:
            if response.status_code != 200:
                response.failure(f"登录 HTTP {response.status_code}")
                return
            body = response.json()
            if body.get("code") != 200 or not body.get("token"):
                response.failure(f"登录失败: {body.get('msg')!r}")
                return
            self.client.headers.update({"Authorization": f"Bearer {body['token']}"})

    # ---- 读场景（权重体现真实流量分布）----
    @task(10)
    def user_list(self) -> None:
        self._get("/system/user/list?pageNum=1&pageSize=10", "GET 用户列表")

    @task(6)
    def user_detail(self) -> None:
        self._get("/system/user/1", "GET 用户详情")

    @task(5)
    def role_list(self) -> None:
        self._get("/system/role/list?pageNum=1&pageSize=10", "GET 角色列表")

    @task(4)
    def dict_data(self) -> None:
        self._get("/system/dict/data/type/sys_normal_disable", "GET 字典数据")

    @task(3)
    def dept_list(self) -> None:
        self._get("/system/dept/list", "GET 部门列表")

    @task(2)
    def get_info(self) -> None:
        self._get("/getInfo", "GET 当前用户")

    def _get(self, path: str, name: str) -> None:
        with self.client.get(path, name=name, catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            try:
                body = response.json()
            except ValueError:
                response.failure("响应不是 JSON")
                return
            code = body.get("code")
            if code != 200:
                response.failure(f"业务码 {code}: {body.get('msg')}")


class StagesShapeBase:
    """占位基类：真正的 LoadTestShape 由 locust 提供，见文件末尾的条件定义。"""


class StagesShape(StagesShapeBase):
    """阶梯加压：低并发 → 中并发 → 高并发，用来看 TPS 拐点。

    注意：Locust 的 `LoadTestShape` 会接管并发数，此时命令行 `-u/-r` 失效。
    只想固定并发压测时，设置 `LOCUST_SHAPE=0` 即可让本类不被注册。
    """

    stages = [
        (30, 10),   # (持续秒数, 目标并发)
        (45, 30),
        (45, 60),
    ]

    def tick(self):  # type: ignore[no-untyped-def]
        run_time = self.get_run_time()
        elapsed = 0
        for duration, users in self.stages:
            if run_time < elapsed + duration:
                return (users, max(users // 5, 1))
            elapsed += duration
        return None


@events.quitting.add_listener
def _sla_check(environment, **_kwargs) -> None:  # type: ignore[no-untyped-def]
    total = environment.stats.total
    if total.num_requests == 0:
        environment.process_exit_code = 1
        print("[SLA] 没有产生任何请求，视为失败")
        return

    p95 = total.get_response_time_percentile(0.95) or 0
    fail_ratio = total.fail_ratio
    print("\n================ 性能基线 ================")
    print(f"请求数        : {total.num_requests}")
    print(f"失败率        : {fail_ratio:.2%}（SLA < {SLA_FAIL_RATIO:.2%}）")
    print(f"平均响应      : {total.avg_response_time:.0f} ms")
    print(f"P50 / P95     : {total.get_response_time_percentile(0.5):.0f} / {p95:.0f} ms（SLA < {SLA_P95_MS:.0f}）")
    print(f"TPS           : {total.total_rps:.1f}")
    print("==========================================")

    violations = []
    if p95 > SLA_P95_MS:
        violations.append(f"P95 {p95:.0f}ms 超过 {SLA_P95_MS:.0f}ms")
    if fail_ratio > SLA_FAIL_RATIO:
        violations.append(f"失败率 {fail_ratio:.2%} 超过 {SLA_FAIL_RATIO:.2%}")

    if violations:
        print("[SLA] 未达标: " + "; ".join(violations))
        environment.process_exit_code = 1
    else:
        print("[SLA] 达标")


# locust 通过"是否存在 LoadTestShape 子类"来决定是否启用自定义加压曲线。
# 默认启用；`LOCUST_SHAPE=0` 时本类不继承 LoadTestShape，因此不会被接管。
if os.getenv("LOCUST_SHAPE", "1") == "1":
    from locust import LoadTestShape

    StagesShape.__bases__ = (LoadTestShape,)
