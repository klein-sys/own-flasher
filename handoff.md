# FlashDock — Agent Handoff Document

**Date:** 2026-10-11  
**Workspace Root:** `C:\Users\dxzmw\.gemini\antigravity-ide\scratch\FlashDock`  
**Application:** FlashDock — One-Click Personal Desktop Android Service Toolbox  
**Runtime:** Python 3.14.7 + PySide6 (Qt 6.10)  
**Distribution:** Standalone Windows Executable (`dist/FlashDock/FlashDock.exe`)  
**Test Suite:** 264 Passed Unit & UI Tests (`pytest tests/`)

---

## 1. Objective & Scope

FlashDock is a personal, safety-first desktop Android flashing and service utility for Windows. It provides a guided, one-click interface for managing Android devices across standard ADB, Fastboot, FastbootD, and Recovery modes.

### Key Goals
- **Safety First**: Hardware pre-flight checks (battery $\ge 30\%$, unlocked bootloader, proper connection mode), typed confirmation prompts for high-risk operations, and rollback protection detection.
- **Offline Capability**: Local offline repository for Custom ROMs, GSIs, modules, root solutions, drivers, and stock firmwares with device compatibility matching. Online actions are automatically shaded/disabled when offline.
- **Real-Time Visualizer**: A dedicated, read-only side terminal displaying active ADB/Fastboot commands and subprocess output in real time without allowing accidental user edits.
- **Modern Android Support**: Full awareness of A/B slots, dynamic partitions (`super.img`), Android 10+ FastbootD transition, and recovery embedding (`boot` vs dedicated `recovery`).
- **Zero-Setup Standalone**: Built and verified as a standalone directory distribution via PyInstaller (`dist/FlashDock/FlashDock.exe`).

---

## 2. Completed Phases & Features

### Phase 1–3: Core Engine & Device Detection
- **ADB & Fastboot wrappers** ([`adb.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/tools/adb.py), [`fastboot.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/tools/fastboot.py)) with timeout management, device enumeration, and property parsing.
- **Device state tracking** ([`device.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/device.py)): tracks mode (`adb`, `fastboot`, `fastbootd`, `recovery`, `sideload`, `unauthorized`, `not_connected`), active slot (`a`/`b`), dynamic partitions (`super.img`), battery level, and codename.
- **Logging & Config** ([`logger.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/logger.py), [`config.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/config.py)): rotating file logger in `data/logs/` and persistent configuration.

### Phase 4: Bootloader Unlock & Brand Handlers
- **Brand modules** ([`brands/`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/brands/)): Google Pixel, Xiaomi / Poco / Redmi (token wait times & fastboot unlock), Samsung (Knox / Odin warning), OnePlus, Motorola, and generic OEM handlers.
- **Unlock Screen** ([`unlock_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/unlock_screen.py)): step-by-step unlock wizard and 1-click command execution.

### Phase 5: Partition Backup & Restore
- **Backup Engine** ([`backup.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/backup.py)): slot-aware backup for critical partitions (`boot`, `init_boot`, `vbmeta`, `vendor_boot`, `dtbo`, `efs`, `persist`).
- **Tar/ZIP packaging** and checksum validation.
- **Backup Screen** ([`backup_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/backup_screen.py)): partition selector, live progress, and one-click restore.

### Phase 6: Root Solutions & Custom Root Management
- **Universal Root Engine** ([`rooting.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rooting.py)):
  - Official Magisk (Stable & Canary), Magisk Alpha, Kitsune Mask, KernelSU Next, APatch, and SukiSU Ultra.
  - Payload dumper extraction & automatic boot image patching.
  - Direct installation of root manager APKs via ADB.
- **Local Root Library Dialog** ([`root_library_dialog.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/root_library_dialog.py)): manages custom root APKs, official GitHub releases links, and local version selection.
- **Root Screen** ([`root_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/root_screen.py)): root solution chooser, boot image patcher, and flashing pipeline.

### Phase 7: Magisk/KSU/APatch Modules Management
- **Module Manager** ([`modules.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/modules.py)): parses `module.prop` and `update-binary`, extracts module metadata, and checks root environment compatibility.
- **Modules Screen** ([`modules_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/modules_screen.py)): offline local repository, multi-select batch flashing, and active module list.

### Phase 8: Return to Stock & Rescue
- **Stock Firmware Engine** ([`return_stock.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/return_stock.py)): unpacks Google factory image ZIPs, Xiaomi Fastboot TGZ, Samsung TAR/MD5, and generic fastboot scripts. Detects anti-rollback version counters.
- **Return Stock Screen** ([`return_stock_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/return_stock_screen.py)): image inspector, wipe/keep data toggle, and emergency unbrick guides.

### Phase 9: Custom ROM, Treble GSI & Custom Recovery Flashing
- **ROM Engine** ([`rom_flasher.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rom_flasher.py)):
  - Fastboot ROM package parser (folder / `.zip`, `flash_all.bat` / `.sh`, `android-info.txt`).
  - Canonical partition sequence (`bootloader` $\to$ `radio` $\to$ `boot` $\to$ `recovery` $\to$ `vbmeta` $\to$ `super`/`system` $\to$ `userdata`).
  - Sparse chunk sequencing (`system.img_sparsechunk.0`, etc.).
  - Treble GSI image inspection (arch `arm64`, slot `a/b`, Phh variant tags).
  - Recovery partition target resolution (`boot` vs `recovery`) & RAM live-boot (`fastboot boot`).
  - FastbootD switcher (`fastboot reboot fastboot`).
