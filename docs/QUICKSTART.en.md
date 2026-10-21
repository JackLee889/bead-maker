# Bead Pattern Maker

The interface supports English, Simplified Chinese, Traditional Chinese and Japanese. Choose a language at the top of the sidebar, or open `http://127.0.0.1:8501/?lang=en`.

1. On Windows, install Python 3.10 or later and run `start_windows.bat` from the extracted app folder. Keep its terminal open. Dependencies need internet access on first installation.
2. Upload an image, choose the bead dimensions and a generic, brand, extracted or imported palette.
3. Click **Generate pattern**. Review the image and color counts, then download PNG, CSV, Excel, PDF or the complete ZIP.

One bead equals one Excel cell, starting at A1. Brand color codes and imported names are kept exactly as supplied. All image processing and exports run on the computer hosting the app.

**Automatic language:** The browser looks up its IP region through Country.is. Mainland China selects Simplified Chinese, Taiwan/Hong Kong/Macao select Traditional Chinese, Japan selects Japanese, and other regions select English. If the lookup fails, the browser language is used. Images are never sent with the lookup.

**Manual language:** Your choice overrides IP detection and is remembered in this browser and the `lang` URL parameter. Switching language keeps the image, settings, bead colors and counts; export text updates automatically. Select **Auto (IP)** to return to automatic mode.

**Offline use:** Set `BEAD_MAKER_IP_LANGUAGE=0` before starting to disable IP queries. All translations and brand palettes are included locally. Modern PDF readers with CJK font support are needed for Chinese and Japanese PDF text.

[中文安装说明](../README.md) · [繁體中文](QUICKSTART.zh-TW.md) · [日本語](QUICKSTART.ja.md)
