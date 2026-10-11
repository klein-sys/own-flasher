# FlashDock — Agent Handoff Document

**Date:** 2026-10-12  
**Current Phase:** **GSM Suite Core Architecture & Feature Expansion (Subsystems 1–4, 100% Scope Completed)**  
**Workspace Root:** `C:\Users\dxzmw\.gemini\antigravity-ide\scratch\FlashDock`  
**Application:** FlashDock — Multi-Chipset Android Service Workstation & Flashing Suite  
**Runtime:** Python 3.14.7 + PySide6 (Qt 6.10)  
**Distribution:** Standalone Windows Executable (`dist/FlashDock_App/FlashDock.exe`) & Release Archive (`dist/FlashDock-v1.0.0-windows-x64.zip`)  
**Test Suite:** **413 Passed Unit & Integration Tests across 42 test modules (`python -m pytest tests/`, 100% success rate)**  
**GitHub Repository:** `https://github.com/klein-sys/own-flasher.git` (synchronized on branch `main`)

---

## 1. Project Overview & Architecture

FlashDock is a macOS Big Sur-inspired desktop Android flashing and service workstation for Windows 10/11 (64-bit), modeled on industry-standard multi-chipset repair platforms (UnlockTool, TFT Unlocker, Chimera Tool). It features a clean, thread-safe, and asynchronous core architecture across four primary subsystems:

### Key Architectural Pillars
- **Hardware Polling & VID/PID Engine (`device_monitor.py`)**: Non-blocking `QThread` polling USB/COM ports via Windows Registry enumeration (`SYSTEM\CurrentControlSet\Enum\USB` and `HARDWARE\DEVICEMAP\SERIALCOMM`). Comprehensive VID/PID mapping for ADB, Fastboot, MediaTek BROM (`0E8D:0003`), Preloader (`0E8D:2000`), Qualcomm EDL 9008 (`05C6:9008`), Qualcomm Diag (`05C6:9006`), Unisoc U2S Diag (`1782:4D00`), and FDL (`1782:4D02`).
- **Device Diagnostics Engine (`diagnostics_engine.py`)**: Batch `getprop` query extracting model, brand, manufacturer, build ID, Android OS, baseband, security patch level, root status (`su` binary, Magisk/KSU), and Samsung Knox warranty bit. Safe Fastboot `getvar all` parser detecting active slot (`_a`/`_b`), bootloader unlocked status, Secure Boot state, CID, and max-download-size.
- **Flashing & Calibration Backup Engine (`flash_engine.py`)**: Asynchronous worker thread supporting chunked single-image write operations (`boot`, `init_boot`, `recovery`, `super`, `system`), byte progress updates (`progress_changed`), pre-flash calibration backups targeting telemetry blocks (`efs`, `nvram`, `nvdata`, `persist`, `sec_efs`) with SHA-256 validation, and bootloader unlock/relock controllers.
- **UI Architecture & macOS Big Sur Styling (`main_window.py` & `styles.py`)**: Top segmented control for high-volume OEMs (Xiaomi, Samsung, Transsion, Universal Android) and Universal Chipsets (MediaTek BROM, Qualcomm EDL, Unisoc SPRD). Left Operations Panel for mode-specific action triggers. Right Console Pane streaming color-coded process telemetry (`[INFO]` in Blue, `[WARN]` in Amber, `[SUCCESS]` in Green, `[ERROR]` in Red). Persistent connection badge and progress bar in status bar. Authentic macOS Big Sur design tokens (`#F5F5F7` background, `#FFFFFF` rounded containers with subtle borders, `#007AFF` accent).

---

## 2. Complete Phase Breakdown (Phases 1–16 + Extended UX & Workstation Setup)

### Phase 1–3: Core Engine & Device Detection
- **ADB & Fastboot wrappers** (`flashdock/tools/adb.py`, `flashdock/tools/fastboot.py`) with timeout management, device enumeration, and property parsing.
- **Device state tracking** (`flashdock/core/device.py`): tracks mode (`adb`, `fastboot`, `fastbootd`, `recovery`, `sideload`, `unauthorized`, `not_connected`), active slot (`a`/`b`), dynamic partitions (`super.img`), battery level, and codename.
- **Logging & Config** (`flashdock/logger/__init__.py`, `flashdock/config.py`): rotating file logger in `data/logs/` and persistent JSON configuration.

