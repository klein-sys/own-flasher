"""
Unit tests — DiagnosticsScreen UI widget (Phase 10).
"""

from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.diagnostics import (
    BatteryHealthInfo,
    HardwareSpecs,
    InstalledPackage,
)
from flashdock.tools.adb import ADB
from flashdock.ui.screens.diagnostics_screen import DiagnosticsScreen


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
    return device_mgr, adb


class TestDiagnosticsScreenUI:
    def test_screen_init(self, qapp, mock_deps):
        dm, adb = mock_deps
        screen = DiagnosticsScreen(dm, adb)
        assert screen._tabs.count() == 3
        assert screen._pkg_table.columnCount() == 4
        assert screen._btn_disable is not None
        assert screen._btn_uninstall is not None
        assert screen._btn_restore is not None
        assert screen._lbl_batt_level.text() == "N/A"

    def test_load_device_and_populate_packages(self, qapp, mock_deps):
        dm, adb = mock_deps
        screen = DiagnosticsScreen(dm, adb)

        sample_packages = [
            InstalledPackage(
                package_name="com.android.systemui",
                label="System UI",
                is_system=True,
                is_enabled=True,
                category="protected",
                can_debloat=False,
            ),
            InstalledPackage(
                package_name="com.facebook.katana",
                label="Facebook App",
                is_system=True,
                is_enabled=True,
                category="bloat",
                can_debloat=True,
            ),
            InstalledPackage(
                package_name="com.vzw.apnlib",
                label="Verizon Telemetry",
                is_system=True,
                is_enabled=False,
                category="carrier",
                can_debloat=True,
            ),
        ]

        with patch("flashdock.core.diagnostics.DebloaterManager.list_packages", return_value=sample_packages), \
             patch("flashdock.core.diagnostics.HardwareHealthInspector.get_battery_health", return_value=BatteryHealthInfo(level=88, health_status="Good", voltage_mv=4200, temperature_c=32.0)), \
             patch("flashdock.core.diagnostics.HardwareHealthInspector.get_hardware_specs", return_value=HardwareSpecs(resolution="1080x2400", density_dpi="440 DPI", cpu_cores=8, cpu_governor="schedutil")):

            dev = DeviceInfo(serial="SERIAL123", brand="google", model="Pixel 7", mode="adb")
            screen.load_for_device(dev)

            assert screen._pkg_table.rowCount() == 3
            assert "com.android.systemui" in screen._pkg_table.item(0, 0).text()
            assert "PROTECTED" in screen._pkg_table.item(0, 2).text()
            assert "Facebook App" in screen._pkg_table.item(1, 1).text()
            assert "BLOAT" in screen._pkg_table.item(1, 2).text()

            # Health data populated
            assert screen._lbl_batt_level.text() == "88%"
            assert screen._lbl_batt_health.text() == "Good"
            assert screen._lbl_hw_res.text() == "1080x2400"
            assert screen._lbl_hw_dpi.text() == "440 DPI"

    def test_filter_packages(self, qapp, mock_deps):
        dm, adb = mock_deps
        screen = DiagnosticsScreen(dm, adb)
        screen._cached_packages = [
            InstalledPackage(package_name="com.facebook.katana", label="Facebook", category="bloat"),
            InstalledPackage(package_name="com.vzw.telemetry", label="Carrier", category="carrier"),
            InstalledPackage(package_name="com.spotify.music", label="Spotify", category="user"),
        ]

        # Search filter
        screen._search_input.setText("spotify")
        assert screen._pkg_table.rowCount() == 1
        assert "com.spotify.music" in screen._pkg_table.item(0, 0).text()

        # Category filter: Bloatware Only (index 1)
        screen._search_input.clear()
        screen._category_combo.setCurrentIndex(1)
        assert screen._pkg_table.rowCount() == 1
        assert "com.facebook.katana" in screen._pkg_table.item(0, 0).text()

    def test_tweaks_animation_and_density(self, qapp, mock_deps):
        dm, adb = mock_deps
        screen = DiagnosticsScreen(dm, adb)
        dev = DeviceInfo(serial="DEV_1", brand="google", model="Pixel", mode="adb")
        screen._current_device = dev

        with patch("flashdock.core.diagnostics.SystemTweaker.set_animation_scales", return_value=(True, "Animation scales set to 0.5x")) as mock_anim, \
             patch("flashdock.core.diagnostics.SystemTweaker.get_animation_scales", return_value={"window": 0.5, "transition": 0.5, "animator": 0.5}), \
             patch("flashdock.core.diagnostics.SystemTweaker.set_screen_density", return_value=(True, "Screen density adjusted to 400 DPI.")) as mock_dpi, \
             patch("flashdock.core.diagnostics.HardwareHealthInspector.get_battery_health", return_value=BatteryHealthInfo()), \
             patch("flashdock.core.diagnostics.HardwareHealthInspector.get_hardware_specs", return_value=HardwareSpecs(density_dpi="400 DPI")):

            screen._apply_animation_scale(0.5)
            mock_anim.assert_called_once_with(0.5, serial="DEV_1")
            assert "0.5x" in screen._lbl_current_anims.text()

            screen._spin_dpi.setValue(400)
            screen._apply_dpi()
            mock_dpi.assert_called_once_with(400, serial="DEV_1")
