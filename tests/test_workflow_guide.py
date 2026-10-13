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
        # 3 main tabs: Workflow, Functions Reference, Under the Hood
        from PySide6.QtWidgets import QTabWidget
        tabs = dlg.findChild(QTabWidget)
        assert tabs is not None
        assert tabs.count() == 3

    def test_all_16_function_cards_loaded(self, qapp):
        dlg = WorkflowGuideDialog()
        assert len(dlg._cards_list) == 16
        assert len(dlg._FUNCTION_GUIDE_DATA) == 16

    def test_action_launch_signal(self, qapp):
        dlg = WorkflowGuideDialog()
        received_actions = []
        dlg.action_requested.connect(lambda aid: received_actions.append(aid))

        dlg._on_launch_tool("root")
        assert received_actions == ["root"]

    def test_search_filter(self, qapp):
        dlg = WorkflowGuideDialog()
        dlg._filter_function_cards("root")
        root_cards = [c for s, c in dlg._cards_list if "root" in s]
        other_cards = [c for s, c in dlg._cards_list if "root" not in s]
        assert all(not c.isHidden() for c in root_cards)
        assert any(c.isHidden() for c in other_cards)
