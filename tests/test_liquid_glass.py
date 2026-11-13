"""
Unit tests for flashdock.ui.widgets.liquid_glass_widget.
Verifies iOS 26 / visionOS Liquid Glass Sheet, Smoked-Obsidian Droplet and Action Rows.
"""

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QApplication

from flashdock.ui.widgets.liquid_glass_widget import (
    LiquidGlassActionRow,
    LiquidGlassDroplet,
    LiquidGlassSheet,
    enable_windows_acrylic_blur,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_liquid_glass_droplet_init_and_render(qapp):
    droplet = LiquidGlassDroplet("search", dark_mode=True)
    assert droplet.width() == 32
    assert droplet.height() == 32
    # Trigger paintEvent
    droplet.repaint()

    # Toggle to light mode
    droplet.set_dark_mode(False)
    droplet.repaint()


def test_liquid_glass_sheet_specular_sheen(qapp):
    sheet = LiquidGlassSheet(dark_mode=True, radius=18.0)
    assert sheet.radius == 18.0
    sheet.resize(300, 200)

    # Trigger hover & mouse move for specular glint
    sheet.enterEvent(None)
    assert sheet._hovered is True

    # Simulate mouse move
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(50.0, 50.0),
        QPointF(50.0, 50.0),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    sheet.mouseMoveEvent(event)
    assert sheet._mouse_pos == QPointF(50.0, 50.0)

    # Repaint with specular sheen active
    sheet.repaint()

    sheet.leaveEvent(None)
    assert sheet._hovered is False
    sheet.repaint()


def test_liquid_glass_action_row_compatibility(qapp):
    row = LiquidGlassActionRow(
        action_id="check_phone",
        icon="search",
        label="Check my phone",
        desc="Detect device & show full specs",
        category="Device",
        dark_mode=True,
    )
    assert row.action_id == "check_phone"
    assert row.label_str == "Check my phone"
    assert row.desc_str == "Detect device & show full specs"
    assert row.category == "Device"
    assert row.height() == 54

    # Check labels
    assert row.title_lbl.text() == "Check my phone"
    assert row.desc_lbl.text() == "Detect device & show full specs"

    # Theme toggle
    row.apply_theme("light")
    assert row.dark_mode is False
    row.apply_theme("dark")
    assert row.dark_mode is True

    # Offline state
    row.set_offline_state(True, "dark")
    assert row.isEnabled() is False
    row.set_offline_state(False, "dark")
    assert row.isEnabled() is True


def test_enable_windows_acrylic_blur():
    # Should execute safely without throwing
    enable_windows_acrylic_blur(0, dark=True)
    enable_windows_acrylic_blur(0, dark=False)
