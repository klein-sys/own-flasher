@echo off
setlocal
title FlashDock Security Certificate Installer
cd /d "%~dp0"

echo ======================================================================
echo   FlashDock Security Certificate Installer (Windows Smart App Control)
echo ======================================================================
echo.
echo Installing FlashDock Workstation Authority certificate to your local
echo trusted root store. This enables Windows 11 Smart App Control and
echo Microsoft Defender SmartScreen to verify FlashDock's digital signature.
echo.

set CERT_FILE=FlashDock-Security-Certificate.cer

if not exist "%CERT_FILE%" (
    echo [ERROR] Certificate file not found: %CERT_FILE%
    echo Please ensure %CERT_FILE% is present in the same directory.
    pause
    exit /b 1
)

echo [*] Adding certificate to Current User Trusted Publishers...
certutil -user -addstore "TrustedPublisher" "%CERT_FILE%"

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] FlashDock Security Certificate has been installed and trusted!
    echo Windows Smart App Control will now allow FlashDock.exe to execute without blocks.
    echo.
) else (
    echo.
    echo [WARNING] Current user store install exited with code %ERRORLEVEL%.
    echo Attempting PowerShell certificate import...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Import-Certificate -FilePath '%CERT_FILE%' -CertStoreLocation 'Cert:\CurrentUser\TrustedPublisher'"
    if %ERRORLEVEL% EQU 0 (
        echo [SUCCESS] PowerShell import completed successfully!
    ) else (
        echo [ERROR] Failed to import certificate. You may need to right-click this script and 'Run as Administrator'.
    )
)

echo.
pause