### Phase 4: Bootloader Unlock & Brand Handlers
- **Brand modules** (`flashdock/brands/`): Google Pixel, Xiaomi / Poco / Redmi (token wait times & fastboot unlock), Samsung (Knox / Odin warning), OnePlus, Motorola, and generic OEM handlers.
- **Unlock Screen** (`flashdock/ui/screens/unlock_screen.py`): step-by-step unlock wizard and 1-click command execution.

### Phase 5: Partition Backup & Restore
- **Backup Engine** (`flashdock/core/backup.py`): slot-aware backup for critical partitions (`boot`, `init_boot`, `vbmeta`, `vendor_boot`, `dtbo`, `efs`, `persist`).
- **Checksum validation**: SHA-256 integrity verification and backup archive management.
- **Backup Screen** (`flashdock/ui/screens/backup_screen.py`): partition selector, live progress, and one-click restore.

### Phase 6: Universal Root Solutions
- **Universal Root Engine** (`flashdock/core/rooting.py`):
  - Official Magisk (Stable & Canary), Magisk Alpha, Kitsune Mask, KernelSU Next, APatch, and SukiSU Ultra.
  - Payload dumper extraction & automatic boot image patching.
  - Direct installation of root manager APKs via ADB.
- **Root Screen** (`flashdock/ui/screens/root_screen.py`): root solution chooser, boot image patcher, and flashing pipeline.

### Phase 7: Magisk/KSU/APatch Modules Management
- **Module Manager** (`flashdock/core/modules.py`): parses `module.prop` and `update-binary`, extracts module metadata, and checks root environment compatibility.
- **Bootloop Recovery Kill-Switch**: automated removal of culprit modules via ADB and recovery.
- **Modules Screen** (`flashdock/ui/screens/modules_screen.py`): offline local repository, multi-select batch flashing, and active module list.

### Phase 8: Return to Stock & Anti-Relock Gate
- **Stock Firmware Engine** (`flashdock/core/return_stock.py`): unpacks Google factory image ZIPs, Xiaomi Fastboot TGZ, Samsung TAR/MD5, and generic fastboot scripts. Detects anti-rollback version counters.
- **Strict Anti-Relock Gate**: blocks bootloader relocking when custom/modified ROMs or mismatched region firmware are detected.
- **Return Stock Screen** (`flashdock/ui/screens/return_stock_screen.py`): image inspector, wipe/keep data toggle, and emergency unbrick guides.

### Phase 9: Custom ROM, Treble GSI & Custom Recovery Flashing
- **ROM Engine** (`flashdock/core/rom_flasher.py`): Fastboot ROM package parser, sparse chunk flasher, Treble GSI flasher, FastbootD switcher, and TWRP/OrangeFox recovery flashing.
- **Local ROM & GSI Library** (`flashdock/core/repository.py`): local offline storage with phone codename & architecture matching.
- **Flash ROM Screen** (`flashdock/ui/screens/flash_rom_screen.py`): 5-tab ROM, GSI, Recovery, Local Library, and Guides screen.

### Phase 10: Advanced Diagnostics, Debloater & System Tweaks
- **Debloater Manager** (`flashdock/core/diagnostics.py`): package enumeration, categorized bloatware list, safe disable via `pm disable-user --user 0`, user-space uninstallation via `pm uninstall -k --user 0`, and 1-click restore.
- **Hardware & Battery Telemetry**: live voltage, temperature, health state, charge cycles, CPU governor, and thermal metrics.
- **System Tweaker**: animation scale speeds (0.0x, 0.5x, 1.0x), custom DPI density modification and reset, wireless ADB over TCP/IP port 5555.
- **Diagnostics Screen** (`flashdock/ui/screens/diagnostics_screen.py`): 3-tab debloater, hardware health, and tweaks screen.

