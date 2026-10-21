from __future__ import annotations

import html
import hashlib
import json
import math
import base64

import streamlit as st
from PIL import Image
from brand_palettes import BRAND_PALETTES, load_brand_palette
from i18n import Translator, error_text
from language_ui import language_controls, translated_selection
from localized_exports import with_localized_exports
from grid_viewer import grid_viewer

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass

from core import (
    builtin_palette,
    extract_palette,
    image_png,
    indices_to_image,
    load_image,
    map_to_palette,
    palette_template_csv,
    parse_palette_csv,
    prepare_image,
    render_grid,
)


language = language_controls()
t = Translator(language)

st.set_page_config(page_title=t('拼豆图生成器'), page_icon="▦", layout="wide")
st.markdown(
    """
    <style>
      :root { --ink:#243746; --accent:#c65236; --paper:#fffdf8; }
      .stApp { background:#f6f7f9; color:var(--ink); }
      [data-testid="stHeader"] { background:transparent; }
      [data-testid="stMainBlockContainer"] { max-width:1440px; padding-top:3.5rem; }
      [data-testid="stSidebar"] { background:#fffdf9; border-right:1px solid #e3e6e9; }
      [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color:#596773; font-size:.82rem; line-height:1.6; }
      [data-testid="stCaptionContainer"] { opacity:1; }
      [data-testid="stExpander"] { background:#fff; border-radius:12px; border-color:#e3e6e9; }
      [data-testid="stMetric"] { background:white; border:1px solid #e3e6e9; border-radius:12px; padding:16px; }
      [data-testid="stMetricValue"] { font-size:clamp(1.1rem, 1.6vw, 1.7rem); white-space:normal; }
      [data-testid="stMetricValue"] > div { white-space:normal; overflow:visible; text-overflow:clip; }
      [data-testid="stTabs"] [role="tablist"] { gap:1rem; }
      .stButton button[kind="primary"]:not(:disabled) { background:var(--accent); border-color:var(--accent); color:white; }
      h1 { letter-spacing:-0.04em; color:var(--ink); }
      .small-note { color:#59636e; font-size:.92rem; line-height:1.55; }
      .intro-badges { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 12px; }
      .intro-badges span { border:1px solid #dce5e1; border-radius:20px; padding:4px 10px; font-size:.78rem; color:#3e655b; background:#edf5f0; }
      .workflow { display:flex; gap:12px; margin:14px 0; flex-wrap:wrap; color:#596773; font-size:.88rem; }
      .workflow span { background:white; border:1px solid #e3e6e9; border-radius:8px; padding:8px 12px; }
      .bead-pixel-view { box-sizing:border-box; width:100%; min-width:0; max-width:100%; overflow:auto; max-height:min(720px, 70vh); background:white; border:1px solid #dde3e7; border-radius:10px; scrollbar-color:#98a5b2 #edf1f5; scrollbar-width:auto; }
      .bead-pixel-view:focus-visible { outline:3px solid #c65236; outline-offset:2px; }
      .bead-pixel-view img { display:block; max-width:none; height:auto; margin:0 auto; }
      .bead-compare-view { height:clamp(280px, 60vh, 640px); max-height:none; }
      .bead-view-fit img { width:100%; height:100%; object-fit:contain; object-position:center; }
      .legend { width:100%; border-collapse:collapse; font-size:.9rem; }
      .legend th,.legend td { padding:8px 10px; border-bottom:1px solid #dde2e7; text-align:left; }
      .swatch { display:inline-block; width:20px; height:20px; border:1px solid #777; border-radius:5px; vertical-align:middle; }
      div.stButton > button, div.stDownloadButton > button { border-radius:10px; min-height:2.65rem; }
      @media (max-width:640px) {
        [data-testid="stMainBlockContainer"] { padding:2.5rem 1rem 1rem; }
        [data-testid="stMainBlockContainer"] h1 { font-size:1.8rem; text-wrap:balance; }
        .workflow { gap:6px; font-size:.8rem; }
      }
    </style>
    """,
    unsafe_allow_html=True,
)


