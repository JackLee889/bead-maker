from __future__ import annotations

from i18n import LocalizedError, Translator

import csv
import io
import json
import math
import zipfile
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import CIDEncoding, UnicodeCIDFont


MAX_PALETTE_COLORS = 512


@dataclass(frozen=True)
class BeadColor:
    code: str
    name: str
    r: int
    g: int
    b: int
    brand: str = "通用"

    @property
    def rgb(self) -> tuple[int, int, int]:
        return self.r, self.g, self.b

    @property
    def hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"


# These are screen-colour references, not a claim that every bead manufacturer
# makes an exact physical match.  Users can import a measured brand palette.
_GENERIC_64: list[tuple[str, tuple[int, int, int]]] = [
    ("纯白", (255, 255, 255)), ("象牙白", (245, 240, 216)),
    ("浅灰", (211, 215, 218)), ("中灰", (148, 154, 160)),
    ("深灰", (82, 88, 94)), ("黑色", (24, 25, 28)),
    ("奶油黄", (255, 239, 173)), ("浅黄", (255, 221, 87)),
    ("亮黄", (255, 194, 22)), ("金黄", (229, 160, 15)),
    ("浅橙", (255, 180, 91)), ("橙色", (245, 119, 34)),
    ("深橙", (211, 75, 26)), ("珊瑚", (245, 105, 93)),
    ("浅红", (238, 85, 87)), ("正红", (205, 38, 43)),
    ("深红", (137, 27, 35)), ("酒红", (91, 31, 43)),
    ("浅粉", (255, 190, 203)), ("粉红", (242, 128, 161)),
    ("玫红", (215, 55, 121)), ("桃粉", (250, 157, 132)),
    ("浅肤", (255, 218, 185)), ("肤色", (235, 177, 133)),
    ("浅棕", (201, 145, 94)), ("棕色", (143, 89, 54)),
    ("深棕", (83, 51, 36)), ("咖啡", (56, 37, 31)),
    ("淡紫", (214, 190, 230)), ("浅紫", (169, 125, 201)),
    ("紫色", (111, 65, 156)), ("深紫", (68, 42, 103)),
    ("淡蓝", (193, 224, 242)), ("天蓝", (100, 190, 225)),
    ("湖蓝", (39, 151, 196)), ("正蓝", (37, 88, 168)),
    ("深蓝", (31, 52, 107)), ("藏蓝", (24, 35, 66)),
    ("浅青", (170, 231, 225)), ("青色", (57, 190, 185)),
    ("蓝绿", (21, 134, 137)), ("深青", (16, 83, 88)),
    ("淡绿", (203, 231, 174)), ("黄绿", (145, 198, 71)),
    ("草绿", (73, 159, 74)), ("正绿", (26, 119, 71)),
    ("深绿", (22, 76, 51)), ("墨绿", (20, 52, 42)),
    ("薄荷", (150, 220, 183)), ("青柠", (185, 218, 56)),
    ("橄榄", (121, 126, 48)), ("卡其", (180, 164, 111)),
    ("沙色", (218, 195, 151)), ("米色", (230, 213, 181)),
    ("杏色", (237, 190, 141)), ("砖红", (166, 69, 55)),
    ("蓝灰", (109, 132, 151)), ("灰紫", (115, 100, 127)),
    ("烟粉", (190, 132, 143)), ("芥末", (192, 153, 45)),
    ("荧光黄", (225, 243, 42)), ("荧光绿", (80, 231, 75)),
    ("荧光粉", (255, 73, 157)), ("荧光橙", (255, 96, 35)),
]


def builtin_palette(name: str = "通用 64 色") -> list[BeadColor]:
    if "64" in name:
        colors = _GENERIC_64
    else:
        # A balanced 32-colour subset spanning neutrals, warm colours,
        # skin/browns, purples, blues, cyans and greens.
        indexes = [
            0, 1, 2, 3, 4, 5, 6, 8, 11, 12, 14, 15, 16, 18, 19, 20,
            22, 23, 24, 25, 26, 28, 30, 32, 33, 35, 36, 38, 39, 42, 44, 45,
        ]
        colors = [_GENERIC_64[index] for index in indexes]
    return [
        BeadColor(f"G{i:02d}", color_name, *rgb, brand=name)
        for i, (color_name, rgb) in enumerate(colors, 1)
    ]


