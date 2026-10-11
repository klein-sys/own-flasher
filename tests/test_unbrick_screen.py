"""
UI tests — UnbrickScreen & Bootloop Rescue Screen.
"""

from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.screens.unbrick_screen import UnbrickScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_unbrick_screen(qapp):
    dev_mgr = MagicMock(spec=DeviceManager)
    dev_mgr.device = None
    adb = MagicMock(spec=ADB)
    fastboot = MagicMock(spec=Fastboot)

    screen = UnbrickScreen(device_mgr=dev_mgr, adb=adb, fastboot=fastboot)
    return screen


class TestUnbrickScreen:
    def test_screen_init_tabs_count(self, mock_unbrick_screen):
        screen = mock_unbrick_screen
        assert screen._tabs.count() == 3
        assert "Fix Bootloop" in screen._tabs.tabText(0)
        assert "Boot Partition Restorer" in screen._tabs.tabText(1)
        assert "Hardware & Unbrick Guides" in screen._tabs.tabText(2)

    def test_load_for_device_updates_badges(self, mock_unbrick_screen):
        screen = mock_unbrick_screen

        dev = DeviceInfo(
            serial="PIXEL_BOOTLOOP",
            brand="Google",
            model="Pixel 7",
            device="panther",
            mode="bootloader",
        )
        with patch.object(screen._fixer, "get_current_fastboot_slot", return_value="a"):
            screen.load_for_device(dev)

        assert "Pixel 7" in screen._device_badge.text()
        assert "Slot A" in screen._slot_status_lbl.text()

    def test_navigation_signal_emitted(self, mock_unbrick_screen):
        screen = mock_unbrick_screen
        signal_target = MagicMock()
        screen.navigate_to_page.connect(signal_target)

        screen.navigate_to_page.emit(7)
        signal_target.assert_called_once_with(7)
