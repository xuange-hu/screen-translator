"""连续监控模式的纯逻辑工具（不依赖 Qt，便于单测）。"""

from __future__ import annotations

import hashlib
from typing import Iterable

from app.models import TextRegion


def region_signature(capture, regions: Iterable[TextRegion]) -> str:
    """内容指纹：同一批 (坐标, 原文, 译文) 算同一哈希。

    监控模式下内容没变就跳过覆盖层重绘，避免整屏闪烁。
    """
    items = []
    for region in regions:
        items.append(
            (
                region.x,
                region.y,
                region.width,
                region.height,
                region.text,
                region.translated_text,
            )
        )
    digest = hashlib.sha1(repr(items).encode("utf-8")).hexdigest()
    return digest


def known_translations(regions: Iterable[TextRegion]) -> dict[str, str]:
    """把本轮的 (原文 -> 译文) 收成字典，供下一轮预热翻译缓存。"""
    return {
        region.text: region.translated_text
        for region in regions
        if region.text and region.translated_text and region.translated_text.strip()
    }
