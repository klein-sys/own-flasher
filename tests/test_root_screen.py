"""
Unit tests — RootScreen UI widget.
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.screens.root_screen import RootScreen


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
    fastboot = MagicMock(spec=Fastboot)
    return device_mgr, adb, fastboot


class TestRootScreenUI:
    def test_init_ui(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = RootScreen(dm, adb, fb)
        assert screen._tabs.count() == 3
        assert screen._rb_magisk.isChecked() is True
        assert screen._btn_flash.isEnabled() is False

    def test_load_legacy_device(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = RootScreen(dm, adb, fb)
        device = DeviceInfo(
            brand="samsung",
            model="Galaxy S10",
            android_version="10",
            sdk_version="29",
            kernel_version="4.14.113",
            mode="system",
            bootloader_state="unlocked",
        )
        screen.load_for_device(device)
        assert screen._rb_magisk.isChecked() is True
        assert "boot" in screen._part_target_label.text()
        assert screen._compat_report is not None

    def test_load_gki_device(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = RootScreen(dm, adb, fb)
        device = DeviceInfo(
            brand="google",
            model="Pixel 8",
            android_version="14",
            sdk_version="34",
            kernel_version="5.15.110-android14",
            mode="system",
            bootloader_state="unlocked",
        )
        screen.load_for_device(device)
        assert screen._rb_ksu.isChecked() is True
        assert "init_boot" in screen._part_target_label.text()

    def test_solution_radio_toggle(self, qapp, mock_deps):
        dm, adb, fb = mock_deps
        screen = RootScreen(dm, adb, fb)
        device = DeviceInfo(
            brand="google",
            model="Pixel 7",
            android_version="13",
            sdk_version="33",
            kernel_version="5.10.150",
            mode="system",
        )
        screen.load_for_device(device)

        screen._rb_apatch.setChecked(True)
        assert screen._selected_solution() == "apatch"
        assert "APatch" in screen._sol_desc.text()

        screen._rb_magisk_alpha.setChecked(True)
        assert screen._selected_solution() == "magisk_alpha"
        assert "Alpha" in screen._sol_desc.text()

        screen._rb_kitsune.setChecked(True)
        assert screen._selected_solution() == "kitsune"
        assert "Kitsune" in screen._sol_desc.text()

        screen._rb_canary.setChecked(True)
        assert screen._selected_solution() == "magisk_canary"
        assert "Canary" in screen._sol_desc.text()

        screen._rb_ksu_next.setChecked(True)
        assert screen._selected_solution() == "kernelsu_next"
        assert "Next" in screen._sol_desc.text()

        screen._rb_sukisu.setChecked(True)
        assert screen._selected_solution() == "sukisu"
        assert "SukiSU" in screen._sol_desc.text()

        screen._rb_magisk.setChecked(True)
        assert screen._selected_solution() == "magisk"
        assert "Magisk" in screen._sol_desc.text()

    def test_custom_root_apk_selection_and_library(self, qapp, mock_deps, tmp_path, monkeypatch):
        from flashdock import constants
        test_root_apps = tmp_path / "root_apps"
        test_root_apps.mkdir()
        monkeypatch.setattr(constants, "ROOT_APPS_DIR", test_root_apps)
        import flashdock.core.rooting as rooting_mod
        monkeypatch.setattr(rooting_mod, "ROOT_APPS_DIR", test_root_apps)
        import flashdock.ui.widgets.root_library_dialog as rld_mod
        monkeypatch.setattr(rld_mod, "ROOT_APPS_DIR", test_root_apps)

        # Create sample custom APK
        test_apk = test_root_apps / "CustomRoot_v2.apk"
        test_apk.write_bytes(b"DUMMY_CUSTOM_APK")

        dm, adb, fb = mock_deps
        screen = RootScreen(dm, adb, fb)
        device = DeviceInfo(brand="google", model="Pixel 7", android_version="13", sdk_version="33")
        screen.load_for_device(device)

        # Stored custom APK should appear in custom radios
        assert "custom_customroot_v2" in screen._custom_radios
        custom_rb = screen._custom_radios["custom_customroot_v2"]
        custom_rb.setChecked(True)
        assert screen._selected_solution() == "custom_customroot_v2"
        assert "CustomRoot_v2" in screen._sol_desc.text()

    def test_dialogs_instantiation(self, qapp, mock_deps):
        from flashdock.ui.widgets.root_library_dialog import RootAppsLibraryDialog, RootDownloadsDialog
        dlg_lib = RootAppsLibraryDialog()
        assert dlg_lib._table.columnCount() == 4

        dlg_down = RootDownloadsDialog()
        assert dlg_down.windowTitle().startswith("🌐")
