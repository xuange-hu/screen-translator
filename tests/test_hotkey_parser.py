"""screen-translator 纯逻辑单测：快捷键归一化与冲突检测。

这些模块不依赖 PySide6，可在无 GUI 的 CI / 沙箱中直接运行。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.hotkey_parser import detect_hotkey_conflicts, normalize_hotkey  # noqa: E402

NORMALIZE_CASES = [
    ("Ctrl+Shift+A", "<ctrl>+<shift>+a"),
    ("ctrl+shift+a", "<ctrl>+<shift>+a"),
    ("Control+Alt+Space", "<ctrl>+<alt>+<space>"),
    ("WIN+B", "<cmd>+b"),
    ("META+X", "<cmd>+x"),
    ("  ctrl + alt + z ", "<ctrl>+<alt>+z"),
    ("ctrl+alt+a, ctrl+alt+b", "<ctrl>+<alt>+a"),  # 取第一个组合
    ("esc", "<esc>"),
    ("a", "a"),  # 单字符键不包裹
]


def test_normalize_hotkey_cases():
    for raw, expected in NORMALIZE_CASES:
        assert normalize_hotkey(raw) == expected, raw


def test_normalize_hotkey_aliases():
    # 大小写与别名等价
    assert normalize_hotkey("CTRL") == normalize_hotkey("ctrl")
    assert normalize_hotkey("Control") == "<ctrl>"
    assert normalize_hotkey("Win") == "<cmd>"
    assert normalize_hotkey("Meta") == "<cmd>"


def test_no_conflict_when_distinct():
    hotkeys = {
        "capture_region": "ctrl+shift+a",
        "capture_full": "ctrl+shift+s",
        "translate": "ctrl+alt+t",
    }
    assert detect_hotkey_conflicts(hotkeys) == []


def test_detects_conflict_across_actions():
    hotkeys = {
        "capture_region": "ctrl+shift+a",
        "capture_full": "ctrl+shift+a",  # 与上面冲突
    }
    conflicts = detect_hotkey_conflicts(hotkeys)
    assert len(conflicts) == 1
    assert "<ctrl>+<shift>+a" in conflicts[0]
    assert "capture_region" in conflicts[0] and "capture_full" in conflicts[0]


def test_distinct_actions_share_combo_is_conflict():
    # 两个不同动作声明同一组合 -> 冲突（dict key 唯一，不会出现“同动作重复”）
    hotkeys = {"capture_region": "ctrl+shift+a", "capture_region_dup": "ctrl+shift+a"}
    conflicts = detect_hotkey_conflicts(hotkeys)
    assert len(conflicts) == 1
    assert "capture_region" in conflicts[0] and "capture_region_dup" in conflicts[0]


def test_empty_shortcut_ignored():
    hotkeys = {"a": "", "b": "ctrl+x"}
    conflicts = detect_hotkey_conflicts(hotkeys)
    assert conflicts == []
