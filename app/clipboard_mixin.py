"""复制识别文本 / 译文到剪贴板的辅助方法。"""

from __future__ import annotations


class ClipboardMixin:
    """复制识别文本 / 译文到剪贴板的辅助方法。"""

    def copy_original(self) -> None:
        self._copy_to_clipboard(self._last_original_text, "原文")

    def copy_translation(self) -> None:
        self._copy_to_clipboard(self._last_translated_text, "译文")

    def _copy_to_clipboard(self, text: str, label: str) -> None:
        from PySide6.QtWidgets import QApplication

        if not text:
            self.set_status(f"没有可复制的{label}")
            return
        QApplication.clipboard().setText(text)
        self.set_status(f"已复制{label}到剪贴板（{len(text)} 字）")