- **Local ROM & GSI Library** ([`repository.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/repository.py)): local offline storage with phone codename & architecture matching.
- **5-Tab UI** ([`flash_rom_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/flash_rom_screen.py)): ROM Flasher, GSI Flasher, Recovery Flasher, Local Library, and Guides.

### User Additions Completed
- **Read-Only Side Terminal** ([`side_terminal.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/side_terminal.py)): monitors executing shell / ADB commands in real time with auto-scroll and clear capabilities.
- **Offline Detection** ([`network.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/network.py)): checks internet connectivity; dims/disables online buttons when offline.
- **Interactive Workflow Guide** ([`workflow_guide.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/workflow_guide.py)): step-by-step interactive workflow wizard.
- **Phone OS Status Detection** ([`os_detection.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/os_detection.py)): checks whether the phone is rooted, running a GSI, or running a custom ROM.

---

## 3. Touched & Created Files

### Core & Logic
- [`flashdock/core/device.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/device.py) — Connected device model & state detector
- [`flashdock/core/safety.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/safety.py) — Pre-flight safety checks & criteria
- [`flashdock/core/backup.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/backup.py) — Partition backup & restore manager
- [`flashdock/core/rooting.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rooting.py) — Universal root solution coordinator
- [`flashdock/core/modules.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/modules.py) — Magisk/KSU/APatch module parser & installer
- [`flashdock/core/return_stock.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/return_stock.py) — Factory image unpacker & stock return engine
- [`flashdock/core/rom_flasher.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rom_flasher.py) — ROM, GSI, and Recovery flasher
- [`flashdock/core/repository.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/repository.py) — Local offline catalog for ROMs, GSIs, modules, root APKs, drivers
- [`flashdock/core/os_detection.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/os_detection.py) — Phone state, root & ROM detection
- [`flashdock/core/network.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/network.py) — Network monitor for offline-mode dimming
- [`flashdock/tools/fastboot.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/tools/fastboot.py) — Added `wipe(serial)` support

### User Interface
- [`flashdock/ui/main_window.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/main_window.py) — Main window integrating navigation, pages, SideTerminal, and device monitoring
- [`flashdock/ui/screens/flash_rom_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/flash_rom_screen.py) — 5-tab ROM, GSI, Recovery, and local library screen
- [`flashdock/ui/screens/root_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/root_screen.py) — Enhanced root solution screen with custom root support
- [`flashdock/ui/screens/modules_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/modules_screen.py) — Modules screen with local storage
- [`flashdock/ui/screens/return_stock_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/return_stock_screen.py) — Stock firmware screen
- [`flashdock/ui/screens/backup_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/backup_screen.py) — Backup & restore screen
- [`flashdock/ui/widgets/flash_shield.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/flash_shield.py) — Pre-flight safety dialog
- [`flashdock/ui/widgets/side_terminal.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/side_terminal.py) — Read-only subprocess terminal viewer
- [`flashdock/ui/widgets/workflow_guide.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/workflow_guide.py) — Step-by-step guide widget
- [`flashdock/ui/widgets/root_library_dialog.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/root_library_dialog.py) — Dialog for root APK management & releases

### Distribution & Tests
- [`flashdock.spec`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock.spec) — PyInstaller specification with all hidden imports and resources
- [`tests/test_rom_flasher.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_rom_flasher.py) — 10 unit tests for ROM/GSI/Recovery logic
- [`tests/test_flash_rom_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_flash_rom_screen.py) — 6 UI tests for FlashRomScreen
- [`tests/`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/) — Full suite containing 264 passing tests

---

### Phase 10: Advanced Diagnostics, Debloater & System Tweaks
- **Diagnostics Engine** ([`diagnostics.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/diagnostics.py)):
  - `DebloaterManager`: Enumerates packages with status, classifies into Bloatware, Carrier Services, User, System, and Protected Core. Safe disable via `pm disable-user --user 0`, user uninstallation via `pm uninstall -k --user 0` (retaining APK in system image for recovery), and re-enable/restore via `cmd package install-existing`.
  - `HardwareHealthInspector`: Battery telemetry (level, voltage, temperature, health state, charge cycles, power source) and hardware specifications (display resolution, density DPI, CPU cores, frequency governor, thermal sensors).
  - `SystemTweaker`: Animation speed scale controls (0.0x instant, 0.5x snappy, 1.0x default), display density modification (120–800 DPI) and reset, wireless ADB over TCP/IP port 5555 with automatic IP detection, and stay-awake toggle.
