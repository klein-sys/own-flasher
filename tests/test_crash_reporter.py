"""
Unit tests for Phase 16 Crash Reporter and Crash Recovery Dialog.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.crash_reporter import (
    build_crash_report,
    handle_uncaught_exception,
    mask_sensitive_info,
    set_crash_dialog_callback,
    write_crash_dump,
)
from flashdock.ui.widgets.crash_dialog import CrashDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_mask_sensitive_info():
    raw = "User path C:\\Users\\Administrator\\test and data"
    masked = mask_sensitive_info(raw)
    assert isinstance(masked, str)


def test_build_crash_report():
    try:
        raise ValueError("Simulated catastrophic failure")
    except ValueError as exc:
        exc_type, exc_val, exc_tb = sys.exc_info()
        report = build_crash_report(exc_type, exc_val, exc_tb)

    assert "CRASH REPORT" in report
    assert "ValueError: Simulated catastrophic failure" in report
    assert "Traceback" in report
    assert f"FlashDock v" in report


def test_write_crash_dump(tmp_path: Path):
    report = "Dummy crash dump content"
    log_file = write_crash_dump(report)
    assert log_file.exists()
    assert log_file.read_text(encoding="utf-8") == report
    log_file.unlink(missing_ok=True)


def test_handle_uncaught_exception():
    cb = MagicMock()
    set_crash_dialog_callback(cb)

    try:
        raise RuntimeError("Crash test triggered")
    except RuntimeError as exc:
        exc_type, exc_val, exc_tb = sys.exc_info()
        handle_uncaught_exception(exc_type, exc_val, exc_tb)

    assert cb.called
    args = cb.call_args[0]
    assert "Crash test triggered" in args[0]
    assert Path(args[1]).exists()
    Path(args[1]).unlink(missing_ok=True)


def test_crash_dialog(qapp, tmp_path: Path):
    dummy_log = tmp_path / "crash_test.log"
    dummy_log.write_text("Crash details", encoding="utf-8")

    dlg = CrashDialog("Sample Crash Traceback", str(dummy_log))
    assert "Unexpected Error" in dlg.windowTitle()
    assert dlg.traceback_view.toPlainText() == "Sample Crash Traceback"
    dlg.close()
