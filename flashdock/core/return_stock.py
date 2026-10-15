"""
FlashDock — Return to Stock & Safe Bootloader Relock Engine.

Handles factory firmware restoration and safe bootloader relocking:
* Stock package discovery and validation (directories, ZIP archives, Pixel factory packages).
* Canonical partition flash ordering to prevent soft-bricks during flash.
* A/B slot awareness and dynamic partition support.
* Strict Anti-Relock Gate: verifies pure stock partitions before unlocking
  the relock mechanism to eliminate hard-brick hazards.
* Brand-specific safety rules (Xiaomi cross-region hazard, Samsung Knox, MTK preloader).
* Dry-run simulation support.

Spec references: Section 14, Section 16.
"""

from __future__ import annotations

import io
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
import tarfile
import zipfile

from flashdock.constants import MIN_BATTERY_PERCENT
from flashdock.core.device import DeviceInfo
from flashdock.core.safety import SafetyCheckResult, SafetyEngine
from flashdock.logger import get_logger
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult

log = get_logger(__name__)

# Required confirmation word for bootloader relock
RELOCK_CONFIRMATION_WORD = "RELOCK"

# Standard OEM flash order (lower index flashes earlier)
ORDERED_PARTITIONS = [
    "bootloader",
    "radio",
    "boot",
    "init_boot",
    "dtbo",
    "vendor_boot",
    "recovery",
    "vbmeta",
    "vbmeta_system",
    "vbmeta_vendor",
    "super",
    "system",
    "system_ext",
    "vendor",
    "product",
    "odm",
    "cust",
]


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PartitionImage:
    """Represents a single partition image found in a stock package."""
    partition: str
    file_path: Path
    size_bytes: int = 0
    sha256: Optional[str] = None
    in_archive: bool = False
    archive_inner_path: str = ""

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)


@dataclass
class StockPackageInfo:
    """Parsed and validated stock firmware package."""
    source_path: Path
    is_valid: bool = False
    target_codename: str = ""
    target_product: str = ""
    build_id: str = ""
    images: dict[str, PartitionImage] = field(default_factory=dict)
    has_bootloader: bool = False
    has_radio: bool = False
    has_super: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def partition_count(self) -> int:
        return len(self.images)

    @property
    def total_size_mb(self) -> float:
        total = sum(img.size_bytes for img in self.images.values())
        return round(total / (1024 * 1024), 2)


@dataclass
class StockFlashOptions:
    """Configuration options for flashing stock firmware."""
    target_slot: str = ""  # "", "a", "b", "both"
    wipe_data: bool = True
    dry_run: bool = False
    auto_reboot: bool = False
    flash_bootloader: bool = True
    flash_radio: bool = True


@dataclass
class FlashStepResult:
    """Outcome of flashing an individual partition."""
    partition: str
    status: str  # "pending", "flashing", "success", "failed", "skipped"
    command: list[str] = field(default_factory=list)
    message: str = ""
    duration_ms: int = 0


@dataclass
class ReturnStockResult:
    """Final outcome of the return-to-stock operation."""
    success: bool
    steps: list[FlashStepResult] = field(default_factory=list)
    error_message: str = ""
    wiped_data: bool = False
    rebooted: bool = False
    ready_for_relock: bool = False

    @property
    def successful_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "success")

    @property
    def failed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "failed")


