"""
FlashDock — Samsung brand handler.

Samsung uses Download mode + Odin (or Heimdall) for flashing.
Bootloader unlock is limited — many carrier models cannot unlock.
"""

from __future__ import annotations

from flashdock.brands import BrandHandler, UnlockFlow, UnlockStep, register_brand
from flashdock.core.device import DeviceInfo


class SamsungHandler(BrandHandler):
    @property
    def brand_id(self) -> str:
        return "samsung"

    @property
    def brand_display(self) -> str:
        return "Samsung"

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="samsung",
            brand_display=self.brand_display,
            prerequisites=[
                "USB debugging enabled and authorized",
                "OEM unlocking toggle visible and enabled in Developer options",
                "Phone is NOT a carrier-locked US model (most US Samsungs cannot unlock)",
                "All important data backed up (unlock WIPES the phone)",
                "Samsung account removed (recommended to avoid FRP issues)",
            ],
            warnings=[
                "Many US carrier Samsung phones CANNOT unlock the bootloader.",
                "Unlocking PERMANENTLY trips the Knox warranty fuse (0x1).",
                "Samsung Pay, Samsung Health, Secure Folder will stop working permanently.",
                "Knox warranty void is IRREVERSIBLE even if you re-lock.",
                "Unlocking ERASES ALL DATA.",
            ],
            firmware_url="https://samfw.com/",
            guide_url="",
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(
                    index=1,
                    title="Check if unlockable",
                    description=(
                        "Go to Settings > Developer options.\n"
                        "If 'OEM unlocking' is present and NOT greyed out, your phone can be unlocked.\n"
                        "If missing or greyed out, your carrier/model does not support unlock."
                    ),
                    action="manual",
                    warning="If OEM unlocking is missing, your phone CANNOT be unlocked. Do not proceed.",
                ),
                UnlockStep(
                    index=2,
                    title="Enable OEM unlocking",
                    description="Toggle 'OEM unlocking' ON in Developer options.",
                    action="manual",
                ),
                UnlockStep(
                    index=3,
                    title="Reboot to bootloader (Download mode)",
                    description=(
                        "Power off the phone, then hold Volume Down + USB cable to enter Download mode.\n"
                        "Or use ADB: adb reboot bootloader"
                    ),
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="adb reboot bootloader",
                ),
                UnlockStep(
                    index=4,
                    title="Long-press Volume Up to unlock",
                    description=(
                        "In Download mode, press and hold Volume Up for 7 seconds.\n"
                        "A warning screen will appear. Press Volume Up again to confirm.\n"
                        "The phone will wipe and reboot."
                    ),
                    action="manual",
                    warning="THIS WILL TRIP KNOX AND ERASE ALL DATA. This is IRREVERSIBLE.",
                ),
                UnlockStep(
                    index=5,
                    title="Wait for reboot",
                    description="The phone will factory reset and reboot. Initial setup required.",
                    action="auto",
                ),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="samsung",
            brand_display=self.brand_display,
            wipes_data=True,
            supports_relock=True,
            warnings=[
                "Re-locking will erase all data.",
                "Knox fuse will remain tripped (0x1) regardless.",
                "Flash stock firmware with Odin before re-locking.",
            ],
            steps=[
                UnlockStep(
                    index=1,
                    title="Flash stock firmware via Odin",
                    description="Use Odin or Heimdall to flash a stock firmware first.",
                    action="manual",
                    warning="Re-locking with modified firmware can soft-brick the device.",
                ),
                UnlockStep(
                    index=2,
                    title="Enable OEM unlocking toggle",
                    description="Settings > Developer options > OEM unlocking ON (yes, to re-lock).",
                    action="manual",
                ),
                UnlockStep(
                    index=3,
                    title="Lock via fastboot",
                    description="Reboot to Download mode and lock the bootloader.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot oem lock",
                ),
            ],
        )

    def get_firmware_url(self, device: DeviceInfo) -> str:
        return "https://samfw.com/"

    def get_warnings(self, device: DeviceInfo) -> list[str]:
        return [
            "Samsung unlock permanently trips the Knox fuse.",
            "Samsung Pay, Secure Folder, and some banking apps will stop working.",
            "US carrier models usually cannot be unlocked.",
        ]


register_brand(SamsungHandler())
