"""image_utils 工具测试。"""

from __future__ import annotations

import numpy as np

from utils.image_utils import frame_signature


def test_frame_signature_none():
    assert frame_signature(None) == ""


def test_frame_signature_stable():
    img = np.zeros((120, 120, 3), dtype=np.uint8)
    img[0:60] = 255
    assert frame_signature(img) == frame_signature(img)


def test_frame_signature_changes_on_content():
    # dhash 只反映相邻列梯度，均匀图（全黑/全白）会得到相同哈希；
    # 用渐变方向相反的两张图来验证其能区分内容变化。
    a = np.zeros((120, 120, 3), dtype=np.uint8)
    a[:, 0:60] = 255  # 左白右黑（水平渐变）
    b = np.ones((120, 120, 3), dtype=np.uint8) * 255
    b[:, 0:60] = 0  # 左黑右白（水平渐变）
    assert frame_signature(a) != frame_signature(b)
    assert len(frame_signature(a)) > 0
