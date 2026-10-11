"""
Unit tests -- Bootloader unlock wizard screen (UI tests).
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.screens.unlock_screen import UnlockScreen, _StepWidget
from flashdock.brands import UnlockStep


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


class TestUnlockStepWidget:
    def test_manual_step_widget(self, qapp):
        step = UnlockStep(index=1, title="Enable OEM", description="Turn on OEM unlock", action="manual")
        w = _StepWidget(step)
        assert not hasattr(w, "_exec_btn")
        w.mark_completed("Done manually")
        assert step.completed is True
        assert "Done manually" in w._result_label.text()

    def test_auto_step_widget_complete(self, qapp):
        step = UnlockStep(index=2, title="Reboot", description="Reboot to bootloader",
                          action="auto", command_preview="adb reboot bootloader")
        w = _StepWidget(step)
        assert hasattr(w, "_exec_btn")
        w.mark_completed("Rebooted")
        assert step.completed is True
        assert not w._exec_btn.isEnabled()

    def test_auto_step_widget_fail(self, qapp):
        step = UnlockStep(index=3, title="Unlock", description="Unlock cmd",
                          action="auto", command_preview="fastboot oem unlock")
        w = _StepWidget(step)
        w.mark_failed("Device not found")
        assert "Device not found" in w._result_label.text()


class TestUnlockScreenLoading:
    def test_no_device_shows_placeholder(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        screen.load_for_device(None)
        assert "No device connected" in screen._subtitle.text()
        assert screen._flow is None

    def test_device_not_connected_mode(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        device = DeviceInfo(mode="not_connected")
        screen.load_for_device(device)
        assert "No device connected" in screen._subtitle.text()

    def test_already_unlocked_device(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        device = DeviceInfo(brand="google", model="Pixel 7", bootloader_state="unlocked", mode="system")
        screen.load_for_device(device)
        assert "already UNLOCKED" in screen._subtitle.text()
        assert screen._flow is None

    def test_loads_google_flow(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        device = DeviceInfo(brand="google", model="Pixel 7 Pro", bootloader_state="locked", mode="system")
        screen.load_for_device(device)
        assert screen._flow is not None
        assert screen._flow.brand == "google"
        assert len(screen._step_widgets) >= 4

    def test_loads_xiaomi_flow(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        device = DeviceInfo(brand="xiaomi", model="Mi 11", bootloader_state="locked", mode="system")
        screen.load_for_device(device)
        assert screen._flow is not None
        assert screen._flow.brand == "xiaomi"
        assert len(screen._step_widgets) >= 6

    def test_loads_samsung_flow(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        device = DeviceInfo(brand="samsung", model="Galaxy S23", bootloader_state="locked", mode="system")
        screen.load_for_device(device)
        assert screen._flow is not None
        assert screen._flow.brand == "samsung"

    def test_loads_oneplus_flow(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        device = DeviceInfo(brand="oneplus", model="OnePlus 11", bootloader_state="locked", mode="system")
        screen.load_for_device(device)
        assert screen._flow is not None
        assert screen._flow.brand == "oneplus"

    def test_loads_generic_flow_for_unknown(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = UnlockScreen(dm, adb, fb)
        device = DeviceInfo(brand="unknownbrand", model="Phone X", bootloader_state="locked", mode="system")
        screen.load_for_device(device)
        assert screen._flow is not None
        assert screen._flow.brand == "generic"
