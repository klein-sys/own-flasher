"""
FlashDock — Xiaomi / Redmi / POCO brand handler.

Xiaomi's unlock requires a Mi account, binding, and a waiting period
(typically 72-168 hours).  The actual unlock is done via the official
Mi Unlock tool or fastboot after approval.
"""

from __future__ import annotations

from flashdock.brands import BrandHandler, UnlockFlow, UnlockStep, register_brand
from flashdock.core.device import DeviceInfo


class XiaomiHandler(BrandHandler):
    @property
    def brand_id(self) -> str:
        return "xiaomi"

    @property
    def brand_display(self) -> str:
        return "Xiaomi / Redmi / POCO"

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="xiaomi",
            brand_display=self.brand_display,
            waiting_period="72-168 hours (varies by model)",
            prerequisites=[
                "Mi account created and logged in on the phone",
                "Mi account bound to the device (Settings > Mi Unlock Status)",
                "Waiting period completed (72-168 hours after binding)",
                "SIM card inserted (required for binding on some models)",
                "USB debugging enabled and authorized",
                "All important data backed up (unlock WIPES the phone)",
            ],
            warnings=[
                "Unlocking ERASES ALL DATA on the phone.",
                "You MUST use a Mi account and wait 72-168 hours before unlocking.",
                "Using the official Mi Unlock tool (Windows) is the supported method.",
                "FlashDock can verify prerequisites, but the actual unlock uses fastboot oem unlock.",
                "Some carrier-locked Xiaomi phones cannot be unlocked.",
            ],
            firmware_url="https://xiaomifirmwareupdater.com/",
            guide_url="https://en.miui.com/unlock/",
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(
                    index=1,
                    title="Create Mi account",
                    description="Create a Xiaomi account at account.xiaomi.com if you don't have one.",
                    action="manual",
                ),
                UnlockStep(
                    index=2,
                    title="Add Mi account to phone",
                    description=(
                        "Go to Settings > Mi account and sign in.\n"
                        "Make sure a SIM card is inserted."
                    ),
                    action="manual",
                ),
                UnlockStep(
                    index=3,
                    title="Bind account for unlock",
                    description=(
                        "Go to Settings > Developer options > Mi Unlock status.\n"
                        "Tap 'Add account and device'. This starts the waiting period."
                    ),
                    action="manual",
                ),
                UnlockStep(
                    index=4,
                    title="Wait for the unlock period",
                    description=(
                        "Xiaomi requires a waiting period of 72-168 hours after binding.\n"
                        "You can check the remaining time in the Mi Unlock tool."
                    ),
                    action="manual",
                    warning="There is no way to skip the waiting period.",
                ),
                UnlockStep(
                    index=5,
                    title="Enable USB debugging",
                    description="Settings > Developer options > USB debugging ON.",
                    action="manual",
                ),
                UnlockStep(
                    index=6,
                    title="Reboot to bootloader",
                    description="The phone will restart into fastboot mode.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="adb reboot bootloader",
                ),
                UnlockStep(
                    index=7,
                    title="Unlock the bootloader",
                    description=(
                        "Send the unlock command via fastboot.\n"
                        "If the waiting period is not complete, this will fail with an error."
                    ),
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot oem unlock",
                    warning="THIS WILL ERASE ALL DATA.",
                ),
                UnlockStep(
                    index=8,
                    title="Wait for reboot",
                    description="The phone will factory reset and reboot. This takes a few minutes.",
                    action="auto",
                ),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="xiaomi",
            brand_display=self.brand_display,
            wipes_data=True,
            supports_relock=True,
            warnings=[
                "Re-locking will ERASE ALL DATA.",
                "Make sure you are running STOCK MIUI/HyperOS firmware.",
                "Re-locking with modified firmware can BRICK the device.",
            ],
            steps=[
                UnlockStep(
                    index=1,
                    title="Flash stock firmware",
                    description="Restore the phone to stock MIUI/HyperOS firmware first.",
                    action="manual",
                    warning="Re-locking with custom ROM or modified boot will brick the device!",
                ),
                UnlockStep(
                    index=2,
                    title="Reboot to bootloader",
                    description="Restart into fastboot mode.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="adb reboot bootloader",
                ),
                UnlockStep(
                    index=3,
                    title="Lock the bootloader",
                    description="Send the lock command.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot oem lock",
                    warning="THIS WILL ERASE ALL DATA.",
                ),
            ],
        )

    def get_firmware_url(self, device: DeviceInfo) -> str:
        return "https://xiaomifirmwareupdater.com/"

    def get_warnings(self, device: DeviceInfo) -> list[str]:
        return [
            "Xiaomi unlock requires a Mi account and 72-168 hour waiting period.",
            "Unlocking erases all data.",
        ]


# Also register for sub-brands
class RedmiHandler(XiaomiHandler):
    @property
    def brand_id(self) -> str:
        return "redmi"

    @property
    def brand_display(self) -> str:
        return "Redmi (Xiaomi)"


class PocoHandler(XiaomiHandler):
    @property
    def brand_id(self) -> str:
        return "poco"

    @property
    def brand_display(self) -> str:
        return "POCO (Xiaomi)"


register_brand(XiaomiHandler())
register_brand(RedmiHandler())
register_brand(PocoHandler())
