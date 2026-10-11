"""
Unit tests — Device detection and DeviceManager.
"""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from flashdock.core.device import DeviceDetector, DeviceInfo
from flashdock.core.device_manager import DeviceManager, _REBOOT_MAP
from flashdock.tools.adb import ADB, ADBDevice
from flashdock.tools.fastboot import Fastboot, FastbootDevice


# ===================================================================
# DeviceInfo tests
# ===================================================================

class TestDeviceInfo:
    def test_summary_line_with_brand_model(self):
        d = DeviceInfo(brand="google", model="Pixel 7 Pro", android_version="14")
        assert "Google" in d.summary_line
        assert "Pixel 7 Pro" in d.summary_line
        assert "Android 14" in d.summary_line

    def test_summary_line_empty(self):
        d = DeviceInfo()
        assert "Unknown" in d.summary_line or "device" in d.summary_line.lower()

    def test_chipset_family_qualcomm(self):
        d = DeviceInfo(hardware="qcom", board="msm8998")
        assert d.chipset_family == "snapdragon"

    def test_chipset_family_mediatek(self):
        d = DeviceInfo(hardware="mt6893")
        assert d.chipset_family == "mediatek"

    def test_chipset_family_exynos(self):
        d = DeviceInfo(hardware="exynos990")
        assert d.chipset_family == "exynos"

    def test_chipset_family_unisoc(self):
        d = DeviceInfo(hardware="ums512")
        assert d.chipset_family == "unisoc"

    def test_chipset_family_tensor(self):
        d = DeviceInfo(hardware="tensor")
        assert d.chipset_family == "tensor"

    def test_chipset_family_unknown(self):
        d = DeviceInfo(hardware="")
        assert d.chipset_family == "unknown"

    def test_brand_normalized(self):
        assert DeviceInfo(brand="Google").brand_normalized == "google"
        assert DeviceInfo(brand="Samsung").brand_normalized == "samsung"
        assert DeviceInfo(brand="Xiaomi").brand_normalized == "xiaomi"
        assert DeviceInfo(brand="POCO").brand_normalized == "poco"
        assert DeviceInfo(brand="OnePlus").brand_normalized == "oneplus"
        assert DeviceInfo(brand="Tecno").brand_normalized == "tecno"
        assert DeviceInfo(brand="Infinix").brand_normalized == "infinix"
        assert DeviceInfo(brand="itel").brand_normalized == "itel"
        assert DeviceInfo(brand="WeirdBrand").brand_normalized == "unknown"

    def test_to_dict(self):
        d = DeviceInfo(serial="ABC", brand="google", model="Pixel")
        result = d.to_dict()
        assert result["serial"] == "ABC"
        assert result["brand"] == "google"
        assert isinstance(result, dict)


# ===================================================================
# DeviceDetector tests (mocked ADB/fastboot)
# ===================================================================

