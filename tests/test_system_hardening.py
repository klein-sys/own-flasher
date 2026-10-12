"""
Unit and integration tests — System Hardening, Brick-Prevention, and Security Guard Overhaul.
Covers:
- Active Slot Desync Guard
- Boot Image Header Parsing (v0-v4) and Anti-Rollback (ARP) checks
- Pre-Flash Partition Integrity & Low Disk Space Abort (< 2 GB)
- Mid-Flash USB Disconnect Detection & Actionable Guidance
- Data Redaction (IMEI, MEID, Android ID, Serials, User Paths)
- Local Sanitized Crash Dumps
- Windows USB Selective Suspend Detection
- WinReg Resilient Enumeration
"""

from __future__ import annotations

import json
import os
import shutil
import struct
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from flashdock.constants import CRASHES_DIR
from flashdock.core.crash_reporter import write_crash_dump
from flashdock.logger import redact_sensitive_data
from flashdock.workers.device_monitor import (
    DeviceMonitorWorker,
    check_windows_usb_selective_suspend,
)
from flashdock.workers.flash_engine import (
    FlashEngineWorker,
    FlashOperationType,
    FlashTask,
    is_usb_disconnect_error,
    parse_boot_image_header,
    validate_active_slot,
)


# ===================================================================
# 1. Active Slot Desync Guard Tests
# ===================================================================

class TestActiveSlotDesyncGuard:
    def test_matching_slot_succeeds(self):
        fastboot = MagicMock()
        fastboot.get_var.return_value = "a"
        valid, token, err = validate_active_slot(fastboot, "dummy_serial", "a")
        assert valid is True
        assert token == "_a"
        assert not err

    def test_slot_prefix_underscore_normalized(self):
        fastboot = MagicMock()
        fastboot.get_var.return_value = "_b"
        valid, token, err = validate_active_slot(fastboot, "dummy_serial", "b")
        assert valid is True
        assert token == "_b"
        assert not err

    def test_slot_mismatch_fails_validation(self):
        fastboot = MagicMock()
        fastboot.get_var.return_value = "a"
        valid, token, err = validate_active_slot(fastboot, "dummy_serial", "b")
        assert valid is False
        assert token == "_a"
        assert "Active Slot Desync Detected" in err

    def test_empty_slot_on_slot_specific_partition_fails(self):
        fastboot = MagicMock()
        fastboot.get_var.return_value = ""
        valid, token, err = validate_active_slot(fastboot, "dummy_serial", "a")
        assert valid is False
        assert "ambiguous" in err.lower() or "slot" in err.lower()

    def test_force_override_allows_mismatch(self):
        fastboot = MagicMock()
        fastboot.get_var.return_value = "a"
        valid, token, err = validate_active_slot(fastboot, "dummy_serial", "b", force_override=True)
        assert valid is True
        assert token == "_b"

    def test_non_slot_partition_on_non_ab_device_succeeds(self):
        fastboot = MagicMock()
        fastboot.get_var.return_value = ""
        valid, token, err = validate_active_slot(fastboot, "dummy_serial", "")
        assert valid is True
        assert token == ""


# ===================================================================
# 2. Boot Image Header Parser & Anti-Rollback (ARP) Tests
# ===================================================================

