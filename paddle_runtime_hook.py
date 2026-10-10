"""PyInstaller runtime hook：让 paddle 在冻结环境里能找到自己的 DLL 目录。"""

import logging
import os
import sys

_log = logging.getLogger(__name__)

_base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.argv[0])))
_libs = os.path.join(_base, "paddle", "libs")
if os.path.isdir(_libs):
    try:
        os.add_dll_directory(_libs)
    except AttributeError as exc:
        _log.debug("当前平台不支持 add_dll_directory，跳过：%s", exc)
    os.environ["PATH"] = _libs + os.pathsep + os.environ.get("PATH", "")
