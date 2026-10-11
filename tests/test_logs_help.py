"""
Unit tests — Logs, Telemetry & Interactive Troubleshooting Center (Phase 15).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.troubleshooter import (
    TROUBLESHOOTING_CATALOG,
    TroubleshooterManager,
    TroubleshootingItem,
)
from flashdock.tools.adb import ADB
from flashdock.tools.runner import CommandResult
from flashdock.ui.screens.logs_help_screen import LogsHelpScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Catalog & Troubleshooter Core Tests
# ---------------------------------------------------------------------------

class TestTroubleshooterCore:
    def test_catalog_structure(self):
        assert len(TROUBLESHOOTING_CATALOG) >= 5
        for item in TROUBLESHOOTING_CATALOG:
            assert item.id != ""
            assert item.title != ""
            assert item.symptom != ""
            assert len(item.causes) > 0
            assert len(item.steps) > 0

    def test_restart_adb_success(self):
        adb = MagicMock(spec=ADB)
        adb.kill_server.return_value = CommandResult(command=["kill-server"], return_code=0, stdout="", stderr="", duration_ms=10)
        adb.start_server.return_value = CommandResult(command=["start-server"], return_code=0, stdout="daemon started", stderr="", duration_ms=10)

        mgr = TroubleshooterManager(adb=adb)
        ok, msg = mgr.restart_adb()
        assert ok is True
        assert "Successfully restarted" in msg

    def test_restart_adb_failure(self):
        adb = MagicMock(spec=ADB)
        adb.kill_server.return_value = CommandResult(command=["kill-server"], return_code=0, stdout="", stderr="", duration_ms=10)
        adb.start_server.return_value = CommandResult(command=["start-server"], return_code=1, stdout="", stderr="bind error", duration_ms=10)

        mgr = TroubleshooterManager(adb=adb)
        ok, msg = mgr.restart_adb()
        assert ok is False
        assert "bind error" in msg

    def test_capture_logcat(self):
        adb = MagicMock(spec=ADB)
        adb.shell.return_value = CommandResult(
            command=["logcat"],
            return_code=0,
            stdout="01-01 12:00:00.000  1000  1000 I ActivityManager: Start proc\n",
            stderr="",
            duration_ms=10,
        )

        mgr = TroubleshooterManager(adb=adb)
        ok, text = mgr.capture_logcat(serial="DEV_1", buffer_name="main", lines=100)
        assert ok is True
        assert "ActivityManager" in text

    def test_clear_device_logcat(self):
        adb = MagicMock(spec=ADB)
        adb.shell.return_value = CommandResult(command=["logcat", "-c"], return_code=0, stdout="", stderr="", duration_ms=10)

        mgr = TroubleshooterManager(adb=adb)
        ok, msg = mgr.clear_device_logcat("DEV_1")
        assert ok is True
        assert "cleared" in msg

    def test_capture_dmesg(self):
        adb = MagicMock(spec=ADB)
        adb.shell.return_value = CommandResult(command=["dmesg"], return_code=0, stdout="[    0.000000] Linux version 5.10", stderr="", duration_ms=10)

        mgr = TroubleshooterManager(adb=adb)
        ok, text = mgr.capture_dmesg("DEV_1")
        assert ok is True
        assert "Linux version" in text


# ---------------------------------------------------------------------------
# LogsHelpScreen UI Tests
# ---------------------------------------------------------------------------

class TestLogsHelpScreen:
    @pytest.fixture
    def screen(self, qapp, tmp_path):
        dev_mgr = MagicMock(spec=DeviceManager)
        dev_mgr.device = None
        adb = MagicMock(spec=ADB)

        # Create temporary fake log files
        log_file = tmp_path / "flashdock_2026-10-11.log"
        log_file.write_text(
            "2026-10-11 21:00:00 | INFO     | flashdock.main | Application startup\n"
            "2026-10-11 21:00:05 | WARNING  | flashdock.usb  | Voltage jitter detected\n"
            "2026-10-11 21:00:10 | ERROR    | flashdock.flsh | Partition write retry\n"
            "2026-10-11 21:00:15 | DEBUG    | flashdock.diag | Reading battery props\n",
            encoding="utf-8",
        )

        with patch("flashdock.ui.screens.logs_help_screen.LOGS_DIR", tmp_path), \
             patch("flashdock.core.troubleshooter.LOGS_DIR", tmp_path):
            scr = LogsHelpScreen(device_mgr=dev_mgr, adb=adb)
            scr._troubleshooter.list_log_files = lambda: [log_file]
            scr._refresh_log_files_list()
            return scr

    def test_screen_tabs(self, screen):
        assert screen._tabs.count() == 4
        assert "Application Logs" in screen._tabs.tabText(0)
        assert "Device Logcat" in screen._tabs.tabText(1)
        assert "Guided Interactive Troubleshooting" in screen._tabs.tabText(2)
        assert "Partition & Architecture Guide" in screen._tabs.tabText(3)

    def test_log_level_filter(self, screen):
        # All levels initially
        assert len(screen._raw_log_lines) == 4
        assert "4 / 4 lines" in screen._match_badge.text()

        # Filter by ERROR
        screen._level_combo.setCurrentText("ERROR")
        assert "1 / 4 lines" in screen._match_badge.text()
        assert "Partition write retry" in screen._log_viewer.toPlainText()
        assert "Application startup" not in screen._log_viewer.toPlainText()

        # Filter by WARNING
        screen._level_combo.setCurrentText("WARNING")
        assert "1 / 4 lines" in screen._match_badge.text()
        assert "Voltage jitter detected" in screen._log_viewer.toPlainText()

    def test_log_search_filter(self, screen):
        screen._level_combo.setCurrentText("All Levels")
        screen._search_input.setText("battery")
        assert "1 / 4 lines" in screen._match_badge.text()
        assert "Reading battery props" in screen._log_viewer.toPlainText()

        screen._search_input.clear()
        assert "4 / 4 lines" in screen._match_badge.text()

    def test_load_for_device_updates_status(self, screen):
        dev = DeviceInfo(serial="HELP_SERIAL", model="Galaxy S22", mode="system")
        screen.load_for_device(dev)
        assert "Galaxy S22" in screen._subtitle.text()
        assert "HELP_SERIAL" in screen._logcat_status_lbl.text()

    def test_troubleshooting_navigation_signal(self, screen):
        target = MagicMock()
        screen.navigate_to_page.connect(target)

        # Card with unbrick navigation target
        item = [it for it in TROUBLESHOOTING_CATALOG if it.navigation_target == 12][0]
        screen._on_troubleshoot_action(item)
        target.assert_called_once_with(12)
