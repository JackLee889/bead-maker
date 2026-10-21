import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image, ImageDraw, ImageOps
from pypdf import PdfReader
from pypdf.generic import ContentStream
from brand_palettes import BRAND_PALETTES, DATA_DIR, load_brand_palette
from test_i18n import I18nTests

from core import (
    BeadColor,
    MAX_PALETTE_COLORS,
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


class CoreRegressionTests(unittest.TestCase):
    def test_detail_controls_preserve_flat_colours_and_old_default(self):
        flat = Image.new("RGB", (180, 120), (83, 142, 201))
        for fit_mode in ("裁剪填满", "完整留白", "拉伸"):
            prepared = prepare_image(flat, 30, 20, fit_mode, line_strength=1, sharpness=1)
            self.assertEqual(prepared.size, (30, 20))
            self.assertTrue(np.all(np.asarray(prepared) == (83, 142, 201)))
        sample = flat.copy()
        ImageDraw.Draw(sample).ellipse((20, 20, 100, 100), fill="black")
        old = ImageOps.fit(sample, (30, 20), method=Image.Resampling.LANCZOS, centering=(.5, .5))
        self.assertTrue(np.array_equal(np.asarray(prepare_image(sample, 30, 20)), np.asarray(old)))
        for values in ((-1, 0), (0, 2), (float("nan"), 0)):
            with self.assertRaises(ValueError):
                prepare_image(flat, 30, 20, line_strength=values[0], sharpness=values[1])

    def test_thin_line_gets_darker_without_polluting_background(self):
        source = Image.new("RGB", (400, 400), "white")
        ImageDraw.Draw(source).line((100, 202, 300, 202), fill=(30, 30, 30), width=2)
        plain = np.asarray(prepare_image(source, 40, 40))
        enhanced = np.asarray(prepare_image(source, 40, 40, line_strength=.65))
        self.assertLess(enhanced[19:22, 12:28].mean(), plain[19:22, 12:28].mean())
        self.assertTrue(np.all(enhanced[:10] == 255))
        self.assertTrue(np.all(enhanced >= 0))

    def test_palette_limits_and_single_color_csv(self):
        header = "brand,code,name,hex\n"
        entry = "Test,001,Red,#f00\n"
        single = parse_palette_csv((header + entry).encode())
        self.assertEqual(single[0].code, "001")
        self.assertEqual(single[0].rgb, (255, 0, 0))
        self.assertEqual(len(parse_palette_csv((header + entry * MAX_PALETTE_COLORS).encode())), 512)
        with self.assertRaisesRegex(ValueError, "512"):
            parse_palette_csv((header + entry * (MAX_PALETTE_COLORS + 1)).encode())
        with self.assertRaisesRegex(ValueError, "512"):
            map_to_palette(Image.new("RGB", (1, 1)), single * (MAX_PALETTE_COLORS + 1))
        with self.assertRaises(ValueError):
            parse_palette_csv(header.encode())

    def test_pdf_partial_tiles_keep_scale_and_cover_every_bead(self):
        indices = np.zeros((38, 28), dtype=np.int16)
        palette = [BeadColor("001", "Red", 255, 0, 0)]
        reader = PdfReader(io.BytesIO(make_pdf(indices, palette, 5, (25, 35))))
        self.assertEqual(len(reader.pages), 5)
        expected = [(25 * 35, "Columns 1-25, Rows 1-35"),
                    (3 * 35, "Columns 26-28, Rows 1-35"),
                    (25 * 3, "Columns 1-25, Rows 36-38"),
                    (3 * 3, "Columns 26-28, Rows 36-38")]
        sizes = set()
        for page, (count, title) in zip(reader.pages[1:], expected):
            self.assertIn(title, page.extract_text())
            operations = ContentStream(page.get_contents(), reader).operations
            rectangles = [args for args, op in operations if op == b"re"]
            self.assertEqual(len(rectangles), count)
            sizes.update((round(float(args[2]), 5), round(float(args[3]), 5)) for args in rectangles)
        self.assertEqual(len(sizes), 1)
        width, height = sizes.pop()
        self.assertEqual(width, height)

    def test_pdf_rejects_invalid_page_dimensions(self):
        for layout in ((0, 35), (-1, 2), (2.5, 3), (True, 3), (2,)):
            with self.subTest(layout=layout), self.assertRaises(ValueError):
                make_pdf(np.zeros((4, 4), dtype=int), [BeadColor("01", "Red", 255, 0, 0)], 5, layout)


class BrandPaletteTests(unittest.TestCase):
    def test_bundled_palettes_match_real_codes_and_exclude_unidentified_rows(self):
        expected = {
            "mard-221-github": (221, 0), "mard-291-github": (291, 0),
            "coco-291": (291, 0), "manman-278": (278, 0),
            "panpan-289": (285, 4), "mixiaowo-290": (286, 4),
        }
        for brand, versions in BRAND_PALETTES.items():
            for palette_id in versions:
                with self.subTest(palette=palette_id):
                    data = load_brand_palette(palette_id)
                    colors = data.select()
                    self.assertEqual((len(colors), len(data.excluded_codes)), expected[palette_id])
                    self.assertEqual(len({c.code for c in colors}), len(colors))
                    self.assertTrue(all(c.brand == brand and not c.code.startswith("UNKNOWN-") for c in colors))
                    mapped = map_to_palette(Image.new("RGB", (4, 4), colors[0].rgb), colors)
                    self.assertTrue(np.all(mapped == 0))
                    self.assertEqual(sum(r["count"] for r in usage_rows(mapped, colors)), 16)
        coco = load_brand_palette("coco-291").select()
        self.assertEqual((coco[0].code, coco[0].rgb), ("A01", (255, 255, 255)))

    def test_versions_share_base_colors_and_group_filter_preserves_codes(self):
        base = load_brand_palette("mard-221-github")
        extended = load_brand_palette("mard-291-github")
        base_map = {c.code: c.rgb for c in base.select()}
        extended_map = {c.code: c.rgb for c in extended.select()}
        self.assertEqual(base_map, {code: extended_map[code] for code in base_map})
        self.assertEqual(len(extended.select(["A"])), 26)
        self.assertEqual(extended.select(["A"])[0].code, "A1")
        self.assertEqual(extended.select([]), [])
        with self.assertRaises(ValueError):
            extended.select(["不存在"])
        with self.assertRaises(ValueError):
            load_brand_palette("../core")

    def test_invalid_or_changed_local_palette_is_detected(self):
        palette_id = "coco-291"
        original = json.loads((DATA_DIR / f"{palette_id}.json").read_bytes())
        old_hash = load_brand_palette(palette_id).sha256
        with tempfile.TemporaryDirectory() as directory, patch("brand_palettes.DATA_DIR", Path(directory)):
            path = Path(directory) / f"{palette_id}.json"
            with self.assertRaisesRegex(ValueError, "无法读取"):
                load_brand_palette(palette_id)
            for field, value in (("rgb", [999, 0, 0]), ("hex", "#000000"), ("code", "A02")):
                data = json.loads(json.dumps(original))
                data["colors"][0][field] = value
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, "数据无效"):
                    load_brand_palette(palette_id)
            original["colors"][0].update(rgb=[1, 2, 3], hex="#010203")
            path.write_text(json.dumps(original), encoding="utf-8")
            changed = load_brand_palette(palette_id)
            self.assertNotEqual(changed.sha256, old_hash)
            self.assertEqual(changed.select()[0].rgb, (1, 2, 3))


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
    unittest.main(verbosity=2)
