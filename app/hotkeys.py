"""全局快捷键管理（pynput 实现，Qt 信号转发到主线程）。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, Signal

from app.hotkey_parser import detect_hotkey_conflicts, normalize_hotkey
from app.logger import get_logger

log = get_logger("hotkeys")


class HotkeyError(Exception):
    pass


class HotkeyManager(QObject):
    """注册全局快捷键，把触发事件转发到主线程信号。"""

    triggered = Signal(str)  # action 名称

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._listener = None
        self._registry: dict[str, str] = {}
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    def apply(self, hotkeys: dict[str, str]) -> None:
        """hotkeys: {action: shortcut}，如 {'capture_region': 'ctrl+shift+a'}。"""
        self.stop()
        self._registry = dict(hotkeys)

        # 冲突检测：同一组合绑定多个动作
        conflicts = detect_hotkey_conflicts(self._registry)
        if conflicts:
            raise HotkeyError("快捷键冲突：" + "；".join(conflicts))

        mapping: dict[str, Callable[[], None]] = {}
        for action, shortcut in self._registry.items():
            combo = normalize_hotkey(shortcut)
            if combo:
                mapping[combo] = (lambda act=action: self.triggered.emit(act))

        if not mapping:
            return

        try:
            from pynput import keyboard

            self._listener = keyboard.GlobalHotKeys(mapping)
            self._listener.daemon = True
            self._listener.start()
            log.info("已注册 %d 个全局快捷键", len(mapping))
        except Exception as exc:  # pragma: no cover - 平台相关
            self._listener = None
            raise HotkeyError(f"全局快捷键注册失败：{exc}") from exc

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
