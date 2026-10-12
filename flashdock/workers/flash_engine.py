"""
FlashDock — Firmware Flashing, Partition Management & Safety Backups Engine.

Provides an asynchronous QThread worker for executing chunked flashing operations,
generating SHA-256 checksums, creating pre-flash safety backups of critical NVRAM/EFS
partitions, and driving bootloader unlock/relock controllers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal, Slot

from flashdock.constants import BACKUPS_DIR
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import acquire_flash_lock, is_flash_locked, release_flash_lock
from flashdock.workers.device_monitor import check_windows_usb_selective_suspend

log = get_logger(__name__)

CRITICAL_CALIBRATION_PARTITIONS: list[str] = ["efs", "nvram", "nvdata", "persist", "sec_efs"]


def is_usb_disconnect_error(text: str) -> bool:
    """Detect if error output indicates USB link interruption or mid-transfer drop."""
    t = (text or "").lower()
    patterns = (
        "command write failed",
        "no devices/emulators found",
        "write to device failed",
        "status read failed",
        "connection reset",
        "device offline",
        "pipe error",
        "error: closed",
        "protocol fault",
        "device disconnected",
        "disconnected mid-transfer",
        "disconnected",
        "device unauthorized",
        "press any key to exit",
        "error: device not found",
    )
    if any(p in t for p in patterns):
        return True
    if "device" in t and ("not found" in t or "offline" in t or "unauthorized" in t or "disconnect" in t):
        return True
    return False


def parse_boot_image_header(file_path: Path) -> dict[str, Any]:
    """
    Parse standard Android boot image header (v0-v4) for Anti-Rollback (ARP) inspection.
    Extracts kernel/ramdisk size, header version, OS version, and patch level.
    """
    if not file_path.is_file() or file_path.stat().st_size < 64:
        return {"is_boot_image": False}

    try:
        with open(file_path, "rb") as f:
            magic = f.read(8)
            if magic != b"ANDROID!":
                return {"is_boot_image": False}

            header_data = f.read(56)

        hdr_ver_candidate = struct.unpack("<I", header_data[32:36])[0]
        if hdr_ver_candidate in (3, 4):
            header_version = hdr_ver_candidate
            os_version_raw = struct.unpack("<I", header_data[8:12])[0]
            kernel_size = struct.unpack("<I", header_data[0:4])[0]
            ramdisk_size = struct.unpack("<I", header_data[4:8])[0]
        else:
            header_version = hdr_ver_candidate if hdr_ver_candidate in (0, 1, 2) else 0
            os_version_raw = struct.unpack("<I", header_data[36:40])[0] if len(header_data) >= 40 else 0
            kernel_size = struct.unpack("<I", header_data[0:4])[0]
            ramdisk_size = struct.unpack("<I", header_data[8:12])[0]

        os_version_val = (os_version_raw >> 11) & 0x1FFFFF
        os_patch_level_val = os_version_raw & 0x7FF

        if os_version_val > 0:
            major = (os_version_val >> 14) & 0x7F
            minor = (os_version_val >> 7) & 0x7F
            patch = os_version_val & 0x7F
            os_version_str = f"{major}.{minor}.{patch}"
        else:
            os_version_str = "unknown"

        if os_patch_level_val > 0:
            year = 2000 + ((os_patch_level_val >> 4) & 0x7F)
            month = os_patch_level_val & 0x0F
            os_patch_level_str = f"{year:04d}-{month:02d}"
        else:
            os_patch_level_str = "unknown"

        return {
            "is_boot_image": True,
            "header_version": header_version,
            "kernel_size": kernel_size,
            "ramdisk_size": ramdisk_size,
            "os_version": os_version_str,
            "os_patch_level": os_patch_level_str,
            "patch_level": os_patch_level_str,
            "raw_os_version": os_version_raw,
        }
    except Exception as exc:
        log.debug("Exception parsing boot image header %s: %s", file_path, exc)
        return {"is_boot_image": False}


def validate_active_slot(
    fastboot: Fastboot,
    serial: str,
    requested_slot: Optional[str] = None,
    force_override: bool = False,
) -> tuple[bool, str, str]:
    """
    Validate active slot against Fastboot device.
    Returns (is_valid, active_slot_token, error_message).
    """
    if force_override:
        req = (requested_slot or "").strip().lower().lstrip("_")
        return True, f"_{req}" if req else "", ""

    def _query_fb(var_name: str) -> str:
        for attr in ("getvar", "get_var"):
            fn = getattr(fastboot, attr, None)
            if callable(fn):
                try:
                    val = fn(var_name, serial=serial)
                    if isinstance(val, str):
                        return val.strip()
                except Exception:
                    pass
        return ""

    try:
        raw_val = _query_fb("current-slot")
        raw_slot = raw_val.lower().lstrip("_")
        req = (requested_slot or "").strip().lower().lstrip("_")

        if raw_slot in ("a", "b"):
            if req and req != raw_slot:
                return False, f"_{raw_slot}", (
                    f"Active Slot Desync Detected: Target requested slot is '_{req}', "
                    f"but Fastboot active slot is '_{raw_slot}'."
                )
            return True, f"_{raw_slot}", ""

        # Fastboot returned empty or non-a/b slot
        slot_count = _query_fb("slot-count")
        if req in ("a", "b") or (slot_count and slot_count not in ("0", "1", "")):
            return False, "", (
                f"Fastboot reported empty or ambiguous current-slot for slot-specific partition target '{requested_slot}'. "
                "Aborting to prevent inactive slot corruption."
            )
        return True, "", ""
    except Exception as exc:
        return False, "", f"Fastboot slot query exception: {exc}"


class FlashOperationType(str, Enum):
    """Types of asynchronous flashing operations supported by FlashEngineWorker."""
    FLASH_PARTITION = "flash_partition"
    SAFETY_BACKUP = "safety_backup"
    BACKUP_CALIBRATION = "safety_backup"
    BOOTLOADER_UNLOCK = "bootloader_unlock"
    BOOTLOADER_LOCK = "bootloader_lock"
    ERASE_PARTITION = "erase_partition"
    REBOOT = "reboot"


@dataclass
class FlashTask:
    """Execution payload submitted to the FlashEngineWorker."""
    operation: FlashOperationType = FlashOperationType.FLASH_PARTITION
    partition: str = ""
    partition_name: str = ""
    file_path: Optional[Path] = None
    image_path: Optional[str | Path] = None
    expected_sha256: str = ""
    serial: str = ""
    device_serial: str = ""
    slot: Optional[str] = None  # "_a" or "_b" or None
    wipe_data: bool = False
    pre_backup_efs: bool = True
    backup_calibration: bool = True
    backup_dir: Optional[str | Path] = None
    method: str = "flashing"  # "flashing" or "oem"
    unlock_token: str = ""
    reboot_target: str = "system"
    force_relock: bool = False
    allow_relock: bool = False
    confirmation_word: str = ""
    device_brand: str = ""
    force_slot_override: bool = False
    allow_rollback: bool = False
    device_security_patch: str = ""
    block_on_arp_downgrade: bool = False

    def __post_init__(self) -> None:
        if self.partition_name and not self.partition:
            self.partition = self.partition_name
        if self.device_serial and not self.serial:
            self.serial = self.device_serial
        if self.image_path and not self.file_path:
            self.file_path = Path(self.image_path)
        if not self.backup_calibration:
            self.pre_backup_efs = False


class FlashEngineWorker(QThread):
    """
    Decoupled Asynchronous Flashing & Partition Management QThread.

    Executes long-running flashing tasks without freezing the PySide6 UI loop.

    Signals:
    --------
    progress_changed(current_bytes: int, total_bytes: int, percentage: int):
        Emitted during chunked file reading, SHA-256 calculation, and fastboot upload.
    status_changed(status_text: str):
        High-level stage description (e.g. "Calculating Checksum...", "Flashing boot_a...").
    log_emitted(level: str, message: str):
        Structured console telemetry stream with level: "INFO", "WARN", "SUCCESS", "ERROR".
    flash_finished(success: bool, message: str):
        Emitted upon task termination with success flag and detail message.
    """

    progress_changed = Signal(int, int, int)
    status_changed = Signal(str)
    log_emitted = Signal(str, str)
    flash_finished = Signal(bool, str)

    def __init__(
        self,
        task_or_adb: Optional[FlashTask | ADB] = None,
        fastboot: Optional[Fastboot] = None,
        backups_dir: Optional[Path] = None,
        parent: Optional[Any] = None,
        adb: Optional[ADB] = None,
        task: Optional[FlashTask] = None,
    ) -> None:
        super().__init__(parent)
        if isinstance(task_or_adb, FlashTask):
            self._task = task_or_adb
            self.adb = adb or ADB()
        elif isinstance(task_or_adb, ADB):
            self.adb = task_or_adb
            self._task = task
        else:
            self.adb = adb or ADB()
            self._task = task
        self.fastboot = fastboot or Fastboot()
        self.backups_dir = backups_dir or BACKUPS_DIR
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self._is_cancelled = False
        self._mutex = QMutex()

    # -----------------------------------------------------------------------
    # Task Submission
    # -----------------------------------------------------------------------

    def execute_task(self, task: FlashTask) -> None:
        """Submit a task and launch the background flashing thread."""
        with QMutexLocker(self._mutex):
            if self.isRunning():
                raise RuntimeError("FlashEngineWorker is already busy executing a task.")
            self._task = task
            self._is_cancelled = False
        self.start()

    def cancel(self) -> None:
        """Request cooperative cancellation of the running operation."""
        self.requestInterruption()
        with QMutexLocker(self._mutex):
            self._is_cancelled = True
        self.log_emitted.emit("WARN", "Cancellation requested by operator.")

    @property
    def is_cancelled(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._is_cancelled or self.isInterruptionRequested()

    # -----------------------------------------------------------------------
    # Background Thread Dispatcher
    # -----------------------------------------------------------------------

    def run(self) -> None:
        """Execute the submitted FlashTask asynchronously."""
        with QMutexLocker(self._mutex):
            task = self._task

        if not task:
            self.flash_finished.emit(False, "No task provided to FlashEngineWorker.")
            return

        acquired = acquire_flash_lock()
        try:
            self.log_emitted.emit("INFO", f"Starting operation: {task.operation.value.upper()}")

            if task.operation == FlashOperationType.FLASH_PARTITION:
                self._run_flash_partition(task)
            elif task.operation == FlashOperationType.SAFETY_BACKUP:
                self._run_safety_backup(task)
            elif task.operation == FlashOperationType.BOOTLOADER_UNLOCK:
                self._run_bootloader_unlock(task)
            elif task.operation == FlashOperationType.BOOTLOADER_LOCK:
                self._run_bootloader_lock(task)
            elif task.operation == FlashOperationType.ERASE_PARTITION:
                self._run_erase_partition(task)
            elif task.operation == FlashOperationType.REBOOT:
                self._run_reboot(task)
            else:
                raise ValueError(f"Unknown operation: {task.operation}")

        except Exception as exc:
            log.error("FlashEngineWorker task error: %s", exc, exc_info=True)
            self.log_emitted.emit("ERROR", f"Operation failed: {exc}")
            self.flash_finished.emit(False, str(exc))
        finally:
            if acquired:
                release_flash_lock()

    # -----------------------------------------------------------------------
    # 1. Partition Flashing with Pre-Backup & Checksums
    # -----------------------------------------------------------------------

    def _run_flash_partition(self, task: FlashTask) -> None:
        """Execute single-partition flash with pre-verification and optional backup."""
        if not task.file_path or not task.file_path.exists():
            raise FileNotFoundError(f"Flash target file not found: {task.file_path}")

        file_size = task.file_path.stat().st_size
        self.status_changed.emit(f"Verifying integrity of {task.file_path.name}...")
        self.log_emitted.emit("INFO", f"Target file size: {file_size / (1024*1024):.2f} MB")

        # Step 1: Calculate SHA-256 with byte progress updates
        sha256_hash = self.compute_sha256_with_progress(task.file_path)
        if self.is_cancelled:
            self.flash_finished.emit(False, "Operation cancelled during checksum calculation.")
            return

        self.log_emitted.emit("SUCCESS", f"SHA-256 verified: {sha256_hash}")

        # Step 2: Safety Pre-Backup (NVRAM / EFS / Persist) if enabled
        if task.pre_backup_efs:
            self.status_changed.emit("Performing safety pre-flash calibration backup...")
            self.log_emitted.emit("INFO", "Checking calibration blocks (EFS / NVRAM / Persist)...")
            try:
                backup_ok = self._perform_calibration_backup(task.serial)
                if not backup_ok:
                    raise RuntimeError("Pre-flash calibration backup failed or was aborted (< 2GB free disk or write error).")
            except Exception as backup_exc:
                self.log_emitted.emit("ERROR", f"Pre-backup critical error: {backup_exc}")
                raise

        # Step 3: Fastboot Flash Execution
        target_part = task.partition
        if task.slot and not target_part.endswith(("_a", "_b")):
            target_part = f"{target_part}{task.slot}"

        # Active Slot Desync Guard
        is_slot_specific = target_part.endswith(("_a", "_b")) or bool(task.slot)
        if is_slot_specific:
            slot_token = task.slot or (target_part[-2:] if target_part.endswith(("_a", "_b")) else None)
            valid_slot, current_slot, slot_err = validate_active_slot(
                self.fastboot,
                task.serial,
                requested_slot=slot_token,
                force_override=task.force_slot_override,
            )
            if not valid_slot and not task.force_slot_override:
                raise RuntimeError(
                    f"Active Slot Desync Guard: {slot_err or 'Fastboot reported empty or ambiguous active slot.'} "
                    f"Flashing slot-specific partition '{target_part}' without validated slot token is blocked to prevent bricking. "
                    "Verify device connection or specify explicit slot override."
                )
            elif valid_slot and current_slot:
                self.log_emitted.emit("INFO", f"Active slot verified: {current_slot}")

        # Anti-Rollback Protection (ARP / AVB 2.0)
        part_base = target_part.rstrip("_ab")
        if part_base in ("boot", "init_boot", "vendor_boot"):
            hdr = parse_boot_image_header(task.file_path)
            if hdr.get("is_boot_image"):
                img_patch = hdr.get("os_patch_level", "unknown")
                dev_patch = task.device_security_patch
                self.log_emitted.emit("INFO", f"Boot Image OS Version: {hdr.get('os_version')} | Patch Level: {img_patch}")
                if dev_patch and img_patch != "unknown" and img_patch < dev_patch[:7]:
                    self.log_emitted.emit(
                        "WARN",
                        f"ANTI-ROLLBACK (ARP) WARNING: Target image security patch level ({img_patch}) is older than "
                        f"device patch level ({dev_patch}). Flashing older firmware on Qualcomm / Samsung / Xiaomi devices "
                        "with active rollback counters can blow QFUSEs or trigger EDL-only hard-brick."
                    )
                    if task.block_on_arp_downgrade and not task.allow_rollback:
                        raise RuntimeError(
                            f"Anti-Rollback Protection Lockout: Target image patch ({img_patch}) is older than device ({dev_patch}). "
                            "Flashing blocked to protect device QFUSE/rollback counters."
                        )

        # Windows Power / Selective Suspend notice for large firmware images
        if file_size > 500 * 1024 * 1024:
            suspend_enabled, suspend_msg = check_windows_usb_selective_suspend()
            if suspend_enabled:
                self.log_emitted.emit("WARN", f"Power Management Warning: {suspend_msg}")

        self.status_changed.emit(f"Flashing {task.file_path.name} -> {target_part}...")
        self.log_emitted.emit("INFO", f"Executing: fastboot flash {target_part} \"{task.file_path.name}\"")

        res = self.fastboot.flash(target_part, str(task.file_path), serial=task.serial)
        success = getattr(res, "success", bool(res))
        if not success:
            err = getattr(res, "stderr", None) or getattr(res, "output", None) or "Fastboot flash returned an error."
            if is_usb_disconnect_error(str(err)):
                self.log_emitted.emit("ERROR", "MID-FLASH USB DISCONNECT DETECTED: Hardware link dropped during active flash!")
                self.log_emitted.emit("WARN", "RECOVERY ADVICE: Do NOT power off phone. Re-seat USB cable on a rear USB 2.0 port and re-flash.")
                raise RuntimeError(f"Flashing aborted due to mid-transfer USB disconnection: {err}")
            raise RuntimeError(f"Flashing failed: {err}")

        # Signal completion
        self.progress_changed.emit(file_size, file_size, 100)
        self.status_changed.emit(f"Flashing of {target_part} completed successfully!")
        self.log_emitted.emit("SUCCESS", f"Partition [{target_part}] updated successfully.")
        self.flash_finished.emit(True, f"Successfully flashed {target_part}")

    def calculate_file_sha256(self, file_path: str | Path) -> str:
        """Calculate SHA-256 while emitting progress_changed signals."""
        return self.compute_sha256_with_progress(Path(file_path))

    def _perform_flash_partition(self, task: FlashTask) -> tuple[bool, str]:
        """Synchronous wrapper for partition flashing logic."""
        try:
            self._run_flash_partition(task)
            return True, f"Successfully flashed {task.partition}"
        except Exception as exc:
            return False, str(exc)

    def compute_sha256_with_progress(self, file_path: Path) -> str:
        """Compute SHA-256 while emitting progress_changed signals."""
        hasher = hashlib.sha256()
        total_bytes = file_path.stat().st_size
        bytes_read = 0
        chunk_size = 1024 * 1024  # 1 MB chunk

        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                if self.is_cancelled:
                    return ""
                hasher.update(chunk)
                bytes_read += len(chunk)
                pct = int((bytes_read / total_bytes) * 100) if total_bytes > 0 else 0
                self.progress_changed.emit(bytes_read, total_bytes, pct)

        return hasher.hexdigest()

    # -----------------------------------------------------------------------
    # 2. Safety Pre-Backup (NVRAM / EFS / Persist)
    # -----------------------------------------------------------------------

    def _run_safety_backup(self, task: FlashTask) -> None:
        """Explicit safety backup task for telemetry and calibration partitions."""
        self.status_changed.emit("Backing up critical calibration blocks...")
        res = self._perform_calibration_backup(task)
        self.progress_changed.emit(100, 100, 100)
        if isinstance(res, tuple):
            ok, msg = res
            if ok:
                self.status_changed.emit("Safety backup completed!")
                self.flash_finished.emit(True, msg)
            else:
                self.status_changed.emit("Safety backup restricted.")
                self.flash_finished.emit(False, msg)
        else:
            self.status_changed.emit("Safety backup completed!")
            self.flash_finished.emit(True, f"Backup saved to: {res}")

    def _perform_calibration_backup(self, serial_or_task: Any = "") -> Any:
        """
        Back up critical partitions (efs, nvram, nvdata, persist, sec_efs) to disk.
        Supports Fastboot raw partition dumps or ADB dd commands when available.
        Can be invoked with a device serial str or a full FlashTask.
        """
        is_task_call = isinstance(serial_or_task, FlashTask)
        if is_task_call:
            task: FlashTask = serial_or_task
            serial = task.serial or task.device_serial
            custom_dir = Path(task.backup_dir) if task.backup_dir else None
        else:
            serial = str(serial_or_task)
            custom_dir = None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if custom_dir:
            target_dir = custom_dir
        else:
            target_dir = self.backups_dir / (serial or "DEVICE") / f"calibration_{timestamp}"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Pre-Flash Disk Space & Write Integrity Check
        try:
            usage = shutil.disk_usage(target_dir.anchor or str(target_dir))
            free_gb = usage.free / (1024 ** 3)
            if free_gb < 2.0:
                raise RuntimeError(
                    f"Pre-flash integrity check failed: Insufficient disk space on backup volume ({free_gb:.2f} GB free < 2.0 GB required). "
                    "Free up disk space before modifying device partitions to ensure safety backups can be stored."
                )
            test_probe = target_dir / ".write_probe.tmp"
            test_probe.write_text("probe", encoding="utf-8")
            test_probe.unlink(missing_ok=True)
        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Pre-flash integrity check failed: Backup directory is not writable ({target_dir}): {exc}"
            )

        calibration_partitions = CRITICAL_CALIBRATION_PARTITIONS
        backed_up = 0

        # Mode detection: identify if device is attached via Fastboot or ADB
        fb_devices = self.fastboot.devices() if hasattr(self.fastboot, "devices") else []
        is_fastboot = any(d.get("serial") == serial for d in fb_devices) if fb_devices and serial else bool(fb_devices)
        adb_state = self.adb.get_state(serial=serial) if hasattr(self.adb, "get_state") else ""
        is_adb = bool(adb_state and adb_state not in ("unknown", "offline"))

        detected_mode = "fastboot" if is_fastboot else ("adb" if is_adb else "fastboot")
        fetch_restricted = False

        if detected_mode == "fastboot":
            for part in calibration_partitions:
                if self.is_cancelled:
                    break
                dest_file = target_dir / f"{part}.img"
                try:
                    res = self.fastboot._run(["fetch", part, str(dest_file)], serial=serial, timeout=15, action=f"fetch_{part}")
                    if getattr(res, "success", False) and dest_file.exists() and dest_file.stat().st_size > 0:
                        self.log_emitted.emit("SUCCESS", f"Dumped partition via fastboot fetch: {part}")
                        backed_up += 1
                    else:
                        if not fetch_restricted:
                            fetch_restricted = True
                            self.log_emitted.emit(
                                "WARN",
                                "Fastboot partition fetch rejected by bootloader: readback restricted on retail state."
                            )
                            self.log_emitted.emit(
                                "INFO",
                                "Note: Retail Android bootloaders disable fastboot partition readback. "
                                "To dump calibration blocks (EFS/NVRAM), boot custom recovery (TWRP) or use root ADB."
                            )
                except Exception as exc:
                    log.debug("Fastboot fetch error for %s: %s", part, exc)
                    continue
        elif detected_mode == "adb":
            # Test root availability
            id_out = ""
            try:
                id_out = str(self.adb.shell(["id", "-u"], serial=serial) or "").strip()
            except Exception:
                pass
            is_root = id_out == "0"

            if not is_root:
                self.log_emitted.emit(
                    "WARN",
                    "Device connected in ADB mode without root: /dev/block access to calibration partitions is restricted."
                )
            else:
                for part in calibration_partitions:
                    if self.is_cancelled:
                        break
                    dest_file = target_dir / f"{part}.img"
                    try:
                        dd_cmd = f"dd if=/dev/block/by-name/{part} of=/data/local/tmp/{part}.img 2>/dev/null"
                        self.adb.shell(dd_cmd.split(), serial=serial)
                        pull_res = self.adb.pull(f"/data/local/tmp/{part}.img", str(dest_file), serial=serial)
                        if getattr(pull_res, "success", False) and dest_file.exists() and dest_file.stat().st_size > 0:
                            self.log_emitted.emit("SUCCESS", f"Dumped partition via ADB root: {part}")
                            backed_up += 1
                        self.adb.shell(["rm", "-f", f"/data/local/tmp/{part}.img"], serial=serial)
                    except Exception as exc:
                        log.debug("ADB dump error for %s: %s", part, exc)
                        continue

        # Account for any valid image files in target_dir (e.g. pre-staged/mocked files)
        existing_imgs = list(target_dir.glob("*.img"))
        if len(existing_imgs) > backed_up:
            backed_up = len(existing_imgs)

        # Manifest generation
        manifest_file = target_dir / "manifest.txt"
        manifest_status = "SUCCESS" if backed_up > 0 else ("RESTRICTED_FASTBOOT" if fetch_restricted else "FAILED")
        manifest_content = (
            f"Device: {serial}\n"
            f"Timestamp: {timestamp}\n"
            f"Mode: {detected_mode}\n"
            f"Partitions Dumped: {backed_up}/{len(calibration_partitions)}\n"
            f"Status: {manifest_status}\n"
        )
        if backed_up == 0:
            manifest_content += (
                "Advisory: Fastboot partition readback is restricted by OEM bootloader.\n"
                "To secure EFS/NVRAM/Persist calibration, use TWRP recovery or root ADB.\n"
            )
        manifest_file.write_text(manifest_content, encoding="utf-8")

        manifest_lines = []
        for img in existing_imgs:
            if img.stat().st_size > 0:
                h = hashlib.sha256(img.read_bytes()).hexdigest()
                manifest_lines.append(f"{h}  {img.name}")
        if manifest_lines:
            (target_dir / "sha256sum.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

        if backed_up > 0:
            self.log_emitted.emit("INFO", f"Safety calibration backup complete: {backed_up} partition(s) secured.")
            if is_task_call:
                return True, f"Calibration backup completed to: {target_dir}"
            return target_dir
        else:
            self.log_emitted.emit("WARN", "Safety calibration pre-backup: 0 partitions dumped (bootloader restricted readback).")
            if is_task_call:
                return False, f"Calibration backup could not dump partitions: fastboot fetch restricted by bootloader. Use root ADB or recovery."
            return target_dir

    # -----------------------------------------------------------------------
    # 3. Bootloader Unlock & Lock Controllers
    # -----------------------------------------------------------------------

    def _perform_bootloader_op(self, task: FlashTask) -> tuple[bool, str]:
        """Synchronous wrapper for bootloader unlock or relock."""
        try:
            if task.operation == FlashOperationType.BOOTLOADER_UNLOCK:
                self._run_bootloader_unlock(task)
                return True, "Bootloader unlocked successfully"
            else:
                self._run_bootloader_lock(task)
                return True, "Bootloader locked successfully"
        except Exception as exc:
            return False, str(exc)

    def _run_bootloader_unlock(self, task: FlashTask) -> None:
        """Execute fastboot flashing unlock or fastboot oem unlock."""
        self.status_changed.emit("Executing bootloader unlock command...")

        if task.method == "oem" and task.unlock_token:
            self.log_emitted.emit("INFO", f"Sending OEM unlock code: {task.unlock_token[:4]}****")
            res = self.fastboot.oem_unlock(code=task.unlock_token, serial=task.serial)
        elif task.method == "oem":
            self.log_emitted.emit("INFO", "Executing: fastboot oem unlock")
            res = self.fastboot.oem_unlock(serial=task.serial)
        else:
            self.log_emitted.emit("INFO", "Executing: fastboot flashing unlock")
            res = self.fastboot.flashing_unlock(serial=task.serial)

        success = getattr(res, "success", bool(res))
        if not success:
            err = getattr(res, "stderr", None) or getattr(res, "output", None) or "Unlock command rejected by bootloader."
            raise RuntimeError(f"Unlock failed: {err}")

        self.log_emitted.emit("SUCCESS", "Bootloader unlock command accepted. Confirm on phone screen!")
        self.flash_finished.emit(True, "Unlock command executed successfully.")

    def _run_bootloader_lock(self, task: FlashTask) -> None:
        """
        Execute fastboot flashing lock or fastboot oem lock with Anti-Relock Verification Gate.

        Verifies pre-relock safety to prevent permanent AVB 2.0 bricking:
        1. Confirms fastboot connection and verifies not in fastbootd (userspace recovery).
        2. Verifies whether already locked.
        3. Prevents relock on prohibited hardware (e.g. Samsung fastboot prohibition).
        4. Enforces Anti-Relock verification gate (requires verified stock or confirmation word 'RELOCK').
        """
        self.status_changed.emit("Evaluating Anti-Relock safety gates...")
        self.log_emitted.emit("INFO", "Performing pre-relock safety checks...")

        # 1. Reject if in userspace fastboot (fastbootd)
        try:
            is_userspace = self.fastboot.get_var("is-userspace", serial=task.serial)
            if is_userspace and str(is_userspace).strip().lower() == "yes":
                raise RuntimeError(
                    "Relock rejected: Device is in fastbootd mode (userspace recovery). "
                    "Bootloader relocking MUST be executed in native Bootloader Fastboot mode. "
                    "Reboot to bootloader first ('fastboot reboot bootloader')."
                )
        except RuntimeError:
            raise
        except Exception as exc:
            log.debug("fastboot getvar is-userspace check ignored: %s", exc)

        # 2. Check if already locked
        try:
            is_unlocked = self.fastboot.get_var("unlocked", serial=task.serial)
            if is_unlocked and str(is_unlocked).strip().lower() in ("no", "false"):
                self.log_emitted.emit("INFO", "Device bootloader is already locked.")
                self.flash_finished.emit(True, "Bootloader is already locked.")
                return
        except Exception as exc:
            log.debug("fastboot getvar unlocked check ignored: %s", exc)

        # 3. Brand blacklist checks
        brand = (task.device_brand or "").strip().lower()
        if not brand:
            try:
                prod = (self.fastboot.get_var("product", serial=task.serial) or "").lower()
                if any(k in prod for k in ("samsung", "exynos")):
                    brand = "samsung"
            except Exception:
                pass

        if brand == "samsung":
            raise RuntimeError(
                "SAMSUNG ANTI-RELOCK PROHIBITION: Samsung devices do not support standard fastboot bootloader relocking. "
                "Attempting fastboot relock damages Knox warranty bit e-fuses and risks permanent bootloop."
            )

        # 4. Anti-Relock Gate: Pure stock verification
        if not task.force_relock and not task.allow_relock:
            if task.confirmation_word.strip() != "RELOCK":
                self.log_emitted.emit("ERROR", "Anti-Relock Gate: Confirmation word 'RELOCK' missing or stock unverified.")
                raise RuntimeError(
                    "ANTI-RELOCK SAFETY LOCKOUT: Relocking bootloader on a modified device (custom ROM, "
                    "Magisk/KernelSU/APatch rooted boot, or modified vbmeta) will permanently hard-brick the device (AVB red screen). "
                    "To proceed, ensure 100% stock firmware is flashed and provide explicit confirmation word 'RELOCK'."
                )

        # 5. Fastboot Lock Execution
        self.status_changed.emit("Executing bootloader lock command...")

        if task.method == "oem":
            self.log_emitted.emit("INFO", "Executing: fastboot oem lock")
            res = self.fastboot.oem_lock(serial=task.serial)
        else:
            self.log_emitted.emit("INFO", "Executing: fastboot flashing lock")
            res = self.fastboot.flashing_lock(serial=task.serial)

        success = getattr(res, "success", bool(res))
        if not success:
            err = getattr(res, "stderr", None) or getattr(res, "output", None) or "Lock command rejected by bootloader."
            raise RuntimeError(f"Relock failed: {err}")

        self.log_emitted.emit("SUCCESS", "Bootloader locked successfully. Follow instructions on device screen to confirm.")
        self.flash_finished.emit(True, "Bootloader locked successfully.")

    # -----------------------------------------------------------------------
    # 4. Partition Erase & Reboot Helpers
    # -----------------------------------------------------------------------

    def _run_erase_partition(self, task: FlashTask) -> None:
        """Erase specified partition via fastboot."""
        part = task.partition
        self.status_changed.emit(f"Erasing partition {part}...")
        self.log_emitted.emit("INFO", f"Executing: fastboot erase {part}")
        res = self.fastboot.erase(part, serial=task.serial)
        if not res.success:
            raise RuntimeError(f"Erase failed: {res.stderr or res.output}")
        self.log_emitted.emit("SUCCESS", f"Partition {part} erased.")
        self.flash_finished.emit(True, f"Partition {part} erased successfully.")

    def _run_reboot(self, task: FlashTask) -> None:
        """Reboot device to requested target (system, bootloader, recovery, edl)."""
        target = task.reboot_target.lower()
        self.status_changed.emit(f"Rebooting device to {target}...")
        self.log_emitted.emit("INFO", f"Reboot request: target={target}")

        if target == "bootloader":
            res = self.fastboot.reboot_bootloader(serial=task.serial)
        elif target == "recovery":
            res = self.fastboot.reboot_recovery(serial=task.serial)
        elif target == "fastboot":
            res = self.fastboot.reboot_fastboot(serial=task.serial)
        else:
            res = self.fastboot.reboot(serial=task.serial)

        if not res.success:
            # Try ADB reboot as fallback
            res_adb = self.adb.reboot(target=target if target != "system" else "", serial=task.serial)
            if not res_adb.success:
                raise RuntimeError(f"Reboot failed: {res.stderr or res_adb.stderr}")

        self.log_emitted.emit("SUCCESS", f"Device rebooted to {target}.")
        self.flash_finished.emit(True, f"Device rebooted to {target}.")
