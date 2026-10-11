"""
Unit tests — Return to Stock & Safe Bootloader Relock Engine.
"""

from pathlib import Path
from unittest.mock import MagicMock
import zipfile
import pytest

from flashdock.core.device import DeviceInfo
from flashdock.core.return_stock import (
    RELOCK_CONFIRMATION_WORD,
    FlashStepResult,
    PartitionImage,
    RelockCheckResult,
    ReturnStockEngine,
    ReturnStockResult,
    StockFlashOptions,
    StockPackageInfo,
)
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult


class TestStockPackageParsing:
    def test_parse_nonexistent_path(self, tmp_path: Path):
        bad_path = tmp_path / "does_not_exist"
        pkg = ReturnStockEngine.parse_stock_package(bad_path)
        assert pkg.is_valid is False
        assert any("does not exist" in e for e in pkg.errors)

    def test_parse_directory_with_images(self, tmp_path: Path):
        # Create dummy partition image files
        (tmp_path / "boot.img").write_bytes(b"BOOT_DATA" * 100)
        (tmp_path / "vbmeta.img").write_bytes(b"VBMETA_DATA" * 50)
        (tmp_path / "super.img").write_bytes(b"SUPER_DATA" * 200)

        # Create android-info.txt
        info_content = (
            "require board=lynx\n"
            "require version-bootloader=lynx-1.0-123456\n"
        )
        (tmp_path / "android-info.txt").write_text(info_content, encoding="utf-8")

        pkg = ReturnStockEngine.parse_stock_package(tmp_path)
        assert pkg.is_valid is True
        assert pkg.target_codename == "lynx"
        assert pkg.build_id == "lynx-1.0-123456"
        assert "boot" in pkg.images
        assert "vbmeta" in pkg.images
        assert "super" in pkg.images
        assert pkg.has_super is True

    def test_parse_zip_package(self, tmp_path: Path):
        zip_file = tmp_path / "factory_image.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("android-info.txt", "require board=cheetah\n")
            zf.writestr("boot.img", b"BOOT_CONTENT")
            zf.writestr("init_boot.img", b"INIT_BOOT_CONTENT")
            zf.writestr("dtbo.img", b"DTBO_CONTENT")
            zf.writestr("system.img", b"SYSTEM_CONTENT")

        pkg = ReturnStockEngine.parse_stock_package(zip_file)
        assert pkg.is_valid is True
        assert pkg.target_codename == "cheetah"
        assert "boot" in pkg.images
        assert "init_boot" in pkg.images
        assert "system" in pkg.images
        assert pkg.partition_count == 4

    def test_parse_nested_pixel_zip(self, tmp_path: Path):
        # Simulate Pixel outer factory package with nested image-*.zip
        inner_buf = zipfile.ZipFile(tmp_path / "inner.zip", "w")
        inner_buf.writestr("boot.img", b"INNER_BOOT")
        inner_buf.writestr("vbmeta.img", b"INNER_VBMETA")
        inner_buf.close()

        outer_zip = tmp_path / "cheetah-factory.zip"
        with zipfile.ZipFile(outer_zip, "w") as zf:
            zf.writestr("android-info.txt", "require board=cheetah|panther\n")
            zf.write(tmp_path / "inner.zip", arcname="image-cheetah-123.zip")

        pkg = ReturnStockEngine.parse_stock_package(outer_zip)
        assert pkg.is_valid is True
        assert pkg.target_codename == "cheetah|panther"
        assert "boot" in pkg.images
        assert "vbmeta" in pkg.images

    def test_parse_empty_dir_invalid(self, tmp_path: Path):
        pkg = ReturnStockEngine.parse_stock_package(tmp_path)
        assert pkg.is_valid is False
        assert any("no boot, super, system" in e for e in pkg.errors)


class TestFlashOrdering:
    def test_canonical_flash_ordering(self):
        images = {
            "system": PartitionImage("system", Path("system.img")),
            "bootloader": PartitionImage("bootloader", Path("bootloader.img")),
            "vbmeta": PartitionImage("vbmeta", Path("vbmeta.img")),
            "boot": PartitionImage("boot", Path("boot.img")),
            "radio": PartitionImage("radio", Path("radio.img")),
            "custom_oem": PartitionImage("custom_oem", Path("custom_oem.img")),
        }
        order = ReturnStockEngine.get_flash_order(images)
        # bootloader and radio must precede boot and system
        assert order.index("bootloader") < order.index("boot")
        assert order.index("radio") < order.index("boot")
        assert order.index("boot") < order.index("vbmeta")
        assert order.index("vbmeta") < order.index("system")
        # unrecognized custom partition is placed at the end
        assert order[-1] == "custom_oem"


