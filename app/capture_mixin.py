"""截图捕获调度：区域/全屏/窗口框选、窗口高亮、捕获会话与回滚。"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt

# 通过 app.application 命名空间解析 is_window_capturable，使测试对该符号的 monkeypatch 仍然生效。
from app import application as _application
from app.capture_session import _CaptureSession
from app.logger import get_logger
from app.models import CaptureInfo
from services.window_capture_service import (
    WindowCaptureError,
    get_window_title,
    window_capture_available,
)
from ui.motion import CAPTURE_SETTLE, SELECTION_SETTLE
from ui.selection_overlay import SelectionOverlay
from ui.window_capture_highlight import WindowCaptureHighlight
from utils import dpi_utils

log = get_logger("application")


class CaptureMixin:
    """截图捕获调度：区域/全屏/窗口框选、窗口高亮、捕获会话与回滚。"""

    def start_region_capture(self) -> None:
        if self._busy or self.window is None or self.overlay_manager is None:
            return
        self._begin_capture_session("region", self._after_region_departure)

    def _after_region_departure(self) -> None:
        self._selection_timer.stop()
        self._selection_timer.start(CAPTURE_SETTLE)

    def _show_selection(self) -> None:
        if self._capture_session is None or self._capture_session.mode != "region":
            return
        try:
            screen = self.qt_app.primaryScreen()
            if screen is None:
                raise RuntimeError("没有检测到可用显示器")
            self._dispose_selection()
            self.selection = SelectionOverlay(
                screen.virtualGeometry(),
                mask_opacity=int(self.config.get("capture.select_mask_opacity", 84)),
                border_color=self._capture_accent(),
            )
            self.selection.selection_done.connect(self._on_selection_done)
            self.selection.cancelled.connect(self._on_selection_cancelled)
            self.selection.show()
            self.selection.raise_()
            self.selection.activateWindow()
            self.selection.setFocus()
        except Exception as exc:
            log.exception("显示框选层失败")
            self._abort_capture(
                "无法开始框选",
                failed=True,
                error_title="无法开始框选",
                error_message=str(exc),
            )

    def _on_selection_done(self, logical_bbox: object) -> None:
        self._dispose_selection()
        if not isinstance(logical_bbox, tuple) or len(logical_bbox) != 4:
            self._abort_capture(
                "框选坐标无效",
                failed=True,
                error_title="框选失败",
                error_message="收到的框选坐标格式无效，请重试。",
            )
            return
        parts = dpi_utils.logical_rect_to_physical_parts(logical_bbox, self.monitor_map)
        if not parts:
            self._abort_capture("框选区域太小，已取消")
            return
        if not dpi_utils.parts_form_rectangle(parts):
            self._abort_capture(
                "框选跨越了不同缩放比例的屏幕",
                failed=True,
                error_title="请在单个屏幕内框选",
                error_message="跨不同缩放比例的显示器会产生非矩形像素区域，请在一个屏幕内完成框选。",
            )
            return
        physical = dpi_utils.union_rects(parts)
        if physical[2] - physical[0] < 4 or physical[3] - physical[1] < 4:
            self._abort_capture("框选区域太小，已取消")
            return
        self._schedule_capture("region", bbox=physical, delay_ms=SELECTION_SETTLE)

    def _on_selection_cancelled(self) -> None:
        self._dispose_selection()
        self._abort_capture("已取消框选")

    def start_capture(self, mode: str) -> None:
        if self._busy or self.window is None or self.overlay_manager is None:
            return
        if mode not in {"fullscreen", "window"}:
            return
        if mode == "window":
            if not window_capture_available():
                self.window.play_capture_failure("window")
                self.set_status("当前平台暂不支持原生窗口捕获")
                return
            hwnd = self._resolve_window_target()
            if not hwnd:
                self.window.play_capture_failure("window")
                self.set_status("请先切换到要翻译的窗口，再使用当前窗口翻译")
                return
            self._begin_capture_session(
                "window",
                self._after_window_departure,
                target_hwnd=hwnd,
            )
            return
        self._begin_capture_session("fullscreen", self._after_fullscreen_departure)

    def _after_fullscreen_departure(self) -> None:
        self._schedule_capture("fullscreen", delay_ms=CAPTURE_SETTLE)

    def _after_window_departure(self) -> None:
        session = self._capture_session
        if session is None or session.mode != "window":
            return
        try:
            rect = _application.get_window_rect_physical(session.target_hwnd)
            intersecting = [
                monitor
                for monitor in self.monitor_map
                if dpi_utils.intersect(rect, monitor.physical) is not None
            ]
            # A single logical outline cannot faithfully cover a window split
            # across different per-monitor coordinate spaces. Skip the outline,
            # keep the target frozen, and proceed after the compositor settles.
            if len(intersecting) != 1:
                self.set_status("已锁定跨屏窗口，正在准备捕获…")
                self._schedule_capture(
                    "window",
                    target_hwnd=session.target_hwnd,
                    delay_ms=CAPTURE_SETTLE,
                )
                return
            center_x = (rect[0] + rect[2]) // 2
            center_y = (rect[1] + rect[3]) // 2
            monitor = intersecting[0]
            geo = dpi_utils.physical_rect_to_overlay_geometry(rect, monitor)
            self._highlight_window_rect = rect
            self._dispose_window_highlight()
            self.window_highlight = WindowCaptureHighlight(
                QRect(geo[0], geo[1], max(1, geo[2]), max(1, geo[3])),
                get_window_title(session.target_hwnd),
                accent_color=self._capture_accent(),
            )
            self.window_highlight.finished.connect(self._on_window_highlight_finished)
            self.window_highlight.show_and_confirm()
        except Exception as exc:
            log.exception("确认目标窗口失败")
            self._abort_capture(
                "目标窗口已经不可用",
                failed=True,
                error_title="窗口捕获失败",
                error_message=str(exc),
            )

    def _on_window_highlight_finished(self) -> None:
        session = self._capture_session
        hwnd = session.target_hwnd if session is not None else 0
        self._dispose_window_highlight()
        if not hwnd:
            self._abort_capture("目标窗口已经不可用", failed=True)
            return
        try:
            current_rect = _application.get_window_rect_physical(hwnd)
        except WindowCaptureError as exc:
            self._abort_capture(
                "目标窗口已经不可用",
                failed=True,
                error_title="窗口捕获失败",
                error_message=str(exc),
            )
            return
        if (
            self._highlight_window_rect is not None
            and current_rect != self._highlight_window_rect
            and self._window_highlight_retries < 1
        ):
            self._window_highlight_retries += 1
            self._after_window_departure()
            return
        self._schedule_capture(
            "window",
            target_hwnd=hwnd,
            delay_ms=SELECTION_SETTLE,
        )

    def _begin_capture_session(
        self,
        mode: str,
        continuation,
        *,
        target_hwnd: int = 0,
    ) -> bool:
        if self._busy or self.window is None or self.overlay_manager is None:
            return False
        self.window.settle_settings_transition_for_capture()
        try:
            self.refresh_monitor_map()
        except Exception as exc:
            log.exception("刷新显示器映射失败")
            self.show_error("无法开始截图", str(exc))
            return False
        self._capture_session = _CaptureSession(
            mode=mode,
            window_was_visible=self.window.isVisible(),
            window_was_minimized=self.window.isMinimized(),
            overlay_was_visible=self.overlay_manager.is_visible(),
            target_hwnd=target_hwnd,
        )
        self._pipeline_succeeded = False
        self._pipeline_error = ""
        self._highlight_window_rect = None
        self._window_highlight_retries = 0
        self._set_busy(True)
        self.floating_status.hide_immediate()
        self.overlay_manager.hide_all()
        self._sync_overlay_state(False)
        self.window.play_capture_departure(mode, continuation)
        return True

    def _schedule_capture(
        self,
        mode: str,
        *,
        bbox: tuple[int, int, int, int] | None = None,
        target_hwnd: int = 0,
        delay_ms: int = CAPTURE_SETTLE,
    ) -> None:
        if self._capture_session is None:
            return
        self._capture_timer.stop()
        self._pending_capture_mode = mode
        self._pending_capture_bbox = bbox
        self._pending_window_hwnd = target_hwnd
        if delay_ms <= 0:
            self._execute_pending_capture()
        else:
            self._capture_timer.start(delay_ms)

    def _execute_pending_capture(self) -> None:
        mode = self._pending_capture_mode
        bbox = self._pending_capture_bbox
        hwnd = self._pending_window_hwnd
        self._pending_capture_mode = ""
        self._pending_capture_bbox = None
        self._pending_window_hwnd = 0
        if self._capture_session is None:
            return
        # There must be no top-most UI alive when the actual pixels are read.
        self.floating_status.hide_immediate()
        try:
            if mode == "fullscreen":
                capture = self.screenshot_service.capture_fullscreen()
            elif mode == "window":
                if not hwnd:
                    raise WindowCaptureError("没有可用的目标窗口")
                capture = self.screenshot_service.capture_window(hwnd)
                self._last_window_hwnd = hwnd
            elif mode == "region" and bbox is not None:
                capture = self.screenshot_service.capture_bbox(bbox)
                capture.mode = "region"
            else:
                raise RuntimeError("截图请求缺少有效范围")
        except Exception as exc:
            log.exception("截图失败")
            self._abort_capture(
                "截图失败",
                failed=True,
                error_title="截图失败",
                error_message=str(exc),
            )
            return
        self._accept_capture(capture)

    def refresh(self) -> None:
        if self._last_capture is None:
            self.set_status("还没有截图，先截一张再说")
            return
        if self._busy:
            return
        mode = self._last_capture.mode
        if mode == "window":
            hwnd = self._last_window_hwnd
            if not hwnd or not _application.is_window_capturable(hwnd):
                if self.window is not None:
                    self.window.play_capture_failure("window")
                self.set_status("上次翻译的窗口已经关闭或最小化")
                return
            self._begin_capture_session(
                "window",
                lambda: self._schedule_capture(
                    "window", target_hwnd=hwnd, delay_ms=CAPTURE_SETTLE
                ),
                target_hwnd=hwnd,
            )
            return
        if mode == "fullscreen":
            self._begin_capture_session(
                "fullscreen",
                lambda: self._schedule_capture("fullscreen", delay_ms=CAPTURE_SETTLE),
            )
            return
        bbox = self._last_capture.bbox
        self._begin_capture_session(
            "region",
            lambda: self._schedule_capture(
                "region", bbox=bbox, delay_ms=CAPTURE_SETTLE
            ),
        )

    def run_capture_rect(
        self, bbox: tuple[int, int, int, int], mode: str, existing: CaptureInfo | None = None
    ) -> None:
        if self._busy:
            return
        if self.window is None or self.overlay_manager is None:
            return

        def continue_capture() -> None:
            if existing is not None:
                existing.mode = mode
                self._accept_capture(existing)
            else:
                self._schedule_capture(mode, bbox=bbox, delay_ms=CAPTURE_SETTLE)

        self._begin_capture_session(mode, continue_capture)

    def _accept_capture(self, capture: CaptureInfo) -> None:
        if self._capture_session is None:
            return
        self._last_capture = capture
        self.floating_status.show_fade("正在识别…", anchor=self._capture_anchor(capture.bbox))
        self._start_pipeline(capture)

    def _capture_anchor(self, bbox: tuple[int, int, int, int]) -> QPoint | None:
        if not self.monitor_map:
            return None
        px = (bbox[0] + bbox[2]) // 2
        py = (bbox[1] + bbox[3]) // 2
        monitor = dpi_utils.monitor_for_physical_point(px, py, self.monitor_map)
        local_x, local_y = dpi_utils.physical_to_local_logical(px, py, monitor)
        return QPoint(
            monitor.logical_origin[0] + local_x,
            monitor.logical_origin[1] + local_y,
        )

    def _dispose_selection(self) -> None:
        selection = self.selection
        self.selection = None
        if selection is not None:
            selection.dismiss()
            selection.deleteLater()

    def _dispose_window_highlight(self) -> None:
        highlight = self.window_highlight
        self.window_highlight = None
        if highlight is not None:
            highlight.dismiss()
            highlight.deleteLater()

    def _abort_capture(
        self,
        status: str,
        *,
        failed: bool = False,
        error_title: str = "",
        error_message: str = "",
    ) -> None:
        self._capture_timer.stop()
        self._selection_timer.stop()
        self._pending_capture_mode = ""
        self._pending_capture_bbox = None
        self._pending_window_hwnd = 0
        self._dispose_selection()
        self._dispose_window_highlight()
        self.floating_status.hide_immediate()

        session = self._capture_session
        self._capture_session = None
        if self.window is not None and session is not None:
            if session.window_was_visible:
                self.window.restore_after_capture(
                    session.mode,
                    was_minimized=session.window_was_minimized,
                    failed=failed,
                )
            elif failed:
                self.window.play_capture_failure(session.mode)
        self.set_status(status)
        if error_title and error_message:
            self.show_error(error_title, error_message)
        if self.overlay_manager is not None:
            if session is not None and session.overlay_was_visible:
                self.overlay_manager.show_all()
                self._sync_overlay_state(True)
            else:
                self.overlay_manager.hide_all()
                self._sync_overlay_state(False)
        self._set_busy(False)
