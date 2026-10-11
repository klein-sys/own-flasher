# FlashDock — Agent Handoff Document

**Date:** 2026-10-12  
**Current Phase:** **Phase 16: Production Hardening, System Self-Test, Crash Reporter & v1.0.0 Release (100% Core & Extended Scope Completed)**  
**Workspace Root:** `C:\Users\dxzmw\.gemini\antigravity-ide\scratch\FlashDock`  
**Application:** FlashDock — One-Click Personal Desktop Android Service Workstation  
**Runtime:** Python 3.14.7 + PySide6 (Qt 6.10)  
**Distribution:** Standalone Windows Executable (`dist/FlashDock/FlashDock.exe`, 2.67 MB) & Release Archive (`dist/FlashDock-v1.0.0-windows-x64.zip`, 56.16 MB)  
**Test Suite:** **378 Passed Unit & Integration Tests across 39 test modules (`python -m pytest tests/`, 100% success rate)**  
**GitHub Repository:** `https://github.com/klein-sys/own-flasher.git` (synchronized on branch `main`)

---

## 1. Project Overview & Architecture

FlashDock is an Apple Human Interface Guidelines (HIG)-styled desktop Android flashing and service utility for Windows 10/11 (64-bit). It provides a guided, safe, 1-click interface for managing Android devices across standard ADB, Fastboot, FastbootD, Recovery, Qualcomm EDL 9008, Samsung Odin, MediaTek BROM, and Unisoc FDL modes.

### Key Architectural Pillars
- **Safety Pre-Flight Engine**: Hardware pre-flight checks (battery $\ge 30\%$, unlocked bootloader, proper connection mode), typed confirmation prompts for high-risk operations, rollback counter protection, and strict anti-relock gate.
- **Offline Capability**: Local offline repository for Custom ROMs, GSIs, modules, root solutions, drivers, and stock firmwares. Online actions are automatically shaded (`opacity: 0.45; dashed border`) and disabled when offline.
- **Read-Only Side Terminal**: A dedicated, read-only terminal panel displaying active ADB/Fastboot commands and subprocess output in real time without allowing accidental user edits.
- **Modern Partition Support**: Native handling of A/B slots, dynamic partitions (`super.img`), Android 10+ FastbootD transition, and recovery embedding (`boot` vs `init_boot` vs `recovery`).
- **Apple HIG Styling**: Refined Athens Gray (`#F5F5F7` light, `#1C1C1E` dark) canvas, subtle drop shadows, System Blue (`#007AFF`) accents, and category pill badges.

---

## 2. Complete Phase Breakdown (Phases 1–16)

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

### Phase 15: Logs, Telemetry & Interactive Troubleshooting Center
- **Troubleshooter Engine** (`flashdock/core/troubleshooter.py`): automated ADB daemon restart, Windows Device Manager launcher (`devmgmt.msc`), device logcat dump & buffer clearing, and kernel dmesg capture.
- **Logs & Help Screen** (`flashdock/ui/screens/logs_help_screen.py`): 4-tab screen for application logs, device logcat, guided interactive triage cards, and partition architecture reference.

### Phase 16: Production Hardening, System Self-Test, Crash Reporter & Release Packaging
- **System Self-Tester** (`flashdock/core/selftest.py`): automated diagnostics verifying Python version, OS environment, filesystem read/write permissions, binary toolchains (ADB/Fastboot), SQLite cache storage, and network socket connectivity.
- **Universal Crash Reporter** (`flashdock/core/crash_reporter.py`): intercepts unhandled exceptions in Python runtime and Qt event loops (`sys.excepthook` and `threading.excepthook`), masks device serials (`[SERIAL]`) and username paths (`[USER]`), writes diagnostic crash dumps to `data/logs/crash_<stamp>.log`.
- **Apple HIG Dialogs**:
  - `SelfTestDialog` (`flashdock/ui/widgets/selftest_dialog.py`): system health cards, status badges (PASS / WARN / FAIL), report copier, and re-run.
  - `CrashDialog` (`flashdock/ui/widgets/crash_dialog.py`): non-fatal recovery modal with masked traceback viewer, logs folder opener, and clean restart.
- **Release Automation Pipeline** (`scripts/release_build.py`):
  - Automatically runs and validates all 378 unit tests.
  - Compiles PyInstaller standalone distribution (`dist/FlashDock/FlashDock.exe`, 2.67 MB).
  - Creates release distribution archive (`dist/FlashDock-v1.0.0-windows-x64.zip`, 56.16 MB).
  - Computes and records SHA-256 hashes in `dist/SHA256SUMS.txt`.

---

## 3. Workstation Navigation Index (All 15 Tools)

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

---

## 4. Test Suite & Verification Results

- **Unit & Integration Tests**: **378 passed in 40.35s** (100% pass rate).
- **Test Modules**: 39 individual test files in `tests/`.
- **Standalone Binary**: `dist/FlashDock/FlashDock.exe` (2.67 MB, Exit code 0).
- **Release Archive**: `dist/FlashDock-v1.0.0-windows-x64.zip` (56.16 MB).
- **Integrity Hashes**:
  - `FlashDock.exe`: `44374216b65d19023aceaad28aa7985ed420b227732099b60eaaf6ec3a7d4809`
  - `Release ZIP`: `9b36b5d121061f9ee9320e8f19348e6c245b9970823a24999feb2453228c17fe`
