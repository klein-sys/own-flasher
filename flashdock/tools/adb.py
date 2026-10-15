"""
FlashDock — ADB wrapper.

Provides a Pythonic interface to Android Debug Bridge.  Every method
returns a :class:`~flashdock.tools.runner.CommandResult` or a parsed
Python value and logs every invocation.

Usage
-----
    from flashdock.tools.adb import ADB

    adb = ADB()                              # auto-finds the binary
    adb = ADB(binary="/path/to/adb.exe")     # explicit path

    devices = adb.devices()
    props   = adb.get_all_props(serial="XXXX")
    adb.reboot(serial="XXXX", mode="bootloader")
"""

from __future__ import annotations

import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from flashdock.constants import DATA_DIR, TOOLS_DIR
from flashdock.logger import get_logger
from flashdock.tools.runner import CommandResult, run_command

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes for parsed output
# ---------------------------------------------------------------------------
@dataclass
class ADBDevice:
    """One line from ``adb devices -l``."""
    serial: str
    state: str            # "device", "unauthorized", "offline", "recovery", "sideload", …
    product: str = ""
    model: str = ""
    device: str = ""      # codename
    transport_id: str = ""

    @property
    def is_ready(self) -> bool:
        return self.state == "device"

    @property
    def is_unauthorized(self) -> bool:
        return self.state == "unauthorized"

    @property
    def is_recovery(self) -> bool:
        return self.state == "recovery"

    @property
    def is_sideload(self) -> bool:
        return self.state == "sideload"