class TestBootImageHeaderParser:
    def _create_mock_boot_v2(self, os_ver_int: int) -> bytes:
        # Magic: 8 bytes b"ANDROID!"
        # header_version at offset 40 (4 bytes uint32: 2)
        # os_version at offset 44 (4 bytes uint32)
        buf = bytearray(1024)
        buf[0:8] = b"ANDROID!"
        struct.pack_into("<I", buf, 40, 2)  # header_version 2
        struct.pack_into("<I", buf, 44, os_ver_int)
        return bytes(buf)

    def _create_mock_boot_v3(self, os_ver_int: int) -> bytes:
        # Magic: 8 bytes b"ANDROID!"
        # os_version at offset 16 (4 bytes uint32)
        # header_version at offset 40 (4 bytes uint32: 3)
        buf = bytearray(1024)
        buf[0:8] = b"ANDROID!"
        struct.pack_into("<I", buf, 16, os_ver_int)
        struct.pack_into("<I", buf, 40, 3)  # header_version 3
        return bytes(buf)

    def test_parse_boot_v2(self, tmp_path: Path):
        # OS Version: 14.0.0 (14 << 14 | 0 << 7 | 0 = 229376)
        # Patch Level: 2024-05 ((2024 - 2000) << 4 | 5 = 24 * 16 + 5 = 389)
        # Combined os_version: (229376 << 11) | 389 = 470089856 + 389 = 470090245
        os_combined = (14 << 25) | (24 << 4) | 5
        data = self._create_mock_boot_v2(os_combined)
        boot_file = tmp_path / "boot_v2.img"
        boot_file.write_bytes(data)

        info = parse_boot_image_header(boot_file)
        assert info["is_boot_image"] is True
        assert info["header_version"] == 2
        assert info["os_version"] == "14.0.0"
        assert info["patch_level"] == "2024-05"

    def test_parse_boot_v3(self, tmp_path: Path):
        # OS Version: 13.2.1
        # 13 << 14 | 2 << 7 | 1 = 212992 + 256 + 1 = 213249
        # Patch Level: 2023-11 ((23) << 4 | 11 = 379)
        os_combined = (213249 << 11) | 379
        data = self._create_mock_boot_v3(os_combined)
        boot_file = tmp_path / "boot_v3.img"
        boot_file.write_bytes(data)

        info = parse_boot_image_header(boot_file)
        assert info["is_boot_image"] is True
        assert info["header_version"] == 3
        assert info["os_version"] == "13.2.1"
        assert info["patch_level"] == "2023-11"

    def test_non_boot_image_returns_false(self, tmp_path: Path):
        corrupt_file = tmp_path / "corrupt.img"
        corrupt_file.write_bytes(b"INVALID_HEADER_DATA_NOT_ANDROID")
        info = parse_boot_image_header(corrupt_file)
        assert info["is_boot_image"] is False


# ===================================================================
# 3. Anti-Rollback (ARP) Worker Integration
# ===================================================================

class TestAntiRollbackWorkerProtection:
    def test_rollback_blocks_flash_when_guard_active(self, tmp_path: Path):
        # Create an older boot image (2022-01)
        os_combined = (12 << 25) | (22 << 4) | 1
        buf = bytearray(1024)
        buf[0:8] = b"ANDROID!"
        struct.pack_into("<I", buf, 40, 2)
        struct.pack_into("<I", buf, 44, os_combined)
        boot_file = tmp_path / "boot.img"
        boot_file.write_bytes(buf)

        task = FlashTask(
            operation=FlashOperationType.FLASH_PARTITION,
            partition="boot_a",
            file_path=boot_file,
            device_serial="DEVICE123",
            device_security_patch="2024-05",  # Newer on device
            block_on_arp_downgrade=True,
            allow_rollback=False,
            pre_backup_efs=False,
        )

        worker = FlashEngineWorker(task)
        messages: list[str] = []
        finished_results: list[tuple[bool, str]] = []
        worker.log_emitted.connect(lambda lvl, msg: messages.append(f"{lvl}: {msg}"))
        worker.flash_finished.connect(lambda ok, msg: finished_results.append((ok, msg)))

        with patch.object(worker.fastboot, "getvar", return_value="a"):
            worker.run()

        # Check that flash was rejected due to ARP Downgrade
        assert any("ANTI-ROLLBACK (ARP) WARNING" in m for m in messages)
        assert any(not ok for ok, _ in finished_results)
        assert any("Anti-Rollback" in msg for _, msg in finished_results)


# ===================================================================
# 4. Pre-Flash Calibration Backup & Low Disk Space Abort (< 2 GB)
# ===================================================================

