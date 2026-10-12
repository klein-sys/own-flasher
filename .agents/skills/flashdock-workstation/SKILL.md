---
name: flashdock-workstation
description: Architectural standards, zero-brick safety protocols, multi-chipset hardware resolution, macOS Big Sur design tokens, and verification workflow for the FlashDock Android service workstation.
---

# FlashDock Architectural & Engineering Standard

Activate and adhere to this skill whenever developing, modifying, refactoring, or testing features in the FlashDock codebase.

---

## 1. Safety-First & Zero-Brick Guarantees

1. **Pre-Flight Operation Gates**:
   - Never write to device partitions without confirming battery charge ($\ge 30\%$), correct USB connection mode, and active partition slot (`_a` or `_b`).
   - If Fastboot reports an ambiguous or null slot on A/B devices, never guess: abort slot-specific flashing and prompt for verification.

2. **Mandatory Calibration Pre-Backups**:
   - Before executing any flash, rooting, or partition modification, dump telemetry/radio calibration blocks:
     - `efs`, `nvram`, `nvdata`, `persist`, `sec_efs`
   - Calculate and persist SHA-256 checksums to `data/backups/`.
   - Abort immediately if free disk space is under 2 GB or if backup verification fails.

3. **Anti-Rollback (ARP/AVB) & Anti-Relock Enforcements**:
   - Never allow bootloader relocking (`fastboot flashing lock`, `oem lock`) if a custom recovery, patched boot image, or cross-region firmware is installed.
   - Guard against downgrading boot/recovery images that blow hardware eFuses (Qualcomm QFUSE, Samsung Knox warranty bit 0x1).

---

## 2. Asynchronous Multi-Subsystem Architecture (`QThread`)

1. **Thread Separation**:
   - Never run blocking I/O, subprocess execution (`fastboot`, `adb`, `edl`), or registry polling on the PySide6 GUI thread.
   - Dedicated worker threads:
     - `DeviceMonitorWorker` (`flashdock/workers/device_monitor.py`): Zero-dependency Windows Registry polling for USB devices (`HKLM\SYSTEM\CurrentControlSet\Enum\USB`) and COM serial ports (`HKLM\HARDWARE\DEVICEMAP\SERIALCOMM`).
     - `FlashEngineWorker` (`flashdock/workers/flash_engine.py`): Chunked partition flashing, verification, and backup dumps.

2. **Thread Lifecycle & Cooperative Cancellation**:
   - Always implement graceful shutdowns using `self.requestInterruption()`, `self.isInterruptionRequested()`, and `with QMutexLocker(self._mutex):`.
   - Clean up subprocess child handles on worker interruption to avoid zombie processes.

3. **Multi-Chipset Hardware ID (VID/PID) Priority**:
   - Hardware detection priority must strictly follow:
     1. Emergency Low-Level Ports: MediaTek BROM (`0E8D:0003`), Qualcomm EDL 9008 (`05C6:9008`), Unisoc FDL (`1782:4D02`).
     2. Bootloader / Preloader: MTK Preloader (`0E8D:2000`), Fastboot / FastbootD (`18D1:D00D` / OEM IDs).
     3. User-Space Daemons: ADB (`18D1:4EE7`, `04E8:6860`), Diagnostic ports (`05C6:9006`, `1782:4D00`).

---

## 3. UI Design System (macOS Big Sur + Apple HIG)

1. **100% Vector SVG Icons (Zero Raw Emoji Stickers)**:
   - Never use unicode emoji characters (⚡, 🔒, 📱, ⚙️, 🚀, etc.) in UI labels, tabs, cards, or buttons.
   - All icons must be generated via `flashdock.ui.icon_assets.get_icon(name, size, color)`.
   - Always generate `QIcon` objects dynamically on demand to prevent C++ lifecycle teardown violations on Python 3.14.

2. **Ergonomic Color Palette & Contrast Hierarchy**:
   - **Light Mode**:
     - Window Canvas: Warm Slate-Mica (`#F0F2F5`) — avoids blinding pure white glare.
     - Cards / Containers: Elevated Soft Frost (`#F8F9FA`) with 1px border (`#DCE1E8`).
     - Sidebar / Panels: Distinct Slate-Blue tint (`#E9EEF5`).
     - Text: Deep Charcoal (`#1C2024`) and Muted Slate (`#5A6572`).
   - **Dark Mode**:
     - Window Canvas: Deep Space Obsidian (`#0D1117`) — avoids flat pitch-black voids.
     - Cards / Containers: Elevated Slate (`#181E26`) with 1px border (`#2C3644`).
     - Sidebar / Panels: Layered Dark Surface (`#141820`) with 1px border (`#252D38`).
     - Text: Soft Platinum (`#E6EDF3`) and Muted Steel (`#8B949E`).
   - **Console Terminal**: Deep Midnight (`#0B0E14`) with syntax-highlighted stream tags:
     - `[INFO]` Blue (`#007AFF` / `#58A6FF`)
     - `[WARN]` Amber (`#FF9500` / `#D29922`)
     - `[SUCCESS]` Green (`#34C759` / `#3FB950`)
     - `[ERROR]` Red (`#FF3B30` / `#F85149`)

---

## 4. Testing, Documentation & Release Discipline

1. **Test-Driven Modifications**:
   - Every core logic modification must be backed by unit tests under `tests/`.
   - Run the full suite with `python scripts/release_build.py` or `pytest`.
   - All tests must pass (baseline: 418+ tests passing).

2. **Triple-Sync Documentation**:
   - Whenever features, version tags, or test counts change, keep these 3 documents synchronized:
     - `README.md`
     - `read.md`
     - `handoff.md`
