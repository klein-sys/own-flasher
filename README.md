# ⚡ FlashDock

**Personal, one-click Android service toolbox for Windows.**

FlashDock handles rooting, bootloader unlocking, ROM flashing, firmware recovery, backup & restore, and returning to stock — all through a simple, safe GUI.  Pick an option and the tool does the needed steps with checks and confirmations before anything risky.

> ⚠️ **Warning:** This tool can modify your phone's firmware, which can void your warranty and, if done incorrectly, brick your phone. **Always test on a spare phone first.** FlashDock is for your own devices only — it does not support or include FRP bypass, IMEI modification, or carrier-lock bypass.

---

## Current Status — Phase 9 ✅

FlashDock now includes the **core service and flashing workflow**:

| Component | What it does |
|---|---|
| **Logger** | Rotating file logs, coloured console output, serial-number masking for safe export, structured action log for every flash command |
| **Config** | JSON-backed settings with typed properties, defaults merging, thread safety, and auto-flush |
| **Network monitor** | Background thread that detects online/offline status and updates the UI in real time |
| **Main window** | Dark-themed GUI with 13 main actions, Phone Control Panel, live status bar, and read-only side terminal |
| **Backup / Restore** | Partition backups with checksums and restore guards that reject simulated or unavailable captures |
| **Rooting** | Root-manager library and compatibility guidance; boot images must be patched by the verified upstream manager |
| **Return to Stock** | Safe firmware inspection, archive extraction, flashing order, wipe support, and strict relock gate |
| **ROM / GSI / Recovery** | ROM archive support, GSI/recovery flashing, FastbootD coordination, and local offline repository |
| **Constants** | Centralised paths, safety defaults, and brand/chipset/mode definitions |

Buttons lead to placeholder screens — the real functionality is built in Phases 2–16.

---

## Requirements

- **Windows 10/11** (64-bit)
- **Python 3.11+**
- **PySide6** (installed via pip)

## Quick Start

```bash
# 1. Clone or download this folder
cd FlashDock

# 2. Create a virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python main.py
```

## Running Tests

```bash
# From the FlashDock directory, with the venv active:
pytest tests/ -v
```

## Project Structure

```
FlashDock/
├── main.py                         # Entry point
├── requirements.txt                # Python dependencies
├── flashdock/
│   ├── __init__.py                 # Version and app name
│   ├── app.py                      # Application bootstrap
│   ├── config.py                   # Configuration manager (JSON)
│   ├── constants.py                # All hard-coded values
│   ├── core/
│   │   ├── network.py              # Online/offline detection
│   │   └── ...                     # (engine, device, safety — later phases)
│   ├── ui/
│   │   ├── main_window.py          # Main application window
│   │   ├── styles.py               # Dark QSS stylesheet
│   │   ├── widgets/
│   │   │   ├── status_bar.py       # Bottom status bar
│   │   │   └── phone_panel.py      # Left sidebar phone control panel
│   │   └── screens/                # (feature screens — later phases)
│   ├── brands/                     # (brand-specific modules — later phases)
│   ├── tools/                      # (ADB, fastboot, etc. wrappers — later phases)
│   ├── database/                   # (SQLite cache — later phases)
│   └── logger/
│       └── __init__.py             # Logger with rotation, masking, action log
├── data/                           # Runtime data (logs, cache, backups, profiles)
├── resources/                      # Icons, license files
└── tests/
    ├── test_logger.py
    ├── test_config.py
    └── test_network.py
```

## Build Phases

This project follows a 16-phase build order. Each phase is completed and tested before the next begins.

