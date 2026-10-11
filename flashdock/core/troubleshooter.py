"""
FlashDock — Interactive Troubleshooter & Telemetry Core (Phase 15).

Provides diagnostics, automated recovery helpers, and structured troubleshooting
knowledge for device connection, driver, bootloop, and security problems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
import os
from pathlib import Path
import subprocess
from typing import Optional

from flashdock.constants import LOGS_DIR
from flashdock.logger import get_logger, mask_serials
from flashdock.tools.adb import ADB

log = get_logger("troubleshooter")


@dataclass
class TroubleshootingItem:
    """Guided symptom, diagnostic explanation, and actionable fixes."""

    id: str
    icon: str
    title: str
    symptom: str
    causes: list[str]
    steps: list[str]
    quick_action_id: str = ""
    quick_action_label: str = ""
    navigation_target: Optional[int] = None  # Stack page index if applicable


TROUBLESHOOTING_CATALOG: list[TroubleshootingItem] = [
    TroubleshootingItem(
        id="device_not_detected",
        icon="🔌",
        title="Phone Not Detected (ADB)",
        symptom="FlashDock or ADB shows 'No device connected' even after plugging in USB cable.",
        causes=[
            "USB Debugging is not enabled on the phone in Developer Options.",
            "Phone is in 'Charging Only' mode instead of 'File Transfer (MTP)'.",
            "Missing OEM USB driver or Windows has an exclamation mark in Device Manager.",
            "Faulty or charge-only USB cable, or front panel USB hub power drop.",
            "ADB daemon is hung or conflicting with another process (e.g. emulator, scrcpy).",
        ],
        steps=[
            "1. Unlock phone > Settings > About phone > tap 'Build Number' 7 times.",
            "2. Settings > Developer options > enable 'USB Debugging'.",
            "3. Plug into a rear USB port directly connected to your motherboard.",
            "4. Check phone screen for 'Allow USB debugging?' prompt and check 'Always allow'.",
            "5. Click 'Restart ADB Server' below to reset the connection pipe.",
        ],
        quick_action_id="restart_adb",
        quick_action_label="🔄 Restart ADB Server",
    ),
    TroubleshootingItem(
        id="fastboot_waiting",
        icon="⚡",
        title="Fastboot Says '<waiting for any device>'",
        symptom="Fastboot commands freeze or device is not recognized in Bootloader mode.",
        causes=[
            "Missing 'Android Bootloader Interface' driver in Windows.",
            "Device booted into stock recovery or EDL mode instead of Fastboot.",
            "AMD Ryzen USB 3.0 / 3.1 chipset bug (often resolves on USB 2.0 ports).",
        ],
        steps=[
            "1. Open Windows Device Manager and look for 'Android' with a yellow warning.",
            "2. Go to FlashDock's Downloads & Tools screen to install Google Universal ADB/Fastboot driver.",
            "3. Try connecting via a USB 2.0 port or through an unpowered USB 2.0 hub (fixes Ryzen USB 3.0 dropouts).",
        ],
        quick_action_id="open_device_manager",
        quick_action_label="🗂️ Open Windows Device Manager",
        navigation_target=11,  # PAGE_DOWNLOADS
    ),
    TroubleshootingItem(
        id="bootloop_rescue",
        icon="🚑",
        title="Phone Stuck in Bootloop (Restart Loop)",
        symptom="Device continuously restarts at boot animation or reboots straight into fastboot/recovery.",
        causes=[
            "Incompatible Magisk/KernelSU module or Xposed/LSPosed hook.",
            "AVB 2.0 / dm-verity signature corruption after flashing patched boot.img.",
            "Failed OTA update corrupted active A/B slot partition.",
            "Stale Dalvik bytecode or incompatible GSI vendor overlay.",
        ],
        steps=[
            "1. Launch FlashDock's dedicated Fix Bricked Phone & Bootloop Rescue screen.",
            "2. Use 'Kill Buggy Root Modules' to disable bad modules without wiping data.",
            "3. If device is in Fastboot, switch active slot from A to B or flash vbmeta disable-verity.",
        ],
        quick_action_id="goto_unbrick",
        quick_action_label="🚑 Open Bootloop Rescue",
        navigation_target=12,  # PAGE_UNBRICK
    ),
    TroubleshootingItem(
        id="play_integrity_fail",
        icon="🛡️",
        title="Google Play Integrity / Banking App Block",
        symptom="Google Wallet, PayPal, banking apps, or Netflix fail or report rooted / modified system.",
        causes=[
            "Bootloader is unlocked and Google Play Services detects hardware attestation failure.",
            "Device fingerprint lacks CTS certification or security patch date mismatch.",
            "Magisk / Zygisk binaries exposed to target app process.",
        ],
        steps=[
            "1. Open FlashDock's 'Fix Play Integrity' screen.",
            "2. Select a verified certified fingerprint (e.g. Pixel 5 or POCO F1 with FIRST_API_LEVEL <= 32).",
            "3. Click 'Apply & Inject pif.json' — FlashDock automatically flushes GMS cache.",
            "4. Add your banking apps to Magisk DenyList in Tab 2.",
        ],
        quick_action_id="goto_integrity",
        quick_action_label="🛡️ Open Play Integrity Fixer",
        navigation_target=13,  # PAGE_INTEGRITY
    ),
    TroubleshootingItem(
        id="xiaomi_wait_time",
        icon="⏳",
        title="Xiaomi / POCO 168-Hour Unlock Wait",
        symptom="Mi Flash Unlock reports error 20036: 'Please unlock 168 hours later'.",
        causes=[
            "Xiaomi enforces an mandatory server-side security cooldown timer on Mi Accounts.",
            "Cooldown is tracked entirely on Xiaomi servers, not on the phone.",
        ],
        steps=[
            "1. Keep your Mi Account signed in and SIM card active with mobile data.",
            "2. Do NOT factory reset, flash other firmware, or log out of Mi Account during the 168 hours (timer resets!).",
            "3. Once the 7-day cooldown expires, rerun the unlock procedure.",
        ],
    ),
    TroubleshootingItem(
        id="samsung_knox_trip",
        icon="🔒",
        title="Samsung Knox Warranty Bit 0x1 (Permanent Trip)",
        symptom="Flashing custom recovery (TWRP) or Magisk on Samsung displays 'Warranty Void: 0x1'.",
        causes=[
            "Samsung devices feature a physical hardware eFuse (Knox bit).",
            "Once a non-official boot image is loaded, hardware fuse blows permanently.",
        ],
        steps=[
            "1. Knox 0x1 CANNOT be reset back to 0x0 by software or flashing stock firmware.",
            "2. Knox-dependent features (Samsung Pay, Secure Folder, Samsung Pass) are disabled permanently.",
            "3. Alternative: Use Google Wallet (working with Play Integrity Fix) instead of Samsung Pay.",
        ],
    ),
]


class TroubleshooterManager:
    """Handles troubleshooting actions, log capture, and diagnostics."""

    def __init__(self, adb: Optional[ADB] = None) -> None:
        self.adb = adb or ADB()

    def restart_adb(self) -> tuple[bool, str]:
        """Kill running ADB server and restart it cleanly."""
        try:
            # Kill server
            kill_res = self.adb.kill_server()
            # Start server
            start_res = self.adb.start_server()
            if start_res.success:
                return True, "Successfully restarted ADB server. Check device connection now."
            return False, f"Failed to restart ADB server:\n{start_res.stderr or start_res.stdout}"
        except Exception as exc:
            log.error("Failed to restart ADB: %s", exc)
            return False, f"Exception while restarting ADB: {exc}"

    def open_device_manager(self) -> tuple[bool, str]:
        """Launch Windows Device Manager (devmgmt.msc)."""
        try:
            subprocess.Popen(["devmgmt.msc"], shell=True)
            return True, "Launched Windows Device Manager."
        except Exception as exc:
            return False, f"Could not launch Device Manager: {exc}"

    def open_logs_folder(self) -> tuple[bool, str]:
        """Open FlashDock logs directory in Windows Explorer."""
        try:
            LOGS_DIR.mkdir(parents=True, exist_ok=True)
            os.startfile(str(LOGS_DIR))
            return True, f"Opened {LOGS_DIR}"
        except Exception as exc:
            return False, f"Could not open logs folder: {exc}"

    def capture_logcat(
        self,
        serial: str,
        buffer_name: str = "main",
        lines: int = 300,
        filter_spec: str = "",
    ) -> tuple[bool, str]:
        """Capture tail lines from device logcat buffer."""
        if not serial:
            return False, "No device connected."

        cmd = f"logcat -b {buffer_name} -d -t {lines}"
        if filter_spec.strip():
            cmd += f" {filter_spec.strip()}"

        res = self.adb.shell(cmd, serial=serial, timeout=15)
        if res.success:
            return True, res.stdout
        return False, res.stderr or "Logcat capture failed."

    def capture_dmesg(self, serial: str) -> tuple[bool, str]:
        """Capture kernel ring buffer / dmesg."""
        if not serial:
            return False, "No device connected."

        res = self.adb.shell("dmesg 2>/dev/null || cat /proc/kmsg 2>/dev/null", serial=serial, timeout=10)
        if res.success and res.stdout.strip():
            return True, res.stdout
        return False, "Could not read kernel logs (dmesg requires root or permissive SELinux on Android 10+)."

    def clear_device_logcat(self, serial: str) -> tuple[bool, str]:
        """Clear device logcat circular buffer."""
        if not serial:
            return False, "No device connected."

        res = self.adb.shell("logcat -c", serial=serial, timeout=10)
        if res.success:
            return True, "Device logcat buffer cleared."
        return False, res.stderr or "Could not clear logcat buffer."

    def list_log_files(self) -> list[Path]:
        """Return list of historical FlashDock log files sorted newest first."""
        if not LOGS_DIR.exists():
            return []
        files = list(LOGS_DIR.glob("flashdock_*.log"))
        files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return files
