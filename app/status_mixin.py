"""跨模块共用的状态栏 / 错误弹窗 / 覆盖层显隐中枢。"""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app.logger import get_logger

log = get_logger("application")


class StatusMixin:
    """跨模块共用的状态栏 / 错误弹窗 / 覆盖层显隐中枢。"""

    def set_status(self, text: str) -> None:
        log.info("状态：%s", text)
        if self.window is not None:
            self.window.set_status(text)
        if self.tray is not None:
            self.tray.set_tooltip(text)

    def show_error(self, title: str, message: str) -> None:
        self.set_status(f"{title}：{message}")
        log.error("%s：%s", title, message)
        if self.window is not None:
            if not self.window.isVisible() or self.window.isMinimized():
                self.window.showNormal()
            self.window.raise_()
            self.window.activateWindow()
            QMessageBox.warning(self.window, title, message)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        if self.window is not None:
            self.window.set_busy(busy)
        if self.tray is not None:
            self.tray.set_busy(busy)
        if self._settings_page is not None:
            self._settings_page.setEnabled(not busy)
        if not busy and self._reopen_settings_after_close:
            from PySide6.QtCore import QTimer

            QTimer.singleShot(0, self._try_reopen_settings)

    def toggle_overlay(self) -> None:
        if self.overlay_manager is None or self._busy:
            return
        visible = not self._overlay_visible
        if visible:
            self.overlay_manager.show_all()
        else:
            self.overlay_manager.hide_all(animate=True)
        self._sync_overlay_state(visible)

    def _sync_overlay_state(self, visible: bool) -> None:
        self._overlay_visible = bool(visible)
        if self.tray is not None:
            self.tray.set_overlay_checked(self._overlay_visible)
        if self.window is not None:
            self.window.set_overlay_checked(self._overlay_visible)

    def set_edit_mode(self, enabled: bool) -> None:
        if self.overlay_manager is None or self._busy:
            return
        self.overlay_manager.set_edit_mode(enabled)
        if self.window is not None:
            self.window.set_edit_mode_checked(enabled)
