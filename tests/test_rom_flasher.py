"""
Unit tests — Custom ROM, GSI & Recovery Flashing Engine (RomFlasher).
"""

from pathlib import Path
from unittest.mock import MagicMock
import zipfile
import pytest

from flashdock.core.device import DeviceInfo
from flashdock.core.rom_flasher import RomFlasher, RomPackageInfo, FlashPartitionItem
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult


@pytest.fixture
def mock_fb():
    fb = MagicMock(spec=Fastboot)
    fb.flash.return_value = CommandResult(["fastboot", "flash"], 0, "OKAY", "", 10)
    fb.erase.return_value = CommandResult(["fastboot", "erase"], 0, "OKAY", "", 10)
    fb.wipe.return_value = CommandResult(["fastboot", "-w"], 0, "OKAY", "", 10)
    fb.boot.return_value = CommandResult(["fastboot", "boot"], 0, "OKAY", "", 10)
    fb.reboot_fastboot.return_value = CommandResult(["fastboot", "reboot", "fastboot"], 0, "OKAY", "", 10)
    fb.flash_vbmeta_disabled.return_value = CommandResult(["fastboot", "flash", "vbmeta"], 0, "OKAY", "", 10)
    return fb


class TestRomFlasherParsing:
    def test_parse_custom_rom_dir(self, tmp_path: Path):
        rom_dir = tmp_path / "MyLineageOS_ROM"
        rom_dir.mkdir()
        (rom_dir / "boot.img").write_bytes(b"BOOT_IMG_DATA")
        (rom_dir / "recovery.img").write_bytes(b"RECOVERY_IMG_DATA")
        (rom_dir / "super.img").write_bytes(b"SUPER_IMG_DATA")
        (rom_dir / "flash_all.bat").write_text("fastboot flash boot boot.img")
        (rom_dir / "android-info.txt").write_text("require product=cheetah\n")

        ok, info, msg = RomFlasher.parse_custom_rom(rom_dir)
        assert ok is True
        assert info is not None
        assert info.name == "MyLineageOS_ROM"
        assert info.has_flash_script is True
        assert info.script_name == "flash_all.bat"
        assert info.target_codename == "cheetah"
        assert len(info.detected_partitions) == 3
        # Check canonical sorting: boot before recovery before super
        part_names = [p.partition_name for p in info.detected_partitions]
        assert part_names == ["boot", "recovery", "super"]

    def test_parse_custom_rom_zip(self, tmp_path: Path):
        zip_path = tmp_path / "FastbootROM.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("boot.img", b"BOOT_BYTES")
            zf.writestr("dtbo.img", b"DTBO_BYTES")
            zf.writestr("android-info.txt", "require product=lynx\n")

        ok, info, msg = RomFlasher.parse_custom_rom(zip_path)
        assert ok is True
        assert info is not None
        assert info.package_type == "fastboot_zip"
        assert info.target_codename == "lynx"
        assert len(info.detected_partitions) == 2

    def test_parse_sparse_chunks(self, tmp_path: Path):
        rom_dir = tmp_path / "MotoROM"
        rom_dir.mkdir()
        (rom_dir / "system.img_sparsechunk.0").write_bytes(b"CHUNK0")
        (rom_dir / "system.img_sparsechunk.1").write_bytes(b"CHUNK1")

        ok, info, msg = RomFlasher.parse_custom_rom(rom_dir)
        assert ok is True
        assert len(info.detected_partitions) == 2
        assert all(p.partition_name == "system" for p in info.detected_partitions)

    def test_parse_gsi_variants(self, tmp_path: Path):
        # arm64 A/B with GApps and Superuser
        gsi1 = tmp_path / "lineage-21.0-arm64_bgS.img"
        gsi1.write_bytes(b"GSI1_CONTENT")
        ok, info1, _ = RomFlasher.parse_gsi(gsi1)
        assert ok is True
        assert info1.arch == "arm64"
        assert info1.slot_scheme == "a/b"
        assert "GApps" in info1.gapps_variant

        # a64 A-only vanilla
        gsi2 = tmp_path / "system-a64-a-vanilla.img"
        gsi2.write_bytes(b"GSI2_CONTENT")
        ok, info2, _ = RomFlasher.parse_gsi(gsi2)
        assert ok is True
        assert info2.arch == "arm"
        assert info2.slot_scheme == "a_only"
        assert "Vanilla" in info2.gapps_variant

    def test_determine_recovery_target(self):
        # Dynamic super partition device -> recovery in boot
        dyn_dev = DeviceInfo(android_version="13", has_dynamic_partitions=True, slot_scheme="a/b")
        target, live, reason = RomFlasher.determine_recovery_target(dyn_dev)
        assert target == "boot"
        assert live is True

        # Legacy device with dedicated recovery
        legacy_dev = DeviceInfo(android_version="8", has_dynamic_partitions=False, slot_scheme="a_only")
        target, live, reason = RomFlasher.determine_recovery_target(legacy_dev)
        assert target == "recovery"
        assert live is True


