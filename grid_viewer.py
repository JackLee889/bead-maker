"""Local, browser-side grid preview with an explicit zoom and pan viewer."""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit.components.v2 as components

from i18n import Translator


_FRONTEND = Path(__file__).resolve().parent / "frontend"
_JS = (_FRONTEND / "grid_viewer.js").read_text(encoding="utf-8")
_CSS = (_FRONTEND / "grid_viewer.css").read_text(encoding="utf-8")


def grid_viewer(png: bytes, language: str) -> None:
    t = Translator(language)
    # Register in the current runtime, including fresh AppTest runtimes.
    viewer = components.component("bead_grid_viewer", js=_JS, css=_CSS)
    viewer(
        key="color_grid_viewer", height="content",
        data={
            "image": "data:image/png;base64," + base64.b64encode(png).decode("ascii"),
            "labels": {
                "title": t("彩色网格图"), "open": t("放大查看"),
                "in": t("放大"), "out": t("缩小"), "fit": t("适应窗口"),
                "actual": t("原始大小"), "close": t("关闭"),
                "hint": t("滚轮或按钮缩放，拖动查看细节；按 Esc 关闭。"),
            },
        },
    )
