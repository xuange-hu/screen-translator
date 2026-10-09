"""一次捕获会话的轻量快照。

单独成模块，避免 ``app.application`` 被 capture Mixin 循环导入。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _CaptureSession:
    mode: str
    window_was_visible: bool
    window_was_minimized: bool
    overlay_was_visible: bool
    target_hwnd: int = 0
