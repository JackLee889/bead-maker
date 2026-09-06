import csv
import io

import numpy as np
from PIL import Image

from core import (
    builtin_palette,
    extract_palette,
    image_png,
    make_pdf,
    map_to_palette,
    parse_palette_csv,
    prepare_image,
    render_grid,
    usage_rows,
)


def main() -> None:
    image = Image.new("RGB", (160, 100), "white")
    pixels = np.asarray(image).copy()
    pixels[:, :80] = (205, 38, 43)
    pixels[25:75, 55:105] = (37, 88, 168)
    image = Image.fromarray(pixels)
    prepared = prepare_image(image, 32, 20)
    palette = builtin_palette("通用 64 色")
    indices = map_to_palette(prepared, palette)
    assert indices.shape == (20, 32)
    assert sum(item["count"] for item in usage_rows(indices, palette)) == 640
    assert image_png(render_grid(indices, palette, 22, True)).startswith(b"\x89PNG")
    assert make_pdf(indices, palette, 5.0, (25, 35), True).startswith(b"%PDF")

    custom = parse_palette_csv(
        "品牌,色号,名称,颜色\n测试,X1,红,#ff0000\n测试,X2,蓝,#0000ff\n".encode("utf-8")
    )
    assert [color.code for color in custom] == ["X1", "X2"]

    solid = prepare_image(Image.new("RGB", (20, 20), "#336699"), 10, 10)
    single_color_palette = extract_palette(solid, 8)
    assert len(single_color_palette) == 1
    single_indices = map_to_palette(solid, single_color_palette)
    assert single_indices.shape == (10, 10)
    assert np.all(single_indices == 0)
    print("core tests passed")


if __name__ == "__main__":
    main()
