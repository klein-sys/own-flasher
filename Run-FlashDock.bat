@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0dist\FlashDock_Dist\FlashDock.exe" goto repository
if exist "%~dp0FlashDock.exe" goto extracted
echo [ERROR] FlashDock.exe was not found. Extract the full Windows ZIP or run build.bat from the source checkout.
exit /b 1

:repository
start "" /d "%~dp0dist\FlashDock_Dist" "%~dp0dist\FlashDock_Dist\FlashDock.exe" %*
exit /b

:extracted
start "" /d "%~dp0." "%~dp0FlashDock.exe" %*
exit /b
