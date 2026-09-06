from __future__ import annotations

import html
import hashlib
import io

import streamlit as st
from PIL import Image
from excel_export import make_xlsx

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
    make_bundle,
    make_pdf,
    map_to_palette,
    palette_template_csv,
    parse_palette_csv,
    prepare_image,
    render_grid,
    usage_csv,
    usage_rows,
)


st.set_page_config(page_title="拼豆图生成器", page_icon="▦", layout="wide")
st.markdown(
    """
    <style>
      :root { --ink:#17202a; --accent:#e35d36; --paper:#fffdf8; }
      .stApp { background:linear-gradient(145deg,#fffdf8 0%,#f5f7fb 65%,#eef7f4 100%); }
      [data-testid="stHeader"] { background:transparent; }
      h1 { letter-spacing:-0.04em; color:var(--ink); }
      .small-note { color:#59636e; font-size:.92rem; line-height:1.55; }
      .legend { width:100%; border-collapse:collapse; font-size:.9rem; }
      .legend th,.legend td { padding:8px 10px; border-bottom:1px solid #dde2e7; text-align:left; }
      .swatch { display:inline-block; width:20px; height:20px; border:1px solid #777; border-radius:5px; vertical-align:middle; }
      .metric-card { padding:14px 16px; background:rgba(255,255,255,.78); border:1px solid #dde2e7; border-radius:14px; }
      div.stButton > button, div.stDownloadButton > button { border-radius:10px; min-height:2.65rem; }
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
    return (
        "<div style='overflow:auto'><table class='legend'>"
        "<thead><tr><th>颜色</th><th>品牌</th><th>色号</th><th>名称</th><th>HEX</th><th>数量</th><th>占比</th></tr></thead>"
        f"<tbody>{''.join(table_rows)}</tbody></table></div>"
    )


st.title("拼豆图生成器")
st.markdown(
    "<div class='small-note'>上传一幅画，设置拼豆数量和色库，即可生成可制作、可统计、可打印的拼豆图。</div>",
    unsafe_allow_html=True,
)

uploaded = st.file_uploader(
    "上传原画",
    type=["jpg", "jpeg", "png", "webp", "bmp", "tif", "tiff", "gif", "heic", "heif"],
    help="支持常见图片格式；GIF 使用第一帧。",
)

source_image: Image.Image | None = None
source_bytes: bytes | None = None
if uploaded is not None:
    source_bytes = uploaded.getvalue()
    if len(source_bytes) > 60 * 1024 * 1024:
        st.error("图片超过 60 MB，请先压缩后再上传。")
    else:
        try:
            source_image = load_image(source_bytes)
            source_id = hashlib.sha256(source_bytes).hexdigest()
            if st.session_state.get("source_id") != source_id:
                st.session_state.pop("result", None)
                st.session_state["source_id"] = source_id
        except ValueError as exc:
            st.error(str(exc))

with st.sidebar:
    st.header("图纸设置")
    columns = st.number_input("横向拼豆数", 4, 300, 50, 1)
    keep_ratio = st.checkbox("按原画比例自动计算纵向", value=True)
    if source_image is not None and keep_ratio:
        rows = max(4, min(300, round(columns * source_image.height / source_image.width)))
        st.caption(f"纵向将使用 {rows} 颗")
    else:
        rows = st.number_input("纵向拼豆数", 4, 300, 50, 1)
    fit_mode = st.selectbox("构图方式", ["裁剪填满", "完整留白", "拉伸"], index=0)
    bead_size = st.number_input("单颗拼豆直径（mm）", 1.0, 10.0, 5.0, 0.1)
    background_hex = st.color_picker("透明/留白区域颜色", "#FFFFFF")

    st.divider()
    st.subheader("图像调整")
    contrast = st.slider("对比度", 0.5, 2.0, 1.05, 0.05)
    saturation = st.slider("饱和度", 0.0, 2.0, 1.05, 0.05)

    st.divider()
    st.subheader("颜色匹配")
    palette_mode = st.radio(
        "色库来源",
        ["内置通用色库", "自动从原画取色", "导入品牌/自定义色号表"],
    )
    palette_name = "通用 64 色"
    auto_count = 24
    custom_file = None
    selected_brands: list[str] = []
    custom_palette = None
    if palette_mode == "内置通用色库":
        palette_name = st.selectbox("通用色库", ["通用 32 色", "通用 64 色"], index=1)
        st.caption("屏幕参考色；若需要严格对应实体拼豆，请导入品牌色号表。")
    elif palette_mode == "自动从原画取色":
        auto_count = st.slider("自动颜色数量", 2, 64, 24, 1)
        st.caption("自动色没有实体品牌色号，适合先设计，再人工选购近似色。")
    else:
        st.download_button(
            "下载 CSV 色号表模板",
            palette_template_csv(),
            "palette_template.csv",
            "text/csv",
            width="stretch",
        )
        custom_file = st.file_uploader("导入色号表 CSV", type=["csv"], key="palette_file")
        if custom_file is not None:
            try:
                custom_palette = parse_palette_csv(custom_file.getvalue())
                brands = sorted({color.brand for color in custom_palette})
                selected_brands = st.multiselect("选择要使用的品牌", brands, default=brands)
                st.caption(f"已识别 {len(custom_palette)} 个颜色、{len(brands)} 个品牌。")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()
    st.subheader("图纸输出")
    show_codes = st.checkbox("格子内显示色号", value=True)
    cell_size = st.slider("PNG 单格大小（像素）", 18, 48, 30, 2)
    pdf_layout_label = st.selectbox("A4 每页网格", ["25 × 35（最清楚）", "30 × 40", "40 × 55（最省纸）"])
    pdf_layout = {
        "25 × 35（最清楚）": (25, 35),
        "30 × 40": (30, 40),
        "40 × 55（最省纸）": (40, 55),
    }[pdf_layout_label]

    generate = st.button("生成拼豆图", type="primary", width="stretch", disabled=source_image is None)

if source_image is None:
    st.info("先上传一张原画，左侧设置会自动启用。")
    st.stop()

if generate:
    try:
        prepared = prepare_image(
            source_image,
            int(columns),
            int(rows),
            fit_mode,
            parse_hex(background_hex),
            float(contrast),
            float(saturation),
        )
        if palette_mode == "内置通用色库":
            palette = builtin_palette(palette_name)
        elif palette_mode == "自动从原画取色":
            palette = extract_palette(prepared, int(auto_count))
        else:
            if not custom_palette:
                raise ValueError("请先导入有效的 CSV 色号表。")
            palette = [color for color in custom_palette if color.brand in selected_brands]
            if not palette:
                raise ValueError("请至少选择一个包含有效颜色的品牌。")

        indices = map_to_palette(prepared, palette)
        preview = indices_to_image(indices, palette, scale=max(4, min(16, 800 // max(int(columns), int(rows)))))
        grid = render_grid(indices, palette, int(cell_size), show_codes)
        usage = usage_rows(indices, palette)
        grid_bytes = image_png(grid)
        preview_bytes = image_png(preview)
        csv_bytes = usage_csv(usage)
        pdf_bytes = make_pdf(indices, palette, float(bead_size), pdf_layout, show_codes)
        xlsx_bytes = make_xlsx(indices, palette, show_codes)
        settings = {
            "columns": int(columns), "rows": int(rows), "fit_mode": fit_mode,
            "bead_size_mm": float(bead_size), "palette_mode": palette_mode,
            "palette_name": palette_name if palette_mode == "内置通用色库" else None,
            "selected_brands": selected_brands, "show_codes": show_codes,
            "contrast": float(contrast), "saturation": float(saturation),
            "background": background_hex, "pdf_cells_per_page": list(pdf_layout),
        }
        bundle = make_bundle(grid_bytes, preview_bytes, csv_bytes, pdf_bytes, palette, settings, xlsx_bytes=xlsx_bytes)
        st.session_state["result"] = {
            "preview": preview_bytes, "grid": grid_bytes, "csv": csv_bytes,
            "pdf": pdf_bytes, "xlsx": xlsx_bytes, "bundle": bundle, "usage": usage,
            "columns": int(columns), "rows": int(rows), "bead_size": float(bead_size),
        }
    except Exception as exc:
        st.error(f"生成失败：{exc}")

result = st.session_state.get("result")

left, right = st.columns(2, gap="large")
with left:
    st.subheader("处理前")
    st.image(source_image, width="stretch")
with right:
    st.subheader("处理后")
    if result:
        st.image(result["preview"], width="stretch")
    else:
        st.info("调整设置后点击“生成拼豆图”。")

if result:
    st.divider()
    total = result["columns"] * result["rows"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("网格", f"{result['columns']} × {result['rows']}")
    m2.metric("拼豆总数", f"{total:,}")
    m3.metric("实际使用颜色", f"{len(result['usage'])}")
    m4.metric(
        "预计成品尺寸",
        f"{result['columns'] * result['bead_size'] / 10:.1f} × {result['rows'] * result['bead_size'] / 10:.1f} cm",
    )

    tab_grid, tab_usage, tab_download = st.tabs(["彩色网格图", "色号与数量", "下载"])
    with tab_grid:
        st.image(result["grid"], caption="深色线每 5 颗出现一次；顶部与左侧为坐标。", width="stretch")
    with tab_usage:
        st.markdown(legend_html(result["usage"]), unsafe_allow_html=True)
    with tab_download:
        st.success("图纸已生成，可以分别下载，也可以下载完整 ZIP。")
        d1, d2 = st.columns(2)
        with d1:
            st.download_button("下载完整图纸包（ZIP）", result["bundle"], "bead_pattern_package.zip", "application/zip", type="primary", width="stretch")
            st.download_button("下载彩色网格图（PNG）", result["grid"], "pattern_grid.png", "image/png", width="stretch")
            if "xlsx" in result:
                st.download_button("下载像素单元格图（Excel）", result["xlsx"], "bead_pattern.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
                st.caption("每颗拼豆对应一个单元格，从 A1 开始；附生成时的色号用量统计。格内色号沿用生成设置。")
            else:
                st.info("请重新生成拼豆图，以启用新增的 Excel 下载。")
        with d2:
            st.download_button("下载 A4 分页图纸（PDF）", result["pdf"], "printable_pattern.pdf", "application/pdf", width="stretch")
            st.download_button("下载色号数量表（CSV）", result["csv"], "bead_usage.csv", "text/csv", width="stretch")