### Phase 11: MediaTek (MTK BROM) & Unisoc (SPD PAC) Engine
- **MediaTek Engine** (`flashdock/core/mtk.py`): MTK scatter parser (v1.1+ and tabular), BROM handshake (`0xA0, 0x0A, 0x50, 0x05`), SLA/DAA authentication bypass via watchdog disable, and partition flashing pipeline.
- **Unisoc Engine** (`flashdock/core/unisoc.py`): Unisoc `.pac` binary extractor, FDL HDLC/CRC-16 communication protocol, and two-stage bootloader execution.
- **MTK & Unisoc Screen** (`flashdock/ui/screens/mtk_unisoc_screen.py`): scatter and PAC flasher with live log output.

### Phase 12: Downloads, OEM Drivers & Platform Tools Manager
- **Driver Manager** (`flashdock/core/driver_manager.py`): installs OEM Windows drivers (Google ADB/Fastboot, Samsung USB, Xiaomi/Qualcomm QDLoader 9008, MTK VCOM, Unisoc SPD).
- **Tools Manager** (`flashdock/core/tools_manager.py`): verifies and downloads 20 bundled service binaries.
- **Downloads Screen** (`flashdock/ui/screens/downloads_screen.py`): 4-tab manager for drivers, platform tools, firmwares, and repositories.

### Phase 13: Emergency Unbrick & EDL Flasher
- **Bootloop Fixer Engine** (`flashdock/core/bootloop_fixer.py`): Qualcomm Emergency Download (EDL 9008) Sahara/Firehose flasher, Samsung Odin TAR/MD5 & PIT extractor, MediaTek SP Flash Tool bridge, and Fastboot emergency rescue.
- **Unbrick Screen** (`flashdock/ui/screens/unbrick_screen.py`): brand-specific triage cards with guided recovery actions.

### Phase 14: Play Integrity Fixer & Fingerprint Spoofer
- **Integrity Engine** (`flashdock/core/integrity.py`): Play Integrity API check guidance, PIF `pif.json` manager, custom `keybox.xml` injector, and Zygisk module injection.
- **Integrity Screen** (`flashdock/ui/screens/integrity_screen.py`): 4-tab dashboard for device status, fingerprint manager, keybox injector, and certification instructions.
- **Banking Protection Redesign**: Completely overhauled Banking / Root Hiding Guard tab into a spacious, scrollable 2-column card layout, fixing the crowded and overlapping button bugs.

### Phase 15: Logs, Telemetry & Interactive Troubleshooting Center
- **Troubleshooter Engine** (`flashdock/core/troubleshooter.py`): automated ADB daemon restart, Windows Device Manager launcher (`devmgmt.msc`), device logcat dump & buffer clearing, and kernel dmesg capture.
- **Logs & Help Screen** (`flashdock/ui/screens/logs_help_screen.py`): 4-tab screen for application logs, device logcat, guided interactive triage cards, and partition architecture reference.

### Phase 16 & UX Hardening: Production Polish, Setup Wizard & Phone Controls
- **Laptop & Workstation Setup Wizard** (`flashdock/ui/widgets/setup_wizard_dialog.py`):
  - 4-step wizard: platform-tools auto-install, OEM Windows driver setup, laptop USB port & sleep best practices, live connection test.
- **Hardware Phone Controls & Navigation Guide** (`flashdock/ui/widgets/key_guide_dialog.py`):
  - Physical button combination guide (Vol+, Vol-, Power) for entering Bootloader, Recovery, FastbootD, EDL, and Download modes across Google, Samsung, Xiaomi, OnePlus, Motorola, LG, and MTK.
  - Sidebar hardware key controls (`🔊 +`, `🔉 -`, `⚡ Pwr`) and modal button launcher.
- **System Self-Tester & Modal Dialog** (`flashdock/core/selftest.py`, `flashdock/ui/widgets/selftest_dialog.py`):
  - Dark/light mode Apple HIG cards (`#1C1C1E` dark mode background), fast 2-second timeout, `CREATE_NO_WINDOW` flags preventing hangs.
