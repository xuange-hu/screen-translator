"""有道智云文本翻译 API（SHA256 v3 签名）。"""

from __future__ import annotations

import hashlib
import os
import time
import uuid

import html
import requests

from services.translation.base import TranslationError, Translator, register_translator
from services.translation.http_errors import raise_for_status
from utils.language_utils import to_youdao_lang


def _sign(app_key: str, q: str, salt: str, curtime: str, app_secret: str) -> str:
    truncated = q if len(q) <= 20 else f"{q[:10]}{len(q)}{q[-10:]}"
    return hashlib.sha256(
        (app_key + truncated + salt + curtime + app_secret).encode("utf-8")
    ).hexdigest()


class YoudaoTranslator(Translator):
    name = "youdao"

    def __init__(self, config_section: dict, cache=None, api_key: str = "") -> None:
        super().__init__(config_section, cache)
        cfg = config_section.get("youdao", {}) if config_section else {}
        self.app_key = os.environ.get("YOUDAO_APP_KEY", "") or str(cfg.get("app_key", "")).strip()
        self.app_secret = (
            os.environ.get("YOUDAO_APP_SECRET", "") or str(cfg.get("app_secret", "")).strip()
        )
        self.base_url = str(
            cfg.get("base_url", "https://openapi.youdao.com/api")
        ).rstrip("/")

    def _translate_batch(self, texts: list[str], source_language: str | None, target_language: str) -> list[str]:
        if not self.app_key or not self.app_secret:
            raise TranslationError(
                "缺少有道翻译 App Key / Secret：请在设置填写，或设置环境变量 YOUDAO_APP_KEY、YOUDAO_APP_SECRET"
            )
        curtime = str(int(time.time()))
        salt = uuid.uuid4().hex
        sign = _sign(self.app_key, "\n".join(texts), salt, curtime, self.app_secret)
        source = to_youdao_lang(source_language) if source_language and source_language != "auto" else "auto"
        params = {
            "q": texts,
            "from": source,
            "to": to_youdao_lang(target_language),
            "appKey": self.app_key,
            "salt": salt,
            "sign": sign,
            "signType": "v3",
            "curtime": curtime,
        }
        try:
            resp = requests.post(
                self.base_url, data=params, timeout=float(self.config.get("timeout_seconds", 30))
            )
        except requests.RequestException as exc:
            raise TranslationError("有道翻译请求失败（网络连接异常）") from exc
        if resp.status_code != 200:
            raise_for_status(resp, "有道")
        try:
            data = resp.json()
        except ValueError as exc:
            raise TranslationError("有道翻译响应格式异常") from exc
        if str(data.get("errorCode", "0")) not in ("0", "200", ""):
            raise TranslationError(
                f"有道翻译错误 {data.get('errorCode')}: {data.get('errorMsg', '')}"
            )
        out = data.get("translation") or []
        if len(out) != len(texts):
            if len(texts) == 1 and len(out) == 1:
                return out
            raise TranslationError("有道翻译返回条数与请求不符")
        return [html.unescape(t) for t in out]


register_translator(YoudaoTranslator)
