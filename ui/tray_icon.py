"""系统托盘：菜单 + 图标。"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from ui.appearance import AppearanceTokens, current_tokens


def _hkfmt(raw: str) -> str:
    """把 ``ctrl+shift+a`` 美化为 ``Ctrl+Shift+A`` 用于菜单展示。"""
    if not raw:
        return ""
    return "+".join(part.capitalize() for part in raw.split("+"))


def build_icon(tokens: AppearanceTokens | None = None) -> QIcon:
    tokens = tokens or current_tokens()
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(tokens.surface))
    painter.drawRoundedRect(3, 3, 58, 58, 14, 14)
    painter.setPen(QPen(QColor(tokens.border), 1.3))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(3, 3, 58, 58, 14, 14)
    painter.setPen(QPen(QColor(tokens.ink), 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for x, y, dx, dy in ((17, 26, 0, -7), (17, 19, 7, 0), (47, 26, 0, -7), (47, 19, -7, 0),
                         (17, 38, 0, 7), (17, 45, 7, 0), (47, 38, 0, 7), (47, 45, -7, 0)):
        painter.drawLine(x, y, x + dx, y + dy)
    painter.drawRoundedRect(25, 25, 14, 11, 3, 3)
    painter.drawLine(30, 36, 33, 39)
    painter.drawLine(29, 29, 35, 29)
    painter.drawLine(29, 32, 34, 32)
    painter.setPen(QPen(QColor(tokens.accent), 2.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    painter.drawLine(25, 44, 32, 44)
    painter.end()
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, controller, parent=None) -> None:
        super().__init__(build_icon(), parent)
        self.controller = controller
        self._busy = False
        self.setToolTip("屏幕截图翻译")

        menu = QMenu()
        self.act_region = QAction("框选翻译", menu)
        self.act_fullscreen = QAction("全屏翻译", menu)
        self.act_window = QAction("当前窗口翻译", menu)
        self._window_capture_available = True
        menu.addAction(self.act_region)
        menu.addAction(self.act_fullscreen)
        menu.addAction(self.act_window)
        menu.addSeparator()
        self.act_toggle = QAction("隐藏译文", menu)
        self.act_toggle.setCheckable(True)
        self.act_toggle.setChecked(True)
        self.act_edit = QAction("编辑模式", menu)
        self.act_edit.setCheckable(True)
        menu.addAction(self.act_toggle)
        menu.addAction(self.act_edit)
        self.act_refresh = QAction("刷新翻译", menu)
        menu.addAction(self.act_refresh)
        self.act_monitor = QAction("实时监控", menu)
        self.act_monitor.setCheckable(True)
        menu.addAction(self.act_monitor)
        self.act_copy_src = QAction("复制原文", menu)
        self.act_copy_tr = QAction("复制译文", menu)
        menu.addAction(self.act_copy_src)
        menu.addAction(self.act_copy_tr)
        menu.addSeparator()
        self.act_settings = QAction("打开设置", menu)
        self.act_about = QAction("关于", menu)
        self.act_quit = QAction("退出", menu)
        menu.addAction(self.act_settings)
        menu.addAction(self.act_about)
        menu.addAction(self.act_quit)
        self.setContextMenu(menu)

        self.act_region.triggered.connect(lambda: self.controller.start_region_capture())
        self.act_fullscreen.triggered.connect(lambda: self.controller.start_capture("fullscreen"))
        self.act_window.triggered.connect(lambda: self.controller.start_capture("window"))
        self.act_toggle.triggered.connect(self._on_toggle)
        self.act_edit.triggered.connect(self._on_edit)
        self.act_refresh.triggered.connect(self.controller.refresh)
        self.act_monitor.triggered.connect(self.controller.toggle_monitor)
        self.act_copy_src.triggered.connect(self.controller.copy_original)
        self.act_copy_tr.triggered.connect(self.controller.copy_translation)
        self.act_settings.triggered.connect(self.controller.open_settings)
        self.act_about.triggered.connect(
            getattr(self.controller, "show_about", lambda: None)
        )
        self.act_quit.triggered.connect(self.controller.shutdown)
        self.activated.connect(self._on_activated)

        hk: dict = {}
        try:
            hk = self.controller.config.hotkeys()
        except Exception:
            hk = {}
        self._hk = hk
        self.act_region.setText(f"框选翻译\t{_hkfmt(hk.get('capture_region', ''))}")
        self.act_fullscreen.setText(f"全屏翻译\t{_hkfmt(hk.get('capture_fullscreen', ''))}")
        self.act_window.setText(f"当前窗口翻译\t{_hkfmt(hk.get('capture_window', ''))}")
        self.act_refresh.setText(f"刷新翻译\t{_hkfmt(hk.get('refresh', ''))}")
        self.act_toggle.setText(f"隐藏译文\t{_hkfmt(hk.get('toggle_overlay', ''))}")
        self.act_monitor.setText(f"实时监控\t{_hkfmt(hk.get('monitor_toggle', ''))}")

    def refresh_appearance(self) -> None:
        self.setIcon(build_icon())

    def _on_toggle(self, _checked: bool) -> None:
        self.controller.toggle_overlay()

    def _on_edit(self, checked: bool) -> None:
        self.controller.set_edit_mode(checked)

    def _on_activated(self, reason) -> None:
        if self._busy:
            return
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.controller.window is not None:
                self.controller.window.showNormal()
                self.controller.window.raise_()
                self.controller.window.activateWindow()

    def set_overlay_checked(self, visible: bool) -> None:
        self.act_toggle.setChecked(visible)
        self.act_toggle.setText(
            f"{'隐藏译文' if visible else '显示译文'}\t{_hkfmt(self._hk.get('toggle_overlay', ''))}"
        )

    def set_monitor_checked(self, active: bool) -> None:
        self.act_monitor.setChecked(active)
        self.act_monitor.setText(
            f"{'停止监控' if active else '实时监控'}\t{_hkfmt(self._hk.get('monitor_toggle', ''))}"
        )

    def set_edit_mode_checked(self, enabled: bool) -> None:
        self.act_edit.setChecked(enabled)

    def set_tooltip(self, text: str) -> None:
        self.setToolTip(text)

    def set_busy(self, busy: bool) -> None:
        self._busy = bool(busy)
        for action in (
            self.act_region,
            self.act_fullscreen,
            self.act_refresh,
            self.act_settings,
            self.act_toggle,
            self.act_edit,
        ):
            action.setEnabled(not busy)
        self.act_window.setEnabled(not busy and self._window_capture_available)

    def set_window_capture_available(self, available: bool, reason: str = "") -> None:
        self._window_capture_available = bool(available)
        self.act_window.setEnabled(self._window_capture_available)
        self.act_window.setToolTip("" if available else (reason or "此平台暂不支持窗口捕获"))
