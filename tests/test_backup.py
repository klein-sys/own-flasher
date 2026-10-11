"""
Unit tests — Backup and Restore Engine.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from flashdock.core.backup import BackupInfo, BackupItem, BackupManager
from flashdock.core.device import DeviceInfo
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult


class TestBackupModels:
    def test_backup_item_serialization(self):
        item = BackupItem(name="boot", filename="boot.img", size_bytes=1024, sha256="abcd1234")
        d = item.to_dict()
        assert d["name"] == "boot"
        assert d["size_bytes"] == 1024

        rebuilt = BackupItem.from_dict(d)
        assert rebuilt.name == "boot"
        assert rebuilt.sha256 == "abcd1234"

    def test_backup_info_serialization(self, tmp_path: Path):
        info = BackupInfo(
            backup_id="test_001",
            serial="SERIAL123",
            brand="google",
            model="Pixel 7",
            codename="panther",
            created_at="2026-10-11T12:00:00",
            backup_type="partitions",
            items=[BackupItem("boot", "boot.img", 2048, "hash1")],
        )
        saved_file = info.save(tmp_path)
        assert saved_file.is_file()

        reloaded = BackupInfo.from_dict(info.to_dict())
        assert reloaded.backup_id == "test_001"
        assert len(reloaded.items) == 1
        assert reloaded.items[0].name == "boot"


class TestBackupManager:
    @pytest.fixture
    def manager(self, tmp_path: Path):
        return BackupManager(root_dir=tmp_path)

    @pytest.fixture
    def device(self):
        return DeviceInfo(serial="DEVICE123", brand="google", model="Pixel 7", device="panther", mode="system")

    def test_create_partition_backup_dry_run(self, manager: BackupManager, device: DeviceInfo):
        mock_adb = MagicMock(spec=ADB)
        mock_fb = MagicMock(spec=Fastboot)

        info = manager.create_partition_backup(
            device=device,
            partitions=["boot", "recovery"],
            adb=mock_adb,
            fastboot=mock_fb,
            dry_run=True,
        )
        assert info.backup_id.startswith("parts_")
        assert len(info.items) == 2
        assert any(it.name == "boot" for it in info.items)
        assert any(it.name == "recovery" for it in info.items)

        # Check listed
        listed = manager.list_backups(serial=device.serial)
        assert len(listed) == 1
        assert listed[0].backup_id == info.backup_id

    def test_create_adb_backup_dry_run(self, manager: BackupManager, device: DeviceInfo):
        mock_adb = MagicMock(spec=ADB)
        info = manager.create_adb_backup(
            device=device,
            adb=mock_adb,
            dry_run=True,
        )
        assert info.backup_type == "adb_full"
        assert len(info.items) == 1
        assert info.items[0].name == "adb_backup"

    def test_restore_partition_rejects_simulated_backup(self, manager: BackupManager, device: DeviceInfo):
        mock_adb = MagicMock(spec=ADB)
        mock_fb = MagicMock(spec=Fastboot)
        mock_fb.flash.return_value = CommandResult(
            command=["fastboot", "flash", "boot", "boot.img"],
            return_code=0,
            stdout="Sending 'boot' (1024 KB)... OKAY\nWriting 'boot'... OKAY",
            stderr="",
            duration_ms=50,
        )

        info = manager.create_partition_backup(
            device=device,
            partitions=["boot"],
            adb=mock_adb,
            fastboot=mock_fb,
            dry_run=True,
        )

        ok, msg = manager.restore_partition(info, "boot", fastboot=mock_fb, serial=device.serial)
        assert ok is False
        assert "cannot be restored" in msg
        mock_fb.flash.assert_not_called()

    def test_restore_partition_missing_fails(self, manager: BackupManager, device: DeviceInfo):
        mock_fb = MagicMock(spec=Fastboot)
        info = BackupInfo(backup_id="fake", serial="s", brand="b", model="m", codename="c", created_at="", backup_type="p")
        ok, msg = manager.restore_partition(info, "nonexistent", fastboot=mock_fb)
        assert ok is False
        assert "not found" in msg

    def test_delete_backup(self, manager: BackupManager, device: DeviceInfo):
        mock_adb = MagicMock(spec=ADB)
        mock_fb = MagicMock(spec=Fastboot)
        info = manager.create_partition_backup(
            device=device,
            partitions=["boot"],
            adb=mock_adb,
            fastboot=mock_fb,
            dry_run=True,
        )
        assert len(manager.list_backups(serial=device.serial)) == 1

        deleted = manager.delete_backup(info.backup_id, serial=device.serial)
        assert deleted is True
        assert len(manager.list_backups(serial=device.serial)) == 0
