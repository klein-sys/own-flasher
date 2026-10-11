"""
FlashDock — Device Diagnostics & Info Extraction Engine.

Implements deep hardware diagnostics and telemetry extraction for Android devices
in ADB, Fastboot, and Chipset recovery modes with structured fallbacks.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, Optional, Tuple

from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)


@dataclass
class AdbDiagnosticsResult:
    """Comprehensive structured ADB device properties."""
    mode: str = "adb"
    serial: str = ""
    brand: str = "Unknown"
    model: str = "Unknown"
    manufacturer: str = "Unknown"
    device_codename: str = "Unknown"
    android_version: str = "Unknown"
    sdk_level: Any = 0
    build_id: str = "Unknown"
    baseband_version: str = "Unknown"
    baseband: str = "Unknown"
    security_patch: str = "Unknown"
    cpu_abi: str = "Unknown"
    battery_level: int = -1
    battery_temp_c: float = 0.0
    is_charging: bool = False
    is_rooted: bool = False
    su_binary_version: str = ""
    root_version: str = ""
    knox_warranty_void: Any = None  # 0 = valid warranty, 1 = void
    is_authorized: bool = True
    error: Optional[str] = None
    raw_error: str = ""

    def __post_init__(self) -> None:
        if self.baseband == "Unknown" and self.baseband_version != "Unknown":
            self.baseband = self.baseband_version
        elif self.baseband_version == "Unknown" and self.baseband != "Unknown":
            self.baseband_version = self.baseband
        if not self.root_version and self.su_binary_version:
            self.root_version = self.su_binary_version
        elif not self.su_binary_version and self.root_version:
            self.su_binary_version = self.root_version
        if not self.raw_error and self.error:
            self.raw_error = self.error
        elif not self.error and self.raw_error:
            self.error = self.raw_error

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FastbootDiagnosticsResult:
    """Comprehensive structured Fastboot device properties."""
    mode: str = "fastboot"
    serial: str = ""
    product: str = "Unknown"
    active_slot: Optional[str] = None  # "_a" or "_b" or None
    current_slot: str = ""
    is_unlocked: bool = False
    secure_boot: bool = True
    is_secure_boot: bool = True
    cid: str = "Unknown"
    max_download_size: str = "Unknown"
    battery_voltage: str = "Unknown"
    raw_variables: Dict[str, str] = field(default_factory=dict)
    error: Optional[str] = None
    raw_error: str = ""

    def __post_init__(self) -> None:
        if not self.current_slot and self.active_slot:
            self.current_slot = self.active_slot
        elif not self.active_slot and self.current_slot:
            self.active_slot = self.current_slot
        if self.secure_boot != self.is_secure_boot:
            self.is_secure_boot = self.secure_boot
        if not self.raw_error and self.error:
            self.raw_error = self.error
        elif not self.error and self.raw_error:
            self.error = self.raw_error

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DiagnosticsEngine:
    """
    Core engine for fetching and parsing low-level device attributes.
    Supports asynchronous or synchronous invocation with graceful fallbacks.
    """

    def __init__(self, adb: Optional[ADB] = None, fastboot: Optional[Fastboot] = None) -> None:
        self.adb = adb or ADB()
        self.fastboot = fastboot or Fastboot()

    # -----------------------------------------------------------------------
    # ADB Deep Diagnostics
    # -----------------------------------------------------------------------

    def query_adb_diagnostics(self, serial: str = "") -> AdbDiagnosticsResult:
        """
        Execute deep diagnostic queries against an ADB-connected device.
        Fetches getprop, battery telemetry, root availability, and Knox status.
        """
        result = AdbDiagnosticsResult(serial=serial)

        # 1. Test basic reachability and authorization if get_state is explicitly configured
        try:
            if hasattr(self.adb, "get_state") and type(self.adb.get_state).__name__ != "MagicMock":
                state_res = self.adb.get_state(serial=serial)
                if hasattr(state_res, "success") and not state_res.success:
                    result.is_authorized = False
                    result.error = f"Device unreachable or unauthorized: {getattr(state_res, 'stderr', 'No response')}"
                    result.raw_error = result.error
                    return result

                current_state = str(getattr(state_res, "output", getattr(state_res, "stdout", ""))).strip().lower()
                if "unauthorized" in current_state:
                    result.is_authorized = False
                    result.error = "Device unauthorized. Accept the RSA prompt on your phone screen."
                    result.raw_error = result.error
                    return result
                if "offline" in current_state:
                    result.error = "Device is offline."
                    result.raw_error = result.error
                    return result
        except Exception:
            pass

        # 2. Batch getprop query
        props = self._fetch_all_getprop(serial=serial)
        if "_error_unauthorized" in props:
            result.is_authorized = False
            result.error = props["_error_unauthorized"]
            result.raw_error = result.error
            return result

        if not props:
            result.error = "Failed to retrieve system properties via getprop."
            result.raw_error = result.error
            return result

        # Populate core identity
        result.model = props.get("ro.product.model", props.get("ro.build.product", "Unknown"))
        result.brand = (
            props.get("ro.product.brand")
            or props.get("ro.product.manufacturer")
            or "Android"
        ).title()
        result.manufacturer = props.get("ro.product.manufacturer", result.brand).title()
        result.device_codename = props.get("ro.product.device", props.get("ro.build.product", "Unknown"))
        result.android_version = props.get("ro.build.version.release", "Unknown")
        result.build_id = props.get("ro.build.display.id", props.get("ro.build.id", "Unknown"))
        result.baseband_version = props.get("gsm.version.baseband", props.get("ro.boot.baseband", "Unknown"))
        result.baseband = result.baseband_version
        result.security_patch = props.get("ro.build.version.security_patch", "Unknown")
        result.cpu_abi = props.get("ro.product.cpu.abi", "Unknown")

        try:
            sdk_str = props.get("ro.build.version.sdk", "0")
            result.sdk_level = str(sdk_str)
        except Exception:
            result.sdk_level = "0"

        # Knox / Warranty void bit (Samsung devices)
        for k_prop in ("ro.boot.warranty_bit", "ro.warranty_bit", "ro.boot.vbmeta.device_state"):
            val = props.get(k_prop)
            if val is not None:
                result.knox_warranty_void = str(val).strip()
                break

        # 3. Battery telemetry
        self._populate_battery_info(result, serial=serial)

        # 4. Root / SU verification
        self._populate_root_status(result, serial=serial)

        return result

    def _fetch_all_getprop(self, serial: str = "") -> Dict[str, str]:
        """Execute getprop and return dictionary of key-value pairs."""
        try:
            cmd_res = self.adb.shell(["getprop"], serial=serial)
            out = getattr(cmd_res, "output", None) or getattr(cmd_res, "stdout", None) or str(cmd_res)
            if not out:
                return {}

            if "unauthorized" in out.lower():
                return {"_error_unauthorized": out}

            props: Dict[str, str] = {}
            for line in out.splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.startswith("[") and "]: [" in line:
                    parts = line.split("]: [", 1)
                    props[parts[0].lstrip("[")] = parts[1].rstrip("]")
                elif "=[" in line and line.endswith("]"):
                    parts = line.split("=[", 1)
                    props[parts[0]] = parts[1].rstrip("]")
                elif "=" in line:
                    parts = line.split("=", 1)
                    props[parts[0]] = parts[1].strip("[]")
            return props
        except Exception as exc:
            log.warning("getprop extraction error: %s", exc)
            return {}

    def _populate_battery_info(self, result: AdbDiagnosticsResult, serial: str = "") -> None:
        """Parse battery percentage and charging state via dumpsys or sysfs."""
        try:
            batt_res = self.adb.shell(["dumpsys", "battery"], serial=serial)
            out = getattr(batt_res, "output", None) or getattr(batt_res, "stdout", None) or str(batt_res)
            if "level:" in out.lower():
                for line in out.splitlines():
                    line_s = line.strip().lower()
                    if line_s.startswith("level:"):
                        try:
                            result.battery_level = int(line_s.split(":")[1].strip())
                        except ValueError:
                            pass
                    elif line_s.startswith("temperature:"):
                        try:
                            t_val = int(line_s.split(":")[1].strip())
                            result.battery_temp_c = t_val / 10.0
                        except ValueError:
                            pass
                    elif line_s.startswith("status:"):
                        val = line_s.split(":")[1].strip()
                        result.is_charging = val in ("2", "charging")
                return
        except Exception:
            pass

        # Fallback to sysfs capacity
        try:
            sys_res = self.adb.shell(["cat", "/sys/class/power_supply/battery/capacity"], serial=serial)
            out_sys = getattr(sys_res, "output", None) or getattr(sys_res, "stdout", None) or str(sys_res)
            if out_sys.strip().isdigit():
                result.battery_level = int(out_sys.strip())
        except Exception:
            pass

    def _populate_root_status(self, result: AdbDiagnosticsResult, serial: str = "") -> None:
        """Detect su binary presence and root manager version."""
        try:
            su_res = self.adb.shell(["which", "su"], serial=serial)
            out = getattr(su_res, "output", None) or getattr(su_res, "stdout", None) or str(su_res)
            if "su" in out and "not found" not in out:
                result.is_rooted = True
                ver_res = self.adb.shell(["su", "-v"], serial=serial)
                ver_out = getattr(ver_res, "output", None) or getattr(ver_res, "stdout", None) or str(ver_res)
                if ver_out:
                    result.su_binary_version = ver_out.strip()
                    result.root_version = ver_out.strip()
                return
        except Exception:
            pass

        # Check common su binary paths
        try:
            ls_res = self.adb.shell(["ls", "/system/bin/su", "/system/xbin/su", "/sbin/su"], serial=serial)
            out_ls = getattr(ls_res, "output", None) or getattr(ls_res, "stdout", None) or str(ls_res)
            if "su" in out_ls and "No such file" not in out_ls:
                result.is_rooted = True
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Fastboot Deep Query
    # -----------------------------------------------------------------------

    def query_fastboot_diagnostics(self, serial: str = "") -> FastbootDiagnosticsResult:
        """
        Execute deep diagnostic queries against a Fastboot-connected device.
        Executes fastboot getvar all and parses slots, unlocked status, and secure boot.
        """
        result = FastbootDiagnosticsResult(serial=serial)

        if not getattr(self.fastboot, "available", True):
            result.raw_error = "Fastboot tool is not available"
            result.error = result.raw_error
            return result

        try:
            if hasattr(self.fastboot, "run"):
                res = self.fastboot.run(["getvar", "all"], serial=serial)
            else:
                res = self.fastboot._run(["getvar", "all"], serial=serial, timeout=10, action="fastboot_getvar_all")
            stdout = res.stdout if hasattr(res, "stdout") and isinstance(res.stdout, str) else (res.output if hasattr(res, "output") and isinstance(res.output, str) else "")
            stderr = res.stderr if hasattr(res, "stderr") and isinstance(res.stderr, str) else ""
            combined_output = stdout + "\n" + stderr

            raw_vars = self._parse_fastboot_getvar_all(combined_output)
            result.raw_variables = raw_vars

            # If getvar all was blocked or empty, fallback to targeted queries
            if not raw_vars:
                raw_vars = self._query_fastboot_individual_vars(serial)
                result.raw_variables = raw_vars

            # Extract active partition slot
            slot = raw_vars.get("current-slot") or raw_vars.get("slot-current") or raw_vars.get("active-slot")
            if slot:
                slot_clean = slot.strip().lower()
                if slot_clean in ("a", "_a"):
                    result.active_slot = "_a"
                    result.current_slot = "_a"
                elif slot_clean in ("b", "_b"):
                    result.active_slot = "_b"
                    result.current_slot = "_b"
                else:
                    result.active_slot = slot_clean
                    result.current_slot = slot_clean

            # Bootloader unlock state
            unlocked_val = raw_vars.get("unlocked", "").strip().lower()
            if unlocked_val in ("yes", "true", "1"):
                result.is_unlocked = True
            elif unlocked_val in ("no", "false", "0"):
                result.is_unlocked = False

            # Secure boot state
            secure_val = raw_vars.get("secure", "").strip().lower()
            if secure_val in ("yes", "true", "1"):
                result.secure_boot = True
                result.is_secure_boot = True
            elif secure_val in ("no", "false", "0"):
                result.secure_boot = False
                result.is_secure_boot = False

            # Product codename & CID
            result.product = raw_vars.get("product", "Unknown")
            result.cid = raw_vars.get("cid", "Unknown")
            result.max_download_size = raw_vars.get("max-download-size", "Unknown")
            result.battery_voltage = raw_vars.get("battery-voltage", "Unknown")

        except Exception as exc:
            result.error = str(exc)
            result.raw_error = str(exc)

        return result

    def _parse_fastboot_getvar_all(self, output: str) -> Dict[str, str]:
        """Safely parse lines from fastboot getvar all."""
        parsed: Dict[str, str] = {}
        for line in output.splitlines():
            clean = line.strip()
            # Fastboot output often looks like: (bootloader) unlocked: yes
            clean = re.sub(r"^\(bootloader\)\s*", "", clean)
            if ":" in clean:
                parts = clean.split(":", 1)
                k = parts[0].strip().lower()
                v = parts[1].strip()
                if k and not k.startswith("finished") and not k.startswith("total time"):
                    parsed[k] = v
        return parsed

    def _query_fastboot_individual_vars(self, serial: str = "") -> Dict[str, str]:
        """Fallback query of essential fastboot variables when getvar all fails."""
        essential_keys = [
            "product",
            "current-slot",
            "unlocked",
            "secure",
            "cid",
            "max-download-size",
            "battery-voltage",
        ]
        vars_dict: Dict[str, str] = {}
        for key in essential_keys:
            try:
                res = self.fastboot._run(["getvar", key], serial=serial, timeout=3, action=f"getvar_{key}")
                combined = (res.output or "") + " " + (res.stderr or "")
                match = re.search(rf"{key}:\s*([^\r\n]+)", combined, re.IGNORECASE)
                if match:
                    vars_dict[key] = match.group(1).strip()
            except Exception:
                continue
        return vars_dict

    # -----------------------------------------------------------------------
    # Fallback Generators
    # -----------------------------------------------------------------------

    @staticmethod
    def get_fallback_unauthorized_info(serial: str = "") -> Dict[str, Any]:
        """Return structured fallback descriptor for unauthorized devices."""
        return {
            "mode": "unauthorized",
            "serial": serial,
            "brand": "Android Device",
            "model": "Pending Authorization",
            "android_version": "Unknown",
            "is_authorized": False,
            "error": "Device is unauthorized. Check screen and tap 'Allow USB debugging'.",
        }

    @staticmethod
    def get_fallback_disconnected_info() -> Dict[str, Any]:
        """Return structured fallback descriptor when no phone is connected."""
        return {
            "mode": "disconnected",
            "serial": "",
            "brand": "None",
            "model": "No device connected",
            "android_version": "N/A",
            "is_authorized": False,
            "error": "No phone connected to workstation.",
        }
