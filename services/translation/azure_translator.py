"""Azure AI 翻译（Microsoft Translator）适配器。"""

from __future__ import annotations

import html
import os

import requests

from services.translation.base import TranslationError, Translator, register_translator
from services.translation.http_errors import raise_for_status
from utils.language_utils import to_azure_lang


class AzureTranslator(Translator):
    name = "azure"

    def __init__(self, config_section: dict, cache=None, api_key: str = "") -> None:
        super().__init__(config_section, cache)
        cfg = config_section.get("azure", {}) if config_section else {}
        self.key = os.environ.get("AZURE_TRANSLATOR_KEY", "") or str(cfg.get("api_key", "")).strip()
        self.region = os.environ.get("AZURE_TRANSLATOR_REGION", "") or str(cfg.get("region", "")).strip()
        self.base_url = str(
            cfg.get("base_url", "https://api.cognitive.microsofttranslator.com")
        ).rstrip("/")

    def _translate_batch(self, texts: list[str], source_language: str | None, target_language: str) -> list[str]:
        if not self.key:
            raise TranslationError(
                "缺少 Azure 翻译 Key：请在设置填写，或设置环境变量 AZURE_TRANSLATOR_KEY"
            )
        if not self.region:
            raise TranslationError(
                "缺少 Azure 翻译区域（Region）：请在设置填写 region，或设置环境变量 AZURE_TRANSLATOR_REGION"
            )
        source = to_azure_lang(source_language) if source_language and source_language != "auto" else None
        target = to_azure_lang(target_language)
        params = {"api-version": "3.0", "to": target}
        if source:
            params["from"] = source
        headers = {
            "Ocp-Apim-Subscription-Key": self.key,
            "Ocp-Apim-Subscription-Region": self.region,
            "Content-Type": "application/json",
        }
        body = [{"Text": t} for t in texts]
        try:
            resp = requests.post(
                f"{self.base_url}/translate",
                params=params,
                headers=headers,
                json=body,
                timeout=float(self.config.get("timeout_seconds", 30)),
            )
        except requests.RequestException as exc:
            raise TranslationError("Azure 翻译请求失败（网络连接异常）") from exc
        if resp.status_code != 200:
            raise_for_status(resp, "Azure")
        try:
            data = resp.json()
        except ValueError as exc:
            raise TranslationError("Azure 翻译响应格式异常") from exc
        out: list[str] = []
        for index, item in enumerate(data):
            translations = item.get("translations") or []
            if translations:
                out.append(html.unescape(translations[0].get("text", "")))
            else:
                out.append(texts[index])
        return out


register_translator(AzureTranslator)
