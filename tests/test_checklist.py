"""
Unit tests — Checklist engine.
"""

from unittest.mock import MagicMock

import pytest

from flashdock.core.checklist import (
    CheckItem,
    ChecklistResult,
    ChecklistRunner,
    CheckStatus,
)
from flashdock.core.device import DeviceInfo
from flashdock.tools.adb import ADB


# ===================================================================
# CheckItem / ChecklistResult model tests
# ===================================================================

class TestCheckItem:
    def test_pass_is_ok(self):
        item = CheckItem(category="test", label="x", status=CheckStatus.PASS)
        assert item.is_ok is True
        assert item.icon == "✅"

    def test_fail_is_not_ok(self):
        item = CheckItem(category="test", label="x", status=CheckStatus.FAIL)
        assert item.is_ok is False
        assert item.icon == "❌"

    def test_warn_icon(self):
        item = CheckItem(category="test", label="x", status=CheckStatus.WARN)
        assert item.icon == "⚠️"

    def test_skip_is_ok(self):
        item = CheckItem(category="test", label="x", status=CheckStatus.SKIP)
        assert item.is_ok is True

    def test_info_is_ok(self):
        item = CheckItem(category="test", label="x", status=CheckStatus.INFO)
        assert item.is_ok is True


class TestChecklistResult:
    def test_counts(self):
        result = ChecklistResult(items=[
            CheckItem(category="a", label="p", status=CheckStatus.PASS),
            CheckItem(category="a", label="f", status=CheckStatus.FAIL),
            CheckItem(category="a", label="w", status=CheckStatus.WARN),
            CheckItem(category="a", label="s", status=CheckStatus.SKIP),
        ])
        assert result.pass_count == 1
        assert result.fail_count == 1
        assert result.warn_count == 1
        assert result.total == 4
        assert result.all_passed is False

    def test_all_passed(self):
        result = ChecklistResult(items=[
            CheckItem(category="a", label="p", status=CheckStatus.PASS),
            CheckItem(category="a", label="i", status=CheckStatus.INFO),
        ])
        assert result.all_passed is True

    def test_summary_format(self):
        result = ChecklistResult(items=[
            CheckItem(category="a", label="p", status=CheckStatus.PASS),
        ])
        assert "1 passed" in result.summary


# ===================================================================
# ChecklistRunner tests — no device
# ===================================================================

class TestChecklistRunnerNoDevice:
    def test_no_device_fails_connection_check(self):
        adb = MagicMock(spec=ADB)
        adb.available = False
        runner = ChecklistRunner(adb=adb, device=None)
        result = runner.run()

        # Should have a FAIL for "Device connected via USB"
        conn_items = [i for i in result.items if "connected" in i.label.lower()]
        assert len(conn_items) >= 1
        assert conn_items[0].status == CheckStatus.FAIL

    def test_no_device_generates_skipped_settings(self):
        adb = MagicMock(spec=ADB)
        adb.available = False
        runner = ChecklistRunner(adb=adb, device=None)
        result = runner.run()

        # Many phone settings should be SKIP
        skip_items = [i for i in result.items
                      if i.category == "phone_settings" and i.status == CheckStatus.SKIP]
        assert len(skip_items) >= 3

    def test_adb_not_found_fails_file_check(self):
        adb = MagicMock(spec=ADB)
        adb.available = False
        runner = ChecklistRunner(adb=adb, device=None)
        result = runner.run()

        adb_items = [i for i in result.items if "adb" in i.label.lower()]
        assert len(adb_items) >= 1
        assert adb_items[0].status == CheckStatus.FAIL


# ===================================================================
# ChecklistRunner tests — with device
# ===================================================================

