"""Local translations and language selection, independent of Streamlit state."""
from __future__ import annotations

from functools import lru_cache
import json
from pathlib import Path
import re


LANGUAGES = {"zh-CN": "简体中文", "zh-TW": "繁體中文", "en": "English", "ja": "日本語"}
LOCALES_DIR = Path(__file__).resolve().parent / "locales"


@lru_cache(maxsize=4)
def catalog(language: str) -> dict[str, str]:
    language = language if language in LANGUAGES else "zh-CN"
    return json.loads((LOCALES_DIR / f"{language}.json").read_text(encoding="utf-8"))


class Translator:
    def __init__(self, language: str = "zh-CN"):
        self.language = language if language in LANGUAGES else "zh-CN"

    def __call__(self, message: str, **values: object) -> str:
        text = catalog(self.language).get(message, message)
        return text.format(**values) if values else text


class LocalizedError(ValueError):
    """A ValueError with a translatable template; data arguments remain literal."""
    def __init__(self, message: str, **values: object):
        self.message = message
        self.values = values
        super().__init__(message.format(**values) if values else message)

    def translated(self, language: str) -> str:
        values = {key: error_text(value, language) if isinstance(value, Exception) else value
                  for key, value in self.values.items()}
        return Translator(language)(self.message, **values)


def error_text(error: Exception, language: str) -> str:
    return error.translated(language) if isinstance(error, LocalizedError) else str(error)


def valid_preference(value: object) -> str | None:
    return value if isinstance(value, str) and value in ("auto", *LANGUAGES) else None


def browser_language(locale: str | None) -> str:
    tag = (locale or "").replace("_", "-").lower()
    if tag.startswith("zh"):
        return "zh-TW" if any(part in ("hant", "tw", "hk", "mo") for part in tag.split("-")) else "zh-CN"
    if tag.startswith("ja"):
        return "ja"
    return "en" if tag else "zh-CN"


def country_language(country: object) -> str | None:
    if not isinstance(country, str) or not re.fullmatch(r"[A-Z]{2}", country) or country in ("XX", "ZZ"):
        return None
    if country == "CN":
        return "zh-CN"
    if country in ("TW", "HK", "MO"):
        return "zh-TW"
    return "ja" if country == "JP" else "en"


def resolve_language(preference: object, country: object = None, locale: str | None = None) -> str:
    if isinstance(preference, str) and preference in LANGUAGES:
        return preference
    return country_language(country) or browser_language(locale)
