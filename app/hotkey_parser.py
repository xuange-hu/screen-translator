"""纯逻辑：快捷键字符串归一化与冲突检测。

独立成模块是为了不让 ``hotkeys.py`` 里的 PySide6 依赖污染单元测试——
本文件仅依赖标准库，可在无 GUI 环境（含 CI）直接 import 与断言。
"""

from __future__ import annotations

import re
from typing import Dict, List

# 修饰键别名 -> pynput 规范名
_MODIFIER_ALIASES = {
    "ctrl": "ctrl",
    "control": "ctrl",
    "shift": "shift",
    "alt": "alt",
    "meta": "cmd",
    "win": "cmd",
    "cmd": "cmd",
    "esc": "esc",
    "space": "space",
}


def normalize_hotkey(sequence: str) -> str:
    """把 'Ctrl+Shift+A' 统一成 pynput 语法：修饰键用 ``<ctrl>`` 形式。

    例：``"Ctrl+Shift+a"`` -> ``"<ctrl>+<shift>+a"``；
        ``"ctrl+alt+a, ctrl+alt+b"`` 取第一个组合 -> ``"<ctrl>+<alt>+a"``。
    """
    sequence = sequence.strip().split(",")[0].strip()
    parts_out: List[str] = []
    for raw in re.split(r"[\s+]+", sequence):
        key = raw.strip().lower().strip("<>")
        if not key:
            continue
        key = _MODIFIER_ALIASES.get(key, key)
        if len(key) == 1:
            parts_out.append(key)
        else:
            parts_out.append(f"<{key}>")
    return "+".join(parts_out)


def detect_hotkey_conflicts(hotkeys: Dict[str, str]) -> List[str]:
    """检测同一按键组合被绑定到多个动作。

    返回形如 ``["<ctrl>+<shift>+a（capture_region 与 capture_full）"]`` 的说明。
    """
    seen: Dict[str, str] = {}
    conflicts: List[str] = []
    for action, shortcut in hotkeys.items():
        combo = normalize_hotkey(shortcut)
        if not combo:
            continue
        if combo in seen and seen[combo] != action:
            conflicts.append(f"{combo}（{seen[combo]} 与 {action}）")
        else:
            seen[combo] = action
    return conflicts
