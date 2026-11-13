"""
Unit tests for flashdock.ui.widgets.dynamic_island.
Verifies DynamicIslandPill telemetry updates, WriteSafetySwitch toggles,
and ObsidianDynamicIslandBar layout.
"""

import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.ui.widgets.dynamic_island import (
    DynamicIslandPill,
    LiquidGlassSegmentedControl,
    ObsidianDynamicIslandBar,
    WriteSafetySwitch,
)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dynamic_island_pill_not_connected(qapp):
    pill = DynamicIslandPill()
    pill.update_device(None)
    assert pill.primary_lbl.text() == "No Device Connected"
    assert pill.telemetry_lbl.text() == "Workstation Ready"
    assert pill.dot_lbl.text() == "○"
    pill.repaint()


def test_dynamic_island_pill_connected_device(qapp):
    pill = DynamicIslandPill()
    dev = DeviceInfo(
        serial="10944373AP103289",
        brand="MediaTek",
        model="ADB",
        mode="adb",
        battery_level=84,
        chipset="MT6789",
        active_slot="a",
        is_rooted=True,
        root_method="magisk",
    )
    pill.update_device(dev)
    assert "ADB" in pill.primary_lbl.text()
    assert "10944373AP103289" in pill.primary_lbl.text()
    assert "Batt 84%" in pill.telemetry_lbl.text()
    assert "MT6789" in pill.telemetry_lbl.text()
    assert "Slot _A ⇄" in pill.telemetry_lbl.text()
    assert pill.dot_lbl.text() == "●"
    pill.repaint()


def test_write_safety_switch(qapp):
    sw = WriteSafetySwitch(is_armed=False)
    assert sw.is_armed is False
    assert "Safe" in sw.text_lbl.text()

    # Toggle to Armed
    sw.set_armed(True)
    assert sw.is_armed is True
    assert "Armed" in sw.text_lbl.text()
    sw.repaint()


def test_segmented_lens_control(qapp):
    lens = LiquidGlassSegmentedControl()
    assert lens._active_key == "All"
    lens.set_active_segment("Root")
    assert lens._active_key == "Root"
    lens.repaint()


def test_obsidian_dynamic_island_bar(qapp):
    bar = ObsidianDynamicIslandBar()
    assert bar.island_pill is not None
    assert bar.write_switch is not None
    assert bar.lens_control is not None
    bar.repaint()
