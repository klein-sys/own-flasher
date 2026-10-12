@echo off
setlocal
title FlashDock Workstation Launcher
cd /d "%~dp0"

echo [FlashDock] Initializing workstation launcher...
rem Unblock all binaries in this directory to clear Windows Mark-of-the-Web (Zone.Identifier)
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Path '%~dp0' -Recurse -ErrorAction SilentlyContinue | Unblock-File" >nul 2>&1

if exist "FlashDock.exe" (
    start "" "%~dp0FlashDock.exe" %*
    exit /b 0
) else (
    echo [ERROR] FlashDock.exe not found in %~dp0
    pause
    exit /b 1
)
