"""公共 HTTP 错误转换 helper 测试。"""

from __future__ import annotations

import pytest

from services.translation.base import TranslationError
from services.translation.http_errors import raise_for_status


class _Resp:
    def __init__(self, code: int) -> None:
        self.status_code = code


def test_ok_passes():
    raise_for_status(_Resp(200), "X")  # 不应抛异常
    raise_for_status(_Resp(204), "X")


def test_rate_limited_flag():
    with pytest.raises(TranslationError) as ei:
        raise_for_status(_Resp(429), "Svc")
    assert ei.value.rate_limited


def test_auth_error():
    with pytest.raises(TranslationError):
        raise_for_status(_Resp(403), "Svc")


def test_server_error():
    with pytest.raises(TranslationError):
        raise_for_status(_Resp(500), "Svc")
