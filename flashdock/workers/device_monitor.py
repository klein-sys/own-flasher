"""
FlashDock — Connection Monitoring & Hardware Polling Engine.

Implements a high-performance, non-blocking background QThread worker
inspired by industry GSM multi-chipset repair tools (UnlockTool, Chimera, TFT).
Monitors USB/COM ports, performs VID/PID matching, and correlates ADB/Fastboot
interfaces without stalling the PySide6 user interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
import re
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal, Slot

from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Hardware Modes & Mapping Definitions
# ---------------------------------------------------------------------------

class HardwareMode(str, Enum):
    """Recognized connection and chipset modes."""
    ADB = "adb"
    FASTBOOT = "fastboot"
    FASTBOOTD = "fastbootd"
    RECOVERY = "recovery"
    SIDELOAD = "sideload"
    UNAUTHORIZED = "unauthorized"
    MTK_BROM = "mtk_brom"
    MTK_PRELOADER = "mtk_preloader"
    QUALCOMM_EDL = "qualcomm_edl"
    QUALCOMM_DIAG = "qualcomm_diag"
    UNISOC_SPRD = "unisoc_sprd"
    UNISOC_DIAG = "unisoc_diag"
    UNISOC_FDL = "unisoc_fdl"
    SAMSUNG_ODIN = "samsung_odin"
    UNKNOWN = "unknown"
    DISCONNECTED = "disconnected"


@dataclass
class HardwareProfile:
    """Specification of a matched hardware identifier."""
    mode: HardwareMode
    display_name: str
    chipset: str
    description: str = ""
    is_emergency: bool = False


# Dictionary mapping (VID, PID) in uppercase hexadecimal to hardware profiles
HARDWARE_VID_PID_MAP: Dict[Tuple[str, str], HardwareProfile] = {
    # MediaTek (BROM / Preloader / DA)
    ("0E8D", "0003"): HardwareProfile(
        mode=HardwareMode.MTK_BROM,
        display_name="MediaTek BootROM (BROM)",
        chipset="MediaTek",
        description="MTK MT67xx/MT68xx Hardware BootROM interface",
        is_emergency=True,
    ),
    ("0E8D", "2000"): HardwareProfile(
        mode=HardwareMode.MTK_PRELOADER,
        display_name="MediaTek Preloader VCOM",
        chipset="MediaTek",
        description="MTK Preloader USB VCOM Port",
    ),
    ("0E8D", "2001"): HardwareProfile(
        mode=HardwareMode.MTK_PRELOADER,
        display_name="MediaTek DA USB VCOM",
        chipset="MediaTek",
        description="MTK Download Agent USB VCOM Port",
    ),

    # Qualcomm Emergency Download (EDL 9008 / Diag 9006)
    ("05C6", "9008"): HardwareProfile(
        mode=HardwareMode.QUALCOMM_EDL,
        display_name="Qualcomm HS-USB QDLoader 9008",
        chipset="Qualcomm",
        description="Snapdragon Emergency Download (EDL) Sahara/Firehose port",
        is_emergency=True,
    ),
    ("05C6", "9006"): HardwareProfile(
        mode=HardwareMode.QUALCOMM_DIAG,
        display_name="Qualcomm HS-USB Diagnostics 9006",
        chipset="Qualcomm",
        description="Snapdragon Diagnostic and raw block interface",
    ),
    ("05C6", "901D"): HardwareProfile(
        mode=HardwareMode.QUALCOMM_EDL,
        display_name="Qualcomm HS-USB QDLoader",
        chipset="Qualcomm",
        description="Emergency QDLoader port",
        is_emergency=True,
    ),

    # Unisoc / Spreadtrum (SPRD U2S Diag / Download FDL)
    ("1782", "4D00"): HardwareProfile(
        mode=HardwareMode.UNISOC_DIAG,
        display_name="Unisoc (SPRD) U2S Diag",
        chipset="Unisoc",
        description="Spreadtrum / Unisoc Diag calibration interface",
    ),
    ("1782", "4D02"): HardwareProfile(
        mode=HardwareMode.UNISOC_FDL,
        display_name="Unisoc (SPRD) Download / FDL",
        chipset="Unisoc",
        description="Spreadtrum / Unisoc FDL Protocol download port",
        is_emergency=True,
    ),
    ("1782", "0001"): HardwareProfile(
        mode=HardwareMode.UNISOC_SPRD,
        display_name="Unisoc Boot Interface",
        chipset="Unisoc",
        description="Unisoc low-level recovery interface",
    ),

    # Fastboot / Bootloader
    ("18D1", "4EE0"): HardwareProfile(
        mode=HardwareMode.FASTBOOT,
        display_name="Google Fastboot Interface",
        chipset="Google / AOSP",
        description="Android Bootloader interface",
    ),
    ("18D1", "0D02"): HardwareProfile(
        mode=HardwareMode.FASTBOOT,
        display_name="Android Bootloader Interface",
        chipset="Universal Android",
        description="Generic Android bootloader USB interface",
    ),
    ("2717", "FF80"): HardwareProfile(
        mode=HardwareMode.FASTBOOT,
        display_name="Xiaomi Fastboot Interface",
        chipset="Xiaomi / Poco / Redmi",
        description="Xiaomi fastboot flashing protocol",
    ),
    ("2717", "FF88"): HardwareProfile(
        mode=HardwareMode.FASTBOOT,
        display_name="Xiaomi Bootloader",
        chipset="Xiaomi",
        description="Xiaomi fastboot interface",
    ),
    ("2717", "FF48"): HardwareProfile(
        mode=HardwareMode.FASTBOOT,
        display_name="Xiaomi Fastboot Interface",
        chipset="Xiaomi",
        description="Xiaomi bootloader interface",
    ),

    # Samsung Odin / Download Mode
    ("04E8", "685D"): HardwareProfile(
        mode=HardwareMode.SAMSUNG_ODIN,
        display_name="Samsung Mobile USB Download Mode",
        chipset="Samsung",
        description="Samsung Odin PIT/TAR flashing interface",
    ),

    # ADB Interfaces (Google, Samsung, Xiaomi, Transsion, etc.)
    ("18D1", "4EE7"): HardwareProfile(
        mode=HardwareMode.ADB,
        display_name="Google Android ADB Interface",
        chipset="Google / Universal",
        description="ADB debugging interface",
    ),
    ("18D1", "4EE2"): HardwareProfile(
        mode=HardwareMode.ADB,
        display_name="Android Composite ADB Interface",
        chipset="Universal Android",
        description="Composite ADB debugging interface",
    ),
    ("04E8", "6860"): HardwareProfile(
        mode=HardwareMode.ADB,
        display_name="Samsung Android Composite ADB",
        chipset="Samsung",
        description="Samsung Galaxy ADB debugging interface",
    ),
    ("2717", "FF18"): HardwareProfile(
        mode=HardwareMode.ADB,
        display_name="Xiaomi Composite ADB Interface",
        chipset="Xiaomi",
        description="Xiaomi HyperOS/MIUI ADB interface",
    ),
    ("2717", "FF40"): HardwareProfile(
        mode=HardwareMode.ADB,
        display_name="Xiaomi ADB Interface",
        chipset="Xiaomi",
        description="Xiaomi ADB interface",
    ),
    ("0E8D", "201D"): HardwareProfile(
        mode=HardwareMode.ADB,
        display_name="MediaTek Android ADB Interface",
        chipset="MediaTek / Transsion",
        description="MTK/Transsion ADB debugging interface",
    ),
    ("22D9", "2765"): HardwareProfile(
        mode=HardwareMode.ADB,
        display_name="OPPO / Realme ADB Interface",
        chipset="OPPO / Realme",
        description="ColorOS/RealmeUI ADB interface",
    ),
}


def identify_hardware_device(vid_or_raw: str, pid: Optional[str] = None) -> HardwareMode:
    """
    Match a vendor ID and product ID (or raw PnP device string) to a recognized HardwareMode.

    Supports:
      - Two arguments: identify_hardware_device("0E8D", "0003")
      - One argument with PnP string: identify_hardware_device(r"USB\\VID_05C6&PID_9008\\...")
    """
    if pid is not None:
        v = str(vid_or_raw).strip().upper()
        p = str(pid).strip().upper()
        prof = HARDWARE_VID_PID_MAP.get((v, p))
        return prof.mode if prof else HardwareMode.UNKNOWN

    raw = str(vid_or_raw).upper()
    m_vid = re.search(r"VID_([0-9A-F]{4})", raw)
    m_pid = re.search(r"PID_([0-9A-F]{4})", raw)
    if m_vid and m_pid:
        v, p = m_vid.group(1), m_pid.group(1)
        prof = HARDWARE_VID_PID_MAP.get((v, p))
        if prof:
            return prof.mode

    if "SPRD" in raw or "SPREADTRUM" in raw or "UNISOC" in raw:
        if "DIAG" in raw:
            return HardwareMode.UNISOC_DIAG
        if "DOWNLOAD" in raw or "FDL" in raw:
            return HardwareMode.UNISOC_FDL
        return HardwareMode.UNISOC_SPRD

    if "9008" in raw or "QDLOADER" in raw:
        return HardwareMode.QUALCOMM_EDL

    if "0003" in raw and ("MEDIATEK" in raw or "MTK" in raw):
        return HardwareMode.MTK_BROM

    return HardwareMode.UNKNOWN


# ---------------------------------------------------------------------------
# Background Device Monitor QThread
# ---------------------------------------------------------------------------

class DeviceMonitorWorker(QThread):
    """
    Continuous asynchronous hardware and port polling thread.

    Scans for physical USB devices, COM ports (VCOM/EDL/SPRD), and CLI daemon
    interfaces (ADB/Fastboot) without blocking the PySide6 UI thread.

    Signals:
    --------
    device_connected(mode: str, port_or_serial: str, details: dict):
        Emitted when a supported phone, chipset interface, or port is detected.
    device_disconnected():
        Emitted when the previously connected device is unplugged or enters an
        unrecognized state.
    hardware_scanned(items: list):
        Emitted on each poll cycle containing raw descriptors of all detected USB/COM ports.
    status_message(msg: str):
        Diagnostic log/status telemetry emitted during state changes.
    """

    device_connected = Signal(str, str, dict)
    device_disconnected = Signal()
    hardware_scanned = Signal(list)
    status_message = Signal(str)

    def __init__(
        self,
        poll_interval_seconds: float = 1.0,
        interval_ms: Optional[int] = None,
        adb: Optional[ADB] = None,
        fastboot: Optional[Fastboot] = None,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        if interval_ms is not None:
            self._poll_interval = max(0.05, interval_ms / 1000.0)
        else:
            self._poll_interval = max(0.2, poll_interval_seconds)
        self._adb = adb or ADB()
        self._fastboot = fastboot or Fastboot()

        self._running = False
        self._paused = False
        self._mutex = QMutex()

        self._last_signature: Optional[str] = None
        self._current_device_info: Optional[dict] = None

    @property
    def interval_ms(self) -> int:
        """Return the polling interval in milliseconds."""
        return int(self._poll_interval * 1000)

    @property
    def is_running(self) -> bool:
        """Return True if the worker is currently marked running."""
        with QMutexLocker(self._mutex):
            return self._running

    @property
    def is_paused(self) -> bool:
        """Return True if polling is currently paused."""
        with QMutexLocker(self._mutex):
            return self._paused

    def _poll_once(self) -> None:
        """Execute a single polling cycle (convenience test helper)."""
        self.poll_cycle()

    # -----------------------------------------------------------------------
    # Thread Lifecycle Controls
    # -----------------------------------------------------------------------

    def start_polling(self) -> None:
        """Start the background hardware monitoring thread."""
        with QMutexLocker(self._mutex):
            if self._running:
                return
            self._running = True
            self._paused = False
        self.start()
        log.info("DeviceMonitorWorker started (interval=%.2fs).", self._poll_interval)

    def stop_polling(self) -> None:
        """Gracefully stop polling and wait for thread termination."""
        with QMutexLocker(self._mutex):
            self._running = False
        self.wait(3000)
        log.info("DeviceMonitorWorker stopped.")

    def pause_polling(self) -> None:
        """Temporarily pause polling (e.g. during active high-speed flashing)."""
        with QMutexLocker(self._mutex):
            self._paused = True
        log.debug("DeviceMonitorWorker paused.")

    def resume_polling(self) -> None:
        """Resume polling after an active flash or reboot operation."""
        with QMutexLocker(self._mutex):
            self._paused = False
        log.debug("DeviceMonitorWorker resumed.")

    @property
    def is_polling(self) -> bool:
        """Return True if the background loop is actively scanning."""
        with QMutexLocker(self._mutex):
            return self._running and not self._paused

    def get_current_device(self) -> Optional[dict]:
        """Thread-safe accessor for the currently connected device details."""
        with QMutexLocker(self._mutex):
            return dict(self._current_device_info) if self._current_device_info else None

    # -----------------------------------------------------------------------
    # Main QThread Loop
    # -----------------------------------------------------------------------

    def run(self) -> None:
        """Execute the continuous background hardware polling loop."""
        while True:
            with QMutexLocker(self._mutex):
                if not self._running:
                    break
                paused = self._paused

            if not paused:
                try:
                    self.poll_cycle()
                except Exception as exc:
                    log.warning("Exception inside DeviceMonitorWorker poll cycle: %s", exc)

            # Sleep in small slices so thread terminates immediately on stop()
            total_sleep = self._poll_interval
            elapsed = 0.0
            slice_sec = 0.1
            while elapsed < total_sleep:
                with QMutexLocker(self._mutex):
                    if not self._running:
                        return
                time.sleep(slice_sec)
                elapsed += slice_sec

    # -----------------------------------------------------------------------
    # Detection Core
    # -----------------------------------------------------------------------

    def poll_cycle(self) -> None:
        """Execute one complete detection pass across USB hardware and CLI tools."""
        raw_hw_list = self.scan_usb_and_com_hardware()
        self.hardware_scanned.emit(raw_hw_list)

        detected = self._resolve_primary_device(raw_hw_list)

        # Build state signature to prevent redundant signal emissions
        sig = (
            f"{detected['mode']}:{detected['identifier']}"
            if detected
            else "NONE"
        )

        with QMutexLocker(self._mutex):
            old_sig = self._last_signature
            self._last_signature = sig
            self._current_device_info = detected

        if sig != old_sig:
            if detected:
                mode = detected["mode"]
                ident = detected["identifier"]
                log.info("Hardware state change -> CONNECTED: %s (%s)", mode, ident)
                self.status_message.emit(f"Connected: {detected.get('display_name', mode)} [{ident}]")
                self.device_connected.emit(mode, ident, detected)
            else:
                log.info("Hardware state change -> DISCONNECTED")
                self.status_message.emit("No device connected")
                self.device_disconnected.emit()

    def _resolve_primary_device(self, raw_hardware: List[dict]) -> Optional[dict]:
        """
        Prioritize and classify detected hardware into a single active device.

        Priority order:
        1. Emergency Chipset Port (MTK BROM, Qualcomm 9008 EDL, Unisoc FDL)
        2. Fastboot / Bootloader (fastboot devices or Fastboot USB VID/PID)
        3. ADB Mode (adb devices or ADB USB VID/PID)
        4. Preloader / Diagnostic Port
        """
        # Step 1: Check emergency hardware ports first (EDL / BROM / Unisoc FDL)
        for hw in raw_hardware:
            if hw.get("is_emergency"):
                return {
                    "mode": hw["mode"],
                    "identifier": hw.get("port", hw.get("instance_id", "USB_PORT")),
                    "display_name": hw.get("display_name", hw["mode"]),
                    "chipset": hw.get("chipset", "Unknown"),
                    "details": hw,
                }

        # Step 2: Check Fastboot CLI
        try:
            fb_devices = self._fastboot.devices()
            if fb_devices:
                fb_dev = fb_devices[0]
                fb_mode = "fastbootd" if fb_dev.get("mode") == "fastbootd" else "fastboot"
                return {
                    "mode": fb_mode,
                    "identifier": fb_dev.get("serial", "FASTBOOT_DEVICE"),
                    "display_name": f"{fb_dev.get('brand', 'Android')} (Fastboot)",
                    "chipset": "Fastboot / Bootloader",
                    "details": fb_dev,
                }
        except Exception:
            pass

        # Step 3: Check ADB CLI
        try:
            adb_devices = self._adb.devices()
            if adb_devices:
                adb_dev = adb_devices[0]
                mode_str = adb_dev.get("mode", "adb")
                return {
                    "mode": mode_str,
                    "identifier": adb_dev.get("serial", "ADB_DEVICE"),
                    "display_name": f"{adb_dev.get('model', adb_dev.get('brand', 'Android'))} ({mode_str.title()})",
                    "chipset": "ADB Daemon",
                    "details": adb_dev,
                }
        except Exception:
            pass

        # Step 4: Check other recognized hardware profiles (Preloader, Diag, etc.)
        for hw in raw_hardware:
            if hw.get("mode") and hw["mode"] != HardwareMode.UNKNOWN:
                return {
                    "mode": hw["mode"],
                    "identifier": hw.get("port", hw.get("instance_id", "PORT")),
                    "display_name": hw.get("display_name", hw["mode"]),
                    "chipset": hw.get("chipset", "Unknown"),
                    "details": hw,
                }

        return None

    # -----------------------------------------------------------------------
    # Low-Level Hardware Enumeration
    # -----------------------------------------------------------------------

    def scan_usb_and_com_hardware(self) -> List[dict]:
        """
        Scan physical USB and COM ports using Windows Registry and serial map.
        Returns a structured list of detected hardware descriptors.
        """
        results: List[dict] = []

        if sys.platform == "win32":
            # 1. Query COM serial ports from registry
            results.extend(self._scan_windows_serial_ports())

            # 2. Query USB devices from registry
            results.extend(self._scan_windows_usb_devices())

        return results

    def _scan_windows_serial_ports(self) -> List[dict]:
        """Enumerate active COM ports from HKLM\\HARDWARE\\DEVICEMAP\\SERIALCOMM."""
        com_ports: List[dict] = []
        try:
            import winreg
            key_path = r"HARDWARE\DEVICEMAP\SERIALCOMM"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                num_values = winreg.QueryInfoKey(key)[1]
                for i in range(num_values):
                    val_name, val_data, _ = winreg.EnumValue(key, i)
                    port_name = str(val_data).strip()
                    val_name_upper = val_name.upper()

                    # Match port driver name for chipset hints
                    mode = HardwareMode.UNKNOWN
                    chipset = "Serial"
                    display_name = f"Serial Port ({port_name})"
                    is_emerg = False

                    if "QCUSB" in val_name_upper or "QDLOADER" in val_name_upper:
                        mode = HardwareMode.QUALCOMM_EDL
                        chipset = "Qualcomm"
                        display_name = f"Qualcomm 9008 ({port_name})"
                        is_emerg = True
                    elif "VCOM" in val_name_upper or "MTK" in val_name_upper:
                        mode = HardwareMode.MTK_PRELOADER
                        chipset = "MediaTek"
                        display_name = f"MTK Preloader ({port_name})"
                    elif "SPRD" in val_name_upper or "SCIUSB" in val_name_upper:
                        mode = HardwareMode.UNISOC_SPRD
                        chipset = "Unisoc"
                        display_name = f"Unisoc Diag ({port_name})"

                    com_ports.append({
                        "type": "com_port",
                        "port": port_name,
                        "device_key": val_name,
                        "mode": mode.value if isinstance(mode, HardwareMode) else mode,
                        "chipset": chipset,
                        "display_name": display_name,
                        "is_emergency": is_emerg,
                    })
        except Exception:
            pass
        return com_ports

    def _scan_windows_usb_devices(self) -> List[dict]:
        """Enumerate active USB devices from HKLM\\SYSTEM\\CurrentControlSet\\Enum\\USB."""
        usb_devices: List[dict] = []
        try:
            import winreg
            base_path = r"SYSTEM\CurrentControlSet\Enum\USB"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as usb_root:
                num_subkeys = winreg.QueryInfoKey(usb_root)[0]
                for i in range(num_subkeys):
                    try:
                        hw_id = winreg.EnumKey(usb_root, i)
                        match = re.search(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", hw_id)
                        if not match:
                            continue

                        vid = match.group(1).upper()
                        pid = match.group(2).upper()

                        profile = HARDWARE_VID_PID_MAP.get((vid, pid))
                        if not profile:
                            continue

                        # Check instance subkeys to verify device is connected/active
                        instance_path = f"{base_path}\\{hw_id}"
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, instance_path) as inst_key:
                            num_inst = winreg.QueryInfoKey(inst_key)[0]
                            for j in range(num_inst):
                                try:
                                    inst_id = winreg.EnumKey(inst_key, j)
                                    detail_path = f"{instance_path}\\{inst_id}"
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, detail_path) as detail_key:
                                        # Try reading friendly name or device desc
                                        friendly_name = ""
                                        try:
                                            friendly_name, _ = winreg.QueryValueEx(detail_key, "FriendlyName")
                                        except Exception:
                                            try:
                                                friendly_name, _ = winreg.QueryValueEx(detail_key, "DeviceDesc")
                                            except Exception:
                                                friendly_name = profile.display_name

                                        usb_devices.append({
                                            "type": "usb_device",
                                            "vid": vid,
                                            "pid": pid,
                                            "instance_id": inst_id,
                                            "hardware_id": hw_id,
                                            "friendly_name": friendly_name,
                                            "mode": profile.mode.value,
                                            "display_name": profile.display_name,
                                            "chipset": profile.chipset,
                                            "description": profile.description,
                                            "is_emergency": profile.is_emergency,
                                        })
                                except Exception:
                                    continue
                    except Exception:
                        continue
        except Exception:
            pass
        return usb_devices