- **Scrcpy Guard**: Guarded device property lookups in `scrcpy_dialog.py`, fixing the `NoneType` brand crash when launched without a connected phone.
- **Telemetry Spam Elimination**: Lowered missing tool runner logging from error to debug and added disk existence guards in device manager cycle.
- **UI Decluttering**: Removed redundant Quick Access chip row to give the 15 main action cards plenty of breathing room, and broadened the Sort dropdown to 160px min-width to avoid text clipping.

### Phase 17: GSM Suite Core Architecture & Multi-Chipset Subsystems
- **Subsystem 1 — Hardware Polling Engine (`flashdock/workers/device_monitor.py`)**:
  - Non-blocking `QThread` polling Windows registry for USB and serial devices without external dependencies.
  - VID/PID table for ADB, Fastboot, MTK BROM (`0E8D:0003`), Preloader (`0E8D:2000`), Qualcomm EDL 9008 (`05C6:9008`), Unisoc U2S Diag (`1782:4D00`), and FDL (`1782:4D02`).
  - Signals: `device_connected(mode, ident, details)` and `device_disconnected()`.
- **Subsystem 2 — Device Diagnostics Engine (`flashdock/core/diagnostics_engine.py`)**:
  - Batch `getprop` query: brand, model, Android version, baseband, security patch level, Knox void bit, root presence (`su` binary, Magisk/KSU), and battery telemetry.
  - Deep Fastboot `getvar all` query: active partition slot (`_a`/`_b`), unlocked bootloader flag, Secure Boot flag, CID, and max download size. Structured fallback dictionaries for offline/unauthorized states.
- **Subsystem 3 — Flashing & Calibration Backup Engine (`flashdock/workers/flash_engine.py`)**:
  - Asynchronous flashing worker with chunked single-image writing (`boot`, `init_boot`, `recovery`, `super`, `system`), byte progress reporting (`progress_changed`), and pre-flash calibration backups (`efs`, `nvram`, `nvdata`, `persist`, `sec_efs`) with SHA-256 verification.
  - Bootloader unlock (`flashing unlock`, `oem unlock`) and relock controllers.
- **Subsystem 4 — UI Architecture & macOS Big Sur Styling (`flashdock/ui/main_window.py` & `flashdock/ui/styles.py`)**:
  - Top segmented control for high-volume OEMs (Xiaomi, Samsung, Transsion, Universal Android) and Universal Chipsets (MediaTek BROM, Qualcomm EDL, Unisoc SPRD).
  - Left Operations Panel: Device Diagnostics, Partition Backup, Flash Firmware, Bootloader Tools, and Reboot Shortcuts.
  - Right Console Pane: Persistent read-only terminal with color-coded stream prefixes (`[INFO]` in Blue, `[WARN]` in Amber, `[SUCCESS]` in Green, `[ERROR]` in Red).
  - Bottom Status Bar: Persistent USB connection badge and smooth `QProgressBar`.

---

## 3. Workstation Navigation Index (All Tools & Modals)

