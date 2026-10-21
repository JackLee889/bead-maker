"""Bundled brand palettes: local data only, with traceable source snapshots."""
from __future__ import annotations

from i18n import LocalizedError, Translator

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from core import BeadColor, MAX_PALETTE_COLORS


DATA_DIR = Path(__file__).resolve().parent / "data" / "brand_palettes"
SOURCE_REPOSITORY = "https://github.com/HansBug/pindou-color-data"
SOURCE_COMMIT = "178dafbc9e77d3de556550dbd058270200129186"
# Palette IDs also identify the original upstream folder and bundled JSON file.
BRAND_PALETTES = {
    "MARD": {
        "mard-221-github": "221 色（基础版）",
        "mard-291-github": "291 色（扩展版）",
    },
    "COCO": {"coco-291": "291 色（公开色卡）"},
    "漫漫": {"manman-278": "278 色（公开色卡）"},
    "盼盼": {"panpan-289": "289 条记录（285 色可用）"},
    "咪小窝": {"mixiaowo-290": "290 条记录（286 色可用）"},
}


@dataclass(frozen=True)
class BrandPalette:
    palette_id: str
    brand: str
    version: str
    data_date: str
    sha256: str
    entries: tuple[tuple[str, BeadColor], ...]
    excluded_codes: tuple[str, ...]

    @property
    def label(self) -> str:
        return f"{self.brand} · {self.version}"

    @property
    def group_counts(self) -> dict[str, int]:
        return dict(Counter(group for group, _ in self.entries))

    def select(self, groups: Sequence[str] | None = None) -> list[BeadColor]:
        if groups is None:
            return [color for _, color in self.entries]
        selected = set(groups)
        if selected - self.group_counts.keys():
            raise LocalizedError('所选色号分组不属于当前色卡。')
        return [color for group, color in self.entries if group in selected]

    def source_info(self) -> dict[str, object]:
        return {
            "id": self.palette_id,
            "brand": self.brand,
            "version": self.version,
            "data_date": self.data_date,
            "sha256": self.sha256,
            "source_repository": SOURCE_REPOSITORY,
            "source_commit": SOURCE_COMMIT,
            "source_url": f"{SOURCE_REPOSITORY}/blob/{SOURCE_COMMIT}/{self.palette_id}/colors.json",
            "excluded_codes": list(self.excluded_codes),
            "reference_only": True,
        }

    def attribution(self, language: str = "zh-CN") -> str:
        t = Translator(language)
        license_text = (DATA_DIR / "LICENSE").read_text(encoding="utf-8")
        return "\n".join((
            t("色卡：{label}", label=f"{self.brand} · {t(self.version)}"),
            t("数据日期：{date}", date=self.data_date),
            t("数据来源：{url}", url=self.source_info()["source_url"]),
            f"SHA-256: {self.sha256}",
            t("数据为公开整理的屏幕参考色，不代表品牌官方实测值。"),
            t("未确认色号已排除：{count} 条。", count=len(self.excluded_codes)), "", license_text,
        ))


def load_brand_palette(palette_id: str) -> BrandPalette:
    """Read a known local palette and reject corrupt or ambiguous color records."""
    spec = next(
        ((brand, versions[palette_id]) for brand, versions in BRAND_PALETTES.items()
         if palette_id in versions),
        None,
    )
    if spec is None:
        raise LocalizedError('未找到所选品牌色卡。')
    brand, version = spec
    try:
        raw = (DATA_DIR / f"{palette_id}.json").read_bytes()
        data = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise LocalizedError('品牌色卡无法读取，请确认程序的 data/brand_palettes 文件夹完整。') from exc

    try:
        if data["schema"] != "pindou-color-palette" or data["id"] != palette_id:
            raise LocalizedError('色卡标识不匹配')
        rows = data["colors"]
        if not isinstance(rows, list) or len(rows) != data["count"]:
            raise LocalizedError('色卡数量不匹配')
        entries = []
        excluded = []
        seen = set()
        for row in rows:
            code = row["code"]
            if not isinstance(code, str) or not code.strip():
                raise LocalizedError('色号必须为非空文本')
            if row.get("unidentified") or code.startswith("UNKNOWN-") or code == "-":
                excluded.append(code)
                continue
            if code in seen:
                raise LocalizedError('重复色号：{code}', code=code)
            seen.add(code)
            rgb = row["rgb"]
            if not isinstance(rgb, list) or len(rgb) != 3 or any(
                type(value) is not int or not 0 <= value <= 255 for value in rgb
            ):
                raise LocalizedError('RGB 无效：{code}', code=code)
            group = row["group"]
            if not isinstance(group, str) or not group.strip():
                raise LocalizedError('色号分组无效：{code}', code=code)
            color = BeadColor(code, code, *rgb, brand=brand)
            if color.hex != str(row["hex"]).upper():
                raise LocalizedError('HEX 与 RGB 不一致：{code}', code=code)
            entries.append((group, color))
        if not 1 <= len(entries) <= MAX_PALETTE_COLORS:
            raise LocalizedError('可用颜色数必须在 1–{MAX_PALETTE_COLORS} 之间', MAX_PALETTE_COLORS=MAX_PALETTE_COLORS)
        return BrandPalette(
            palette_id, brand, version, str(data["generated_at"]),
            hashlib.sha256(raw).hexdigest(), tuple(entries), tuple(excluded),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LocalizedError('品牌色卡数据无效：{exc}', exc=exc) from exc
