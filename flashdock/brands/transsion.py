"""
FlashDock — Transsion Holdings (Tecno, Infinix, itel) Brand Handlers.

Covers bootloader unlock, re-lock, firmware channels, and hardware key recovery
for Tecno (HiOS), Infinix (XOS), and itel (itelOS) devices powered by MediaTek
(Helio G35/G85/G88/G96/G99, Dimensity) and Unisoc (T606/T612/T616/SC9863A).
"""

from __future__ import annotations

from flashdock.brands import BrandHandler, UnlockFlow, UnlockStep, register_brand
from flashdock.core.device import DeviceInfo


class TranssionBaseHandler(BrandHandler):
    """Base handler for all Transsion Holdings brands."""

    _BRAND_ID: str = "transsion"
    _BRAND_DISPLAY: str = "Transsion Holdings"
    _OS_NAME: str = "HiOS / XOS / itelOS"
    _PORTAL_URL: str = "https://www.carlcare.com/"

    @property
    def brand_id(self) -> str:
        return self._BRAND_ID

    @property
    def brand_display(self) -> str:
        return self._BRAND_DISPLAY

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        chipset_note = ""
        if device.chipset_family == "mediatek":
            chipset_note = " (MediaTek Helio / Dimensity chipset detected — standard fastboot flashing unlock supported)"
        elif device.chipset_family == "unisoc":
            chipset_note = " (Unisoc chipset detected — fastboot flashing unlock supported)"

        return UnlockFlow(
            brand=self.brand_id,
            brand_display=self.brand_display,
            prerequisites=[
                f"USB debugging enabled in {self._OS_NAME} Developer options",
                "OEM unlocking toggled ON in Developer options (Settings > System > Developer options)",
                "Complete backup of personal photos, messages, and files (unlock completely wipes userdata)",
                "Battery charged to ≥ 50%",
                "PC connected directly to USB-A / USB 2.0 port with high-quality data cable",
            ],
            warnings=[
                f"Unlocking the bootloader will COMPLETELY ERASE ALL USER DATA on your {self.brand_display} device.",
                f"Your phone will reboot into factory recovery to format /data.",
                "Warranty through Carlcare may be affected depending on region.",
                "Google Play Integrity will require Magisk/KernelSU with Play Integrity Fix module.",
            ],
            firmware_url=self._PORTAL_URL,
            guide_url="https://forum.hovatek.com/forum-89.html",
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(
                    index=1,
                    title="Enable Developer Options",
                    description=(
                        f"On your phone, open Settings > My Phone (or About Phone).\n"
                        "Locate 'Build Number' and tap it rapidly 7 times until you see 'You are now a developer!'."
                    ),
                    action="manual",
                ),
                UnlockStep(
                    index=2,
                    title="Enable OEM Unlocking & USB Debugging",
                    description=(
                        "Go to Settings > System > Developer options.\n"
                        "1. Turn ON 'OEM unlocking' (enter your lock screen PIN to confirm).\n"
                        "2. Turn ON 'USB debugging'."
                    ),
                    action="manual",
                ),
                UnlockStep(
                    index=3,
                    title="Reboot to Fastboot / Bootloader",
                    description=(
                        f"Reboot the {self.brand_display} phone into fastboot mode via ADB.\n"
                        "The screen will show 'FASTBOOT...' in small white text."
                    ),
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="adb reboot bootloader",
                ),
                UnlockStep(
                    index=4,
                    title="Send Fastboot Unlock Command",
                    description=(
                        f"Send standard unlock command to the device{chipset_note}.\n"
                        "Some newer models require 'fastboot flashing unlock_critical' as well."
                    ),
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot flashing unlock",
                    warning="THIS WILL ERASE ALL USERDATA ON CONFIRMATION.",
                ),
                UnlockStep(
                    index=5,
                    title="Confirm on Phone Screen with Volume Up",
                    description=(
                        "Look at your phone screen: a confirmation prompt will appear.\n"
                        "Press the physical VOLUME UP button on your phone to confirm unlock and erase data.\n"
                        "(Pressing Volume Down will cancel without wiping)."
                    ),
                    action="manual",
                    warning="Press Volume Up to confirm, or Volume Down to abort.",
                ),
                UnlockStep(
                    index=6,
                    title="Reboot System",
                    description="Reboot the phone into system mode. First boot after factory wipe takes 3-5 minutes.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot reboot",
                ),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand=self.brand_id,
            brand_display=self.brand_display,
            wipes_data=True,
            supports_relock=True,
            warnings=[
                f"Re-locking the bootloader on {self.brand_display} WIPES ALL USERDATA.",
                "CRITICAL WARNING: NEVER re-lock the bootloader if you have custom ROMs, GSIs, "
                "TWRP, or Magisk/KernelSU installed! The phone will hard-brick upon dm-verity verification.",
                "Ensure 100% untouched stock firmware from Carlcare / Official ROM is flashed first.",
            ],
            steps=[
                UnlockStep(
                    index=1,
                    title="Verify 100% Stock Firmware",
                    description="Ensure stock boot, init_boot, dtbo, vendor_boot, and vbmeta are completely restored.",
                    action="manual",
                    warning="Re-locking on modified firmware causes immediate bootloops or Red State bricks.",
                ),
                UnlockStep(
                    index=2,
                    title="Reboot to Fastboot",
                    description="Reboot device into fastboot mode.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="adb reboot bootloader",
                ),
                UnlockStep(
                    index=3,
                    title="Lock Bootloader",
                    description="Send fastboot flashing lock command.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot flashing lock",
                    warning="WILL ERASE USERDATA. Confirm with Volume Up on the phone screen.",
                ),
                UnlockStep(
                    index=4,
                    title="Confirm Re-lock on Phone",
                    description="Press Volume Up button on device to confirm locking.",
                    action="manual",
                ),
            ],
        )

    def get_firmware_url(self, device: DeviceInfo) -> str:
        return self._PORTAL_URL

    def get_warnings(self, device: DeviceInfo) -> list[str]:
        return [
            f"Transsion devices ({self.brand_display}) use dm-verity and avb 2.0.",
            "Always keep a backup of stock boot.img and vbmeta.img before flashing any Magisk patch or GSI.",
            "If your phone enters 'Red State: Your device has failed verification', use FlashDock's Fix Bricked Phone or MTK BROM tool to restore stock vbmeta.",
        ]


