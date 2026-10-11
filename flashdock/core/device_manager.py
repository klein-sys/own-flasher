"""
FlashDock — Device manager.

Runs a background poll loop that detects connected devices, maintains
the active :class:`DeviceInfo`, handles serial locking, and drives the
Phone Control Panel and status bar updates.

Spec reference: Sections 6, 15, 16.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from flashdock.config import Config
from flashdock.constants import ADB_POLL_INTERVAL_MS, DEVICE_MODES
from flashdock.core.device import DeviceDetector, DeviceInfo
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Allowed reboot targets per current mode
# ---------------------------------------------------------------------------
_REBOOT_MAP: dict[str, list[str]] = {
    # mode → list of reboot targets the phone panel should enable
    "system":       ["system", "recovery", "bootloader", "fastbootd", "download", "edl", "poweroff", "safemode"],
    "recovery":     ["system", "bootloader", "fastbootd", "poweroff"],
    "sideload":     ["system", "recovery", "bootloader"],
    "bootloader":   ["system", "recovery", "bootloader", "fastbootd"],
    "fastbootd":    ["system", "recovery", "bootloader", "fastbootd"],
    "download":     [],  # Samsung download mode — can't reboot via SW
    "edl":          [],  # Qualcomm EDL — can't reboot via SW
    "brom":         [],  # MTK BROM — can't reboot via SW
    "unauthorized": [],
    "offline":      [],
    "not_connected":[],
}


class DeviceManager:
    """Manages the lifecycle of a connected Android device.

    Public attributes
    -----------------
    device : DeviceInfo | None
        The current device snapshot.  ``None`` if nothing is connected.
    all_devices : list[DeviceInfo]
        Snapshots for every device detected in the latest poll.

    Callbacks
    ---------
    on_device_changed : (DeviceInfo | None) -> None
        Fired whenever the device state changes (connected, disconnected,
        mode change, re-detection).
    """

    def __init__(
        self,
        config: Config,
        adb: ADB,
        fastboot: Fastboot,
    ) -> None:
        self._config = config
        self._adb = adb
        self._fb = fastboot
        self._detector = DeviceDetector(adb, fastboot)

        self.device: Optional[DeviceInfo] = None
        self.all_devices: list[DeviceInfo] = []

        self.on_device_changed: Optional[Callable[[Optional[DeviceInfo]], None]] = None

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._poll_interval_s = ADB_POLL_INTERVAL_MS / 1000.0

    # ----- Lifecycle --------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop, daemon=True, name="DeviceManager",
        )
        self._thread.start()
        log.info("DeviceManager polling started (interval=%.1fs).", self._poll_interval_s)

    def stop(self) -> None:
        """Stop the polling thread."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        log.info("DeviceManager stopped.")

    # ----- Manual operations ------------------------------------------------

    def refresh(self) -> Optional[DeviceInfo]:
        """Run a single detection cycle and return the result."""
        self._detect_cycle()
        return self.device

    def lock_serial(self, serial: str) -> None:
        """Lock onto a specific device serial for safety."""
        self._config.set("locked_serial", serial)
        log.info("Serial locked: %s", serial)

    def unlock_serial(self) -> None:
        """Remove the serial lock."""
        self._config.set("locked_serial", None)
        log.info("Serial lock removed.")

    @property
    def locked_serial(self) -> Optional[str]:
        return self._config.locked_serial

    @property
    def is_serial_locked(self) -> bool:
        return self._config.locked_serial is not None

    @property
    def allowed_reboot_targets(self) -> list[str]:
        """Return which reboot buttons should be enabled."""
        if not self.device:
            return []
        return _REBOOT_MAP.get(self.device.mode, [])

    # ----- Reboot commands --------------------------------------------------

    def reboot(self, mode: str) -> bool:
        """Reboot the device to *mode*.  Returns True on success.

        Chooses the correct tool (ADB vs fastboot) based on current mode.
        """
        if not self.device or self.device.mode == "not_connected":
            log.warning("Cannot reboot: no device connected.")
            return False

        serial = self.device.serial
        current = self.device.mode
        log.info("Reboot requested: %s → %s (serial=%s)", current, mode, serial)

        # Determine which tool to use based on current mode
        if current in ("system", "recovery", "sideload"):
            return self._reboot_via_adb(serial, mode)
        elif current in ("bootloader", "fastbootd"):
            return self._reboot_via_fastboot(serial, mode)
        else:
            log.warning("Cannot reboot from mode: %s", current)
            return False

    def _reboot_via_adb(self, serial: str, target: str) -> bool:
        mapping = {
            "system":     lambda: self._adb.reboot(serial=serial),
            "recovery":   lambda: self._adb.reboot_recovery(serial=serial),
            "bootloader": lambda: self._adb.reboot_bootloader(serial=serial),
            "fastbootd":  lambda: self._adb.reboot_fastboot(serial=serial),
            "download":   lambda: self._adb.reboot(serial=serial, mode="download"),
            "edl":        lambda: self._adb.reboot_edl(serial=serial),
            "poweroff":   lambda: self._adb.poweroff(serial=serial),
            "safemode":   lambda: self._adb.reboot_safemode(serial=serial),
        }
        func = mapping.get(target)
        if not func:
            log.warning("Unknown reboot target: %s", target)
            return False
        res = func()
        return res.success

    def _reboot_via_fastboot(self, serial: str, target: str) -> bool:
        mapping = {
            "system":     lambda: self._fb.reboot(serial=serial),
            "recovery":   lambda: self._fb.reboot_recovery(serial=serial),
            "bootloader": lambda: self._fb.reboot_bootloader(serial=serial),
            "fastbootd":  lambda: self._fb.reboot_fastboot(serial=serial),
        }
        func = mapping.get(target)
        if not func:
            log.warning("Cannot reboot to %s from fastboot.", target)
            return False
        res = func()
        return res.success

    # ----- Auto boot-mode switching (Section 15) ----------------------------

    def switch_to_mode(
        self,
        target_mode: str,
        timeout: int = 120,
        dry_run: bool = False,
    ) -> bool:
        """Automatically reboot into *target_mode* and wait for the device.

        Used by every flow that needs a specific mode (e.g. rooting needs
        system → bootloader → system).

        Returns True if the device is now in *target_mode*.
        """
        if not self.device:
            log.error("switch_to_mode: no device.")
            return False

        if self.device.mode == target_mode:
            log.info("Already in %s mode.", target_mode)
            return True

        if dry_run:
            log.info("[DRY RUN] Would switch %s → %s", self.device.mode, target_mode)
            return True

        log.info("Switching mode: %s → %s", self.device.mode, target_mode)

        # Issue the reboot
        if not self.reboot(target_mode):
            log.error("Reboot command failed.")
            return False

        # Wait for the device to appear in the target mode
        return self._wait_for_mode(target_mode, timeout)

    def _wait_for_mode(self, target_mode: str, timeout: int) -> bool:
        """Poll until the device appears in *target_mode* or timeout."""
        deadline = time.monotonic() + timeout
        log.info("Waiting up to %ds for device in %s mode…", timeout, target_mode)

        while time.monotonic() < deadline:
            time.sleep(2)
            info = self._detector.detect(serial=self.device.serial if self.device else "")
            if info.mode == target_mode:
                self._update_device(info)
                log.info("Device appeared in %s mode.", target_mode)
                return True
            if self._stop_event.is_set():
                return False

        log.error("Timeout waiting for %s mode after %ds.", target_mode, timeout)
        return False

    # ----- Polling loop -----------------------------------------------------

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._detect_cycle()
            except Exception:
                log.exception("Error in device detection cycle.")
            # Sleep in small increments for responsiveness
            for _ in range(int(self._poll_interval_s * 10)):
                if self._stop_event.is_set():
                    return
                time.sleep(0.1)

    def _detect_cycle(self) -> None:
        """Run one detection cycle."""
        if not self._adb.available and not self._fb.available:
            self.all_devices = []
            if self.device is not None:
                self._update_device(None)
            return

        serial = self._config.locked_serial or ""

        # Detect all ADB devices for the selector
        all_infos: list[DeviceInfo] = []
        if self._adb.available:
            for adb_dev in self._adb.devices():
                info = self._detector.detect(serial=adb_dev.serial)
                all_infos.append(info)
        if self._fb.available:
            for fb_dev in self._fb.devices():
                # Skip if already found via ADB
                if any(d.serial == fb_dev.serial for d in all_infos):
                    continue
                info = self._detector.detect(serial=fb_dev.serial)
                all_infos.append(info)

        self.all_devices = all_infos

        # Pick the active device
        if serial:
            target = next((d for d in all_infos if d.serial == serial), None)
        elif all_infos:
            target = all_infos[0]
        else:
            target = None

        # Detect change
        old_mode = self.device.mode if self.device else "not_connected"
        old_serial = self.device.serial if self.device else ""
        new_mode = target.mode if target else "not_connected"
        new_serial = target.serial if target else ""

        if new_mode != old_mode or new_serial != old_serial:
            self._update_device(target)

    def _update_device(self, info: Optional[DeviceInfo]) -> None:
        """Update the current device and fire the callback."""
        self.device = info
        mode = info.mode if info else "not_connected"
        summary = info.summary_line if info else ""
        serial = info.serial if info else ""

        if mode == "not_connected":
            log.info("Device disconnected.")
        else:
            log.info("Device state: %s — %s (serial=%s)", mode, summary, serial)

        # Save last used serial
        if serial:
            self._config.set("last_device_serial", serial, save=False)

        if self.on_device_changed:
            try:
                self.on_device_changed(info)
            except Exception:
                log.exception("Error in on_device_changed callback.")
