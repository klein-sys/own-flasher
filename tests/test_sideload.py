"""
Unit & Integration Tests — Universal Sideloading & App Manager (Phase 23).

Tests:
1. SideloadFlags: argument generation, Android 14+ SDK 34 bypass, permissions, downgrade, user 0.
2. extract_apk_metadata:
   - Plain ZIP with manifest.json (XAPK structure)
   - APK with binary/simulated AndroidManifest.xml
   - APK with icon and OBB files
3. SideloadManager:
   - Single APK installation command generation and execution
   - Android 14+ automatic low-target-sdk-block bypass detection
   - Split bundle (.xapk) extraction, install-multiple command, and OBB push
   - Recovery mode OTA ZIP sideloading and progress parsing
   - Package enumeration (3rd party, system, disabled)
   - Package management operations (pull, clear, force_stop, disable, enable, uninstall)
4. SideloadScreen UI:
   - Instantiation, device loading, file drag/drop selection, metadata card update, and theme switching.
"""

from __future__ import annotations

import io
import json
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.tools.adb import ADB
from flashdock.tools.runner import CommandResult
from flashdock.tools.sideload import (
    ApkMetadata,
    SideloadAppItem,
    SideloadFlags,
    SideloadManager,
    extract_apk_metadata,
)
from flashdock.ui.screens.sideload_screen import FileDropZone, SideloadScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Test SideloadFlags
# ---------------------------------------------------------------------------

class TestSideloadFlags:
    def test_default_flags(self):
        flags = SideloadFlags()
        args = flags.to_adb_args(device_sdk=30)
        assert "-r" in args
        assert "-d" in args
        assert "-g" in args
        assert "-t" not in args
        assert "--user" not in args
        assert "--bypass-low-target-sdk-block" not in args

    def test_android_14_auto_bypass(self):
        flags = SideloadFlags()
        # SDK 34 is Android 14
        args = flags.to_adb_args(device_sdk=34)
        assert "--bypass-low-target-sdk-block" in args

        # Explicit bypass flag on older Android
        flags.bypass_low_sdk_block = True
        args2 = flags.to_adb_args(device_sdk=31)
        assert "--bypass-low-target-sdk-block" in args2

    def test_optional_user_and_test_flags(self):
        flags = SideloadFlags(
            allow_test_packages=True,
            install_user_0=True,
            allow_downgrade=False,
        )
        args = flags.to_adb_args(device_sdk=33)
        assert "-t" in args
        assert "--user" in args
        assert "0" in args
        assert "-d" not in args


# ---------------------------------------------------------------------------
# Test extract_apk_metadata
# ---------------------------------------------------------------------------

