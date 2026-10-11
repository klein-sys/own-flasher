"""
Tests for FlashDock Phase 10 — Advanced Diagnostics, Debloater & System Tweaks.
"""

from unittest.mock import MagicMock
import pytest

from flashdock.core.diagnostics import (
    CRITICAL_PROTECTED_PACKAGES,
    DebloaterManager,
    HardwareHealthInspector,
    SystemTweaker,
)
from flashdock.tools.adb import ADB
from flashdock.tools.runner import CommandResult


def make_result(stdout: str = "", return_code: int = 0, stderr: str = "") -> CommandResult:
    return CommandResult(
        command=["mock"],
        return_code=return_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=10,
    )


@pytest.fixture
def mock_adb():
    adb = MagicMock(spec=ADB)
    adb.available = True
    return adb


class TestDebloaterManager:
    def test_list_packages_categorization(self, mock_adb):
        manager = DebloaterManager(adb=mock_adb)

        # Mock packages list
        mock_adb.shell.side_effect = [
            # pm list packages -u -f
            make_result(
                stdout=(
                    "package:/system/priv-app/SystemUI/SystemUI.apk=com.android.systemui\n"
                    "package:/system/app/Facebook/Facebook.apk=com.facebook.katana\n"
                    "package:/system/priv-app/Vzw/vzw.apk=com.vzw.apnlib\n"
                    "package:/data/app/MyApp/base.apk=com.example.myapp\n"
                    "package:/system/priv-app/Oem/oem.apk=com.oem.customservice\n"
                )
            ),
            # pm list packages -d
            make_result(stdout="package:com.facebook.katana\n"),
            # pm list packages -3
            make_result(stdout="package:com.example.myapp\n"),
        ]

        pkgs = manager.list_packages(serial="DEVICE1")
        assert len(pkgs) == 5

        # Protected core
        sysui = next(p for p in pkgs if p.package_name == "com.android.systemui")
        assert sysui.category == "protected"
        assert sysui.can_debloat is False
        assert sysui.is_enabled is True

        # Known bloat
        fb = next(p for p in pkgs if p.package_name == "com.facebook.katana")
        assert fb.category == "bloat"
        assert fb.can_debloat is True
        assert fb.is_enabled is False

        # Carrier
        vzw = next(p for p in pkgs if p.package_name == "com.vzw.apnlib")
        assert vzw.category == "carrier"

        # Third party user
        my_app = next(p for p in pkgs if p.package_name == "com.example.myapp")
        assert my_app.category == "user"
        assert my_app.is_system is False

    def test_disable_protected_package_blocked(self, mock_adb):
        manager = DebloaterManager(adb=mock_adb)
        ok, msg = manager.disable_package("com.android.systemui", serial="DEV")
        assert ok is False
        assert "essential" in msg.lower()
        mock_adb.shell.assert_not_called()

    def test_disable_bloat_package_success(self, mock_adb):
        manager = DebloaterManager(adb=mock_adb)
        mock_adb.shell.return_value = make_result(stdout="Package com.facebook.katana new state: disabled-user")
        ok, msg = manager.disable_package("com.facebook.katana", serial="DEV")
        assert ok is True
        assert "Disabled" in msg

    def test_uninstall_package_success(self, mock_adb):
        manager = DebloaterManager(adb=mock_adb)
        mock_adb.shell.return_value = make_result(stdout="Success")
        ok, msg = manager.uninstall_package("com.facebook.katana", serial="DEV")
        assert ok is True

    def test_restore_package_success(self, mock_adb):
        manager = DebloaterManager(adb=mock_adb)
        mock_adb.shell.side_effect = [
            make_result(stdout="Package com.facebook.katana new state: default"),
            make_result(stdout="Package com.facebook.katana installed for user: 0"),
        ]
        ok, msg = manager.restore_package("com.facebook.katana", serial="DEV")
        assert ok is True


class TestHardwareHealthInspector:
    def test_get_battery_health_parsing(self, mock_adb):
        inspector = HardwareHealthInspector(adb=mock_adb)
        mock_adb.shell.return_value = make_result(
            stdout=(
                "Current Battery Service state:\n"
                "  AC powered: false\n"
                "  USB powered: true\n"
                "  level: 84\n"
                "  voltage: 4125\n"
                "  temperature: 315\n"
                "  technology: Li-poly\n"
                "  health: 2\n"
                "  Cycle count: 142\n"
            )
        )

        info = inspector.get_battery_health(serial="DEV")
        assert info.level == 84
        assert info.voltage_mv == 4125
        assert info.temperature_c == 31.5
        assert info.health_status == "Good"
        assert info.power_source == "USB Port"
        assert info.technology == "Li-poly"
        assert info.cycle_count == 142

    def test_get_hardware_specs(self, mock_adb):
        inspector = HardwareHealthInspector(adb=mock_adb)
        mock_adb.shell.side_effect = [
            # wm size
            make_result(stdout="Physical size: 1080x2400"),
            # wm density
            make_result(stdout="Physical density: 440"),
            # governor
            make_result(stdout="schedutil"),
            # cores
            make_result(stdout="8"),
            # thermal
            make_result(stdout="38500"),
        ]

        specs = inspector.get_hardware_specs(serial="DEV")
        assert specs.resolution == "1080x2400"
        assert specs.density_dpi == "440 DPI"
        assert specs.cpu_governor == "schedutil"
        assert specs.cpu_cores == 8
        assert "38.5°C" in specs.thermal_zones[0]


class TestSystemTweaker:
    def test_animation_scales(self, mock_adb):
        tweaker = SystemTweaker(adb=mock_adb)
        mock_adb.shell.side_effect = [
            make_result(stdout="0.5"),
            make_result(stdout="0.5"),
            make_result(stdout="0.5"),
        ]
        scales = tweaker.get_animation_scales(serial="DEV")
        assert scales["window"] == 0.5
        assert scales["transition"] == 0.5

        mock_adb.shell.side_effect = None
        mock_adb.shell.return_value = make_result(stdout="")
        ok, msg = tweaker.set_animation_scales(0.5, serial="DEV")
        assert ok is True
        assert "0.5x" in msg

    def test_screen_density(self, mock_adb):
        tweaker = SystemTweaker(adb=mock_adb)
        mock_adb.shell.return_value = make_result(stdout="")
        ok, msg = tweaker.set_screen_density(420, serial="DEV")
        assert ok is True
        assert "420 DPI" in msg

        # Out of bounds
        bad_ok, _ = tweaker.set_screen_density(50, serial="DEV")
        assert bad_ok is False

    def test_enable_wireless_adb(self, mock_adb):
        tweaker = SystemTweaker(adb=mock_adb)
        mock_adb.shell.side_effect = [
            make_result(stdout=""),
            make_result(stdout="inet 192.168.1.150/24 brd 192.168.1.255 scope global wlan0"),
        ]
        ok, msg = tweaker.enable_wireless_adb(serial="DEV")
        assert ok is True
        assert "192.168.1.150:5555" in msg
