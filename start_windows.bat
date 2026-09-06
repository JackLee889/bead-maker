@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON_EXE="
set "PYTHON_ARGS="
where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_EXE=py"
  set "PYTHON_ARGS=-3"
) else (
  where python >nul 2>nul
  if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE goto :python_missing
%PYTHON_EXE% %PYTHON_ARGS% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" || goto :python_version

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Creating Python environment...
  %PYTHON_EXE% %PYTHON_ARGS% -m venv .venv || goto :error
)
if not exist ".venv\Scripts\python.exe" (
  echo The local Python environment is incomplete.
  goto :error
)

echo [2/3] Installing or checking dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error

echo [3/3] Opening Bead Pattern Maker...
echo Local address: http://127.0.0.1:8501
echo Closing this window will stop the application.
".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
goto :eof

:python_missing
echo.
echo Python was not found. Install Python 3.10 or newer first:
echo https://www.python.org/downloads/windows/
echo During installation, select "Add python.exe to PATH".
pause
exit /b 1

:python_version
echo.
echo Python 3.10 or newer is required. Please upgrade Python and try again.
pause
exit /b 1

:error
echo.
echo Local deployment failed. Review the error above, then run this file again.
pause
exit /b 1