# ---------------------------------------------------------------------------
# ADB class
# ---------------------------------------------------------------------------
class ADB:
    """Wrapper around the ``adb`` binary."""

    def __init__(
        self,
        binary: Optional[str] = None,
        dry_run: bool = False,
    ) -> None:
        self._binary = binary or self._find_binary()
        self._dry_run = dry_run
        if self._binary:
            log.info("ADB binary: %s", self._binary)
        else:
            log.warning("ADB binary not found. Install platform-tools or use the Tools Manager.")

    @property
    def available(self) -> bool:
        """True if the ADB binary was found."""
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
        """Search for adb.exe in well-known locations."""
        candidates = [
            TOOLS_DIR / "platform-tools" / "adb.exe",
            Path(sys.executable).parent / "data" / "tools" / "platform-tools" / "adb.exe",
            Path(sys.executable).parent / "platform-tools" / "adb.exe",
            Path(__file__).resolve().parent.parent.parent / "data" / "tools" / "platform-tools" / "adb.exe",
        ]
        local_appdata = os.environ.get("LOCALAPPDATA")
        if local_appdata:
            candidates.append(Path(local_appdata) / "FlashDock" / "tools" / "platform-tools" / "adb.exe")

        for c in candidates:
            if c.is_file():
                return str(c)

        # System PATH
        found = shutil.which("adb")
        if found:
            return found

        # Common Android SDK install locations
        for env_var in ("LOCALAPPDATA", "USERPROFILE"):
            base = os.environ.get(env_var)
            if base:
                sdk_c = Path(base) / "Android" / "Sdk" / "platform-tools" / "adb.exe"
                if sdk_c.is_file():
                    return str(sdk_c)

        return None

    # ----- Low-level command runner -----------------------------------------

    def _run(
        self,
        args: list[str],
        *,
        serial: str = "",
        timeout: int = 30,
        action: str = "adb",
    ) -> CommandResult:
        """Build the full adb command and run it."""
        if not self._binary:
            return CommandResult(
                command=["adb"] + args,
                return_code=-1,
                stdout="",
                stderr="ADB binary not found",
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
            env=self._adb_environment(),
        )

    @staticmethod
    def _adb_environment() -> dict[str, str]:
        """Return a writable, private home directory for the ADB server.

        ADB stores its server key and settings in ``.android`` below the
        user's home directory.  On locked-down Windows installations that
        directory may be unavailable (or resolve to ``\\.android``), which
        prevents *any* device enumeration.  Keeping it below FlashDock's
        application data also makes the packaged application self-contained.
        """
        adb_home = DATA_DIR / "android"
        adb_home.mkdir(parents=True, exist_ok=True)
        drive = adb_home.drive
        home_path = str(adb_home)[len(drive):] if drive else str(adb_home)
        return {
            "ANDROID_SDK_HOME": str(adb_home),
            "ANDROID_USER_HOME": str(adb_home),
            "HOME": str(adb_home),
            "USERPROFILE": str(adb_home),
            "HOMEDRIVE": drive,
            "HOMEPATH": home_path,
        }

    # ----- Server management ------------------------------------------------

    def start_server(self) -> CommandResult:
        """Start the ADB server."""
        return self._run(["start-server"], action="adb_start_server", timeout=15)

    def kill_server(self) -> CommandResult:
        """Kill the ADB server (useful for resolving conflicts)."""
        return self._run(["kill-server"], action="adb_kill_server", timeout=10)

    def restart_server(self) -> CommandResult:
        """Kill and restart the ADB server."""
        self.kill_server()
        return self.start_server()

    def version(self) -> Optional[str]:
        """Return the ADB version string, or None."""
        res = self._run(["version"], action="adb_version", timeout=5)
        if res.success:
            # Parse "Android Debug Bridge version X.Y.Z"
            for line in res.stdout.splitlines():
                if "version" in line.lower():
                    parts = line.strip().split()
                    if parts:
                        return parts[-1]
        return None

    # ----- Device listing ---------------------------------------------------

    _DEVICE_LINE_RE = re.compile(
        r"^(\S+)\s+(device|unauthorized|offline|recovery|sideload|"
        r"authorizing|no permissions|bootloader|host)\s*(.*)"
    )

    def devices(self) -> list[ADBDevice]:
        """Return a list of connected ADB devices."""
        res = self._run(["devices", "-l"], action="adb_devices", timeout=10)
        if not res.success:
            return []

        result = []
        for line in res.stdout.splitlines():
            m = self._DEVICE_LINE_RE.match(line.strip())
            if not m:
                continue
            serial, state, extra = m.group(1), m.group(2), m.group(3)

            # Parse key:value pairs from extra
            kvs = {}
            for token in extra.split():
                if ":" in token:
                    k, v = token.split(":", 1)
                    kvs[k] = v

            result.append(ADBDevice(
                serial=serial,
                state=state,
                product=kvs.get("product", ""),
                model=kvs.get("model", ""),
                device=kvs.get("device", ""),
                transport_id=kvs.get("transport_id", ""),
            ))
        return result

    def wait_for_device(self, serial: str = "", timeout: int = 120) -> CommandResult:
        """Block until a device is available or *timeout* is reached."""
        return self._run(
            ["wait-for-device"],
            serial=serial,
            timeout=timeout,
            action="adb_wait",
        )

    def tcpip(self, port: int = 5555, serial: str = "") -> CommandResult:
        """Restart ADB in TCP/IP mode listening on the specified port."""
        return self._run(
            ["tcpip", str(port)],
            serial=serial,
            timeout=15,
            action="adb_tcpip",
        )

    # ----- Properties -------------------------------------------------------

    def getprop(self, prop: str, serial: str = "") -> Optional[str]:
        """Read a single system property."""
        res = self._run(
            ["shell", "getprop", prop],
            serial=serial,
            timeout=10,
            action="adb_getprop",
        )
        if res.success:
            value = res.stdout.strip()
            return value if value else None
        return None

    def get_all_props(self, serial: str = "") -> dict[str, str]:
        """Read all system properties as a dict."""
        res = self._run(
            ["shell", "getprop"],
            serial=serial,
            timeout=15,
            action="adb_getprop_all",
        )
        props: dict[str, str] = {}
        if not res.success:
            return props
        for line in res.stdout.splitlines():
            line = line.strip()
            # Format: [key]: [value]
            if line.startswith("[") and "]: [" in line:
                parts = line.split("]: [", 1)
                key = parts[0].lstrip("[")
                value = parts[1].rstrip("]")
                props[key] = value
        return props

    # ----- Shell commands ---------------------------------------------------

    def shell(self, command: str, serial: str = "", timeout: int = 30) -> CommandResult:
        """Run an arbitrary shell command on the device."""
        return self._run(
            ["shell", command],
            serial=serial,
            timeout=timeout,
            action="adb_shell",
        )

    def shell_su(self, command: str, serial: str = "", timeout: int = 30) -> CommandResult:
        """Run a shell command as root (requires root access)."""
        return self._run(
            ["shell", "su", "-c", command],
            serial=serial,
            timeout=timeout,
            action="adb_shell_su",
        )

    # ----- Reboot -----------------------------------------------------------

    def reboot(self, serial: str = "", mode: str = "") -> CommandResult:
        """Reboot the device.

        Parameters
        ----------
        mode : str
            Empty for normal reboot, or one of:
            ``bootloader``, ``recovery``, ``sideload``,
            ``sideload-auto-reboot``, ``fastboot``, ``edl``.
        """
        args = ["reboot"]
        if mode:
            args.append(mode)
        return self._run(args, serial=serial, timeout=30, action=f"adb_reboot_{mode or 'system'}")

    def reboot_bootloader(self, serial: str = "") -> CommandResult:
        return self.reboot(serial=serial, mode="bootloader")

    def reboot_recovery(self, serial: str = "") -> CommandResult:
        return self.reboot(serial=serial, mode="recovery")

    def reboot_fastboot(self, serial: str = "") -> CommandResult:
        """Reboot to FastbootD (userspace fastboot)."""
        return self.reboot(serial=serial, mode="fastboot")

    def reboot_edl(self, serial: str = "") -> CommandResult:
        """Attempt to reboot to EDL (Qualcomm Emergency Download) mode."""
        return self.reboot(serial=serial, mode="edl")

    def reboot_safemode(self, serial: str = "") -> CommandResult:
        """Reboot into safe mode by setting the persist property."""
        self.shell("setprop persist.sys.safemode 1", serial=serial)
        return self.reboot(serial=serial)

    def poweroff(self, serial: str = "") -> CommandResult:
        """Power off the device."""
        return self._run(
            ["shell", "reboot", "-p"],
            serial=serial,
            timeout=15,
            action="adb_poweroff",
        )

    # ----- File transfer ----------------------------------------------------

    def pull(self, remote: str, local: str, serial: str = "") -> CommandResult:
        return self._run(
            ["pull", remote, local],
            serial=serial,
            timeout=300,
            action="adb_pull",
        )

    def push(self, local: str, remote: str, serial: str = "") -> CommandResult:
        return self._run(
            ["push", local, remote],
            serial=serial,
            timeout=300,
            action="adb_push",
        )

    # ----- Install / Uninstall -----------------------------------------------

    def install(self, apk_path: str, serial: str = "", extra_args: list[str] | None = None) -> CommandResult:
        args = ["install"]
        if extra_args:
            args.extend(extra_args)
        args.append(apk_path)
        return self._run(args, serial=serial, timeout=120, action="adb_install")

    def uninstall(self, package: str, serial: str = "") -> CommandResult:
        return self._run(
            ["uninstall", package],
            serial=serial,
            timeout=30,
            action="adb_uninstall",
        )

    # ----- Sideload ---------------------------------------------------------

    def sideload(self, zip_path: str, serial: str = "") -> CommandResult:
        return self._run(
            ["sideload", zip_path],
            serial=serial,
            timeout=600,
            action="adb_sideload",
        )

    # ----- Logcat -----------------------------------------------------------

    def logcat_dump(self, serial: str = "", lines: int = 500) -> CommandResult:
        """Dump recent logcat output."""
        return self._run(
            ["logcat", "-d", "-t", str(lines)],
            serial=serial,
            timeout=15,
            action="adb_logcat",
        )

    # ----- Backup & Restore -------------------------------------------------

    def backup(
        self,
        destination_path: str,
        packages: list[str] | None = None,
        include_apk: bool = False,
        include_shared: bool = False,
        include_all: bool = True,
        include_system: bool = True,
        serial: str = "",
        timeout: int = 600,
    ) -> CommandResult:
        """Run adb backup to create an Android backup archive (.ab)."""
        args = ["backup", "-f", destination_path]
        if include_apk:
            args.append("-apk")
        else:
            args.append("-noapk")
        if include_shared:
            args.append("-shared")
        if include_all:
            args.append("-all")
        if include_system:
            args.append("-system")
        else:
            args.append("-nosystem")
        if packages:
            args.extend(packages)
        return self._run(args, serial=serial, timeout=timeout, action="adb_backup")

    def restore(
        self,
        backup_path: str,
        serial: str = "",
        timeout: int = 600,
    ) -> CommandResult:
        """Run adb restore to restore an Android backup archive (.ab)."""
        return self._run(["restore", backup_path], serial=serial, timeout=timeout, action="adb_restore")
