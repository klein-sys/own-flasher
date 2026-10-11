@echo off
REM FlashDock — Build script
REM Builds the FlashDock.exe using PyInstaller
REM Output: dist\FlashDock\FlashDock.exe

echo.
echo ===================================
echo   Building FlashDock...
echo ===================================
echo.

REM Ensure PyInstaller is installed
python -m pip show pyinstaller >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing PyInstaller...
    python -m pip install pyinstaller --quiet
)

REM Run tests first
echo Running tests...
python -m pytest tests/ -q
if %ERRORLEVEL% neq 0 (
    echo.
    echo !! Tests failed. Fix them before building.
    pause
    exit /b 1
)

echo.
echo Tests passed. Building EXE...
echo.

python -m PyInstaller flashdock.spec --noconfirm

if %ERRORLEVEL% equ 0 (
    echo.
    echo ===================================
    echo   Build successful!
    echo   EXE: dist\FlashDock\FlashDock.exe
    echo ===================================
    echo.
) else (
    echo.
    echo !! Build failed. Check the output above.
    echo.
)

pause
