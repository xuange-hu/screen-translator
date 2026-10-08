"""连续监控模式纯逻辑测试（不依赖 Qt）。"""

from __future__ import annotations

from app.models import TextRegion
from app.monitor_utils import known_translations, region_signature


def _region(text: str, translated: str, x: int = 0) -> TextRegion:
    region = TextRegion(text=text, x=x, y=0, width=10, height=10)
    region.translated_text = translated
    return region


def test_signature_is_stable_for_same_content():
    regions = [_region("Hello", "你好"), _region("World", "世界", x=20)]
    first = region_signature(None, regions)
    assert first == region_signature(None, regions)


def test_signature_changes_when_text_or_translation_changes():
    base = [_region("Hello", "你好"), _region("World", "世界", x=20)]
    translated_changed = [_region("Hello", "您好"), _region("World", "世界", x=20)]
    layout_changed = [_region("Hello", "你好"), _region("World", "世界", x=40)]
    assert region_signature(None, base) != region_signature(None, translated_changed)
    assert region_signature(None, base) != region_signature(None, layout_changed)


def test_known_translations_maps_source_to_translation():
    regions = [_region("Hello", "你好"), _region("World", "世界", x=20)]
    assert known_translations(regions) == {"Hello": "你好", "World": "世界"}


def test_known_translations_skips_empty_translation():
    regions = [_region("Hello", "你好"), _region("World", "", x=20)]
    assert known_translations(regions) == {"Hello": "你好"}
