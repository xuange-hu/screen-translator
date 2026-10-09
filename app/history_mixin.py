"""把截图与识别结果落盘到 history 目录。"""

from __future__ import annotations

import json
import time
from pathlib import Path

from app.logger import get_logger
from app.models import CaptureInfo, TextRegion

log = get_logger("application")


class HistoryMixin:
    """把截图与识别结果落盘到 history 目录。"""

    def _save_history(self, capture: CaptureInfo, regions: list[TextRegion]) -> None:
        if not self.config.get("general.save_history", False):
            return
        try:
            history_dir = Path(self.config.get("general.history_dir", "") or "history")
            history_dir.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d_%H%M%S")
            capture_path = history_dir / f"capture_{stamp}.png"
            from PIL import Image

            rgb = capture.image[:, :, ::-1]
            Image.fromarray(rgb, mode="RGB").save(capture_path, format="PNG")
            record = {"capture": capture_path.name, "regions": [r.to_dict() for r in regions]}
            (history_dir / f"regions_{stamp}.json").write_text(
                json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as exc:
            log.warning("保存历史失败：%s", exc)
