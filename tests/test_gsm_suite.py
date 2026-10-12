"""
Unit & Integration Tests for FlashDock GSM Suite Architecture.

Covers all 4 core subsystems:
1. Hardware Polling & VID/PID Engine (device_monitor.py)
2. Device Diagnostics & Info Extraction Engine (diagnostics_engine.py)
3. Firmware Flashing, Calibration Backups & Bootloader Controller (flash_engine.py)
4. UI Architecture, Colored Terminal Streaming & macOS Big Sur Integration
"""

import os
import hashlib
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from flashdock.workers.device_monitor import (
    DeviceMonitorWorker,
    HardwareMode,
    HARDWARE_VID_PID_MAP,
    identify_hardware_device,
)
from flashdock.core.diagnostics_engine import (
    DiagnosticsEngine,
    AdbDiagnosticsResult,
    FastbootDiagnosticsResult,
)
from flashdock.workers.flash_engine import (
    FlashEngineWorker,
    FlashTask,
    FlashOperationType,
    CRITICAL_CALIBRATION_PARTITIONS,
)
from flashdock.ui.widgets.status_bar import StatusBarWidget
from flashdock.ui.widgets.side_terminal import SideTerminalWidget
from flashdock.ui.styles import get_stylesheet


@pytest.fixture(scope="session")
def qapp():
    """Ensure a QApplication instance exists for GUI tests."""
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


# ===========================================================================
# Subsystem 1: Connection Monitoring & Hardware Polling Engine
# ===========================================================================

class TestDeviceMonitorEngine:
    """Tests for USB/COM VID/PID mapping and non-blocking polling worker."""

    def test_hardware_modes_defined(self):
        """Verify all required GSM Suite chipset modes are cataloged."""
        assert HardwareMode.ADB.value == "adb"
        assert HardwareMode.FASTBOOT.value == "fastboot"
        assert HardwareMode.MTK_BROM.value == "mtk_brom"
        assert HardwareMode.MTK_PRELOADER.value == "mtk_preloader"
        assert HardwareMode.QUALCOMM_EDL.value == "qualcomm_edl"
        assert HardwareMode.UNISOC_DIAG.value == "unisoc_diag"
        assert HardwareMode.UNISOC_FDL.value == "unisoc_fdl"

    def test_vid_pid_lookup_mtk_brom(self):
        """MediaTek BROM (VID 0E8D, PID 0003) must resolve correctly."""
        mode = identify_hardware_device("0E8D", "0003")
        assert mode == HardwareMode.MTK_BROM

    def test_vid_pid_lookup_mtk_preloader(self):
        """MediaTek Preloader (VID 0E8D, PID 2000) must resolve correctly."""
        mode = identify_hardware_device("0E8D", "2000")
        assert mode == HardwareMode.MTK_PRELOADER

    def test_vid_pid_lookup_qualcomm_edl(self):
        """Qualcomm EDL 9008 (VID 05C6, PID 9008) must resolve correctly."""
        mode = identify_hardware_device("05C6", "9008")
        assert mode == HardwareMode.QUALCOMM_EDL

    def test_vid_pid_lookup_unisoc(self):
        """Unisoc SPRD U2S Diag (1782:4D00) and FDL (1782:4D02) must resolve."""
        assert identify_hardware_device("1782", "4D00") == HardwareMode.UNISOC_DIAG
        assert identify_hardware_device("1782", "4D02") == HardwareMode.UNISOC_FDL

    def test_identify_from_raw_string(self):
        """identify_hardware_device extracts VID/PID from complex PnP strings."""
        raw_pnp = r"USB\VID_05C6&PID_9008\5&229D29A&0&1"
        mode = identify_hardware_device(raw_pnp)
        assert mode == HardwareMode.QUALCOMM_EDL

    def test_monitor_worker_init_and_state(self, qapp):
        """DeviceMonitorWorker initializes cleanly with safe defaults."""
        worker = DeviceMonitorWorker(interval_ms=1000)
        assert worker.interval_ms == 1000
        assert not worker.is_running
        assert not worker.is_paused

        # Test pause & resume state flags
        worker.pause_polling()
        assert worker.is_paused
        worker.resume_polling()
        assert not worker.is_paused

    def test_monitor_worker_emergency_priority(self, qapp):
        """Emergency hardware modes (EDL, BROM) take precedence over ADB."""
        worker = DeviceMonitorWorker()
        
        # Mock finding both an emergency port and an ADB port
        emergency_dev = {
            "mode": HardwareMode.QUALCOMM_EDL.value,
            "port": "COM7",
            "name": "Qualcomm HS-USB QDLoader 9008",
            "vid": "05C6",
            "pid": "9008",
            "is_emergency": True,
        }
        adb_dev = {
            "mode": HardwareMode.ADB.value,
            "port": "USB#VID_18D1&PID_4EE7",
            "name": "Android Device",
            "vid": "18D1",
            "pid": "4EE7",
            "is_emergency": False,
        }

        connected_signals = []
        worker.device_connected.connect(lambda mode, ident, d: connected_signals.append((mode, ident)))

        with patch.object(worker, "scan_usb_and_com_hardware", return_value=[emergency_dev, adb_dev]), \
             patch.object(worker._adb, "devices", return_value=[]), \
             patch.object(worker._fastboot, "devices", return_value=[]):
            worker._poll_once()

        assert len(connected_signals) == 1
        assert connected_signals[0][0] == HardwareMode.QUALCOMM_EDL.value
        assert connected_signals[0][1] == "COM7"

    def test_monitor_worker_disconnect_signal(self, qapp):
        """Worker emits device_disconnected when device is unplugged."""
        worker = DeviceMonitorWorker()
        worker._last_signature = "fastboot:FASTBOOT123"
        worker._current_device_info = {"mode": "fastboot", "identifier": "FASTBOOT123"}

        disconnected_emitted = []
        worker.device_disconnected.connect(lambda: disconnected_emitted.append(True))

        with patch.object(worker, "scan_usb_and_com_hardware", return_value=[]), \
             patch.object(worker._adb, "devices", return_value=[]), \
             patch.object(worker._fastboot, "devices", return_value=[]):
            worker._poll_once()

        assert len(disconnected_emitted) == 1
        assert worker._current_device_info is None


