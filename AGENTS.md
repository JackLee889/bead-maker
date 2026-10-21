# Codex project guide

## Product

This repository contains a local-first Streamlit bead-pattern generator. Keep all image conversion and export processing local; do not add an external image-processing API unless the user explicitly requests it.

The UI supports Simplified Chinese, Traditional Chinese, English and Japanese. Keep translations local in `locales/`, preserve format placeholders, and update all four catalogs for user-facing additions. Primary developer documentation remains concise Simplified Chinese. Never translate imported color codes, brands or names as UI text.

## Architecture

- `app.py`: Streamlit UI, session state, orchestration, and downloads.
- `core.py`: image loading, resizing, palette matching, PNG/CSV/PDF/ZIP output.
- `excel_export.py`: XLSX output; one mapped bead pixel must equal exactly one worksheet cell starting at A1.
- `i18n.py`, `locales/`: translations, language rules and localizable errors.
- `language_ui.py`, `frontend/language.js`: language controls, browser preferences and browser-only IP region lookup.
- `localized_exports.py`: refresh export text from existing indices when language changes.
- `grid_viewer.py`, `frontend/grid_viewer.js`, `frontend/grid_viewer.css`: local grid preview and browser zoom/pan dialog; keep viewing changes separate from generation and exports.
- `test_core.py`, `test_excel.py`, `test_app.py`: core, Excel, and end-to-end regression tests.

## Setup and run

Windows users can run `start_windows.bat`. The equivalent manual setup is:

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe -m streamlit run app.py
```

On macOS/Linux, use `.venv/bin/python` instead.

## Required verification

Run from the repository root after code changes:

```bash
python test_core.py
python -m unittest test_excel -v
python test_app.py
```

For UI or startup changes, also launch Streamlit and verify `/_stcore/health` returns `ok`.

Preserve these invariants:

- `indices` is the single source of truth for all rendered/exported outputs.
- Usage counts sum to `rows * columns`.
- Excel keeps leading zeros and treats imported labels as literal text, never formulas.
- ZIP export contains the same standalone XLSX bytes.
- Existing local workflows remain usable without an account, database, or internet after dependencies are installed.
- Language switches preserve the uploaded image, settings, indices, RGB values, codes and quantities. IP lookup failure must not block generation; `BEAD_MAKER_IP_LANGUAGE=0` disables IP queries.

Do not commit `.venv`, caches, generated previews, PDFs, spreadsheets, or ZIP archives.
