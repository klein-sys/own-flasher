"""
Unit tests for Phase 16 System Self-Test Engine and Dialog.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.selftest import SystemSelfTester, SelfTestReport, SelfTestResult
from flashdock.ui.widgets.selftest_dialog import SelfTestDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_selftest_result_dataclass():
    r = SelfTestResult(
        name="Test Check",
        category="Environment",
        status="PASS",
        detail="All good",
        remediation=None,
    )
    assert r.name == "Test Check"
    assert r.status == "PASS"
    assert r.category == "Environment"


def test_selftest_report_aggregation():
    results = [
        SelfTestResult("Check 1", "Env", "PASS", "ok"),
        SelfTestResult("Check 2", "Tool", "WARN", "warning", "fix it"),
        SelfTestResult("Check 3", "DB", "FAIL", "failed", "repair"),
    ]
    report = SelfTestReport(timestamp="2026-10-12 00:00:00", app_version="1.0.0", results=results)
    assert report.total_count == 3
    assert report.passed_count == 1
    assert report.warn_count == 1
    assert report.fail_count == 1
    assert report.is_healthy is False

    text = report.format_text()
    assert "FlashDock System Self-Test Diagnostics" in text
    assert "[✅ PASS] Check 1" in text
    assert "[⚠️ WARN] Check 2" in text
    assert "[❌ FAIL] Check 3" in text


def test_check_os_environment():
    tester = SystemSelfTester()
    res = tester.check_os_environment()
    assert res.category == "Environment"
    assert res.status in ("PASS", "WARN")


def test_check_python_runtime():
    tester = SystemSelfTester()
    res = tester.check_python_runtime()
    assert res.category == "Environment"
    assert res.status == "PASS"
    assert "Python 3." in res.detail


def test_check_filesystem_permissions(tmp_path: Path):
    tester = SystemSelfTester(data_dir=tmp_path)
    results = tester.check_filesystem_permissions()
    assert len(results) >= 4
    for r in results:
        assert r.category == "Filesystem"
        assert r.status == "PASS"


def test_check_sqlite_database():
    tester = SystemSelfTester()
    res = tester.check_sqlite_database()
    assert res.category == "Database"
    assert res.status == "PASS"


def test_check_binary_toolchains():
    tester = SystemSelfTester()
    results = tester.check_binary_toolchains()
    assert len(results) == 2
    for r in results:
        assert r.category == "Toolchains"
        assert r.status in ("PASS", "WARN")


def test_run_all_checks():
    tester = SystemSelfTester()
    report = tester.run_all_checks()
    assert report.total_count >= 8
    assert report.app_version == "1.0.0"


def test_selftest_dialog(qapp):
    dlg = SelfTestDialog()
    assert dlg.windowTitle() == "System Health & Toolchain Self-Test"
    assert dlg.latest_report is not None
    assert dlg.latest_report.total_count >= 8
    dlg.close()
