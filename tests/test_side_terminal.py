"""
Unit tests — Side Activity Terminal widget.
"""

import pytest
from PySide6.QtWidgets import QApplication

from flashdock.ui.widgets.side_terminal import SideTerminalWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSideTerminalWidget:
    def test_init_and_properties(self, qapp):
        term = SideTerminalWidget()
        assert term.width() == 320
        assert term._text_edit.isReadOnly() is True  # Non-editable requirement

    def test_append_line_and_clear(self, qapp):
        term = SideTerminalWidget()
        term.append_line("fastboot flash boot boot.img", level="command")
        term.append_line("Flash complete", level="info")

        plain_text = term._text_edit.toPlainText()
        assert "fastboot flash boot" in plain_text
        assert "Flash complete" in plain_text

        term.clear()
        assert term._text_edit.toPlainText() == ""

    def test_collapse_toggle(self, qapp):
        term = SideTerminalWidget()
        assert term._is_collapsed is False

        term._toggle_collapse()
        assert term._is_collapsed is True
        assert term.width() == 40
        assert term._text_edit.isVisible() is False

        term._toggle_collapse()
        assert term._is_collapsed is False
        assert term.width() == 320
        assert term._text_edit.isHidden() is False
