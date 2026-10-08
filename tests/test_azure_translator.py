"""Azure 翻译适配器测试（用 monkeypatch 拦截网络请求）。"""

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


def test_azure_translate_success(monkeypatch):
    cfg = {"azure": {"api_key": "key", "region": "eastasia"}}
    tr = create_translator("azure", cfg)
    captured = {}

    def fake_post(url, params=None, headers=None, json=None, timeout=30, **_kw):
        captured.update(url=url, params=params, headers=headers, json=json)
        return _Resp(200, [{"translations": [{"text": "你好", "to": "zh-Hans"}]}])

    monkeypatch.setattr(requests, "post", fake_post)
    out = tr.translate(["hello"], "en", "zh")
    assert out == ["你好"]
    assert captured["params"]["to"] == "zh-Hans"
    assert captured["params"]["api-version"] == "3.0"
    assert captured["headers"]["Ocp-Apim-Subscription-Region"] == "eastasia"
    assert captured["headers"]["Ocp-Apim-Subscription-Key"] == "key"


def test_azure_missing_key(monkeypatch):
    tr = create_translator("azure", {"azure": {"region": "eastasia"}})
    with pytest.raises(TranslationError):
        tr.translate(["hi"], "auto", "zh")


def test_azure_missing_region(monkeypatch):
    tr = create_translator("azure", {"azure": {"api_key": "key"}})
    with pytest.raises(TranslationError):
        tr.translate(["hi"], "auto", "zh")


def test_azure_rate_limited(monkeypatch):
    cfg = {"azure": {"api_key": "key", "region": "eastasia"}}
    tr = create_translator("azure", cfg)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(429, {}))
    with pytest.raises(TranslationError) as ei:
        tr._translate_batch(["hi"], "auto", "zh")
    assert ei.value.rate_limited
