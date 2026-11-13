"""
Unit tests — MainWindow UI, Theme Toggle & Navigation (Phase 10).
"""

from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from flashdock import __version__
from flashdock.config import Config
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.network import NetworkMonitor
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.main_window import (
    MainWindow,
    PAGE_HOME,
    PAGE_DEVICE_CARD,
    PAGE_DIAGNOSTICS,
    PAGE_DOWNLOADS,
    PAGE_UNBRICK,
    PAGE_INTEGRITY,
    PAGE_LOGS_HELP,
    PAGE_SIDELOAD,
)



@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_main_window(tmp_path):
    config = Config(path=tmp_path / "config.json")
    network = MagicMock(spec=NetworkMonitor)
    network.is_online = True
    device_mgr = MagicMock(spec=DeviceManager)
    device_mgr.device = None
    device_mgr.all_devices = []
    device_mgr.locked_serial = None
    adb = MagicMock(spec=ADB)
    fastboot = MagicMock(spec=Fastboot)

    win = MainWindow(
        config=config,
        network=network,
        device_mgr=device_mgr,
        adb=adb,
        fastboot=fastboot,
    )
    yield win
    win.close()
    win.deleteLater()
    from PySide6.QtCore import QCoreApplication, QEvent
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.instance().processEvents()


class TestMainWindow:
    def test_theme_toggle(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._config.get("theme", "dark") == "dark"
        assert "Light" in win._theme_btn.text()

        # Toggle to light
        win._toggle_theme()
        assert win._config.get("theme") == "light"
        assert "Dark" in win._theme_btn.text()

        # Toggle back to dark
        win._toggle_theme()
        assert win._config.get("theme") == "dark"
        assert "Light" in win._theme_btn.text()

    def test_navigation_to_diagnostics(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger diagnostics action
        win._on_action("diagnostics")
        assert win._stack.currentIndex() == PAGE_DIAGNOSTICS

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_device_change_refreshes_diagnostics(self, qapp, mock_main_window):
        win = mock_main_window
        win._stack.setCurrentIndex(PAGE_DIAGNOSTICS)

        dev = DeviceInfo(serial="DEV_99", brand="Xiaomi", model="POCO F3", mode="adb")
        win._handle_device_change(dev)
        assert "DEV_99" in win._diagnostics_screen._device_badge.text()

    def test_navigation_to_downloads(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger downloads action
        win._on_action("downloads")
        assert win._stack.currentIndex() == PAGE_DOWNLOADS

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_unbrick(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger unbrick action
        win._on_action("unbrick")
        assert win._stack.currentIndex() == PAGE_UNBRICK

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_integrity(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger integrity action
        win._on_action("integrity")
        assert win._stack.currentIndex() == PAGE_INTEGRITY

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_logs_help(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger logs_help action
        win._on_action("logs_help")
        assert win._stack.currentIndex() == PAGE_LOGS_HELP

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_navigation_to_sideload(self, qapp, mock_main_window):
        win = mock_main_window
        assert win._stack.currentIndex() == PAGE_HOME

        # Trigger sideload action
        win._on_action("sideload")
        assert win._stack.currentIndex() == PAGE_SIDELOAD

        # Back to home
        win._stack.setCurrentIndex(PAGE_HOME)
        assert win._stack.currentIndex() == PAGE_HOME

    def test_tool_filter_by_category(self, qapp, mock_main_window):
        win = mock_main_window
        # Initial: All tools visible
        visible_initial = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert len(visible_initial) == 16

        win._on_category_clicked("Flash")
        visible = {aid for aid, row in win._action_buttons.items() if not row.isHidden()}
        assert visible == {"flash_rom", "unbrick", "mtk_unisoc", "return_stock"}
        win._on_category_clicked("Root")
        visible = {aid for aid, row in win._action_buttons.items() if not row.isHidden()}
        assert visible == {"root", "modules", "integrity", "unlock_bl"}
        win._on_category_clicked("Daily")
        visible = {aid for aid, row in win._action_buttons.items() if not row.isHidden()}
        assert visible == {"sideload", "scrcpy", "downloads", "logs_help"}

    def test_tool_filter_by_search_query(self, qapp, mock_main_window):
        win = mock_main_window
        # Search for bootloop
        win._search_input.setText("bootloop")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "unbrick" in visible
        assert "diagnostics" not in visible

        # Search for scrcpy / mirror
        win._search_input.setText("mirror")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "scrcpy" in visible
        assert "root" not in visible

        # Search for drivers
        win._search_input.setText("driver")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "downloads" in visible
        assert "root" not in visible

        # Search for sideload
        win._search_input.setText("sideload")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert "sideload" in visible
        assert "root" not in visible

        # Search for non-existent keyword shows empty state
        win._search_input.setText("nonexistent_unknown_tool_xyz")
        visible = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert len(visible) == 0
        assert not win._empty_state_widget.isHidden()

        # Reset filters
        win._reset_filters()
        assert win._search_input.text() == ""
        assert win._active_category == "All"
        visible_reset = [aid for aid, b in win._action_buttons.items() if not b.isHidden()]
        assert len(visible_reset) == 16
        assert win._empty_state_widget.isHidden()

        # Test tool sorting
        win._sort_combo.setCurrentIndex(1)  # A -> Z
        assert win._sort_combo.currentData() == "az"
        # Reset back to recommended
        win._reset_filters()
        assert win._sort_combo.currentData() == "recommended"

    def test_workflow_sheets_replace_oem_strip(self, qapp, mock_main_window):
        from PySide6.QtWidgets import QScrollArea
        from flashdock.ui.widgets.liquid_glass_widget import LiquidGlassSheet

        win = mock_main_window
        assert len(win._workflow_sheets) == 4
        assert all(isinstance(sheet, LiquidGlassSheet) for sheet in win._workflow_sheets.values())
        assert win._island.lens_control._active_key == "All"
        assert not win._phone_panel.findChildren(QScrollArea)
        assert len(win._action_buttons) == 16

    def test_terminal_clean_toggle_and_fixed_width(self, qapp, mock_main_window):
        """Fix 18: Terminal is fixed 320px width when visible, toggles smoothly without layout glitches."""
        win = mock_main_window
        assert win._side_terminal.isHidden()
        assert "Show Terminal" in win._btn_terminal_toggle.text()

        win._toggle_terminal_visibility()
        assert not win._side_terminal.isHidden()
        assert "Hide Terminal" in win._btn_terminal_toggle.text()
        assert win._side_terminal.minimumWidth() == 240
        assert win._side_terminal.maximumWidth() == 600

        # Header and footer use the same visibility action.
        win._side_terminal._toggle_btn.click()
        assert win._side_terminal.isHidden()
        win._toggle_terminal_visibility()
        assert not win._side_terminal.isHidden()
        assert win._side_terminal.minimumWidth() == 240
        assert win._side_terminal.maximumWidth() == 600

    def test_unified_single_row_bottom_bar(self, qapp, mock_main_window):
        """Fix 18 & v1.3.3: Bottom bar unifies Status badges and Device Controls into single horizontal row."""
        win = mock_main_window
        assert hasattr(win, "_status_bar")
        assert hasattr(win, "_device_selector")
        # Ensure DeviceSelector is hosted inside status bar
        assert win._status_bar._device_selector is win._device_selector
        assert win._status_bar.height() == 38 or win._status_bar.maximumHeight() == 38
        assert not win._status_bar._net_label.isHidden()
        assert win._status_bar._connection_badge.isHidden()
        assert not win._status_bar._mode_label.isHidden()
        assert not win._status_bar._version_label.isHidden()
        assert win._status_bar._version_label.text() == f"v{__version__}"



    def test_safety_gates_write_screens_and_disarms_on_device_change(self, qapp, mock_main_window):
        win = mock_main_window
        assert not win._island.write_switch.is_armed
        assert not win._flash_rom_screen.isEnabled()
        win._island.write_switch.set_armed(True)
        assert win._flash_rom_screen.isEnabled()
        dev = DeviceInfo(serial="PHONE_A", mode="system", battery_level=84, active_slot="a")
        win._handle_device_change(dev)
        assert not win._island.write_switch.is_armed
        assert "84%" in win._island.island_pill.telemetry_lbl.text()
        win._island.write_switch.set_armed(True)
        dev.battery_level = 83
        win._handle_device_change(dev)
        assert win._island.write_switch.is_armed
        assert "83%" in win._island.island_pill.telemetry_lbl.text()
        win._handle_device_change(None)
        assert not win._island.write_switch.is_armed
        assert not win._flash_rom_screen.isEnabled()

    def test_sideload_drop_in_safe_mode(self, qtbot, mock_main_window, tmp_path, monkeypatch):
        import zipfile
        from pathlib import Path
        from PySide6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
        from PySide6.QtGui import QDragEnterEvent, QDropEvent
        from flashdock.tools.runner import CommandResult
        from flashdock.ui.screens.sideload_screen import SideloadWorker
        qapp = QApplication.instance()

        win = mock_main_window
        win._on_action("sideload")
        screen = win._sideload_screen
        assert screen._dropzone.isEnabled()
        assert screen._dropzone_recovery.isEnabled()

        apk = tmp_path / "example.apk"
        with zipfile.ZipFile(apk, "w") as bundle:
            bundle.writestr("AndroidManifest.xml", b"test")
            bundle.writestr("META-INF/CERT.RSA", b"test signature marker")
        unsupported = tmp_path / "notes.txt"
        unsupported.touch()
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(unsupported)), QUrl.fromLocalFile(str(apk))])
        drag = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        qapp.sendEvent(screen._dropzone, drag)
        qapp.sendEvent(screen._dropzone, drop)
        assert drag.isAccepted() and drop.isAccepted()
        qtbot.waitUntil(lambda: not screen.is_inspecting_package())
        assert Path(screen._selected_file_path) == apk
        assert not screen._btn_install.isEnabled()

        ota = tmp_path / "update.zip"
        ota.touch()
        mime.setUrls([QUrl.fromLocalFile(str(apk)), QUrl.fromLocalFile(str(ota))])
        drag = QDragEnterEvent(QPoint(10, 10), Qt.DropAction.CopyAction, mime,
                               Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        drop = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime,
                          Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
        qapp.sendEvent(screen._dropzone_recovery, drag)
        qapp.sendEvent(screen._dropzone_recovery, drop)
        assert drag.isAccepted() and drop.isAccepted()
        assert Path(screen._selected_ota_path) == ota
        assert not screen._btn_sideload_ota.isEnabled()

        monkeypatch.setattr(screen._adb, "shell", lambda *_, **__: CommandResult([], 1, "", "offline", 0))
        screen.load_for_device(DeviceInfo(serial="PHONE", mode="system"))
        qtbot.waitUntil(lambda: screen._version_worker is None)
        started = []
        start_worker = SideloadWorker.start
        monkeypatch.setattr(SideloadWorker, "start",
                            lambda self: start_worker(self) if self.action == "installed_version"
                            else started.append(self.action))
        screen._on_install_clicked()
        assert not started and not screen._btn_install.isEnabled()
        assert "Arm Write" in screen._install_status.text()
        screen._btn_arm_install.click()
        assert win._island.write_switch.is_armed and not started
        assert screen._btn_install.isEnabled()
        monkeypatch.setattr(screen, "_confirm_install", lambda *args: False)
        screen._btn_install.click()
        assert not started

        def switch_target(*args):
            screen.load_for_device(DeviceInfo(serial="OTHER", mode="system"))
            return True

        monkeypatch.setattr(screen, "_confirm_install", switch_target)
        screen._btn_install.click()
        assert not started and not screen._write_in_progress
        screen.load_for_device(DeviceInfo(serial="PHONE", mode="system"))
        qtbot.waitUntil(lambda: screen._version_worker is None)
        monkeypatch.setattr(screen, "_confirm_install", lambda *args: True)
        screen._btn_install.click()
        assert started == ["install_single"]
        win._island.write_switch.set_armed(False)
        assert screen._dropzone.isEnabled() and not screen._btn_install.isEnabled()
        screen._worker.finished.emit()
        screen.load_for_device(DeviceInfo(serial="PHONE", mode="sideload"))
        screen._on_sideload_ota_clicked()
        assert started == ["install_single"]
        win._island.write_switch.set_armed(True)
        assert screen._btn_sideload_ota.isEnabled() and not screen._btn_install.isEnabled()

    def test_background_device_and_network_updates_reach_ui(self, qapp, mock_main_window):
        from threading import Thread

        win = mock_main_window
        dev = DeviceInfo(serial="QUEUED_PHONE", mode="bootloader", active_slot="_b")
        def publish():
            win._device_mgr.on_device_changed(dev)
            win._network.on_change(False)

        worker = Thread(target=publish)
        worker.start()
        worker.join()
        qapp.processEvents()
        assert "QUEUED_PHONE" in win._island.island_pill.primary_lbl.text()
        assert "Slot _B" in win._island.island_pill.telemetry_lbl.text()
        assert not win._action_buttons["downloads"].isEnabled()
        win._network.on_change(True)
        qapp.processEvents()
        assert win._action_buttons["downloads"].isEnabled()

    def test_hardware_emergency_mode_has_priority(self, qapp, mock_main_window):
        win = mock_main_window
        win._on_hardware_device_connected("mtk_brom", "COM4", {"display_name": "MediaTek BROM"})
        win._handle_device_change(DeviceInfo(serial="STALE_ADB", mode="system"))
        assert "MTK BROM" in win._island.island_pill.primary_lbl.text()
        assert "COM4" in win._island.island_pill.primary_lbl.text()
        win._on_hardware_device_disconnected()
        assert win._island.island_pill.primary_lbl.text() == "No Device Connected"
