"""有道翻译适配器测试（用 monkeypatch 拦截网络请求）。"""

from __future__ import annotations

import pytest
import requests

from services.translation.base import TranslationError
from services.translation.factory import create_translator


class _Resp:
    def __init__(self, status_code: int, payload) -> None:
        self.status_code = status_code
        self._payload = payload
        self.encoding = "utf-8"

    def json(self):
        return self._payload


def test_youdao_translate_success(monkeypatch):
    cfg = {"youdao": {"app_key": "key", "app_secret": "secret"}}
    tr = create_translator("youdao", cfg)
    captured = {}

    def fake_post(url, data=None, timeout=30, **_kw):
        captured["data"] = data
        return _Resp(200, {"translation": ["你好", "世界"], "errorCode": "0"})

    monkeypatch.setattr(requests, "post", fake_post)
    out = tr.translate(["hello", "world"], "en", "zh")
    assert out == ["你好", "世界"]
    assert captured["data"]["appKey"] == "key"
    assert captured["data"]["signType"] == "v3"
    assert "sign" in captured["data"]


def test_youdao_missing_credentials(monkeypatch):
    tr = create_translator("youdao", {"youdao": {}})
    with pytest.raises(TranslationError):
        tr.translate(["hi"], "auto", "zh")


def test_youdao_error_code(monkeypatch):
    cfg = {"youdao": {"app_key": "k", "app_secret": "s"}}
    tr = create_translator("youdao", cfg)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(200, {"errorCode": "108", "errorMsg": "x"}))
    with pytest.raises(TranslationError):
        tr.translate(["hi"], "auto", "zh")


def test_youdao_rate_limited(monkeypatch):
    cfg = {"youdao": {"app_key": "k", "app_secret": "s"}}
    tr = create_translator("youdao", cfg)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(429, {}))
    with pytest.raises(TranslationError) as ei:
        tr._translate_batch(["hi"], "auto", "zh")
    assert ei.value.rate_limited
