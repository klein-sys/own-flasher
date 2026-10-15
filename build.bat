@echo off
setlocal
title FlashDock v1.5.0 — Automated Release Builder
cd /d "%~dp0"
set PYTHONUTF8=1

echo ============================================================================
echo  FlashDock v1.5.0 — Applying Hardening Hooks, Running Tests & Building EXE
echo ============================================================================
if exist "%~dp0.venv\Scripts\python.exe" (
    set "PY_CMD=%~dp0.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

"%PY_CMD%" scripts/apply_v150_hardening.py
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%

"%PY_CMD%" scripts/release_build.py
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Release build failed.
    pause
    exit /b %ERRORLEVEL%
)
echo [OK] FlashDock v1.5.0 release build complete.
