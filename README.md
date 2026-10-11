# ⚡ FlashDock — Personal Android Service Workstation

[![Version](https://img.shields.io/badge/version-1.0.0-0A84FF.svg)](https://github.com/klein-sys/own-flasher)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011%20(64--bit)-1D1D1F.svg)](https://github.com/klein-sys/own-flasher)
[![License](https://img.shields.io/badge/license-MIT-30D158.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-378%20%2F%20378%20passing-30D158.svg)](tests/)
[![Architecture](https://img.shields.io/badge/design-Apple%20HIG%20Aesthetics-BF5AF2.svg)](flashdock/ui/styles.py)

**Personal, one-click Android service workstation for Windows.**

FlashDock handles rooting, bootloader unlocking, fastboot & custom ROM flashing, Samsung Odin tar extraction, Qualcomm EDL 9008 Sahara/Firehose rescue, MediaTek BROM scatter flashing, Unisoc PAC recovery, bootloop unbricking, Play Integrity spoofing, offline partition backup & restore, live screen mirroring (scrcpy), and interactive troubleshooting — all through a clean, guided Apple Human Interface Guidelines (HIG) desktop GUI.

> ⚠️ **Safety Warning:** This tool modifies device firmware. Always back up your critical partitions before flashing. FlashDock is designed strictly for servicing your own devices and does not support carrier bypass, FRP bypass, or IMEI modifications.

---

## 🏆 Current Status — Phase 16 Complete (v1.0.0 Release) ✅

FlashDock has achieved **100% completion across all 16 planned engineering phases**. Every tool is implemented, tested with 378 automated test cases, and packaged into a standalone Windows distribution.

| # | Phase | Domain | Status | Key Deliverables |
|---|---|---|---|---|
| 1 | **Foundation & Architecture** | Core | ✅ Done | Rotating logger, thread-safe config, online/offline monitor, serial masking |
| 2 | **ADB & Fastboot Engine** | Device | ✅ Done | Subprocess wrappers, fastboot device tracking, Phone Control Panel |
| 3 | **Safety Checklist & Distribution** | Rescue | ✅ Done | Pre-flight safety checklist, battery/lock gates, PyInstaller build spec |
| 4 | **Bootloader Unlock Wizard** | Flashing | ✅ Done | Brand-specific unlock guides: Google Pixel, Xiaomi (token countdown), Samsung, OnePlus, Motorola |
| 5 | **Partition Backup & Restore** | Rescue | ✅ Done | Slot-aware partition backups (`boot`, `init_boot`, `vbmeta`, `efs`, `persist`) with SHA-256 verification |
| 6 | **Universal Rooting Wizard** | Root | ✅ Done | Magisk (Stable/Alpha), KernelSU Next, APatch, SukiSU; boot extraction & auto-patching |
| 7 | **Root Modules & Kill-Switch** | Root | ✅ Done | Offline module repository, batch flashing, emergency bootloop recovery kill-switch |
| 8 | **Return to Stock & Anti-Relock Gate** | Flashing | ✅ Done | Factory image unpacker (Google, Xiaomi TGZ, Samsung TAR/MD5); strict anti-rollback check |
| 9 | **ROM, GSI & Recovery Flasher** | Flashing | ✅ Done | Fastboot ROM package parser, sparse chunk flasher, Treble GSI flasher, FastbootD switcher |
| 10 | **Diagnostics, Debloater & Tweaks** | Device | ✅ Done | Package manager debloater (safe user-0 disable), battery health telemetry, wireless ADB |
| 11 | **MediaTek & Unisoc Engine** | Flashing | ✅ Done | MTK BROM scatter parser, SLA/DAA auth bypass, Unisoc PAC extractor, FDL HDLC protocol |
| 12 | **Downloads & OEM Driver Manager** | Device | ✅ Done | Driver installer (Google, Samsung, Qualcomm 9008, MTK, Unisoc), platform-tools downloader |
| 13 | **Emergency Unbrick & EDL Flasher** | Rescue | ✅ Done | Qualcomm Emergency Download (EDL 9008), Samsung Odin PIT/TAR, MTK SP Flash, Fastboot unbrick |
| 14 | **Play Integrity & Fingerprint Spoofer** | Root | ✅ Done | PIF `pif.json` manager, custom `keybox.xml` injector, Google Play Integrity attestation guides |
| 15 | **Logs, Telemetry & Troubleshooting** | Device | ✅ Done | Rotating application log viewer, device logcat streamer, kernel dmesg, guided interactive triage |
| 16 | **Production Hardening & Release** | Release | ✅ Done | Automated System Self-Test, non-fatal Crash Reporter, release packaging & SHA-256 checksums |

---

## 🧭 Complete Workstation Navigation Matrix

FlashDock organizes its 15 workstation utilities across four curated categories:

```
FlashDock Workstation
├── 🌱 Root & Modules
│   ├── Root my phone (Magisk, KernelSU, APatch, SukiSU)
│   ├── Manage Modules (Batch install, repository, kill-switch)
│   └── Fix Play Integrity (PIF spoofing, keybox injection)
├── 💾 Flashing & ROMs
│   ├── Unlock Bootloader (Multi-brand wizards & fastboot)
│   ├── Return to Stock (Factory images & anti-relock protection)
│   ├── Flash ROM / GSI (Fastboot ROMs, GSIs, TWRP/OrangeFox)
│   └── MTK / Unisoc mode (BROM scatter & PAC flasher)
├── 🚑 Rescue & Unbrick
│   ├── Safety Checklist (Pre-flight hardware verification)
│   ├── Backup / Restore (Critical partition image dumps)
│   └── Fix bricked phone (Qualcomm 9008 EDL, Odin, SP Flash)
└── 🩺 Device & Tools
    ├── Check my phone (Hardware properties, slot, OS detection)
    ├── Diagnostics & Tweaks (Debloater, battery health, wireless ADB)
    ├── Downloads & Tools (Platform-tools, USB drivers, firmware finder)
    ├── Screen Mirror (Live scrcpy display & keyboard/touch control)
    ├── Logs & Help (Application telemetry, logcat streamer, triage)
    └── ⚡ Self-Test (Prerequisites, toolchain, & permission diagnostics)
```

---

## 🎨 Visual Design System (Apple Human Interface Guidelines)

FlashDock is built with a refined Apple HIG aesthetic:
- **Eye-Friendly Canvas**: Soothing Athens Gray (`#F5F5F7` in light mode, `#000000`/`#1C1C1E` in dark mode).
- **Elevated Surfaces**: 10–12px rounded cards with subtle drop shadows (`QGraphicsDropShadowEffect`).
- **Interactive System Blue**: Standard Apple `#007AFF` accent for active selections and primary triggers.
- **Side Activity Terminal**: Non-editable, read-only terminal continuously displaying executing commands and stdout without allowing accidental edits.
- **Offline Shading**: When internet connectivity drops, cloud-dependent buttons automatically dim (`opacity: 0.45; dashed border`) and update tooltips to `"[OFFLINE] Internet connection required"`.

---

## 🚀 Getting Started

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
python -m pytest tests/ -v
# 378 passed in 40.35s (100% success rate)
```

### Building Release Package
```powershell
python scripts/release_build.py
```

---

## 🔒 Safety Principles

1. **Pre-Flight Hardware Checks**: Operations verify battery charge ($\ge 30\%$), correct USB connection mode, and active slot.
2. **Strict Anti-Relock Gate**: Prevents users from relocking bootloaders on modified, custom, or cross-region ROMs to prevent permanent bricks.
3. **Serial Number Privacy**: All log exports and crash reports automatically mask device serial numbers (`[SERIAL]`) and username paths (`[USER]`).
4. **Local-First Architecture**: Firmware, drivers, modules, and cache files stay entirely on your local workstation.

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
