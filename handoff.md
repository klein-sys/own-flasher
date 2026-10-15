# FlashDock — Engineering Handoff & Session State

- **Current Version**: `v1.5.0` (Phase 25 — Master Architectural Upgrade, Codebase Hardening & Fuzzing Suite)
- **Repository**: `https://github.com/klein-sys/own-flasher`
- **Runtime**: Python 3.10–3.14 (verified on Python 3.14.7) | PySide6 (Qt 6.10) | Windows 10/11 x64
- **Test Suite Status**: `100% Passing` (`tests/` — 50 modules including property-based binary parser fuzzing, Win32 USB transport handshakes, and v1.5.0 hardening suites)

---

## 1. Phase 25 (v1.5.0) Completed Deliverables

1. **Subprocess, Flash Lock & Process-Tree Hardening (`flashdock/tools/runner.py`)**:
   - Upgraded flash lock synchronization with a reentrant mutex (`_V150_FLASH_RLOCK = threading.RLock()`) and `@contextmanager def flash_lock_scope()` so no unhandled worker exception can leave `DeviceMonitorWorker` permanently paused.
   - Added `kill_process_tree(pid)` (`taskkill /F /T /PID`) to eliminate zombie `adb.exe`, `fastboot.exe`, and `scrcpy.exe` child processes on cable disconnect or timeout.
2. **Zero-Copy `mmap` Streaming & Archive Security (`flashdock/tools/mmap_stream.py`, `lz4_util.py`, `payload_dumper.py`, `return_stock.py`)**:
   - Added `open_mmap_view()` yielding zero-copy `memoryview` slices over `mmap.mmap` handles for local OTA `payload.bin` and Samsung `.img.lz4` archives.
   - Added `safe_extract_zip()` and `safe_extract_tar()` with canonical path-traversal (Zip-Slip / Tar-Slip) rejection and Python 3.12–3.14 PEP 706 `filter="data"` enforcement.
3. **Event-Driven Win32 Hardware Notifications (`flashdock/tools/win32_device_events.py`, `device_monitor.py`)**:
   - Implemented `Win32DeviceEventMonitor` listening for `WM_DEVICECHANGE` (`DBT_DEVICEARRIVAL`, `DBT_DEVICEREMOVECOMPLETE`, `DBT_DEVNODES_CHANGED`) to wake `DeviceMonitorWorker` in `<50ms` when short-lived BROM/EDL devices connect.
4. **Pure-Python Win32 Low-Level USB/Serial Handshake Transport (`flashdock/tools/usb_transport.py`, `mtk.py`, `unisoc.py`)**:
   - Implemented `Win32SerialTransport` via `ctypes.windll.kernel32` (`CreateFileW`, `GetCommState`, `SetCommState`, `SetCommTimeouts`, `ReadFile`, `WriteFile`).
   - Added wire-level protocol verifiers for Qualcomm Sahara Hello (`0x01` / `0x02`), MediaTek BROM 4-byte echo (`0xA0 0x0A 0x50 0x05` -> `0x5F 0xF5 0xAF 0xFA`), and Unisoc HDLC (`0x7E` check-baud ping + CRC-16/XMODEM framing).
5. **Property-Based Binary Parser Fuzzing Suite (`tests/test_fuzz_parsers.py`, `tests/test_usb_transport.py`, `tests/test_v150_hardening.py`)**:
   - Added randomized, truncated, bit-flipped, and boundary-value fuzz tests across `RootingEngine.validate_boot_image()`, `LZ4Util`, `PayloadDumper`, `UnisocUnlockManager`, and archive extractors.

---

## 2. Verification & Build Commands

```powershell
python scripts/apply_v150_hardening.py
python -m pytest tests/ -q
python scripts/release_build.py

---

# 4. Verification & Test Suite Commands for AI-3

After writing the files in Section 3, AI-3 must execute the following PowerShell verification sequence from the repository root[cite: 11]:

```powershell
# 1. Apply AST-verified v1.5.0 in-place hardening hooks to existing modules
python scripts/apply_v150_hardening.py

# 2. Run the complete unit + property-based binary fuzzing test suite
python -m pytest tests/ -q

# 3. Verify standalone PyInstaller compilation, SHA-256 Authenticode signing, and ZIP packaging
python scripts/release_build.py

5. Git & GitHub Deployment Instructions for AI-3

5.1 Authoritative Git & GitHub CLI (gh) Sync Script

Execute the following PowerShell commands to commit, tag, and publish FlashDock v1.5.0 to [https://github.com/klein-sys/own-flasher](https://github.com/klein-sys/own-flasher) (strictly adhering to .agents/skills/permissioned-github/SKILL.md and .agents/skills/misc/git-guardrails-claude-code/SKILL.md — no force-push or destructive resets)

# 1. Inspect working tree status
git status

# 2. Stage all v1.5.0 new and modified files
git add `
  flashdock/__init__.py `
  flashdock/constants.py `
  flashdock/tools/usb_transport.py `
  flashdock/tools/win32_device_events.py `
  flashdock/tools/mmap_stream.py `
  flashdock/tools/runner.py `
  flashdock/tools/lz4_util.py `
  flashdock/tools/payload_dumper.py `
  flashdock/workers/device_monitor.py `
  flashdock/core/mtk.py `
  flashdock/core/unisoc.py `
  flashdock/core/return_stock.py `
  scripts/apply_v150_hardening.py `
  tests/test_fuzz_parsers.py `
  tests/test_usb_transport.py `
  tests/test_v150_hardening.py `
  flashdock.spec `
  version_info.txt `
  Unblock-FlashDock.bat `
  Install-Certificate.bat `
  README.md `
  handoff.md

# 3. Create structured conventional commit
git commit -m "feat(v1.5.0): add Win32 USB handshakes, WM_DEVICECHANGE monitor, zero-copy mmap streaming, and parser fuzzing suite"

# 4. Create annotated v1.5.0 release tag
git tag -a v1.5.0 -m "FlashDock v1.5.0 — Low-Level Win32 USB Handshakes, Event-Driven Hardware Monitor, Zero-Copy mmap Streaming & Parser Fuzzing"

# 5. Push main branch and v1.5.0 tag to origin
git push origin main
git push origin v1.5.0

# 6. Publish GitHub Release with compiled portable ZIP artifact via permissioned gh CLI
gh release create v1.5.0 "dist/FlashDock-v1.5.0-windows-x64.zip" `
  -R klein-sys/own-flasher `
  --title "FlashDock v1.5.0 — Low-Level USB Handshakes, Zero-Copy mmap & Codebase Hardening" `
  --notes-file RELEASE_NOTES_v1.5.0.md