class TestChecklistRunnerWithDevice:
    def _make_device(self, **kwargs) -> DeviceInfo:
        defaults = dict(
            serial="TEST123",
            brand="google",
            model="Pixel 7",
            device="panther",
            android_version="14",
            security_patch="2024-01-05",
            mode="system",
            bootloader_state="unlocked",
            oem_unlock_allowed="1",
            battery_level=85,
            encryption_state="encrypted",
        )
        defaults.update(kwargs)
        return DeviceInfo(**defaults)

    def _make_runner(self, device: DeviceInfo) -> ChecklistRunner:
        adb = MagicMock(spec=ADB)
        adb.available = True
        adb.version.return_value = "35.0.2"
        return ChecklistRunner(adb=adb, device=device)

    def test_connected_device_passes(self):
        device = self._make_device()
        runner = self._make_runner(device)
        result = runner.run()

        conn_items = [i for i in result.items if "connected" in i.label.lower()]
        assert conn_items[0].status == CheckStatus.PASS

    def test_usb_debugging_passes_in_system(self):
        device = self._make_device(mode="system")
        runner = self._make_runner(device)
        result = runner.run()

        debug_items = [i for i in result.items if "debugging" in i.label.lower()]
        assert debug_items[0].status == CheckStatus.PASS

    def test_oem_unlock_allowed_passes(self):
        device = self._make_device(oem_unlock_allowed="1")
        runner = self._make_runner(device)
        result = runner.run()

        oem_items = [i for i in result.items if "oem" in i.label.lower()]
        assert oem_items[0].status == CheckStatus.PASS

    def test_oem_unlock_blocked_fails(self):
        device = self._make_device(oem_unlock_allowed="0")
        runner = self._make_runner(device)
        result = runner.run()

        oem_items = [i for i in result.items if "oem" in i.label.lower()]
        assert oem_items[0].status == CheckStatus.FAIL
        assert oem_items[0].fix_hint  # Should have a fix hint

    def test_battery_above_60_passes(self):
        device = self._make_device(battery_level=85)
        runner = self._make_runner(device)
        result = runner.run()

        batt_items = [i for i in result.items if "battery" in i.label.lower()]
        assert batt_items[0].status == CheckStatus.PASS

    def test_battery_below_60_fails(self):
        device = self._make_device(battery_level=42)
        runner = self._make_runner(device)
        result = runner.run()

        batt_items = [i for i in result.items if "battery" in i.label.lower()]
        assert batt_items[0].status == CheckStatus.FAIL

    def test_unauthorized_device_fails_debugging(self):
        device = self._make_device(mode="unauthorized")
        runner = self._make_runner(device)
        result = runner.run()

        debug_items = [i for i in result.items if "debugging" in i.label.lower()]
        assert debug_items[0].status == CheckStatus.FAIL

    def test_adb_available_passes(self):
        device = self._make_device()
        runner = self._make_runner(device)
        result = runner.run()

        adb_items = [i for i in result.items if "adb" in i.label.lower()]
        assert adb_items[0].status == CheckStatus.PASS

    def test_model_info_passes(self):
        device = self._make_device(model="Pixel 7", android_version="14")
        runner = self._make_runner(device)
        result = runner.run()

        model_items = [i for i in result.items if "android version" in i.label.lower()]
        assert model_items[0].status == CheckStatus.PASS
        assert "Pixel 7" in model_items[0].detail

    def test_encryption_notice_present(self):
        device = self._make_device(encryption_state="encrypted")
        runner = self._make_runner(device)
        result = runner.run()

        enc_items = [i for i in result.items if "encryption" in i.label.lower()]
        assert len(enc_items) >= 1
        assert enc_items[0].status == CheckStatus.INFO

    def test_has_all_three_categories(self):
        device = self._make_device()
        runner = self._make_runner(device)
        result = runner.run()

        categories = set(i.category for i in result.items)
        assert "phone_settings" in categories
        assert "files" in categories
        assert "safety" in categories


class TestChecklistRunnerXiaomi:
    """Test brand-specific checklist items for Xiaomi."""

    def test_xiaomi_shows_mi_unlock_item(self):
        device = DeviceInfo(
            serial="X", brand="xiaomi", model="Redmi Note 12",
            mode="system", oem_unlock_allowed="1", battery_level=80,
            android_version="13",
        )
        adb = MagicMock(spec=ADB)
        adb.available = True
        adb.version.return_value = "35.0.2"
        runner = ChecklistRunner(adb=adb, device=device)
        result = runner.run()

        mi_items = [i for i in result.items if "xiaomi" in i.label.lower() or "mi unlock" in i.label.lower()]
        assert len(mi_items) >= 1