# ===========================================================================
# Subsystem 2: Device Diagnostics & Info Extraction Engine
# ===========================================================================

class TestDiagnosticsEngine:
    """Tests for non-blocking ADB getprop and Fastboot getvar all parsing."""

    def test_adb_diagnostics_parsing(self):
        """ADB getprop, dumpsys, and su stdout parse accurately into AdbDiagnosticsResult."""
        mock_adb = MagicMock()
        mock_adb.available = True
        mock_adb.shell.side_effect = [
            # 1. Batch getprop
            "ro.product.brand=[Xiaomi]\n"
            "ro.product.model=[2201116SG]\n"
            "ro.product.manufacturer=[Xiaomi]\n"
            "ro.build.display.id=[HyperOS 1.0.4.0.TGAMIXM]\n"
            "ro.build.version.release=[14]\n"
            "ro.build.version.sdk=[34]\n"
            "gsm.version.baseband=[MPSS.DE.3.1.1]\n"
            "ro.build.version.security_patch=[2026-09-01]\n"
            "ro.product.cpu.abi=[arm64-v8a]\n"
            "ro.boot.warranty_bit=[0]\n",
            # 2. dumpsys battery
            "Current Battery Service state:\n"
            "  level: 88\n"
            "  scale: 100\n"
            "  temperature: 295\n",
            # 3. which su
            "/system/bin/su\n",
            # 4. su -v
            "MagiskSU 27.0\n",
        ]

        engine = DiagnosticsEngine(adb=mock_adb)
        result = engine.query_adb_diagnostics("TEST_SERIAL_123")

        assert isinstance(result, AdbDiagnosticsResult)
        assert result.brand == "Xiaomi"
        assert result.model == "2201116SG"
        assert result.android_version == "14"
        assert result.sdk_level == "34"
        assert result.baseband == "MPSS.DE.3.1.1"
        assert result.security_patch == "2026-09-01"
        assert result.cpu_abi == "arm64-v8a"
        assert result.battery_level == 88
        assert result.battery_temp_c == 29.5
        assert result.is_rooted is True
        assert "MagiskSU 27.0" in result.root_version
        assert result.knox_warranty_void == "0"

    def test_adb_diagnostics_unauthorized_fallback(self):
        """Unauthorized or offline ADB returns structured fallback without crashing."""
        mock_adb = MagicMock()
        mock_adb.available = True
        mock_adb.shell.return_value = "error: device unauthorized. Please check the confirmation dialog."

        engine = DiagnosticsEngine(adb=mock_adb)
        result = engine.query_adb_diagnostics("UNAUTH_SERIAL")

        assert result.is_authorized is False
        assert result.brand == "Unknown"
        assert result.model == "Unknown"
        assert result.raw_error != ""

    def test_fastboot_diagnostics_parsing(self):
        """Fastboot getvar all output parses slot, unlocked state, secure boot, and CID."""
        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot.run.return_value = MagicMock(
            returncode=0,
            stdout="",
            stderr=(
                "(bootloader) version-baseband: M9615A-CEFWMAZM-2.0.170068\n"
                "(bootloader) current-slot: _a\n"
                "(bootloader) unlocked: yes\n"
                "(bootloader) secure: yes\n"
                "(bootloader) max-download-size: 0x20000000\n"
                "(bootloader) cid: 0x0002\n"
                "(bootloader) product: star\n"
                "all: done\n"
            ),
        )

        engine = DiagnosticsEngine(fastboot=mock_fastboot)
        result = engine.query_fastboot_diagnostics("FASTBOOT_SERIAL")

        assert isinstance(result, FastbootDiagnosticsResult)
        assert result.current_slot == "_a"
        assert result.is_unlocked is True
        assert result.is_secure_boot is True
        assert result.cid == "0x0002"
        assert result.product == "star"
        assert result.max_download_size == "0x20000000"

    def test_fastboot_diagnostics_offline_fallback(self):
        """Non-responsive fastboot returns clean structured response."""
        mock_fastboot = MagicMock()
        mock_fastboot.available = False

        engine = DiagnosticsEngine(fastboot=mock_fastboot)
        result = engine.query_fastboot_diagnostics("OFFLINE_FB")

        assert result.is_unlocked is False
        assert result.current_slot == ""
        assert "not available" in result.raw_error.lower()


