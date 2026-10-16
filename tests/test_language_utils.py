"""语言工具单测：needs_translation 启发式 + 各服务语言参数映射。

该模块是纯逻辑（不依赖 PySide6 / 网络），因此可离线运行，
并纳入 CI 的 `pure` 作业做快速回归。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.language_utils import (  # noqa: E402
    LANGUAGES,
    LANGUAGE_CODES,
    display_name,
    needs_translation,
    to_azure_lang,
    to_baidu_lang,
    to_deepl_lang,
    to_google_lang,
    to_mymemory_lang,
    to_openai_lang,
    to_paddle_lang,
    to_windows_lang,
    to_youdao_lang,
)

ALL_MAPPERS = [
    to_paddle_lang,
    to_openai_lang,
    to_deepl_lang,
    to_google_lang,
    to_windows_lang,
    to_mymemory_lang,
    to_baidu_lang,
    to_youdao_lang,
    to_azure_lang,
]


# --------------------------------------------------------- needs_translation


def test_empty_and_whitespace_are_rejected():
    assert needs_translation("", "zh") is False
    assert needs_translation("   ", "zh") is False


def test_single_ascii_letter_is_rejected():
    assert needs_translation("A", "zh") is False
    assert needs_translation("x", "zh") is False


def test_single_cjk_char_still_counts_when_target_differs():
    """单个汉字对英文目标语言仍是待翻译内容（不会被单字母规则误杀）。"""
    assert needs_translation("中", "en") is True


def test_technical_paths_are_rejected():
    assert needs_translation("app/services/ocr.py", "zh") is False
    assert needs_translation("C:\\Users\\me\\notes.txt", "zh") is False


def test_technical_filenames_are_rejected():
    assert needs_translation("requirements.txt", "zh") is False
    assert needs_translation("build.spec", "zh") is False
    assert needs_translation("photo.JPG", "zh") is False


def test_hex_ids_are_rejected():
    assert needs_translation("deadbeef1234", "zh") is False
    assert needs_translation("a1b2c3d4e5f6a7b8", "zh") is False


def test_brand_names_are_rejected():
    assert needs_translation("Claude", "zh") is False
    assert needs_translation("GitHub", "zh") is False


def test_xhigh_token_is_rejected():
    assert needs_translation("xhigh", "zh") is False
    assert needs_translation("XHIGH", "zh") is False


def test_benchmark_labels_are_rejected():
    assert needs_translation("SWE-Bench Verified", "zh") is False
    assert needs_translation("GDPval-AA", "zh") is False


def test_normal_sentence_needs_translation():
    assert needs_translation("Please save the file before closing.", "zh") is True


def test_target_zh_pure_chinese_is_skipped():
    assert needs_translation("这是一段已经翻译好的中文", "zh") is False


def test_target_zh_with_few_latin_words_is_skipped():
    """少量英文单词混在中文里不值得再翻一次。"""
    assert needs_translation("设置 保存 OK 取消", "zh") is False


def test_target_zh_half_chinese_half_english_is_translated():
    """回归：半中半英的残缺覆盖层必须能被修回来。

    旧逻辑只要看见一个汉字就整块跳过，导致残留英文永远翻不掉。
    """
    mixed = "这是一段中文 " + "the quick brown fox jumps over the lazy dog"
    assert needs_translation(mixed, "zh") is True


def test_target_ja_kana_is_skipped():
    assert needs_translation("これは日本語です", "ja") is False


def test_target_ko_hangul_is_skipped():
    assert needs_translation("안녕하세요 세계", "ko") is False


def test_target_ru_cyrillic_is_skipped():
    assert needs_translation("Привет мир", "ru") is False


def test_target_ar_arabic_is_skipped():
    assert needs_translation("مرحبا بالعالم", "ar") is False


def test_target_th_thai_is_skipped():
    assert needs_translation("สวัสดีชาวโลก", "th") is False


def test_chinese_text_still_translates_to_english():
    assert needs_translation("这是一段中文", "en") is True


# -------------------------------------------------------------- display_name


def test_display_name_known_codes():
    assert display_name("zh") == "简体中文"
    assert display_name("zh-hant") == "繁体中文"
    assert display_name("en") == "英语"
    assert display_name("auto") == "自动检测"


def test_display_name_unknown_falls_back_to_code():
    assert display_name("xx") == "xx"


def test_language_codes_match_table():
    assert LANGUAGE_CODES == [code for code, _ in LANGUAGES]
    assert LANGUAGE_CODES[0] == "auto"
    assert len(LANGUAGE_CODES) == len(LANGUAGES)


# ------------------------------------------------------------------- mappers


def test_paddle_mapping():
    assert to_paddle_lang("zh") == "ch"
    assert to_paddle_lang("zh-hant") == "chinese_cht"
    assert to_paddle_lang("ja") == "japan"
    assert to_paddle_lang("ko") == "korean"
    assert to_paddle_lang("nope") == "ch", "未知语言回退中文"


def test_openai_mapping():
    assert to_openai_lang("zh") == "简体中文 (zh)"
    assert to_openai_lang("en") == "English (en)"
    assert to_openai_lang("auto") == "auto"
    assert to_openai_lang("nope") == "nope"


def test_deepl_mapping():
    assert to_deepl_lang("en") == "EN-US"
    assert to_deepl_lang("zh") == "ZH"
    assert to_deepl_lang("auto") == ""
    assert to_deepl_lang("fr") == "FR"


def test_google_mapping():
    assert to_google_lang("zh") == "zh-CN"
    assert to_google_lang("zh-hant") == "zh-TW"
    assert to_google_lang("ja") == "ja", "未列出的语言原样返回"


def test_windows_mapping():
    assert to_windows_lang("zh") == "zh-Hans-CN"
    assert to_windows_lang("zh-hant") == "zh-Hant-TW"
    assert to_windows_lang("en") == "en-US"
    assert to_windows_lang("nope") == "zh-Hans-CN"


def test_mymemory_mapping():
    assert to_mymemory_lang("auto") == "en"
    assert to_mymemory_lang("zh") == "zh-CN"
    assert to_mymemory_lang("zh-hant") == "zh-TW"


def test_baidu_mapping():
    assert to_baidu_lang("ja") == "jp"
    assert to_baidu_lang("ko") == "kor"
    assert to_baidu_lang("fr") == "fra"
    assert to_baidu_lang("zh-hant") == "zh"


def test_youdao_mapping():
    assert to_youdao_lang("zh") == "zh-CHS"
    assert to_youdao_lang("zh-hant") == "zh-CHT"


def test_azure_mapping():
    assert to_azure_lang("zh") == "zh-Hans"
    assert to_azure_lang("zh-hant") == "zh-Hant"
    assert to_azure_lang("auto") == "", "Azure 省略源语言即自动检测"


def test_every_language_code_maps_without_error():
    """所有内置语言代码都应能穿过每一个映射函数，且返回字符串。"""
    for code in LANGUAGE_CODES:
        for mapper in ALL_MAPPERS:
            result = mapper(code)
            assert isinstance(result, str), f"{mapper.__name__}({code}) 返回非字符串"


def test_mappers_return_strings_for_unknown_code():
    for mapper in ALL_MAPPERS:
        assert isinstance(mapper("__unknown__"), str)


def test_no_mapper_returns_none():
    for code in LANGUAGE_CODES:
        for mapper in ALL_MAPPERS:
            assert mapper(code) is not None


def test_hex_regex_boundary():
    """少于 7 位的十六进制串不算 commit id，仍需翻译判定流程。"""
    assert not re.fullmatch(r"[0-9a-f]{7,64}", "abc123", re.IGNORECASE)
    assert re.fullmatch(r"[0-9a-f]{7,64}", "abc1234", re.IGNORECASE)
