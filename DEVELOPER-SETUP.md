# Continue FlashDock development on another PC

Use Windows x64 with Python 3.10–3.14 x64 installed and available through the Python launcher or on PATH. This release was built and tested with Python 3.14.7. Setup needs internet access to install Python dependencies.

1. Extract the developer ZIP into a writable folder. Use this folder as your project root.
2. Run `Setup-FlashDock.bat`. It creates a project-local `.venv` and installs `requirements.txt`.
3. Run `Run-Via-Python.bat` to open FlashDock from source.

From PowerShell in the project root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
.\build.bat
```

The build produces `dist\FlashDock_Dist\FlashDock.exe` with its runtime and a Windows ZIP with a SHA-256 checksum. See [the Windows quick start](WINDOWS-QUICKSTART.md) for Platform-Tools setup and launching the executable.

The developer ZIP is a source snapshot. To continue with Git history, clone the repository, then run the same setup from the checkout.

```powershell
git clone https://github.com/klein-sys/own-flasher.git
cd own-flasher
git checkout v1.7.4
.\Setup-FlashDock.bat
```

Source runs create a local `data\` directory. The developer ZIP carries project files only. Keep any old device backups, logs, settings, and credentials private.
