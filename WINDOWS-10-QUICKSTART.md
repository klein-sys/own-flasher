# FlashDock v1.7.4 on Windows 10 Pro

Use **Windows 10 Pro 22H2, 64-bit**, on an Intel or AMD x64 PC. Open **Settings → System → About** to check the system type and use `winver` to check the Windows version. Windows 10 22H2 is build 19045. [Microsoft release information](https://learn.microsoft.com/en-us/windows/release-health/release-information)

## Run the Windows 10 ZIP

1. Download `FlashDock-v1.7.4-windows-10-x64.zip` and its matching checksum from the [v1.7.4 release](https://github.com/klein-sys/own-flasher/releases/tag/v1.7.4).
2. In PowerShell, run `Get-FileHash .\FlashDock-v1.7.4-windows-10-x64.zip -Algorithm SHA256` and compare it with the published Windows 10 checksum.
3. Choose **Extract All** and extract to a short, writable path, such as a `FlashDock` folder in Documents. Open `FlashDock.exe` from the extracted folder. Keep the `_internal` folder next to it.
4. If ADB or Fastboot is missing, use **Downloads, Drivers & Tools Manager → Platform-Tools & Daemon → Download Google Platform-Tools**. For a phone that Windows cannot recognize, check the cable and the phone maker’s USB driver. [Google Platform-Tools](https://developer.android.com/tools/releases/platform-tools)

The Windows 10 ZIP uses the same unsigned FlashDock executable and runtime as the general v1.7.4 Windows x64 ZIP. Python and Qt both document Windows 10 support for the versions used here. FlashDock falls back to its painted background when the Windows 11 native backdrop is unavailable. [Python on Windows](https://docs.python.org/3.14/using/windows.html#supported-windows-versions) · [Qt for Windows](https://doc.qt.io/qtforpython-6/overviews/qtdoc-windows.html) · [Microsoft DWM backdrop requirements](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute)

## If FlashDock does not open

- **A DLL or Qt platform plugin is missing.** Extract the whole ZIP again into a fresh folder and check that `FlashDock.exe` and `_internal` are side by side.
- **Windows blocks the unsigned executable.** Use the [developer ZIP](https://github.com/klein-sys/own-flasher/releases/download/v1.7.4/FlashDock-v1.7.4-developer.zip). With supported 64-bit Python installed, run `Setup-FlashDock.bat` and then `Run-Via-Python.bat`.
- **FlashDock opens but the phone is missing.** Start with read-only detection in Android, approve the USB debugging prompt on the phone, and check **Downloads, Drivers & Tools Manager** before trying a device operation.

The Windows 10 ZIP was checked for archive integrity and byte-for-byte agreement with the published v1.7.4 runtime. The release was built on Windows 11 x64. Native startup, USB drivers, and phone operations on Windows 10 still need a test on that system.
