from io import BytesIO
import zipfile

from PIL import Image, ImageDraw
from openpyxl import load_workbook
from streamlit.testing.v1 import AppTest


def sample_png(solid: str | None = None) -> bytes:
    image = Image.new("RGB", (160, 100), solid or "#F3EFE7")
    if solid is None:
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 79, 99), fill="#D33242")
        draw.ellipse((45, 15, 135, 92), fill="#2B68B8")
        draw.polygon([(80, 5), (150, 55), (95, 95)], fill="#F4C542")
    output = BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_builtin_palette() -> None:
    app = AppTest.from_file("app.py", default_timeout=60).run()
    assert not app.exception
    app.get("file_uploader")[0].upload(
        "qa_source.png", sample_png(), "image/png"
    ).run(timeout=60)
    app.number_input[0].set_value(40)
    app.selectbox[0].set_value("完整留白")
    app.selectbox[1].set_value("通用 32 色")
    app.selectbox[2].set_value("30 × 40")
    app.run(timeout=60)
    app.button[0].click().run(timeout=60)
    assert not app.exception
    assert not app.error
    result = app.session_state["result"]
    assert (result["columns"], result["rows"]) == (40, 25)
    assert result["grid"].startswith(b"\x89PNG")
    assert result["preview"].startswith(b"\x89PNG")
    assert result["pdf"].startswith(b"%PDF")
    assert result["bundle"].startswith(b"PK")
    assert result["csv"].startswith(b"\xef\xbb\xbf")
    assert sum(item["count"] for item in result["usage"]) == 1000
    assert result["xlsx"].startswith(b"PK")
    assert len(app.get("download_button")) == 5
    excel = load_workbook(BytesIO(result["xlsx"]))
    assert (excel["拼豆图"].max_row, excel["拼豆图"].max_column) == (25, 40)
    with zipfile.ZipFile(BytesIO(result["bundle"])) as archive:
        assert archive.read("bead_pattern.xlsx") == result["xlsx"]


def test_custom_palette() -> None:
    app = AppTest.from_file("app.py", default_timeout=60).run()
    app.get("file_uploader")[0].upload(
        "solid.png", sample_png("#CC2233"), "image/png"
    ).run(timeout=60)
    app.radio[0].set_value("导入品牌/自定义色号表").run(timeout=60)
    palette_csv = (
        b"brand,code,name,hex\n"
        b"BrandX,X01,Red,#CC2233\n"
        b"BrandX,X02,White,#FFFFFF\n"
        b"BrandY,Y01,Black,#000000\n"
    )
    app.get("file_uploader")[1].upload(
        "palette.csv", palette_csv, "text/csv"
    ).run(timeout=60)
    app.multiselect[0].set_value(["BrandX"]).run(timeout=60)
    app.button[-1].click().run(timeout=60)
    assert not app.exception
    assert not app.error
    assert {item["brand"] for item in app.session_state["result"]["usage"]} == {
        "BrandX"
    }
    excel = load_workbook(BytesIO(app.session_state["result"]["xlsx"]))
    assert excel["拼豆图"]["A1"].value == "X01"


def test_uniform_auto_palette() -> None:
    app = AppTest.from_file("app.py", default_timeout=60).run()
    app.get("file_uploader")[0].upload(
        "solid.png", sample_png("#336699"), "image/png"
    ).run(timeout=60)
    app.radio[0].set_value("自动从原画取色").run(timeout=60)
    app.button[0].click().run(timeout=60)
    assert not app.exception
    assert not app.error
    result = app.session_state["result"]
    usage = result["usage"]
    assert len(usage) == 1
    assert usage[0]["count"] == result["columns"] * result["rows"]
    app.checkbox[1].set_value(False).run(timeout=60)
    app.button[0].click().run(timeout=60)
    assert not app.exception
    assert not app.error
    excel = load_workbook(BytesIO(app.session_state["result"]["xlsx"]))
    assert excel["拼豆图"]["A1"].value is None
    assert excel["拼豆图"]["A1"].fill.patternType == "solid"


def main() -> None:
    test_builtin_palette()
    test_custom_palette()
    test_uniform_auto_palette()
    print("app end-to-end tests passed")


if __name__ == "__main__":
    main()
