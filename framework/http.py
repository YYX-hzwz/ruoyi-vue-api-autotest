"""HTTP 客户端。

这里集中了接口自动化最容易踩的 4 个坑，并逐条给出处理：

1. **没有超时** → 后端一卡，CI 挂到 job 超时才发现。默认强制 (3s, 10s)。
2. **连接不复用** → 每条用例新建 TCP + TLS 握手，规模一上来就慢且不稳。
   统一用 `requests.Session`。
3. **无脑重试** → POST 重试会产生重复数据。默认只重试幂等的 GET/HEAD，
   且只针对连接错误和 5xx/429。
4. **token 过期** → 长跑用例集中途开始 401。提供 `on_unauthorized` 钩子，
   触发一次重登录并重放请求（只重放一次，防止死循环）。
"""

from __future__ import annotations

import json
import time
from typing import Any, Callable, Iterable, Mapping

import requests

from .logger import get_logger
from .settings import SETTINGS, Settings
from .trace import RECORDER, Exchange

logger = get_logger("http")

_IDEMPOTENT = frozenset({"GET", "HEAD", "OPTIONS"})
_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


class TransportError(RuntimeError):
    """网络层失败（连不上、超时），区别于业务层失败。"""


class ApiResponse:
    """对 `requests.Response` 的薄包装，让用例读起来像业务语言。"""

    __slots__ = ("exchange", "_json", "_json_parsed")

    def __init__(self, exchange: Exchange) -> None:
        self.exchange = exchange
        self._json: Any = None
        self._json_parsed = False

    # ---- 传输层 ----
    @property
    def status_code(self) -> int:
        return self.exchange.status_code

    @property
    def text(self) -> str:
        return self.exchange.response_text

    @property
    def elapsed_ms(self) -> float:
        return self.exchange.elapsed_ms

    @property
    def url(self) -> str:
        return self.exchange.url

    @property
    def content_type(self) -> str:
        return self.exchange.response_headers.get("Content-Type", "")

    # ---- 业务层（RuoYi 的 AjaxResult 约定）----
    @property
    def json(self) -> Any:
        if not self._json_parsed:
            self._json_parsed = True
            try:
                self._json = json.loads(self.exchange.response_text)
            except (json.JSONDecodeError, TypeError):
                self._json = None
        return self._json

    @property
    def is_json(self) -> bool:
        return isinstance(self.json, (dict, list))

    def get(self, key: str, default: Any = None) -> Any:
        data = self.json
        if isinstance(data, dict):
            return data.get(key, default)
        return default

    @property
    def code(self) -> int | None:
        value = self.get("code")
        return value if isinstance(value, int) else None

    @property
    def msg(self) -> str:
        value = self.get("msg")
        return value if isinstance(value, str) else ""

    @property
    def data(self) -> Any:
        return self.get("data")

    @property
    def rows(self) -> list[dict[str, Any]]:
        value = self.get("rows")
        return value if isinstance(value, list) else []

    @property
    def total(self) -> int | None:
        value = self.get("total")
        return value if isinstance(value, int) else None

    @property
    def ok(self) -> bool:
        return self.code == 200

    # ---- 诊断 ----
    def summary(self, limit: int = 600) -> str:
        body = self.text
        if len(body) > limit:
            body = f"{body[:limit]}..."
        return (
            f"{self.exchange.method} {self.exchange.short_url} -> "
            f"HTTP {self.status_code} / code={self.code} / {self.elapsed_ms:.0f}ms\n"
            f"msg={self.msg!r}\nbody={body}"
        )

    def __repr__(self) -> str:  # pragma: no cover - 仅调试用
        return f"<ApiResponse {self.exchange.method} {self.exchange.short_url} code={self.code}>"


