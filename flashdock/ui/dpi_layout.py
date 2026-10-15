"""
FlashDock v1.5.0 — High-DPI Geometry, Splitter & ScrollArea Hardening Engine.

Eliminates widget clipping, label truncation, nested double scrollbars, and
cramped form rows across 100%, 125%, 150%, and 200% Windows High-DPI displays.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QComboBox,
    QDialog,
    QFrame,
    QLayout,
    QLineEdit,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QWidget,
)

MIN_BUTTON_HEIGHT_PX = 34
MIN_INPUT_HEIGHT_PX = 34
MIN_CENTRAL_CANVAS_WIDTH_PX = 640
MIN_SIDE_TERMINAL_WIDTH_PX = 280


def configure_frameless_scroll_area(scroll_area: QScrollArea) -> None:
    """
    Standardize a `QScrollArea` so it never spawns nested double borders,
    clips child cards, or forces horizontal scrollbars on High-DPI displays.
    """
    scroll_area.setWidgetResizable(True)
    scroll_area.setFrameShape(QFrame.Shape.NoFrame)
    scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    viewport = scroll_area.viewport()
    if viewport is not None:
        viewport.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        viewport.setStyleSheet("background: transparent; border: none;")


def apply_responsive_screen_geometry(root_widget: QWidget) -> None:
    """
    Recursively normalize `QSizePolicy`, `minimumHeight`, and scroll viewports
    inside any FlashDock screen or dialog so controls never crush vertically.
    """
    if root_widget is None:
        return

    for scroll in root_widget.findChildren(QScrollArea):
        configure_frameless_scroll_area(scroll)

    for btn in root_widget.findChildren(QAbstractButton):
        if btn.minimumHeight() < 28:
            btn.setMinimumHeight(MIN_BUTTON_HEIGHT_PX)

    for line_edit in root_widget.findChildren(QLineEdit):
        if line_edit.minimumHeight() < 28:
            line_edit.setMinimumHeight(MIN_INPUT_HEIGHT_PX)
        pol = line_edit.sizePolicy()
        pol.setHorizontalPolicy(QSizePolicy.Policy.Expanding)
        line_edit.setSizePolicy(pol)

    for combo in root_widget.findChildren(QComboBox):
        if combo.minimumHeight() < 28:
            combo.setMinimumHeight(MIN_INPUT_HEIGHT_PX)

    layout: QLayout | None = root_widget.layout()
    if layout is not None:
        margins = layout.contentsMargins()
        if margins.left() == 0 and margins.top() == 0 and margins.right() == 0:
            layout.setContentsMargins(16, 16, 16, 16)
        if layout.spacing() < 6:
            layout.setSpacing(10)


def harden_splitter_geometry(
    splitter: QSplitter,
    primary_min_width: int = MIN_CENTRAL_CANVAS_WIDTH_PX,
    secondary_min_width: int = MIN_SIDE_TERMINAL_WIDTH_PX,
) -> None:
    """
    Harden the central workspace vs. `SideTerminalWidget` `QSplitter` so that
    expanding the terminal never clips the 4-column Home Canvas (`DeviceCard`).
    """
    if splitter is None:
        return
    splitter.setChildrenCollapsible(False)
    splitter.setHandleWidth(2)
    if splitter.count() >= 1 and splitter.widget(0) is not None:
        splitter.widget(0).setMinimumWidth(primary_min_width)
        splitter.setStretchFactor(0, 4)
    if splitter.count() >= 2 and splitter.widget(1) is not None:
        splitter.widget(1).setMinimumWidth(secondary_min_width)
        splitter.setStretchFactor(1, 1)


def harden_modal_dialog(dialog: QDialog, min_width: int = 520, min_height: int = 360) -> None:
    """
    Standardize modal dialog sizing, High-DPI control heights, and keyboard focus.
    """
    if dialog is None:
        return
    if dialog.minimumWidth() < 320:
        dialog.setMinimumWidth(min_width)
    if dialog.minimumHeight() < 240:
        dialog.setMinimumHeight(min_height)
    dialog.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    apply_responsive_screen_geometry(dialog)
