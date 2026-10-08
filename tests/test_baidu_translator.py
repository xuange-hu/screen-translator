"""百度翻译适配器测试（用 monkeypatch 拦截网络请求）。"""

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


def test_baidu_translate_success(monkeypatch):
    cfg = {"baidu": {"appid": "appid", "api_key": "secret"}}
    tr = create_translator("baidu", cfg)
    captured = {}

    def fake_post(url, data=None, timeout=30, **_kw):
        captured["data"] = data
        return _Resp(
            200,
            {
                "from": "en",
                "to": "zh",
                "trans_result": [
                    {"src": "hello", "dst": "你好"},
                    {"src": "world", "dst": "世界"},
                ],
            },
        )

    monkeypatch.setattr(requests, "post", fake_post)
    out = tr.translate(["hello", "world"], "en", "zh")
    assert out == ["你好", "世界"]
    assert captured["data"]["appid"] == "appid"
    assert "sign" in captured["data"] and captured["data"]["salt"]


def test_baidu_missing_credentials(monkeypatch):
    tr = create_translator("baidu", {"baidu": {}})
    with pytest.raises(TranslationError):
        tr.translate(["hi"], "auto", "zh")


def test_baidu_error_code(monkeypatch):
    cfg = {"baidu": {"appid": "a", "api_key": "k"}}
    tr = create_translator("baidu", cfg)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(200, {"error_code": "54001", "error_msg": "x"}))
    with pytest.raises(TranslationError):
        tr.translate(["hi"], "auto", "zh")


def test_baidu_rate_limited(monkeypatch):
    cfg = {"baidu": {"appid": "a", "api_key": "k"}}
    tr = create_translator("baidu", cfg)
    monkeypatch.setattr(requests, "post", lambda *a, **k: _Resp(429, {}))
    # 限流由底层批次抛出并被基类降级；这里直接校验底层抛错且带 rate_limited 标记。
    with pytest.raises(TranslationError) as ei:
        tr._translate_batch(["hi"], "auto", "zh")
    assert ei.value.rate_limited
