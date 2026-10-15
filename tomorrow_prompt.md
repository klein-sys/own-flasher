---
title: "FlashDock — Tomorrow's Comprehensive Execution Plan & Master Prompt (v1.4.0)"
type: execution-plan
status: ready
version: 1.4.0
date: 2026-10-14
tags:
  - flashdock
  - execution-prompt
  - audited-open-items-only
  - device-sync-fix
  - boot-patch-engine
  - driver-elevation-fix
  - unisoc-token-unlocker
  - payload-dumper
  - samsung-lz4-decompressor
  - fastbootd-hud
  - slot-switcher
  - non-scrolling-tools-canvas
  - interactive-workflow-guide
  - virtual-keypad-fix
  - thread-freezing-prevention
  - unicode-decode-shield
  - fastboot-bootloader-parser-fix
---

# FlashDock — Master Execution Prompt (Phase 24 / v1.4.0)

> **Audit Context & Status Verification:**
> Several earlier visual fixes from `fix 1.png` – `fix 15.png` have **already been resolved** in v1.3.0–v1.3.3:
> - ✅ `fix 1.png` (Reboot buttons clipped text): Already fixed with 2-row clean grid (`System`, `Recovery`, `Bootloader`, `More...`).
> - ✅ `fix 2.png` (Classic menu bar): Already hidden with `menu.setVisible(False)`.
> - ✅ `fix 3.png` (GSM brand bar plain text buttons): Already replaced with full vector SVG brand icons (Tecno, Infinix, itel, Samsung, Xiaomi, Huawei, OPPO, Vivo, Realme, Pixel, OnePlus, Motorola).
> - ✅ `fix 4.png` (Combobox width stretch): Already constrained with `setMaximumWidth(280)`.
> - ✅ `fix 7.png` (Unwanted horizontal scrollbar): Already suppressed with `ScrollBarAlwaysOff`.
> - ✅ `fix 9.png` (Partition checkboxes squashed): Already overhauled into a clean 2-column card grid in `backup_screen.py`.
> - ✅ `fix 10.png` ("scrcpv" typo & truncated buttons): Already corrected to "scrcpy" with widened layout.
> - ✅ `fix 11.png` (Logo badge box outline): Already rewritten with squircle gradient chip and borderless labels.
> - ✅ `fix 15.png` (`DeviceInfo` NameError in `reboot_switchboard.py`): Already imported and verified.
>
> The `/goal` below has been **deeply audited and enriched** with all runtime exceptions, UI thread freeze vectors, fastboot parser edge cases, and missing workstation superpowers.

---

