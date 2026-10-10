"""百度翻译开放平台 API v2 适配器（MD5 签名）。"""

from __future__ import annotations

import hashlib
import html
import os
import random
import string

import requests

from services.translation.base import TranslationError, Translator, register_translator
from services.translation.http_errors import raise_for_status
from utils.language_utils import to_baidu_lang


class BaiduTranslator(Translator):
    name = "baidu"

    def __init__(self, config_section: dict, cache=None, api_key: str = "") -> None:
        super().__init__(config_section, cache)
        cfg = config_section.get("baidu", {}) if config_section else {}
        self.appid = os.environ.get("BAIDU_APP_ID", "") or str(cfg.get("appid", "")).strip()
        self.secret = (
            os.environ.get("BAIDU_APP_KEY", "") or str(cfg.get("api_key", "")).strip()
        )
        self.base_url = str(
            cfg.get("base_url", "https://fanyi-api.baidu.com/api/trans/vip/translate")
        ).rstrip("/")

    def _translate_batch(self, texts: list[str], source_language: str | None, target_language: str) -> list[str]:
        if not self.appid or not self.secret:
            raise TranslationError(
                "缺少百度翻译 APP ID / Key：请在设置填写，或设置环境变量 BAIDU_APP_ID、BAIDU_APP_KEY"
            )
        q = "\n".join(texts)
        salt = "".join(random.choices(string.digits, k=10))
        sign = hashlib.md5(
            (self.appid + q + salt + self.secret).encode("utf-8")
        ).hexdigest()
        source = to_baidu_lang(source_language) if source_language and source_language != "auto" else "auto"
        params = {
            "q": q,
            "from": source,
            "to": to_baidu_lang(target_language),
            "appid": self.appid,
            "salt": salt,
            "sign": sign,
        }
        try:
            resp = requests.post(
                self.base_url, data=params, timeout=float(self.config.get("timeout_seconds", 30))
            )
        except requests.RequestException as exc:
            raise TranslationError("百度翻译请求失败（网络连接异常）") from exc
        if resp.status_code != 200:
            raise_for_status(resp, "百度")
        try:
            data = resp.json()
        except ValueError as exc:
            raise TranslationError("百度翻译响应格式异常") from exc
        if "error_code" in data:
            raise TranslationError(
                f"百度翻译错误 {data.get('error_code')}: {data.get('error_msg', '')}"
            )
        results = data.get("trans_result") or []
        out = [html.unescape(item.get("dst", "")) for item in results]
        if len(out) != len(texts):
            # 单行模式下百度可能把整段作为一条返回
            if len(texts) == 1 and len(out) == 1:
                return out
            raise TranslationError("百度翻译返回条数与请求不符")
        return out


register_translator(BaiduTranslator)