def _decode_csv(data: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise LocalizedError('色号表编码无法识别，请另存为 UTF-8 CSV。')


def parse_palette_csv(data: bytes) -> list[BeadColor]:
    text = _decode_csv(data)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise LocalizedError('CSV 没有表头。')
    key_map = {str(k).strip().lower(): k for k in reader.fieldnames}
    hex_key = key_map.get("hex") or key_map.get("颜色") or key_map.get("color")
    rgb_keys = [key_map.get(x) for x in ("r", "g", "b")]
    if not hex_key and not all(rgb_keys):
        raise LocalizedError('CSV 需要 hex 列，或同时提供 r、g、b 三列。')

    result: list[BeadColor] = []
    for row_no, row in enumerate(reader, 2):
        if not any(str(v or "").strip() for v in row.values()):
            continue
        try:
            if hex_key:
                raw = str(row.get(hex_key, "")).strip().lstrip("#")
                if len(raw) == 3:
                    raw = "".join(ch * 2 for ch in raw)
                if len(raw) != 6:
                    raise LocalizedError('hex 必须是 6 位颜色值')
                r, g, b = tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
            else:
                r, g, b = (int(str(row.get(k, "")).strip()) for k in rgb_keys)
            if not all(0 <= value <= 255 for value in (r, g, b)):
                raise LocalizedError('RGB 必须在 0–255 之间')
        except (TypeError, ValueError) as exc:
            raise LocalizedError('CSV 第 {row_no} 行颜色无效：{exc}', row_no=row_no, exc=exc) from exc

        code_key = key_map.get("code") or key_map.get("色号")
        name_key = key_map.get("name") or key_map.get("名称")
        brand_key = key_map.get("brand") or key_map.get("品牌")
        code = str(row.get(code_key, "") if code_key else "").strip() or f"C{len(result) + 1:03d}"
        color_name = str(row.get(name_key, "") if name_key else "").strip() or code
        brand = str(row.get(brand_key, "") if brand_key else "").strip() or "自定义"
        result.append(BeadColor(code, color_name, r, g, b, brand))
        if len(result) > MAX_PALETTE_COLORS:
            raise LocalizedError('色号表最多支持 {MAX_PALETTE_COLORS} 个颜色。', MAX_PALETTE_COLORS=MAX_PALETTE_COLORS)

    if not result:
        raise LocalizedError('色号表至少需要一个有效颜色。')
    return result


def palette_template_csv(*, language: str = "zh-CN") -> bytes:
    t = Translator(language)
    text = "brand,code,name,hex\n" + "\n".join((
        f'{t("我的品牌")},A01,{t("白色")},#FFFFFF',
        f'{t("我的品牌")},A02,{t("黑色")},#18191C',
        f'{t("另一品牌")},B01,{t("红色")},#CD262B',
    )) + "\n"
    return text.encode("utf-8-sig")


def load_image(data: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(data))
        image.seek(0)
        if image.width * image.height > 80_000_000:
            raise LocalizedError('图片像素超过 8000 万，请先缩小图片。')
        image.load()
    except ValueError:
        raise
    except Exception as exc:
        raise LocalizedError('无法读取这张图片，请使用 JPG、PNG、WEBP、BMP、TIFF 或 GIF。') from exc
    return ImageOps.exif_transpose(image)


def prepare_image(
    image: Image.Image,
    columns: int,
    rows: int,
    fit_mode: str = "裁剪填满",
    background: tuple[int, int, int] = (255, 255, 255),
    contrast: float = 1.0,
    saturation: float = 1.0,
    line_strength: float = 0.0,
    sharpness: float = 0.0,
) -> Image.Image:
    if not (4 <= columns <= 300 and 4 <= rows <= 300):
        raise LocalizedError('宽和高需要在 4–300 颗之间。')
    if not (0 <= line_strength <= 1 and 0 <= sharpness <= 1):
        raise LocalizedError('细线保留和锐化强度需要在 0–1 之间。')
    rgba = image.convert("RGBA")
    base = Image.new("RGBA", rgba.size, (*background, 255))
    base.alpha_composite(rgba)
    rgb = base.convert("RGB")
    rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    rgb = ImageEnhance.Color(rgb).enhance(saturation)
    def fit(size: tuple[int, int]) -> Image.Image:
        if fit_mode == "完整留白":
            return ImageOps.pad(rgb, size, method=Image.Resampling.LANCZOS, color=background)
        if fit_mode == "拉伸":
            return rgb.resize(size, Image.Resampling.LANCZOS)
        return ImageOps.fit(rgb, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

    result = fit((columns, rows))
    if line_strength > 0:
        # Work at 4 samples per bead, bounded to 1200 x 1200. A closing of
        # luminance identifies narrow dark strokes rather than every dark area.
        detail = fit((columns * 4, rows * 4))
        luminance = detail.convert("L")
        closed = luminance.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
        residual = np.asarray(closed, dtype=np.float32) - np.asarray(luminance, dtype=np.float32)
        weights = np.clip((residual - 12) / 52, 0, 1).reshape(rows, 4, columns, 4)
        pixels = np.asarray(detail, dtype=np.float32).reshape(rows, 4, columns, 4, 3)
        mass = weights.sum(axis=(1, 3))
        line_rgb = (pixels * weights[..., None]).sum(axis=(1, 3)) / np.maximum(mass[..., None], 1e-6)
        base_rgb = np.asarray(result, dtype=np.float32)
        # Do not lighten cells or spread a stroke to a neighbouring bead.
        darker = (line_rgb @ np.array([.299, .587, .114])) < (base_rgb @ np.array([.299, .587, .114]))
        alpha = (np.minimum(mass / 16 * 2.5, .85) * line_strength * darker)[..., None]
        result = Image.fromarray(np.clip(np.rint(base_rgb * (1 - alpha) + line_rgb * alpha), 0, 255).astype(np.uint8))
    if sharpness > 0:
        result = result.filter(ImageFilter.UnsharpMask(radius=.6, percent=round(sharpness * 160), threshold=3))
    return result


def extract_palette(image: Image.Image, color_count: int) -> list[BeadColor]:
    color_count = max(2, min(96, int(color_count)))
    sample = image.copy()
    sample.thumbnail((512, 512), Image.Resampling.LANCZOS)
    quantized = sample.quantize(
        colors=color_count,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB")
    counts = Counter(quantized.getdata())
    rgb_colors = [rgb for rgb, _ in counts.most_common(color_count)]
    return [
        BeadColor(f"A{i:02d}", f"自动色 {i:02d}", *rgb, brand="自动取色")
        for i, rgb in enumerate(rgb_colors, 1)
    ]


def _srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    values = rgb.astype(np.float64) / 255.0
    values = np.where(values <= 0.04045, values / 12.92, ((values + 0.055) / 1.055) ** 2.4)
    xyz = values @ np.array([
        [0.4124564, 0.2126729, 0.0193339],
        [0.3575761, 0.7151522, 0.1191920],
        [0.1804375, 0.0721750, 0.9503041],
    ])
    xyz /= np.array([0.95047, 1.0, 1.08883])
    delta = 6 / 29
    f = np.where(xyz > delta ** 3, np.cbrt(xyz), xyz / (3 * delta ** 2) + 4 / 29)
    return np.stack([
        116 * f[..., 1] - 16,
        500 * (f[..., 0] - f[..., 1]),
        200 * (f[..., 1] - f[..., 2]),
    ], axis=-1)


def map_to_palette(image: Image.Image, palette: Sequence[BeadColor]) -> np.ndarray:
    if not palette:
        raise LocalizedError('至少需要一个颜色。')
    if len(palette) > MAX_PALETTE_COLORS:
        raise LocalizedError('色库最多支持 {MAX_PALETTE_COLORS} 个颜色。', MAX_PALETTE_COLORS=MAX_PALETTE_COLORS)
    pixels = np.asarray(image.convert("RGB"), dtype=np.uint8)
    flat_lab = _srgb_to_lab(pixels.reshape(-1, 3))
    palette_rgb = np.array([c.rgb for c in palette], dtype=np.uint8)
    palette_lab = _srgb_to_lab(palette_rgb)
    result = np.empty(flat_lab.shape[0], dtype=np.int16)
    for start in range(0, len(flat_lab), 4096):
        chunk = flat_lab[start:start + 4096]
        distances = np.sum((chunk[:, None, :] - palette_lab[None, :, :]) ** 2, axis=2)
        result[start:start + len(chunk)] = np.argmin(distances, axis=1)
    return result.reshape(pixels.shape[:2])


def indices_to_image(indices: np.ndarray, palette: Sequence[BeadColor], scale: int = 12) -> Image.Image:
    colors = np.array([c.rgb for c in palette], dtype=np.uint8)
    image = Image.fromarray(colors[indices], mode="RGB")
    return image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _text_color(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    luminance = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return (22, 24, 28) if luminance > 145 else (255, 255, 255)


def render_grid(
    indices: np.ndarray,
    palette: Sequence[BeadColor],
    cell_size: int = 32,
    show_codes: bool = True,
) -> Image.Image:
    rows, columns = indices.shape
    # Bound memory use for very large patterns while retaining legible cells.
    requested_cell = max(14, min(64, int(cell_size)))
    cell_size = min(requested_cell, max(14, 5200 // max(rows, columns)))
    header = max(28, cell_size)
    output = Image.new("RGB", (header + columns * cell_size + 1, header + rows * cell_size + 1), "white")
    draw = ImageDraw.Draw(output)
    code_font = _font(max(7, min(14, cell_size // 3)))
    header_font = _font(max(8, min(13, cell_size // 3)))

    for row in range(rows):
        for col in range(columns):
            color = palette[int(indices[row, col])]
            x0, y0 = header + col * cell_size, header + row * cell_size
            draw.rectangle((x0, y0, x0 + cell_size, y0 + cell_size), fill=color.rgb)
            if show_codes:
                draw.text(
                    (x0 + cell_size / 2, y0 + cell_size / 2),
                    color.code[:5],
                    font=code_font,
                    fill=_text_color(color.rgb),
                    anchor="mm",
                )

    thin, major = (115, 118, 125), (25, 28, 34)
    for col in range(columns + 1):
        x = header + col * cell_size
        width = 2 if col % 5 == 0 else 1
        draw.line((x, header, x, header + rows * cell_size), fill=major if width == 2 else thin, width=width)
    for row in range(rows + 1):
        y = header + row * cell_size
        width = 2 if row % 5 == 0 else 1
        draw.line((header, y, header + columns * cell_size, y), fill=major if width == 2 else thin, width=width)

    for col in range(columns):
        draw.text((header + (col + 0.5) * cell_size, header / 2), str(col + 1), font=header_font, fill=(35, 38, 44), anchor="mm")
    for row in range(rows):
        draw.text((header / 2, header + (row + 0.5) * cell_size), str(row + 1), font=header_font, fill=(35, 38, 44), anchor="mm")
    draw.rectangle((header, header, header + columns * cell_size, header + rows * cell_size), outline=major, width=2)
    return output


def usage_rows(indices: np.ndarray, palette: Sequence[BeadColor]) -> list[dict[str, object]]:
    counts = np.bincount(indices.reshape(-1), minlength=len(palette))
    total = int(indices.size)
    rows = []
    for index, count in enumerate(counts):
        if count:
            color = palette[index]
            rows.append({
                "brand": color.brand,
                "code": color.code,
                "name": color.name,
                "hex": color.hex,
                "r": color.r,
                "g": color.g,
                "b": color.b,
                "count": int(count),
                "percent": round(int(count) * 100 / total, 2),
            })
    return sorted(rows, key=lambda item: (-int(item["count"]), str(item["code"])))


def usage_csv(rows: Iterable[dict[str, object]]) -> bytes:
    output = io.StringIO()
    fields = ["brand", "code", "name", "hex", "r", "g", "b", "count", "percent"]
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    safe_rows = []
    for item in rows:
        safe_item = dict(item)
        for key in ("brand", "code", "name", "hex"):
            value = str(safe_item.get(key, ""))
            if value.startswith(("=", "+", "-", "@")):
                value = "'" + value
            safe_item[key] = value
        safe_rows.append(safe_item)
    writer.writerows(safe_rows)
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def image_png(image: Image.Image) -> bytes:
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def _register_pdf_cjk_font(name: str) -> None:
    if name in pdfmetrics.getRegisteredFontNames():
        return
    font = UnicodeCIDFont(name)
    if name == "MSung-Light":
        # ReportLab's default uses the GB CMap for this CNS font. Correct only
        # our font instance so Traditional Chinese renders in standard readers.
        font.encodingName = "UniCNS-UCS2-H"
        font.encoding = CIDEncoding(font.encodingName)
    pdfmetrics.registerFont(font)


def make_pdf(
    indices: np.ndarray,
    palette: Sequence[BeadColor],
    bead_size_mm: float,
    cells_per_page: tuple[int, int] = (25, 35),
    show_codes: bool = True,
    *,
    language: str = "en",
) -> bytes:
    if (len(cells_per_page) != 2 or
            any(isinstance(value, bool) or not isinstance(value, (int, np.integer)) or value <= 0
                for value in cells_per_page)):
        raise LocalizedError('PDF 每页行列数必须是正整数。')
    t = Translator(language)
    cjk_font = {"zh-CN": "STSong-Light", "zh-TW": "MSung-Light", "ja": "HeiseiKakuGo-W5"}.get(language)
    # CID fonts use the PDF reader's CJK font support; no font or network download.
    if cjk_font:
        _register_pdf_cjk_font(cjk_font)
    regular = cjk_font or "Helvetica"
    bold = cjk_font or "Helvetica-Bold"
    output = io.BytesIO()
    page_size = A4
    pdf = canvas.Canvas(output, pagesize=page_size, pageCompression=1)
    page_w, page_h = page_size
    rows, columns = indices.shape
    usage = usage_rows(indices, palette)

    pdf.setTitle(t("拼豆图"))
    pdf.setFont(bold, 22)
    pdf.drawString(42, page_h - 58, t("拼豆图"))
    pdf.setFont(regular, 11)
    summary = [
        t("网格：{columns} x {rows} 颗（共 {total:,} 颗）", columns=columns, rows=rows, total=columns * rows),
        t("成品尺寸：{width:.1f} x {height:.1f} cm", width=columns * bead_size_mm / 10, height=rows * bead_size_mm / 10),
        t("使用颜色：{count}", count=len(usage)),
        t("每 5 颗拼豆显示一条粗网格线。"),
    ]
    y = page_h - 88
    for line in summary:
        pdf.drawString(42, y, line)
        y -= 18
    y -= 10
    pdf.setFont(bold, 11)
    pdf.drawString(42, y, t("色号"))
    pdf.drawString(104, y, t("名称"))
    pdf.drawString(260, y, "HEX")
    pdf.drawRightString(390, y, t("数量"))
    pdf.drawRightString(470, y, t("占比"))
    y -= 14
    pdf.setFont(regular, 9)
    for item in usage:
        if y < 48:
            pdf.showPage()
            y = page_h - 48
            pdf.setFont(regular, 9)
        rgb = (int(item["r"]), int(item["g"]), int(item["b"]))
        pdf.setFillColor(Color(*(component / 255 for component in rgb)))
        pdf.rect(42, y - 2, 12, 12, fill=1, stroke=1)
        pdf.setFillColorRGB(0.1, 0.1, 0.12)
        pdf.drawString(60, y, str(item["code"])[:12])
        name = str(item["name"])
        name_font = regular
        if not cjk_font and not name.isascii():
            name_font = "STSong-Light"
            _register_pdf_cjk_font(name_font)
        name_size = min(9, 148 / max(1, pdfmetrics.stringWidth(name, name_font, 1)))
        pdf.setFont(name_font, name_size)
        pdf.drawString(104, y, name)
        pdf.setFont(regular, 9)
        pdf.drawString(260, y, str(item["hex"]))
        pdf.drawRightString(390, y, f"{int(item['count']):,}")
        pdf.drawRightString(470, y, f"{float(item['percent']):.2f}%")
        y -= 16
    pdf.showPage()

    tile_columns, tile_rows = cells_per_page
    col_pages = math.ceil(columns / tile_columns)
    row_pages = math.ceil(rows / tile_rows)
    margin, label_space, title_space = 30, 24, 42
    # Every tile shares the same scale, including partial tiles at the edges.
    cell = min(
        (page_w - margin * 2 - label_space) / min(columns, tile_columns),
        (page_h - margin * 2 - title_space - label_space) / min(rows, tile_rows),
    )
    for page_row in range(row_pages):
        for page_col in range(col_pages):
            x_start = page_col * tile_columns
            y_start = page_row * tile_rows
            x_end = min(columns, x_start + tile_columns)
            y_end = min(rows, y_start + tile_rows)
            visible_cols, visible_rows = x_end - x_start, y_end - y_start
            origin_x = margin + label_space
            origin_y = page_h - margin - title_space - label_space

            pdf.setFillColorRGB(0.08, 0.09, 0.11)
            pdf.setFont(bold, 10)
            pdf.drawString(
                margin,
                page_h - margin,
                t("分页 {col_page}/{col_pages}, {row_page}/{row_pages}  |  列 {x_start}-{x_end}, 行 {y_start}-{y_end}",
                  col_page=page_col + 1, col_pages=col_pages, row_page=page_row + 1, row_pages=row_pages,
                  x_start=x_start + 1, x_end=x_end, y_start=y_start + 1, y_end=y_end),
            )
            header_size = max(4, min(7, cell * 0.35))
            pdf.setFont("Helvetica", header_size)
            for local_col, col in enumerate(range(x_start, x_end)):
                x = origin_x + (local_col + 0.5) * cell
                pdf.drawCentredString(x, origin_y + 7, str(col + 1))
            for local_row, row in enumerate(range(y_start, y_end)):
                y_cell = origin_y - (local_row + 1) * cell
                pdf.setFillColorRGB(0.08, 0.09, 0.11)
                pdf.setFont("Helvetica", header_size)
                pdf.drawRightString(origin_x - 5, y_cell + cell * 0.35, str(row + 1))
                for local_col, col in enumerate(range(x_start, x_end)):
                    bead = palette[int(indices[row, col])]
                    x_cell = origin_x + local_col * cell
                    pdf.setFillColor(Color(*(value / 255 for value in bead.rgb)))
                    pdf.rect(x_cell, y_cell, cell, cell, fill=1, stroke=0)
                    if show_codes and cell >= 8:
                        text_rgb = _text_color(bead.rgb)
                        pdf.setFillColor(Color(*(value / 255 for value in text_rgb)))
                        font_size = max(3.5, min(6.5, cell * 0.28))
                        pdf.setFont("Helvetica-Bold", font_size)
                        code = bead.code[:6]
                        pdf.drawCentredString(x_cell + cell / 2, y_cell + cell * 0.35, code)
            pdf.setStrokeColorRGB(0.15, 0.16, 0.18)
            for local_col in range(visible_cols + 1):
                major = (x_start + local_col) % 5 == 0 or local_col in (0, visible_cols)
                pdf.setLineWidth(0.7 if major else 0.25)
                x = origin_x + local_col * cell
                pdf.line(x, origin_y, x, origin_y - visible_rows * cell)
            for local_row in range(visible_rows + 1):
                major = (y_start + local_row) % 5 == 0 or local_row in (0, visible_rows)
                pdf.setLineWidth(0.7 if major else 0.25)
                y = origin_y - local_row * cell
                pdf.line(origin_x, y, origin_x + visible_cols * cell, y)
            pdf.showPage()

    pdf.save()
    return output.getvalue()


def make_bundle(
    grid_png: bytes,
    preview_png: bytes,
    csv_bytes: bytes,
    pdf_bytes: bytes,
    palette: Sequence[BeadColor],
    settings: dict[str, object],
    xlsx_bytes: bytes | None = None,
    *,
    palette_notice: str | None = None,
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pattern_grid.png", grid_png)
        archive.writestr("pixel_preview.png", preview_png)
        archive.writestr("bead_usage.csv", csv_bytes)
        archive.writestr("printable_pattern.pdf", pdf_bytes)
        if xlsx_bytes is not None:
            archive.writestr("bead_pattern.xlsx", xlsx_bytes)
        if palette_notice is not None:
            archive.writestr("palette_source.txt", palette_notice.encode("utf-8"))
        archive.writestr(
            "palette_used.csv",
            usage_csv([{
                "brand": color.brand, "code": color.code, "name": color.name,
                "hex": color.hex, "r": color.r, "g": color.g, "b": color.b,
                "count": "", "percent": "",
            } for color in palette]),
        )
        archive.writestr(
            "settings.json",
            json.dumps(settings, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return output.getvalue()
