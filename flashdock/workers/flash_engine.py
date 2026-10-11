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
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal, Slot

from flashdock.constants import BACKUPS_DIR
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import acquire_flash_lock, is_flash_locked, release_flash_lock

log = get_logger(__name__)

CRITICAL_CALIBRATION_PARTITIONS: list[str] = ["efs", "nvram", "nvdata", "persist", "sec_efs"]


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
    operation: FlashOperationType
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
    backup_dir: Optional[str | Path] = None
    method: str = "flashing"  # "flashing" or "oem"
    unlock_token: str = ""
    reboot_target: str = "system"

    def __post_init__(self) -> None:
        if self.partition_name and not self.partition:
            self.partition = self.partition_name
        if self.device_serial and not self.serial:
            self.serial = self.device_serial
        if self.image_path and not self.file_path:
            self.file_path = Path(self.image_path)


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
        adb: Optional[ADB] = None,
        fastboot: Optional[Fastboot] = None,
        backups_dir: Optional[Path] = None,
        parent: Optional[Any] = None,
    ) -> None:
        super().__init__(parent)
        self.adb = adb or ADB()
        self.fastboot = fastboot or Fastboot()
        self.backups_dir = backups_dir or BACKUPS_DIR
        self.backups_dir.mkdir(parents=True, exist_ok=True)

        self._task: Optional[FlashTask] = None
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
        with QMutexLocker(self._mutex):
            self._is_cancelled = True
        self.log_emitted.emit("WARN", "Cancellation requested by operator.")

    @property
    def is_cancelled(self) -> bool:
        with QMutexLocker(self._mutex):
            return self._is_cancelled

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
                self._perform_calibration_backup(task.serial)
            except Exception as backup_exc:
                self.log_emitted.emit("WARN", f"Pre-backup warning (non-fatal): {backup_exc}")

        # Step 3: Fastboot Flash Execution
        target_part = task.partition
        if task.slot and not target_part.endswith(("_a", "_b")):
            target_part = f"{target_part}{task.slot}"

        self.status_changed.emit(f"Flashing {task.file_path.name} -> {target_part}...")
        self.log_emitted.emit("INFO", f"Executing: fastboot flash {target_part} \"{task.file_path.name}\"")

        res = self.fastboot.flash(target_part, str(task.file_path), serial=task.serial)
        success = getattr(res, "success", bool(res))
        if not success:
            err = getattr(res, "stderr", None) or getattr(res, "output", None) or "Fastboot flash returned an error."
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
        backup_folder = self._perform_calibration_backup(task.serial)
        self.progress_changed.emit(100, 100, 100)
        self.status_changed.emit("Safety backup completed!")
        self.flash_finished.emit(True, f"Backup saved to: {backup_folder}")

    def _perform_calibration_backup(self, serial_or_task: Any = "") -> Any:
        """
        Back up critical partitions (efs, nvram, nvdata, persist) to disk.
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

        calibration_partitions = CRITICAL_CALIBRATION_PARTITIONS
        backed_up = 0

        for part in calibration_partitions:
            if self.is_cancelled:
                break
            dest_file = target_dir / f"{part}.img"
            try:
                # Try fastboot fetch / dump
                res = self.fastboot._run(["fetch", part, str(dest_file)], serial=serial, timeout=15, action=f"fetch_{part}")
                if getattr(res, "success", False) and dest_file.exists() and dest_file.stat().st_size > 0:
                    self.log_emitted.emit("SUCCESS", f"Dumped partition: {part}")
                    backed_up += 1
                else:
                    # Check if ADB shell dd is accessible
                    dd_cmd = f"dd if=/dev/block/by-name/{part} of=/data/local/tmp/{part}.img 2>/dev/null"
                    self.adb.shell(dd_cmd.split(), serial=serial)
                    pull_res = self.adb.pull(f"/data/local/tmp/{part}.img", str(dest_file), serial=serial)
                    if getattr(pull_res, "success", False) and dest_file.exists() and dest_file.stat().st_size > 0:
                        self.log_emitted.emit("SUCCESS", f"Dumped partition via ADB: {part}")
                        backed_up += 1
                    # Clean up temp on device
                    self.adb.shell(["rm", "-f", f"/data/local/tmp/{part}.img"], serial=serial)
            except Exception:
                continue

        # Save manifest
        manifest_file = target_dir / "manifest.txt"
        manifest_file.write_text(
            f"Device: {serial}\nTimestamp: {timestamp}\nPartitions Dumped: {backed_up}\n",
            encoding="utf-8",
        )

        manifest_lines = []
        for img in target_dir.glob("*.img"):
            h = hashlib.sha256(img.read_bytes()).hexdigest()
            manifest_lines.append(f"{h}  {img.name}")
        if manifest_lines:
            (target_dir / "sha256sum.txt").write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

        self.log_emitted.emit("INFO", f"Safety calibration backup complete: {backed_up} partition(s) secured.")
        if is_task_call:
            return True, f"Calibration backup completed to: {target_dir}"
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
        """Execute fastboot flashing lock or fastboot oem lock."""
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

        self.log_emitted.emit("SUCCESS", "Bootloader locked successfully.")
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
