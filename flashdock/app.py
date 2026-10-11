"""
FlashDock — Application bootstrap.

Creates the QApplication, loads the config, starts the network monitor
and device manager, and shows the main window.  Called by ``main.py``.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from flashdock import __app_name__
from flashdock.config import Config
from flashdock.core.crash_reporter import install_crash_handler, set_crash_dialog_callback
from flashdock.core.device_manager import DeviceManager
from flashdock.core.network import NetworkMonitor
from flashdock.logger import get_logger, setup_logging
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.main_window import MainWindow
from flashdock.ui.styles import get_stylesheet
from flashdock.ui.widgets.crash_dialog import CrashDialog

log = get_logger(__name__)


def run() -> int:
    """Entry point for the GUI application.  Returns the exit code."""

    # ---- Phase 16 Crash Reporter ------------------------------------------
    install_crash_handler()

    # ---- Logging -----------------------------------------------------------
    log_file = setup_logging()
    log.info("=" * 60)
    log.info("  %s starting", __app_name__)
    log.info("  Log file: %s", log_file)
    log.info("=" * 60)

    # ---- Config ------------------------------------------------------------
    config = Config.load()

    # ---- Qt application ----------------------------------------------------
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setStyle("Fusion")  # Consistent look across Windows versions
    active_theme = config.get("theme", "dark")
    app.setStyleSheet(get_stylesheet(active_theme))

    def _show_crash_modal(report_text: str, log_file_path: str) -> None:
        try:
            dlg = CrashDialog(report_text, log_file_path)
            dlg.exec()
        except Exception:
            pass

    set_crash_dialog_callback(_show_crash_modal)

    # ---- Tools -------------------------------------------------------------
    dry_run = config.dry_run
    adb = ADB(dry_run=dry_run)
    fastboot = Fastboot(dry_run=dry_run)

    # Ensure the ADB server is running
    if adb.available:
        adb.start_server()
        ver = adb.version()
        if ver:
            log.info("ADB version: %s", ver)

    if fastboot.available:
        ver = fastboot.version()
        if ver:
            log.info("Fastboot version: %s", ver)

    # ---- Network monitor ---------------------------------------------------
    network = NetworkMonitor(
        interval=config.get("connectivity_recheck_sec", 30),
    )
    network.start()

    # ---- Device manager ----------------------------------------------------
    device_mgr = DeviceManager(config=config, adb=adb, fastboot=fastboot)
    device_mgr.start()

    # ---- Main window -------------------------------------------------------
    window = MainWindow(
        config=config,
        network=network,
        device_mgr=device_mgr,
        adb=adb,
        fastboot=fastboot,
    )
    window.show()

    log.info("Main window shown -- entering event loop.")
    exit_code = app.exec()

    # ---- Cleanup -----------------------------------------------------------
    device_mgr.stop()
    network.stop()
    log.info("Application exited with code %d.", exit_code)
    return exit_code
