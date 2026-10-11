"""
Unit tests — SetupWizardDialog widget.
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication, QStackedWidget

from flashdock.ui.widgets.setup_wizard_dialog import SetupWizardDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSetupWizardDialog:
    def test_init_and_steps(self, qapp):
        mock_adb = MagicMock()
        mock_fastboot = MagicMock()
        mock_adb.available = True
        mock_fastboot.available = True

        dlg = SetupWizardDialog(adb=mock_adb, fastboot=mock_fastboot)
        assert "Setup Wizard" in dlg.windowTitle()

        stack = dlg.findChild(QStackedWidget)
        assert stack is not None
        assert stack.count() == 4  # 4 steps: Platform Tools, Drivers, USB Best Practices, Test Connection

        # Test step navigation
        assert dlg._current_step == 0
        dlg._go_next()
        assert dlg._current_step == 1
        dlg._go_prev()
        assert dlg._current_step == 0
