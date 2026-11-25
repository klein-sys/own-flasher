@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\release_build.py %*
    exit /b
)
echo [ERROR] Run Setup-FlashDock.bat to create the project environment before building.
exit /b 1
