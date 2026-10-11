"""
Unit tests — HardwareKeyGuideDialog widget and PhoneControlPanel hardware key signals.
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication, QTabWidget, QPushButton

from flashdock.ui.widgets.key_guide_dialog import HardwareKeyGuideDialog
from flashdock.ui.widgets.phone_panel import PhoneControlPanel


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestHardwareKeyGuideDialog:
    def test_init_and_tabs(self, qapp):
        mock_adb = MagicMock()
        dlg = HardwareKeyGuideDialog(adb=mock_adb)
        assert "Hardware Keys" in dlg.windowTitle()

        tabs = dlg.findChild(QTabWidget)
        assert tabs is not None
        assert tabs.count() == 3  # Bootloader Nav, Key Combos, Remote Control

    def test_phone_panel_key_signals(self, qapp):
        panel = PhoneControlPanel()
        received_keys = []
        guide_requested = []

        panel.key_event_requested.connect(lambda k: received_keys.append(k))
        panel.key_guide_requested.connect(lambda: guide_requested.append(True))

        # Check button existence
        vol_up = panel.findChild(QPushButton, "btn_key_volup")
        vol_down = panel.findChild(QPushButton, "btn_key_voldown")
        power = panel.findChild(QPushButton, "btn_key_power")
        guide_btn = panel.findChild(QPushButton, "btn_key_guide")

        assert vol_up is not None
        assert vol_down is not None
        assert power is not None
        assert guide_btn is not None

        vol_up.click()
        vol_down.click()
        power.click()
        guide_btn.click()

        assert 24 in received_keys  # KEYCODE_VOLUME_UP
        assert 25 in received_keys  # KEYCODE_VOLUME_DOWN
        assert 26 in received_keys  # KEYCODE_POWER
        assert len(guide_requested) == 1
