"""
Unit tests — Play Integrity Fixer, Diagnostics, and Fingerprint Spoofer (Phase 14).
"""

import json
from unittest.mock import MagicMock, patch
import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.integrity import (
    BUILTIN_PROFILES,
    FingerprintProfile,
    IntegrityDiagnostic,
    PlayIntegrityFixer,
    RECOMMENDED_PROTECTED_PACKAGES,
)
from flashdock.tools.adb import ADB
from flashdock.ui.screens.integrity_screen import IntegrityScreen


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# FingerprintProfile & Vault Tests
# ---------------------------------------------------------------------------

class TestFingerprintProfiles:
    def test_builtin_profiles_exist(self):
        assert len(BUILTIN_PROFILES) >= 5

    def test_all_builtin_profiles_have_safe_api_level(self):
        for prof in BUILTIN_PROFILES:
            assert prof.first_api_level <= 32, f"Profile {prof.id} has API > 32"
            assert prof.fingerprint != ""
            assert prof.security_patch != ""
            assert prof.model != ""

    def test_to_pif_dict(self):
        p = BUILTIN_PROFILES[0]
        p_dict = p.to_pif_dict()
        assert p_dict["MANUFACTURER"] == p.manufacturer
        assert p_dict["FINGERPRINT"] == p.fingerprint
        assert p_dict["FIRST_API_LEVEL"] == str(p.first_api_level)

    def test_to_pif_json(self):
        p = BUILTIN_PROFILES[1]
        json_str = p.to_pif_json()
        parsed = json.loads(json_str)
        assert parsed["MODEL"] == p.model
        assert parsed["PRODUCT"] == p.product


# ---------------------------------------------------------------------------
# PlayIntegrityFixer Logic Tests
# ---------------------------------------------------------------------------

class TestPlayIntegrityFixer:
    @pytest.fixture
    def mock_adb(self):
        return MagicMock(spec=ADB)

    def test_diagnose_disconnected_device(self, mock_adb):
        fixer = PlayIntegrityFixer(adb=mock_adb)
        diag = fixer.diagnose_device(None)
        assert diag.bootloader_status == "Unknown"
        assert diag.verdict_basic == "Unknown"

    def test_diagnose_unlocked_device_without_pif(self, mock_adb):
        fixer = PlayIntegrityFixer(adb=mock_adb)
        dev = DeviceInfo(serial="DEMO_SERIAL", mode="system")

        mock_adb.get_all_props.return_value = {
            "ro.boot.flash.locked": "0",
            "ro.boot.verifiedbootstate": "orange",
        }
        mock_adb.shell.side_effect = [
            ("Enforcing\n", 0),          # getenforce
            ("", 0),                     # which su
            ("Magisk 27.0\n", 0),        # magisk / zygisk
            ("", 0),                     # pif module check
        ]

        diag = fixer.diagnose_device(dev)
        assert diag.bootloader_status == "Unlocked"
        assert diag.selinux_status == "Enforcing"
        assert diag.verdict_basic == "Fail"
        assert diag.verdict_device == "Fail"

    def test_diagnose_unlocked_device_with_pif(self, mock_adb):
        fixer = PlayIntegrityFixer(adb=mock_adb)
        dev = DeviceInfo(serial="DEMO_SERIAL", mode="system", is_rooted=True, root_method="Magisk")

        mock_adb.get_all_props.return_value = {"ro.boot.flash.locked": "0"}
        mock_adb.shell.side_effect = [
            ("Enforcing\n", 0),                     # getenforce
            ("zygisk\n", 0),                        # zygisk check
            ("MODULE_EXISTS\nPIF_JSON_EXISTS", 0),  # module & pif.json
            ('{"BRAND":"google","MODEL":"Pixel 5"}', 0),  # cat pif.json
        ]

        diag = fixer.diagnose_device(dev)
        assert diag.bootloader_status == "Unlocked"
        assert diag.pif_module_installed is True
        assert diag.custom_pif_active is True
        assert "Pixel 5" in diag.current_spoofed_model
        assert diag.verdict_basic == "Pass"
        assert diag.verdict_device == "Pass"

    def test_inject_pif_json_invalid(self, mock_adb):
        fixer = PlayIntegrityFixer(adb=mock_adb)
        ok, msg = fixer.inject_pif_json("SERIAL", "not valid json")
        assert ok is False
        assert "JSON parse error" in msg

        ok2, msg2 = fixer.inject_pif_json("SERIAL", json.dumps({"BRAND": "Google"}))
        assert ok2 is False
        assert "FINGERPRINT" in msg2

    def test_inject_pif_json_success(self, mock_adb):
        fixer = PlayIntegrityFixer(adb=mock_adb)
        mock_adb.push.return_value = True
        mock_adb.shell.side_effect = [
            ("SUCCESS\n", 0),  # copy cmd
            ("DONE\n", 0),     # clear cache cmd
        ]

        prof = BUILTIN_PROFILES[0]
        ok, msg = fixer.inject_profile("TEST_SERIAL", prof, clear_gms=True)
        assert ok is True
        assert "Successfully injected" in msg

    def test_clear_gms_cache(self, mock_adb):
        fixer = PlayIntegrityFixer(adb=mock_adb)
        mock_adb.shell.return_value = ("DONE\n", 0)
        ok, msg = fixer.clear_gms_cache("TEST_SERIAL")
        assert ok is True
        assert "Killed unstable GMS" in msg

    def test_add_package_to_denylist(self, mock_adb):
        fixer = PlayIntegrityFixer(adb=mock_adb)
        mock_adb.shell.return_value = ("", 0)
        ok, msg = fixer.add_package_to_denylist("TEST_SERIAL", "com.paypal.android.p2pmobile")
        assert ok is True
        assert "Added 'com.paypal.android.p2pmobile'" in msg