```markdown
/goal

Execute the Comprehensive Workstation Superpower, Bugfix & Thread Safety Sprint for FlashDock (Phase 24 / v1.4.0):

### 1. Fix Device Synchronization & Blank Dropdown Bug (`fix 16.png`, `fix 17.png`, `fix 18.png`, `fix with 16.png`)
- **Problem**: Status bar shows `ADB (10944373AP103209) Connected` in green, but the Device Selector combobox at the top is completely blank/empty, and the Live HUD reports `• No Device Connected`.
- **Root Cause & Fixes**:
  1. In `flashdock/workers/device_monitor.py:472` & `488`: Fix `AttributeError` caused by calling `.get("mode")` and `.get("serial")` on `FastbootDevice` and `ADBDevice` dataclasses. Replace with direct attribute access (`fb_dev.serial`, `fb_dev.mode`, `adb_dev.serial`, `adb_dev.mode`, `adb_dev.model`).
  2. In `flashdock/ui/main_window.py:1567`: In `_on_hardware_device_connected()`, automatically trigger `self._refresh_device()` so `DeviceManager` immediately queries the connected device and updates the HUD, Phone Control Panel, and Device Selector combobox.
  3. In `flashdock/ui/main_window.py:1588`: In `_on_hardware_device_disconnected()`, reset the HUD, Phone Control Panel, and Device Selector cleanly to avoid displaying stale data.
  4. In `flashdock/ui/widgets/device_selector.py:60`: Initialize the combobox with `"No device connected"` placeholder on startup so it never renders as an empty black box before detection.

### 2. Fastboot & ADB Parser Hardening & Windows Unicode Decode Shield (`tools/`)
- **Problem 1 (Windows Unicode Decode Crash — `runner.py:161`)**: `subprocess.run(..., text=True)` on Windows defaults to the system ANSI code page (e.g. CP1252 or GBK). When Fastboot, ADB, or OEM tools output foreign characters, symbols, or binary progress bytes, Python throws an unhandled `UnicodeDecodeError` (which inherits from `ValueError`, bypassing `except OSError`).
  - *Fix*: Explicitly specify `encoding="utf-8", errors="replace"` in `runner.py:161` and catch `(OSError, ValueError)`.
- **Problem 2 (Fastboot `(bootloader) ` Prefix Parsing Bug — `fastboot.py:183, 203`)**: Almost all Android bootloaders prefix variable output with `(bootloader) ` (e.g., `(bootloader) unlocked: yes`, `(bootloader) product: raven`). In `fastboot.py:203`, `getvar_all()` filters out all lines where `line.startswith("(") `, causing it to drop EVERY single variable on real devices! In `fastboot.py:183`, `getvar()` fails `startswith(var + ":")` because of the `(bootloader)` prefix.
  - *Fix*: Strip `r"^\(bootloader\)\s*"` via regex or prefix strip before parsing in both `getvar()` and `getvar_all()`.
- **Problem 3 (Fastboot `--slot` Flag Placement — `fastboot.py:233`)**: Placing `--slot=a` after `flash` (`fastboot flash --slot=a boot boot.img`) causes errors on many fastboot CLI versions.
  - *Fix*: Place `--slot` before `flash` (`fastboot --slot=a flash boot boot.img`) or target the slot partition directly (`boot_a`).
- **Problem 4 (ADB Props Truncation — `adb.py:299`)**: `line.split("]: [")[1]` truncates props whose values contain `]: [`.
  - *Fix*: Use `line.split("]: [", 1)`.
- **Problem 5 (Missing Public Properties — `device_manager.py`)**: `diagnostics_screen.py:74` accesses `device_mgr.adb`.
  - *Fix*: Expose `@property def adb(self) -> ADB: return self._adb` and `@property def fastboot(self) -> Fastboot: return self._fb`.

### 3. FlashShield Lock Engagement & Main-Thread Freezing Elimination (`flash_shield.py` & Screens)
- **Problem 1 (FlashShield Never Engages Global Lock — `flash_shield.py:42`)**: `FlashShieldDialog` calls `release_flash_lock()` upon completion, but never calls `acquire_flash_lock()` upon creation! As a result, `is_flash_locked()` remains `False`, allowing `DeviceMonitor` to continue polling USB/ADB in the background during active partition writes.
  - *Fix*: Call `acquire_flash_lock()` in `FlashShieldDialog.__init__()` and ensure `release_flash_lock()` is called on completion and close.
- **Problem 2 (Main GUI Thread Freezing on Long Operations)**: Multi-minute flashing, backup, and extraction routines run synchronously on the main Qt thread:
  - `flash_rom_screen.py:744`: Custom ROM flashing runs on main thread.
  - `root_screen.py:711`: Root image flashing runs on main thread.
  - `backup_screen.py:371, 398`: Partition dumps and ADB backups run on main thread.
  - `mtk_unisoc_screen.py:536, 570`: PAC firmware extraction and flashing run on main thread.
  - `downloads_screen.py:767`: Driver installation / PowerShell UAC elevation runs with a 60-second blocking timeout on main thread.
  - *Fix*: Wrap long operations in non-blocking background workers (using `QThread` pattern, matching `sideload_screen.py`'s `SideloadWorker`), keeping UI animated, responsive, and preventing Windows "Not Responding" crashes.

### 4. Implement Dual-Mode Boot Image Patching Pipeline (`rooting.py` & `root_screen.py`)
- **Problem**: In `RootScreen`, clicking "1. Patch Boot Image" fails because `RootingEngine.prepare_patch()` currently hardcodes an automatic failure stub.
- **Implementation**:
  1. **Pre-patched Direct Import Mode**: Allow operators to browse/select an already-patched `boot.img` / `init_boot.img` (`magisk_patched_*.img` or `kernelsu_*.img`), validate kernel magic headers, and skip Step 1 straight to Step 2 ("Flash to Phone").
  2. **Device-Assisted ADB Patching Pipeline**: Automatically push `stock_boot.img` to `/sdcard/Download/boot.img`, invoke the Magisk/KernelSU patch script via ADB shell, and pull the resulting patched image back into `data/tools/patched_boot/`.
  3. **Offline Fallback**: Support bundling/calling `magiskboot.exe` or pure-Python GKI header parser for zero-phone offline patching.

### 5. Implement Unisoc 1-Click Token Unlocker & Anti-Red-State Shield (`unlock_screen.py`, `unisoc.py`, `transsion.py`)
- **Problem**: Unisoc devices (Tecno Pop, Infinix Smart, itel, Realme C, Moto E) reject standard `fastboot flashing unlock` with `remote: 'Unlock bootloader is not allowed'`.
- **Implementation**:
  1. In `flashdock/core/unisoc.py`, create `UnisocUnlockManager`:
     - Query `fastboot oem get_identifier_token` and extract 64-character token.
     - Cryptographically sign with community RSA 2048 private key to output `signature.bin`.
     - Dispatch `fastboot flashing unlock_bootloader signature.bin`.
     - Add 1-click **"Flash Disabled vbmeta (Anti-Red State)"** button running `fastboot --disable-verity --disable-verification flash vbmeta vbmeta.img` to prevent immediate Red-State brick bootloops.
  2. In `flashdock/ui/screens/unlock_screen.py`: Add dedicated **"Unisoc / Spreadtrum Token Unlocker"** tab/wizard.
  3. In `flashdock/brands/transsion.py`: Update Unisoc chipset unlock flow to point directly to the Token Unlocker wizard.

### 6. Built-in `payload.bin` Dumper & Samsung `.lz4` Decompressor (`flashdock/tools/`)
- **Problem**: Modern OTA update zips (Pixel, OnePlus, Nothing, HyperOS, Motorola) contain `payload.bin`, and Samsung firmware contains `.img.lz4` archives. FlashDock cannot parse these directly.
- **Implementation**:
  1. Create `flashdock/tools/payload_dumper.py`: Streaming parser for Android Delta/Full OTA `payload.bin` files that extracts individual partitions (`boot.img`, `init_boot.img`, `recovery.img`, `vbmeta.img`) in under 10 seconds without unpacking the entire multi-gigabyte ZIP.
  2. Create `flashdock/tools/lz4_util.py`: Pure-Python chunked LZ4 decompressor to unpack Samsung `AP_*.tar.md5` archives directly into clean `.img` files.
  3. Wire extractors into `FlashRomScreen`, `RootScreen`, and `ReturnStockScreen`.

### 7. Expand Factory Restore Firmware Formats (`return_stock_screen.py` & `return_stock.py`)
- **Problem**: `return_stock_screen.py:613` file picker only permits `"ZIP Archives (*.zip)"` and `return_stock.py:190` rejects any non-zip/folder input. Official Xiaomi fastboot ROMs are `.tgz`/`.tar.gz`, Samsung Odin firmwares are `.tar.md5`, and Unisoc firmwares are `.pac`.
- **Implementation**:
  1. Update file picker filter: `"Firmware Archives (*.zip *.tgz *.tar.gz *.tar.md5 *.tar *.pac);;All Files (*.*)"`.
  2. In `ReturnStockEngine.parse_stock_package()`: Support extracting/parsing `.tgz`, `.tar.gz`, `.tar.md5`, and `.pac` packages into valid partition manifests.

### 8. Subprocess Leak Cleanup & Offline Recovery Dumps (`unbrick_screen.py`, `bootloop_fixer.py`, `backup.py`, `scrcpy.py`)
- **Unbrick Screen (`unbrick_screen.py:581`)**: Replace direct `subprocess.run` with `self._fastboot.flash()` to avoid black console popups, honor dry-run mode, and respect UTF-8 encoding.
- **Bootloop Fixer (`bootloop_fixer.py:114, 140, 160`)**: Replace raw `subprocess.run` with `run_command()` with `CREATE_NO_WINDOW`.
- **Custom Recovery Partition Dumps (`backup.py:234`)**: Allow raw partition dumps in `"recovery"` mode (TWRP / OrangeFox) where ADB shell has root permissions (`uid=0`), without requiring `su -c`.
- **scrcpy Launch Window (`scrcpy.py:182`)**: Add `CREATE_NO_WINDOW` to avoid opening a blank command prompt window alongside the mirror window.

### 9. A/B Slot Switcher & FastbootD HUD Indicator
- **Live HUD Differentiation (`device_hud.py`)**:
  - In Fastboot mode, query `fastboot getvar is-userspace`.
  - If `yes`, display **`FastbootD (Userspace)`** badge in Cyan (`#00E5FF`).
  - If `no`, display **`Fastboot (Bootloader)`** in Cobalt Blue (`#007AFF`).
- **1-Click Active Slot Switcher (`reboot_switchboard.py` & `phone_panel.py`)**:
  - Add **"Switch Active Slot (A/B)"** button running `fastboot --set-active=<other_slot>` directly in the Reboot Switchboard and Phone Control Panel for instant bootloop rollback.

### 10. Fix Virtual Keypad (ADB) (`key_guide_dialog.py`)
- **Problem**: Virtual keypad buttons fail to send keypresses.
- **Fix**: Format commands strictly as `f"input keyevent {keycode}"`, pass active device serial from `main_window.py`, and automatically detect serial if blank.

### 11. Remaining Visual & Layout Polish (`fix 6.png`, `12.png`, `13.png`, `14.png`, `fix 8.png`)
- **`fix 6.png` & `fix 13.png` (`key_guide_dialog.py`)**: Replace glaring white cards with sleek dark cards (`rgba(255,255,255,0.05)`) and fix dark-on-dark unreadable headers.
- **`fix 12.png` (`device_hud.py`)**: In `_set_mode_ui()`, scope QFrame border style (`QFrame { border: 1px solid {color}; }`) and add `QLabel { border: none; }` so child labels do not inherit the border and create double boxes around the text.
- **`fix 14.png` (`tools_manager.py:684`)**: Fix `_execute_pnputil_install()` logic check so it never reports success when pnputil output contains "Failed to add driver package: Access is denied" or "Added driver packages: 0".
- **`fix 8.png` (`integrity_screen.py`)**: Constrain fingerprint table height and enclose the tab in a `QScrollArea` so the "Apply & Inject pif.json" button is never clipped on laptop displays.

### 12. Ergonomic Non-Scrolling Home Tools Canvas (`main_window.py`)
- Compact Home screen grid into **4 columns** with compact HyperOS chips (height 52–56px) with tooltips.
- Remove outer `QScrollArea` from `_build_home_page()` so all 15 tools fit **100% visible on screen without vertical scrollbars**.
- Retain smooth slim scrolling in Left Navigation Sidebar and Live Terminal with smooth splitter handle.

### 13. Interactive Clickable Workflow Guide (`workflow_guide.py`)
- Overhaul all 15 tool cards with "How It Works (Under the Hood)", "Step-by-Step Instructions", safety checklists, and direct "Launch Tool ➔" shortcut buttons.

### 14. Mandatory Verification, Version Bump & GitHub Pipeline
*(Strictly enforce Section 4 of `.agents/skills/flashdock-workstation/SKILL.md`)*
1. **Semantic Version Bump to `1.4.0`**:
   - `flashdock/__init__.py`: `__version__ = "1.4.0"`
   - `flashdock/constants.py`: `APP_VERSION = "1.4.0"`
   - `scripts/version_info.txt`: Update `FileVersion` and `ProductVersion` to `1.4.0.0`
   - `README.md`, `read.md`, and `handoff.md`: Update badges, frontmatter, and headings to `v1.4.0 (Phase 24)`.
2. **Automated Verification & Packaging**:
   - Run `python scripts/release_build.py` (ensure 485+ tests pass with 100% success rate).
   - Compile clean binary `dist/FlashDock_Dist/FlashDock.exe` and archive `dist/FlashDock-v1.4.0-windows-x64.zip`.
3. **GitHub Push**:
   - `git add .`
   - `git commit -m "feat(v1.4.0): Unisoc token unlocker, device sync fix, payload.bin dumper, boot patch engine, and non-scrolling canvas"`
   - `git push origin main`
```
