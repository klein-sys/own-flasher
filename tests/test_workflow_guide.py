"""
Unit tests — WorkflowGuideDialog widget.
"""

import pytest
from PySide6.QtWidgets import QApplication

from flashdock.ui.widgets.workflow_guide import WorkflowGuideDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestWorkflowGuideDialog:
    def test_init_and_tabs(self, qapp):
        dlg = WorkflowGuideDialog()
        assert dlg.windowTitle() == "📖 FlashDock — Workflow & Function Guide"
        # 3 main tabs: Workflow, 13 Functions, Under the Hood
        from PySide6.QtWidgets import QTabWidget
        tabs = dlg.findChild(QTabWidget)
        assert tabs is not None
        assert tabs.count() == 3
