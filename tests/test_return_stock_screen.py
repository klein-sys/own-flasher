"""
Unit tests — ReturnStockScreen UI and Relock dialog.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.return_stock import (
    FlashStepResult,
    PartitionImage,
    ReturnStockResult,
    StockPackageInfo,
)
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.screens.return_stock_screen import (
    RelockConfirmationDialog,
    ReturnStockScreen,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_deps():
    device_mgr = MagicMock(spec=DeviceManager)
    device_mgr.device = None
    adb = MagicMock(spec=ADB)
    fastboot = MagicMock(spec=Fastboot)
    return device_mgr, adb, fastboot


class TestRelockConfirmationDialog:
    def test_relock_dialog_typed_validation(self, qapp):
        dev = DeviceInfo(serial="PIXEL123", mode="bootloader", device="lynx")
        dlg = RelockConfirmationDialog(
            device=dev,
            command="fastboot flashing lock",
            warnings=["Test warning"],
        )

        assert dlg._confirm_btn.isEnabled() is False

        # Wrong input
        dlg._input.setText("relock")
        assert dlg._confirm_btn.isEnabled() is False

        # Correct input in all caps
        dlg._input.setText("RELOCK")
        assert dlg._confirm_btn.isEnabled() is True


class TestReturnStockScreenUI:
    def test_screen_init(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = ReturnStockScreen(dm, adb, fb)

        assert screen._tabs.count() == 3
        assert screen._flash_btn is not None
        assert screen._flash_btn.isEnabled() is False
        assert screen._relock_btn.isEnabled() is False
        assert screen._wipe_cb.isChecked() is True

    def test_load_disconnected_device(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = ReturnStockScreen(dm, adb, fb)
        screen.load_for_device(None)

        assert "No device connected" in screen._dev_title_label.text()
        assert screen._flash_btn.isEnabled() is False
        assert screen._relock_btn.isEnabled() is False

    def test_load_connected_device_in_fastboot(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = ReturnStockScreen(dm, adb, fb)

        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            model="Pixel 7a",
            device="lynx",
            active_slot="a",
            battery_level=80,
        )
        screen.load_for_device(dev)

        assert "Google Pixel 7a [BOOTLOADER]" in screen._dev_title_label.text()
        assert "lynx" in screen._dev_detail_label.text()
        assert screen._reboot_fb_btn.isEnabled() is False  # Already in fastboot

    def test_load_connected_device_in_system_mode(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = ReturnStockScreen(dm, adb, fb)

        dev = DeviceInfo(
            serial="PIXEL123",
            mode="system",
            brand="Google",
            model="Pixel 7a",
            device="lynx",
            battery_level=80,
        )
        screen.load_for_device(dev)

        # In system mode, "Reboot to Fastboot" should be enabled
        assert screen._reboot_fb_btn.isEnabled() is True

    def test_package_loading_and_table_population(self, qapp, mock_deps, tmp_path: Path):
        dm, adb, fb = mock_deps
        screen = ReturnStockScreen(dm, adb, fb)

        # Create sample partition images
        (tmp_path / "boot.img").write_bytes(b"B" * 1024)
        (tmp_path / "vbmeta.img").write_bytes(b"V" * 1024)
        (tmp_path / "system.img").write_bytes(b"S" * 2048)
        (tmp_path / "android-info.txt").write_text("require board=lynx\n")

        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=85,
        )
        screen.load_for_device(dev)
        screen._load_package(tmp_path)

        assert screen._current_pkg is not None
        assert screen._current_pkg.is_valid is True
        assert screen._part_table.rowCount() == 3
        assert screen._part_table.isHidden() is False
        assert screen._flash_btn.isEnabled() is True

    def test_relock_gate_updates_after_successful_flash(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = ReturnStockScreen(dm, adb, fb)

        dev = DeviceInfo(
            serial="PIXEL123",
            mode="bootloader",
            brand="Google",
            device="lynx",
            battery_level=90,
        )
        screen.load_for_device(dev)

        # Initially, relock is prohibited
        assert screen._relock_btn.isEnabled() is False
        assert "PROHIBITED" in screen._gate_status_label.text()

        # Simulate flash completed successfully
        flash_res = ReturnStockResult(
            success=True,
            steps=[
                FlashStepResult(partition="boot", status="success"),
                FlashStepResult(partition="vbmeta", status="success"),
            ],
            ready_for_relock=True,
        )
        screen._on_flash_finished(flash_res)

        assert screen._relock_btn.isEnabled() is True
        assert "READY TO RELOCK" in screen._gate_status_label.text()
