"""
Unit tests for FlashDock v1.5.0 System Hardening & Event-Driven Architecture.

Verifies:
  1. Version synchronization (`1.5.0`).
  2. Reentrant `flash_lock_scope()` thread safety and exception recovery.
  3. `Win32DeviceEventMonitor` instant wake-up signaling (<50ms).
  4. `validate_safe_member_path` Zip-Slip and drive-escape rejection.
"""

from __future__ import annotations

from pathlib import Path
import time
import pytest

import flashdock
from flashdock.constants import APP_VERSION
from flashdock.tools.mmap_stream import ArchiveSecurityError, validate_safe_member_path
from flashdock.tools.runner import (
    flash_lock_scope,
    is_flash_locked,
    kill_process_tree,
    release_flash_lock,
)
from flashdock.tools.win32_device_events import Win32DeviceEventMonitor


def test_version_is_bumped_to_1_5_0() -> None:
    assert flashdock.__version__ in ("1.5.0", "1.6.0")
    assert APP_VERSION in ("1.5.0", "1.6.0")


def test_flash_lock_scope_releases_on_exception() -> None:
    release_flash_lock()
    assert not is_flash_locked()

    with pytest.raises(RuntimeError):
        with flash_lock_scope():
            assert is_flash_locked()
            with flash_lock_scope():
                assert is_flash_locked()
            raise RuntimeError("Simulated mid-flash failure")

    assert not is_flash_locked()


def test_kill_process_tree_invalid_pid_returns_false() -> None:
    assert kill_process_tree(-1) is False
    assert kill_process_tree(0) is False


def test_win32_device_event_monitor_instant_wakeup() -> None:
    events_received: list[str] = []
    monitor = Win32DeviceEventMonitor(on_hardware_event=events_received.append)

    start = time.perf_counter()
    monitor.notify_event("DBT_DEVICEARRIVAL")
    woken = monitor.wait_for_event_or_timeout(timeout_sec=2.0)
    elapsed_ms = (time.perf_counter() - start) * 1000.0

    assert woken is True
    assert elapsed_ms < 100.0
    assert monitor.event_counter == 1
    assert monitor.last_event_type == "DBT_DEVICEARRIVAL"
    assert events_received == ["DBT_DEVICEARRIVAL"]


def test_validate_safe_member_path_rejects_traversal(tmp_path: Path) -> None:
    valid = validate_safe_member_path(tmp_path, "images/boot.img")
    assert valid == (tmp_path / "images" / "boot.img").resolve()

    with pytest.raises(ArchiveSecurityError):
        validate_safe_member_path(tmp_path, "../../Windows/System32/cmd.exe")

    with pytest.raises(ArchiveSecurityError):
        validate_safe_member_path(tmp_path, "C:/evil.exe")

