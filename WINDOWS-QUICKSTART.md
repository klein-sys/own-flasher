# Run FlashDock on Windows

1. Download the Windows x64 ZIP and its SHA-256 checksum from the same GitHub release.
2. In PowerShell, run `Get-FileHash .\FlashDock-v1.7.4-windows-x64.zip -Algorithm SHA256` and compare the result with the published checksum.
3. Extract the entire ZIP into a folder you can write to. Open `FlashDock.exe` or `Run-FlashDock.bat` in that folder. Keep the `_internal` directory beside the executable.
4. If ADB or Fastboot is missing, open **Downloads, Drivers & Tools Manager → Platform-Tools & Daemon** and select **Download Google Platform-Tools**. You can also get the tools from [Android Developers](https://developer.android.com/tools/releases/platform-tools). A phone may require its manufacturer's Windows USB driver.

The Windows ZIP runs without a separate Python installation. FlashDock creates local settings in `%LOCALAPPDATA%\FlashDock` on first launch.

## If Smart App Control blocks the executable

The v1.7.4 executable is unsigned. `Run-FlashDock.bat` points to that same executable. Use the portable source launcher from the developer ZIP:

1. Extract `FlashDock-v1.7.4-developer.zip` into a separate folder.
2. Install supported 64-bit Python and run `Setup-FlashDock.bat` in that folder.
3. Open `Run-Via-Python.bat` from the same folder.

Setup and source launch were verified on Windows 11 x64. See the [developer setup guide](https://github.com/klein-sys/own-flasher/blob/main/DEVELOPER-SETUP.md) for details and [Microsoft's Smart App Control guidance](https://support.microsoft.com/en-us/windows/security/threat-malware-protection/smart-app-control-frequently-asked-questions) for publisher verification.

Get the current Windows and developer downloads from [GitHub Releases](https://github.com/klein-sys/own-flasher/releases/latest).
