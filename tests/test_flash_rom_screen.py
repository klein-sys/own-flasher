"""
Unit tests — FlashRomScreen UI widget.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.repository import StoredItem
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.screens.flash_rom_screen import FlashRomScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def mock_deps():
    dm = MagicMock(spec=DeviceManager)
    dm.device = None
    fb = MagicMock(spec=Fastboot)
    return dm, fb


class TestFlashRomScreenUI:
    def test_init_ui(self, qapp, mock_deps):
        dm, fb = mock_deps
        screen = FlashRomScreen(dm, fb)
        assert screen._tabs.count() == 5
        assert screen._tabs.tabText(0) == "Custom ROM"
        assert screen._tabs.tabText(1) == "Treble GSI"
        assert screen._tabs.tabText(2) == "Custom Recovery"
        assert screen._tabs.tabText(3) == "Local ROM Library"
        assert screen._tabs.tabText(4) == "Guides & Help"

    def test_load_for_device_fastboot_dynamic(self, qapp, mock_deps):
        dm, fb = mock_deps
        screen = FlashRomScreen(dm, fb)
        device = DeviceInfo(
            brand="google",
            model="Pixel 7",
            device="panther",
            mode="fastboot",
            bootloader_state="unlocked",
            has_dynamic_partitions=True,
            active_slot="a",
            battery_level=85,
        )
        screen.load_for_device(device)

        assert "panther" in screen._device_banner.text()
        assert "FASTBOOT" in screen._lbl_fb_mode.text()
        assert screen._btn_switch_fastbootd.isEnabled() is True
        assert "boot" in screen._lbl_rec_target.text()

    def test_load_for_device_fastbootd_mode(self, qapp, mock_deps):
        dm, fb = mock_deps
        screen = FlashRomScreen(dm, fb)
        device = DeviceInfo(
            brand="google",
            model="Pixel 8",
            mode="fastbootd",
            bootloader_state="unlocked",
            has_dynamic_partitions=True,
            active_slot="b",
            battery_level=90,
        )
        screen.load_for_device(device)

        assert "FASTBOOTD" in screen._lbl_fb_mode.text()
        assert screen._btn_switch_fastbootd.isEnabled() is False

    def test_inspect_rom_folder(self, qapp, mock_deps, tmp_path: Path):
        dm, fb = mock_deps
        screen = FlashRomScreen(dm, fb)

        rom_dir = tmp_path / "LineageOS"
        rom_dir.mkdir()
        (rom_dir / "boot.img").write_bytes(b"DATA")
        (rom_dir / "system.img").write_bytes(b"DATA2")

        screen._inspect_rom_package(str(rom_dir))
        assert screen._parsed_rom is not None
        assert screen._rom_table.rowCount() == 2
        assert "2 partitions" in screen._lbl_rom_info.text()

    def test_inspect_gsi_and_recovery(self, qapp, mock_deps, tmp_path: Path):
        dm, fb = mock_deps
        screen = FlashRomScreen(dm, fb)

        gsi_file = tmp_path / "system-arm64-ab-gapps.img"
        gsi_file.write_bytes(b"GSI_BYTES")
        screen._edit_gsi_path.setText(str(gsi_file))
        ok, info, _ = screen._rom_flasher.parse_gsi(gsi_file)
        screen._parsed_gsi = info
        screen._lbl_gsi_badge.setText(f"✅ {info.name}")
        assert "system-arm64-ab-gapps" in screen._lbl_gsi_badge.text()

        rec_file = tmp_path / "twrp-3.7.0.img"
        rec_file.write_bytes(b"RECOVERY_BYTES")
        screen._edit_rec_path.setText(str(rec_file))
        ok, r_info, _ = screen._rom_flasher.parse_recovery_image(rec_file)
        screen._parsed_recovery = r_info
        assert r_info.recovery_type == "TWRP"

    def test_use_library_item(self, qapp, mock_deps, tmp_path: Path):
        dm, fb = mock_deps
        screen = FlashRomScreen(dm, fb)

        rom_file = tmp_path / "TestROM.zip"
        rom_file.write_bytes(b"FAKE_ZIP")
        item = StoredItem(
            id="testrom",
            name="TestROM.zip",
            category="rom",
            file_path=rom_file,
            size_bytes=1000,
        )

        screen._use_library_item(item)
        assert screen._tabs.currentIndex() == 0  # Switched to Custom ROM tab
        assert screen._edit_rom_path.text() == str(rom_file)
