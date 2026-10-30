"""验证码获取。

原项目为了登录，直接注释掉了后端的 `SysLoginService.validateCaptcha`——
被测代码被改了，测试结论就不可迁移到线上，也无法在 CI 复现。

这里的做法一行业务代码都不碰，按优先级自动选择取码方式：

1. **固定码**：`AUTOTEST_CAPTCHA_CODE=1111`。测试环境常把验证码固定，
   这是成本最低、最稳定的方式，且不依赖任何内部结构。
2. **桩调试接口**：`AUTOTEST_TARGET=stub` 时桩会暴露 `/__stub/captcha/{uuid}`，
   让框架能在离线环境跑通"真实取码"链路。
3. **直连 Redis**：真实 RuoYi 把答案存在 `captcha_codes:{uuid}`。
   这是"不碰业务代码"的正解——需要 `redis` 客户端和 `AUTOTEST_REDIS_URL`。

三条路都不通时**明确报错**，而不是静默跳过或伪造验证码。
"""

from __future__ import annotations

import json

from framework.http import HttpClient, TransportError
from framework.settings import Settings

CAPTCHA_KEY_PREFIX = "captcha_codes:"


class CaptchaError(RuntimeError):
    """无法取得验证码，属于环境配置问题，不是用例失败。"""


def fetch_uuid(http: HttpClient) -> tuple[bool, str]:
    """调用 /captchaImage，返回 (是否开启验证码, uuid)。"""
    try:
        response = http.get("/captchaImage")
    except TransportError as exc:
        raise CaptchaError(f"无法访问 /captchaImage：{exc}") from exc

    payload = response.json
    if not isinstance(payload, dict) or payload.get("code") != 200:
        raise CaptchaError(
            "调用 /captchaImage 失败，无法判断验证码开关。\n"
            f"HTTP {response.status_code} body={response.text[:300]}"
        )
    return bool(payload.get("captchaEnabled")), str(payload.get("uuid") or "")


def _from_redis(settings: Settings, uuid: str) -> str:
    try:
        import redis  # 可选依赖
    except ImportError as exc:  # pragma: no cover - 取决于环境
        raise CaptchaError(
            "需要用 Redis 取验证码，但未安装 redis 客户端。\n"
            "  pip install redis\n"
            "或改用固定验证码：AUTOTEST_CAPTCHA_CODE=1111"
        ) from exc

    client = redis.Redis.from_url(settings.redis_url, socket_timeout=3)
    raw = client.get(f"{CAPTCHA_KEY_PREFIX}{uuid}")
    if raw is None:
        raise CaptchaError(f"Redis 中不存在验证码键 {CAPTCHA_KEY_PREFIX}{uuid}（可能已过期）")
    text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    # RuoYi 用 FastJson2 序列化，字符串会带引号
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = text
    return str(decoded)


def _from_stub(http: HttpClient, uuid: str) -> str:
    response = http.get(f"/__stub/captcha/{uuid}")
    payload = response.json
    if isinstance(payload, dict) and payload.get("code") == 200:
        return str(payload.get("code_value") or payload.get("data") or "")
    raise CaptchaError(
        f"桩调试接口不可用（HTTP {response.status_code}），"
        "确认 AUTOTEST_TARGET=stub 且桩已启动"
    )


def resolve(http: HttpClient, settings: Settings) -> tuple[str, str]:
    """返回 (验证码, uuid)；未开启验证码时返回 ("", "")。"""
    if not settings.captcha_enabled:
        return "", ""

    enabled, uuid = fetch_uuid(http)
    if not enabled:
        return "", ""
    if not uuid:
        raise CaptchaError("/captchaImage 返回 captchaEnabled=true 但缺少 uuid")

    if settings.captcha_code:
        return settings.captcha_code, uuid

    if settings.is_stub:
        return _from_stub(http, uuid), uuid

    if settings.redis_url:
        return _from_redis(settings, uuid), uuid

    raise CaptchaError(
        "后端开启了验证码，但框架没有取码途径。三选一：\n"
        "  1) AUTOTEST_CAPTCHA_CODE=1111（测试环境固定码，推荐）\n"
        "  2) AUTOTEST_REDIS_URL=redis://host:6379/0（直连 Redis 读真实验证码）\n"
        "  3) AUTOTEST_CAPTCHA_ENABLED=false（确认测试环境确实关了验证码）"
    )