class TestPreFlashPartitionIntegrity:
    def test_low_disk_space_aborts_backup(self, tmp_path: Path):
        task = FlashTask(
            operation=FlashOperationType.FLASH_PARTITION,
            partition="boot",
            file_path=tmp_path / "dummy.img",
            device_serial="DEVICE123",
            pre_backup_efs=True,
        )
        task.file_path.write_bytes(b"DATA")
        worker = FlashEngineWorker(task)

        # Mock shutil.disk_usage to return 500 MB (< 2 GB)
        mock_usage = MagicMock(free=500 * 1024 * 1024)
        with patch("shutil.disk_usage", return_value=mock_usage):
            with pytest.raises(RuntimeError, match="Insufficient disk space"):
                worker._perform_calibration_backup("DEVICE123")


# ===================================================================
# 5. Mid-Flash USB Disconnect Isolation
# ===================================================================

class TestUsbDisconnectIsolation:
    @pytest.mark.parametrize(
        "err_str",
        [
            "error: device 'ZY22FV6BKR' not found",
            "error: device offline",
            "fastboot: error: closed",
            "Device disconnected mid-transfer",
            "fastboot: error: command failed: device unauthorized",
        ],
    )
    def test_is_usb_disconnect_error_positive(self, err_str: str):
        assert is_usb_disconnect_error(err_str) is True

    def test_is_usb_disconnect_error_negative(self):
        assert is_usb_disconnect_error("Sending 'boot' (65536 KB)... OKAY") is False
        assert is_usb_disconnect_error("Writing 'boot'... OKAY") is False


# ===================================================================
# 6. Privacy & Strict Data Redaction
# ===================================================================

class TestPrivacyAndSecretMasking:
    def test_imei_redaction(self):
        text = "Device IMEI 860123456789012 verified."
        redacted = redact_sensitive_data(text)
        assert "860123456789012" not in redacted
        assert "[REDACTED_IMEI]" in redacted

    def test_meid_redaction(self):
        text = "MEID A100002A3B4C5D registered."
        redacted = redact_sensitive_data(text)
        assert "A100002A3B4C5D" not in redacted
        assert "[REDACTED_MEID]" in redacted

    def test_android_id_redaction(self):
        text = "device_id: 4a2b3c4d5e6f7a8b reported."
        redacted = redact_sensitive_data(text)
        assert "4a2b3c4d5e6f7a8b" not in redacted
        assert "[REDACTED_ANDROID_ID]" in redacted

    def test_windows_user_path_redaction(self):
        text = r"Loading firmware from C:\Users\JohnDoe\Downloads\rom.zip"
        redacted = redact_sensitive_data(text)
        assert "JohnDoe" not in redacted
        assert r"C:\Users\[USER_DIR]" in redacted

    def test_crash_dump_sanitized_json(self):
        test_content = r"Exception in C:\Users\Developer\repo\main.py with IMEI 860123456789012"
        dump_path = write_crash_dump(test_content)
        assert dump_path.exists()

        # Verify json bundle was generated in CRASHES_DIR
        json_files = list(CRASHES_DIR.glob("crash_*.json"))
        assert len(json_files) > 0

        latest_json = sorted(json_files, key=lambda p: p.stat().st_mtime)[-1]
        data = json.loads(latest_json.read_text(encoding="utf-8"))
        assert "Developer" not in data["report"]
        assert "860123456789012" not in data["report"]
        assert "[REDACTED_IMEI]" in data["report"]
        assert "[USER_DIR]" in data["report"]

        # Cleanup
        dump_path.unlink(missing_ok=True)
        latest_json.unlink(missing_ok=True)


# ===================================================================
# 7. Windows USB Selective Suspend & WinReg Protection
# ===================================================================

class TestWindowsResilience:
    def test_check_windows_usb_selective_suspend_safe_call(self):
        is_enabled, advice = check_windows_usb_selective_suspend()
        assert isinstance(is_enabled, bool)
        assert isinstance(advice, str)

    def test_winreg_enumeration_protected_against_errors(self):
        worker = DeviceMonitorWorker()
        with patch("winreg.OpenKey", side_effect=PermissionError("Access Denied")):
            ports = worker._scan_windows_serial_ports()
            assert isinstance(ports, list)
            assert len(ports) == 0

            devs = worker._scan_windows_usb_devices()
            assert isinstance(devs, list)
            assert len(devs) == 0
