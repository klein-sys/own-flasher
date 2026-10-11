"""
FlashDock — Generic / other brand handlers.

Covers OnePlus, Motorola, Sony, and a fallback generic handler for
unknown brands.  Each uses the standard fastboot oem unlock flow with
brand-specific notes.
"""

from __future__ import annotations

from flashdock.brands import BrandHandler, UnlockFlow, UnlockStep, register_brand
from flashdock.core.device import DeviceInfo


# ===================================================================
# OnePlus
# ===================================================================
class OnePlusHandler(BrandHandler):
    @property
    def brand_id(self) -> str:
        return "oneplus"

    @property
    def brand_display(self) -> str:
        return "OnePlus"

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="oneplus",
            brand_display=self.brand_display,
            prerequisites=[
                "USB debugging enabled and authorized",
                "OEM unlocking enabled in Developer options",
                "All important data backed up (unlock WIPES the phone)",
            ],
            warnings=[
                "Unlocking ERASES ALL DATA on the phone.",
                "OnePlus generally supports unlocking without restrictions.",
            ],
            firmware_url="https://service.oneplus.com/",
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(index=1, title="Enable OEM unlocking",
                           description="Settings > Developer options > OEM unlocking ON.",
                           action="manual"),
                UnlockStep(index=2, title="Reboot to bootloader",
                           description="Restart into fastboot mode.",
                           action="auto", requires_mode="bootloader",
                           command_preview="adb reboot bootloader"),
                UnlockStep(index=3, title="Unlock the bootloader",
                           description="Send the fastboot unlock command.",
                           action="auto", requires_mode="bootloader",
                           command_preview="fastboot oem unlock",
                           warning="THIS WILL ERASE ALL DATA."),
                UnlockStep(index=4, title="Confirm on phone",
                           description="Select 'Unlock the bootloader' on the phone screen.",
                           action="manual"),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="oneplus", brand_display=self.brand_display,
            wipes_data=True, supports_relock=True,
            warnings=["Re-locking erases all data. Use stock firmware first."],
            steps=[
                UnlockStep(index=1, title="Flash stock firmware", description="Restore stock OOS.", action="manual"),
                UnlockStep(index=2, title="Reboot to bootloader", description="Restart into fastboot.",
                           action="auto", requires_mode="bootloader", command_preview="adb reboot bootloader"),
                UnlockStep(index=3, title="Lock bootloader",
                           description="fastboot oem lock", action="auto", requires_mode="bootloader",
                           command_preview="fastboot oem lock", warning="ERASES ALL DATA."),
            ],
        )

    def get_firmware_url(self, device: DeviceInfo) -> str:
        return "https://service.oneplus.com/"


# ===================================================================
# Motorola
# ===================================================================
class MotorolaHandler(BrandHandler):
    @property
    def brand_id(self) -> str:
        return "motorola"

    @property
    def brand_display(self) -> str:
        return "Motorola"

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="motorola",
            brand_display=self.brand_display,
            prerequisites=[
                "Motorola account created",
                "Unlock code obtained from Motorola's website",
                "USB debugging enabled and authorized",
                "OEM unlocking enabled (if available)",
                "All important data backed up",
            ],
            warnings=[
                "You must request an unlock code from Motorola's website.",
                "Not all Motorola models support unlocking.",
                "Unlocking ERASES ALL DATA.",
                "Motorola unlock voids the warranty.",
            ],
            firmware_url="https://mirrors.lolinet.com/firmware/motorola/",
            guide_url="https://motorola-global-portal.custhelp.com/app/standalone/bootloader/unlock-your-device-b",
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(index=1, title="Get your unlock code",
                           description=(
                               "1. Go to motorola-global-portal.custhelp.com\n"
                               "2. Sign in with your Motorola account\n"
                               "3. Follow the steps to get your device's unlock code\n"
                               "4. You will need your device's 'unlock data' string"
                           ), action="manual"),
                UnlockStep(index=2, title="Reboot to bootloader",
                           description="Restart into fastboot mode.",
                           action="auto", requires_mode="bootloader",
                           command_preview="adb reboot bootloader"),
                UnlockStep(index=3, title="Get unlock data",
                           description="Read the unlock data string from the device.",
                           action="auto", requires_mode="bootloader",
                           command_preview="fastboot oem get_unlock_data"),
                UnlockStep(index=4, title="Submit unlock data to Motorola",
                           description="Paste the unlock data on Motorola's website to get your unlock code.",
                           action="manual"),
                UnlockStep(index=5, title="Unlock with code",
                           description="Enter the unlock code received from Motorola.",
                           action="auto", requires_mode="bootloader",
                           command_preview="fastboot oem unlock <YOUR_CODE>",
                           warning="THIS WILL ERASE ALL DATA."),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="motorola", brand_display=self.brand_display,
            wipes_data=True, supports_relock=True,
            steps=[
                UnlockStep(index=1, title="Flash stock firmware", description="Restore stock.", action="manual"),
                UnlockStep(index=2, title="Reboot to bootloader", action="auto", requires_mode="bootloader",
                           description="Restart into fastboot.", command_preview="adb reboot bootloader"),
                UnlockStep(index=3, title="Lock bootloader", action="auto", requires_mode="bootloader",
                           description="Re-lock.", command_preview="fastboot oem lock"),
            ],
        )


