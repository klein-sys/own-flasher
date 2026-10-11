"""
FlashDock — Pre-flash checklist engine.

Runs automated checks against the connected device and local files,
returning a list of :class:`CheckItem` results that the UI renders as
a green/red checklist.  Each failed item includes a human-readable
fix hint.

Spec reference: Section 7.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from flashdock.constants import BACKUPS_DIR, MIN_BATTERY_PERCENT, TOOLS_DIR
from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Check result model
# ---------------------------------------------------------------------------
class CheckStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"      # Non-blocking but worth noting
    SKIP = "skip"      # Cannot check in current mode
    INFO = "info"      # Informational (not a pass/fail)


@dataclass
class CheckItem:
    """One item in the checklist."""
    category: str           # "files", "phone_settings", "safety"
    label: str              # Short description shown to the user
    status: CheckStatus
    detail: str = ""        # Extra info / current value
    fix_hint: str = ""      # What the user should do to fix it
    auto_checked: bool = True  # True if the tool checked this; False if manual

    @property
    def is_ok(self) -> bool:
        return self.status in (CheckStatus.PASS, CheckStatus.INFO, CheckStatus.SKIP)

    @property
    def icon(self) -> str:
        return {
            CheckStatus.PASS: "✅",
            CheckStatus.FAIL: "❌",
            CheckStatus.WARN: "⚠️",
            CheckStatus.SKIP: "⏭️",
            CheckStatus.INFO: "ℹ️",
        }[self.status]


@dataclass
class ChecklistResult:
    """Complete checklist for a device."""
    items: list[CheckItem] = field(default_factory=list)
    device_serial: str = ""
    device_model: str = ""

    @property
    def pass_count(self) -> int:
        return sum(1 for i in self.items if i.status == CheckStatus.PASS)

    @property
    def fail_count(self) -> int:
        return sum(1 for i in self.items if i.status == CheckStatus.FAIL)

    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.items if i.status == CheckStatus.WARN)

    @property
    def total(self) -> int:
        return len(self.items)

    @property
    def all_passed(self) -> bool:
        return self.fail_count == 0

    @property
    def summary(self) -> str:
        return (
            f"{self.pass_count} passed, {self.fail_count} failed, "
            f"{self.warn_count} warnings out of {self.total} checks"
        )


# ---------------------------------------------------------------------------
# Checklist runner
# ---------------------------------------------------------------------------
class ChecklistRunner:
    """Runs the pre-flash checklist against a device and local state."""

    def __init__(self, adb: ADB, device: Optional[DeviceInfo] = None) -> None:
        self._adb = adb
        self._device = device

    def run(self) -> ChecklistResult:
        """Execute all checks and return the result."""
        result = ChecklistResult()

        if self._device:
            result.device_serial = self._device.serial
            result.device_model = self._device.model

        # ---- Phone Settings checks ----
        self._check_phone_settings(result)

        # ---- Files checks ----
        self._check_files(result)

        # ---- Safety checks ----
        self._check_safety(result)

        log.info("Checklist complete: %s", result.summary)
        return result

    # ==================================================================
    # Phone Settings
    # ==================================================================

    def _check_phone_settings(self, result: ChecklistResult) -> None:
        cat = "phone_settings"

        # --- Device connected ---
        if not self._device or self._device.mode == "not_connected":
            result.items.append(CheckItem(
                category=cat,
                label="Device connected via USB",
                status=CheckStatus.FAIL,
                detail="No device detected",
                fix_hint="Connect your phone with a USB cable and enable USB debugging.",
            ))
            # Can't check anything else without a device
            self._add_skipped_phone_settings(result)
            return

        result.items.append(CheckItem(
            category=cat,
            label="Device connected via USB",
            status=CheckStatus.PASS,
            detail=self._device.summary_line,
        ))

        # --- USB debugging authorized ---
        if self._device.mode == "unauthorized":
            result.items.append(CheckItem(
                category=cat,
                label="USB debugging authorized",
                status=CheckStatus.FAIL,
                detail="Device visible but not authorized",
                fix_hint="Check your phone screen for the 'Allow USB debugging' prompt and tap Allow.",
            ))
            self._add_skipped_phone_settings(result)
            return

        if self._device.mode == "system":
            result.items.append(CheckItem(
                category=cat,
                label="USB debugging authorized",
                status=CheckStatus.PASS,
                detail="ADB connection active",
            ))
        else:
            result.items.append(CheckItem(
                category=cat,
                label="USB debugging authorized",
                status=CheckStatus.SKIP,
                detail=f"Device is in {self._device.mode} mode",
                fix_hint="Boot to system to verify USB debugging.",
            ))

        # --- Developer options (inferred from ADB working) ---
        if self._device.mode == "system":
            result.items.append(CheckItem(
                category=cat,
                label="Developer options enabled",
                status=CheckStatus.PASS,
                detail="USB debugging works, so developer options are on",
            ))
        else:
            result.items.append(CheckItem(
                category=cat,
                label="Developer options enabled",
                status=CheckStatus.SKIP,
                detail="Cannot verify outside system mode",
                fix_hint="Go to Settings > About phone > tap Build number 7 times.",
                auto_checked=False,
            ))

        # --- OEM unlocking toggle ---
        if self._device.oem_unlock_allowed == "1":
            result.items.append(CheckItem(
                category=cat,
                label="OEM unlocking enabled",
                status=CheckStatus.PASS,
                detail="OEM unlock toggle is ON",
            ))
        elif self._device.oem_unlock_allowed == "0":
            result.items.append(CheckItem(
                category=cat,
                label="OEM unlocking enabled",
                status=CheckStatus.FAIL,
                detail="OEM unlock toggle is OFF or greyed out",
                fix_hint=(
                    "Go to Settings > Developer options > toggle 'OEM unlocking' ON.\n"
                    "If greyed out, the carrier or brand may block unlocking."
                ),
            ))
        else:
            result.items.append(CheckItem(
                category=cat,
                label="OEM unlocking enabled",
                status=CheckStatus.SKIP if self._device.mode != "system" else CheckStatus.WARN,
                detail="Could not determine OEM unlock status",
                fix_hint="Check Settings > Developer options for the OEM unlocking toggle.",
                auto_checked=self._device.mode == "system",
            ))

        # --- Battery level ---
        if self._device.battery_level >= 0:
            if self._device.battery_level >= MIN_BATTERY_PERCENT:
                result.items.append(CheckItem(
                    category=cat,
                    label=f"Battery above {MIN_BATTERY_PERCENT}%",
                    status=CheckStatus.PASS,
                    detail=f"Battery at {self._device.battery_level}%",
                ))
            else:
                result.items.append(CheckItem(
                    category=cat,
                    label=f"Battery above {MIN_BATTERY_PERCENT}%",
                    status=CheckStatus.FAIL,
                    detail=f"Battery at {self._device.battery_level}%",
                    fix_hint=f"Charge your phone to at least {MIN_BATTERY_PERCENT}% before flashing.",
                ))
        else:
            result.items.append(CheckItem(
                category=cat,
                label=f"Battery above {MIN_BATTERY_PERCENT}%",
                status=CheckStatus.SKIP,
                detail="Cannot read battery level in current mode",
                fix_hint="Boot to system to check battery.",
                auto_checked=False,
            ))

        # --- Good cable / direct USB port (manual check) ---
        result.items.append(CheckItem(
            category=cat,
            label="Good USB cable, direct port (no hub)",
            status=CheckStatus.INFO,
            detail="Manual check — use a quality data cable and a port on the PC, not a hub",
            fix_hint="Use a known-good USB data cable plugged directly into the PC.",
            auto_checked=False,
        ))

        # --- Brand unlock account (manual, brand-specific) ---
        brand = self._device.brand_normalized
        if brand in ("xiaomi", "redmi", "poco"):
            result.items.append(CheckItem(
                category=cat,
                label="Xiaomi Mi Unlock account + waiting period",
                status=CheckStatus.INFO,
                detail="Xiaomi requires a Mi account bound to the phone and a waiting period (up to 168 hours).",
                fix_hint="Link your Mi account in Settings > Mi Unlock, then wait for the required period.",
                auto_checked=False,
            ))
        elif brand == "motorola":
            result.items.append(CheckItem(
                category=cat,
                label="Motorola unlock code obtained",
                status=CheckStatus.INFO,
                detail="Motorola requires an unlock code from their website.",
                fix_hint="Visit motorola-global-portal.custhelp.com to request your unlock code.",
                auto_checked=False,
            ))

        # --- FRP warning ---
        result.items.append(CheckItem(
            category=cat,
            label="Google account password known (FRP)",
            status=CheckStatus.WARN,
            detail="After a factory reset, you will need your Google account credentials to set up the phone.",
            fix_hint="Make sure you know your Google account email and password before proceeding.",
            auto_checked=False,
        ))

    def _add_skipped_phone_settings(self, result: ChecklistResult) -> None:
        """Add SKIP items for settings that can't be checked."""
        cat = "phone_settings"
        for label in [
            "Developer options enabled",
            "OEM unlocking enabled",
            f"Battery above {MIN_BATTERY_PERCENT}%",
            "Good USB cable, direct port (no hub)",
            "Google account password known (FRP)",
        ]:
            result.items.append(CheckItem(
                category=cat, label=label, status=CheckStatus.SKIP,
                detail="Cannot check without an active device connection",
                auto_checked=False,
            ))

    # ==================================================================
    # Files
    # ==================================================================

    def _check_files(self, result: ChecklistResult) -> None:
        cat = "files"

        # --- Platform tools (ADB/fastboot) ---
        if self._adb.available:
            ver = self._adb.version() or "unknown"
            result.items.append(CheckItem(
                category=cat,
                label="ADB / fastboot installed",
                status=CheckStatus.PASS,
                detail=f"ADB version {ver}",
            ))
        else:
            result.items.append(CheckItem(
                category=cat,
                label="ADB / fastboot installed",
                status=CheckStatus.FAIL,
                detail="platform-tools not found",
                fix_hint="Use Downloads & Updates > Tools Manager to install platform-tools, or download from developer.android.com.",
            ))

        # --- USB drivers (Windows-specific) ---
        # We can't programmatically verify drivers easily; mark as manual
        result.items.append(CheckItem(
            category=cat,
            label="USB drivers installed",
            status=CheckStatus.INFO,
            detail="Manual check — install the appropriate USB driver for your phone brand.",
            fix_hint="For Google: Google USB Driver. For Samsung: Samsung USB Driver. For others: check the brand's support page.",
            auto_checked=False,
        ))

        # --- Stock firmware (manual) ---
        result.items.append(CheckItem(
            category=cat,
            label="Stock firmware for this model",
            status=CheckStatus.INFO,
            detail="Have the stock firmware (zip, img, PAC, or tar.md5) for your exact model ready.",
            fix_hint="Download from the official brand site or a trusted source. Verify the codename and build number match.",
            auto_checked=False,
        ))

        # --- Stock boot.img, recovery, vbmeta ---
        result.items.append(CheckItem(
            category=cat,
            label="Stock boot.img, recovery.img, vbmeta.img",
            status=CheckStatus.INFO,
            detail="Needed for rooting (boot.img), recovery flashing, and vbmeta patching.",
            fix_hint="Extract from your stock firmware, or pull from the device using Backup / Restore.",
            auto_checked=False,
        ))

        # --- TWRP / custom recovery (optional) ---
        result.items.append(CheckItem(
            category=cat,
            label="TWRP or custom recovery (if available)",
            status=CheckStatus.INFO,
            detail="Optional — needed for ZIP-based ROM installs and advanced recovery.",
            fix_hint="Download from twrp.me or the recovery's official page. Match your exact device codename.",
            auto_checked=False,
        ))

        # --- Root tool (Magisk/KernelSU/APatch) ---
        result.items.append(CheckItem(
            category=cat,
            label="Magisk, KernelSU, or APatch APK",
            status=CheckStatus.INFO,
            detail="Needed for rooting. Download the latest from the official GitHub releases.",
            fix_hint="Magisk: github.com/topjohnwu/Magisk. KernelSU: github.com/tiann/KernelSU. APatch: github.com/bmax121/APatch.",
            auto_checked=False,
        ))

    # ==================================================================
    # Safety
    # ==================================================================

    def _check_safety(self, result: ChecklistResult) -> None:
        cat = "safety"

        # --- Backup of personal data (manual) ---
        result.items.append(CheckItem(
            category=cat,
            label="Backup of photos, contacts, and app data",
            status=CheckStatus.WARN,
            detail="Unlocking or flashing wipes the phone. Back up everything first.",
            fix_hint="Use Google Backup, Samsung Cloud, or a manual copy of photos/files to your PC.",
            auto_checked=False,
        ))

        # --- Partition backup (check if any backups exist for this device) ---
        has_backup = False
        if self._device and self._device.serial:
            device_backup_dir = BACKUPS_DIR / self._device.serial
            if device_backup_dir.exists() and any(device_backup_dir.iterdir()):
                has_backup = True

        if has_backup:
            result.items.append(CheckItem(
                category=cat,
                label="Stock partition backup (boot, recovery, vbmeta, EFS)",
                status=CheckStatus.PASS,
                detail=f"Backup found in {BACKUPS_DIR / self._device.serial}",
            ))
        else:
            result.items.append(CheckItem(
                category=cat,
                label="Stock partition backup (boot, recovery, vbmeta, EFS)",
                status=CheckStatus.FAIL,
                detail="No partition backup found for this device",
                fix_hint=(
                    "Use Backup / Restore to save your stock boot.img, recovery.img, "
                    "vbmeta.img, and critical partitions (EFS/NVRAM/modem) BEFORE making any changes."
                ),
            ))

        # --- Model and version noted ---
        if self._device and self._device.model and self._device.android_version:
            result.items.append(CheckItem(
                category=cat,
                label="Model, Android version, and security patch noted",
                status=CheckStatus.PASS,
                detail=(
                    f"Model: {self._device.model}, "
                    f"Android: {self._device.android_version}, "
                    f"Patch: {self._device.security_patch or 'unknown'}"
                ),
            ))
        else:
            result.items.append(CheckItem(
                category=cat,
                label="Model, Android version, and security patch noted",
                status=CheckStatus.WARN,
                detail="Could not read full device details",
                fix_hint="Note your model number, Android version, and security patch level manually.",
                auto_checked=False,
            ))

        # --- Bootloader state awareness ---
        if self._device:
            if self._device.bootloader_state == "unlocked":
                result.items.append(CheckItem(
                    category=cat,
                    label="Bootloader state known",
                    status=CheckStatus.PASS,
                    detail="Bootloader is UNLOCKED",
                ))
            elif self._device.bootloader_state == "locked":
                result.items.append(CheckItem(
                    category=cat,
                    label="Bootloader state known",
                    status=CheckStatus.PASS,
                    detail="Bootloader is LOCKED — unlock required before flashing custom images",
                ))
            else:
                result.items.append(CheckItem(
                    category=cat,
                    label="Bootloader state known",
                    status=CheckStatus.WARN,
                    detail="Could not determine bootloader state",
                    fix_hint="Boot to bootloader/fastboot to check, or look in Developer options.",
                ))

        # --- Anti-rollback warning ---
        if self._device and self._device.anti_rollback_index:
            result.items.append(CheckItem(
                category=cat,
                label="Anti-rollback awareness",
                status=CheckStatus.WARN,
                detail=f"Anti-rollback index: {self._device.anti_rollback_index}",
                fix_hint=(
                    "Do NOT flash firmware older than your current anti-rollback index. "
                    "Doing so can permanently brick some devices."
                ),
            ))

        # --- Encryption notice ---
        if self._device and self._device.encryption_state == "encrypted":
            result.items.append(CheckItem(
                category=cat,
                label="Encryption notice",
                status=CheckStatus.INFO,
                detail="Device data is encrypted. Custom recovery may not access data without the decryption key.",
                fix_hint="Format data in recovery if you cannot decrypt, but this ERASES everything.",
            ))