class TestMetadataExtractor:
    def test_extract_from_xapk_bundle(self, tmp_path):
        xapk_file = tmp_path / "test_app.xapk"
        manifest_data = {
            "xapk_version": 1,
            "package_name": "com.hyperos.tool",
            "name": "HyperOS Tool",
            "version_name": "2.4.0",
            "version_code": "240",
            "min_sdk_version": "26",
            "target_sdk_version": "34",
        }
        with zipfile.ZipFile(xapk_file, "w") as zf:
            zf.writestr("manifest.json", json.dumps(manifest_data))
            zf.writestr("base.apk", b"PK\x03\x04fakepk")
            zf.writestr("config.arm64_v8a.apk", b"PK\x03\x04splitapk")
            zf.writestr("icon.png", b"\x89PNG\r\n\x1a\nfakeicon")
            zf.writestr("Android/obb/com.hyperos.tool/main.240.com.hyperos.tool.obb", b"fakeobbdata")

        meta = extract_apk_metadata(xapk_file)
        assert meta.package_name == "com.hyperos.tool"
        assert meta.app_label == "HyperOS Tool"
        assert meta.version_name == "2.4.0"
        assert meta.version_code == 240
        assert meta.min_sdk == 26
        assert meta.target_sdk == 34
        assert meta.is_split is True
        assert len(meta.split_names) == 2
        assert len(meta.obb_files) == 1
        assert meta.icon_bytes is not None
        assert "HyperOS Tool • v2.4.0" in meta.summary_line

    def test_extract_from_synthetic_apk(self, tmp_path):
        apk_file = tmp_path / "sample_app.apk"
        with zipfile.ZipFile(apk_file, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake binary manifest content")
            zf.writestr("res/mipmap-hdpi/ic_launcher.png", b"\x89PNGfake")

        meta = extract_apk_metadata(apk_file)
        assert meta.package_name == "sample_app"
        assert meta.icon_bytes == b"\x89PNGfake"
        assert meta.is_split is False

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            extract_apk_metadata("non_existent_file_path_12345.apk")


# ---------------------------------------------------------------------------
# Test SideloadManager
# ---------------------------------------------------------------------------

class TestSideloadManager:
    @pytest.fixture
    def mock_adb(self):
        adb = MagicMock(spec=ADB)
        adb.getprop.return_value = "34"
        return adb

    def test_install_single_apk_success(self, tmp_path, mock_adb):
        apk_path = tmp_path / "app.apk"
        apk_path.write_bytes(b"dummy apk")

        mock_adb._run.return_value = CommandResult(
            command=["adb", "install"],
            return_code=0,
            stdout="Success\n",
            stderr="",
            duration_ms=100,
        )

        mgr = SideloadManager(adb=mock_adb)
        flags = SideloadFlags(grant_permissions=True, allow_downgrade=True)
        ok, msg = mgr.install_apk(apk_path, flags=flags, serial="TEST_SERIAL")

        assert ok is True
        assert "Successfully installed" in msg
        mock_adb._run.assert_called_once()
        cmd_run = mock_adb._run.call_args[0][0]
        assert "install" in cmd_run
        assert "-g" in cmd_run
        assert "-d" in cmd_run
        # Android 14+ SDK 34 auto-bypass
        assert "--bypass-low-target-sdk-block" in cmd_run

    def test_install_single_apk_error_parsing(self, tmp_path, mock_adb):
        apk_path = tmp_path / "legacy_app.apk"
        apk_path.write_bytes(b"dummy apk")

        mock_adb._run.return_value = CommandResult(
            command=["adb", "install"],
            return_code=1,
            stdout="Failure [INSTALL_FAILED_DEPRECATED_SDK_VERSION: App target SDK 22 is lower than minimum 23]\n",
            stderr="",
            duration_ms=80,
        )

        mgr = SideloadManager(adb=mock_adb)
        ok, msg = mgr.install_apk(apk_path, serial="TEST_SERIAL")
        assert ok is False
        assert "Android 14+ blocked this legacy APK" in msg

    def test_install_split_bundle_success(self, tmp_path, mock_adb):
        bundle_path = tmp_path / "bundle.xapk"
        with zipfile.ZipFile(bundle_path, "w") as zf:
            zf.writestr("manifest.json", json.dumps({"package_name": "com.test.split"}))
            zf.writestr("base.apk", b"base apk data")
            zf.writestr("split.arm64.apk", b"split apk data")
            zf.writestr("main.1.com.test.split.obb", b"obb expansion data")

        mock_adb._run.return_value = CommandResult(
            command=["adb", "install-multiple"],
            return_code=0,
            stdout="Success\n",
            stderr="",
            duration_ms=250,
        )
        mock_adb.push.return_value = CommandResult(
            command=["adb", "push"],
            return_code=0,
            stdout="1 file pushed\n",
            stderr="",
            duration_ms=50,
        )

        mgr = SideloadManager(adb=mock_adb)
        logs = []
        ok, msg = mgr.install_split_bundle(
            bundle_path,
            serial="TEST_SERIAL",
            progress_cb=lambda s: logs.append(s),
        )

        assert ok is True
        assert "Successfully installed" in msg
        assert any("install-multiple" in l for l in logs)
        mock_adb._run.assert_called_once()
        cmd = mock_adb._run.call_args[0][0]
        assert "install-multiple" in cmd
        mock_adb.push.assert_called_once()

    def test_sideload_ota_zip(self, tmp_path, mock_adb):
        ota_zip = tmp_path / "update.zip"
        ota_zip.write_bytes(b"dummy ota content")

        mock_adb._run.return_value = CommandResult(
            command=["adb", "sideload"],
            return_code=0,
            stdout="serving: 'update.zip'  (~48%)\nserving: 'update.zip'  (~100%)\nTotal xfer: 1.00x\n",
            stderr="",
            duration_ms=500,
        )

        mgr = SideloadManager(adb=mock_adb)
        progress_calls = []
        ok, msg = mgr.sideload_ota_zip(
            ota_zip,
            serial="TEST_SERIAL",
            progress_cb=lambda pct, st: progress_calls.append((pct, st)),
        )

        assert ok is True
        assert "Successfully sideloaded" in msg
        assert any(p[0] == 100 for p in progress_calls)

    def test_list_installed_packages(self, mock_adb):
        mock_adb.shell.side_effect = [
            # pm list packages -3 -f
            CommandResult(
                command=["shell"],
                return_code=0,
                stdout="package:/data/app/~~a/com.test.one-b/base.apk=com.test.one\npackage:/data/app/~~c/com.test.two-d/base.apk=com.test.two\n",
                stderr="",
                duration_ms=20,
            ),
            # pm list packages -d
            CommandResult(
                command=["shell"],
                return_code=0,
                stdout="package:com.test.two\n",
                stderr="",
                duration_ms=10,
            ),
        ]

        mgr = SideloadManager(adb=mock_adb)
        pkgs = mgr.list_installed_packages(serial="TEST_SERIAL", filter_type="3rd_party")

        assert len(pkgs) == 2
        p1 = next(p for p in pkgs if p.package_name == "com.test.one")
        assert p1.is_enabled is True
        assert p1.category == "user"

        p2 = next(p for p in pkgs if p.package_name == "com.test.two")
        assert p2.is_enabled is False
        assert p2.category == "disabled"

    def test_manage_package_actions(self, tmp_path, mock_adb):
        mgr = SideloadManager(adb=mock_adb)

        # 1. Clear data
        mock_adb.shell.return_value = CommandResult(command=[], return_code=0, stdout="Success\n", stderr="", duration_ms=10)
        ok, msg = mgr.manage_package("com.test.app", "clear", serial="SERIAL")
        assert ok is True
        assert "Cleared cache and data" in msg

        # 2. Force stop
        mock_adb.shell.return_value = CommandResult(command=[], return_code=0, stdout="", stderr="", duration_ms=10)
        ok, msg = mgr.manage_package("com.test.app", "force_stop", serial="SERIAL")
        assert ok is True
        assert "Force-stopped" in msg

        # 3. Disable
        mock_adb.shell.return_value = CommandResult(command=[], return_code=0, stdout="Package com.test.app new state: disabled-user\n", stderr="", duration_ms=10)
        ok, msg = mgr.manage_package("com.test.app", "disable", serial="SERIAL")
        assert ok is True
        assert "Disabled" in msg

        # 4. Enable
        mock_adb.shell.return_value = CommandResult(command=[], return_code=0, stdout="Package com.test.app new state: enabled\n", stderr="", duration_ms=10)
        ok, msg = mgr.manage_package("com.test.app", "enable", serial="SERIAL")
        assert ok is True
        assert "Re-enabled" in msg

        # 5. Uninstall
        mock_adb.shell.return_value = CommandResult(command=[], return_code=0, stdout="Success\n", stderr="", duration_ms=10)
        ok, msg = mgr.manage_package("com.test.app", "uninstall", serial="SERIAL")
        assert ok is True
        assert "Uninstalled" in msg

        # 6. Pull APK to PC
        mock_adb.shell.return_value = CommandResult(command=[], return_code=0, stdout="package:/data/app/base.apk\n", stderr="", duration_ms=10)
        mock_adb.pull.return_value = CommandResult(command=[], return_code=0, stdout="1 file pulled", stderr="", duration_ms=20)
        ok, msg = mgr.manage_package("com.test.app", "pull", serial="SERIAL", dest_dir=tmp_path)
        assert ok is True
        assert "Extracted APK to" in msg


# ---------------------------------------------------------------------------
# Test SideloadScreen UI
# ---------------------------------------------------------------------------

class TestSideloadScreenUI:
    def test_screen_initialization_and_device_load(self, qapp):
        adb = MagicMock(spec=ADB)
        adb.getprop.return_value = "34"

        screen = SideloadScreen(adb=adb)
        assert screen._tabs.count() == 3

        # Simulate device connection
        dev = DeviceInfo(serial="DEV_123", mode="device", model="Pixel 8 Pro", brand="Google")
        screen.load_for_device(dev)

        assert "DEV_123" in screen._dev_chip.text() or "Pixel 8 Pro" in screen._dev_chip.text()
        assert screen._chk_bypass_low_sdk.isChecked() is True

    def test_file_selection_updates_ui(self, qapp, tmp_path):
        adb = MagicMock(spec=ADB)
        screen = SideloadScreen(adb=adb)

        dev = DeviceInfo(serial="DEV_123", mode="device", model="Galaxy S24", brand="Samsung")
        screen.load_for_device(dev)

        apk_path = tmp_path / "com.example.hello.apk"
        with zipfile.ZipFile(apk_path, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake xml")

        screen._on_file_selected(str(apk_path))

        assert not screen._meta_card.isHidden()
        assert "com.example.hello" in screen._meta_pkg_lbl.text()
        assert screen._btn_install.isEnabled() is True

    def test_theme_toggle_applies_cleanly(self, qapp):
        adb = MagicMock(spec=ADB)
        screen = SideloadScreen(adb=adb)

        screen.apply_theme("light")
        assert screen._current_theme == "light"
        screen.apply_theme("dark")
        assert screen._current_theme == "dark"
