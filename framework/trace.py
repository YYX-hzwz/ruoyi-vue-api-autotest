"""请求/响应追踪。

为什么需要它
------------
用例失败时最贵的成本不是"修"，而是"定位"。默认的 pytest 报告只有一行
`AssertionError: 期望 code=200，实际 403`，看不到请求体、响应体、请求头，
排查等于盲猜。

这个模块只做一件事：把**每条用例**期间发生的所有 HTTP 交互收集起来，
由 conftest 在用例结束时挂到 pytest-html 报告里（request/response/cURL
三件套），失败时可直接复制 cURL 找后端复现。

实现上刻意保持极简：模块级 list + 用例开始/结束的清空语义。pytest 单进程
单线程按用例串行执行，因此不需要锁；pytest-xdist 下每个 worker 是独立
进程，天然隔离。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


def _truncate(text: str, limit: int = 8000) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n...（已截断，原始长度 {len(text)} 字符）"


@dataclass(slots=True)
class Exchange:
    """一次完整的 HTTP 往返。"""

    method: str
    url: str
    request_headers: dict[str, str]
    request_body: Any
    status_code: int
    response_text: str
    elapsed_ms: float
    response_headers: dict[str, str] = field(default_factory=dict)
    attempt: int = 1

    @property
    def short_url(self) -> str:
        """去掉 host，报告里更易读。"""
        marker = "://"
        if marker in self.url:
            rest = self.url.split(marker, 1)[1]
            slash = rest.find("/")
            return rest[slash:] if slash >= 0 else "/"
        return self.url

    def as_dict(self) -> dict[str, Any]:
        body = self.request_body
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False)
        return {
            "attempt": self.attempt,
            "method": self.method,
            "url": self.short_url,
            "status": self.status_code,
            "elapsed_ms": round(self.elapsed_ms, 1),
            "request": body,
            "response": self.response_text,
        }

    def as_curl(self) -> str:
        parts = [f"curl -i -X {self.method}", f"'{self.url}'"]
        for key, value in self.request_headers.items():
            if key.lower() == "authorization":
                value = "Bearer $TOKEN"
            parts.append(f"-H '{key}: {value}'")
        body = self.request_body
        if body is not None:
            if isinstance(body, (dict, list)):
                body = json.dumps(body, ensure_ascii=False)
            parts.append(f"--data-raw '{body}'")
        return " \\\n  ".join(parts)


@dataclass(slots=True)
class _Recorder:
    case_id: str = ""
    exchanges: list[Exchange] = field(default_factory=list)

    def start(self, case_id: str) -> None:
        self.case_id = case_id
        self.exchanges.clear()

    def record(self, exchange: Exchange) -> None:
        self.exchanges.append(exchange)

    def drain(self) -> list[Exchange]:
        items = list(self.exchanges)
        self.exchanges.clear()
        return items


RECORDER = _Recorder()
