"""
Tests for DriverManager enhancements: fuzzy scanning, zip extraction, and custom driver installation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import zipfile

import pytest

from flashdock.core.tools_manager import DriverManager, DEFAULT_DRIVERS


def test_driver_manager_fuzzy_scanning(tmp_path: Path):
    drivers_dir = tmp_path / "drivers"
    drivers_dir.mkdir(parents=True)

    # User placed a Samsung driver with an arbitrary filename containing 'samsung'
    custom_samsung_exe = drivers_dir / "my_custom_samsung_driver_v2.exe"
    custom_samsung_exe.write_text("fake samsung exe")

    mgr = DriverManager(drivers_dir=drivers_dir)
    pkg = mgr.get_driver("samsung_usb")
    assert pkg is not None
    assert pkg.is_downloaded is True
    assert pkg.local_path == custom_samsung_exe


def test_driver_manager_auto_extract_zip_on_install(tmp_path: Path):
    drivers_dir = tmp_path / "drivers"
    drivers_dir.mkdir(parents=True)

    # Create a real zip file containing an INF file
    zip_path = drivers_dir / "usb_driver_r13-windows.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("usb_driver/android_winusb.inf", "[Version]\nSignature=\"$Windows NT$\"")

    mgr = DriverManager(drivers_dir=drivers_dir)
    pkg = mgr.get_driver("google_usb")
    assert pkg is not None
    assert pkg.is_downloaded is True

    with patch.object(mgr, "_execute_pnputil_install", return_value=(True, "Installed INF successfully")) as mock_pnp:
        success, msg = mgr.install_driver("google_usb")
        assert success is True
        assert "Installed INF successfully" in msg
        assert mock_pnp.called
        # Check that it extracted the zip
        extracted_dir = drivers_dir / "google_usb"
        assert extracted_dir.exists()
        assert (extracted_dir / "usb_driver" / "android_winusb.inf").exists()


def test_driver_manager_install_custom_driver_file_inf(tmp_path: Path):
    drivers_dir = tmp_path / "drivers"
    drivers_dir.mkdir(parents=True)
    loose_inf = tmp_path / "custom_phone.inf"
    loose_inf.write_text("[Version]\nSignature=\"$Windows NT$\"")

    mgr = DriverManager(drivers_dir=drivers_dir)
    with patch.object(mgr, "_execute_pnputil_install", return_value=(True, "Custom INF Installed")) as mock_pnp:
        success, msg = mgr.install_custom_driver_file(loose_inf)
        assert success is True
        assert "Custom INF Installed" in msg
        mock_pnp.assert_called_once_with(loose_inf)
