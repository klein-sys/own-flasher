"""
FlashDock — Fastboot wrapper.

Provides a Pythonic interface to the ``fastboot`` binary.  Covers device
listing, getvar queries, partition flashing, unlocking, and reboot
commands.

Usage
-----
    from flashdock.tools.fastboot import Fastboot

    fb = Fastboot()
    devices = fb.devices()
    fb.flash("boot", "patched_boot.img", serial="XXXX")
    fb.reboot(serial="XXXX")
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from flashdock.constants import TOOLS_DIR
from flashdock.logger import get_logger
from flashdock.tools.runner import CommandResult, run_command

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass
class FastbootDevice:
    """One line from ``fastboot devices``."""
    serial: str
    mode: str  # "fastboot" or "fastbootd"


# ---------------------------------------------------------------------------
# Fastboot class
# ---------------------------------------------------------------------------
class Fastboot:
    """Wrapper around the ``fastboot`` binary."""

    def __init__(
        self,
        binary: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self._binary = binary or self._find_binary()
        self._dry_run = dry_run
        if self._binary:
            log.info("Fastboot binary: %s", self._binary)
        else:
            log.warning("Fastboot binary not found. Install platform-tools or use the Tools Manager.")

    @property
    def available(self) -> bool:
        """True if fastboot was found."""
        return self._binary is not None

    @property
    def binary_path(self) -> Optional[str]:
        return self._binary

    @binary_path.setter
    def binary_path(self, path: Optional[str | Path]) -> None:
        self._binary = str(path) if path else None

    # ----- Binary discovery -------------------------------------------------

    @staticmethod
    def _find_binary() -> Optional[str]:
        """Search for fastboot.exe in well-known locations."""
        candidates = [
            TOOLS_DIR / "platform-tools" / "fastboot.exe",
            Path(sys.executable).parent / "data" / "tools" / "platform-tools" / "fastboot.exe",
            Path(sys.executable).parent / "platform-tools" / "fastboot.exe",
            Path(__file__).resolve().parent.parent.parent / "data" / "tools" / "platform-tools" / "fastboot.exe",
        ]
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "FlashDock" / "tools" / "platform-tools" / "fastboot.exe")

        for c in candidates:
            if c.is_file():
                return str(c)

        # System PATH
        found = shutil.which("fastboot")
        if found:
            return found

        # Common Android SDK install locations
        for env_var in ("LOCALAPPDATA", "USERPROFILE"):
            base = os.environ.get(env_var)
            if base:
                sdk_c = Path(base) / "Android" / "Sdk" / "platform-tools" / "fastboot.exe"
                if sdk_c.is_file():
                    return str(sdk_c)

        return None

    # ----- Low-level runner -------------------------------------------------

    def _run(
        self,
        args: list[str],
        *,
        serial: str = "",
        timeout: int = 60,
        action: str = "fastboot",
    ) -> CommandResult:
        if not self._binary:
            return CommandResult(
                command=["fastboot"] + args,
                return_code=-1,
                stdout="",
                stderr="Fastboot binary not found",
                duration_ms=0,
            )
        cmd = [self._binary]
        if serial:
            cmd += ["-s", serial]
        cmd += args
        return run_command(
            cmd,
            timeout=timeout,
            dry_run=self._dry_run,
            action_name=action,
            device_serial=serial,
        )

    # ----- Version ----------------------------------------------------------

    def version(self) -> Optional[str]:
        res = self._run(["--version"], action="fastboot_version", timeout=5)
        if res.success:
            # "fastboot version 35.0.2-..."
            for line in res.stdout.splitlines():
                if "version" in line.lower():
                    parts = line.strip().split()
                    for p in parts:
                        if re.match(r"\d+\.\d+", p):
                            return p
        return None

    # ----- Device listing ---------------------------------------------------

    def devices(self) -> list[FastbootDevice]:
        """List devices in fastboot mode."""
        res = self._run(["devices"], action="fastboot_devices", timeout=10)
        result = []
        if not res.success:
            return result
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("*"):
                continue
            parts = line.split()
            if len(parts) >= 2:
                result.append(FastbootDevice(serial=parts[0], mode=parts[1]))
        return result

    # ----- Getvar -----------------------------------------------------------

    def getvar(self, var: str, serial: str = "") -> Optional[str]:
        """Read a single fastboot variable."""
        res = self._run(
            ["getvar", var],
            serial=serial,
            timeout=10,
            action="fastboot_getvar",
        )
        # fastboot prints to stderr: "var: value"
        output = res.stderr or res.stdout
        for line in output.splitlines():
            clean = re.sub(r"^\(bootloader\)\s*", "", line.strip(), flags=re.IGNORECASE)
            if clean.lower().startswith(var.lower() + ":"):
                return clean.split(":", 1)[1].strip()
        return None

    def get_var(self, var: str, serial: str = "") -> Optional[str]:
        return self.getvar(var, serial=serial)

    def getvar_all(self, serial: str = "") -> dict[str, str]:
        """Read all fastboot variables."""
        res = self._run(
            ["getvar", "all"],
            serial=serial,
            timeout=15,
            action="fastboot_getvar_all",
        )
        result: dict[str, str] = {}
        output = res.stderr or res.stdout
        for line in output.splitlines():
            clean = re.sub(r"^\(bootloader\)\s*", "", line.strip(), flags=re.IGNORECASE)
            if ":" in clean:
                key, _, value = clean.partition(":")
                key = key.strip().lower()
                value = value.strip()
                if key and value and not key.startswith("("):
                    result[key] = value
        return result

    # ----- Flash operations ------------------------------------------------

    def flash(
        self,
        partition: str,
        image_path: str,
        serial: str = "",
        slot: str = "",
        timeout: int = 300,
    ) -> CommandResult:
        """Flash an image to a partition.

        Parameters
        ----------
        partition : str
            Partition name (e.g. "boot", "system", "vbmeta").
        image_path : str
            Path to the image file.
        slot : str
            Optional slot override ("a", "b", or "").
        """
        args = []
        if slot:
            args += [f"--slot={slot}"]
        target = f"{partition}_{slot}" if slot else partition
        args += ["flash", partition, image_path]
        return self._run(
            args,
            serial=serial,
            timeout=timeout,
            action=f"fastboot_flash_{target}",
        )

    def erase(self, partition: str, serial: str = "") -> CommandResult:
        """Erase a partition."""
        return self._run(
            ["erase", partition],
            serial=serial,
            timeout=60,
            action=f"fastboot_erase_{partition}",
        )

    def wipe(self, serial: str = "") -> CommandResult:
        """Format userdata and cache (-w)."""
        return self._run(
            ["-w"],
            serial=serial,
            timeout=180,
            action="fastboot_wipe",
        )

    # ----- Boot (temporary) -------------------------------------------------

    def boot(self, image_path: str, serial: str = "") -> CommandResult:
        """Boot an image without flashing it (temporary)."""
        return self._run(
            ["boot", image_path],
            serial=serial,
            timeout=120,
            action="fastboot_boot",
        )

    # ----- Slot management --------------------------------------------------

    def get_active_slot(self, serial: str = "") -> Optional[str]:
        """Return the current active slot ("a" or "b"), or None."""
        val = self.getvar("current-slot", serial=serial)
        if val:
            return val.strip().lower().lstrip("_")
        return None

    def set_active_slot(self, slot: str, serial: str = "") -> CommandResult:
        """Set the active slot."""
        return self._run(
            ["set_active", slot],
            serial=serial,
            timeout=15,
            action=f"fastboot_set_active_{slot}",
        )

    # ----- Unlock / Lock ----------------------------------------------------

    def oem_unlock(self, code: str = "", serial: str = "") -> CommandResult:
        """Unlock the bootloader (OEM unlock, optionally with unlock code)."""
        args = ["oem", "unlock"]
        if code:
            args.append(code)
        return self._run(
            args,
            serial=serial,
            timeout=30,
            action="fastboot_oem_unlock",
        )

    def flashing_unlock(self, serial: str = "") -> CommandResult:
        """Unlock the bootloader (flashing unlock — Pixel-style)."""
        return self._run(
            ["flashing", "unlock"],
            serial=serial,
            timeout=30,
            action="fastboot_flashing_unlock",
        )

    def flashing_unlock_critical(self, serial: str = "") -> CommandResult:
        """Unlock critical partitions (Pixel / Transsion newer devices)."""
        return self._run(
            ["flashing", "unlock_critical"],
            serial=serial,
            timeout=30,
            action="fastboot_flashing_unlock_critical",
        )

    def flashing_lock(self, serial: str = "") -> CommandResult:
        """Lock the bootloader."""
        return self._run(
            ["flashing", "lock"],
            serial=serial,
            timeout=30,
            action="fastboot_flashing_lock",
        )

    def oem_lock(self, serial: str = "") -> CommandResult:
        """Lock the bootloader (OEM lock)."""
        return self._run(
            ["oem", "lock"],
            serial=serial,
            timeout=30,
            action="fastboot_oem_lock",
        )

    # ----- vbmeta -----------------------------------------------------------

    def flash_vbmeta_disabled(
        self,
        image_path: str,
        serial: str = "",
    ) -> CommandResult:
        """Flash vbmeta with verification disabled (--disable-verity --disable-verification)."""
        return self._run(
            ["--disable-verity", "--disable-verification",
             "flash", "vbmeta", image_path],
            serial=serial,
            timeout=60,
            action="fastboot_flash_vbmeta_disabled",
        )

    # ----- Reboot -----------------------------------------------------------

    def reboot(self, serial: str = "") -> CommandResult:
        """Reboot to system."""
        return self._run(["reboot"], serial=serial, timeout=15, action="fastboot_reboot")

    def reboot_bootloader(self, serial: str = "") -> CommandResult:
        """Reboot back into bootloader."""
        return self._run(
            ["reboot-bootloader"],
            serial=serial,
            timeout=15,
            action="fastboot_reboot_bootloader",
        )

    def reboot_fastboot(self, serial: str = "") -> CommandResult:
        """Reboot into FastbootD (userspace fastboot)."""
        return self._run(
            ["reboot", "fastboot"],
            serial=serial,
            timeout=15,
            action="fastboot_reboot_fastbootd",
        )

    def reboot_recovery(self, serial: str = "") -> CommandResult:
        """Reboot into recovery from bootloader."""
        return self._run(
            ["reboot", "recovery"],
            serial=serial,
            timeout=15,
            action="fastboot_reboot_recovery",
        )