| Action ID | Tool Name | Category | Screen / Dialog | Page Index |
|---|---|---|---|---|
| `check_phone` | Check my phone | Device | `DeviceCard` | `PAGE_DEVICE_CARD = 1` |
| `checklist` | Safety Checklist | Rescue | `ChecklistScreen` | `PAGE_CHECKLIST = 2` |
| `unlock_bl` | Unlock Bootloader | Flashing | `UnlockScreen` | `PAGE_UNLOCK = 3` |
| `backup` | Backup / Restore | Rescue | `BackupScreen` | `PAGE_BACKUP = 4` |
| `root` | Root my phone | Root | `RootScreen` | `PAGE_ROOT = 5` |
| `modules` | Manage Modules | Root | `ModulesScreen` | `PAGE_MODULES = 6` |
| `return_stock` | Return to Stock | Flashing | `ReturnStockScreen` | `PAGE_RETURN_STOCK = 7` |
| `flash_rom` | Flash ROM / GSI | Flashing | `FlashRomScreen` | `PAGE_FLASH_ROM = 8` |
| `diagnostics` | Diagnostics & Tweaks | Device | `DiagnosticsScreen` | `PAGE_DIAGNOSTICS = 9` |
| `mtk_unisoc` | MTK / Unisoc mode | Flashing | `MtkUnisocScreen` | `PAGE_MTK_UNISOC = 10` |
| `downloads` | Downloads & Tools | Device | `DownloadsScreen` | `PAGE_DOWNLOADS = 11` |
| `unbrick` | Fix bricked phone | Rescue | `UnbrickScreen` | `PAGE_UNBRICK = 12` |
| `integrity` | Fix Play Integrity | Root | `IntegrityScreen` | `PAGE_INTEGRITY = 13` |
| `scrcpy` | Screen Mirror (scrcpy) | Device | `ScrcpyDialog` | Modal Dialog |
| `logs_help` | Logs & Help | Device | `LogsHelpScreen` | `PAGE_LOGS_HELP = 14` |
| `selftest` | System Self-Test | Device | `SelfTestDialog` | Modal Dialog |
| `setup_wizard` | Laptop Setup Wizard | Workstation | `SetupWizardDialog` | Modal Dialog |
| `key_guide` | Hardware Key Guide | Controls | `HardwareKeyGuideDialog` | Modal Dialog |

---

## 4. Test Suite & Verification Results

- **Unit & Integration Tests**: **413 passed in 43.60s** (100% pass rate).
- **Test Modules**: 42 individual test files in `tests/`.
- **Standalone Binary**: `dist/FlashDock_App/FlashDock.exe` (2.71 MB, Exit code 0).
- **Release Archive**: `dist/FlashDock-v1.0.0-windows-x64.zip` (56.25 MB).
- **Integrity Hashes**:
  - `FlashDock.exe`: `82271f2d47862d3a28ce250bfa997001ae785c90415fcf54a3cac47e5147f6ed`
  - `Release ZIP`: `36788d1a6067629f871cc713151f9acb26e16e86ff54104d5a55d3f65874be2f`

---

## 5. Recent Additions & Enhancements

1. **Transsion Holdings Support**:
   - Implemented `flashdock/brands/transsion.py` providing complete handlers for **Tecno** (HiOS), **Infinix** (XOS), and **itel** (itelOS).
   - Bootloader unlock flows with `fastboot flashing unlock` and `fastboot flashing unlock_critical`, Volume Up hardware confirmation guides, and Carlcare official firmware portals.
   - Updated `DeviceInfo.brand_normalized` and cataloged `transsion_usb` and `unisoc_spd` driver packages.

2. **Clean Vector Brand Badges & Icons**:
   - Created `flashdock/ui/brand_assets.py` rendering high-resolution, pixel-perfect vector SVG brand logos (Google, Samsung, Xiaomi, Tecno, Infinix, itel, OnePlus, Motorola, MediaTek, Qualcomm, Unisoc, Android).
   - Replaced emoji stickers in `DeviceCard` and `UnlockScreen` with modern vector badges.

3. **Smart Connection Helper & Troubleshooting**:
   - Added connection guidance card in the sidebar: informs users when phone is in MTP/Charge mode, guides enabling USB Debugging, and displays high-visibility amber prompt when RSA key is unauthorized.
   - 1-click **Setup Wizard** and **Restart ADB & Re-prompt** actions for quick resolution.

4. **Hardware Key Guide & Remote**:
   - Replaced loose sidebar sticker buttons with dedicated, contextual `HardwareKeyGuideDialog` modal detailing hardware combinations for Recovery, Fastboot, Bootloader unlock confirmation, and force restarts.

5. **Driver Links & Portal Fix**:
   - Fixed SP Flash Tool 404 URL by updating root portal to `https://spflashtool.com/`.
   - Added official Transsion Carlcare, Tecno, and Infinix stock ROM repositories to Firmware Finder.
