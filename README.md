# FlashDock — Personal Android Service Workstation

[![Version](https://img.shields.io/badge/version-1.0.0-0A84FF.svg)](https://github.com/klein-sys/own-flasher)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(64--bit)-1D1D1F.svg)](https://github.com/klein-sys/own-flasher)
[![License](https://img.shields.io/badge/license-MIT-30D158.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-413%20%2F%20413%20passing-30D158.svg)](tests/)
[![Architecture](https://img.shields.io/badge/architecture-GSM%20Suite%20%2B%20macOS%20Big%20Sur-BF5AF2.svg)](flashdock/ui/styles.py)
[![UI Assets](https://img.shields.io/badge/vector%20graphics-100%25%20SVG%20%7C%20Apple%20HIG-FF9500.svg)](flashdock/ui/icon_assets.py)

**Personal, one-click Android service workstation for Windows.**

FlashDock handles rooting, bootloader unlocking, fastboot & custom ROM flashing, Samsung Odin tar extraction, Qualcomm EDL 9008 Sahara/Firehose rescue, MediaTek BROM scatter flashing, Unisoc PAC recovery, bootloop unbricking, Play Integrity spoofing, offline partition backup & restore, live screen mirroring (scrcpy), hardware button navigation, laptop setup assistance, and interactive troubleshooting — all through a clean, guided macOS Big Sur-inspired interface with multi-chipset repair tool architecture (UnlockTool, TFT, Chimera).

> **Safety Warning:** This tool modifies device firmware. Always back up your critical partitions before flashing. FlashDock is designed strictly for servicing your own devices and does not support carrier bypass, FRP bypass, or IMEI modifications.

---

## Current Status — GSM Suite Architecture & Vector Asset Overhaul (v1.0.0)

FlashDock features a fully modular, thread-safe, and asynchronous **GSM Suite Core Architecture** inspired by professional multi-chipset repair platforms:

### Five Major Workstation Subsystems:
1. **Connection Monitoring & Hardware Polling Engine (`device_monitor.py`)**:
   - Asynchronous `QThread` scanning USB/COM ports via zero-dependency Windows Registry enumeration.
   - Comprehensive Hardware ID (VID/PID) resolution: ADB, Fastboot, MediaTek BROM (`0E8D:0003`), MTK Preloader (`0E8D:2000`), Qualcomm EDL 9008 (`05C6:9008`), Qualcomm Diag (`05C6:9006`), Unisoc SPRD U2S Diag (`1782:4D00`), and FDL Download (`1782:4D02`).
   - Multi-tiered resolution prioritizing emergency recovery ports over standard user-space daemons.
2. **Device Diagnostics & Info Extraction Engine (`diagnostics_engine.py`)**:
   - Deep ADB property extraction: brand, model, manufacturer, build display, Android OS, baseband, security patch level, and battery level/temperature.
   - Root detection (`su` binary verification, Magisk/KSU version) and Samsung Knox warranty bit tracking.
   - Deep Fastboot `getvar all` parsing: active partition slot (`_a`/`_b`), bootloader unlocked status, Secure Boot state, CID, and max-download-size with structured fallback dictionaries.
3. **Firmware Flashing, Partition Management & Safety Backups (`flash_engine.py`)**:
   - Decoupled `QThread` external binary execution with byte-accurate progress reporting.
   - Mandatory calibration pre-backups targeting telemetry blocks (`efs`, `nvram`, `nvdata`, `persist`, `sec_efs`) with SHA-256 verification.
   - Chunked single-image flashing (`boot`, `init_boot`, `recovery`, `super`, `system`) with pre-flash checksum verification.
   - Bootloader unlock (`flashing unlock`, `oem unlock`) and relock controllers.
4. **Vector Icon Asset Manager & Image Provider (`icon_assets.py` & `brand_assets.py`)**:
   - Zero informal unicode emoji stickers in the UI. 100% vector SVG rendering adhering to Apple Human Interface Guidelines.
   - 37+ crisp, high-DPI icons (`search`, `checklist`, `warning`, `unlock`, `lock`, `root`, `flash`, `modules`, `diagnostics`, `integrity`, `backup`, `unbrick`, `return_stock`, `mtk_unisoc`, `scrcpy`, `downloads`, `logs_help`, `tools`, etc.) with dynamic tinting.
   - Clean, on-demand `QIcon` generation that prevents Qt C++ teardown access violations on Windows Python 3.14.
5. **UI Architecture & macOS Big Sur Styling (`main_window.py` & `styles.py`)**:
   - Top Segmented Bar for high-volume OEMs (Xiaomi, Samsung, Transsion, Universal Android) and Universal Chipsets (MediaTek BROM, Qualcomm EDL, Unisoc SPRD).
   - Left Operations Panel: Device Diagnostics, Partition Backup, Flash Firmware, Bootloader Tools, and Reboot Shortcuts.
   - Right Console Pane: Persistent read-only terminal with color-coded stream prefixes (`[INFO]` in Blue, `[WARN]` in Amber, `[SUCCESS]` in Green, `[ERROR]` in Red).
   - Bottom Status Bar: Persistent USB connection badge and smooth `QProgressBar`.
   - Authentic macOS Big Sur design tokens: `#F5F5F7` canvas, `#FFFFFF` rounded containers with subtle borders, `#007AFF` accent, and SF Pro typography hierarchy.

| # | Phase / Feature | Domain | Status | Key Deliverables |
|---|---|---|---|---|
| 1 | **Foundation & Architecture** | Core | Done | Rotating logger, thread-safe config, online/offline monitor, serial masking |
| 2 | **ADB & Fastboot Engine** | Device | Done | Subprocess wrappers, fastboot device tracking, Phone Control Panel |
| 3 | **Safety Checklist & Distribution** | Rescue | Done | Pre-flight safety checklist, battery/lock gates, PyInstaller build spec |
| 4 | **Bootloader Unlock Wizard** | Flashing | Done | Brand-specific unlock guides: Google Pixel, Xiaomi (token countdown), Samsung, Tecno (HiOS), Infinix (XOS), itel (itelOS), OnePlus, Motorola |
| 5 | **Partition Backup & Restore** | Rescue | Done | Slot-aware partition backups (`boot`, `init_boot`, `vbmeta`, `efs`, `persist`) with SHA-256 verification |
| 6 | **Universal Rooting Wizard** | Root | Done | Magisk (Stable/Alpha), KernelSU Next, APatch, SukiSU; boot extraction & auto-patching |
| 7 | **Root Modules & Kill-Switch** | Root | Done | Offline module repository, batch flashing, emergency bootloop recovery kill-switch |
| 8 | **Return to Stock & Anti-Relock Gate** | Flashing | Done | Factory image unpacker (Google, Xiaomi TGZ, Samsung TAR/MD5); strict anti-rollback check |
| 9 | **ROM, GSI & Recovery Flasher** | Flashing | Done | Fastboot ROM package parser, sparse chunk flasher, Treble GSI flasher, FastbootD switcher |
| 10 | **Diagnostics, Debloater & Tweaks** | Device | Done | Package manager debloater (safe user-0 disable), battery health telemetry, wireless ADB |
| 11 | **MediaTek & Unisoc Engine** | Flashing | Done | MTK BROM scatter parser, SLA/DAA auth bypass, Unisoc PAC extractor, FDL HDLC protocol |
| 12 | **Downloads & OEM Driver Manager** | Device | Done | Driver installer (Google, Samsung, Qualcomm 9008, MTK VCOM, Transsion USB, Unisoc SPD), platform-tools downloader |
| 13 | **Emergency Unbrick & EDL Flasher** | Rescue | Done | Qualcomm Emergency Download (EDL 9008), Samsung Odin PIT/TAR, MTK SP Flash, Fastboot unbrick |
| 14 | **Play Integrity & Fingerprint Spoofer** | Root | Done | PIF `pif.json` manager, custom `keybox.xml` injector, banking root-hiding card grid |
| 15 | **Logs, Telemetry & Troubleshooting** | Device | Done | Rotating application log viewer, device logcat streamer, kernel dmesg, guided interactive triage |
| 16 | **Production Hardening & Release** | Release | Done | Automated System Self-Test, non-fatal Crash Reporter, release packaging & SHA-256 checksums |
| 17 | **GSM Suite Core Subsystems** | Core / UI | Done | 4-subsystem engine (Hardware Polling QThread, Deep Diagnostics, FlashEngineWorker, macOS Big Sur UI) |
| 18 | **Vector SVG Icon Architecture** | UI / UX | Done | Centralized vector SVG asset engine, 100% unicode emoji sticker elimination across 13 screens and 11 widgets |
| + | **Transsion Brands Engine** | Brands | Done | Complete handlers for Tecno (HiOS), Infinix (XOS), itel (itelOS), and Carlcare firmware portal |
| + | **Vector Brand Badges** | UI / UX | Done | Pixel-perfect vector SVG brand logos (Google, Samsung, Xiaomi, Tecno, Infinix, itel, etc.) |
| + | **Smart Connection & Keys Helper** | Controls | Done | Interactive sidebar connection troubleshooter (USB debugging/RSA key) & contextual Hardware Key Guide |
| + | **Laptop Setup Wizard** | Workstation | Done | 4-step wizard for platform-tools, OEM drivers, laptop USB power/sleep settings & live test |

---

## Complete Workstation Navigation Matrix

FlashDock organizes its 15 workstation utilities across four curated categories:

```
FlashDock Workstation
├── Root & Modules
│   ├── Root my phone (Magisk, KernelSU, APatch, SukiSU)
│   ├── Manage Modules (Batch install, repository, kill-switch)
│   └── Fix Play Integrity (PIF spoofing, keybox injection, banking protection)
├── Flashing & ROMs
│   ├── Unlock Bootloader (Multi-brand wizards & fastboot)
│   ├── Return to Stock (Factory images & anti-relock protection)
│   ├── Flash ROM / GSI (Fastboot ROMs, GSIs, TWRP/OrangeFox)
│   └── MTK / Unisoc mode (BROM scatter & PAC flasher)
├── Rescue & Unbrick
│   ├── Safety Checklist (Pre-flight hardware verification)
│   ├── Backup / Restore (Critical partition image dumps)
│   └── Fix bricked phone (Qualcomm 9008 EDL, Odin, SP Flash)
└── Device & Tools
    ├── Check my phone (Hardware properties, slot, OS detection)
    ├── Diagnostics & Tweaks (Debloater, battery health, wireless ADB)
    ├── Downloads & Tools (Platform-tools, USB drivers, firmware finder)
    ├── Screen Mirror (Live scrcpy display & keyboard/touch control)
    ├── Logs & Help (Application telemetry, logcat streamer, triage)
    ├── Setup Laptop (Platform-tools, USB drivers, laptop power setup)
    ├── Key Guide (Physical Vol+/Vol-/Power combinations & remote)
    └── Self-Test (Prerequisites, toolchain, & permission diagnostics)
```

---

## Visual Design System (Apple Human Interface Guidelines)

FlashDock is built with a refined Apple HIG aesthetic:
- **Eye-Friendly Canvas**: Soothing Athens Gray (`#F5F5F7` in light mode, `#000000`/`#1C1C1E` in dark mode).
- **High-DPI Vector Icons**: Native SVG rendering replaces emoji stickers with crisp iconography scaled smoothly to any display DPI.
- **Elevated Surfaces**: 10–12px rounded cards with subtle drop shadows (`QGraphicsDropShadowEffect`).
- **Interactive System Blue**: Standard Apple `#007AFF` accent for active selections and primary triggers.
- **Side Activity Terminal**: Non-editable, read-only terminal continuously displaying executing commands and stdout without allowing accidental edits.
- **Offline Shading**: When internet connectivity drops, cloud-dependent buttons automatically dim (`opacity: 0.45; dashed border`) and update tooltips to `"[OFFLINE] Internet connection required"`.

---

## Getting Started

### Option A: Standalone Windows Binary (Recommended)
Download the standalone precompiled release from `dist/`:
1. Extract `FlashDock-v1.0.0-windows-x64.zip`.
2. Run `FlashDock.exe`. No Python installation required!
3. Verify integrity against `dist/SHA256SUMS.txt`.

### Option B: Run from Source
```powershell
# 1. Clone repository
git clone https://github.com/klein-sys/own-flasher.git
cd own-flasher

# 2. Set up virtual environment
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch FlashDock
python main.py
```

### Running Tests
```powershell
python scripts/release_build.py
# 413 passed in 27.07s (100% success rate)
```

---

## Safety Principles

1. **Pre-Flight Hardware Checks**: Operations verify battery charge ($\ge 30\%$), correct USB connection mode, and active slot.
2. **Strict Anti-Relock Gate**: Prevents users from relocking bootloaders on modified, custom, or cross-region ROMs to prevent permanent bricks.
3. **Serial Number Privacy**: All log exports and crash reports automatically mask device serial numbers (`[SERIAL]`) and username paths (`[USER]`).
4. **Local-First Architecture**: Firmware, drivers, modules, and cache files stay entirely on your local workstation.

---

## License

Distributed under the **MIT License**. See `LICENSE` for details.
