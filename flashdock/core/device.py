"""
FlashDock — Device detection and profile builder.

Reads device details over ADB (system/recovery/sideload) or fastboot
(bootloader) and builds a :class:`DeviceInfo` snapshot.  This is the
single source of truth for "what phone is connected and what state is
it in".

Spec reference: Section 6 (Device detection).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from flashdock.logger import get_logger
from flashdock.tools.adb import ADB, ADBDevice
from flashdock.tools.fastboot import Fastboot, FastbootDevice

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Device info snapshot
# ---------------------------------------------------------------------------
@dataclass
class DeviceInfo:
    """Complete picture of a connected Android device.

    Fields that cannot be read in the current mode are left as their
    default (empty string / None / "unknown").
    """

    # ---- Identifiers ----
    serial: str = ""
    brand: str = ""
    manufacturer: str = ""
    model: str = ""             # Marketing name (e.g. "Pixel 7 Pro")
    device: str = ""            # Codename (e.g. "cheetah")
    product: str = ""           # Build product (e.g. "cheetah")

    # ---- Software ----
    android_version: str = ""
    sdk_version: str = ""
    security_patch: str = ""
    build_number: str = ""
    build_fingerprint: str = ""
    build_display: str = ""

    # ---- Hardware ----
    chipset: str = "unknown"          # "mediatek", "snapdragon", etc.
    hardware: str = ""                # raw ro.hardware value
    cpu_abi: str = ""                 # "arm64-v8a", etc.
    board: str = ""

    # ---- Bootloader & partitions ----
    bootloader_state: str = "unknown"  # "locked", "unlocked", "unknown"
    oem_unlock_allowed: str = "unknown"  # "1", "0", "unknown"
    slot_scheme: str = "unknown"       # "a/b", "a_only", "unknown"
    active_slot: str = ""              # "a", "b", ""
    has_dynamic_partitions: bool = False
    treble_enabled: bool = False

    # ---- Misc ----
    kernel_version: str = ""
    battery_level: int = -1            # -1 = unknown
    battery_temp_c: float = -1.0       # Temperature in Celsius (-1 = unknown)
    battery_voltage_mv: int = -1       # Voltage in millivolts (-1 = unknown)
    knox_warranty_bit: str = "0x0"     # Samsung Knox bit ("0x0" clean, "0x1" tripped)
    is_rooted: bool = False
    root_method: str = ""              # "magisk", "kernelsu", "apatch", ""
    encryption_state: str = "unknown"  # "encrypted", "unencrypted", "unknown"
    anti_rollback_index: str = ""

    # ---- OS & Modification status (User Additions) ----
    os_type: str = "unknown"           # "stock", "custom_rom", "gsi", "unknown"
    os_name: str = ""                  # e.g. "Official Stock Firmware", "LineageOS 21.0", "PixelOS", "Phh-Treble GSI"

    # ---- Detection state ----
    mode: str = "not_connected"        # matches DEVICE_MODES constant
    detection_source: str = ""         # "adb", "fastboot", "limited"
    detection_errors: list[str] = field(default_factory=list)

    # ---- Convenience properties -------------------------------------------

    @property
    def os_display(self) -> str:
        """User-friendly OS status badge."""
        if self.os_name:
            return self.os_name
        if self.os_type == "stock":
            return f"Stock OEM ({self.brand.title()})" if self.brand else "Stock OEM"
        if self.os_type == "custom_rom":
            return "Custom ROM"
        if self.os_type == "gsi":
            return "Generic System Image (GSI)"
        return "Unknown OS"

    @property
    def root_display(self) -> str:
        """User-friendly root status badge."""
        if self.is_rooted:
            method = self.root_method.title() if self.root_method else "Active"
            return f"Rooted ({method})"
        return "Not Rooted"

    @property
    def summary_line(self) -> str:
        """Short one-line description for the status bar."""
        parts = []
        if self.brand:
            parts.append(self.brand.title())
        if self.model:
            parts.append(self.model)
        if self.android_version:
            parts.append(f"Android {self.android_version}")
        if not parts:
            if self.serial:
                return f"Device {self.serial[:8]}…"
            return "Unknown device"
        return " · ".join(parts)

    @property
    def chipset_family(self) -> str:
        """Normalise the chipset to one of the known families."""
        hw = (self.hardware + " " + self.chipset + " " + self.board).lower()
        if any(k in hw for k in ("qcom", "qualcomm", "snapdragon", "msm", "sdm", "sm8", "sm6", "sm7")):
            return "snapdragon"
        if any(k in hw for k in ("mt", "mediatek", "mtk")):
            return "mediatek"
        if any(k in hw for k in ("exynos", "samsungexynos", "universal")):
            return "exynos"
        if any(k in hw for k in ("unisoc", "sprd", "spreadtrum", "ums", "ud7")):
            return "unisoc"
        if any(k in hw for k in ("tensor", "gs1", "gs2", "gs3")):
            return "tensor"
        if any(k in hw for k in ("kirin", "hisilicon")):
            return "kirin"
        return "unknown"

    @property
    def brand_normalized(self) -> str:
        """Normalise brand to one of the known brand constants."""
        b = self.brand.lower().strip()
        # Handle sub-brands
        if b in ("redmi", "poco"):
            return b
        if b in ("xiaomi", "redmi", "poco"):
            return b
        if b in ("oneplus", "one plus"):
            return "oneplus"
        if b in ("oppo", "realme"):
            return b
        if "transsion" in b:
            return "transsion"
        if "tecno" in b:
            return "tecno"
        if "infinix" in b:
            return "infinix"
        if "itel" in b:
            return "itel"
        brand_map = {
            "google": "google",
            "samsung": "samsung",
            "motorola": "motorola",
            "sony": "sony",
            "nokia": "nokia",
            "asus": "asus",
            "tecno": "tecno",
            "infinix": "infinix",
            "itel": "itel",
            "huawei": "huawei",
            "honor": "huawei",
            "vivo": "vivo",
            "nothing": "nothing",
            "fairphone": "fairphone",
        }
        return brand_map.get(b, "unknown")

    def to_dict(self) -> dict:
        """Serialise to a dict (for JSON storage in device profiles)."""
        d = {}
        for f_name in self.__dataclass_fields__:
            val = getattr(self, f_name)
            if isinstance(val, list):
                val = list(val)
            d[f_name] = val
        return d


# ---------------------------------------------------------------------------
# Detection engine
# ---------------------------------------------------------------------------
class DeviceDetector:
    """Reads device information via ADB and/or fastboot.

    Usage::

        detector = DeviceDetector(adb, fastboot)
        info = detector.detect(serial="ABC123")
    """

    def __init__(self, adb: ADB, fastboot: Fastboot) -> None:
        self._adb = adb
        self._fb = fastboot

    def detect(self, serial: str = "") -> DeviceInfo:
        """Detect the device and return a full :class:`DeviceInfo`.

        Tries ADB first (most data available), falls back to fastboot
        for devices in bootloader mode, and returns a minimal stub for
        unknown modes.
        """
        info = DeviceInfo(serial=serial)

        # --- Try ADB first ---
        if self._adb.available:
            adb_devs = self._adb.devices()
            adb_dev = self._find_device(adb_devs, serial)
            if adb_dev:
                info.serial = adb_dev.serial
                info.mode = self._adb_state_to_mode(adb_dev.state)
                info.detection_source = "adb"

                if adb_dev.is_ready:
                    self._read_adb_props(info)
                elif adb_dev.is_recovery:
                    self._read_recovery_props(info)
                elif adb_dev.is_unauthorized:
                    info.detection_errors.append(
                        "USB debugging not authorized. Check the phone screen."
                    )
                return info

        # --- Try fastboot ---
        if self._fb.available:
            fb_devs = self._fb.devices()
            fb_dev = self._find_fb_device(fb_devs, serial)
            if fb_dev:
                info.serial = fb_dev.serial
                info.mode = "fastbootd" if fb_dev.mode == "fastbootd" else "bootloader"
                info.detection_source = "fastboot"
                self._read_fastboot_vars(info)
                return info

        # --- Nothing found ---
        info.mode = "not_connected"
        info.detection_source = "none"
        return info

    # ---- ADB detection ----------------------------------------------------

    def _read_adb_props(self, info: DeviceInfo) -> None:
        """Fill in device info from ADB properties (device in system mode)."""
        props = self._adb.get_all_props(serial=info.serial)
        if not props:
            info.detection_errors.append("Could not read device properties.")
            return

        info.brand = props.get("ro.product.brand", "")
        info.manufacturer = props.get("ro.product.manufacturer", "")
        info.model = props.get("ro.product.model", "")
        info.device = props.get("ro.product.device", "")
        info.product = props.get("ro.build.product", "")

        info.android_version = props.get("ro.build.version.release", "")
        info.sdk_version = props.get("ro.build.version.sdk", "")
        info.security_patch = props.get("ro.build.version.security_patch", "")
        info.build_number = props.get("ro.build.display.id",
                           props.get("ro.build.id", ""))
        info.build_fingerprint = props.get("ro.build.fingerprint", "")
        info.build_display = props.get("ro.build.display.id", "")

        info.hardware = props.get("ro.hardware", "")
        info.board = props.get("ro.board.platform", "")
        info.cpu_abi = props.get("ro.product.cpu.abi", "")

        # Bootloader state
        bl = props.get("ro.boot.flash.locked", "")
        if bl == "1":
            info.bootloader_state = "locked"
        elif bl == "0":
            info.bootloader_state = "unlocked"
        else:
            # Try alternative property
            verifiedboot = props.get("ro.boot.verifiedbootstate", "")
            if verifiedboot == "orange":
                info.bootloader_state = "unlocked"
            elif verifiedboot == "green":
                info.bootloader_state = "locked"

        # OEM unlock
        oem = props.get("ro.oem_unlock_supported", "")
        sys_oem = props.get("sys.oem_unlock_allowed", "")
        if sys_oem:
            info.oem_unlock_allowed = sys_oem
        elif oem:
            info.oem_unlock_allowed = oem

        # Slots
        slot_suffix = props.get("ro.boot.slot_suffix", "")
        if slot_suffix:
            info.slot_scheme = "a/b"
            info.active_slot = slot_suffix.lstrip("_")
        else:
            info.slot_scheme = "a_only"

        # Dynamic partitions
        info.has_dynamic_partitions = (
            props.get("ro.boot.dynamic_partitions", "") == "true"
        )

        # Treble
        info.treble_enabled = (
            props.get("ro.treble.enabled", "") == "true"
        )

        # Kernel
        res = self._adb.shell("uname -r", serial=info.serial, timeout=5)
        if res.success:
            info.kernel_version = res.stdout.strip()

        # Battery telemetry
        res = self._adb.shell("dumpsys battery", serial=info.serial, timeout=5)
        if res.success:
            m_level = re.search(r"level:\s*(\d+)", res.stdout)
            if m_level:
                info.battery_level = int(m_level.group(1))
            m_temp = re.search(r"temperature:\s*(\d+)", res.stdout)
            if m_temp:
                info.battery_temp_c = round(int(m_temp.group(1)) / 10.0, 1)
            m_volt = re.search(r"voltage:\s*(\d+)", res.stdout)
            if m_volt:
                info.battery_voltage_mv = int(m_volt.group(1))

        # Knox Warranty Bit (Samsung / OEM)
        knox_bit = props.get("ro.boot.warranty_bit", "") or props.get("ro.warranty_bit", "")
        if knox_bit:
            info.knox_warranty_bit = "0x1" if knox_bit in ("1", "0x1") else "0x0"

        # Root detection
        info.is_rooted, info.root_method = self._detect_root(info.serial, props)

        # OS Type detection (Stock OEM, Custom ROM, GSI)
        info.os_type, info.os_name = self._detect_os_type(props, info)

        # Encryption
        encrypt_state = props.get("ro.crypto.state", "")
        if encrypt_state:
            info.encryption_state = encrypt_state

        # Anti-rollback (where available)
        info.anti_rollback_index = props.get("ro.boot.avb_rollback_index", "")

        # Chipset
        info.chipset = info.chipset_family

        log.info("ADB detection complete: %s (%s)", info.model, info.device)

    def _read_recovery_props(self, info: DeviceInfo) -> None:
        """Read limited props available in recovery mode."""
        props = self._adb.get_all_props(serial=info.serial)
        if props:
            info.brand = props.get("ro.product.brand", "")
            info.model = props.get("ro.product.model", "")
            info.device = props.get("ro.product.device", "")
            info.build_fingerprint = props.get("ro.build.fingerprint", "")
            info.android_version = props.get("ro.build.version.release", "")
        info.detection_errors.append(
            "Limited info available in recovery mode."
        )
        log.info("Recovery detection: %s (%s)", info.model, info.device)

    # ---- Fastboot detection ------------------------------------------------

    def _read_fastboot_vars(self, info: DeviceInfo) -> None:
        """Fill in device info from fastboot getvar."""
        vars_dict = self._fb.getvar_all(serial=info.serial)
        if not vars_dict:
            info.detection_errors.append("Could not read fastboot variables.")
            return

        info.product = vars_dict.get("product", "")
        info.device = vars_dict.get("product", "")
        info.model = vars_dict.get("product", "")  # fastboot often only has product
        info.hardware = vars_dict.get("hw-revision", "")

        # Bootloader state
        bl = vars_dict.get("unlocked", "")
        if bl == "yes":
            info.bootloader_state = "unlocked"
        elif bl == "no":
            info.bootloader_state = "locked"

        # Secure boot / state
        secure = vars_dict.get("secure", "")

        # Slots
        slot_count = vars_dict.get("slot-count", "")
        is_ab = False
        if slot_count:
            try:
                is_ab = int(slot_count) > 1
            except (ValueError, TypeError):
                is_ab = False

        if is_ab:
            info.slot_scheme = "a/b"
            current = vars_dict.get("current-slot", "")
            info.active_slot = current.strip().lstrip("_")
        else:
            info.slot_scheme = "a_only"

        # Anti-rollback
        info.anti_rollback_index = vars_dict.get(
            "anti-rollback",
            vars_dict.get("rollback-index", ""),
        )

        # Fastboot Battery level & voltage
        batt_soc = vars_dict.get("battery-soc-ok", vars_dict.get("battery-soc", ""))
        if batt_soc:
            try:
                info.battery_level = int(batt_soc.rstrip("%"))
            except (ValueError, TypeError):
                pass
        batt_volt = vars_dict.get("battery-voltage", "")
        if batt_volt:
            try:
                info.battery_voltage_mv = int(batt_volt.rstrip("mVmv"))
            except (ValueError, TypeError):
                pass

        # Brand guess from product name
        if not info.brand:
            product_lower = info.product.lower()
            # Well-known prefixes
            for brand_hint in ("pixel", "oriole", "raven", "cheetah", "panther",
                               "shiba", "husky", "akita", "tokay", "caiman"):
                if brand_hint in product_lower:
                    info.brand = "google"
                    break

        info.chipset = info.chipset_family
        info.detection_errors.append(
            "Limited info available in bootloader/fastboot mode. "
            "Boot to system for full details."
        )
        log.info("Fastboot detection: product=%s, unlocked=%s",
                 info.product, info.bootloader_state)

    # ---- Root detection ----------------------------------------------------

    def _detect_root(self, serial: str, props: dict[str, str]) -> tuple[bool, str]:
        """Try to detect if the device is rooted and by which method."""
        # Magisk
        magisk_ver = props.get("magisk.version", "")
        if magisk_ver:
            return True, "magisk"

        # Check for su binary
        res = self._adb.shell("which su", serial=serial, timeout=5)
        if res.success and "/su" in res.stdout:
            # Try to distinguish KernelSU vs Magisk vs generic
            res2 = self._adb.shell("su -v", serial=serial, timeout=5)
            if res2.success:
                out = res2.stdout.lower()
                if "kernelsu" in out:
                    return True, "kernelsu"
                if "magisk" in out:
                    return True, "magisk"
                if "apatch" in out:
                    return True, "apatch"
            return True, "unknown"

        # Check for KernelSU module
        res3 = self._adb.shell("ls /data/adb/ksu 2>/dev/null", serial=serial, timeout=5)
        if res3.success and res3.stdout.strip():
            return True, "kernelsu"

        # Check for APatch
        res4 = self._adb.shell("ls /data/adb/apatch 2>/dev/null", serial=serial, timeout=5)
        if res4.success and res4.stdout.strip():
            return True, "apatch"

        return False, ""

    # ---- OS Type detection (Stock, Custom ROM, GSI) ------------------------

    def _detect_os_type(self, props: dict[str, str], info: DeviceInfo) -> tuple[str, str]:
        """Classify OS as Stock OEM, Custom ROM, or Generic System Image (GSI)."""
        flavor = props.get("ro.build.flavor", "").lower()
        dev_prop = props.get("ro.product.device", "").lower()
        sys_dev = props.get("ro.product.system.device", "").lower()
        disp_id = props.get("ro.build.display.id", "").lower()
        tags = props.get("ro.build.tags", "").lower()

        # 1. GSI (Generic System Image) detection
        is_gsi = (
            any(k in flavor for k in ("gsi_", "treble_", "system_gsi", "aosp_arm64-userdebug", "aosp_arm-userdebug"))
            or any(k in dev_prop for k in ("phh", "gsi", "treble"))
            or any(k in sys_dev for k in ("phh", "gsi", "treble"))
            or "phh" in disp_id
            or "persist.sys.phh" in props
            or bool(props.get("ro.gsi.version_code", ""))
        )
        if is_gsi:
            ver = props.get("ro.build.version.release", "")
            return "gsi", f"Generic System Image (GSI Android {ver})"

        # 2. Custom ROM detection
        lineage_ver = props.get("ro.lineage.version", props.get("ro.lineage.build.version", ""))
        if lineage_ver or "lineage" in disp_id or "lineage" in flavor:
            return "custom_rom", f"LineageOS {lineage_ver}".strip()

        pe_ver = props.get("ro.pixelexperience.version", "")
        if pe_ver or "pixelexperience" in disp_id:
            return "custom_rom", f"PixelExperience {pe_ver}".strip()

        cr_ver = props.get("ro.crdroid.version", "")
        if cr_ver or "crdroid" in disp_id:
            return "custom_rom", f"crDroid {cr_ver}".strip()

        evo_ver = props.get("ro.evolution.version", "")
        if evo_ver or "evolution" in disp_id:
            return "custom_rom", f"Evolution X {evo_ver}".strip()

        mod_ver = props.get("ro.modversion", "")
        if mod_ver:
            return "custom_rom", f"Custom ROM ({mod_ver})"

        custom_rom_signatures = ("pixelos", "arrowos", "havoc", "paranoid", "corvus", "risingos", "derpfest")
        for sig in custom_rom_signatures:
            if sig in disp_id or sig in flavor:
                return "custom_rom", f"Custom ROM ({sig.title()})"

        # 3. Stock OEM detection
        known_oems = ("google", "samsung", "xiaomi", "redmi", "poco", "oneplus", "oppo", "realme", "motorola", "sony", "asus", "nokia")
        brand_norm = info.brand.lower().strip()
        if brand_norm in known_oems:
            return "stock", f"Official {brand_norm.title()} Stock Firmware"

        # Fallback
        if "release-keys" in tags:
            return "stock", "Stock OEM Firmware"
        return "unknown", "Android OS"

    # ---- Helpers -----------------------------------------------------------

    @staticmethod
    def _find_device(devices: list[ADBDevice], serial: str) -> Optional[ADBDevice]:
        """Find a device by serial, or return the first one if no serial."""
        if not devices:
            return None
        if serial:
            for d in devices:
                if d.serial == serial:
                    return d
            return None
        return devices[0]

    @staticmethod
    def _find_fb_device(devices: list[FastbootDevice], serial: str) -> Optional[FastbootDevice]:
        if not devices:
            return None
        if serial:
            for d in devices:
                if d.serial == serial:
                    return d
            return None
        return devices[0]

    @staticmethod
    def _adb_state_to_mode(state: str) -> str:
        """Map ADB device state to a FlashDock mode constant."""
        mapping = {
            "device": "system",
            "recovery": "recovery",
            "sideload": "sideload",
            "unauthorized": "unauthorized",
            "offline": "offline",
            "authorizing": "unauthorized",
            "bootloader": "bootloader",
        }
        return mapping.get(state, "system")
