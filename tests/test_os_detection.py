"""
Unit tests — OS Modification & Root Status Detection.
"""

from unittest.mock import MagicMock
import pytest

from flashdock.core.device import DeviceDetector, DeviceInfo
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot


class TestOSModificationDetection:
    def test_detect_gsi_phh(self):
        detector = DeviceDetector(MagicMock(spec=ADB), MagicMock(spec=Fastboot))
        props = {
            "ro.build.flavor": "treble_arm64_bvN-userdebug",
            "ro.product.device": "phh_gsi",
            "ro.build.version.release": "14",
        }
        dev = DeviceInfo()
        os_type, os_name = detector._detect_os_type(props, dev)
        assert os_type == "gsi"
        assert "GSI" in os_name

    def test_detect_custom_rom_lineage(self):
        detector = DeviceDetector(MagicMock(spec=ADB), MagicMock(spec=Fastboot))
        props = {
            "ro.lineage.version": "21.0-20240501-NIGHTLY-cheetah",
            "ro.build.display.id": "lineage_cheetah-userdebug 14",
        }
        dev = DeviceInfo()
        os_type, os_name = detector._detect_os_type(props, dev)
        assert os_type == "custom_rom"
        assert "LineageOS" in os_name

    def test_detect_custom_rom_crdroid(self):
        detector = DeviceDetector(MagicMock(spec=ADB), MagicMock(spec=Fastboot))
        props = {
            "ro.crdroid.version": "10.4",
            "ro.build.display.id": "crDroidAndroid-14.0-20240501",
        }
        dev = DeviceInfo()
        os_type, os_name = detector._detect_os_type(props, dev)
        assert os_type == "custom_rom"
        assert "crDroid" in os_name

    def test_detect_stock_oem(self):
        detector = DeviceDetector(MagicMock(spec=ADB), MagicMock(spec=Fastboot))
        props = {
            "ro.product.brand": "Google",
            "ro.build.tags": "release-keys",
            "ro.build.display.id": "UQ1A.240205.002",
        }
        dev = DeviceInfo(brand="Google")
        os_type, os_name = detector._detect_os_type(props, dev)
        assert os_type == "stock"
        assert "Google Stock" in os_name

    def test_device_info_display_properties(self):
        dev_rooted = DeviceInfo(is_rooted=True, root_method="magisk", os_type="stock", brand="Google")
        assert dev_rooted.root_display == "Rooted (Magisk)"
        assert "Stock OEM (Google)" in dev_rooted.os_display

        dev_stock_clean = DeviceInfo(is_rooted=False, os_type="stock", brand="Samsung")
        assert dev_stock_clean.root_display == "Not Rooted"
        assert "Stock OEM (Samsung)" in dev_stock_clean.os_display
