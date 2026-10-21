"""Browser-only IP detection and per-browser language preference storage."""
from __future__ import annotations

import os
import uuid
from pathlib import Path
import streamlit as st
import streamlit.components.v2 as components

from i18n import LANGUAGES, Translator, country_language, resolve_language, valid_preference


_BRIDGE_JS = (Path(__file__).resolve().parent / "frontend" / "language.js").read_text(encoding="utf-8")


def _bridge(**kwargs):
    # Idempotent registration also supports fresh Streamlit runtimes in AppTest.
    return components.component("bead_language", js=_BRIDGE_JS)(**kwargs)


def _accept_environment() -> None:
    state = st.session_state
    environment = state.get("language_environment", {}).get("environment")
    if isinstance(environment, dict) and state.get("_language_preference") is None:
        state["_language_preference"] = valid_preference(environment.get("preference"))


def _remember_choice() -> None:
    preference = st.session_state["language_choice"]
    st.session_state["_language_preference"] = preference
    st.query_params["lang"] = preference


def language_controls() -> str:
    state = st.session_state
    if "_language_preference" not in state:
        state["_language_preference"] = valid_preference(st.query_params.get("lang"))
    if "_language_session" not in state:
        state["_language_session"] = str(uuid.uuid4())
    ip_enabled = os.environ.get("BEAD_MAKER_IP_LANGUAGE", "1").lower() not in ("0", "false", "off")
    existing = state.get("language_environment", {}).get("environment") or {}
    initial_language = resolve_language(state["_language_preference"], existing.get("country") if ip_enabled else None,
                                        existing.get("locale") or st.context.locale)
    result = _bridge(
        data={"preference": state["_language_preference"], "ipEnabled": ip_enabled, "session": state["_language_session"],
              "language": initial_language},
        default={"environment": None}, on_environment_change=_accept_environment,
        key="language_environment", height=0,
    )
    environment = result.environment if isinstance(result.environment, dict) else {}
    if state["_language_preference"] is None:
        saved = valid_preference(environment.get("preference"))
        if saved is not None:
            state["_language_preference"] = saved
    preference = state["_language_preference"] or "auto"
    country = environment.get("country") if ip_enabled else None
    locale = environment.get("locale") or st.context.locale
    language = resolve_language(preference, country, locale)
    state["_language_effective"] = language
    # The explicit key keeps widget identity stable when its label is translated.
    if state.get("language_choice") != preference:
        state["language_choice"] = preference
    t = Translator(language)
    st.sidebar.selectbox(
        "语言 / Language / 言語", ["auto", *LANGUAGES],
        format_func=lambda value: "Auto (IP) / 自动 / 自動" if value == "auto" else LANGUAGES[value],
        key="language_choice", on_change=_remember_choice,
    )
    if preference != "auto":
        note = t("已手动选择，优先于自动识别。")
    elif country_language(country):
        note = t("已按 IP 地区 {country} 自动选择：{language}。", country=country, language=LANGUAGES[language])
    else:
        note = t("当前使用浏览器语言：{language}；IP 不可用时保持此语言。", language=LANGUAGES[language])
    st.sidebar.caption(note)
    st.sidebar.caption(t("自动模式通过 Country.is 查询 IP 地区；图片不参与查询。"))
    return language


def _save_selection(model_key: str, widget_key: str) -> None:
    st.session_state.setdefault("_selection_values", {})[model_key] = st.session_state[widget_key]


def translated_selection(kind: str, label: str, options, *, key: str, language: str,
                         index: int = 0, default=None, format_func=None):
    """Keep canonical values while rebuilding translated option labels.

    Streamlit 1.63 can retain the old formatted selection with an unchanged key.
    Only these option widgets get language-specific keys; the model survives
    widget cleanup, language changes and a return to a previous language.
    """
    options = list(options)
    values = st.session_state.setdefault("_selection_values", {})
    widget_key = f"{key}__{language}"
    selected = values.get(key, default if kind == "multiselect" else options[index])
    if kind == "multiselect":
        selected = [value for value in (selected or []) if value in options]
        kwargs = {"default": selected}
    else:
        selected = selected if selected in options else options[index]
        kwargs = {"index": options.index(selected)}
    value = getattr(st, kind)(label, options, key=widget_key, format_func=format_func or Translator(language),
                              on_change=_save_selection, args=(key, widget_key), **kwargs)
    values[key] = value
    return value
