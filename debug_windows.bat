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

echo [2/3] Installing application and debugging dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt || goto :error

echo [3/3] Starting in debug mode...
echo Web page: http://127.0.0.1:8501
echo Debug attach: 127.0.0.1:5678
echo You can use the VS Code configuration "Attach to debug_windows.bat".
echo Closing this window will stop the application.
".venv\Scripts\python.exe" -Xfrozen_modules=off -m debugpy --listen 127.0.0.1:5678 -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501 --server.headless false --browser.gatherUsageStats false
goto :eof

:python_missing
echo Python was not found. Install Python 3.10 or newer and select "Add python.exe to PATH".
pause
exit /b 1

:python_version
echo Python 3.10 or newer is required.
pause
exit /b 1

:error
echo Debug startup failed. Review the error above, then run this file again.
pause
exit /b 1
