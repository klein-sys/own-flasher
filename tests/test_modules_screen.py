"""
Unit tests — ModulesScreen UI widget.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.modules import ModuleInfo, ModuleInspectionResult
from flashdock.tools.adb import ADB
from flashdock.ui.screens.modules_screen import ModulesScreen, ModuleInspectorDialog


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_deps():
    device_mgr = MagicMock(spec=DeviceManager)
    device_mgr.device = None
    adb = MagicMock(spec=ADB)
    return device_mgr, adb


class TestModuleInspectorDialog:
    def test_inspector_dialog_ui(self, qapp, tmp_path: Path):
        mod = ModuleInfo(
            id="test_id",
            name="Super Boost",
            version="2.0",
            version_code=20,
            author="Dev",
            description="Boosts performance",
        )
        insp = ModuleInspectionResult(
            is_valid_module=True,
            module_info=mod,
            warnings=["Modifies system partition"],
            file_count=5,
            total_size_bytes=20480,
        )
        dlg = ModuleInspectorDialog(insp, tmp_path / "mod.zip")
        from PySide6.QtWidgets import QLabel
        labels = dlg.findChildren(QLabel)
        assert any("Super Boost" in l.text() for l in labels)


class TestModulesScreenUI:
    def test_screen_init(self, qapp, mock_deps):
        dm, adb = mock_deps
        screen = ModulesScreen(dm, adb)
        assert screen._table.columnCount() == 5
        assert screen._btn_install is not None
        assert screen._btn_emergency_disable is not None

    def test_load_device_and_populate_table(self, qapp, mock_deps):
        dm, adb = mock_deps
        screen = ModulesScreen(dm, adb)

        sample_modules = [
            ModuleInfo(id="m1", name="Module 1", version="1.0", author="A1", enabled=True),
            ModuleInfo(id="m2", name="Module 2", version="2.0", author="A2", enabled=False),
        ]

        with patch("flashdock.core.modules.ModuleManager.list_installed_modules", return_value=sample_modules):
            device = DeviceInfo(serial="DEV_1", brand="google", model="Pixel 7", mode="system", is_rooted=True, root_method="magisk")
            screen.load_for_device(device)

            assert screen._table.rowCount() == 2
            assert "Module 1" in screen._table.item(0, 0).text()
            assert "Module 2" in screen._table.item(1, 0).text()
            assert "Enabled" in screen._table.item(0, 3).text()
            assert "Disabled" in screen._table.item(1, 3).text()

    def test_module_library_tab(self, qapp, mock_deps, tmp_path: Path):
        dm, adb = mock_deps
        screen = ModulesScreen(dm, adb)
        assert screen._tabs.count() == 2
        assert "Installed Modules" in screen._tabs.tabText(0)
        assert "Module Library" in screen._tabs.tabText(1)
        assert screen._lib_table.columnCount() == 5
        assert screen._btn_import_lib is not None
        assert screen._btn_open_lib_folder is not None