# ===========================================================================
# Subsystem 3: Firmware Flashing, Partition Management & Safety Backups
# ===========================================================================

class TestFlashEngineWorker:
    """Tests for asynchronous flashing worker, calibration backup, and SHA-256 validation."""

    def test_sha256_calculation_with_progress(self, qapp, tmp_path):
        """Worker calculates exact SHA-256 and emits byte progress updates."""
        test_file = tmp_path / "boot.img"
        data = b"FlashDock Test Payload Boot Data" * 2048  # ~64 KB
        test_file.write_bytes(data)

        expected_hash = hashlib.sha256(data).hexdigest()

        worker = FlashEngineWorker()
        progress_events = []
        worker.progress_changed.connect(lambda cur, tot, pct: progress_events.append((cur, tot, pct)))

        calculated_hash = worker.calculate_file_sha256(str(test_file))

        assert calculated_hash == expected_hash
        assert len(progress_events) > 0
        assert progress_events[-1][2] == 100

    def test_calibration_backup_workflow(self, qapp, tmp_path):
        """Worker dumps calibration blocks and computes sha256 checksums."""
        mock_adb = MagicMock()
        mock_adb.available = True
        mock_adb.shell.return_value = "1024+0 records in\n1024+0 records out\n"
        mock_adb.pull.return_value = MagicMock(success=True)

        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot._run.return_value = MagicMock(success=True)

        worker = FlashEngineWorker(adb=mock_adb, fastboot=mock_fastboot)
        task = FlashTask(
            operation=FlashOperationType.BACKUP_CALIBRATION,
            backup_dir=str(tmp_path),
            device_serial="DEVICE_CAL_01",
        )

        with patch("flashdock.workers.flash_engine.is_flash_locked", return_value=False), \
             patch("flashdock.workers.flash_engine.acquire_flash_lock"), \
             patch("flashdock.workers.flash_engine.release_flash_lock"):
            
            # Create dummy backup target partition files so SHA-256 step succeeds
            for part in CRITICAL_CALIBRATION_PARTITIONS:
                (tmp_path / f"{part}.img").write_bytes(b"DUMMY_CALIBRATION_DATA")

            success, msg = worker._perform_calibration_backup(task)
            assert success is True
            assert "completed" in msg.lower()
            # Verify checksum manifest created
            manifest = tmp_path / "sha256sum.txt"
            assert manifest.exists()
            assert "efs.img" in manifest.read_text()

    def test_single_partition_flash_workflow(self, qapp, tmp_path):
        """Worker verifies SHA-256 and executes fastboot flash command."""
        test_image = tmp_path / "recovery.img"
        test_image.write_bytes(b"RECOVERY_IMAGE_PAYLOAD_TEST")
        sha256_hash = hashlib.sha256(test_image.read_bytes()).hexdigest()

        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot.flash.return_value = True

        worker = FlashEngineWorker(fastboot=mock_fastboot)
        task = FlashTask(
            operation=FlashOperationType.FLASH_PARTITION,
            partition_name="recovery",
            image_path=str(test_image),
            expected_sha256=sha256_hash,
            device_serial="FB_DEV_01",
        )

        with patch("flashdock.workers.flash_engine.is_flash_locked", return_value=False), \
             patch("flashdock.workers.flash_engine.acquire_flash_lock"), \
             patch("flashdock.workers.flash_engine.release_flash_lock"):
            
            success, msg = worker._perform_flash_partition(task)
            assert success is True
            mock_fastboot.flash.assert_called_once_with("recovery", str(test_image), serial="FB_DEV_01")

    def test_bootloader_unlock_controller(self, qapp):
        """Worker executes bootloader unlock with modern and legacy fallbacks."""
        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot.run.return_value = MagicMock(returncode=0, stdout="OKAY", stderr="")

        worker = FlashEngineWorker(fastboot=mock_fastboot)
        task = FlashTask(
            operation=FlashOperationType.BOOTLOADER_UNLOCK,
            device_serial="FB_UNLOCK_01",
        )

        with patch("flashdock.workers.flash_engine.is_flash_locked", return_value=False), \
             patch("flashdock.workers.flash_engine.acquire_flash_lock"), \
             patch("flashdock.workers.flash_engine.release_flash_lock"):
            
            success, msg = worker._perform_bootloader_op(task)
            assert success is True
            assert "unlocked" in msg.lower()

    def test_calibration_backup_fastboot_restricted_mode(self, qapp, tmp_path):
        """Worker transparently identifies when retail fastboot restricts fetch and avoids dead ADB calls."""
        mock_adb = MagicMock()
        mock_adb.available = True
        mock_adb.get_state.return_value = ""

        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot.devices.return_value = [{"serial": "PIXEL_RETAIL_01", "state": "fastboot"}]
        mock_fastboot._run.return_value = MagicMock(
            success=False,
            stderr="FAILED (remote: 'Command not allowed in locked/user state')",
            stdout="",
        )

        worker = FlashEngineWorker(adb=mock_adb, fastboot=mock_fastboot)
        task = FlashTask(
            operation=FlashOperationType.BACKUP_CALIBRATION,
            backup_dir=str(tmp_path),
            device_serial="PIXEL_RETAIL_01",
        )

        with patch("flashdock.workers.flash_engine.is_flash_locked", return_value=False), \
             patch("flashdock.workers.flash_engine.acquire_flash_lock"), \
             patch("flashdock.workers.flash_engine.release_flash_lock"):
            
            success, msg = worker._perform_calibration_backup(task)
            assert success is False
            assert "restricted" in msg.lower()

            # ADB shell should NOT have been invoked because device was in Fastboot mode
            mock_adb.shell.assert_not_called()

            # Manifest reflects RESTRICTED_FASTBOOT status honestly
            manifest = tmp_path / "manifest.txt"
            assert manifest.exists()
            content = manifest.read_text()
            assert "Partitions Dumped: 0/5" in content
            assert "RESTRICTED_FASTBOOT" in content

    def test_bootloader_lock_anti_relock_blocks_unverified(self, qapp):
        """Anti-Relock Gate strictly blocks relocking without verified stock or confirmation word."""
        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot.get_var.side_effect = lambda var, **kw: "no" if var == "is-userspace" else "yes" if var == "unlocked" else "oriole"

        worker = FlashEngineWorker(fastboot=mock_fastboot)
        task = FlashTask(
            operation=FlashOperationType.BOOTLOADER_LOCK,
            device_serial="PIXEL_RELOCK_01",
            confirmation_word="",
            allow_relock=False,
        )

        with patch("flashdock.workers.flash_engine.is_flash_locked", return_value=False), \
             patch("flashdock.workers.flash_engine.acquire_flash_lock"), \
             patch("flashdock.workers.flash_engine.release_flash_lock"):
            
            success, msg = worker._perform_bootloader_op(task)
            assert success is False
            assert "ANTI-RELOCK SAFETY LOCKOUT" in msg
            mock_fastboot.flashing_lock.assert_not_called()

            with pytest.raises(RuntimeError) as exc_info:
                worker._run_bootloader_lock(task)
            assert "ANTI-RELOCK SAFETY LOCKOUT" in str(exc_info.value)

    def test_bootloader_lock_anti_relock_permits_confirmed(self, qapp):
        """Anti-Relock Gate permits relock when confirmation word is 'RELOCK'."""
        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot.get_var.side_effect = lambda var, **kw: "no" if var == "is-userspace" else "yes" if var == "unlocked" else "oriole"
        mock_fastboot.flashing_lock.return_value = MagicMock(success=True)

        worker = FlashEngineWorker(fastboot=mock_fastboot)
        task = FlashTask(
            operation=FlashOperationType.BOOTLOADER_LOCK,
            device_serial="PIXEL_RELOCK_01",
            confirmation_word="RELOCK",
            allow_relock=True,
        )

        with patch("flashdock.workers.flash_engine.is_flash_locked", return_value=False), \
             patch("flashdock.workers.flash_engine.acquire_flash_lock"), \
             patch("flashdock.workers.flash_engine.release_flash_lock"):
            
            success, msg = worker._perform_bootloader_op(task)
            assert success is True
            assert "locked" in msg.lower()
            mock_fastboot.flashing_lock.assert_called_once_with(serial="PIXEL_RELOCK_01")

    def test_bootloader_lock_rejects_fastbootd_and_samsung(self, qapp):
        """Worker rejects relocking in fastbootd mode and on Samsung hardware."""
        mock_fastboot = MagicMock()
        mock_fastboot.available = True

        # Test fastbootd rejection
        mock_fastboot.get_var.side_effect = lambda var, **kw: "yes" if var == "is-userspace" else "yes"
        worker = FlashEngineWorker(fastboot=mock_fastboot)
        task_fastbootd = FlashTask(
            operation=FlashOperationType.BOOTLOADER_LOCK,
            device_serial="DEV_01",
            confirmation_word="RELOCK",
        )
        success, msg = worker._perform_bootloader_op(task_fastbootd)
        assert success is False
        assert "fastbootd" in msg.lower()

        with pytest.raises(RuntimeError) as exc_info:
            worker._run_bootloader_lock(task_fastbootd)
        assert "fastbootd" in str(exc_info.value).lower()

        # Test Samsung rejection
        mock_fastboot.get_var.side_effect = lambda var, **kw: "no" if var == "is-userspace" else "yes"
        task_samsung = FlashTask(
            operation=FlashOperationType.BOOTLOADER_LOCK,
            device_serial="DEV_SAM",
            device_brand="samsung",
            confirmation_word="RELOCK",
        )
        success_sam, msg_sam = worker._perform_bootloader_op(task_samsung)
        assert success_sam is False
        assert "samsung" in msg_sam.lower()

        with pytest.raises(RuntimeError) as exc_info_sam:
            worker._run_bootloader_lock(task_samsung)
        assert "samsung" in str(exc_info_sam.value).lower()

    def test_flash_engine_worker_acquires_flash_lock_in_run(self, qapp):
        """FlashEngineWorker.run() guarantees acquisition and release of global flash lock."""
        mock_fastboot = MagicMock()
        mock_fastboot.available = True
        mock_fastboot.reboot.return_value = MagicMock(success=True)

        worker = FlashEngineWorker(fastboot=mock_fastboot)
        task = FlashTask(
            operation=FlashOperationType.REBOOT,
            device_serial="DEV_REBOOT",
        )
        worker._task = task

        with patch("flashdock.workers.flash_engine.acquire_flash_lock", return_value=True) as mock_acquire, \
             patch("flashdock.workers.flash_engine.release_flash_lock") as mock_release:
            worker.run()
            mock_acquire.assert_called_once()
            mock_release.assert_called_once()


