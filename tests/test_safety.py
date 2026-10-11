"""
Unit tests — Safety Engine.
"""

from pathlib import Path
import pytest

from flashdock.core.device import DeviceInfo
from flashdock.core.safety import SafetyCheckResult, SafetyEngine, ScriptWarning


class TestDeviceMatch:
    def test_no_device_blocked(self):
        res = SafetyEngine.check_device_match(None, target_codename="cheetah")
        assert res.is_blocked is True
        assert "No device" in res.message

    def test_matching_device_passes(self):
        device = DeviceInfo(brand="google", model="Pixel 7 Pro", device="cheetah", mode="system")
        res = SafetyEngine.check_device_match(device, target_codename="cheetah", target_model="Pixel 7 Pro", target_brand="google")
        assert res.passed is True
        assert res.level == "ok"

    def test_codename_mismatch_blocks(self):
        device = DeviceInfo(brand="google", model="Pixel 7 Pro", device="cheetah", mode="system")
        res = SafetyEngine.check_device_match(device, target_codename="oriole")
        assert res.is_blocked is True
        assert "oriole" in res.message
        assert "cheetah" in res.message

    def test_brand_mismatch_blocks(self):
        device = DeviceInfo(brand="google", model="Pixel 7", device="panther", mode="system")
        res = SafetyEngine.check_device_match(device, target_brand="samsung")
        assert res.is_blocked is True
        assert "Brand mismatch" in res.message


class TestChecksum:
    def test_calculate_and_verify_hash(self, tmp_path: Path):
        test_file = tmp_path / "boot.img"
        test_file.write_bytes(b"ANDROID!dummy_kernel_data")

        sha = SafetyEngine.calculate_hash(test_file, algorithm="sha256")
        assert len(sha) == 64

        # Verify matching
        res = SafetyEngine.verify_checksum(test_file, sha, algorithm="sha256")
        assert res.passed is True
        assert res.level == "ok"

        # Verify mismatch
        bad_res = SafetyEngine.verify_checksum(test_file, "0" * 64, algorithm="sha256")
        assert bad_res.is_blocked is True
        assert "mismatch" in bad_res.message.lower()

    def test_missing_file_blocks(self, tmp_path: Path):
        missing = tmp_path / "nonexistent.img"
        res = SafetyEngine.verify_checksum(missing, "abc")
        assert res.is_blocked is True
        assert "not found" in res.message.lower()

    def test_empty_expected_hash_warns(self, tmp_path: Path):
        test_file = tmp_path / "file.img"
        test_file.write_text("content")
        res = SafetyEngine.verify_checksum(test_file, "")
        assert res.level == "warning"
        assert res.passed is False


class TestBatteryGuard:
    def test_battery_above_threshold_passes(self):
        res = SafetyEngine.check_battery(80)
        assert res.passed is True
        assert res.level == "ok"

    def test_battery_below_threshold_blocks(self):
        res = SafetyEngine.check_battery(45)
        assert res.is_blocked is True
        assert "below safe threshold" in res.message

    def test_battery_unknown_warns(self):
        res = SafetyEngine.check_battery(None)
        assert res.passed is True
        assert res.level == "warning"


class TestAntiRollback:
    def test_downgrade_blocked(self):
        res = SafetyEngine.check_anti_rollback(current_rollback_index=3, target_rollback_index=1)
        assert res.is_blocked is True
        assert "ANTI-ROLLBACK VIOLATION" in res.message

    def test_equal_or_upgrade_allowed(self):
        res1 = SafetyEngine.check_anti_rollback(current_rollback_index=2, target_rollback_index=2)
        assert res1.passed is True
        res2 = SafetyEngine.check_anti_rollback(current_rollback_index=2, target_rollback_index=3)
        assert res2.passed is True

    def test_unreported_arb_passes(self):
        res = SafetyEngine.check_anti_rollback(None, None)
        assert res.passed is True


class TestVendorScriptInspector:
    def test_detects_erase_userdata(self):
        script = (
            "fastboot flash boot boot.img\n"
            "fastboot erase userdata\n"
            "fastboot reboot\n"
        )
        warnings = SafetyEngine.inspect_vendor_script(script_content=script)
        assert len(warnings) == 2
        userdata_warn = next(w for w in warnings if "userdata" in w.command)
        assert userdata_warn.risk_level == "critical"
        reboot_warn = next(w for w in warnings if "reboot" in w.command)
        assert reboot_warn.risk_level == "info"

    def test_detects_lock_commands(self):
        script = (
            "# Flash script\n"
            "fastboot flash system system.img\n"
            "fastboot oem lock\n"
        )
        warnings = SafetyEngine.inspect_vendor_script(script_content=script)
        assert len(warnings) == 1
        assert warnings[0].risk_level == "critical"
        assert "Relocks" in warnings[0].description


class TestTypedConfirmation:
    def test_destructive_actions(self):
        assert SafetyEngine.is_destructive_action("format_userdata") is True
        assert SafetyEngine.is_destructive_action("unlock_bootloader") is True
        assert SafetyEngine.is_destructive_action("restore_partition") is True
        assert SafetyEngine.is_destructive_action("read_props") is False

    def test_expected_confirmation_word(self):
        assert SafetyEngine.expected_confirmation_word() == "FLASH"
