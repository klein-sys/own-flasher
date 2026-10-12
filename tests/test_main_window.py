"""
Unit tests — MainWindow UI, Theme Toggle & Navigation (Phase 10).
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.config import Config
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.network import NetworkMonitor
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.main_window import (
    MainWindow,
    PAGE_HOME,
    PAGE_DEVICE_CARD,
    PAGE_DIAGNOSTICS,
    PAGE_DOWNLOADS,
    PAGE_UNBRICK,
    PAGE_INTEGRITY,
    PAGE_LOGS_HELP,
    PAGE_SIDELOAD,
)



@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_main_window(tmp_path):
    config = Config(path=tmp_path / "config.json")
    network = MagicMock(spec=NetworkMonitor)
    network.is_online = True
    device_mgr = MagicMock(spec=DeviceManager)
    device_mgr.device = None
    device_mgr.all_devices = []
    device_mgr.locked_serial = None
    adb = MagicMock(spec=ADB)
    fastboot = MagicMock(spec=Fastboot)

    win = MainWindow(
        config=config,
        network=network,
        device_mgr=device_mgr,
        adb=adb,
        fastboot=fastboot,
    )
    return win


class TestMainWindow:
    def test_theme_toggle(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._config.get("theme", "dark") == "dark"
        assert "Light" in win._theme_btn.text()

        # Toggle to light
        win._toggle_theme()
        assert win._config.get("theme") == "light"
        assert "Dark" in win._theme_btn.text()

        # Toggle back to dark
        win._toggle_theme()
        assert win._config.get("theme") == "dark"
        assert "Light" in win._theme_btn.text()

    def test_navigation_to_diagnostics(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger diagnostics action
        win._on_action("diagnostics")
        assert win._stack.currentIndex() == PAGE_DIAGNOSTICS

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_device_change_refreshes_diagnostics(self, qapp, mock_main_window):
        win = mock_main_window
        win._stack.setCurrentIndex(PAGE_DIAGNOSTICS)

        dev = DeviceInfo(serial="DEV_99", brand="Xiaomi", model="POCO F3", mode="adb")
        win._handle_device_change(dev)
        assert "DEV_99" in win._diagnostics_screen._device_badge.text()

    def test_navigation_to_downloads(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger downloads action
        win._on_action("downloads")
        assert win._stack.currentIndex() == PAGE_DOWNLOADS

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_unbrick(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger unbrick action
        win._on_action("unbrick")
        assert win._stack.currentIndex() == PAGE_UNBRICK

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_integrity(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger integrity action
        win._on_action("integrity")
        assert win._stack.currentIndex() == PAGE_INTEGRITY

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_logs_help(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger logs_help action
        win._on_action("logs_help")
        assert win._stack.currentIndex() == PAGE_LOGS_HELP

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_sideload(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger sideload action
        win._on_action("sideload")
        assert win._stack.currentIndex() == PAGE_SIDELOAD

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_tool_filter_by_category(self, qapp, mock_main_window):
        win = mock_main_window
        # Initial: All tools visible
        visible_initial = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert len(visible_initial) == 16

        # Filter by Rescue
        win._on_category_clicked("Rescue")
        visible_rescue = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "unbrick" in visible_rescue
        assert "backup" in visible_rescue
        assert "checklist" in visible_rescue
        assert "root" not in visible_rescue
        assert len(visible_rescue) == 3

        # Filter by Root
        win._on_category_clicked("Root")
        visible_root = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "root" in visible_root
        assert "modules" in visible_root
        assert "integrity" in visible_root
        assert len(visible_root) == 3

        # Filter by Device (includes scrcpy and sideload)
        win._on_category_clicked("Device")
        visible_dev = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "scrcpy" in visible_dev
        assert "sideload" in visible_dev
        assert len(visible_dev) == 6

    def test_tool_filter_by_search_query(self, qapp, mock_main_window):
        win = mock_main_window
        # Search for bootloop
        win._search_input.setText("bootloop")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "unbrick" in visible
        assert "diagnostics" not in visible

        # Search for scrcpy / mirror
        win._search_input.setText("mirror")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "scrcpy" in visible
        assert "root" not in visible

        # Search for drivers
        win._search_input.setText("driver")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "downloads" in visible
        assert "root" not in visible

        # Search for sideload
        win._search_input.setText("sideload")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "sideload" in visible
        assert "root" not in visible

        # Search for non-existent keyword shows empty state
        win._search_input.setText("nonexistent_unknown_tool_xyz")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert len(visible) == 0
        assert not win._empty_state_widget.isHidden()

        # Reset filters
        win._reset_filters()
        assert win._search_input.text() == ""
        assert win._active_category == "All"
        visible_reset = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert len(visible_reset) == 16
        assert win._empty_state_widget.isHidden()

        # Test tool sorting
        win._sort_combo.setCurrentIndex(1)  # A -> Z
        assert win._sort_combo.currentData() == "az"
        # Reset back to recommended
        win._reset_filters()
        assert win._sort_combo.currentData() == "recommended"

    def test_device_selector_footer_and_stretched_brand_bar(self, qapp, mock_main_window):
        """Fix 16 & Fix 17: DeviceSelector sits in bottom bar, brand showcase stretches evenly."""
        win = mock_main_window
        # Check brand bar stretches 12 OEM buttons
        assert hasattr(win, "_seg_frame")
        assert len(win._gsm_btn_group) == 12
        for key, btn in win._gsm_btn_group.items():
            assert btn.sizePolicy().horizontalPolicy().name == "Expanding"

        # Check DeviceSelector is initialized in bottom bar with action widgets
        assert hasattr(win, "_device_selector")
        assert hasattr(win, "_btn_driver_fix")
        assert hasattr(win, "_btn_terminal_toggle")

    def test_terminal_clean_toggle_and_fixed_width(self, qapp, mock_main_window):
        """Fix 18: Terminal is fixed 320px width when visible, toggles smoothly without layout glitches."""
        win = mock_main_window
        assert win._side_terminal.isHidden() is False
        assert "Hide Terminal" in win._btn_terminal_toggle.text()

        # Toggle terminal to hidden
        win._toggle_terminal_visibility()
        assert win._side_terminal.isHidden() is True
        assert "Show Terminal" in win._btn_terminal_toggle.text()

        # Toggle terminal back to visible
        win._toggle_terminal_visibility()
        assert win._side_terminal.isHidden() is False
        assert win._side_terminal.maximumWidth() == 320
        assert "Hide Terminal" in win._btn_terminal_toggle.text()

