"""
FlashDock — Google / Pixel brand handler.

Covers Pixel 2+ bootloader unlock and re-lock.
Google's flow is the simplest: OEM unlock toggle + fastboot flashing unlock.
"""

from __future__ import annotations

from flashdock.brands import BrandHandler, UnlockFlow, UnlockStep, register_brand
from flashdock.core.device import DeviceInfo


class GoogleHandler(BrandHandler):
    @property
    def brand_id(self) -> str:
        return "google"

    @property
    def brand_display(self) -> str:
        return "Google / Pixel"

    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="google",
            brand_display=self.brand_display,
            prerequisites=[
                "USB debugging enabled and authorized",
                "OEM unlocking enabled in Developer options",
                "All important data backed up (unlock WIPES the phone)",
                "Battery above 60%",
            ],
            warnings=[
                "Unlocking the bootloader will ERASE ALL DATA on the phone.",
                "Your phone will reboot and perform a factory reset.",
                "The bootloader will show an 'unlocked' warning on every boot.",
                "SafetyNet/Play Integrity may fail until you configure root hiding.",
            ],
            firmware_url="https://developers.google.com/android/images",
            guide_url="https://source.android.com/docs/core/architecture/bootloader/locking_unlocking",
            wipes_data=True,
            supports_relock=True,
            steps=[
                UnlockStep(
                    index=1,
                    title="Enable OEM unlocking",
                    description=(
                        "Go to Settings > Developer options and toggle 'OEM unlocking' ON.\n"
                        "If it's greyed out, your carrier may block unlocking."
                    ),
                    action="manual",
                ),
                UnlockStep(
                    index=2,
                    title="Reboot to bootloader",
                    description="The phone will restart into fastboot mode.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="adb reboot bootloader",
                ),
                UnlockStep(
                    index=3,
                    title="Unlock the bootloader",
                    description=(
                        "This sends the unlock command. You MUST confirm on the phone screen\n"
                        "using the volume and power buttons."
                    ),
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot flashing unlock",
                    warning="THIS WILL ERASE ALL DATA. Confirm on the phone screen.",
                ),
                UnlockStep(
                    index=4,
                    title="Confirm on phone",
                    description=(
                        "Use Volume Up/Down to highlight 'Unlock the bootloader' and press Power to confirm.\n"
                        "The phone will wipe and reboot."
                    ),
                    action="manual",
                    warning="If you do NOT confirm, the unlock will be cancelled (no data loss).",
                ),
                UnlockStep(
                    index=5,
                    title="Wait for reboot",
                    description="The phone will factory reset and reboot. This takes a few minutes.",
                    action="auto",
                ),
            ],
        )

    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        return UnlockFlow(
            brand="google",
            brand_display=self.brand_display,
            wipes_data=True,
            supports_relock=True,
            warnings=[
                "Re-locking will ERASE ALL DATA again.",
                "Make sure you are running STOCK firmware before re-locking.",
                "Re-locking with modified firmware can BRICK the device.",
            ],
            steps=[
                UnlockStep(
                    index=1,
                    title="Flash stock firmware",
                    description="Ensure the phone is running unmodified stock firmware.",
                    action="manual",
                    warning="Re-locking with modified firmware can permanently brick the device!",
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
                    description="Send the lock command and confirm on the phone.",
                    action="auto",
                    requires_mode="bootloader",
                    command_preview="fastboot flashing lock",
                    warning="THIS WILL ERASE ALL DATA.",
                ),
            ],
        )

    def get_firmware_url(self, device: DeviceInfo) -> str:
        return "https://developers.google.com/android/images"

    def get_warnings(self, device: DeviceInfo) -> list[str]:
        warnings = ["Pixel bootloader unlock erases all data."]
        if device.anti_rollback_index:
            warnings.append(
                f"Anti-rollback index: {device.anti_rollback_index}. "
                "Do NOT flash older firmware than your current version."
            )
        return warnings


register_brand(GoogleHandler())