class TestRomFlasherExecution:
    def test_flash_custom_rom_dry_run(self, mock_fb, tmp_path: Path):
        flasher = RomFlasher(mock_fb)
        pkg = RomPackageInfo(
            name="TestROM",
            package_type="fastboot_dir",
            path=tmp_path,
            detected_partitions=[
                FlashPartitionItem("boot", tmp_path / "boot.img", 1024),
                FlashPartitionItem("system", tmp_path / "system.img", 2048),
            ],
        )
        ok, msg = flasher.flash_custom_rom(
            package_info=pkg,
            slot_target="both",
            wipe_userdata=True,
            dry_run=True,
        )
        assert ok is True
        assert "Successfully flashed" in msg
        mock_fb.flash.assert_not_called()  # Dry run doesn't call real hardware flash

    def test_flash_custom_rom_live(self, mock_fb, tmp_path: Path):
        flasher = RomFlasher(mock_fb)
        boot_img = tmp_path / "boot.img"
        boot_img.write_bytes(b"DATA")
        pkg = RomPackageInfo(
            name="TestROM",
            package_type="fastboot_dir",
            path=tmp_path,
            detected_partitions=[
                FlashPartitionItem("boot", boot_img, 1024),
            ],
        )
        ok, msg = flasher.flash_custom_rom(
            package_info=pkg,
            slot_target="a",
            wipe_userdata=True,
            dry_run=False,
            serial="SERIAL1",
        )
        assert ok is True
        mock_fb.flash.assert_called_once()
        mock_fb.wipe.assert_called_once()

    def test_flash_custom_rom_zip_extracts_images_before_fastboot(self, mock_fb, tmp_path: Path):
        archive = tmp_path / "rom.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("boot.img", b"BOOT")
        ok, package, _ = RomFlasher.parse_custom_rom(archive)
        assert ok and package

        def verify_materialized(**kwargs):
            image = Path(kwargs["image_path"])
            assert image.is_file()
            assert image.read_bytes() == b"BOOT"
            return CommandResult(["fastboot", "flash"], 0, "OKAY", "", 10)

        mock_fb.flash.side_effect = verify_materialized
        ok, _ = RomFlasher(mock_fb).flash_custom_rom(package, serial="SERIAL1")
        assert ok is True
        mock_fb.flash.assert_called_once()

    def test_flash_gsi_requires_real_vbmeta_when_avb_is_disabled(self, mock_fb, tmp_path: Path):
        gsi_file = tmp_path / "gsi.img"
        gsi_file.write_bytes(b"GSI_RAW")
        ok, message = RomFlasher(mock_fb).flash_gsi(gsi_file, disable_avb=True)
        assert ok is False
        assert "vbmeta.img" in message
        mock_fb.flash.assert_not_called()

    def test_flash_gsi_dry_run(self, mock_fb, tmp_path: Path):
        flasher = RomFlasher(mock_fb)
        gsi_file = tmp_path / "gsi.img"
        gsi_file.write_bytes(b"GSI_RAW")

        ok, msg = flasher.flash_gsi(
            gsi_image_path=gsi_file,
            disable_avb=True,
            wipe_userdata=True,
            is_dynamic_super=True,
            dry_run=True,
        )
        assert ok is True
        assert "Successfully flashed GSI" in msg

    def test_flash_recovery_live_boot(self, mock_fb, tmp_path: Path):
        flasher = RomFlasher(mock_fb)
        rec_file = tmp_path / "twrp.img"
        rec_file.write_bytes(b"TWRP_RAW")

        ok, msg = flasher.flash_recovery(
            recovery_image_path=rec_file,
            target_partition="recovery",
            live_boot_only=True,
            dry_run=False,
            serial="S1",
        )
        assert ok is True
        mock_fb.boot.assert_called_once_with(image_path=str(rec_file), serial="S1")

    def test_switch_to_fastbootd(self, mock_fb):
        flasher = RomFlasher(mock_fb)
        res = flasher.switch_to_fastbootd(serial="S1")
        assert res.success is True
        mock_fb.reboot_fastboot.assert_called_once_with(serial="S1")
