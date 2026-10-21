#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "Python 3.10 or newer is required."
  exit 1
}

if [ ! -x ".venv/bin/python" ]; then
  echo "[1/3] Creating Python environment..."
  python3 -m venv .venv
fi

echo "[2/3] Installing or checking dependencies..."
.venv/bin/python -m pip install -r requirements.txt

echo "[3/3] Opening Bead Pattern Maker..."
echo "Local address: http://127.0.0.1:8501"
echo "Press Ctrl+C to stop the application."
.venv/bin/python -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
