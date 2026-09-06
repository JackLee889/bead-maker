# Codex project guide

## Product

This repository contains a local-first Streamlit bead-pattern generator. Keep all image conversion and export processing local; do not add an external image-processing API unless the user explicitly requests it.

The visible UI and user documentation are Chinese. Keep user-facing additions in concise Simplified Chinese.

## Architecture

- `app.py`: Streamlit UI, session state, orchestration, and downloads.
- `core.py`: image loading, resizing, palette matching, PNG/CSV/PDF/ZIP output.
- `excel_export.py`: XLSX output; one mapped bead pixel must equal exactly one worksheet cell starting at A1.
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

Do not commit `.venv`, caches, generated previews, PDFs, spreadsheets, or ZIP archives.