| # | Phase | Status |
|---|---|---|
| 1 | Foundation, logger, config, online/offline detection | ✅ Done |
| 2 | ADB/fastboot core, device detection, Phone Control Panel | ✅ Done |
| 3 | Checklist screen & PyInstaller Windows distribution | ✅ Done |
| 4 | Bootloader unlock wizard (brand-aware: Google, Xiaomi, Samsung, OnePlus, etc.) | ✅ Done |
| 5 | Safety engine (match check, checksum, anti-rollback) & Backup / Restore | ✅ Done |
| 6 | Rooting wizard (Magisk, KernelSU, APatch with GKI & ramdisk detection) | ✅ Done |
| 7 | Root module flasher, live management & bootloop recovery kill-switch | ✅ Done |
| 8 | Return to Stock & Strict Anti-Relock Gate (blocks bricks on modified/cross-region ROMs) | ✅ Done |
| 9 | ROM, GSI, and recovery flashers & Local ROM Repository | ✅ Done |
| 10 | MTK and Unisoc low-level mode (BROM, scatter, PAC) | 🔲 |
| 11 | Compatibility database & online updates | 🔲 |
| 12 | Play Integrity Fixer & fingerprint spoofer | 🔲 |
| 13 | Driver Fixer (Google, Samsung, QDLoader 9008, MTK, Unisoc) & 20 Service Tools | 🔲 |
| 14 | Final packaging & signed release distribution | 🔲 |
| 15 | End-to-end multi-device testing & documentation | 🔲 |
| 16 | Polishing & release hardening | 🔲 |

---

## 29. User Additions & Core Architectural Enhancements

The following user-requested capabilities have been merged into the plan and application architecture:

1. **Offline Button Shading & Auto-Disabling**:
   - When offline, buttons for online-only features (`Downloads & Updates`, `Fix Integrity`) are dimmed (`opacity: 0.45; dashed border`), unclickable (`ForbiddenCursor`), and annotated with a clear tooltip: `"[OFFLINE] Internet connection required"`.
   - Re-enabled automatically when connectivity is restored.

2. **Persistent Side Activity Terminal (Live Process Display)**:
   - A non-editable, read-only terminal panel (`SideTerminalWidget`) integrated directly onto the right-side dock.
   - Streams fastboot commands, adb operations, and detection events in real time without interfering with user interaction.

3. **OS Modification & Root Status Inspector**:
   - `DeviceCard` and `DeviceInfo` now actively diagnose phone modification state:
     - **OS Type**: `Stock OEM Firmware` vs `Custom ROM` (LineageOS, PixelExperience, crDroid, etc.) vs `Generic System Image (GSI)`.
     - **Root Status**: `Rooted (Magisk / KernelSU / APatch)` vs `Not Rooted`.

4. **Interactive "Workflow Guide"**:
   - A dedicated **"📖 Workflow Guide"** button in the header and Help menu opening an interactive modal walkthrough:
     - Explains the recommended safe workflow (Check ➔ Checklist ➔ Backup ➔ Unlock ➔ Root/ROM ➔ Integrity ➔ Return to Stock).
     - Explains all 13 core functions and their low-level mechanics.
     - Details Android Verified Boot (AVB), A/B seamless slots, dynamic Super partitions, and anti-brick rules.

5. **Local ROM & GSI Repository (`data/roms/`, `data/gsis/`)**:
   - Local storage for downloaded/imported ROMs and GSIs.
   - Compatibility filter highlights packages matching the connected phone's CPU architecture (`arm64-v8a` vs `arm`), slot scheme (`A/B` vs `A-only`), and codename.

6. **Local Root Apps & Modules Repository (`data/root_apps/`, `data/modules/`)**:
   - Persistent store for Magisk, KernelSU Manager, and APatch APKs plus downloaded ZIP modules, ready for 1-click selection and flashing.

7. **Local Driver Repository & Manager (`data/drivers/`)**:
   - Stores Windows USB drivers (Google ADB/Fastboot, Samsung USB, Xiaomi/Qualcomm QDLoader 9008, MTK VCOM, Unisoc SPD) for offline installation.

8. **Bundled & Managed 20 Service Tools (`data/tools/`)**:
   - Platform-tools (adb, fastboot, fastbootd, mke2fs), payload-dumper-go, magiskboot, avbtool, lpunpack, lpmake, simg2img, img2simg, apktool, scrcpy, MTKClient, SP Flash Tool, heimdall, edl.py.

---

## Safety Principles

- **Simple first:** Big buttons, plain language, step-by-step wizards.
- **Safe first:** Check, back up, confirm, flash, verify.
- **Honest:** Shows "unverified" instead of guessing. Never promises success.
- **Offline-capable:** Core tasks work without internet. Online data is cached.
- **Private:** All data stays local. Nothing is sent anywhere.

## License

MIT License — see `LICENSE` for details.
