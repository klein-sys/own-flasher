"""
Unit tests — BackupScreen and FlashShieldDialog (UI tests).
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.screens.backup_screen import BackupScreen
from flashdock.ui.widgets.flash_shield import FlashShieldDialog


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


class TestFlashShieldDialog:
    def test_shield_lifecycle(self, qapp):
        shield = FlashShieldDialog()
        assert shield._is_active is True
        shield.update_progress("Flashing boot partition...", 30)
        assert "boot" in shield._status_label.text()
        assert shield._progress_bar.value() == 30

        shield.append_log("Writing 'boot'... OKAY")
        assert "Writing 'boot'" in shield._log_view.toPlainText()

        shield.mark_completed(True, "All partitions written.")
        assert shield._is_active is False
        assert shield._close_btn.isEnabled() is True


class TestBackupScreenUI:
    def test_screen_init(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = BackupScreen(dm, adb, fb)
        assert screen._tabs.count() == 3
        assert "boot" in screen._part_checkboxes

    def test_load_device(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = BackupScreen(dm, adb, fb)
        device = DeviceInfo(serial="TEST123", brand="google", model="Pixel 7", mode="system")
        screen.load_for_device(device)
        assert "Pixel 7" in screen._subtitle.text()

    def test_checkbox_selection(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = BackupScreen(dm, adb, fb)
        # Select all / clear
        for cb in screen._part_checkboxes.values():
            cb.setChecked(False)
        assert all(not cb.isChecked() for cb in screen._part_checkboxes.values())

        screen._part_checkboxes["boot"].setChecked(True)
        assert screen._part_checkboxes["boot"].isChecked() is True
