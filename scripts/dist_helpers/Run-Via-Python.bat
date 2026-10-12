@echo off
setlocal
title FlashDock Direct Python Launcher
cd /d "%~dp0"

echo [FlashDock] Launching FlashDock via Python interpreter...
where python >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3.10+ was not found in your system PATH.
    echo Please install Python from https://www.python.org/ or use FlashDock.exe.
    pause
    exit /b 1
)

python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] FlashDock exited with status code %ERRORLEVEL%.
    pause
)