class TestDeviceDetectorADB:
    """Test detection via ADB (device in system mode)."""

    def _make_detector(self, adb_devices, props, shell_results=None):
        adb = MagicMock(spec=ADB)
        adb.available = True
        adb.devices.return_value = adb_devices
        adb.get_all_props.return_value = props

        # Default shell results
        default_shell = MagicMock()
        default_shell.success = False
        default_shell.stdout = ""
        if shell_results is None:
            shell_results = {}

        def shell_side_effect(cmd, serial="", timeout=30):
            for key, result in shell_results.items():
                if key in cmd:
                    return result
            return default_shell

        adb.shell.side_effect = shell_side_effect

        fb = MagicMock(spec=Fastboot)
        fb.available = False

        return DeviceDetector(adb, fb)

    def test_detects_pixel_in_system(self):
        adb_devs = [ADBDevice(serial="ZY22FV6BKR", state="device",
                              model="Pixel_7_Pro", device="cheetah")]
        props = {
            "ro.product.brand": "google",
            "ro.product.model": "Pixel 7 Pro",
            "ro.product.device": "cheetah",
            "ro.build.product": "cheetah",
            "ro.product.manufacturer": "Google",
            "ro.build.version.release": "14",
            "ro.build.version.sdk": "34",
            "ro.build.version.security_patch": "2024-01-05",
            "ro.build.display.id": "UP1A.231105.001",
            "ro.build.fingerprint": "google/cheetah/cheetah:14/UP1A.231105.001:userdebug/dev-keys",
            "ro.hardware": "tensor",
            "ro.board.platform": "gs201",
            "ro.product.cpu.abi": "arm64-v8a",
            "ro.boot.flash.locked": "0",
            "sys.oem_unlock_allowed": "1",
            "ro.boot.slot_suffix": "_a",
            "ro.boot.dynamic_partitions": "true",
            "ro.treble.enabled": "true",
            "ro.crypto.state": "encrypted",
        }

        detector = self._make_detector(adb_devs, props)
        info = detector.detect(serial="ZY22FV6BKR")

        assert info.mode == "system"
        assert info.brand == "google"
        assert info.model == "Pixel 7 Pro"
        assert info.device == "cheetah"
        assert info.android_version == "14"
        assert info.bootloader_state == "unlocked"
        assert info.oem_unlock_allowed == "1"
        assert info.slot_scheme == "a/b"
        assert info.active_slot == "a"
        assert info.has_dynamic_partitions is True
        assert info.treble_enabled is True
        assert info.chipset == "tensor"
        assert info.encryption_state == "encrypted"

    def test_unauthorized_device(self):
        adb_devs = [ADBDevice(serial="UNAUTH", state="unauthorized")]
        detector = self._make_detector(adb_devs, {})
        info = detector.detect(serial="UNAUTH")

        assert info.mode == "unauthorized"
        assert len(info.detection_errors) > 0
        assert "authorized" in info.detection_errors[0].lower()

    def test_no_device(self):
        adb = MagicMock(spec=ADB)
        adb.available = True
        adb.devices.return_value = []
        fb = MagicMock(spec=Fastboot)
        fb.available = True
        fb.devices.return_value = []

        detector = DeviceDetector(adb, fb)
        info = detector.detect()
        assert info.mode == "not_connected"


class TestDeviceDetectorFastboot:
    """Test detection via fastboot (device in bootloader mode)."""

    def test_detects_device_in_fastboot(self):
        adb = MagicMock(spec=ADB)
        adb.available = True
        adb.devices.return_value = []

        fb = MagicMock(spec=Fastboot)
        fb.available = True
        fb.devices.return_value = [FastbootDevice(serial="FB123", mode="fastboot")]
        fb.getvar_all.return_value = {
            "product": "cheetah",
            "unlocked": "yes",
            "slot-count": "2",
            "current-slot": "a",
        }

        detector = DeviceDetector(adb, fb)
        info = detector.detect(serial="FB123")

        assert info.mode == "bootloader"
        assert info.product == "cheetah"
        assert info.bootloader_state == "unlocked"
        assert info.slot_scheme == "a/b"
        assert info.active_slot == "a"
        assert info.detection_source == "fastboot"


# ===================================================================
# DeviceManager tests
# ===================================================================

class TestDeviceManager:
    def _make_manager(self):
        from flashdock.config import Config
        config = Config.__new__(Config)
        config._data = {"locked_serial": None, "last_device_serial": None}
        config._lock = __import__("threading").RLock()
        config._path = __import__("pathlib").Path("/tmp/fake_config.json")
        config.save = MagicMock()

        adb = MagicMock(spec=ADB)
        adb.available = True
        fb = MagicMock(spec=Fastboot)
        fb.available = False

        return DeviceManager(config=config, adb=adb, fastboot=fb)

    def test_allowed_reboot_targets_system(self):
        mgr = self._make_manager()
        mgr.device = DeviceInfo(mode="system")
        targets = mgr.allowed_reboot_targets
        assert "recovery" in targets
        assert "bootloader" in targets
        assert "poweroff" in targets

    def test_allowed_reboot_targets_no_device(self):
        mgr = self._make_manager()
        mgr.device = None
        assert mgr.allowed_reboot_targets == []

    def test_serial_lock(self):
        mgr = self._make_manager()
        assert mgr.is_serial_locked is False
        mgr.lock_serial("ABC123")
        assert mgr.is_serial_locked is True
        assert mgr.locked_serial == "ABC123"
        mgr.unlock_serial()
        assert mgr.is_serial_locked is False


class TestRebootMap:
    def test_system_has_all_options(self):
        assert "recovery" in _REBOOT_MAP["system"]
        assert "bootloader" in _REBOOT_MAP["system"]
        assert "poweroff" in _REBOOT_MAP["system"]

    def test_not_connected_has_no_options(self):
        assert _REBOOT_MAP["not_connected"] == []

    def test_edl_has_no_options(self):
        assert _REBOOT_MAP["edl"] == []
