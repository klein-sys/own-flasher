"""
Unit tests -- Brand handlers and unlock flows.
"""

import pytest

from flashdock.brands import (
    BrandHandler,
    UnlockFlow,
    UnlockStep,
    get_brand_handler,
    get_handler_for_device,
    get_all_brands,
)
from flashdock.core.device import DeviceInfo

# Import brand modules to trigger registration
import flashdock.brands.google  # noqa: F401
import flashdock.brands.xiaomi  # noqa: F401
import flashdock.brands.samsung  # noqa: F401
import flashdock.brands.transsion  # noqa: F401
import flashdock.brands.others  # noqa: F401


# ===================================================================
# Registry tests
# ===================================================================

class TestBrandRegistry:
    def test_google_registered(self):
        h = get_brand_handler("google")
        assert h is not None
        assert h.brand_id == "google"

    def test_samsung_registered(self):
        h = get_brand_handler("samsung")
        assert h is not None

    def test_xiaomi_registered(self):
        h = get_brand_handler("xiaomi")
        assert h is not None

    def test_redmi_registered(self):
        h = get_brand_handler("redmi")
        assert h is not None

    def test_poco_registered(self):
        h = get_brand_handler("poco")
        assert h is not None

    def test_oneplus_registered(self):
        h = get_brand_handler("oneplus")
        assert h is not None

    def test_motorola_registered(self):
        h = get_brand_handler("motorola")
        assert h is not None

    def test_sony_registered(self):
        h = get_brand_handler("sony")
        assert h is not None

    def test_tecno_registered(self):
        h = get_brand_handler("tecno")
        assert h is not None
        assert h.brand_id == "tecno"

    def test_infinix_registered(self):
        h = get_brand_handler("infinix")
        assert h is not None
        assert h.brand_id == "infinix"

    def test_itel_registered(self):
        h = get_brand_handler("itel")
        assert h is not None
        assert h.brand_id == "itel"

    def test_transsion_registered(self):
        h = get_brand_handler("transsion")
        assert h is not None
        assert h.brand_id == "transsion"

    def test_generic_registered(self):
        h = get_brand_handler("generic")
        assert h is not None

    def test_unknown_returns_none(self):
        h = get_brand_handler("nonexistent_brand_xyz")
        assert h is None

    def test_get_all_brands(self):
        brands = get_all_brands()
        assert len(brands) >= 8  # google, samsung, xiaomi, redmi, poco, oneplus, moto, sony, generic

    def test_get_handler_for_device_google(self):
        device = DeviceInfo(brand="google")
        h = get_handler_for_device(device)
        assert h is not None
        assert h.brand_id == "google"

    def test_get_handler_for_device_unknown(self):
        device = DeviceInfo(brand="weirdphone")
        h = get_handler_for_device(device)
        assert h is not None
        assert h.brand_id == "generic"


# ===================================================================
# Unlock flow model tests
# ===================================================================

class TestUnlockStep:
    def test_defaults(self):
        s = UnlockStep(index=1, title="Test", description="Desc")
        assert s.index == 1
        assert s.completed is False
        assert s.action == ""

    def test_auto_step(self):
        s = UnlockStep(index=1, title="T", description="D", action="auto",
                       command_preview="fastboot oem unlock")
        assert s.action == "auto"
        assert "fastboot" in s.command_preview


class TestUnlockFlow:
    def test_defaults(self):
        f = UnlockFlow(brand="test", brand_display="Test")
        assert f.wipes_data is True
        assert f.supports_relock is True
        assert f.steps == []


# ===================================================================
# Google flow tests
# ===================================================================

