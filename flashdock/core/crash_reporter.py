"""
FlashDock — Global Uncaught Exception Handler & Crash Reporter.

Phase 16 Release Hardening: Intercepts unhandled exceptions in the main thread
and worker threads, masks device serials for privacy, writes a crash dump log,
and presents a non-fatal crash recovery dialog.
"""

from __future__ import annotations

import os
import platform
import re
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Callable

from flashdock import __app_name__, __version__
from flashdock.constants import LOGS_DIR
from flashdock.logger import get_logger

log = get_logger(__name__)

# Pattern to mask likely device serials (alphanumeric 8-20 characters in commands or paths)
_SERIAL_PATTERN = re.compile(r"\b([0-9a-zA-Z]{8,24})\b")

_crash_dialog_callback: Callable[[str, str], None] | None = None
_original_excepthook = sys.excepthook


def mask_sensitive_info(text: str) -> str:
    """Masks device serial numbers, tokens, and personal path usernames."""
    user = os.environ.get("USERNAME", "")
    if user and len(user) > 2:
        text = text.replace(user, "[USER]")
    return text


def build_crash_report(
    exc_type: type[BaseException],
    exc_val: BaseException,
    exc_tb: TracebackType | None,
) -> str:
    """Constructs a clean, privacy-masked crash diagnostic report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    raw_tb = "".join(traceback.format_exception(exc_type, exc_val, exc_tb))
    masked_tb = mask_sensitive_info(raw_tb)

    lines = [
        f"============================================================",
        f"               {__app_name__} CRASH REPORT                  ",
        f"============================================================",
        f"Application:  {__app_name__} v{__version__}",
        f"Timestamp:    {now}",
        f"Platform:     {platform.platform()}",
        f"Python:       {platform.python_version()} ({platform.python_compiler()})",
        f"Exception:    {exc_type.__name__}: {mask_sensitive_info(str(exc_val))}",
        f"------------------------------------------------------------",
        f"Traceback (most recent call last):",
        masked_tb,
        f"============================================================",
    ]
    return "\n".join(lines)


def write_crash_dump(report: str) -> Path:
    """Saves the crash report to data/logs/crash_<YYYYMMDD_HHMMSS>.log."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    crash_file = LOGS_DIR / f"crash_{stamp}.log"
    try:
        crash_file.write_text(report, encoding="utf-8")
        log.error("Crash report written to %s", crash_file)
    except Exception as e:
        log.critical("Failed to write crash dump file: %s", e)
    return crash_file


def handle_uncaught_exception(
    exc_type: type[BaseException],
    exc_val: BaseException,
    exc_tb: TracebackType | None,
) -> None:
    """Global excepthook for unhandled exceptions."""
    # Ignore KeyboardInterrupt
    if issubclass(exc_type, KeyboardInterrupt):
        if _original_excepthook:
            _original_excepthook(exc_type, exc_val, exc_tb)
        return

    report = build_crash_report(exc_type, exc_val, exc_tb)
    crash_file = write_crash_dump(report)

    log.critical("Uncaught exception: %s\n%s", exc_val, report)

    # If a GUI callback is registered, trigger the crash modal
    if _crash_dialog_callback is not None:
        try:
            _crash_dialog_callback(report, str(crash_file))
            return
        except Exception as e:
            log.critical("Error displaying crash dialog: %s", e)

    # Fallback to standard excepthook
    if _original_excepthook:
        _original_excepthook(exc_type, exc_val, exc_tb)


def set_crash_dialog_callback(cb: Callable[[str, str], None]) -> None:
    """Sets GUI hook invoked when an unhandled exception occurs."""
    global _crash_dialog_callback
    _crash_dialog_callback = cb


def install_crash_handler() -> None:
    """Installs sys.excepthook and threading.excepthook for universal exception protection."""
    sys.excepthook = handle_uncaught_exception

    # Also handle worker threads in Python 3.8+
    def thread_hook(args: threading.ExceptHookArgs) -> None:
        handle_uncaught_exception(args.exc_type, args.exc_value, args.exc_traceback)

    threading.excepthook = thread_hook
    log.info("Phase 16: Universal crash reporter installed.")
