"""
UI tests — Downloads, Drivers & Platform-Tools Screen (Phase 12).
"""

from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.screens.downloads_screen import DownloadsScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_downloads_screen(qapp):
    dev_mgr = MagicMock(spec=DeviceManager)
    dev_mgr.device = None
    adb = MagicMock(spec=ADB)
    fastboot = MagicMock(spec=Fastboot)

    screen = DownloadsScreen(device_mgr=dev_mgr, adb=adb, fastboot=fastboot)
    return screen


class TestDownloadsScreen:
    def test_screen_init_tabs_count(self, mock_downloads_screen):
        screen = mock_downloads_screen
        assert screen._tabs.count() == 3
        assert "Platform-Tools" in screen._tabs.tabText(0)
        assert "OEM USB Drivers" in screen._tabs.tabText(1)
        assert "Official Firmware" in screen._tabs.tabText(2)

    def test_load_for_device_updates_badges(self, mock_downloads_screen):
        screen = mock_downloads_screen

        dev = DeviceInfo(
            serial="PIXEL_8_TEST",
            brand="Google",
            model="Pixel 8 Pro",
            device="husky",
            mode="adb",
        )
        screen.load_for_device(dev)

        assert "Pixel 8 Pro" in screen._device_badge.text()
        assert "Google USB Driver" in screen._driver_suggestion_lbl.text()

    def test_category_switching_and_filtering(self, mock_downloads_screen):
        screen = mock_downloads_screen

        # Default all
        screen._set_fw_category("factory")
        assert screen._active_fw_category == "factory"
        assert screen._fw_cat_btn_factory.isChecked()

        screen._set_fw_category("gsi")
        assert screen._active_fw_category == "gsi"
        assert screen._fw_cat_btn_gsi.isChecked()

        # Search filter
        screen._fw_search_input.setText("LineageOS")
        # Should filter without crash
        assert screen._fw_search_input.text() == "LineageOS"

    def test_refresh_tools_status(self, mock_downloads_screen):
        screen = mock_downloads_screen
        with patch.object(screen._tools_mgr, "check_status") as mock_chk:
            mock_chk.return_value = {
                "adb": MagicMock(status="ready", version="37.0.1", binary_path="/path/adb"),
                "fastboot": MagicMock(status="ready", version="35.0.2", binary_path="/path/fastboot"),
            }
            screen.refresh_tools_status()
            mock_chk.assert_called_once()
            assert "37.0.1" in screen._adb_status_text.text()
            assert "35.0.2" in screen._fb_status_text.text()