class TecnoHandler(TranssionBaseHandler):
    """Tecno Mobile (HiOS) brand handler."""
    _BRAND_ID = "tecno"
    _BRAND_DISPLAY = "Tecno (HiOS)"
    _OS_NAME = "HiOS"
    _PORTAL_URL = "https://www.tecno-mobile.com/"


class InfinixHandler(TranssionBaseHandler):
    """Infinix Mobility (XOS) brand handler."""
    _BRAND_ID = "infinix"
    _BRAND_DISPLAY = "Infinix (XOS)"
    _OS_NAME = "XOS"
    _PORTAL_URL = "https://www.infinixmobility.com/"


class ItelHandler(TranssionBaseHandler):
    """itel Mobile (itelOS) brand handler."""
    _BRAND_ID = "itel"
    _BRAND_DISPLAY = "itel (itelOS)"
    _OS_NAME = "itelOS"
    _PORTAL_URL = "https://www.itel-life.com/"


class TranssionGenericHandler(TranssionBaseHandler):
    """Transsion Holdings generic umbrella handler."""
    _BRAND_ID = "transsion"
    _BRAND_DISPLAY = "Transsion (Tecno / Infinix / itel)"
    _OS_NAME = "HiOS / XOS / itelOS"
    _PORTAL_URL = "https://www.carlcare.com/"


# Register all Transsion brand handlers
register_brand(TecnoHandler())
register_brand(InfinixHandler())
register_brand(ItelHandler())
register_brand(TranssionGenericHandler())
