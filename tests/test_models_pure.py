"""app.models.TextRegion 纯逻辑单测（无 Qt 依赖）。

TextRegion 是数据模型，其几何属性与 (反)序列化此前没有独立单测，这里补上。
"""

from __future__ import annotations

from app.models import TextRegion


def test_geometry_properties():
    r = TextRegion(text="a", x=10, y=20, width=100, height=40)
    assert r.right == 110
    assert r.bottom == 60
    assert r.center == (60, 40)


def test_geometry_with_zero_size():
    r = TextRegion(text="a", x=0, y=0, width=0, height=0)
    assert r.right == 0
    assert r.bottom == 0
    assert r.center == (0, 0)


def test_with_translation_returns_copy():
    r = TextRegion(text="hi", x=1, y=2, width=3, height=4)
    t = r.with_translation("你好")
    assert t.translated_text == "你好"
    assert r.translated_text == ""              # 原对象不被修改
    assert t is not r


def test_to_dict_roundtrip():
    r = TextRegion(
        text="hi",
        x=1,
        y=2,
        width=3,
        height=4,
        source_line_height=12.0,
        source_line_count=2,
        confidence=0.9,
        screen_index=3,
    )
    d = r.to_dict()
    assert d["text"] == "hi"
    assert d["width"] == 3
    assert d["source_line_height"] == 12.0
    back = TextRegion.from_dict(d)
    assert back == r


def test_to_dict_includes_translated_text():
    r = TextRegion(text="hi", x=1, y=2, width=3, height=4, translated_text="你好")
    d = r.to_dict()
    assert d["translated_text"] == "你好"


def test_from_dict_defaults_and_clamps_line_count():
    # 缺失字段走默认值；source_line_count 至少 1（即便传 0）
    r = TextRegion.from_dict({"text": "hi", "source_line_count": 0})
    assert r.source_line_count == 1
    assert r.x == 0 and r.width == 0
    assert r.text == "hi"


def test_from_dict_coerces_types():
    r = TextRegion.from_dict(
        {
            "text": "hi",
            "x": "5",
            "width": "7",
            "source_line_height": "9.5",
            "confidence": "0.5",
        }
    )
    assert r.x == 5 and r.width == 7
    assert r.source_line_height == 9.5
    assert r.confidence == 0.5


def test_right_bottom_use_physical_pixels():
    # 多行合并框：height 为整框，属性仍按物理像素算
    r = TextRegion(text="a", x=0, y=0, width=50, height=25)
    assert (r.right, r.bottom) == (50, 25)