# ===================================================================
# Sony
# ===================================================================
class SonyHandler(BrandHandler):
    @property
    def brand_id(self) -> str:
        return "sony"

    @property
    def brand_display(self) -> str:
        return "Sony / Xperia"

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="sony",
            brand_display=self.brand_display,
            prerequisites=[
                "Unlock code obtained from Sony's developer website",
                "USB debugging enabled",
                "IMEI noted (dial *#06#)",
                "All data backed up",
            ],
            warnings=[
                "You must get an unlock code from developer.sony.com/open/",
                "Unlocking voids Sony's warranty and disables some DRM features.",
                "Camera quality may degrade (DRM keys lost) on some Xperia models.",
                "Unlocking ERASES ALL DATA.",
            ],
            firmware_url="https://xperifirm.com/",
            guide_url="https://developer.sony.com/open/",
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(index=1, title="Get unlock code from Sony",
                           description=(
                               "1. Go to developer.sony.com/open/\n"
                               "2. Select your device model\n"
                               "3. Enter your IMEI to get the unlock code"
                           ), action="manual"),
                UnlockStep(index=2, title="Reboot to bootloader",
                           description="Restart into fastboot mode.",
                           action="auto", requires_mode="bootloader",
                           command_preview="adb reboot bootloader"),
                UnlockStep(index=3, title="Unlock with code",
                           description="Send the unlock code.",
                           action="auto", requires_mode="bootloader",
                           command_preview="fastboot oem unlock 0x<YOUR_CODE>",
                           warning="THIS WILL ERASE ALL DATA and void warranty."),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="sony", brand_display=self.brand_display,
            wipes_data=True, supports_relock=True,
            steps=[
                UnlockStep(index=1, title="Flash stock firmware", description="Restore stock.", action="manual"),
                UnlockStep(index=2, title="Reboot to bootloader", action="auto", requires_mode="bootloader",
                           description="Restart into fastboot.", command_preview="adb reboot bootloader"),
                UnlockStep(index=3, title="Lock bootloader", action="auto", requires_mode="bootloader",
                           description="Re-lock.", command_preview="fastboot oem lock"),
            ],
        )


# ===================================================================
# Generic fallback
# ===================================================================
class GenericHandler(BrandHandler):
    @property
    def brand_id(self) -> str:
        return "generic"

    @property
    def brand_display(self) -> str:
        return "Generic / Unknown Brand"

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        brand_name = device.brand.title() if device.brand else "Unknown"
        return UnlockFlow(
            brand="generic",
            brand_display=f"{brand_name} (generic flow)",
            prerequisites=[
                "USB debugging enabled and authorized",
                "OEM unlocking enabled in Developer options (if available)",
                "All important data backed up",
                "Check your brand's official unlock policy",
            ],
            warnings=[
                f"FlashDock does not have a specific handler for '{brand_name}'.",
                "The generic flow uses standard fastboot commands.",
                "Check your brand's documentation for any special requirements.",
                "Unlocking usually ERASES ALL DATA.",
            ],
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(index=1, title="Check brand's unlock policy",
                           description="Search for your brand's bootloader unlock procedure online.",
                           action="manual"),
                UnlockStep(index=2, title="Enable OEM unlocking",
                           description="Settings > Developer options > OEM unlocking ON.",
                           action="manual"),
                UnlockStep(index=3, title="Reboot to bootloader",
                           description="Restart into fastboot mode.",
                           action="auto", requires_mode="bootloader",
                           command_preview="adb reboot bootloader"),
                UnlockStep(index=4, title="Try standard unlock",
                           description="Try the standard fastboot unlock command.",
                           action="auto", requires_mode="bootloader",
                           command_preview="fastboot oem unlock",
                           warning="THIS MAY ERASE ALL DATA."),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="generic", brand_display="Generic",
            wipes_data=True, supports_relock=True,
            steps=[
                UnlockStep(index=1, title="Flash stock firmware", description="Restore stock first.",
                           action="manual", warning="Re-locking with modified firmware can brick!"),
                UnlockStep(index=2, title="Reboot to bootloader", action="auto", requires_mode="bootloader",
                           description="Restart into fastboot.", command_preview="adb reboot bootloader"),
                UnlockStep(index=3, title="Lock bootloader", action="auto", requires_mode="bootloader",
                           description="Re-lock.", command_preview="fastboot oem lock"),
            ],
        )


register_brand(OnePlusHandler())
register_brand(MotorolaHandler())
register_brand(SonyHandler())
register_brand(GenericHandler())
