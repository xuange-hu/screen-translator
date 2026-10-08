"""把第三方翻译服务的 HTTP 响应统一转换为 TranslationError。

消除 openai / deepl / google 等适配器里重复的「状态码 -> 错误」分支，
并统一 429 限流标记，便于基类做「限流即保留原文」的降级。
"""

from __future__ import annotations

from services.translation.base import TranslationError


def raise_for_status(response, service: str) -> None:
    """非 2xx 时抛出 TranslationError；429 标记为限流。

    ``response`` 需提供 ``status_code`` 与 ``json()``（requests 响应即可）。
    """
    code = int(response.status_code)
    if 200 <= code < 300:
        return
    if code == 429:
        raise TranslationError(f"{service} 翻译触发限流（429），请稍后重试", rate_limited=True)
    if code in (401, 403):
        raise TranslationError(f"{service} 返回 {code}：API Key 无效或未授权")
    if code >= 500:
        raise TranslationError(f"{service} 服务端错误（{code}）")
    raise TranslationError(f"{service} 返回错误 {code}")


__all__ = ["raise_for_status"]
