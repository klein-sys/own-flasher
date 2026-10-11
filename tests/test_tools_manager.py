"""
Unit tests — Tools, Drivers & Firmware Manager (Phase 12 Core).
"""

from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch
import zipfile
import pytest

from flashdock.core.device import DeviceInfo
from flashdock.core.tools_manager import (
    DriverManager,
    DriverPackage,
    FirmwareFinder,
    FirmwareRepo,
    PlatformToolsManager,
    ToolInfo,
)
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot


class TestPlatformToolsManager:
    def test_check_status_when_binaries_exist(self, tmp_path):
        adb_mock = MagicMock(spec=ADB)
        adb_file = tmp_path / "adb.exe"
        adb_file.write_text("dummy adb")
        adb_mock.binary_path = adb_file

        fb_mock = MagicMock(spec=Fastboot)
        fb_file = tmp_path / "fastboot.exe"
        fb_file.write_text("dummy fastboot")
        fb_mock.binary_path = fb_file

        mgr = PlatformToolsManager(adb=adb_mock, fastboot=fb_mock)

        with patch.object(mgr, "get_adb_version", return_value="37.0.1"), \
             patch.object(mgr, "get_fastboot_version", return_value="35.0.2"):
            status = mgr.check_status()

        assert status["adb"].status == "ready"
        assert status["adb"].version == "37.0.1"
        assert status["fastboot"].status == "ready"
        assert status["fastboot"].version == "35.0.2"

    def test_check_status_when_binaries_missing(self):
        adb_mock = MagicMock(spec=ADB)
        adb_mock.binary_path = None

        fb_mock = MagicMock(spec=Fastboot)
        fb_mock.binary_path = None

        mgr = PlatformToolsManager(adb=adb_mock, fastboot=fb_mock)
        status = mgr.check_status()

        assert status["adb"].status == "missing"
        assert status["fastboot"].status == "missing"

    def test_get_adb_version_parsing(self, tmp_path):
        adb_mock = MagicMock(spec=ADB)
        adb_file = tmp_path / "adb.exe"
        adb_file.write_text("fake")
        adb_mock.binary_path = adb_file

        mgr = PlatformToolsManager(adb=adb_mock)

        mock_res = MagicMock()
        mock_res.stdout = "Android Debug Bridge version 1.0.41\nVersion 35.0.1-11580240\n"
        mock_res.stderr = ""
        mock_res.returncode = 0

        with patch("subprocess.run", return_value=mock_res):
            ver = mgr.get_adb_version()
        assert ver == "1.0.41"

    def test_restart_adb_daemon(self, tmp_path):
        adb_mock = MagicMock(spec=ADB)
        adb_file = tmp_path / "adb.exe"
        adb_file.write_text("fake")
        adb_mock.binary_path = adb_file

        mgr = PlatformToolsManager(adb=adb_mock)

        mock_kill = MagicMock(returncode=0)
        mock_start = MagicMock(returncode=0, stdout="* daemon started successfully *", stderr="")

        with patch("subprocess.run", side_effect=[mock_kill, mock_start]):
            success, msg = mgr.restart_adb_daemon()

        assert success is True
        assert "successfully" in msg

    def test_download_and_install_platform_tools_mock(self, tmp_path):
        # Create a mock zip
        zip_file = tmp_path / "test_pt.zip"
        pt_dir = tmp_path / "platform-tools"
        pt_dir.mkdir(parents=True, exist_ok=True)
        (pt_dir / "adb.exe").write_text("mock adb exe")
        (pt_dir / "fastboot.exe").write_text("mock fb exe")

        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.write(pt_dir / "adb.exe", "platform-tools/adb.exe")
            zf.write(pt_dir / "fastboot.exe", "platform-tools/fastboot.exe")

        mgr = PlatformToolsManager()
        dest_dir = tmp_path / "installed_pt"

        # Mock urllib download to just copy test_pt.zip to target
        def mock_urlretrieve(req, *args, **kwargs):
            mock_resp = MagicMock()
            mock_resp.headers = {"Content-Length": str(zip_file.stat().st_size)}
            mock_resp.read.side_effect = [zip_file.read_bytes(), b""]
            mock_resp.__enter__.return_value = mock_resp
            return mock_resp

        with patch("urllib.request.urlopen", side_effect=mock_urlretrieve):
            success, msg = mgr.download_and_install_platform_tools(target_dir=dest_dir)

        assert success is True
        assert (dest_dir / "adb.exe").exists()
        assert (dest_dir / "fastboot.exe").exists()
        assert mgr.adb.binary_path == str(dest_dir / "adb.exe")
        assert mgr.fastboot.binary_path == str(dest_dir / "fastboot.exe")


