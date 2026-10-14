"""运行时路径辅助单测（纯标准库，无需 PySide6，可在 CI / 沙箱直接运行）。

覆盖打包（frozen）与源码两种形态下 ``main_script`` / ``sys_executable`` 的取值——
这是开机自启逻辑依赖的关键分支。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.runtime import main_script, sys_executable  # noqa: E402


def test_sys_executable_matches_interpreter():
    assert sys_executable() == sys.executable


def test_main_script_source_mode_is_absolute_entry():
    # 非冻结（源码）模式：返回入口脚本的绝对路径
    assert main_script() == os.path.abspath(sys.argv[0])


def test_main_script_frozen_mode_returns_executable(monkeypatch):
    # 冻结（PyInstaller 打包）模式：sys.argv[0] 不可靠，应回退到可执行文件本身
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "argv", ["some/relative/entry.py"])
    assert main_script() == sys.executable


def test_main_script_is_always_absolute(monkeypatch):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "argv", ["relative.py"])
    assert os.path.isabs(main_script())
