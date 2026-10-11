"""
Unit tests — BootloopFixer engine.
"""

from unittest.mock import MagicMock, patch
import pytest

from flashdock.core.bootloop_fixer import BootloopFixer
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot


@pytest.fixture
def fixer():
    adb_mock = MagicMock(spec=ADB)
    adb_mock.available = True
    adb_mock.binary_path = "/path/to/adb"

    fb_mock = MagicMock(spec=Fastboot)
    fb_mock.available = True
    fb_mock.binary_path = "/path/to/fastboot"

    return BootloopFixer(adb=adb_mock, fastboot=fb_mock)


class TestBootloopFixer:
    def test_disable_root_modules_adb_success(self, fixer):
        mock_res = MagicMock()
        mock_res.stdout = "SUCCESS\n"
        mock_res.stderr = ""
        mock_res.returncode = 0

        with patch("subprocess.run", return_value=mock_res) as mock_run:
            success, msg = fixer.disable_root_modules_adb(serial="DEVICE123")

        assert success is True
        assert "kill-switch triggered" in msg
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-s" in cmd
        assert "DEVICE123" in cmd
        assert ".disable" in cmd[-1]

    def test_remove_root_modules_adb(self, fixer):
        mock_res = MagicMock()
        mock_res.stdout = "REMOVED\n"
        mock_res.stderr = ""
        mock_res.returncode = 0

        with patch("subprocess.run", return_value=mock_res):
            success, msg = fixer.remove_root_modules_adb()

        assert success is True
        assert "cleared" in msg

    def test_reboot_safe_mode(self, fixer):
        mock_res = MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", return_value=mock_res) as mock_run:
            success, msg = fixer.reboot_safe_mode(serial="SER_1")

        assert success is True
        assert "Safe Mode" in msg
        cmd = mock_run.call_args[0][0]
        assert "safemode" in cmd

    def test_get_current_fastboot_slot(self, fixer):
        mock_res = MagicMock()
        mock_res.stdout = "current-slot: _a\nFinished."
        mock_res.stderr = ""
        mock_res.returncode = 0

        with patch("subprocess.run", return_value=mock_res):
            slot = fixer.get_current_fastboot_slot()

        assert slot == "a"

    def test_switch_active_slot(self, fixer):
        mock_res = MagicMock(returncode=0, stdout="Setting current slot to 'b'... Finished.", stderr="")

        with patch("subprocess.run", return_value=mock_res) as mock_run:
            success, msg = fixer.switch_active_slot("b")

        assert success is True
        assert "switched active slot" in msg
        cmd = mock_run.call_args[0][0]
        assert "--set-active=b" in cmd

    def test_disable_verity_vbmeta(self, fixer):
        mock_res = MagicMock(returncode=0, stdout="Sending 'vbmeta' (4 KB)... Finished.", stderr="")

        with patch("subprocess.run", return_value=mock_res) as mock_run:
            success, msg = fixer.disable_verity_vbmeta("/path/vbmeta.img")

        assert success is True
        assert "verity and verification disabled" in msg
        cmd = mock_run.call_args[0][0]
        assert "--disable-verity" in cmd
        assert "--disable-verification" in cmd

    def test_erase_fastboot_cache(self, fixer):
        mock_res = MagicMock(returncode=0, stdout="Erasing 'cache'... Finished.", stderr="")

        with patch("subprocess.run", return_value=mock_res):
            success, msg = fixer.erase_fastboot_cache()

        assert success is True
        assert "erased successfully" in msg
