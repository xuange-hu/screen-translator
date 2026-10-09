"""首次启动的欢迎引导：三步上手，降低新用户的使用门槛。

只在 ``general.first_run_done`` 为 False 时由控制器弹出一次；用户点“开始使用”
后由调用方把该标志写入配置。对话框完全复用项目的主题调色板（见 ``ui/style``）。
"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


def _hkfmt(raw: str) -> str:
    """把 ``ctrl+shift+a`` 之类的配置值美化为 ``Ctrl+Shift+A`` 用于展示。"""
    if not raw:
        return ""
    return "+".join(part.capitalize() for part in raw.split("+"))


class WelcomeDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        hotkeys: dict,
        on_finish: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._on_finish = on_finish
        self.setWindowTitle("欢迎使用 屏幕翻译")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self._hotkeys = hotkeys
        self._build_ui()
        self._page = 0
        self._show_page(0)

    # ------------------------------------------------------------------ ui
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("WelcomeHeader")
        hb = QVBoxLayout(header)
        hb.setContentsMargins(36, 28, 36, 18)
        hb.setSpacing(8)
        title = QLabel("欢迎使用 屏幕翻译")
        title.setObjectName("WelcomeTitle")
        sub = QLabel("三步上手，把屏幕上任何看不懂的文字，一键变成你能读懂的语言。")
        sub.setObjectName("WelcomeSubtitle")
        hb.addWidget(title)
        hb.addWidget(sub)
        root.addWidget(header)

        self._stack = QStackedWidget()
        self._stack.setObjectName("WelcomeStack")
        self._stack.addWidget(self._page_capture())
        self._stack.addWidget(self._page_language())
        self._stack.addWidget(self._page_tray())
        root.addWidget(self._stack, 1)

        footer = QWidget()
        footer.setObjectName("WelcomeFooter")
        fb = QHBoxLayout(footer)
        fb.setContentsMargins(36, 16, 36, 26)
        fb.setSpacing(10)
        dots = QWidget()
        dl = QHBoxLayout(dots)
        dl.setSpacing(8)
        self._dots = []
        for _ in range(3):
            d = QWidget()
            d.setFixedSize(8, 8)
            d.setObjectName("WelcomeDot")
            dl.addWidget(d)
            self._dots.append(d)
        fb.addWidget(dots)
        fb.addStretch(1)
        self.btn_back = QPushButton("上一步")
        self.btn_back.setObjectName("DialogCancelButton")
        self.btn_back.clicked.connect(self._back)
        self.btn_next = QPushButton("下一步")
        self.btn_next.setObjectName("PrimaryButton")
        self.btn_next.clicked.connect(self._next)
        fb.addWidget(self.btn_back)
        fb.addWidget(self.btn_next)
        root.addWidget(footer)

    def _mode_row(self, glyph: str, title: str, hotkey: str, desc: str) -> QWidget:
        row = QWidget()
        rb = QHBoxLayout(row)
        rb.setContentsMargins(2, 10, 2, 10)
        rb.setSpacing(14)
        badge = QLabel(glyph)
        badge.setObjectName("WelcomeBadge")
        badge.setFixedSize(42, 42)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rb.addWidget(badge)
        text = QVBoxLayout()
        text.setSpacing(4)
        head = QHBoxLayout()
        head.setSpacing(10)
        t = QLabel(title)
        t.setObjectName("WelcomeRowTitle")
        chip = QLabel(_hkfmt(hotkey))
        chip.setObjectName("HotkeyChip")
        head.addWidget(t)
        head.addWidget(chip)
        head.addStretch(1)
        d = QLabel(desc)
        d.setObjectName("WelcomeRowDesc")
        d.setWordWrap(True)
        text.addLayout(head)
        text.addWidget(d)
        rb.addLayout(text, 1)
        return row

    def _page_capture(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 12, 36, 8)
        v.setSpacing(10)
        intro = QLabel("先选一种截图方式，框好范围后即开始识别与翻译：")
        intro.setObjectName("WelcomeBody")
        intro.setWordWrap(True)
        v.addWidget(intro)
        v.addWidget(
            self._mode_row(
                "▦", "框选翻译", self._hotkeys.get("capture_region", ""),
                "拖拽鼠标圈出任意屏幕区域，适合零散段落。",
            )
        )
        v.addWidget(
            self._mode_row(
                "▣", "全屏翻译", self._hotkeys.get("capture_fullscreen", ""),
                "一次翻译整个屏幕，适合网页或长文档。",
            )
        )
        v.addWidget(
            self._mode_row(
                "▢", "当前窗口", self._hotkeys.get("capture_window", ""),
                "自动锁定最前面的应用窗口，无需手动框选。",
            )
        )
        v.addStretch(1)
        return page

    def _page_language(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 12, 36, 8)
        v.setSpacing(12)
        body = QLabel(
            "在主界面顶部选好<strong>源语言</strong>与<strong>目标语言</strong>，"
            "点任意截图方式即可翻译。\n\n"
            "默认使用内置词典翻译，<strong>开箱即用、无需任何配置</strong>；"
            "想要更地道的在线翻译，可在「设置 → 翻译」填入对应服务的 API Key，"
            "程序会自动切换到该服务。"
        )
        body.setObjectName("WelcomeBody")
        body.setWordWrap(True)
        v.addWidget(body, 1)
        return page

    def _page_tray(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(36, 12, 36, 8)
        v.setSpacing(12)
        body = QLabel(
            "翻译时主窗口会最小化到系统托盘，译文直接覆盖在屏幕上原文的位置。\n\n"
            "关闭主窗口不会退出程序——单击托盘图标即可随时唤回；"
            "按 <strong>F1</strong> 可随时查看本帮助与全部快捷键。"
        )
        body.setObjectName("WelcomeBody")
        body.setWordWrap(True)
        v.addWidget(body, 1)
        return page

    # ------------------------------------------------------------------ nav
    def _show_page(self, index: int) -> None:
        self._page = index
        self._stack.setCurrentIndex(index)
        for i, dot in enumerate(self._dots):
            dot.setProperty("active", i == index)
            dot.style().unpolish(dot)
            dot.style().polish(dot)
        self.btn_back.setEnabled(index > 0)
        self.btn_next.setText("开始使用" if index == self._stack.count() - 1 else "下一步")

    def _back(self) -> None:
        if self._page > 0:
            self._show_page(self._page - 1)

    def _next(self) -> None:
        if self._page < self._stack.count() - 1:
            self._show_page(self._page + 1)
        else:
            self.accept()

    def accept(self) -> None:
        if self._on_finish is not None:
            self._on_finish()
        super().accept()
