"""
Unit tests — Logger module.
"""

import logging
import tempfile
from pathlib import Path

from flashdock.logger import (
    ActionLog,
    ActionRecord,
    get_logger,
    mask_serials,
    setup_logging,
)


class TestMaskSerials:
    """Verify that serial-number masking works correctly."""

    def test_hex_serial(self):
        assert "[SERIAL]" in mask_serials("Device ZY22FV6BKR connected")

    def test_ip_serial(self):
        assert "[SERIAL]" in mask_serials("adb connect 192.168.1.42:5555")

    def test_emulator_serial(self):
        assert "[SERIAL]" in mask_serials("emulator-5554 device")

    def test_no_false_positive_short(self):
        # Short strings like "OK" should NOT be masked
        result = mask_serials("All OK")
        assert "OK" in result

    def test_preserves_normal_text(self):
        text = "Flashing boot partition"
        assert mask_serials(text) == text


class TestActionRecord:
    def test_to_dict_has_all_fields(self):
        rec = ActionRecord(
            action="flash_boot",
            command="fastboot flash boot patched.img",
            device_serial="ZY22FV6BKR",
            result="success",
            output="Sending 'boot' (32768 KB)...",
            duration_ms=4200,
        )
        d = rec.to_dict()
        assert d["action"] == "flash_boot"
        assert d["device_serial"] == "ZY22FV6BKR"
        assert "timestamp" in d

    def test_to_masked_dict_hides_serial(self):
        rec = ActionRecord(
            action="flash",
            command="fastboot -s ZY22FV6BKR flash boot x.img",
            device_serial="ZY22FV6BKR",
        )
        d = rec.to_masked_dict()
        assert d["device_serial"] == "[SERIAL]"
        assert "ZY22FV6BKR" not in d["command"]


class TestActionLog:
    def test_record_and_export(self):
        al = ActionLog()
        al.record(ActionRecord("test", "echo hi", result="ok"))
        assert len(al.records) == 1
        masked = al.export_masked()
        assert len(masked) == 1
        assert masked[0]["action"] == "test"


class TestGetLogger:
    def test_returns_child_logger(self):
        lg = get_logger("test_module")
        assert lg.name == "flashdock.test_module"

    def test_already_prefixed(self):
        lg = get_logger("flashdock.foo")
        assert lg.name == "flashdock.foo"


class TestSetupLogging:
    def test_returns_path(self):
        path = setup_logging()
        assert isinstance(path, Path)
        assert "flashdock_" in path.name