class TestCompatibilityAndSafety:
    def test_check_firmware_compatibility_matching(self):
        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            model="Pixel 7a",
            device="lynx",
            battery_level=85,
        )
        pkg = StockPackageInfo(
            source_path=Path("dummy"),
            is_valid=True,
            target_codename="lynx",
            images={"boot": PartitionImage("boot", Path("boot.img"))},
        )
        res = ReturnStockEngine.check_firmware_compatibility(dev, pkg)
        assert res.passed is True
        assert res.level == "ok"

    def test_check_firmware_compatibility_mismatch(self):
        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            model="Pixel 7 Pro",
            device="cheetah",
            battery_level=80,
        )
        pkg = StockPackageInfo(
            source_path=Path("dummy"),
            is_valid=True,
            target_codename="lynx",  # Wrong model!
            images={"boot": PartitionImage("boot", Path("boot.img"))},
        )
        res = ReturnStockEngine.check_firmware_compatibility(dev, pkg)
        assert res.passed is False
        assert res.level == "blocked"
        assert "CRITICAL CODENAME MISMATCH" in res.message

    def test_check_firmware_low_battery_blocked(self):
        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=25,  # Below 60% threshold
        )
        pkg = StockPackageInfo(
            source_path=Path("dummy"),
            is_valid=True,
            target_codename="lynx",
            images={"boot": PartitionImage("boot", Path("boot.img"))},
        )
        res = ReturnStockEngine.check_firmware_compatibility(dev, pkg)
        assert res.is_blocked is True
        assert "Battery level" in res.message


class TestRelockSafetyGate:
    def test_relock_blocked_if_no_flash_performed(self):
        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=90,
        )
        gate = ReturnStockEngine.check_relock_safety(device=dev, flash_result=None)
        assert gate.can_relock is False
        assert gate.risk_level == "prohibited"
        assert any("not been flashed in this session" in r for r in gate.reasons)

    def test_relock_blocked_if_flash_had_errors(self):
        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=90,
        )
        failed_result = ReturnStockResult(
            success=False,
            steps=[
                FlashStepResult(partition="boot", status="success"),
                FlashStepResult(partition="system", status="failed", message="Write error"),
            ],
            error_message="System write failed",
        )
        gate = ReturnStockEngine.check_relock_safety(device=dev, flash_result=failed_result)
        assert gate.can_relock is False
        assert any("failed" in r.lower() for r in gate.reasons)

    def test_relock_blocked_on_xiaomi_cross_region(self):
        dev = DeviceInfo(
            serial="MI123",
            mode="bootloader",
            brand="Xiaomi",
            device="fuxi",
            battery_level=85,
        )
        flash_res = ReturnStockResult(
            success=True,
            steps=[FlashStepResult(partition="boot", status="success")],
        )
        gate = ReturnStockEngine.check_relock_safety(
            device=dev, flash_result=flash_res, cross_region_risk=True
        )
        assert gate.can_relock is False
        assert any("XIAOMI CROSS-REGION" in r for r in gate.reasons)

    def test_relock_blocked_on_samsung(self):
        dev = DeviceInfo(
            serial="SAM123",
            mode="bootloader",
            brand="Samsung",
            device="dm3q",
            battery_level=85,
        )
        flash_res = ReturnStockResult(
            success=True,
            steps=[FlashStepResult(partition="boot", status="success")],
        )
        gate = ReturnStockEngine.check_relock_safety(device=dev, flash_result=flash_res)
        assert gate.can_relock is False
        assert any("SAMSUNG PROHIBITION" in r for r in gate.reasons)

    def test_relock_allowed_after_clean_pixel_flash(self):
        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=90,
        )
        flash_res = ReturnStockResult(
            success=True,
            steps=[
                FlashStepResult(partition="boot", status="success"),
                FlashStepResult(partition="vbmeta", status="success"),
            ],
        )
        gate = ReturnStockEngine.check_relock_safety(device=dev, flash_result=flash_res)
        assert gate.can_relock is True
        assert gate.recommended_command == "fastboot flashing lock"