class HttpClient:
    """所有 API 对象的底座。不含任何业务语义。"""

    def __init__(
        self,
        base_url: str | None = None,
        *,
        settings: Settings | None = None,
        default_headers: Mapping[str, str] | None = None,
        session: requests.Session | None = None,
    ) -> None:
        self.settings = settings or SETTINGS
        self.base_url = (base_url or self.settings.base_url).rstrip("/")
        self.session = session or requests.Session()
        self._token: str | None = None
        self.on_unauthorized: Callable[[], None] | None = None
        self._reauth_guard = False

        self.session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "User-Agent": "ruoyi-api-autotest/2.0 (+pytest)",
            }
        )
        if default_headers:
            self.session.headers.update(default_headers)

    # ---- 鉴权 ----
    def set_token(self, token: str | None) -> None:
        self._token = token
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            self.session.headers.pop("Authorization", None)

    @property
    def token(self) -> str | None:
        return self._token

    def close(self) -> None:
        self.session.close()

    # ---- 请求 ----
    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
        json_body: Any = None,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
        files: Any = None,
        retry: int | None = None,
        timeout: tuple[float, float] | None = None,
        allow_reauth: bool = True,
    ) -> ApiResponse:
        method = method.upper()
        url = path if path.startswith(("http://", "https://")) else f"{self.base_url}{path}"
        budget = self._retry_budget(method, retry)
        attempt = 0

        while True:
            attempt += 1
            response = self._send(
                method, url, params, json_body, data, headers, files, timeout
            )

            if (
                allow_reauth
                and response.status_code == 401
                and self.on_unauthorized is not None
                and not self._reauth_guard
            ):
                logger.warning("收到 401，尝试重新登录后重放一次请求：%s %s", method, path)
                self._reauth_guard = True
                try:
                    self.on_unauthorized()
                finally:
                    self._reauth_guard = False
                attempt -= 1  # 重认证不计入重试预算
                continue

            if attempt <= budget and self._should_retry(method, response):
                delay = min(0.2 * (2 ** (attempt - 1)), 2.0)
                logger.info(
                    "第 %d 次重试 %s %s（HTTP %s），%.1fs 后继续",
                    attempt,
                    method,
                    path,
                    response.status_code,
                    delay,
                )
                time.sleep(delay)
                continue

            return response

    def get(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("PUT", path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("DELETE", path, **kwargs)

    # ---- 内部 ----
    def _retry_budget(self, method: str, retry: int | None) -> int:
        if retry is not None:
            return max(retry, 0)
        return self.settings.retries if method in _IDEMPOTENT else 0

    @staticmethod
    def _should_retry(method: str, response: ApiResponse) -> bool:
        if method not in _IDEMPOTENT:
            return False
        return response.status_code in _RETRYABLE_STATUS

    def _send(
        self,
        method: str,
        url: str,
        params: Any,
        json_body: Any,
        data: Any,
        headers: Mapping[str, str] | None,
        files: Any,
        timeout: tuple[float, float] | None,
    ) -> ApiResponse:
        started = time.perf_counter()
        try:
            raw = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                data=data,
                headers=dict(headers) if headers else None,
                files=files,
                timeout=timeout or self.settings.timeout,
            )
        except requests.RequestException as exc:
            elapsed = (time.perf_counter() - started) * 1000
            logger.error("请求失败 %s %s: %s", method, url, exc)
            raise TransportError(f"{method} {url} 失败: {exc}") from exc

        elapsed = (time.perf_counter() - started) * 1000
        request_body = json_body if json_body is not None else data
        exchange = Exchange(
            method=method,
            url=str(raw.url),
            request_headers={k: v for k, v in raw.request.headers.items()},
            request_body=request_body,
            status_code=raw.status_code,
            response_text=raw.text,
            elapsed_ms=elapsed,
            response_headers={k: v for k, v in raw.headers.items()},
        )
        RECORDER.record(exchange)
        logger.debug(
            "HTTP %s %s -> %s (%.0fms)\n  request=%s\n  response=%s",
            method,
            url,
            raw.status_code,
            elapsed,
            _dump(request_body),
            _dump(raw.text),
        )
        return ApiResponse(exchange)


def _dump(payload: Any, limit: int = 1500) -> str:
    if payload is None:
        return "<empty>"
    if isinstance(payload, (dict, list)):
        text = json.dumps(payload, ensure_ascii=False)
    else:
        text = str(payload)
    return text if len(text) <= limit else f"{text[:limit]}..."
