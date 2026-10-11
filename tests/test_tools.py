"""
Unit tests — ADB wrapper, Fastboot wrapper, and subprocess runner.
"""

from unittest.mock import MagicMock, patch

import pytest

from flashdock.tools.runner import CommandResult, run_command, is_flash_locked
from flashdock.tools.adb import ADB, ADBDevice
from flashdock.tools.fastboot import Fastboot, FastbootDevice


# ===================================================================
# Runner tests
# ===================================================================

class TestCommandResult:
    def test_success_when_rc_zero(self):
        r = CommandResult(command=["echo"], return_code=0, stdout="hi",
                          stderr="", duration_ms=10)
        assert r.success is True

    def test_failure_when_rc_nonzero(self):
        r = CommandResult(command=["fail"], return_code=1, stdout="",
                          stderr="err", duration_ms=5)
        assert r.success is False

    def test_failure_when_timed_out(self):
        r = CommandResult(command=["slow"], return_code=0, stdout="",
                          stderr="", duration_ms=0, timed_out=True)
        assert r.success is False

    def test_output_combines(self):
        r = CommandResult(command=["x"], return_code=0, stdout="out",
                          stderr="err", duration_ms=0)
        assert "out" in r.output
        assert "err" in r.output

    def test_command_str(self):
        r = CommandResult(command=["adb", "devices"], return_code=0,
                          stdout="", stderr="", duration_ms=0)
        assert r.command_str == "adb devices"


class TestRunCommandDryRun:
    def test_dry_run_does_not_execute(self):
        r = run_command(["echo", "hello"], dry_run=True, action_name="test")
        assert r.dry_run is True
        assert r.success is True
        assert "DRY RUN" in r.stdout

    def test_dry_run_logs_action(self):
        from flashdock.logger import action_log
        before = len(action_log.records)
        run_command(["test_cmd"], dry_run=True, action_name="dry_test")
        assert len(action_log.records) > before


class TestFlashLock:
    def test_initially_unlocked(self):
        assert is_flash_locked() is False


# ===================================================================
# ADB tests
# ===================================================================

class TestADBDevice:
    def test_is_ready(self):
        d = ADBDevice(serial="X", state="device")
        assert d.is_ready is True
        assert d.is_unauthorized is False

    def test_is_unauthorized(self):
        d = ADBDevice(serial="X", state="unauthorized")
        assert d.is_unauthorized is True
        assert d.is_ready is False

    def test_is_recovery(self):
        d = ADBDevice(serial="X", state="recovery")
        assert d.is_recovery is True


class TestADBBinarySearch:
    def test_no_binary_marks_unavailable(self):
        with patch("flashdock.tools.adb.ADB._find_binary", return_value=None):
            adb = ADB()
            assert adb.available is False

    def test_explicit_binary(self):
        adb = ADB(binary="/fake/adb.exe")
        assert adb.available is True
        assert adb.binary_path == "/fake/adb.exe"


class TestADBDeviceParsing:
    """Test that devices() parses adb output correctly."""

    @patch("flashdock.tools.adb.run_command")
    def test_parses_device_line(self, mock_run):
        mock_run.return_value = CommandResult(
            command=["adb", "devices", "-l"],
            return_code=0,
            stdout=(
                "List of devices attached\n"
                "ZY22FV6BKR             device usb:1-3 product:cheetah model:Pixel_7_Pro device:cheetah transport_id:1\n"
                "192.168.1.42:5555      unauthorized\n"
            ),
            stderr="",
            duration_ms=10,
        )
        adb = ADB(binary="/fake/adb")
        devs = adb.devices()
        assert len(devs) == 2

        assert devs[0].serial == "ZY22FV6BKR"
        assert devs[0].state == "device"
        assert devs[0].model == "Pixel_7_Pro"
        assert devs[0].device == "cheetah"

        assert devs[1].serial == "192.168.1.42:5555"
        assert devs[1].state == "unauthorized"


class TestADBDryRun:
    def test_dry_run_returns_without_executing(self):
        adb = ADB(binary="/fake/adb", dry_run=True)
        res = adb.shell("echo hi", serial="TEST")
        assert res.dry_run is True


class TestADBEnvironment:
    @patch("flashdock.tools.adb.run_command")
    def test_uses_writable_private_android_home(self, mock_run):
        mock_run.return_value = CommandResult(
            command=["adb", "devices", "-l"],
            return_code=0,
            stdout="List of devices attached\n",
            stderr="",
            duration_ms=1,
        )
        ADB(binary="/fake/adb").devices()

        env = mock_run.call_args.kwargs["env"]
        assert env["ANDROID_SDK_HOME"].endswith("data\\android")
        assert env["ANDROID_USER_HOME"] == env["ANDROID_SDK_HOME"]
        assert env["USERPROFILE"] == env["ANDROID_SDK_HOME"]


# ===================================================================
# Fastboot tests
# ===================================================================

class TestFastbootDevice:
    def test_fields(self):
        d = FastbootDevice(serial="ABC", mode="fastboot")
        assert d.serial == "ABC"
        assert d.mode == "fastboot"


class TestFastbootParsing:
    @patch("flashdock.tools.fastboot.run_command")
    def test_parses_device_list(self, mock_run):
        mock_run.return_value = CommandResult(
            command=["fastboot", "devices"],
            return_code=0,
            stdout="ZY22FV6BKR\tfastboot\nABC123\tfastbootd\n",
            stderr="",
            duration_ms=5,
        )
        fb = Fastboot(binary="/fake/fb")
        devs = fb.devices()
        assert len(devs) == 2
        assert devs[0].serial == "ZY22FV6BKR"
        assert devs[0].mode == "fastboot"
        assert devs[1].mode == "fastbootd"

    @patch("flashdock.tools.fastboot.run_command")
    def test_getvar(self, mock_run):
        mock_run.return_value = CommandResult(
            command=["fastboot", "getvar", "unlocked"],
            return_code=0,
            stdout="",
            stderr="unlocked: yes\nFinished. Total time: 0.001s",
            duration_ms=5,
        )
        fb = Fastboot(binary="/fake/fb")
        val = fb.getvar("unlocked", serial="X")
        assert val == "yes"

    @patch("flashdock.tools.fastboot.run_command")
    def test_getvar_all(self, mock_run):
        mock_run.return_value = CommandResult(
            command=["fastboot", "getvar", "all"],
            return_code=0,
            stdout="",
            stderr=(
                "product: cheetah\n"
                "unlocked: yes\n"
                "secure: yes\n"
                "slot-count: 2\n"
                "current-slot: a\n"
                "(bootloader) Finished. Total time: 0.005s\n"
            ),
            duration_ms=15,
        )
        fb = Fastboot(binary="/fake/fb")
        vs = fb.getvar_all()
        assert vs["product"] == "cheetah"
        assert vs["unlocked"] == "yes"
        assert vs["slot-count"] == "2"
