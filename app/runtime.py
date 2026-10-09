"""运行时路径辅助：解析当前可执行文件与入口脚本。

单独成模块，避免 ``app.application`` 被其它模块循环导入（设置里的开机自启逻辑需要它）。
"""

from __future__ import annotations

import os
import sys


def sys_executable() -> str:
    return sys.executable


def main_script() -> str:
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.abspath(sys.argv[0])
