@echo off
setlocal
cd /d "%~dp0"
set "CHECK_PY=import sys,sysconfig; sys.exit(not (sys.version_info[:2] in [(3, minor) for minor in range(10, 15)] and sysconfig.get_platform() == 'win-amd64'))"
if exist ".venv\Scripts\python.exe" goto install

for %%V in (3.14 3.13 3.12 3.11 3.10) do (
    py -%%V -c "%CHECK_PY%" >nul 2>&1
    if not errorlevel 1 (
        py -%%V -m venv ".venv"
        if errorlevel 1 exit /b 1
        goto install
    )
)

python -c "%CHECK_PY%" >nul 2>&1
if errorlevel 1 goto unsupported
python -m venv ".venv"
if errorlevel 1 exit /b 1

:install
".venv\Scripts\python.exe" -c "%CHECK_PY%" >nul 2>&1
if errorlevel 1 goto unsupported
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo [OK] FlashDock is ready. Run Run-Via-Python.bat to launch from source.
exit /b 0

:unsupported
echo [ERROR] FlashDock needs 64-bit Python 3.10 through 3.14 for Windows x64.
echo Install Python from https://www.python.org/downloads/windows/ and rerun this script.
echo If .venv already exists, rename it before rerunning setup with the supported Python.
exit /b 1
