"""Application version and release-channel constants."""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

_SOURCE_VERSION = "0.3.0-beta"


def _runtime_version() -> str:
    if not getattr(sys, "frozen", False):
        return _SOURCE_VERSION
    try:
        value = (Path(sys._MEIPASS) / "build-version.txt").read_text(
            encoding="ascii"
        ).strip()
    except (AttributeError, OSError) as exc:
        _log.debug("读取冻结版本文件失败，回退源码版本：%s", exc)
        return _SOURCE_VERSION
    if re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", value):
        return value
    return _SOURCE_VERSION


__version__ = _runtime_version()
RELEASE_REPOSITORY = "xuange-hu/screen-translator"
RELEASE_CHANNEL = "beta"