class TestGoogleFlow:
    def _device(self):
        return DeviceInfo(
            brand="google", model="Pixel 7 Pro", device="cheetah",
            bootloader_state="locked", mode="system",
        )

    def test_unlock_flow_has_steps(self):
        h = get_brand_handler("google")
        flow = h.get_unlock_flow(self._device())
        assert len(flow.steps) >= 4
        assert flow.wipes_data is True

    def test_unlock_flow_has_flashing_unlock(self):
        h = get_brand_handler("google")
        flow = h.get_unlock_flow(self._device())
        commands = [s.command_preview for s in flow.steps if s.command_preview]
        assert any("flashing unlock" in c for c in commands)

    def test_relock_flow_has_steps(self):
        h = get_brand_handler("google")
        flow = h.get_relock_flow(self._device())
        assert len(flow.steps) >= 2

    def test_firmware_url(self):
        h = get_brand_handler("google")
        url = h.get_firmware_url(self._device())
        assert "google" in url.lower() or "android" in url.lower()

    def test_warnings_include_data_loss(self):
        h = get_brand_handler("google")
        flow = h.get_unlock_flow(self._device())
        all_text = " ".join(flow.warnings).lower()
        assert "erase" in all_text or "data" in all_text


# ===================================================================
# Samsung flow tests
# ===================================================================

class TestSamsungFlow:
    def _device(self):
        return DeviceInfo(
            brand="samsung", model="Galaxy S24", device="e3q",
            bootloader_state="locked", mode="system",
        )

    def test_unlock_has_knox_warning(self):
        h = get_brand_handler("samsung")
        flow = h.get_unlock_flow(self._device())
        all_text = " ".join(flow.warnings).lower()
        assert "knox" in all_text

    def test_unlock_mentions_carrier(self):
        h = get_brand_handler("samsung")
        flow = h.get_unlock_flow(self._device())
        all_text = " ".join(flow.warnings + flow.prerequisites).lower()
        assert "carrier" in all_text


# ===================================================================
# Xiaomi flow tests
# ===================================================================

class TestXiaomiFlow:
    def _device(self):
        return DeviceInfo(
            brand="xiaomi", model="Redmi Note 12", device="ruby",
            bootloader_state="locked", mode="system",
        )

    def test_has_waiting_period(self):
        h = get_brand_handler("xiaomi")
        flow = h.get_unlock_flow(self._device())
        assert flow.waiting_period != ""

    def test_has_mi_account_prerequisite(self):
        h = get_brand_handler("xiaomi")
        flow = h.get_unlock_flow(self._device())
        prereqs = " ".join(flow.prerequisites).lower()
        assert "mi account" in prereqs

    def test_more_steps_than_google(self):
        h = get_brand_handler("xiaomi")
        flow = h.get_unlock_flow(self._device())
        assert len(flow.steps) >= 6


# ===================================================================
# Motorola flow tests
# ===================================================================

class TestMotorolaFlow:
    def _device(self):
        return DeviceInfo(brand="motorola", model="Edge 40", mode="system")

    def test_has_unlock_code_step(self):
        h = get_brand_handler("motorola")
        flow = h.get_unlock_flow(self._device())
        step_titles = [s.title.lower() for s in flow.steps]
        assert any("code" in t or "unlock data" in t for t in step_titles)


# ===================================================================
# Generic flow tests
# ===================================================================

class TestGenericFlow:
    def test_works_for_unknown_brand(self):
        device = DeviceInfo(brand="weirdphone", model="XYZ-100", mode="system")
        h = get_handler_for_device(device)
        flow = h.get_unlock_flow(device)
        assert len(flow.steps) >= 3
        assert "weirdphone" in flow.warnings[0].lower() or "generic" in flow.brand.lower()


# ===================================================================
# OnePlus flow tests
# ===================================================================

class TestOnePlusFlow:
    def _device(self):
        return DeviceInfo(brand="oneplus", model="OnePlus 11", mode="system")

    def test_unlock_flow_has_steps(self):
        h = get_brand_handler("oneplus")
        flow = h.get_unlock_flow(self._device())
        assert len(flow.steps) >= 4
        assert flow.wipes_data is True

    def test_unlock_command(self):
        h = get_brand_handler("oneplus")
        flow = h.get_unlock_flow(self._device())
        commands = [s.command_preview for s in flow.steps if s.command_preview]
        assert any("oem unlock" in c for c in commands)

    def test_relock_flow(self):
        h = get_brand_handler("oneplus")
        flow = h.get_relock_flow(self._device())
        assert len(flow.steps) >= 2
        commands = [s.command_preview for s in flow.steps if s.command_preview]
        assert any("oem lock" in c for c in commands)


