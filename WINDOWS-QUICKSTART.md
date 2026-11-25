# Run FlashDock on Windows

1. Download the Windows x64 ZIP and its SHA-256 checksum from the same GitHub release.
2. In PowerShell, run `Get-FileHash .\FlashDock-v1.7.4-windows-x64.zip -Algorithm SHA256` and compare the result with the published checksum.
3. Extract the entire ZIP into a folder you can write to. Open `FlashDock.exe` or `Run-FlashDock.bat` in that folder. Keep the `_internal` directory beside the executable.
4. If ADB or Fastboot is missing, open **Downloads, Drivers & Tools Manager → Platform-Tools & Daemon** and select **Download Google Platform-Tools**. You can also get the tools from [Android Developers](https://developer.android.com/tools/releases/platform-tools). A phone may require its manufacturer's Windows USB driver.

The Windows ZIP runs without a separate Python installation. FlashDock creates local settings in `%LOCALAPPDATA%\FlashDock` on first launch.

This executable is unsigned. If Windows blocks it, use the developer ZIP and follow [the source setup](https://github.com/klein-sys/own-flasher#option-b-run-from-source).

Get the current Windows and developer downloads from [GitHub Releases](https://github.com/klein-sys/own-flasher/releases/latest).
