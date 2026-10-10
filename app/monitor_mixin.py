"""实时监控：按固定间隔截图、像素门控、调度翻译管线。"""

from __future__ import annotations

# 通过 app.application 命名空间解析 is_window_capturable，使测试对该符号的 monkeypatch 仍然生效。
from app import application as _application
from app.logger import get_logger

log = get_logger("application")


class MonitorMixin:
    """实时监控：按固定间隔截图、像素门控、调度翻译管线。"""

    def toggle_monitor(self) -> None:
        if self._monitor_active:
            self.stop_monitor()
        else:
            self.start_monitor()

    def start_monitor(self) -> None:
        if self._monitor_active:
            return
        if self._busy:
            self.set_status("正在处理上一次任务，稍后再开监控")
            return
        if self._last_capture is None:
            self.set_status("先截一张图，再开启实时监控")
            return
        if self._last_capture.mode == "window" and (
            not self._last_window_hwnd or not _application.is_window_capturable(self._last_window_hwnd)
        ):
            self.set_status("上次窗口已关闭，请重新框选/窗口截图后再监控")
            return
        if not bool(self.config.get("monitor.enabled", True)):
            self.set_status("实时监控已在设置中关闭")
            return
        self._monitor_request = {
            "mode": self._last_capture.mode,
            "bbox": tuple(self._last_capture.bbox),
            "hwnd": self._last_window_hwnd,
        }
        if self._last_capture.mode == "region":
            self._create_monitor_region_selector()
        self._monitor_active = True
        self._monitor_errors = 0
        self._monitor_no_text = False
        self._monitor_known = {}
        self._monitor_signature = ""
        self._monitor_frame_hash = ""
        self._set_busy(True)
        self.set_status("实时监控已开启，页面一动就会自动重译")
        if self.window is not None:
            self.window.set_monitor_checked(True)
        if self.tray is not None:
            self.tray.set_monitor_checked(True)
        self._monitor_cycle()

    def stop_monitor(self, reason: str = "") -> None:
        if not self._monitor_active:
            return
        self._monitor_active = False
        self._monitor_timer.stop()
        self._monitor_request = None
        self._monitor_known = {}
        self._monitor_signature = ""
        self._monitor_frame_hash = ""
        self._dispose_monitor_region()
        self._cancel_worker()
        self._set_busy(False)
        if self.window is not None:
            self.window.set_monitor_checked(False)
        if self.tray is not None:
            self.tray.set_monitor_checked(False)
        self.set_status(reason or "已停止实时监控")

    def _monitor_cycle(self) -> None:
        from utils.image_utils import frame_signature

        if not self._monitor_active or self._shutting_down:
            return
        request = self._monitor_request
        if request is None:
            return
        try:
            if request["mode"] == "fullscreen":
                capture = self.screenshot_service.capture_fullscreen()
            elif request["mode"] == "window":
                capture = self.screenshot_service.capture_window(request["hwnd"])
                self._last_window_hwnd = request["hwnd"]
            elif request["mode"] == "region":
                capture = self.screenshot_service.capture_bbox(request["bbox"])
                capture.mode = "region"
            else:
                return
        except Exception as exc:
            log.warning("监控截图失败：%s", exc)
            self._monitor_errors += 1
            if self._monitor_errors >= int(self.config.get("monitor.max_consecutive_errors", 3)):
                self.stop_monitor(reason="监控截图连续失败，已停止")
            else:
                self._monitor_schedule_next()
            return
        capture.mode = request["mode"]
        self._last_capture = capture
        # 像素差异门控：画面完全没变就跳过整轮 OCR + 翻译管线，覆盖层保持，省资源。
        frame_hash = frame_signature(capture.image)
        if self._monitor_frame_hash and self._monitor_frame_hash == frame_hash and self._monitor_signature:
            self._monitor_schedule_next()
            return
        self._monitor_frame_hash = frame_hash
        # 把上一轮译文写回缓存：内容没变过的文本块直接命中缓存，几乎瞬时返回，
        # 只有新出现/变化的文字才真正走网络——这就是“特别快”的来源。
        if (
            self.config.get("monitor.skip_unchanged", True)
            and self._monitor_known
            and self.cache is not None
        ):
            source = str(self.config.get("translation.source_language", "auto"))
            target = str(self.config.get("translation.target_language", "zh"))
            for text, translated in self._monitor_known.items():
                try:
                    self.cache.set(source, target, text, translated)
                except Exception:
                    pass
        self._pipeline_succeeded = False
        self._pipeline_error = ""
        self._start_pipeline(capture)

    def _monitor_schedule_next(self) -> None:
        if not self._monitor_active:
            return
        interval = int(self.config.get("monitor.interval_ms", 1200))
        self._monitor_timer.stop()
        self._monitor_timer.start(max(200, interval))

    def _create_monitor_region_selector(self) -> None:
        self._dispose_monitor_region()
        if self.monitor_map is None or self._monitor_request is None:
            return
        from ui.monitor_region import MonitorRegionSelector

        bbox = self._monitor_request["bbox"]
        accent = str(self.config.get("capture.select_border_color", "#2878E8"))
        selector = MonitorRegionSelector(self.monitor_map, bbox, accent)
        selector.region_changed.connect(self._on_monitor_region_changed)
        selector.region_committed.connect(self._on_monitor_region_committed)
        selector.stop_requested.connect(self.stop_monitor)
        self._monitor_region_selector = selector
        selector.show()
        selector.raise_()

    def _dispose_monitor_region(self) -> None:
        if self._monitor_region_selector is not None:
            try:
                self._monitor_region_selector.close()
            except Exception:
                pass
            self._monitor_region_selector = None

    def _on_monitor_region_changed(self, bbox) -> None:
        if self._monitor_request is not None:
            self._monitor_request["bbox"] = tuple(bbox)

    def _on_monitor_region_committed(self, bbox) -> None:
        if self._monitor_request is not None:
            self._monitor_request["bbox"] = tuple(bbox)
        # 拖拽结束尽快重刷一次；若当前正在跑轮询则不抢占，避免阻塞 UI 线程，
        # 下一轮周期自会采用新位置。
        if self._monitor_active and self.worker is None:
            self._monitor_timer.stop()
            self._monitor_timer.start(80)
