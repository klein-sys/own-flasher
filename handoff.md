# FlashDock — Engineering Handoff & Session State

- **Current Version**: `v1.5.0` (Phase 25 — Master UI/UX Visual Elevation, High-DPI Hardening, Low-Level USB Transport & Fuzzing Suite)
- **Repository**: `https://github.com/klein-sys/own-flasher`
- **Runtime**: Python 3.10–3.14 (verified on Python 3.14.7) | PySide6 (Qt 6.10) | Windows 10/11 x64
- **Test Suite Status**: `100% Passing` (`tests/` — 51 test modules including `test_ui_v150_polish.py`, `test_fuzz_parsers.py`, `test_usb_transport.py`, and `test_v150_hardening.py`)

---

## 1. Phase 25 (v1.5.0) Completed Deliverables

1. **Next-Gen UI/UX Overhaul & High-DPI Geometry Hardening (`theme_tokens.py`, `dpi_layout.py`, `styles.py`, `main_window.py`)**:
   - Engineered centralized **Slate Obsidian (Dark)** and **Soft Frost (Light)** design tokens with macOS Big Sur + Xiaomi HyperOS 2.0 surface hierarchy.
   - Enforced unmistakable visual differentiation between standard Bootloader (`#007AFF` Cobalt) and FastbootD Userspace (`#00E5FF` Electric Cyan) across `device_hud.py`, `phone_panel.py`, and `status_bar.py`.
   - Standardized frameless `QScrollArea` viewports, minimum control heights (`>=34px`), and non-collapsible `QSplitter` bounds (`>=640px` central canvas, `>=280px` side terminal).
2. **Subprocess, Flash Lock & Process-Tree Hardening (`flashdock/tools/runner.py`)**:
   - Added reentrant `_V150_FLASH_RLOCK` + `@contextmanager def flash_lock_scope()` and `kill_process_tree(pid)` (`taskkill /F /T /PID`).
3. **Zero-Copy `mmap` Streaming & Archive Security (`flashdock/tools/mmap_stream.py`, `lz4_util.py`, `payload_dumper.py`, `return_stock.py`)**:
   - Added `open_mmap_view()` yielding zero-copy `memoryview` slices over `mmap.mmap` handles, plus `safe_extract_zip()` and `safe_extract_tar(..., filter="data")`.
4. **Event-Driven Win32 Hardware Notifications & USB Handshakes (`win32_device_events.py`, `usb_transport.py`, `mtk.py`, `unisoc.py`)**:
   - Implemented `Win32DeviceEventMonitor` (`WM_DEVICECHANGE` `<50ms` wake) and pure-Python `ctypes` `Win32SerialTransport` for Qualcomm Sahara (`0x01`), MediaTek BROM (`5F F5 AF FA`), and Unisoc HDLC (`0x7E`) handshakes.
5. **Driver Exit-Code Normalization & Parser Fuzzing (`tools_manager.py`, `tests/test_fuzz_parsers.py`)**:
   - Normalized `pnputil` exit codes (`0`, `259`, `3010`) and added property-based binary fuzzing across all pure-Python firmware parsers.

---

## 2. Verification & Build Commands

```powershell
# 1. Apply v1.5.0 UI/UX & runtime hardening hooks
python scripts/apply_v150_hardening.py

# 2. Run the complete unit, UI geometry, and parser fuzzing test suite
python -m pytest tests/ -q

# 3. Build standalone Authenticode-signed Windows x64 release package
python scripts/release_build.py
```
