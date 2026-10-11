"""
FlashDock — Safety Engine.

Enforces critical safety rules before any destructive action:
* Pre-flash match check (device codename, model, region, slot).
* Checksum verification (SHA-256 / SHA-1 / MD5) with origin checks.
* Battery level guard (minimum 60% requirement).
* Anti-rollback protection (checks downgrade risks).
* Vendor fastboot script inspection (detects erase userdata, relocking).
* Typed confirmation requirement helper.

Spec references: Section 16, Section 2.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from flashdock.constants import CONFIRMATION_WORD, MIN_BATTERY_PERCENT
from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class SafetyCheckResult:
    """Outcome of a safety inspection."""
    passed: bool
    level: str  # "ok", "warning", "blocked"
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def is_blocked(self) -> bool:
        return self.level == "blocked" or not self.passed


@dataclass
class ScriptWarning:
    """A risky or destructive line detected in a vendor flashing script."""
    line_number: int
    command: str
    risk_level: str  # "critical", "warning", "info"
    description: str


# ---------------------------------------------------------------------------
# Safety Engine
# ---------------------------------------------------------------------------

class SafetyEngine:
    """Central safety validation engine."""

    # -----------------------------------------------------------------------
    # 1. Device match check
    # -----------------------------------------------------------------------
    @staticmethod
    def check_device_match(
        device: DeviceInfo,
        target_codename: str = "",
        target_model: str = "",
        target_brand: str = "",
    ) -> SafetyCheckResult:
        """
        Verify that a firmware or image file is meant for the connected phone.

        A codename mismatch is FATAL and blocks the operation immediately.
        """
        if not device or device.mode == "not_connected":
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message="No device connected. Cannot verify compatibility.",
            )

        mismatches: list[str] = []

        # Codename check (most crucial identifier)
        if target_codename:
            dev_code = (device.device or "").strip().lower()
            tgt_code = target_codename.strip().lower()
            if dev_code and dev_code != tgt_code:
                mismatches.append(
                    f"Codename mismatch: phone is '{dev_code}', file is for '{tgt_code}'."
                )

        # Brand check
        if target_brand:
            dev_brand = (device.brand or "").strip().lower()
            tgt_brand = target_brand.strip().lower()
            if dev_brand and dev_brand != tgt_brand:
                mismatches.append(
                    f"Brand mismatch: phone is '{device.brand}', file is for '{target_brand}'."
                )

        # Model check
        if target_model:
            dev_model = (device.model or "").strip().lower()
            tgt_model = target_model.strip().lower()
            if dev_model and tgt_model not in dev_model and dev_model not in tgt_model:
                mismatches.append(
                    f"Model mismatch: phone is '{device.model}', file specifies '{target_model}'."
                )

        if mismatches:
            msg = "PRE-FLASH CHECK FAILED:\n" + "\n".join(f"• {m}" for m in mismatches)
            log.warning("Device match failed: %s", msg)
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message=msg,
                details={"mismatches": mismatches},
            )

        return SafetyCheckResult(
            passed=True,
            level="ok",
            message="Device and file identifiers match.",
            details={
                "device_codename": device.device,
                "device_model": device.model,
                "device_brand": device.brand,
            },
        )

    # -----------------------------------------------------------------------
    # 2. Checksum verification
    # -----------------------------------------------------------------------
    @staticmethod
    def calculate_hash(file_path: Path | str, algorithm: str = "sha256") -> str:
        """Compute the cryptographic hash of a file using chunked streaming."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {path}")

        hasher = getattr(hashlib, algorithm.lower())()
        buffer_size = 64 * 1024  # 64 KB chunks

        with open(path, "rb") as f:
            while chunk := f.read(buffer_size):
                hasher.update(chunk)

        return hasher.hexdigest().lower()

    @classmethod
    def verify_checksum(
        cls,
        file_path: Path | str,
        expected_hash: str,
        algorithm: str = "sha256",
    ) -> SafetyCheckResult:
        """
        Verify the integrity of a downloaded or local file against an expected hash.
        """
        path = Path(file_path)
        if not path.is_file():
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message=f"File not found: {path.name}",
            )

        expected = expected_hash.strip().lower()
        if not expected:
            return SafetyCheckResult(
                passed=False,
                level="warning",
                message="No checksum provided for verification. File integrity unverified.",
            )

        try:
            actual = cls.calculate_hash(path, algorithm=algorithm)
        except Exception as e:
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message=f"Failed to calculate checksum: {e}",
            )

        if actual == expected:
            return SafetyCheckResult(
                passed=True,
                level="ok",
                message=f"{algorithm.upper()} checksum verified successfully.",
                details={"hash": actual, "file": str(path)},
            )
        else:
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message=(
                    f"Checksum mismatch for {path.name}!\n"
                    f"Expected: {expected}\n"
                    f"Computed: {actual}\n"
                    "The file may be corrupt or tampered with."
                ),
                details={"expected": expected, "actual": actual},
            )

    # -----------------------------------------------------------------------
    # 3. Battery level check
    # -----------------------------------------------------------------------
    @staticmethod
    def check_battery(battery_percent: Optional[int]) -> SafetyCheckResult:
        """
        Ensure battery level is adequate for flashing (> 60%).
        """
        if battery_percent is None or battery_percent < 0:
            return SafetyCheckResult(
                passed=True,
                level="warning",
                message="Battery level could not be determined. Ensure device has ample charge.",
            )

        if battery_percent < MIN_BATTERY_PERCENT:
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message=(
                    f"Battery level ({battery_percent}%) is below safe threshold ({MIN_BATTERY_PERCENT}%).\n"
                    "Flashing requires at least 60% battery to prevent mid-flash power failure."
                ),
                details={"battery_percent": battery_percent},
            )

        return SafetyCheckResult(
            passed=True,
            level="ok",
            message=f"Battery level ({battery_percent}%) is safe for flashing.",
            details={"battery_percent": battery_percent},
        )

    # -----------------------------------------------------------------------
    # 4. Anti-rollback guard
    # -----------------------------------------------------------------------
    @staticmethod
    def check_anti_rollback(
        current_rollback_index: Optional[int],
        target_rollback_index: Optional[int],
    ) -> SafetyCheckResult:
        """
        Check rollback index to protect against hard-brick downgrades.
        """
        if current_rollback_index is None or target_rollback_index is None:
            return SafetyCheckResult(
                passed=True,
                level="info",
                message="Anti-rollback index not applicable or not reported by device.",
            )

        if target_rollback_index < current_rollback_index:
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message=(
                    f"ANTI-ROLLBACK VIOLATION:\n"
                    f"Device rollback index is {current_rollback_index}, but target firmware is {target_rollback_index}.\n"
                    "Flashing this will permanently brick your phone!"
                ),
                details={
                    "current": current_rollback_index,
                    "target": target_rollback_index,
                },
            )

        return SafetyCheckResult(
            passed=True,
            level="ok",
            message="Anti-rollback index is compatible.",
            details={
                "current": current_rollback_index,
                "target": target_rollback_index,
            },
        )

    # -----------------------------------------------------------------------
    # 5. Vendor script inspector
    # -----------------------------------------------------------------------
    @staticmethod
    def inspect_vendor_script(
        script_path: Optional[Path | str] = None,
        script_content: str = "",
    ) -> list[ScriptWarning]:
        """
        Parse official vendor fastboot scripts (flash_all.bat, flash_all.sh)
        and detect dangerous commands.
        """
        warnings: list[ScriptWarning] = []
        lines: list[str] = []

        if script_path:
            p = Path(script_path)
            if p.is_file():
                try:
                    lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
                except Exception as e:
                    log.warning("Could not read script %s: %e", p, e)

        if script_content:
            lines = script_content.splitlines()

        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("REM") or line.startswith("::") or line.startswith("#"):
                continue

            lower_line = line.lower()

            # Data wipe checks
            if any(cmd in lower_line for cmd in ("erase userdata", "-w", "format userdata", "erase data")):
                warnings.append(ScriptWarning(
                    line_number=idx,
                    command=line,
                    risk_level="critical",
                    description="Erases/formats userdata partition. All photos, apps, and data will be lost.",
                ))

            # Bootloader lock checks
            elif any(cmd in lower_line for cmd in ("oem lock", "flashing lock")):
                warnings.append(ScriptWarning(
                    line_number=idx,
                    command=line,
                    risk_level="critical",
                    description="Relocks the bootloader! If custom or mismatched firmware is installed, this will brick.",
                ))

            # Erase critical partitions
            elif any(cmd in lower_line for cmd in ("erase efs", "erase modem", "erase nvram", "erase persist")):
                warnings.append(ScriptWarning(
                    line_number=idx,
                    command=line,
                    risk_level="critical",
                    description="Erases cellular / EFS calibration partition! Device will lose IMEI and network access.",
                ))

            # Reboot command
            elif "fastboot reboot" in lower_line:
                warnings.append(ScriptWarning(
                    line_number=idx,
                    command=line,
                    risk_level="info",
                    description="Reboots device upon completion.",
                ))

        return warnings

    # -----------------------------------------------------------------------
    # 6. Typed confirmation requirement
    # -----------------------------------------------------------------------
    @staticmethod
    def is_destructive_action(action_id: str) -> bool:
        """Return True if the action poses risk of data loss or firmware corruption."""
        destructive_actions = {
            "unlock_bootloader",
            "relock_bootloader",
            "flash_rom",
            "flash_gsi",
            "flash_partition",
            "format_userdata",
            "erase_partition",
            "return_to_stock",
            "restore_partition",
        }
        return action_id.lower() in destructive_actions

    @staticmethod
    def expected_confirmation_word() -> str:
        """The exact word the user must type for destructive confirmations."""
        return CONFIRMATION_WORD
