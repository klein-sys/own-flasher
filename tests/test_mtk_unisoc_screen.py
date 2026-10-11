"""
UI tests for MtkUnisocScreen and its integration into MainWindow.
"""

from pathlib import Path
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from flashdock.config import Config
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.network import NetworkMonitor
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.main_window import MainWindow, PAGE_HOME, PAGE_MTK_UNISOC
from flashdock.ui.screens.mtk_unisoc_screen import MtkUnisocScreen

SAMPLE_SCATTER_CONTENT = """
- general: MTK_PLATFORM_CFG
  info:
    - platform: MT6765
      project: k65v1
      storage_type: EMMC

- partition_index: SYS0
  partition_name: preloader
  file_name: preloader.bin
  is_download: true
  linear_start_addr: 0x0
  partition_size: 0x40000

- partition_index: SYS1
  partition_name: boot
  file_name: boot.img
  is_download: true
  linear_start_addr: 0x40000
  partition_size: 0x2000000
"""


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_mtk_unisoc_screen_init(qapp):
    screen = MtkUnisocScreen()
    assert screen._tabs.count() == 2
    assert "MediaTek" in screen._tabs.tabText(0)
    assert "Unisoc" in screen._tabs.tabText(1)


def test_mtk_tab_interactions(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: QMessageBox.StandardButton.Ok)

    screen = MtkUnisocScreen()
    assert screen._btn_mtk_bypass.isEnabled() is False

    # Connect
    screen._on_mtk_connect()
    assert screen._brom_mgr.connected is True
    assert screen._btn_mtk_bypass.isEnabled() is True
    assert screen._btn_mtk_reboot.isEnabled() is True

    # Bypass
    screen._on_mtk_bypass()
    assert screen._auth_handler.bypassed is True
    assert "Bypassed" in screen._mtk_auth_lbl.text()


def test_scatter_file_load(qapp, tmp_path: Path):
    scatter_file = tmp_path / "MT6765_Android_scatter.txt"
    scatter_file.write_text(SAMPLE_SCATTER_CONTENT, encoding="utf-8")

    screen = MtkUnisocScreen()
    # Mock browse by setting file directly
    screen._current_scatter = None
    # Simulate loading
    from flashdock.core.mtk import ScatterParser
    scatter = ScatterParser.parse_file(scatter_file)
    screen._current_scatter = scatter
    screen._scatter_dir = tmp_path
    screen._scatter_path_edit.setText(str(scatter_file))

    assert screen._current_scatter.platform == "MT6765"
    assert len(screen._current_scatter.partitions) == 2


def test_device_auto_tab_selection(qapp):
    screen = MtkUnisocScreen()

    # Device with MediaTek chipset
    mtk_dev = DeviceInfo(serial="mtk123", mode="adb", chipset="mediatek", hardware="mt6765")
    screen.load_for_device(mtk_dev)
    assert screen._tabs.currentIndex() == 0

    # Device with Unisoc chipset
    unisoc_dev = DeviceInfo(serial="spd123", mode="adb", chipset="unisoc", hardware="sc9863a")
    screen.load_for_device(unisoc_dev)
    assert screen._tabs.currentIndex() == 1


def test_main_window_mtk_unisoc_navigation(qapp, tmp_path: Path):
    config = Config(path=tmp_path / "config.json")
    net = NetworkMonitor()
    adb = ADB()
    fastboot = Fastboot()
    mgr = DeviceManager(config=config, adb=adb, fastboot=fastboot)

    win = MainWindow(config=config, network=net, device_mgr=mgr, adb=adb, fastboot=fastboot)
    assert win._stack.currentIndex() == PAGE_HOME

    # Trigger mtk_unisoc action
    win._on_action("mtk_unisoc")
    assert win._stack.currentIndex() == PAGE_MTK_UNISOC
    assert isinstance(win._mtk_unisoc_screen, MtkUnisocScreen)