# ---------------------------------------------------------------------------
# IntegrityScreen UI Tests
# ---------------------------------------------------------------------------

class TestIntegrityScreen:
    @pytest.fixture
    def screen(self, qapp):
        dev_mgr = MagicMock(spec=DeviceManager)
        dev_mgr.device = None
        adb = MagicMock(spec=ADB)
        adb.binary_path = "adb"
        return IntegrityScreen(device_mgr=dev_mgr, adb=adb)

    def test_screen_initial_state(self, screen):
        assert screen._tabs.count() == 3
        assert screen._profile_combo.count() == len(BUILTIN_PROFILES)
        assert screen._card_basic["title"].text() == "Basic Integrity"
        assert screen._card_device["title"].text() == "Device Integrity"

    def test_profile_switch_updates_editor(self, screen):
        screen._profile_combo.setCurrentIndex(1)
        prof = BUILTIN_PROFILES[1]
        assert prof.model in screen._json_edit.toPlainText()
        assert screen._props_table.rowCount() >= 8

    def test_load_for_device_updates_diagnostic(self, screen):
        dev = DeviceInfo(serial="INTEGRITY_DEV", model="Pixel 7", mode="system")
        with patch.object(
            screen._fixer,
            "diagnose_device",
            return_value=IntegrityDiagnostic(
                bootloader_status="Unlocked",
                selinux_status="Enforcing",
                root_type="Magisk",
                zygisk_active=True,
                pif_module_installed=True,
                custom_pif_active=True,
                verdict_basic="Pass",
                verdict_device="Pass",
                verdict_strong="Notice: Keystore Locked BL Only",
            ),
        ):
            screen.load_for_device(dev)

        assert "Pixel 7" in screen._subtitle.text()
        assert "PASS" in screen._card_basic["value"].text()
        assert "PASS" in screen._card_device["value"].text()

    def test_denylist_buttons(self, screen):
        dev = DeviceInfo(serial="INTEGRITY_DEV", model="Pixel 7", mode="system")
        screen._current_device = dev

        with patch.object(screen._fixer, "add_package_to_denylist", return_value=(True, "Added to list")):
            screen._add_denylist_pkg("com.paypal.android.p2pmobile")
            assert "Added to list" in screen._banking_log.text()
