"""
Tests for FlashDock v1.2.0 GSM Suite Features:
- Live Device Diagnostics HUD (device_hud.py)
- Universal Multi-Mode Reboot Switchboard (reboot_switchboard.py)
- Partition Image & Header Inspector (header_inspector_dialog.py)
- Workstation Settings Center (settings_dialog.py)
- Auto-Rescue Emergency Pre-Flash Fallback (flash_engine.py)
"""

from __future__ import annotations

import struct
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from flashdock.config import Config
from flashdock.core.device import DeviceInfo
from flashdock.ui.widgets.device_hud import LiveDeviceHud
from flashdock.ui.widgets.reboot_switchboard import RebootSwitchboardDialog
from flashdock.ui.widgets.header_inspector_dialog import PartitionHeaderInspectorDialog
from flashdock.ui.widgets.settings_dialog import SettingsDialog
from flashdock.workers.flash_engine import FlashEngineWorker, FlashTask, FlashOperationType


@pytest.fixture
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_live_device_hud_telemetry_updates(qapp):
    hud = LiveDeviceHud()
    assert hud.objectName() == "liveDeviceHud"

    # Offline / None device test
    hud.update_device(None)
    assert hud._gauge_batt.text() != ""
    assert hud._btn_rescue.isHidden()

    # Active device with telemetry
    dev = DeviceInfo(
        serial="TEST_SERIAL_123",
        mode="system",
        brand="Samsung",
        model="Galaxy S23",
        battery_level=85,
        battery_temp_c=31,
        battery_voltage_mv=4100,
        chipset="snapdragon",
        bootloader_state="unlocked",
        slot_scheme="a/b",
        active_slot="a",
        knox_warranty_bit="0x0",
        security_patch="2026-08-01",
    )
    hud.update_device(dev)

    assert "85%" in hud._gauge_batt.text()
    assert "31°C" in hud._gauge_batt.text()
    assert "Snapdragon" in hud._gauge_soc.text()
    assert "UNLOCKED" in hud._gauge_bl.text()
    assert "_a" in hud._gauge_slot.text()
    assert "Clean" in hud._gauge_knox.text()
    assert "2026-08-01" in hud._gauge_patch.text()
    assert "ROOT: NO" in hud._gauge_root.text()
    assert "ROM:" in hud._gauge_rom.text()


def test_live_device_hud_stepped_pipeline(qapp):
    hud = LiveDeviceHud()

    # Stage 1 Handshake
    hud.set_stepped_stage(1, "Handshake Established", 25)
    assert hud._prog_bar.value() == 25
    assert "Handshake" in hud._stage_status_text.text()

    # Stage 2 Verifying
    hud.set_stepped_stage(2, "Verifying Partition Table", 50)
    assert hud._prog_bar.value() == 50

    # Stage 3 Flashing
    hud.set_stepped_stage(3, "Writing boot_a partition", 75)
    assert hud._prog_bar.value() == 75

    # Stage 4 Complete
    hud.set_stepped_stage(4, "SHA-256 Checksum Verified", 100)
    assert hud._prog_bar.value() == 100

    # Trigger failure alert
    hud.trigger_failure_alert("Fastboot command timed out")
    assert "Aborted" in hud._stage_status_text.text()

    # Reset
    hud.reset_pipeline("Idle Standby")
    assert hud._prog_bar.value() == 0
    assert hud._stage_status_text.text() == "Idle Standby"


def test_reboot_switchboard_dialog(qapp):
    dev = DeviceInfo(
        serial="DEVICE_XYZ",
        mode="bootloader",
        brand="Google",
        model="Pixel 8 Pro",
    )
    dlg = RebootSwitchboardDialog(device=dev)
    assert "Power & Reboot Switchboard" in dlg.windowTitle()

    emitted_modes = []
    dlg.reboot_mode_selected.connect(emitted_modes.append)

    # Click recovery button
    dlg._on_mode_clicked("recovery")
    assert emitted_modes == ["recovery"]


def test_partition_header_inspector_parser(qapp, tmp_path: Path):
    # Create synthetic Android boot image v2 header (ANDROID! magic)
    boot_img = tmp_path / "test_boot.img"
    header_data = bytearray(16384)
    # Magic ANDROID!
    header_data[0:8] = b"ANDROID!"
    # kernel size 32MB
    struct.pack_into("<I", header_data, 8, 33554432)
    # ramdisk size 4MB
    struct.pack_into("<I", header_data, 16, 4194304)
    # os version raw: os_version 14.0.0, patch 2026-05
    os_ver_encoded = (14 << 25) | (5 << 11) | 0
    struct.pack_into("<I", header_data, 44, os_ver_encoded)
    # header version: 2
    struct.pack_into("<I", header_data, 40, 2)
    boot_img.write_bytes(header_data)

    dlg = PartitionHeaderInspectorDialog(file_path=str(boot_img))
    assert "Partition Header" in dlg.windowTitle()
    assert dlg.parsed_info.get("header_version") == "v2"
    assert dlg.parsed_info.get("kernel_size") == 33554432


def test_settings_dialog_tabs_and_toggles(qapp, tmp_path: Path):
    cfg = Config(path=tmp_path / "config.json")
    dlg = SettingsDialog(config=cfg)
    assert "Settings" in dlg.windowTitle()
    assert dlg._tabs.count() == 6

    theme_signals = []
    dlg.theme_changed.connect(theme_signals.append)

    # Toggle theme to light and save
    dlg._theme_combo.setCurrentIndex(1)
    dlg._save_settings()

    assert cfg.get("theme") == "light"
    assert "light" in theme_signals


def test_flash_engine_auto_rescue_restore(tmp_path: Path):
    adb = MagicMock()
    fastboot = MagicMock()
    fastboot.flash.return_value = MagicMock(success=True)

    backups_dir = tmp_path / "backups"
    worker = FlashEngineWorker(adb=adb, fastboot=fastboot, backups_dir=backups_dir)

    # Setup emergency directory
    serial = "TEST_SERIAL_999"
    emergency_dir = backups_dir / "emergency_preflash" / serial
    emergency_dir.mkdir(parents=True, exist_ok=True)
    (emergency_dir / "boot.img").write_bytes(b"MOCK_BOOT_IMAGE_DATA")
    (emergency_dir / "vbmeta.img").write_bytes(b"MOCK_VBMETA_DATA")

    ok, msg = worker.restore_emergency_preflash(serial=serial)
    assert ok is True
    assert "Restored 2/2" in msg
    assert fastboot.flash.call_count == 2
