@echo off
setlocal
title FlashDock SmartScreen / Mark-of-the-Web Unblocker
cd /d "%~dp0"

echo ======================================================================
echo   FlashDock Mark-of-the-Web (Zone.Identifier) Unblocker
echo ======================================================================
echo.
echo Removing download flags (Mark-of-the-Web) from all files in this folder...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Path '%~dp0' -Recurse | Unblock-File; Write-Host '[OK] All files unblocked successfully!' -ForegroundColor Green"

echo.
echo You can now launch FlashDock.exe normally without SmartScreen warnings.
echo.
pause