def parse_hex(value: str) -> tuple[int, int, int]:
    raw = value.strip().lstrip("#")
    if len(raw) != 6:
        return 255, 255, 255
    try:
        return tuple(int(raw[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return 255, 255, 255


def legend_html(items: list[dict[str, object]]) -> str:
    table_rows = []
    for item in items:
        table_rows.append(
            "<tr>"
            f"<td><span class='swatch' style='background:{html.escape(str(item['hex']))}'></span></td>"
            f"<td>{html.escape(str(item['brand']))}</td>"
            f"<td><strong>{html.escape(str(item['code']))}</strong></td>"
            f"<td>{html.escape(str(item['name']))}</td>"
            f"<td>{html.escape(str(item['hex']))}</td>"
            f"<td>{int(item['count']):,}</td>"
            f"<td>{float(item['percent']):.2f}%</td>"
            "</tr>"
        )
    headers = "".join(f"<th>{html.escape(t(label))}</th>" for label in ("颜色", "品牌", "色号", "名称", "HEX", "数量", "占比"))
    return (
        "<div style='overflow:auto'><table class='legend'>"
        f"<thead><tr>{headers}</tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table></div>"
    )


def pixel_view(
    data: bytes,
    width: int | None,
    label: str,
    *,
    comparison: bool = False,
    pixelated: bool = True,
) -> None:
    """Fit the full image or scroll its actual width inside a bounded viewport."""
    encoded = base64.b64encode(data).decode("ascii")
    classes = "bead-pixel-view"
    if comparison:
        classes += " bead-compare-view"
    if width is None:
        classes += " bead-view-fit"
    image_style = f"width:{int(width)}px;" if width is not None else ""
    if pixelated:
        image_style += "image-rendering:pixelated;"
    escaped_label = html.escape(label, quote=True)
    st.html(
        f'<div class="{classes}" tabindex="0" role="region" aria-label="{escaped_label}">'
        f'<img src="data:image/png;base64,{encoded}" alt="{escaped_label}" '
        f'style="{image_style}" /></div>',
        width="stretch",
    )


def text_badges(css_class: str, labels: list[str]) -> str:
    return f'<div class="{css_class}">' + ''.join(f'<span>{html.escape(t(label))}</span>' for label in labels) + '</div>'


st.markdown(text_badges("intro-badges", ["本机处理", "无需账号", "多格式图纸导出"]), unsafe_allow_html=True)
st.title(t('拼豆图生成器'))
st.markdown(
    "<div class='small-note'>" + html.escape(t("上传一幅画，设置拼豆数量和色库，即可生成可制作、可统计、可打印的拼豆图。")) + "</div>",
    unsafe_allow_html=True,
)
st.markdown(text_badges("workflow", ["01 · 上传原画", "02 · 调整图纸设置", "03 · 生成与下载"]), unsafe_allow_html=True)

uploaded = st.file_uploader(
    t('上传原画'),
    type=["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "gif", "heic", "heif"],
    help=t('支持常见图片格式；GIF 使用第一帧。'),
    key="source_file",
)
st.caption(t('支持 JPG、PNG、WEBP 等常见图片，每张最多 60 MB；GIF 只取第一帧。更换原画后需重新生成图纸。'))

source_image: Image.Image | None = None
source_bytes: bytes | None = None
if uploaded is not None:
    if uploaded.size > 60 * 1024 * 1024:
        st.session_state.pop("result", None)
        st.session_state.pop("source_id", None)
        st.error(t('图片超过 60 MB，请先压缩后再上传。'))
    else:
        source_bytes = uploaded.getvalue()
        source_id = hashlib.sha256(source_bytes).hexdigest()
        if st.session_state.get("source_id") != source_id:
            st.session_state.pop("result", None)
            st.session_state["source_id"] = source_id
        try:
            source_image = load_image(source_bytes)
        except ValueError as exc:
            st.session_state.pop("result", None)
            st.error(error_text(exc, language))
else:
    st.session_state.pop("result", None)
    st.session_state.pop("source_id", None)

with st.sidebar:
    st.header(t('图纸设置'))
    st.caption(t('每项参数下方都有说明。可以收起暂时不用的分组，调整后点击生成。'))
    generate_slot = st.container()
    st.divider()
with st.sidebar.expander(t('01 · 尺寸与构图'), expanded=True):
    columns = st.number_input(t('横向拼豆数'), 4, 300, 50, 1, key='columns')
    st.caption(t('范围 4–300 颗。越多越能保留细节，但用豆量和成品宽度也会增加。'))
    keep_ratio = st.checkbox(t('按原画比例自动计算纵向'), value=True, key='keep_ratio')
    st.caption(t('开启后按原图比例计算高度；关闭后可分别设置宽高。自动高度仍限制在 4–300 颗。'))
    if source_image is not None and keep_ratio:
        rows = max(4, min(300, round(columns * source_image.height / source_image.width)))
        st.caption(t('当前纵向：{rows} 颗，由原图比例自动计算。', rows=rows))
    else:
        rows = st.number_input(t('纵向拼豆数'), 4, 300, 50, 1, key='rows')
        st.caption(t('范围 4–300 颗，控制图案高度；上传图片并锁定比例后，此值将自动计算。'))
    fit_mode = translated_selection("selectbox", t('构图方式'), ["裁剪填满", "完整留白", "拉伸"], key="fit_mode", language=language)
    st.caption(t({"裁剪填满": "保持比例并填满网格，超出部分会从四周居中裁掉。",
                "完整留白": "保持比例并保留整张原图，空余区域使用下方选择的背景色。",
                "拉伸": "把原图强制铺满指定宽高；比例不一致时，人物或物体会变形。"}[fit_mode]))
    bead_size = st.number_input(t('单颗拼豆直径（mm）'), 1.0, 10.0, 2.6, 0.1, key='bead_size')
    st.caption(t('用于估算实物尺寸：颗数 × 直径。不改变图像清晰度，也不控制 PDF 的实际打印格子尺寸。'))
    background_hex = st.color_picker(t('透明/留白区域颜色'), "#FFFFFF", key='background')
    st.caption(t('填充透明像素和构图留白，随后参与配色。这些区域仍需要拼豆，不会成为空格。'))

with st.sidebar.expander(t('02 · 图像与清晰度'), expanded=True):
    contrast = st.slider(t('对比度'), 0.5, 2.0, 1.0, 0.05, key='contrast')
    st.caption(t('1.0 保持原始对比。调高可加强深浅区别；调低更柔和，但细线可能变淡。'))
    saturation = st.slider(t('饱和度'), 0.0, 2.0, 1.05, 0.05, key='saturation')
    st.caption(t('1.0 保持原始色彩，0 为灰度；调高更鲜艳，过高可能丢失柔和的颜色层次。'))
    line_strength = st.slider(t('细线保留（动漫/插画）'), 0.0, 1.0, 0.65, 0.05, key='line_strength')
    st.caption(t('加强嘴部、帽檐等细暗线，建议从 0.65 开始。照片或纹理较多时可调为 0，避免杂点加重。'))
    sharpness = st.slider(t('轻度锐化'), 0.0, 1.0, 0.25, 0.05, key='sharpness')
    st.caption(t('增强缩小后的局部边缘，建议从 0.25 开始；0 为关闭。过高可能出现硬边或光晕，不能恢复所有细节。'))

with st.sidebar.expander(t('03 · 色库与配色'), expanded=True):
    palette_mode = translated_selection("radio",
        t('色库来源'),
        ["内置通用色库", "内置品牌色卡", "自动从原画取色", "导入品牌/自定义色号表"],
        key="palette_mode", language=language,
    )
    st.caption(t('品牌色卡按对应品牌色号配色，已随程序内置；也可使用通用色、自动取色或导入自己的色表。'))
    palette_name = "通用 64 色"
    auto_count = 24
    custom_file = None
    palette_sha256 = None
    selected_brands: list[str] = []
    custom_palette = None
    brand_palette = None
    brand_colors = []
    palette_groups: list[str] = []
    if palette_mode == "内置通用色库":
        palette_name = translated_selection("selectbox", t('通用色库'), ["通用 32 色", "通用 64 色"], index=1, key="generic_palette", language=language)
        st.caption(t('32 色较容易备料，64 色层次更丰富。均为屏幕参考色，不代表任何实体品牌的官方颜色。'))
    elif palette_mode == "内置品牌色卡":
        bead_brand = st.selectbox(t('拼豆品牌'), list(BRAND_PALETTES), key="bead_brand")
        versions = BRAND_PALETTES[bead_brand]
        palette_id = translated_selection("selectbox",
            t('色卡版本'), list(versions), format_func=lambda value: t(versions[value]), key="brand_palette_id", language=language,
        )
        try:
            brand_palette = load_brand_palette(palette_id)
            palette_name = brand_palette.label
            palette_sha256 = brand_palette.sha256
            selected_brands = [bead_brand]
            palette_groups = translated_selection("multiselect",
                t('参与配色的色号分组'),
                list(brand_palette.group_counts),
                default=list(brand_palette.group_counts),
                key=f"brand_groups_{palette_id}",
                language=language,
            )
            brand_colors = brand_palette.select(palette_groups)
            st.caption(t('已选 {v0} / {v1} 个可用色号。可取消自己没有的分组，生成时只使用所选颜色。', v0=len(brand_colors), v1=len(brand_palette.entries)))
            if brand_palette.excluded_codes:
                st.caption(t('此版已排除 {v0} 条未确认色号，不会出现在图纸或采购统计中。', v0=len(brand_palette.excluded_codes)))
            if not brand_colors:
                st.warning(t('请至少选择一个色号分组。'))
            st.caption(t('色卡为公开整理的屏幕参考色；透明、夜光等特殊材质的效果请对照实物。单颗直径请按实物规格填写。'))
            st.caption(t('数据日期：{v0} · [查看色卡来源]({v1})', v0=brand_palette.data_date, v1=brand_palette.source_info()['source_url']))
        except ValueError as exc:
            st.error(error_text(exc, language))
    elif palette_mode == "自动从原画取色":
        auto_count = st.slider(t('自动颜色数量'), 2, 64, 24, 1, key='auto_count')
        st.caption(t('设置最多提取的颜色数，实际可能更少。颜色越多层次越丰富；自动色需自行寻找近似实体拼豆。'))
    else:
        st.download_button(
            t('下载 CSV 色号表模板'),
            palette_template_csv(language=language),
            "palette_template.csv",
            "text/csv",
            width="stretch",
        )
        custom_file = st.file_uploader(t('导入色号表 CSV'), type=["csv"], key="palette_file")
        st.caption(t('支持 1–512 色。使用 brand、code、name、hex 列，或用 r、g、b 替代 hex；可先下载模板填写。'))
        if custom_file is not None:
            custom_bytes = custom_file.getvalue()
            palette_sha256 = hashlib.sha256(custom_bytes).hexdigest()
            try:
                custom_palette = parse_palette_csv(custom_bytes)
                brands = sorted({color.brand for color in custom_palette})
                selected_brands = st.multiselect(t('选择要使用的品牌'), brands, default=brands, key='custom_brands')
                st.caption(t('只使用勾选品牌的颜色进行匹配，可多选；至少选择一个品牌。'))
                st.caption(t('已识别 {v0} 个颜色、{v1} 个品牌。', v0=len(custom_palette), v1=len(brands)))
            except ValueError as exc:
                st.error(error_text(exc, language))

with st.sidebar.expander(t('04 · 图纸与打印'), expanded=True):
    show_codes = st.checkbox(t('格子内显示色号'), value=True, key='show_codes')
    st.caption(t('控制 PNG、PDF 和 Excel 格内的色号。关闭后保留色块，用量统计仍然包含完整色号。'))
    cell_size = st.slider(t('PNG 单格大小（像素）'), 18, 48, 30, 2, key='cell_size')
    st.caption(t('只调整 PNG 图纸中格子和文字的大小，不增加图案细节；大网格会自动限制渲染尺寸。'))
    pdf_layout_label = translated_selection("selectbox", t('A4 每页网格'), ["25 × 35（最清楚）", "30 × 40", "40 × 55（最省纸）"], key="pdf_layout", language=language)
    st.caption(t('每页格子越少，色号越大、页数越多。PDF 各页比例一致，但不是按拼豆直径 1:1 打印。'))
    pdf_layout = {
        "25 × 35（最清楚）": (25, 35),
        "30 × 40": (30, 40),
        "40 × 55（最省纸）": (40, 55),
    }[pdf_layout_label]
    if source_image is not None:
        grid_pages = math.ceil(columns / pdf_layout[0]) * math.ceil(rows / pdf_layout[1])
        st.caption(t('PDF 将生成 {grid_pages} 页网格，另附色号统计页；各页格子大小一致。', grid_pages=grid_pages))
        if grid_pages > 36:
            st.warning(t('图纸页数较多，生成和打印需要更长时间，可选择更密的分页规格。'))

with generate_slot:
    generate = st.button(
        t('生成拼豆图'), type="primary", width="stretch",
        disabled=source_image is None or (palette_mode == "内置品牌色卡" and not brand_colors),
        key="generate",
    )
    if source_image is not None:
        st.caption(t('本次设置：{v0} × {v1} 颗 · {v2:,} 颗拼豆', v0=int(columns), v1=int(rows), v2=int(columns) * int(rows)))
    else:
        st.caption(t('先在右侧上传原画，再调整参数并生成。'))

if source_image is None:
    st.info(t('先上传一张原画。可以先用默认参数生成，再根据效果调整左侧设置。'))
    st.stop()

settings = {
    "app_version": "1.5.0",
    "columns": int(columns), "rows": int(rows), "fit_mode": fit_mode,
    "keep_ratio": keep_ratio,
    "bead_size_mm": float(bead_size), "palette_mode": palette_mode,
    "palette_name": palette_name if palette_mode in ("内置通用色库", "内置品牌色卡") else None,
    "brand_palette": brand_palette.source_info() if brand_palette else None,
    "palette_groups": sorted(palette_groups),
    "auto_count": int(auto_count) if palette_mode == "自动从原画取色" else None,
    "palette_sha256": palette_sha256,
    "selected_brands": sorted(selected_brands), "show_codes": show_codes,
    "contrast": float(contrast), "saturation": float(saturation),
    "line_strength": float(line_strength), "sharpness": float(sharpness),
    "background": background_hex, "pdf_cells_per_page": list(pdf_layout),
    "png_cell_size": int(cell_size),
    "source_name": uploaded.name, "source_sha256": st.session_state["source_id"],
}
settings_id = hashlib.sha256(
    json.dumps(settings, ensure_ascii=False, sort_keys=True).encode("utf-8")
).hexdigest()
previous = st.session_state.get("result")
if previous and previous.get("settings_id") != settings_id:
    st.session_state.pop("result", None)
    st.info(t('设置或色库已变化，请重新生成拼豆图后下载。'))

if generate:
    # A failed attempt must never leave a previous success available to download.
    st.session_state.pop("result", None)
    try:
        prepared = prepare_image(
            source_image,
            int(columns),
            int(rows),
            fit_mode,
            parse_hex(background_hex),
            float(contrast),
            float(saturation),
            line_strength=float(line_strength),
            sharpness=float(sharpness),
        )
        if palette_mode == "内置通用色库":
            palette = builtin_palette(palette_name)
        elif palette_mode == "内置品牌色卡":
            if not brand_palette or not brand_colors:
                raise ValueError(t("请选择有效的品牌色卡和色号分组。"))
            palette = brand_colors
        elif palette_mode == "自动从原画取色":
            palette = extract_palette(prepared, int(auto_count))
        else:
            if not custom_palette:
                raise ValueError(t("请先导入有效的 CSV 色号表。"))
            palette = [color for color in custom_palette if color.brand in selected_brands]
            if not palette:
                raise ValueError(t("请至少选择一个包含有效颜色的品牌。"))

        indices = map_to_palette(prepared, palette)
        preview = indices_to_image(indices, palette, scale=max(4, min(16, 800 // max(int(columns), int(rows)))))
        grid = render_grid(indices, palette, int(cell_size), show_codes)
        grid_bytes = image_png(grid)
        preview_bytes = image_png(preview)
        pending_result = {
            "settings_id": settings_id,
            "preview": preview_bytes, "grid": grid_bytes,
            "columns": int(columns), "rows": int(rows), "bead_size": float(bead_size),
            "palette_name": settings["palette_name"],
            "indices": indices, "source_palette": palette, "generation_settings": settings,
            "brand_palette_data": brand_palette,
        }
        st.session_state["result"] = with_localized_exports(pending_result, language)
    except Exception as exc:
        st.error(t('生成失败：{error}', error=error_text(exc, language)))

result = st.session_state.get("result")
if result and result.get("export_language") != language:
    try:
        result = with_localized_exports(result, language)
        st.session_state["result"] = result
    except Exception as exc:
        st.session_state.pop("result", None)
        result = None
        st.error(t("生成失败：{error}", error=error_text(exc, language)))

preview_width = None
if result:
    zoom = st.select_slider(
        t('对比预览缩放'),
        options=["适应窗口", 2, 4, 6, 8, 10, 12, 16],
        value="适应窗口",
        format_func=lambda value: t(value) if isinstance(value, str) else t("{value} 像素/颗", value=value),
        key="comparison_zoom",
    )
    if zoom != "适应窗口":
        preview_width = result["columns"] * int(zoom)
    st.caption(t('两图同步缩放；适应窗口可查看完整图片，放大后可在各自框内横向、纵向滚动。仅调整预览，不改变图纸和下载文件。'))

left, right = st.columns(2, gap="large")
with left:
    st.subheader(t('处理前'))
    pixel_view(image_png(source_image), preview_width, t("原画预览"), comparison=True, pixelated=False)
with right:
    st.subheader(t('处理后'))
    if result:
        pixel_view(result["preview"], preview_width, t("拼豆效果预览"), comparison=True)
    else:
        st.info(t('调整设置后点击“生成拼豆图”。'))

if result:
    st.divider()
    if result.get("palette_name"):
        display_name = (f"{brand_palette.brand} · {t(brand_palette.version)}" if brand_palette else t(result["palette_name"]))
        st.caption(t('本次生成色卡：{v0}', v0=display_name))
    total = result["columns"] * result["rows"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(t('网格'), f"{result['columns']} × {result['rows']}")
    m2.metric(t('拼豆总数'), f"{total:,}")
    m3.metric(t('实际使用颜色'), f"{len(result['usage'])}")
    m4.metric(
        t('预计成品尺寸'),
        f"{result['columns'] * result['bead_size'] / 10:.1f} × {result['rows'] * result['bead_size'] / 10:.1f} cm",
    )

    tab_grid, tab_usage, tab_download = st.tabs([t("彩色网格图"), t("色号与数量"), t("下载")])
    with tab_grid:
        grid_viewer(result["grid"], language)
        st.caption(t('点击“放大查看”或图纸可缩放、拖动查看；每 5 颗一条粗线，顶部与左侧为坐标。'))
    with tab_usage:
        st.markdown(legend_html(result["usage"]), unsafe_allow_html=True)
    with tab_download:
        st.success(t('图纸已就绪。备份或分享选 ZIP；打印制作选 PDF；逐格查看选 Excel。'))
        d1, d2 = st.columns(2)
        with d1:
            st.download_button(t('下载完整图纸包（ZIP）'), result["bundle"], "bead_pattern_package.zip", "application/zip", type="primary", width="stretch")
            st.caption(t('包含所有图纸、色号表与本次生成设置，方便保存和分享。'))
            st.download_button(t('下载彩色网格图（PNG）'), result["grid"], "pattern_grid.png", "image/png", width="stretch")
            st.caption(t('带坐标和网格的图片，适合屏幕查看或分享。'))
            if "xlsx" in result:
                st.download_button(t('下载像素单元格图（Excel）'), result["xlsx"], "bead_pattern.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
                st.caption(t('每颗拼豆对应一个单元格，从 A1 开始；附生成时的色号用量统计。格内色号沿用生成设置。'))
            else:
                st.info(t('请重新生成拼豆图，以启用新增的 Excel 下载。'))
        with d2:
            st.download_button(t('下载 A4 分页图纸（PDF）'), result["pdf"], "printable_pattern.pdf", "application/pdf", width="stretch")
            st.caption(t('按所选网格密度分页，附色号用量统计，适合打印制作。'))
            st.download_button(t('下载色号数量表（CSV）'), result["csv"], "bead_usage.csv", "text/csv", width="stretch")
            st.caption(t('列出色号、数量和占比，可用于备料和核对；不包含网格图。'))