class TestDriverManager:
    def test_catalog_and_scanning(self, tmp_path):
        mgr = DriverManager(drivers_dir=tmp_path)
        drivers = mgr.get_all_drivers()
        assert len(drivers) >= 6

        # Check default state
        g_drv = mgr.get_driver("google_usb")
        assert g_drv is not None
        assert g_drv.is_downloaded is False

        # Place a dummy driver file
        (tmp_path / g_drv.filename).write_text("dummy driver archive")
        mgr.scan_local_drivers()

        updated_g = mgr.get_driver("google_usb")
        assert updated_g.is_downloaded is True

    def test_install_inf_driver_pnputil_called(self, tmp_path):
        mgr = DriverManager(drivers_dir=tmp_path)
        g_drv = mgr.get_driver("google_usb")

        # Create simulated extracted folder with inf
        drv_folder = tmp_path / g_drv.id
        drv_folder.mkdir(parents=True, exist_ok=True)
        inf_file = drv_folder / "android_winusb.inf"
        inf_file.write_text("; Dummy INF")

        mgr.scan_local_drivers()

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "Driver package added successfully."
        mock_proc.stderr = ""

        with patch("subprocess.run", return_value=mock_proc) as mock_run:
            success, msg = mgr.install_driver("google_usb")

        assert success is True
        assert "Successfully installed" in msg
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "pnputil" in cmd
        assert "/add-driver" in cmd

    def test_pnp_diagnostics_parsing(self):
        mgr = DriverManager()
        sample_json = (
            '[{"InstanceId": "USB\\\\VID_18D1&PID_4EE2\\\\SERIAL123", '
            '"FriendlyName": "Android ADB Interface", "Status": "Error", "Problem": "CM_PROB_FAILED_INSTALL"}]'
        )

        mock_res = MagicMock()
        mock_res.stdout = sample_json
        mock_res.returncode = 0

        with patch("subprocess.run", return_value=mock_res), \
             patch("sys.platform", "win32"):
            issues = mgr.diagnose_pnp_devices()

        assert len(issues) == 1
        assert issues[0]["status"] == "Error"
        assert issues[0]["recommended_driver"] == "Google USB Driver"


class TestFirmwareFinder:
    def test_category_filtering(self):
        finder = FirmwareFinder()
        all_repos = finder.get_repositories("all")
        assert len(all_repos) >= 8

        factories = finder.get_repositories("factory")
        assert len(factories) >= 4
        assert all(r.category == "factory" for r in factories)

        gsis = finder.get_repositories("gsi")
        assert len(gsis) >= 2
        assert all(r.category == "gsi" for r in gsis)

        recs = finder.get_repositories("recovery")
        assert len(recs) >= 2
        assert all(r.category == "recovery" for r in recs)

    def test_recommendations_for_device(self):
        finder = FirmwareFinder()

        # Google device
        dev_pixel = DeviceInfo(serial="PIXEL_1", brand="Google", model="Pixel 7", device="panther", mode="adb")
        pixel_recs = finder.get_recommendations_for_device(dev_pixel)
        assert len(pixel_recs) > 0
        # First repo should be Google Factory
        assert pixel_recs[0].brand.lower() == "google"

        # Xiaomi device
        dev_xiaomi = DeviceInfo(serial="MI_1", brand="Xiaomi", model="POCO F3", device="alioth", mode="adb")
        mi_recs = finder.get_recommendations_for_device(dev_xiaomi)
        assert len(mi_recs) > 0
        assert mi_recs[0].brand.lower() == "xiaomi"
