"""Refresh output language from the same indices without reprocessing images."""
from __future__ import annotations

from dataclasses import replace

import core
from excel_export import make_xlsx
from i18n import Translator


def localized_palette(palette, mode: str, language: str):
    t = Translator(language)
    if mode == "内置通用色库":
        return [replace(color, name=t(color.name), brand=t(color.brand)) for color in palette]
    if mode == "自动从原画取色":
        return [replace(color, name=t("自动色 {index:02d}", index=index), brand=t("自动取色"))
                for index, color in enumerate(palette, 1)]
    # Brand names, imported names and all codes are user data, not UI messages.
    return list(palette)


def with_localized_exports(result: dict, language: str) -> dict:
    settings = {**result["generation_settings"], "export_language": language}
    palette = localized_palette(result["source_palette"], settings["palette_mode"], language)
    indices = result["indices"]
    usage = core.usage_rows(indices, palette)
    csv_bytes = core.usage_csv(usage)
    pdf_bytes = core.make_pdf(indices, palette, settings["bead_size_mm"],
                              tuple(settings["pdf_cells_per_page"]), settings["show_codes"], language=language)
    xlsx_bytes = make_xlsx(indices, palette, settings["show_codes"], language=language)
    brand = result["brand_palette_data"]
    bundle = core.make_bundle(result["grid"], result["preview"], csv_bytes, pdf_bytes, palette, settings,
                               xlsx_bytes=xlsx_bytes, palette_notice=brand.attribution(language) if brand else None)
    return {**result, "usage": usage, "csv": csv_bytes, "pdf": pdf_bytes, "xlsx": xlsx_bytes,
            "bundle": bundle, "export_language": language}