class TestFlashingAndRelockExecution:
    def test_live_flash_stock_extracts_zip_image_before_fastboot(self, tmp_path: Path):
        archive = tmp_path / "factory.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("boot.img", b"FACTORY_BOOT")
        package = ReturnStockEngine.parse_stock_package(archive)
        mock_fb = MagicMock(spec=Fastboot)

        def verify_materialized(**kwargs):
            image = Path(kwargs["image_path"])
            assert image.is_file()
            assert image.read_bytes() == b"FACTORY_BOOT"
            return CommandResult(["fastboot", "flash"], 0, "OKAY", "", 10)

        mock_fb.flash.side_effect = verify_materialized
        engine = ReturnStockEngine(fastboot=mock_fb)
        dev = DeviceInfo(serial="PIXEL123", mode="bootloader", brand="Google", device="lynx", battery_level=85)
        package.target_codename = "lynx"
        result = engine.flash_stock(dev, package, StockFlashOptions(wipe_data=False))
        assert result.success is True
        mock_fb.flash.assert_called_once()

    def test_dry_run_flash_stock(self):
        mock_fb = MagicMock(spec=Fastboot)
        engine = ReturnStockEngine(fastboot=mock_fb)

        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=85,
        )
        pkg = StockPackageInfo(
            source_path=Path("dummy"),
            is_valid=True,
            target_codename="lynx",
            images={
                "boot": PartitionImage("boot", Path("boot.img")),
                "vbmeta": PartitionImage("vbmeta", Path("vbmeta.img")),
            },
        )

        options = StockFlashOptions(dry_run=True, wipe_data=True)
        res = engine.flash_stock(dev, pkg, options=options)

        assert res.success is True
        assert res.wiped_data is True
        assert res.ready_for_relock is True
        # Fastboot was NOT invoked because dry_run was active
        mock_fb.flash.assert_not_called()

    def test_live_flash_stock_success(self, tmp_path: Path):
        mock_fb = MagicMock(spec=Fastboot)
        mock_fb.flash.return_value = CommandResult(
            command=["fastboot", "flash"], return_code=0, stdout="OKAY", stderr="", duration_ms=100
        )
        mock_fb._run.return_value = CommandResult(
            command=["fastboot", "-w"], return_code=0, stdout="wiped", stderr="", duration_ms=100
        )
        engine = ReturnStockEngine(fastboot=mock_fb)

        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=85,
        )
        boot_image = tmp_path / "boot.img"
        boot_image.write_bytes(b"BOOT")
        pkg = StockPackageInfo(
            source_path=Path("dummy"),
            is_valid=True,
            target_codename="lynx",
            images={
                "boot": PartitionImage("boot", boot_image),
            },
        )

        options = StockFlashOptions(dry_run=False, wipe_data=True)
        res = engine.flash_stock(dev, pkg, options=options)

        assert res.success is True
        assert mock_fb.flash.call_count == 1
        assert res.wiped_data is True

    def test_flash_stock_user_cancel(self):
        mock_fb = MagicMock(spec=Fastboot)
        engine = ReturnStockEngine(fastboot=mock_fb)

        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=85,
        )
        pkg = StockPackageInfo(
            source_path=Path("dummy"),
            is_valid=True,
            target_codename="lynx",
            images={"boot": PartitionImage("boot", Path("boot.img"))},
        )

        res = engine.flash_stock(dev, pkg, cancel_requested=lambda: True)
        assert res.success is False
        assert "cancelled by user" in res.error_message

    def test_execute_relock_dry_run(self):
        mock_fb = MagicMock(spec=Fastboot)
        engine = ReturnStockEngine(fastboot=mock_fb)
        dev = DeviceInfo(serial="PIXEL123", mode="bootloader")

        res = engine.execute_relock(dev, command="fastboot flashing lock", dry_run=True)
        assert res.success is True
        assert "[Dry Run]" in res.stdout
        mock_fb.flashing_lock.assert_not_called()

    def test_execute_relock_live(self):
        mock_fb = MagicMock(spec=Fastboot)
        mock_fb.flashing_lock.return_value = CommandResult(
            command=["fastboot", "flashing", "lock"], return_code=0, stdout="OKAY", stderr="", duration_ms=50
        )
        engine = ReturnStockEngine(fastboot=mock_fb)
        dev = DeviceInfo(serial="PIXEL123", mode="bootloader")

        res = engine.execute_relock(dev, command="fastboot flashing lock", dry_run=False)
        assert res.success is True
        mock_fb.flashing_lock.assert_called_once_with(serial="PIXEL123")