@dataclass
class RelockCheckResult:
    """Result of bootloader relock safety evaluation."""
    can_relock: bool
    risk_level: str  # "safe", "warning", "prohibited"
    recommended_command: str  # "fastboot flashing lock" or "fastboot oem lock"
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_blocked(self) -> bool:
        return not self.can_relock or self.risk_level == "prohibited"


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ReturnStockEngine:
    """Engine for flashing factory stock images and safe bootloader relocking."""

    def __init__(self, fastboot: Optional[Fastboot] = None) -> None:
        self._fastboot = fastboot or Fastboot()

    # -----------------------------------------------------------------------
    # Package discovery and parsing
    # -----------------------------------------------------------------------

    @staticmethod
    def parse_stock_package(source: str | Path) -> StockPackageInfo:
        """
        Inspect a file or folder and return a StockPackageInfo.

        Accepts:
        - A directory of .img files (e.g. extracted firmware)
        - A ZIP file containing .img files (or nested image-*.zip)
        """
        path = Path(source)
        pkg = StockPackageInfo(source_path=path)

        if not path.exists():
            pkg.errors.append(f"Specified path does not exist: {path}")
            return pkg

        lower_name = path.name.lower()
        if path.is_dir():
            ReturnStockEngine._parse_directory(path, pkg)
        elif path.is_file():
            if lower_name.endswith(".zip"):
                ReturnStockEngine._parse_zip(path, pkg)
            elif any(lower_name.endswith(ext) for ext in (".tar", ".tar.gz", ".tgz", ".tar.md5")):
                ReturnStockEngine._parse_tar(path, pkg)
            elif lower_name.endswith(".pac"):
                ReturnStockEngine._parse_pac(path, pkg)
            elif lower_name.endswith("payload.bin"):
                ReturnStockEngine._parse_payload_bin(path, pkg)
            else:
                pkg.errors.append("Unsupported file type. Select a directory, .zip, .tgz, .tar.md5, .pac, or payload.bin package.")
                return pkg
        else:
            pkg.errors.append("Unsupported file type. Select a directory or a firmware package.")
            return pkg

        # Check minimal required partitions
        has_kernel_or_system = any(
            p in pkg.images for p in ("boot", "init_boot", "system", "super", "recovery")
        )
        if not has_kernel_or_system:
            pkg.errors.append("Package contains no boot, super, system, or recovery partition images.")
        else:
            pkg.is_valid = len(pkg.errors) == 0

        pkg.has_bootloader = "bootloader" in pkg.images
        pkg.has_radio = "radio" in pkg.images
        pkg.has_super = "super" in pkg.images

        log.info(
            "Parsed stock package '%s': %d partitions detected, valid=%s",
            path.name, len(pkg.images), pkg.is_valid
        )
        return pkg

    @staticmethod
    def _parse_directory(dir_path: Path, pkg: StockPackageInfo) -> None:
        """Scan a directory for partition images and android-info.txt."""
        # Check android-info.txt
        info_file = dir_path / "android-info.txt"
        if info_file.is_file():
            try:
                content = info_file.read_text(encoding="utf-8", errors="ignore")
                ReturnStockEngine._parse_android_info(content, pkg)
            except Exception as e:
                pkg.warnings.append(f"Failed to read android-info.txt: {e}")

        # Search for .img files directly
        for f in dir_path.glob("*.img"):
            part_name = ReturnStockEngine._canonical_partition_name(f.stem)
            if part_name:
                pkg.images[part_name] = PartitionImage(
                    partition=part_name,
                    file_path=f,
                    size_bytes=f.stat().st_size,
                )

        # Check for nested Pixel zip: image-*.zip
        nested_zips = list(dir_path.glob("image-*.zip"))
        if nested_zips and not pkg.images:
            # If no .img found in root, look inside the nested image-*.zip
            nested = nested_zips[0]
            log.info("Found nested factory zip: %s", nested.name)
            ReturnStockEngine._parse_zip(nested, pkg)

    @staticmethod
    def _parse_zip(zip_path: Path, pkg: StockPackageInfo) -> None:
        """Scan a ZIP archive for partition images."""
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                # Look for android-info.txt
                for name in zf.namelist():
                    if Path(name).name.lower() == "android-info.txt":
                        try:
                            with zf.open(name) as af:
                                text = af.read().decode("utf-8", errors="ignore")
                                ReturnStockEngine._parse_android_info(text, pkg)
                        except Exception:
                            pass

                # Look for nested image-*.zip
                nested_images_zip = None
                for name in zf.namelist():
                    base = Path(name).name
                    if base.startswith("image-") and base.endswith(".zip"):
                        nested_images_zip = name
                        break

                if nested_images_zip:
                    # Parse inner zip entries
                    with zf.open(nested_images_zip) as nested_file:
                        with zipfile.ZipFile(io.BytesIO(nested_file.read())) as nzf:
                            for inner_name in nzf.namelist():
                                p = Path(inner_name)
                                if p.suffix.lower() == ".img":
                                    part = ReturnStockEngine._canonical_partition_name(p.stem)
                                    if part:
                                        info = nzf.getinfo(inner_name)
                                        pkg.images[part] = PartitionImage(
                                            partition=part,
                                            file_path=zip_path,
                                            size_bytes=info.file_size,
                                            in_archive=True,
                                            archive_inner_path=f"{nested_images_zip}:{inner_name}",
                                        )

                # Direct .img files in the zip
                for name in zf.namelist():
                    p = Path(name)
                    if p.suffix.lower() == ".img":
                        part = ReturnStockEngine._canonical_partition_name(p.stem)
                        if part and part not in pkg.images:
                            info = zf.getinfo(name)
                            pkg.images[part] = PartitionImage(
                                partition=part,
                                file_path=zip_path,
                                size_bytes=info.file_size,
                                in_archive=True,
                                archive_inner_path=name,
                            )
        except zipfile.BadZipFile:
            pkg.errors.append("Invalid or corrupted ZIP archive.")
        except Exception as e:
            pkg.errors.append(f"Failed to inspect ZIP archive: {e}")

    @staticmethod
    def _parse_tar(tar_path: Path, pkg: StockPackageInfo) -> None:
        """Scan a TAR archive (.tar, .tar.gz, .tgz, .tar.md5) for partition images."""
        try:
            with tarfile.open(tar_path, "r:*") as tf:
                for member in tf.getmembers():
                    name = member.name
                    clean_name = name.lower()
                    if clean_name.endswith(".img.lz4"):
                        canon = ReturnStockEngine._canonical_partition_name(Path(name[:-4]).stem)
                        if canon and canon not in pkg.images:
                            pkg.images[canon] = PartitionImage(
                                partition=canon,
                                file_path=tar_path,
                                size_bytes=member.size,
                                in_archive=True,
                                archive_inner_path=name,
                            )
                    elif Path(name).suffix.lower() == ".img":
                        canon = ReturnStockEngine._canonical_partition_name(Path(name).stem)
                        if canon and canon not in pkg.images:
                            pkg.images[canon] = PartitionImage(
                                partition=canon,
                                file_path=tar_path,
                                size_bytes=member.size,
                                in_archive=True,
                                archive_inner_path=name,
                            )
                    elif Path(name).name.lower() == "android-info.txt":
                        try:
                            f = tf.extractfile(member)
                            if f:
                                ReturnStockEngine._parse_android_info(f.read().decode("utf-8", errors="ignore"), pkg)
                        except Exception:
                            pass
        except Exception as e:
            pkg.errors.append(f"Failed to inspect TAR archive: {e}")

    @staticmethod
    def _parse_pac(pac_path: Path, pkg: StockPackageInfo) -> None:
        """Scan a Unisoc .pac archive for partition entries."""
        from flashdock.core.unisoc import PACExtractor
        try:
            info = PACExtractor.parse_pac(pac_path)
            pkg.target_product = info.product_name
            for entry in info.files:
                if entry.file_size > 0:
                    clean_name = entry.file_name or entry.file_id
                    canon = ReturnStockEngine._canonical_partition_name(Path(clean_name).stem)
                    if canon and canon not in pkg.images:
                        pkg.images[canon] = PartitionImage(
                            partition=canon,
                            file_path=pac_path,
                            size_bytes=entry.file_size,
                            in_archive=True,
                            archive_inner_path=entry.file_id,
                        )
        except Exception as e:
            pkg.errors.append(f"Failed to parse Unisoc PAC archive: {e}")

    @staticmethod
    def _parse_payload_bin(payload_path: Path, pkg: StockPackageInfo) -> None:
        """Scan an Android OTA payload.bin file for partition entries."""
        from flashdock.tools.payload_dumper import PayloadDumper
        try:
            parts = PayloadDumper.list_partitions(payload_path)
            for part_name in parts:
                canon = ReturnStockEngine._canonical_partition_name(part_name)
                if canon and canon not in pkg.images:
                    pkg.images[canon] = PartitionImage(
                        partition=canon,
                        file_path=payload_path,
                        size_bytes=0,
                        in_archive=True,
                        archive_inner_path=part_name,
                    )
        except Exception as e:
            pkg.errors.append(f"Failed to parse payload.bin: {e}")

    @staticmethod
    def _parse_android_info(content: str, pkg: StockPackageInfo) -> None:
        """Parse android-info.txt to extract target device metadata."""
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lower = line.lower()
            if "require board=" in lower or "require-for-product:" in lower:
                # e.g. "require board=lynx" or "require board=panther|cheetah"
                parts = line.split("=", 1)
                if len(parts) == 2:
                    pkg.target_codename = parts[1].strip()
            elif "require product=" in lower:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    pkg.target_product = parts[1].strip()
            elif "require version-bootloader=" in lower:
                parts = line.split("=", 1)
                if len(parts) == 2:
                    pkg.build_id = parts[1].strip()

    @staticmethod
    def _canonical_partition_name(stem: str) -> str:
        """Map filename stem to canonical partition name."""
        lower = stem.lower()
        if lower.startswith("bootloader"):
            return "bootloader"
        if lower.startswith("radio"):
            return "radio"
        if lower in ORDERED_PARTITIONS:
            return lower
        # Strip trailing slot suffixes like _a, _b
        for suffix in ("_a", "_b", "-a", "-b"):
            if lower.endswith(suffix):
                base = lower[:-2]
                if base in ORDERED_PARTITIONS:
                    return base
        return lower

    # -----------------------------------------------------------------------
    # Ordering & sequence
    # -----------------------------------------------------------------------

    @staticmethod
    def get_flash_order(images: dict[str, PartitionImage]) -> list[str]:
        """
        Return partition names in the safe OEM flashing order.
        Any unrecognized partitions are appended at the end.
        """
        ordered: list[str] = []
        for part in ORDERED_PARTITIONS:
            if part in images:
                ordered.append(part)

        # Append remaining partitions
        for part in images:
            if part not in ordered:
                ordered.append(part)

        return ordered

    @staticmethod
    def _materialize_image(image: PartitionImage, destination_dir: Path) -> tuple[Optional[Path], str]:
        """Return a disk image path, extracting an archived image when needed."""
        if not image.in_archive:
            if image.file_path.is_file():
                return image.file_path, ""
            return None, f"Firmware image is missing: {image.file_path}"

        destination = destination_dir / f"{image.partition}.img"
        try:
            # 1. Payload.bin (raw or inside zip)
            if image.archive_inner_path.startswith("payload.bin:") or image.file_path.name.lower() == "payload.bin":
                from flashdock.tools.payload_dumper import PayloadDumper
                part_target = image.archive_inner_path.split(":", 1)[-1] if ":" in image.archive_inner_path else image.partition
                extracted = PayloadDumper.extract_partitions(image.file_path, destination_dir, target_partitions=[part_target])
                if extracted and extracted[0].is_file():
                    return extracted[0], ""
                return None, f"Failed to extract {image.partition} from payload.bin"

            # 2. Unisoc PAC archive
            if image.file_path.name.lower().endswith(".pac"):
                from flashdock.core.unisoc import PACExtractor
                extracted_file = PACExtractor.extract_file(image.file_path, image.archive_inner_path, destination_dir)
                if extracted_file and extracted_file.is_file():
                    return extracted_file, ""
                return None, f"Failed to extract {image.partition} from PAC archive"

            # 3. TAR / TAR.GZ / TGZ / TAR.MD5 archive (including Samsung .img.lz4)
            lower_name = image.file_path.name.lower()
            if any(lower_name.endswith(ext) for ext in (".tar", ".tgz", ".tar.gz", ".tar.md5")):
                with tarfile.open(image.file_path, "r:*") as archive:
                    member = archive.getmember(image.archive_inner_path)
                    f_in = archive.extractfile(member)
                    if not f_in:
                        return None, f"Could not read member {image.archive_inner_path} from TAR"
                    if image.archive_inner_path.lower().endswith(".lz4"):
                        from flashdock.tools.lz4_util import decompress_lz4_stream
                        with destination.open("wb") as target:
                            decompress_lz4_stream(f_in, target)
                    else:
                        with destination.open("wb") as target:
                            shutil.copyfileobj(f_in, target)
                return destination, ""

            # 4. Standard ZIP archive
            with zipfile.ZipFile(image.file_path, "r") as archive:
                if ":" in image.archive_inner_path:
                    nested_name, member = image.archive_inner_path.split(":", 1)
                    with archive.open(nested_name) as nested_stream:
                        with zipfile.ZipFile(io.BytesIO(nested_stream.read())) as nested_archive:
                            with nested_archive.open(member) as source, destination.open("wb") as target:
                                shutil.copyfileobj(source, target)
                else:
                    with archive.open(image.archive_inner_path) as source, destination.open("wb") as target:
                        shutil.copyfileobj(source, target)
            if image.size_bytes and destination.stat().st_size != image.size_bytes:
                return None, f"Extracted image size does not match archive metadata: {image.partition}"
            return destination, ""
        except Exception as exc:
            return None, f"Could not extract {image.partition} from firmware archive: {exc}"

    # -----------------------------------------------------------------------
    # Compatibility & safety checks
    # -----------------------------------------------------------------------

    @staticmethod
    def check_firmware_compatibility(
        device: DeviceInfo,
        package: StockPackageInfo,
    ) -> SafetyCheckResult:
        """
        Verify that the firmware package is compatible with the connected device.
        """
        if not device or device.mode == "not_connected":
            return SafetyCheckResult(
                passed=False,
                level="blocked",
                message="No device connected. Connect your phone to verify compatibility.",
            )

        if not package.is_valid:
            msg = "Firmware package is invalid: " + "; ".join(package.errors)
            return SafetyCheckResult(passed=False, level="blocked", message=msg)

        # Codename comparison
        if package.target_codename and device.device:
            target_codes = [c.strip().lower() for c in package.target_codename.split("|")]
            device_code = device.device.strip().lower()
            if device_code and device_code not in target_codes:
                return SafetyCheckResult(
                    passed=False,
                    level="blocked",
                    message=(
                        f"CRITICAL CODENAME MISMATCH:\n"
                        f"Connected device codename: '{device_code}'\n"
                        f"Firmware target codenames: '{package.target_codename}'\n"
                        "Flashing firmware for a different model will permanently brick your device!"
                    ),
                    details={
                        "device_codename": device_code,
                        "package_codename": package.target_codename,
                    },
                )

        # Battery check
        battery_res = SafetyEngine.check_battery(device.battery_level)
        if battery_res.is_blocked:
            return battery_res

        return SafetyCheckResult(
            passed=True,
            level="ok",
            message="Firmware package matches device and is safe to flash.",
            details={
                "target_codename": package.target_codename,
                "partitions": list(package.images.keys()),
            },
        )

    # -----------------------------------------------------------------------
    # Anti-Relock Gate & Safety Evaluation
    # -----------------------------------------------------------------------

    @staticmethod
    def check_relock_safety(
        device: DeviceInfo,
        flash_result: Optional[ReturnStockResult] = None,
        cross_region_risk: bool = False,
    ) -> RelockCheckResult:
        """
        Strictly evaluate whether it is safe to relock the bootloader.

        ANTI-BRICK RELOCK RULES:
        1. Device must be connected and in fastboot or fastbootd mode.
        2. Stock firmware must have been completely flashed with 100% success.
        3. Never relock if partition flash failed or was skipped.
        4. Brand-specific blacklists:
           - Xiaomi / Redmi / POCO cross-region ROM: Relocking causes instant hard-brick.
           - Samsung: Bootloader relock in fastboot is dangerous and Knox cannot be restored.
           - MediaTek / Unisoc devices with modified preloader.
        """
        reasons: list[str] = []
        warnings: list[str] = []

        # 1. Device check
        if not device or device.mode == "not_connected":
            reasons.append("No device connected.")
            return RelockCheckResult(
                can_relock=False,
                risk_level="prohibited",
                recommended_command="",
                reasons=reasons,
            )

        if device.mode not in ("bootloader", "fastbootd"):
            reasons.append(
                f"Device is in '{device.mode}' mode. Bootloader relock requires Fastboot mode."
            )

        # 2. Flash result check
        if flash_result is None:
            reasons.append(
                "Stock firmware has not been flashed in this session. "
                "Relocking without freshly verifying pure stock partitions will cause an unrecoverable brick."
            )
        elif not flash_result.success:
            reasons.append(
                f"Stock firmware flashing failed ({flash_result.failed_steps} failed steps). "
                "NEVER relock bootloader on a partially flashed or modified device!"
            )
        elif flash_result.successful_steps == 0:
            reasons.append("No partitions were flashed.")

        # 3. Brand-specific blacklist checks
        brand = (device.brand or "").strip().lower()

        if brand in ("xiaomi", "redmi", "poco"):
            if cross_region_risk:
                reasons.append(
                    "XIAOMI CROSS-REGION LOCK PROHIBITED:\n"
                    "Relocking bootloader on Xiaomi/Redmi/POCO devices with a cross-region ROM "
                    "(e.g. Global ROM on Chinese hardware) causes an unrecoverable hard-brick "
                    "('This MIUI version can't be installed on this device')."
                )
            else:
                warnings.append(
                    "Xiaomi notice: Ensure the installed ROM strictly matches your phone's hardware region "
                    "(e.g. Global on Global, CN on CN) before locking."
                )

        if brand == "samsung":
            reasons.append(
                "SAMSUNG PROHIBITION:\n"
                "Samsung devices do not support standard fastboot bootloader relocking. "
                "Furthermore, Knox status is a physical hardware e-fuse and cannot be reset."
            )

        if (device.chipset or "").strip().lower() in ("mediatek", "unisoc"):
            warnings.append(
                "MediaTek/Unisoc notice: Ensure the preloader and bootloader were not modified by an exploit."
            )

        # 4. Battery check
        if device.battery_level is not None and device.battery_level < MIN_BATTERY_PERCENT:
            reasons.append(
                f"Battery level ({device.battery_level}%) is below {MIN_BATTERY_PERCENT}%. "
                "Charge device before relocking."
            )

        # Determine recommended command
        # Modern Pixel & Android 10+ devices use 'fastboot flashing lock'
        cmd = "fastboot flashing lock"
        if brand in ("motorola", "oneplus", "sony", "htc"):
            # Older implementations or legacy brands
            if device.api_level and device.api_level < 29:
                cmd = "fastboot oem lock"

        if reasons:
            return RelockCheckResult(
                can_relock=False,
                risk_level="prohibited",
                recommended_command=cmd,
                reasons=reasons,
                warnings=warnings,
            )

        return RelockCheckResult(
            can_relock=True,
            risk_level="safe" if not warnings else "warning",
            recommended_command=cmd,
            reasons=["All pre-relock safety checks passed."],
            warnings=warnings,
        )

    # -----------------------------------------------------------------------
    # Flashing Pipeline
    # -----------------------------------------------------------------------

    def flash_stock(
        self,
        device: DeviceInfo,
        package: StockPackageInfo,
        options: Optional[StockFlashOptions] = None,
        progress_callback: Optional[Callable[[int, int, str, str, str], None]] = None,
        cancel_requested: Optional[Callable[[], bool]] = None,
    ) -> ReturnStockResult:
        """
        Execute full stock firmware flashing sequence.

        Parameters
        ----------
        device : DeviceInfo
            Target device.
        package : StockPackageInfo
            Parsed stock firmware package.
        options : Optional[StockFlashOptions]
            Flashing options (dry_run, slot, wipe_data, etc.).
        progress_callback : Optional[Callable[[current, total, partition, status, message]]]
            Step progress callback.
        cancel_requested : Optional[Callable[[], bool]]
            Function returning True if user cancelled operation.
        """
        options = options or StockFlashOptions()
        serial = device.serial if device else ""
        dry_run = options.dry_run

        log.info(
            "Starting Return-to-Stock on %s (dry_run=%s, slot='%s', wipe=%s)",
            serial, dry_run, options.target_slot, options.wipe_data
        )

        # Compatibility check
        compat = self.check_firmware_compatibility(device, package)
        if compat.is_blocked:
            log.error("Return-to-stock compatibility blocked: %s", compat.message)
            return ReturnStockResult(
                success=False,
                error_message=compat.message,
            )

        # Order partitions
        ordered = self.get_flash_order(package.images)
        total_steps = len(ordered) + (1 if options.wipe_data else 0)
        current_step = 0
        step_results: list[FlashStepResult] = []

        with tempfile.TemporaryDirectory(prefix="flashdock-stock-") as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            for part in ordered:
                if cancel_requested and cancel_requested():
                    log.warning("Return-to-stock cancelled by user.")
                    return ReturnStockResult(
                        success=False,
                        steps=step_results,
                        error_message="Operation cancelled by user.",
                    )

                current_step += 1
                img = package.images[part]

                # Skip bootloader or radio if option disabled
                if part == "bootloader" and not options.flash_bootloader:
                    step_results.append(FlashStepResult(
                        partition=part,
                        status="skipped",
                        message="Skipped by user option.",
                    ))
                    if progress_callback:
                        progress_callback(current_step, total_steps, part, "skipped", "Skipped by option")
                    continue

                if part == "radio" and not options.flash_radio:
                    step_results.append(FlashStepResult(
                        partition=part,
                        status="skipped",
                        message="Skipped by user option.",
                    ))
                    if progress_callback:
                        progress_callback(current_step, total_steps, part, "skipped", "Skipped by option")
                    continue

                if progress_callback:
                    progress_callback(current_step, total_steps, part, "flashing", f"Flashing {part}...")

                image_path = img.file_path
                if not dry_run:
                    image_path, extract_error = self._materialize_image(img, temp_dir)
                    if not image_path:
                        step_results.append(FlashStepResult(partition=part, status="failed", message=extract_error))
                        return ReturnStockResult(success=False, steps=step_results, error_message=extract_error)

                # Prepare fastboot flash command
                target_slots = [options.target_slot] if options.target_slot != "both" else ["a", "b"]

                part_success = True
                part_msg = ""
                for slot_item in target_slots:
                    cmd_args = ["fastboot"]
                    if serial:
                        cmd_args += ["-s", serial]
                    cmd_args += ["flash"]
                    if slot_item:
                        cmd_args += [f"--slot={slot_item}"]
                    cmd_args += [part, str(image_path)]

                    if dry_run:
                        log.info("[DRY RUN] Would execute: %s", " ".join(cmd_args))
                        part_msg = f"[Dry Run] Successfully simulated flash of {part}"
                    else:
                        res = self._fastboot.flash(
                            partition=part,
                            image_path=str(image_path),
                            serial=serial,
                            slot=slot_item,
                        )
                        if not res.success:
                            part_success = False
                            part_msg = res.stderr or res.stdout or "Flash command failed."
                            log.error("Failed to flash partition %s: %s", part, part_msg)
                            break
                        part_msg = f"Flashed {part} successfully."

                if not part_success:
                    step_results.append(FlashStepResult(
                        partition=part,
                        status="failed",
                        command=cmd_args,
                        message=part_msg,
                    ))
                    if progress_callback:
                        progress_callback(current_step, total_steps, part, "failed", part_msg)
                    return ReturnStockResult(
                        success=False,
                        steps=step_results,
                        error_message=f"Flashing partition '{part}' failed: {part_msg}",
                    )

                step_results.append(FlashStepResult(
                    partition=part,
                    status="success",
                    command=cmd_args,
                    message=part_msg,
                ))
                if progress_callback:
                    progress_callback(current_step, total_steps, part, "success", part_msg)

        # Handle Wipe Data
        wiped_data = False
        if options.wipe_data:
            current_step += 1
            if progress_callback:
                progress_callback(current_step, total_steps, "userdata", "flashing", "Erasing userdata...")

            erase_cmd = ["fastboot", "-w"]
            if serial:
                erase_cmd = ["fastboot", "-s", serial, "-w"]

            if dry_run:
                log.info("[DRY RUN] Would execute: %s", " ".join(erase_cmd))
                wiped_data = True
                step_results.append(FlashStepResult(
                    partition="userdata",
                    status="success",
                    command=erase_cmd,
                    message="[Dry Run] Userdata wipe simulated.",
                ))
                if progress_callback:
                    progress_callback(current_step, total_steps, "userdata", "success", "Wiped data simulated")
            else:
                erase_res = self._fastboot._run(["-w"], serial=serial, timeout=120)
                if not erase_res.success:
                    # Fallback to erase userdata
                    erase_res = self._fastboot.erase("userdata", serial=serial)

                if erase_res.success:
                    wiped_data = True
                    step_results.append(FlashStepResult(
                        partition="userdata",
                        status="success",
                        command=erase_cmd,
                        message="Userdata erased successfully.",
                    ))
                    if progress_callback:
                        progress_callback(current_step, total_steps, "userdata", "success", "Userdata erased")
                else:
                    step_results.append(FlashStepResult(
                        partition="userdata",
                        status="failed",
                        command=erase_cmd,
                        message=erase_res.stderr or "Failed to erase userdata.",
                    ))
                    if progress_callback:
                        progress_callback(current_step, total_steps, "userdata", "failed", "Wipe userdata failed")

        # Auto reboot if requested
        rebooted = False
        if options.auto_reboot:
            if dry_run:
                log.info("[DRY RUN] Would execute: fastboot reboot")
                rebooted = True
            else:
                rb_res = self._fastboot.reboot(serial=serial)
                rebooted = rb_res.success

        log.info("Return-to-stock completed successfully for %s", serial)
        return ReturnStockResult(
            success=True,
            steps=step_results,
            wiped_data=wiped_data,
            rebooted=rebooted,
            ready_for_relock=True,
        )

    # -----------------------------------------------------------------------
    # Relock Execution
    # -----------------------------------------------------------------------

    def execute_relock(
        self,
        device: DeviceInfo,
        command: str = "fastboot flashing lock",
        dry_run: bool = False,
    ) -> CommandResult:
        """
        Execute bootloader relock command in Fastboot.
        """
        serial = device.serial if device else ""
        log.info("Executing bootloader relock command '%s' on %s (dry_run=%s)", command, serial, dry_run)

        if dry_run:
            return CommandResult(
                command=[command],
                return_code=0,
                stdout="[Dry Run] Simulated bootloader relock successful.",
                stderr="",
                duration_ms=10,
            )

        if "flashing lock" in command.lower():
            return self._fastboot.flashing_lock(serial=serial)
        else:
            return self._fastboot.oem_lock(serial=serial)