- **3-Tab UI Screen** ([`diagnostics_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/diagnostics_screen.py)):
  - Tab 1: Package Manager Debloater with search bar, category chips, state filters, batch recommended debloat, and strict safety guards preventing system bricking.
  - Tab 2: Hardware & Battery Health dashboard with real-time tabular metrics.
  - Tab 3: System Tweaks with instant animation presets, custom DPI input, wireless ADB with 1-click clipboard copy, and developer display settings.
- **Theme System**:
  - Global Dark and Light SaaS QSS stylesheets (`DARK_STYLESHEET`, `LIGHT_STYLESHEET`) in [`styles.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/styles.py).
  - Dynamic 1-click Dark/Light mode toggle button in `MainWindow` header bar (`☀️ Light Mode` / `🌙 Dark Mode`) and menu (`View -> Theme`).
  - Strict anti-slop SaaS principles: Zinc monochromatic scale, subtle 1px hairline borders (`#1f1f23` / `#e4e4e7`), single royal blue accent (`#2563eb`), tabular monospaced numbers.

### User Additions Completed
- **Read-Only Side Terminal** ([`side_terminal.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/side_terminal.py)): monitors executing shell / ADB commands in real time with auto-scroll and clear capabilities.
- **Offline Detection** ([`network.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/network.py)): checks internet connectivity; dims/disables online buttons when offline.
- **Interactive Workflow Guide** ([`workflow_guide.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/workflow_guide.py)): step-by-step interactive workflow wizard.
- **Phone OS Status Detection** ([`os_detection.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/os_detection.py)): checks whether the phone is rooted, running a GSI, or running a custom ROM.

---

## 3. Touched & Created Files

### Core & Logic
- [`flashdock/core/device.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/device.py) — Connected device model & state detector
- [`flashdock/core/safety.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/safety.py) — Pre-flight safety checks & criteria
- [`flashdock/core/backup.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/backup.py) — Partition backup & restore manager
- [`flashdock/core/rooting.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rooting.py) — Universal root solution coordinator
- [`flashdock/core/modules.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/modules.py) — Magisk/KSU/APatch module parser & installer
- [`flashdock/core/return_stock.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/return_stock.py) — Factory image unpacker & stock return engine
- [`flashdock/core/rom_flasher.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rom_flasher.py) — ROM, GSI, and Recovery flasher
- [`flashdock/core/diagnostics.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/diagnostics.py) — Debloater, hardware health, and tweaks engine
- [`flashdock/core/repository.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/repository.py) — Local offline catalog for ROMs, GSIs, modules, root APKs, drivers
- [`flashdock/core/os_detection.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/os_detection.py) — Phone state, root & ROM detection
- [`flashdock/core/network.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/network.py) — Network monitor for offline-mode dimming
- [`flashdock/tools/adb.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/tools/adb.py) — ADB wrapper with `tcpip(port)` command
- [`flashdock/tools/fastboot.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/tools/fastboot.py) — Added `wipe(serial)` support

### User Interface
- [`flashdock/ui/main_window.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/main_window.py) — Main window integrating navigation, pages, theme toggle, and device monitoring
- [`flashdock/ui/styles.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/styles.py) — SaaS Dark & Light stylesheets
- [`flashdock/ui/screens/diagnostics_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/diagnostics_screen.py) — 3-tab debloater, hardware health, and tweaks screen
- [`flashdock/ui/screens/flash_rom_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/flash_rom_screen.py) — 5-tab ROM, GSI, Recovery, and local library screen
- [`flashdock/ui/screens/root_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/root_screen.py) — Enhanced root solution screen with custom root support
- [`flashdock/ui/screens/modules_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/modules_screen.py) — Modules screen with local storage
- [`flashdock/ui/screens/return_stock_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/return_stock_screen.py) — Stock firmware screen
- [`flashdock/ui/screens/backup_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/backup_screen.py) — Backup & restore screen
- [`flashdock/ui/widgets/flash_shield.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/flash_shield.py) — Pre-flight safety dialog
- [`flashdock/ui/widgets/side_terminal.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/side_terminal.py) — Read-only subprocess terminal viewer
- [`flashdock/ui/widgets/workflow_guide.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/workflow_guide.py) — Step-by-step guide widget
- [`flashdock/ui/widgets/root_library_dialog.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/root_library_dialog.py) — Dialog for root APK management & releases

### Distribution & Tests
- [`flashdock.spec`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock.spec) — PyInstaller specification with all hidden imports and resources
- [`tests/test_diagnostics.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_diagnostics.py) — 10 unit tests for diagnostics logic
- [`tests/test_diagnostics_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_diagnostics_screen.py) — 4 UI tests for DiagnosticsScreen
- [`tests/test_main_window.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_main_window.py) — 3 UI tests for MainWindow theme toggle and navigation
- [`tests/`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/) — Full suite containing 284 passing tests

---

### Phase 11: MediaTek (MTK) & Unisoc (SPD) Engine
- **MediaTek Module** ([`mtk.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/mtk.py)):
  - `ScatterParser`: parses MTK scatter files (v1.1+ indented blocks and legacy tabular formats) extracting platform, storage type, linear/physical addresses, partition sizes, and downloadable images. Includes image validation and preloader safety checks.
  - `MTKBROMManager`: BootROM (VID `0x0E8D`, PID `0x0003`) and Preloader (`0x2000`) connection handshake protocol (`0xA0, 0x0A, 0x50, 0x05`), hardware code query (`CMD_GET_HW_CODE`), and chipset family detection (`MT6765`, `MT6785`, `MT6877`, etc.).
  - `AuthBypassHandler`: SLA (Serial Link Authentication) and DAA (Download Agent Authentication) security bypass via watchdog timer register disable (`0x10007000`) and security patching.
  - `MTKFlashPipeline`: orchestrated partition downloads, progress emission, and preloader safety guards.
- **Unisoc / Spreadtrum Module** ([`unisoc.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/unisoc.py)):
  - `PACExtractor`: binary parser for Unisoc `.pac` archives (`BP_Firmware` format), extracting manifest, single partition streaming, and full archive extraction (`FDL1`, `FDL2`, `boot`, `super`, etc.).
  - `FDLProtocolHandler`: Bootloader Serial Link (BSL) HDLC packet framing (`0x7E`, escape `0x7D`), command framing, and CRC-16 CCITT validation.
  - `UnisocFlashPipeline`: two-stage bootloader execution (FDL1 to SRAM $\to$ FDL2 to DRAM) and partition flashing workflow.

### User Interface Overhaul: Apple Human Interface Guidelines (HIG)
- **Eye-Friendly Light Mode**:
  - Eliminated stark `#FFFFFF` vs `#000000` glare.
  - Main window application background set to soothing off-white/Athens Gray (`#F5F5F7`).
  - Elevated cards & containers float gently on pure white (`#FFFFFF`) with 10px rounded corners and subtle drop shadows (`QGraphicsDropShadowEffect`).
  - Primary text softened to Apple Shark (`#1D1D1F`), secondary/subtitles to `#6E6E73` and `#86868B`.
  - Apple System Blue (`#007AFF`) used exclusively for interactive elements and active selections.
  - Soft-gray sidebars and bars (`#EBEBF0`).
  - Replaced hardcoded widget inline styles with unified `_make_back_button()` navigation helper.

---

## 3. Touched & Created Files

### Core & Logic
- [`flashdock/core/mtk.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/mtk.py) — MediaTek BROM connection, scatter parser, auth bypass
- [`flashdock/core/unisoc.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/unisoc.py) — Unisoc PAC extractor, FDL HDLC/CRC-16 protocol, two-stage loader
- [`flashdock/core/diagnostics.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/diagnostics.py) — Debloater, hardware health, and tweaks engine
- [`flashdock/core/rom_flasher.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rom_flasher.py) — ROM, GSI, and Recovery flasher
- [`flashdock/core/return_stock.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/return_stock.py) — Factory image unpacker & stock return engine
- [`flashdock/core/repository.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/repository.py) — Local offline catalog for ROMs, GSIs, modules, root APKs, drivers
- [`flashdock/core/rooting.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/rooting.py) — Universal root solution coordinator
- [`flashdock/core/modules.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/modules.py) — Magisk/KSU/APatch module parser & installer
- [`flashdock/core/backup.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/backup.py) — Partition backup & restore manager
- [`flashdock/core/device.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/device.py) — Connected device model & state detector
- [`flashdock/core/safety.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/safety.py) — Pre-flight safety checks & criteria
- [`flashdock/core/network.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/core/network.py) — Network monitor for offline-mode dimming

### User Interface
- [`flashdock/ui/styles.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/styles.py) — Apple HIG Light & Dark stylesheets (`#F5F5F7` Athens Gray, `#1D1D1F` Shark, `#007AFF` System Blue)
- [`flashdock/ui/main_window.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/main_window.py) — Main window with elevation drop shadows, expanded margins, and dynamic theme switching
- [`flashdock/ui/widgets/phone_panel.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/phone_panel.py) — Soft sidebar styling
- [`flashdock/ui/widgets/device_selector.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/device_selector.py) — Apple HIG device selector
- [`flashdock/ui/widgets/status_bar.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/status_bar.py) — Apple HIG status bar
- [`flashdock/ui/widgets/side_terminal.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/widgets/side_terminal.py) — Real-time read-only side terminal
- [`flashdock/ui/screens/diagnostics_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/diagnostics_screen.py) — Diagnostics, debloater, tweaks screen
- [`flashdock/ui/screens/flash_rom_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/flash_rom_screen.py) — ROM, GSI, Recovery flasher screen
- [`flashdock/ui/screens/root_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/root_screen.py) — Root solutions screen
- [`flashdock/ui/screens/modules_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/modules_screen.py) — Modules screen
- [`flashdock/ui/screens/return_stock_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/return_stock_screen.py) — Return to stock screen
- [`flashdock/ui/screens/backup_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/backup_screen.py) — Backup & restore screen
- [`flashdock/ui/screens/mtk_unisoc_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/mtk_unisoc_screen.py) — MediaTek BROM and Unisoc PAC Flasher screen
- [`flashdock/ui/screens/downloads_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock/ui/screens/downloads_screen.py) — Downloads, Drivers & Tools Manager screen

### Distribution & Tests
- [`flashdock.spec`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/flashdock.spec) — PyInstaller spec file with MTK, Unisoc & Tools Manager hidden imports
- [`tests/test_tools_manager.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_tools_manager.py) — 10 unit tests for PlatformToolsManager, DriverManager, and FirmwareFinder
- [`tests/test_downloads_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_downloads_screen.py) — 4 UI tests for DownloadsScreen
- [`tests/test_mtk.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_mtk.py) — 6 unit tests for MTK BROM engine and scatter parser
- [`tests/test_unisoc.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_unisoc.py) — 4 unit tests for Unisoc PAC extractor and FDL protocol
- [`tests/test_mtk_unisoc_screen.py`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/test_mtk_unisoc_screen.py) — 5 UI tests for MtkUnisocScreen and navigation
- [`tests/`](file:///C:/Users/dxzmw/.gemini/antigravity-ide/scratch/FlashDock/tests/) — Full suite containing 316 passing tests

---

## 4. Current State & Verification

- **Standalone Executable**: Freshly recompiled into `dist/FlashDock/FlashDock.exe` (PyInstaller 6.22.3, Exit code 0).
- **PyTest Suite**: 316 passed in 12.44s (100% pass rate).
- **Apple HIG Styling**: Locked in across all components, widgets, and dialogs.
- **Eye-Friendly Dark Mode**: Text contrast softened from harsh stark `#FFFFFF`/`#F2F2F7` to `#D1D1D6` and `#E5E5EA` to eliminate halation and glare.
- **Phase 12 Complete**: Tools Manager, OEM Driver Installer & Firmware Repositories Finder integrated and fully active.
