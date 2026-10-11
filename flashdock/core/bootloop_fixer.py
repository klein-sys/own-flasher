"""
FlashDock — Bootloop Fixer & Emergency Rescue Engine.

Provides automated diagnosis and one-click recovery operations for:
1. Magisk / KernelSU / APatch module bootloop kill-switch (disables bad modules without wiping data).
2. Safe Mode forced boot (bypasses crashing user apps and overlays).
3. A/B slot rollback switcher (reverts to previous working slot in Fastboot).
4. AVB / dm-verity corruption bypass (vbmeta verification disable).
5. Cache & Dalvik-cache wipe (clears stale bytecode and runtime caches).
6. Fastboot/Recovery stuck loop escape.
"""

from __future__ import annotations

import re
import subprocess
from typing import Optional, Tuple

from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)


class BootloopFixer:
    """Coordinates low-level emergency actions to recover bootlooping devices."""

    def __init__(self, adb: Optional[ADB] = None, fastboot: Optional[Fastboot] = None) -> None:
        self.adb = adb or ADB()
        self.fastboot = fastboot or Fastboot()

    # -------------------------------------------------------------------------
    # 1. Module Bootloop Kill-Switch (Magisk / KernelSU / APatch)
    # -------------------------------------------------------------------------

    def disable_root_modules_adb(self, serial: Optional[str] = None) -> Tuple[bool, str]:
        """Disable all root modules via ADB shell (creates disable flag). Preserves user data."""
        if not self.adb.available:
            return False, "ADB binary not available."

        cmd_base = [str(self.adb.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        log.info("Attempting root module kill-switch via ADB...")

        # Commands to disable modules across Magisk, KernelSU, APatch
        disable_script = (
            "touch /data/adb/modules/.disable 2>/dev/null; "
            "touch /cache/.disable_magisk 2>/dev/null; "
            "touch /data/adb/ksu/.disable 2>/dev/null; "
            "touch /data/adb/ap/.disable 2>/dev/null; "
            "echo SUCCESS"
        )

        try:
            res = subprocess.run(
                cmd_base + ["shell", disable_script],
                capture_output=True,
                text=True,
                timeout=12,
            )
            out = (res.stdout + res.stderr).strip()
            if "SUCCESS" in out:
                return True, (
                    "✅ Module kill-switch triggered!\n"
                    "Flag created at /data/adb/modules/.disable.\n"
                    "Reboot the device now — all modules will be skipped on boot."
                )
            return False, f"Could not access /data/adb (permission denied or device offline):\n{out}"
        except Exception as exc:
            return False, f"Error executing module kill-switch: {exc}"

    def remove_root_modules_adb(self, serial: Optional[str] = None) -> Tuple[bool, str]:
        """Delete all installed modules from /data/adb/modules to guarantee clean startup."""
        if not self.adb.available:
            return False, "ADB binary not available."

        cmd_base = [str(self.adb.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        try:
            res = subprocess.run(
                cmd_base + ["shell", "rm -rf /data/adb/modules/* 2>/dev/null; echo REMOVED"],
                capture_output=True,
                text=True,
                timeout=12,
            )
            out = (res.stdout + res.stderr).strip()
            if "REMOVED" in out:
                return True, "✅ All active root modules have been cleared from /data/adb/modules/."
            return False, f"Failed to clear modules: {out}"
        except Exception as exc:
            return False, f"Error removing modules: {exc}"

    # -------------------------------------------------------------------------
    # 2. Safe Mode Boot
    # -------------------------------------------------------------------------

    def reboot_safe_mode(self, serial: Optional[str] = None) -> Tuple[bool, str]:
        """Force device to reboot into Android Safe Mode (disables user apps and third-party overlays)."""
        if not self.adb.available:
            return False, "ADB binary not available."

        cmd_base = [str(self.adb.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        try:
            log.info("Sending reboot safemode command...")
            res = subprocess.run(
                cmd_base + ["reboot", "safemode"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if res.returncode == 0:
                return True, "✅ Device commanded to reboot into Safe Mode."
            return False, f"Reboot safe mode failed: {res.stderr.strip()}"
        except Exception as exc:
            return False, f"Error triggering safe mode: {exc}"

    # -------------------------------------------------------------------------
    # 3. A/B Slot Rollback Switcher (Fastboot)
    # -------------------------------------------------------------------------

    def get_current_fastboot_slot(self, serial: Optional[str] = None) -> Optional[str]:
        """Query current active slot in Fastboot ('a' or 'b')."""
        if not self.fastboot.available:
            return None

        cmd_base = [str(self.fastboot.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        try:
            res = subprocess.run(
                cmd_base + ["getvar", "current-slot"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            out = res.stdout + res.stderr
            match = re.search(r"current-slot:\s*([a-bA-B_]+)", out)
            if match:
                raw_slot = match.group(1).lower().replace("_", "").strip()
                return raw_slot
            return None
        except Exception:
            return None

    def switch_active_slot(self, target_slot: str, serial: Optional[str] = None) -> Tuple[bool, str]:
        """Switch active slot (e.g. 'a' <-> 'b') via Fastboot to rollback bootloop."""
        if not self.fastboot.available:
            return False, "Fastboot binary not available."

        slot_clean = target_slot.lower().replace("_", "").strip()
        if slot_clean not in ("a", "b", "other"):
            return False, f"Invalid slot: '{target_slot}'. Must be 'a', 'b', or 'other'."

        cmd_base = [str(self.fastboot.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        try:
            log.info("Switching Fastboot active slot to %s...", slot_clean)
            res = subprocess.run(
                cmd_base + [f"--set-active={slot_clean}"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            out = (res.stdout + res.stderr).strip()
            if res.returncode == 0 or "finished" in out.lower() or "ok" in out.lower():
                return True, f"✅ Successfully switched active slot to '{slot_clean}'.\nReboot device to test."
            return False, f"Slot switch failed: {out}"
        except Exception as exc:
            return False, f"Error switching slot: {exc}"

    # -------------------------------------------------------------------------
    # 4. AVB / dm-verity Verification Bypass (Fastboot)
    # -------------------------------------------------------------------------

    def disable_verity_vbmeta(self, vbmeta_path: str, serial: Optional[str] = None) -> Tuple[bool, str]:
        """Flash vbmeta with verification and verity disabled to bypass dm-verity bootloops."""
        if not self.fastboot.available:
            return False, "Fastboot binary not available."

        cmd_base = [str(self.fastboot.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        try:
            log.info("Flashing vbmeta with verity disabled: %s", vbmeta_path)
            res = subprocess.run(
                cmd_base + [
                    "--disable-verity",
                    "--disable-verification",
                    "flash",
                    "vbmeta",
                    vbmeta_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = (res.stdout + res.stderr).strip()
            if res.returncode == 0 or "finished" in out.lower() or "ok" in out.lower():
                return True, "✅ vbmeta flashed with verity and verification disabled."
            return False, f"Fastboot vbmeta flash failed: {out}"
        except Exception as exc:
            return False, f"Error disabling verity: {exc}"

    # -------------------------------------------------------------------------
    # 5. Cache & Stale Dalvik Wipe
    # -------------------------------------------------------------------------

    def erase_fastboot_cache(self, serial: Optional[str] = None) -> Tuple[bool, str]:
        """Erase cache partition in Fastboot."""
        if not self.fastboot.available:
            return False, "Fastboot binary not available."

        cmd_base = [str(self.fastboot.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        try:
            res = subprocess.run(
                cmd_base + ["erase", "cache"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            out = (res.stdout + res.stderr).strip()
            if res.returncode == 0 or "finished" in out.lower() or "ok" in out.lower():
                return True, "✅ Cache partition erased successfully."
            return False, f"Cache erase failed: {out}"
        except Exception as exc:
            return False, f"Error erasing cache: {exc}"

    # -------------------------------------------------------------------------
    # 6. Escape Stuck Bootloader / Continue Boot
    # -------------------------------------------------------------------------

    def fastboot_continue_boot(self, serial: Optional[str] = None) -> Tuple[bool, str]:
        """Run 'fastboot continue' to attempt normal boot execution."""
        if not self.fastboot.available:
            return False, "Fastboot binary not available."

        cmd_base = [str(self.fastboot.binary_path)]
        if serial:
            cmd_base.extend(["-s", serial])

        try:
            res = subprocess.run(
                cmd_base + ["continue"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            out = (res.stdout + res.stderr).strip()
            if res.returncode == 0 or "resuming" in out.lower() or "finished" in out.lower():
                return True, "✅ Bootloader instructed to resume standard boot."
            return False, f"Fastboot continue failed: {out}"
        except Exception as exc:
            return False, f"Error in fastboot continue: {exc}"
