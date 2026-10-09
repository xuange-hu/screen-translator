"""翻译管线协调：启动 worker、接收状态/错误/结果、收尾与回滚。"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt

from app.logger import get_logger
from app.models import CaptureInfo, TextRegion
from ui.motion import STATUS_HOLD
from workers.translation_worker import PipelineTask

log = get_logger("application")


class PipelineMixin:
    """翻译管线协调：启动 worker、接收状态/错误/结果、收尾与回滚。"""

    def _start_pipeline(self, capture: CaptureInfo) -> None:
        if not self._cancel_worker():
            self._abort_capture(
                "上一次翻译仍在结束，请稍后重试",
                failed=True,
                error_title="任务仍在运行",
                error_message="旧任务尚未安全结束，没有启动新的翻译。",
            )
            return
        try:
            config_snapshot = copy.copy(self.config)
            config_snapshot.data = copy.deepcopy(self.config.data)
            self.worker = PipelineTask(
                capture=capture,
                ocr_engine=self.ocr_engine,
                translator=self.translator,
                config=config_snapshot,
            )
            self.worker.status.connect(self._on_worker_status)
            self.worker.error.connect(self._on_worker_error)
            self.worker.result.connect(self.on_pipeline_result)
            self.worker.finished.connect(self._on_worker_finished)
            self.worker.start()
        except Exception as exc:
            log.exception("启动翻译任务失败")
            self._abort_capture(
                "无法启动翻译任务",
                failed=True,
                error_title="处理失败",
                error_message=str(exc),
            )

    def _on_worker_status(self, text: str) -> None:
        signal_sender = self.sender()
        if (
            self._shutting_down
            or (self._capture_session is None and not self._monitor_active)
            or (signal_sender is not None and signal_sender is not self.worker)
        ):
            return
        self.set_status(text)
        if not self._monitor_active:
            self.floating_status.set_text(text)

    def _on_worker_error(self, message: str) -> None:
        signal_sender = self.sender()
        if (
            self._shutting_down
            or (self._capture_session is None and not self._monitor_active)
            or (signal_sender is not None and signal_sender is not self.worker)
        ):
            return
        if self._monitor_active:
            # 画面里没有文字是常态（视频/空白），不算错误，照常继续轮询
            if message.startswith("没有识别到文字"):
                self._monitor_no_text = True
                self.set_status("监控中：当前画面没有可翻译的文字")
            else:
                self._pipeline_error = message
                self.set_status(f"监控出错：{message}")
            return
        self._pipeline_error = message
        self.set_status(f"处理失败：{message}")

    def _on_worker_finished(self) -> None:
        signal_sender = self.sender()
        if signal_sender is not None and signal_sender is not self.worker:
            return
        finished_worker = self.worker
        if finished_worker is None:
            return
        self.worker = None
        finished_worker.deleteLater()
        if self._shutting_down:
            return
        if self._monitor_active:
            if self._pipeline_succeeded or self._monitor_no_text:
                self._monitor_errors = 0
            else:
                self._monitor_errors += 1
                if self._monitor_errors >= int(
                    self.config.get("monitor.max_consecutive_errors", 3)
                ):
                    self.stop_monitor(reason="连续翻译失败，已停止实时监控")
                    return
            self._monitor_no_text = False
            self._monitor_schedule_next()
            return
        if self._pipeline_succeeded:
            session = self._capture_session
            self._capture_session = None
            if self.window is not None and session is not None:
                self.window.finish_capture(session.mode)
            self._set_busy(False)
            self.floating_status.hide_fade(delay_ms=STATUS_HOLD)
            return
        message = self._pipeline_error or "处理已取消"
        show_dialog = bool(self._pipeline_error)
        self._abort_capture(
            message,
            failed=show_dialog,
            error_title="处理失败" if show_dialog else "",
            error_message=message if show_dialog else "",
        )

    def _cancel_worker(self) -> bool:
        if self.worker is not None and self.worker.isRunning():
            self.worker.cancel()
            if not self.worker.wait(1000):
                return False
        if self.worker is not None:
            self.worker.deleteLater()
        self.worker = None
        return True

    def on_pipeline_result(self, payload: dict) -> None:
        signal_sender = self.sender()
        if (
            self._shutting_down
            or self._capture_session is None
            or (signal_sender is not None and signal_sender is not self.worker)
        ):
            return
        capture: CaptureInfo = payload["capture"]
        regions: list[TextRegion] = payload["regions"]
        recognized_count = int(payload.get("recognized_count", len(regions)))
        translated_count = int(
            payload.get("translated_count", max(0, len(regions)))
        )
        failed_count = int(payload.get("failed_count", 0))
        if self.overlay_manager is None:
            return
        if not regions:
            self._pipeline_error = "没有识别到可翻译的文字"
            return
        # 监控模式下，内容没变就保留当前覆盖层不重绘，避免整屏闪烁
        if self._monitor_active:
            from app.monitor_utils import known_translations, region_signature

            signature = region_signature(capture, regions)
            self._monitor_known = known_translations(regions)
            if signature == self._monitor_signature:
                self._pipeline_succeeded = True
                return
            self._monitor_signature = signature
        # Preserve the previous translation until a new result actually exists;
        # that lets cancellation/OCR errors restore it without stale ghost windows.
        # 监控模式不整屏清屏（避免闪烁），只更新变化的文本块。
        if not self._monitor_active:
            self.overlay_manager.clear_all()
        overlay_visible = self.overlay_manager.show_regions(
            capture, regions, animate_new_only=self._monitor_active
        )
        self._sync_overlay_state(overlay_visible)
        if self._monitor_active and self._monitor_region_selector is not None:
            self._monitor_region_selector.raise_()
        self._pipeline_succeeded = True
        if failed_count:
            self.set_status(
                f"识别 {recognized_count} 个文本块，已翻译 {translated_count} 个，"
                f"{failed_count} 个保留原文"
            )
        else:
            self.set_status(
                f"翻译完成：识别 {recognized_count} 个文本块，"
                f"已翻译 {translated_count} 个"
            )
        self.floating_status.set_text("翻译完成")
        self._save_history(capture, regions)
        original = "\n".join(str(getattr(r, "text", "") or "") for r in regions)
        translated = "\n".join(str(getattr(r, "translated_text", "") or "") for r in regions)
        self._last_original_text = original
        self._last_translated_text = translated