# ===================================================================
# Sony flow tests
# ===================================================================

class TestSonyFlow:
    def _device(self):
        return DeviceInfo(brand="sony", model="Xperia 1 V", mode="system")

    def test_has_drm_warning(self):
        h = get_brand_handler("sony")
        flow = h.get_unlock_flow(self._device())
        warnings = " ".join(flow.warnings).lower()
        assert "drm" in warnings or "camera" in warnings

    def test_has_imei_prereq(self):
        h = get_brand_handler("sony")
        flow = h.get_unlock_flow(self._device())
        prereqs = " ".join(flow.prerequisites).lower()
        assert "imei" in prereqs

    def test_guide_url_present(self):
        h = get_brand_handler("sony")
        flow = h.get_unlock_flow(self._device())
        assert "developer.sony.com" in flow.guide_url


# ===================================================================
# Fastboot unlock commands unit tests
# ===================================================================

class TestFastbootUnlockCommands:
    def test_oem_unlock_dry_run(self):
        from flashdock.tools.fastboot import Fastboot
        fb = Fastboot(binary="dummy_fastboot", dry_run=True)
        res = fb.oem_unlock(serial="TEST_SERIAL")
        assert res.command == ["dummy_fastboot", "-s", "TEST_SERIAL", "oem", "unlock"]
        assert res.return_code == 0
        assert res.success is True

    def test_oem_unlock_with_code_dry_run(self):
        from flashdock.tools.fastboot import Fastboot
        fb = Fastboot(binary="dummy_fastboot", dry_run=True)
        res = fb.oem_unlock(code="ABC123XYZ", serial="TEST_SERIAL")
        assert res.command == ["dummy_fastboot", "-s", "TEST_SERIAL", "oem", "unlock", "ABC123XYZ"]
        assert res.return_code == 0
        assert res.success is True

    def test_flashing_unlock_dry_run(self):
        from flashdock.tools.fastboot import Fastboot
        fb = Fastboot(binary="dummy_fastboot", dry_run=True)
        res = fb.flashing_unlock(serial="TEST_SERIAL")
        assert res.command == ["dummy_fastboot", "-s", "TEST_SERIAL", "flashing", "unlock"]
        assert res.return_code == 0
        assert res.success is True

    def test_oem_lock_dry_run(self):
        from flashdock.tools.fastboot import Fastboot
        fb = Fastboot(binary="dummy_fastboot", dry_run=True)
        res = fb.oem_lock(serial="TEST_SERIAL")
        assert res.command == ["dummy_fastboot", "-s", "TEST_SERIAL", "oem", "lock"]
        assert res.return_code == 0
        assert res.success is True

    def test_flashing_lock_dry_run(self):
        from flashdock.tools.fastboot import Fastboot
        fb = Fastboot(binary="dummy_fastboot", dry_run=True)
        res = fb.flashing_lock(serial="TEST_SERIAL")
        assert res.command == ["dummy_fastboot", "-s", "TEST_SERIAL", "flashing", "lock"]
        assert res.return_code == 0
        assert res.success is True


class TestTranssionFlows:
    def test_tecno_unlock_flow(self):
        h = get_brand_handler("tecno")
        flow = h.get_unlock_flow(DeviceInfo(brand="Tecno", chipset="mediatek"))
        assert flow.brand == "tecno"
        assert flow.wipes_data is True
        assert len(flow.steps) >= 5

    def test_infinix_unlock_flow(self):
        h = get_brand_handler("infinix")
        flow = h.get_unlock_flow(DeviceInfo(brand="Infinix"))
        assert flow.brand == "infinix"
        assert "XOS" in flow.brand_display

    def test_itel_unlock_flow(self):
        h = get_brand_handler("itel")
        flow = h.get_unlock_flow(DeviceInfo(brand="itel"))
        assert flow.brand == "itel"
        assert flow.supports_relock is True

