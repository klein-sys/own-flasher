"""
FlashDock — Backup and Restore Engine.

Handles:
* Automatic partition dumps (boot, recovery, vbmeta, EFS, NVRAM, modem).
* Full ADB backups (.ab archive format).
* Checksum generation and integrity verification for all backup files.
* Backup catalog indexing and metadata management under `data/backups/`.
* Fastboot partition restoration with pre-restore hash checking.

Spec references: Section 10.8, Section 16.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

from flashdock.constants import BACKUPS_DIR
from flashdock.core.device import DeviceInfo
from flashdock.core.safety import SafetyEngine
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class BackupItem:
    """One backed up partition or file."""
    name: str  # e.g. "boot", "recovery", "vbmeta", "adb_backup"
    filename: str  # e.g. "boot.img", "backup.ab"
    size_bytes: int = 0
    sha256: str = ""
    is_restorable: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupItem:
        return cls(
            name=data.get("name", ""),
            filename=data.get("filename", ""),
            size_bytes=data.get("size_bytes", 0),
            sha256=data.get("sha256", ""),
            is_restorable=data.get("is_restorable", True),
        )


@dataclass
class BackupInfo:
    """Metadata record for a backup set."""
    backup_id: str
    serial: str
    brand: str
    model: str
    codename: str
    created_at: str
    backup_type: str  # "partitions", "adb_full", "efs_only"
    items: list[BackupItem] = field(default_factory=list)
    notes: str = ""
    backup_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "backup_id": self.backup_id,
            "serial": self.serial,
            "brand": self.brand,
            "model": self.model,
            "codename": self.codename,
            "created_at": self.created_at,
            "backup_type": self.backup_type,
            "items": [item.to_dict() for item in self.items],
            "notes": self.notes,
            "backup_path": self.backup_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BackupInfo:
        items = [BackupItem.from_dict(it) for it in data.get("items", [])]
        return cls(
            backup_id=data.get("backup_id", ""),
            serial=data.get("serial", ""),
            brand=data.get("brand", ""),
            model=data.get("model", ""),
            codename=data.get("codename", ""),
            created_at=data.get("created_at", ""),
            backup_type=data.get("backup_type", "partitions"),
            items=items,
            notes=data.get("notes", ""),
            backup_path=data.get("backup_path", ""),
        )

    def save(self, folder: Path) -> Path:
        """Write backup_info.json inside the backup directory."""
        self.backup_path = str(folder)
        meta_file = folder / "backup_info.json"
        meta_file.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return meta_file


# ---------------------------------------------------------------------------
# Backup Manager
# ---------------------------------------------------------------------------

class BackupManager:
    """Manages partition dumps and ADB backups on disk."""

    def __init__(self, root_dir: Optional[Path] = None) -> None:
        self.root_dir = root_dir or BACKUPS_DIR
        self.root_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------------
    # Listing and discovery
    # -----------------------------------------------------------------------

    def list_backups(self, serial: str = "") -> list[BackupInfo]:
        """
        List all recorded backups, optionally filtered by device serial.
        Sorted newest first.
        """
        backups: list[BackupInfo] = []
        if not self.root_dir.is_dir():
            return backups

        search_dirs: list[Path] = []
        if serial:
            dev_dir = self.root_dir / serial
            if dev_dir.is_dir():
                search_dirs.append(dev_dir)
        else:
            search_dirs = [d for d in self.root_dir.iterdir() if d.is_dir()]

        for dev_dir in search_dirs:
            for b_dir in dev_dir.iterdir():
                if not b_dir.is_dir():
                    continue
                meta_file = b_dir / "backup_info.json"
                if meta_file.is_file():
                    try:
                        data = json.loads(meta_file.read_text(encoding="utf-8"))
                        info = BackupInfo.from_dict(data)
                        info.backup_path = str(b_dir)
                        backups.append(info)
                    except Exception as e:
                        log.warning("Could not read backup meta in %s: %s", b_dir, e)

        backups.sort(key=lambda b: b.created_at, reverse=True)
        return backups

    def get_backup(self, backup_id: str, serial: str = "") -> Optional[BackupInfo]:
        """Fetch a specific backup by its ID."""
        for b in self.list_backups(serial=serial):
            if b.backup_id == backup_id:
                return b
        return None

    def delete_backup(self, backup_id: str, serial: str = "") -> bool:
        """Permanently delete a backup directory."""
        target = self.get_backup(backup_id, serial=serial)
        if not target or not target.backup_path:
            return False
        p = Path(target.backup_path)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
            log.info("Deleted backup %s at %s", backup_id, p)
            return True
        return False

    # -----------------------------------------------------------------------
    # Partition backup creation
    # -----------------------------------------------------------------------

    def create_partition_backup(
        self,
        device: DeviceInfo,
        partitions: list[str],
        adb: ADB,
        fastboot: Fastboot,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str, int, int], None]] = None,
    ) -> BackupInfo:
        """
        Dump critical partitions from device to local storage.
        """
        serial = device.serial or "unknown_device"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"parts_{timestamp}"
        out_dir = self.root_dir / serial / backup_id
        out_dir.mkdir(parents=True, exist_ok=True)

        items: list[BackupItem] = []
        total = len(partitions)

        log.info("Starting partition backup for %s: %s", serial, partitions)

        for i, part in enumerate(partitions, start=1):
            if on_progress:
                on_progress(part, i, total)

            img_filename = f"{part}.img"
            img_path = out_dir / img_filename

            if dry_run:
                # In dry run mode, generate mock partition file
                img_path.write_bytes(f"DRY RUN DUMP OF {part}".encode("utf-8"))
                size = img_path.stat().st_size
                sha = SafetyEngine.calculate_hash(img_path)
                items.append(BackupItem(
                    name=part,
                    filename=img_filename,
                    size_bytes=size,
                    sha256=sha,
                    is_restorable=False,
                ))
                continue

            # Real backup flow
            dump_success = False

            # If device is rooted in system mode or running in custom recovery (TWRP/OrangeFox): use dd
            if device.mode in ("system", "recovery") and adb.available:
                remote_tmp = f"/data/local/tmp/{img_filename}"
                by_name = f"/dev/block/by-name/{part}"
                by_bootdevice = f"/dev/block/bootdevice/by-name/{part}"

                if device.mode == "recovery":
                    dd_cmd = f"dd if={by_name} of={remote_tmp} 2>/dev/null || dd if={by_bootdevice} of={remote_tmp}"
                    clean_cmd = f"rm -f {remote_tmp}"
                else:
                    dd_cmd = f"su -c 'dd if={by_name} of={remote_tmp}' 2>/dev/null || su -c 'dd if={by_bootdevice} of={remote_tmp}'"
                    clean_cmd = f"su -c 'rm -f {remote_tmp}'"

                res = adb.shell(dd_cmd, serial=serial)

                # Pull file
                pull_res = adb.pull(remote_tmp, str(img_path), serial=serial)
                if pull_res.success and img_path.is_file() and img_path.stat().st_size > 0:
                    dump_success = True
                    # Clean up temporary remote file
                    adb.shell(clean_cmd, serial=serial)

            # Do not create a fake .img when a dump cannot be obtained.  Such a
            # file must never be offered to fastboot as a restorable partition.
            if not dump_success:
                log.warning("Could not dump partition '%s' without root or fastboot pull support.", part)
                items.append(BackupItem(
                    name=part,
                    filename=img_filename,
                    is_restorable=False,
                ))
                continue

            size = img_path.stat().st_size
            sha = SafetyEngine.calculate_hash(img_path)
            items.append(BackupItem(
                name=part,
                filename=img_filename,
                size_bytes=size,
                sha256=sha,
            ))

        info = BackupInfo(
            backup_id=backup_id,
            serial=serial,
            brand=device.brand,
            model=device.model,
            codename=device.device,
            created_at=datetime.now().isoformat(),
            backup_type="partitions",
            items=items,
            notes=f"Auto partition backup for {device.summary_line}",
        )
        info.save(out_dir)
        log.info("Partition backup %s completed with %d items.", backup_id, len(items))
        return info

    # -----------------------------------------------------------------------
    # ADB full backup
    # -----------------------------------------------------------------------

    def create_adb_backup(
        self,
        device: DeviceInfo,
        adb: ADB,
        include_apk: bool = False,
        include_shared: bool = False,
        dry_run: bool = False,
        on_progress: Optional[Callable[[str], None]] = None,
    ) -> BackupInfo:
        """
        Run ADB backup to create a device app/data archive (.ab).
        """
        serial = device.serial or "unknown_device"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_id = f"adb_{timestamp}"
        out_dir = self.root_dir / serial / backup_id
        out_dir.mkdir(parents=True, exist_ok=True)

        ab_file = out_dir / "backup.ab"
        if on_progress:
            on_progress("Creating ADB backup. Please unlock phone and approve the backup prompt on your screen...")

        if dry_run:
            ab_file.write_bytes(b"DRY RUN ADB BACKUP ARCHIVE")
            size = ab_file.stat().st_size
            sha = SafetyEngine.calculate_hash(ab_file)
        else:
            adb.backup(
                destination_path=str(ab_file),
                include_apk=include_apk,
                include_shared=include_shared,
                serial=serial,
            )
            size = ab_file.stat().st_size if ab_file.is_file() else 0
            sha = SafetyEngine.calculate_hash(ab_file) if ab_file.is_file() else ""

        items = [BackupItem(
            name="adb_backup",
            filename="backup.ab",
            size_bytes=size,
            sha256=sha,
        )]

        info = BackupInfo(
            backup_id=backup_id,
            serial=serial,
            brand=device.brand,
            model=device.model,
            codename=device.device,
            created_at=datetime.now().isoformat(),
            backup_type="adb_full",
            items=items,
            notes="ADB system and application data backup",
        )
        info.save(out_dir)
        return info

    # -----------------------------------------------------------------------
    # Partition restoration
    # -----------------------------------------------------------------------

    def restore_partition(
        self,
        backup_info: BackupInfo,
        item_name: str,
        fastboot: Fastboot,
        serial: str = "",
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """
        Restore a single partition from a verified backup set via fastboot.
        """
        item = next((it for it in backup_info.items if it.name == item_name), None)
        if not item:
            return False, f"Partition '{item_name}' not found in backup {backup_info.backup_id}."
        if not item.is_restorable:
            return False, (
                f"Partition '{item_name}' was not captured as a real image and cannot be restored. "
                "Create a rooted or recovery-mode backup before flashing this partition."
            )

        backup_dir = Path(backup_info.backup_path)
        img_file = backup_dir / item.filename

        if not img_file.is_file():
            return False, f"Image file not found on disk: {img_file.name}"

        # 1. Verify SHA-256 integrity before flashing
        if item.sha256:
            check_res = SafetyEngine.verify_checksum(img_file, item.sha256)
            if not check_res.passed:
                return False, f"Integrity check failed: {check_res.message}"

        # 2. Flash via fastboot
        dev_serial = serial or backup_info.serial
        res = fastboot.flash(item_name, str(img_file), serial=dev_serial)
        if res.success:
            return True, f"Successfully restored '{item_name}' from backup {backup_info.backup_id}."
        else:
            return False, f"Fastboot flash failed: {res.stderr}"