# ===========================================================================
# Subsystem 4: UI Architecture & macOS Big Sur Styling
# ===========================================================================

class TestUIArchitectureAndBigSurStyles:
    """Tests for StatusBar connection badge, SideTerminal colored stream, and Big Sur tokens."""

    def test_status_bar_connection_badge(self, qapp):
        """StatusBar displays persistent styled connection badge."""
        bar = StatusBarWidget()
        bar.update_connection_badge("mtk_brom", "COM4 Connected")
        assert "COM4" in bar._connection_badge.text()
        assert not bar._connection_badge.isHidden()

        # Update to disconnected
        bar.update_connection_badge("disconnected", "")
        assert "DISCONNECTED" in bar._connection_badge.text().upper()

    def test_status_bar_progress_controls(self, qapp):
        """StatusBar progress bar updates and hides cleanly."""
        bar = StatusBarWidget()
        bar.set_progress(45)
        assert not bar._progress_bar.isHidden()
        assert bar._progress_bar.value() == 45

        bar.hide_progress()
        assert bar._progress_bar.isHidden()

    def test_side_terminal_colored_streaming(self, qapp):
        """SideTerminal formats INFO, WARN, SUCCESS, and ERROR prefixes with distinct colors."""
        term = SideTerminalWidget()
        term.clear()

        term.append_colored_stream("INFO", "Device connected to port COM3")
        term.append_colored_stream("WARN", "Battery level is below 30%")
        term.append_colored_stream("SUCCESS", "Partition boot flashed successfully")
        term.append_colored_stream("ERROR", "Flashing verification failed")

        text = term._text_edit.toPlainText()
        assert "[INFO]" in text
        assert "[WARN]" in text
        assert "[SUCCESS]" in text
        assert "[ERROR]" in text
        html = term._text_edit.document().toHtml().lower()
        # Check colored CSS hex references
        assert "#007aff" in html or "#0a84ff" in html  # Blue
        assert "#ff9500" in html or "#ff9f0a" in html  # Amber
        assert "#34c759" in html or "#30d158" in html  # Green
        assert "#ff3b30" in html or "#ff453a" in html  # Red

    def test_macos_big_sur_stylesheets_load(self):
        """macOS Big Sur stylesheets contain required tokens for segmented controls and cards."""
        light_qss = get_stylesheet("light")
        dark_qss = get_stylesheet("dark")

        assert "segmented_control" in light_qss
        assert "segmented_control" in dark_qss
        assert "operations_panel" in light_qss
        assert "operations_panel" in dark_qss
        assert "connection_badge" in light_qss
        assert "connection_badge" in dark_qss
        assert "#007AFF" in light_qss  # Apple Accent Blue
        assert "#0A84FF" in dark_qss   # Apple Dark Accent Blue

        # Ergonomic Light Mode Tokens (SKILL.md standard)
        assert "#F0F2F5" in light_qss  # Slate-Mica Canvas
        assert "#F8F9FA" in light_qss  # Soft Frost Cards
        assert "#DCE1E8" in light_qss  # Soft Card Border
        assert "#E9EEF5" in light_qss  # Sidebar & Segmented Control Tint
        assert "#1C2024" in light_qss  # Deep Slate Charcoal Text
        assert "#5A6572" in light_qss  # Muted Secondary Text

        # Ergonomic Dark Mode Tokens (SKILL.md standard)
        assert "#0D1117" in dark_qss   # Deep Space Obsidian Canvas
        assert "#181E26" in dark_qss   # Elevated Slate Cards
        assert "#2C3644" in dark_qss   # Elevated Slate Border
        assert "#141820" in dark_qss   # Sidebar & Segmented Control Surface
        assert "#252D38" in dark_qss   # Sidebar Border
        assert "#E6EDF3" in dark_qss   # Soft Platinum Text
        assert "#8B949E" in dark_qss   # Muted Steel Text
        assert "#0B0E14" in dark_qss   # Deep Midnight Terminal Canvas
