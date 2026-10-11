"""
Unit tests — Local Repository Manager & StoredItem Compatibility.
"""

from pathlib import Path
import pytest

from flashdock.core.device import DeviceInfo
from flashdock.core.repository import RepositoryManager, StoredItem


class TestStoredItemCompatibility:
    def test_unfiltered_when_no_device(self):
        item = StoredItem(
            id="gsi_1",
            name="AOSP 14 GSI",
            category="gsi",
            file_path=Path("dummy.img"),
            size_bytes=1000,
            target_arch="arm64",
            target_slot="a/b",
        )
        compat, msg = item.is_compatible_with(None)
        assert compat is True

    def test_codename_mismatch(self):
        item = StoredItem(
            id="rom_1",
            name="PixelOS Lynx",
            category="rom",
            file_path=Path("dummy.zip"),
            size_bytes=1000,
            target_codename="lynx",
        )
        dev = DeviceInfo(serial="CH123", mode="system", device="cheetah")
        compat, msg = item.is_compatible_with(dev)
        assert compat is False
        assert "Requires device 'lynx'" in msg

    def test_arch_compatibility(self):
        item_arm64 = StoredItem(
            id="gsi_64",
            name="GSI ARM64",
            category="gsi",
            file_path=Path("dummy.img"),
            size_bytes=1000,
            target_arch="arm64",
        )
        dev_arm64 = DeviceInfo(serial="D1", mode="system", cpu_abi="arm64-v8a")
        dev_arm32 = DeviceInfo(serial="D2", mode="system", cpu_abi="armeabi-v7a")

        compat64, _ = item_arm64.is_compatible_with(dev_arm64)
        compat32, _ = item_arm64.is_compatible_with(dev_arm32)

        assert compat64 is True
        assert compat32 is False

    def test_dynamic_partitions_requirement(self):
        item = StoredItem(
            id="super_rom",
            name="Super ROM",
            category="rom",
            file_path=Path("dummy.zip"),
            size_bytes=1000,
            requires_dynamic=True,
        )
        dev_legacy = DeviceInfo(serial="D1", mode="system", has_dynamic_partitions=False)
        dev_dynamic = DeviceInfo(serial="D2", mode="system", has_dynamic_partitions=True)

        assert item.is_compatible_with(dev_legacy)[0] is False
        assert item.is_compatible_with(dev_dynamic)[0] is True


class TestRepositoryManagerScan:
    def test_repository_scan_creates_directories(self):
        repo = RepositoryManager()
        items = repo.scan_all()
        assert isinstance(items, list)
