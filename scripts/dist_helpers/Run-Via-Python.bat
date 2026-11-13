@echo off
setlocal
title FlashDock Direct Python Launcher
cd /d "%~dp0"
set "FLASHDOCK_PYTHON_ARGS="

if exist ".venv\Scripts\python.exe" (
    set "FLASHDOCK_PYTHON=.venv\Scripts\python.exe"
    goto launch
)

py -3 -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    set "FLASHDOCK_PYTHON=py"
    set "FLASHDOCK_PYTHON_ARGS=-3"
    goto launch
)

python -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>&1
if not errorlevel 1 (
    set "FLASHDOCK_PYTHON=python"
    goto launch
)

echo [ERROR] Install Python 3.10 or later and the dependencies in requirements.txt.
pause
exit /b 1

:launch
echo [FlashDock] Launching from source...
"%FLASHDOCK_PYTHON%" %FLASHDOCK_PYTHON_ARGS% main.py
set "FLASHDOCK_EXIT=%ERRORLEVEL%"
if not "%FLASHDOCK_EXIT%"=="0" (
    echo.
    echo [ERROR] FlashDock exited with status code %FLASHDOCK_EXIT%.
    pause
)
exit /b %FLASHDOCK_EXIT%
