"""设置、外观、OCR/翻译器解析、快捷键与开机自启。"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QTimer

# 通过 app.application 命名空间解析 create_ocr_engine，使测试对该符号的 monkeypatch 仍然生效。
from app import application as _application
from app.hotkeys import HotkeyError, HotkeyManager
from app.logger import get_logger
from app.runtime import main_script, sys_executable
from services.ocr.base import OCRUnavailableError
from services.translation.base import Translator
from services.translation.factory import create_translator
from ui.appearance import resolve_tokens
from ui.settings_dialog import SettingsDialog
from ui.style import apply_style
from ui.tray_icon import build_icon

log = get_logger("application")


class SettingsMixin:
    """设置、外观、OCR/翻译器解析、快捷键与开机自启。"""

    def _capture_accent(self) -> str:
        """Resolve the capture accent from the versioned appearance settings."""
        return resolve_tokens(self.config.section("appearance")).accent

    def _refresh_appearance(self) -> None:
        tokens = apply_style(self.qt_app, self.config.section("appearance"))
        self.qt_app.setWindowIcon(build_icon(tokens))
        self.floating_status.refresh_appearance()
        if self.selection is not None:
            self.selection.set_accent(tokens.accent)
        if self.window_highlight is not None:
            self.window_highlight.set_accent(tokens.accent)
        if self.tray is not None:
            self.tray.refresh_appearance()
        if self.window is not None:
            self.window.refresh_appearance()
        if self._settings_page is not None:
            self._settings_page.refresh_appearance()

    def _on_system_color_scheme_changed(self, _scheme) -> None:
        if self.config.get("appearance.palette", "warm_paper") == "system":
            self._refresh_appearance()

    def open_settings(self) -> None:
        if self.window is None or self._busy:
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()
        if self._settings_page is not None:
            if self._settings_page.close_intent == 1:
                self._reopen_settings_after_close = True
                return
            if self._settings_page.exit_pending:
                self._settings_page.cancel_exit()
            self.window.show_settings_page(self._settings_page)
            return
        # A direct or queued open has now reached the only point where it can
        # succeed. Consume the request here, never when merely scheduling it.
        self._reopen_settings_after_close = False
        dialog = SettingsDialog(self.config, parent=self.window)
        dialog.setWindowFlags(Qt.WindowType.Widget)
        dialog.setMinimumSize(0, 0)
        self._settings_page = dialog
        dialog.accepted.connect(self._apply_settings)
        dialog.exit_requested.connect(
            lambda result, page=dialog: self._begin_settings_exit(page, result)
        )
        dialog.finished.connect(
            lambda result, page=dialog: self._close_settings_page(page, result)
        )
        dialog.install_update_requested.connect(self.install_update)
        self.window.show_settings_page(dialog)

    def _begin_settings_exit(self, page: SettingsDialog, result: int) -> None:
        if self._settings_page is not page:
            page.complete_exit(result)
            return
        if self.window is None:
            page.complete_exit(result)
            return
        self.window.begin_settings_exit(
            page,
            lambda current=page, value=result: current.complete_exit(value),
        )

    def _close_settings_page(self, page: SettingsDialog, _result: int = 0) -> None:
        if self._settings_page is page:
            self._settings_page = None
        if self.window is not None:
            self.window.remove_settings_page(page)
        if self._reopen_settings_after_close:
            QTimer.singleShot(0, self._try_reopen_settings)

    def _try_reopen_settings(self) -> None:
        """Honor a queued reopen only when capture and teardown are both idle."""
        if (
            not self._reopen_settings_after_close
            or self._busy
            or self.window is None
            or self._settings_page is not None
        ):
            return
        self.open_settings()

    def _apply_settings(self) -> None:
        self._refresh_appearance()
        self.refresh_monitor_map()
        if self.cache is not None:
            self.cache.set_ttl(
                self.config.get("translation.cache_ttl_days", 30),
                self.config.get("translation.cache_max_entries", 2000),
            )
        self.ocr_engine = self._create_configured_ocr_engine()
        resolved_service = self._resolve_translator_service()
        if resolved_service != self.config.get("translation.service", "mock"):
            self.config.set("translation.service", resolved_service)
            self.config.save()
            self.set_status(f"检测到 API Key，已自动切换到 {resolved_service} 翻译服务")
        self.translator = create_translator(
            self.config.get("translation.service", "mock"),
            self.config.section("translation"),
            cache=self.cache,
            api_key_resolver=self.config.api_key,
        )
        if self.overlay_manager is not None:
            self.overlay_manager.apply_style()
        try:
            self._apply_hotkeys()
        except HotkeyError as exc:
            self.show_error("快捷键", str(exc))
        self._apply_autostart()
        if self.window is not None:
            self.window.reload_values()
        self.set_status("设置已保存")

    def apply_runtime_selection(
        self,
        ocr_engine: str | None = None,
        service: str | None = None,
        source: str | None = None,
        target: str | None = None,
    ) -> None:
        """主窗口下拉框变更时立即生效并保存。"""
        if ocr_engine:
            self.config.set("ocr.engine", ocr_engine)
        if service:
            self.config.set("translation.service", service)
            self.config.set("translation.auto_select_service", False)
        previous_source = str(
            self.config.get("translation.source_language", "auto") or "auto"
        )
        if source:
            self.config.set("translation.source_language", source)
            # The main window exposes the source language but not the advanced
            # OCR-language selector.  Keep them aligned when the user actually
            # changes the visible source selector; stale Chinese-only settings
            # must not silently poison English screenshots.
            if source != previous_source:
                self.config.set("ocr.lang", source)
                self.config.set("ocr.language_mode_version", 2)
        if target:
            self.config.set("translation.target_language", target)
        self.config.save()
        self.ocr_engine = self._create_configured_ocr_engine()
        self.translator = create_translator(
            self.config.get("translation.service", "mock"),
            self.config.section("translation"),
            cache=self.cache,
            api_key_resolver=self.config.api_key,
        )
        if self.window is not None:
            self.window.reload_values()
        self.set_status(
            f"已切换：OCR={self._active_ocr_engine_name} 翻译={self.config.get('translation.service')} "
            f"目标={self.config.get('translation.target_language')}"
        )

    def _create_configured_ocr_engine(self):
        """Resolve the requested backend without making a light build unbootable."""
        requested = str(self.config.get("ocr.engine", "windows") or "windows")
        candidates = list(dict.fromkeys((requested, "windows", "paddle", "none")))
        failures: list[str] = []
        for candidate in candidates:
            try:
                engine = _application.create_ocr_engine(
                    candidate, self.config.section("ocr"), self.config
                )
            except (OCRUnavailableError, OSError, RuntimeError, ValueError) as exc:
                failures.append(f"{candidate}: {exc}")
                continue
            self._active_ocr_engine_name = candidate
            if candidate != requested:
                log.warning(
                    "OCR %s unavailable; using %s (%s)",
                    requested,
                    candidate,
                    "; ".join(failures),
                )
                # Keep the visible selectors and the engine actually executing
                # in agreement. This also migrates v0.1 users whose saved
                # Paddle choice is not present in the lightweight package.
                self.config.set("ocr.engine", candidate)
                try:
                    self.config.save()
                except OSError as exc:
                    log.warning("无法保存 OCR 回退选择：%s", exc)
            return engine
        raise OCRUnavailableError("没有可用的 OCR 引擎：" + "; ".join(failures))

    def _resolve_translator_service(self) -> str:
        """启动时若当前是 mock 且检测到已配置的真实服务 Key，自动切换。"""
        service = str(self.config.get("translation.service", "mock"))
        if service != "mock" or not self.config.get("translation.auto_select_service", True):
            return service
        env_names = {
            "openai": "OPENAI_API_KEY",
            "deepl": "DEEPL_API_KEY",
            "google": "GOOGLE_TRANSLATE_API_KEY",
        }
        for candidate in ("openai", "deepl", "google"):
            if os.environ.get(env_names[candidate]) or self.config.api_key(candidate):
                return candidate
        return service

    def _apply_hotkeys(self) -> None:
        try:
            self.hotkey_manager.apply(self.config.hotkeys())
        except HotkeyError as exc:
            log.exception("快捷键注册失败")
            self.set_status(f"快捷键注册失败：{exc}")

    def _apply_autostart(self) -> None:
        try:
            import winreg

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            if self.config.get("general.startup_with_system", False):
                exe = sys_executable()
                winreg.SetValueEx(
                    key, "ScreenTranslator", 0, winreg.REG_SZ, f'"{exe}" "{main_script()}"'
                )
            else:
                try:
                    winreg.DeleteValue(key, "ScreenTranslator")
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        except Exception as exc:
            log.warning("开机启动设置失败：%s", exc)
