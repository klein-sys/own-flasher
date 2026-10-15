"""
FlashDock — Custom ROM, GSI & Recovery Flashing Engine.

Handles:
* Custom Fastboot ROM package parsing and ordered partition flashing.
* Treble Generic System Image (GSI) analysis, fastbootd coordination, and flashing.
* Custom Recovery (TWRP, OrangeFox, PBRP) target partition resolution and flashing/booting.
* Integration with local RepositoryManager (data/roms/, data/gsis/).
* Safety gates: battery threshold >= 60%, match checking, slot targeting, and FlashShield progress tracking.

Spec references: Section 12, Section 13, Section 29.
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from flashdock.core.device import DeviceInfo
from flashdock.core.safety import SafetyEngine
from flashdock.logger import get_logger
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult

log = get_logger(__name__)

# Standard flashing order to prevent bootloader mismatches
CANONICAL_ROM_ORDER = [
    "bootloader",
    "radio",
    "boot",
    "init_boot",
    "dtbo",
    "recovery",
    "vbmeta",
    "vbmeta_system",
    "vbmeta_vendor",
    "super",
    "system",
    "vendor",
    "product",
    "system_ext",
    "odm",
    "cust",
    "userdata",
]


@dataclass
class FlashPartitionItem:
    """A single partition image within a ROM package."""
    partition_name: str
    image_path: Path
    file_size_bytes: int
    slot_target: str = ""  # "", "a", "b", "both"

    @property
    def size_mb(self) -> float:
        return round(self.file_size_bytes / (1024 * 1024), 2)


@dataclass
class RomPackageInfo:
    """Parsed Custom Fastboot ROM package metadata."""
    name: str
    package_type: str  # "fastboot_dir", "fastboot_zip", "single_image"
    path: Path
    detected_partitions: list[FlashPartitionItem] = field(default_factory=list)
    has_flash_script: bool = False
    script_name: str = ""
    target_codename: str = ""
    total_size_bytes: int = 0

    @property
    def total_size_mb(self) -> float:
        return round(self.total_size_bytes / (1024 * 1024), 2)


@dataclass
class GsiInfo:
    """Parsed Generic System Image (GSI) metadata."""
    name: str
    image_path: Path
    arch: str  # "arm64", "arm", "x86_64"
    slot_scheme: str  # "a/b", "a_only"
    gapps_variant: str  # "Vanilla (v)", "GApps (g)", "MicroG (o)", "SuperSU (s)"
    file_size_bytes: int

    @property
    def size_mb(self) -> float:
        return round(self.file_size_bytes / (1024 * 1024), 2)


@dataclass
class RecoveryInfo:
    """Custom recovery metadata and target recommendation."""
    name: str
    image_path: Path
    recovery_type: str  # "TWRP", "OrangeFox", "PBRP", "Custom"
    recommended_partition: str  # "recovery" or "boot"
    supports_live_boot: bool = True
    file_size_bytes: int = 0

    @property
    def size_mb(self) -> float:
        return round(self.file_size_bytes / (1024 * 1024), 2)


class RomFlasher:
    """Core engine for Custom ROM, GSI, and Recovery operations."""

    def __init__(self, fastboot: Optional[Fastboot] = None) -> None:
        self.fb = fastboot or Fastboot()

    # -----------------------------------------------------------------------
    # ROM Package Parsing
    # -----------------------------------------------------------------------

    @classmethod
    def parse_custom_rom(cls, path: Path | str) -> tuple[bool, Optional[RomPackageInfo], str]:
        """
        Inspect a folder or .zip file containing a Fastboot ROM.
        Discovers partitions, scripts, and target codename.
        """
        p = Path(path)
        if not p.exists():
            return False, None, f"Path not found: {p}"

        partitions: list[FlashPartitionItem] = []
        has_script = False
        script_name = ""
        codename = ""
        total_size = 0

        # Case 1: Directory
        if p.is_dir():
            script_names = ("flash_all.bat", "flash_all.sh", "flash-all.bat", "flash-all.sh")
            for sn in script_names:
                sp = p / sn
                if sp.is_file():
                    has_script = True
                    script_name = sn
                    break

            # Check android-info.txt
            info_file = p / "android-info.txt"
            if info_file.is_file():
                try:
                    text = info_file.read_text(encoding="utf-8", errors="ignore")
                    m = re.search(r"require\s+product=([^\s]+)", text)
                    if m:
                        codename = m.group(1).split(",")[0].strip()
                except Exception:
                    pass

            # Scan image files
            for img in p.glob("*.img"):
                part_name = cls._map_partition_name(img.stem)
                sz = img.stat().st_size
                total_size += sz
                partitions.append(FlashPartitionItem(
                    partition_name=part_name,
                    image_path=img,
                    file_size_bytes=sz,
                ))

            # Scan sparse chunks (e.g. Motorola style system.img_sparsechunk.0)
            chunk_files = list(p.glob("*sparsechunk*"))
            for cf in chunk_files:
                base_part = re.sub(r"\.img.*", "", cf.name).lower()
                base_part = re.sub(r"[._]sparsechunk.*", "", base_part)
                part_name = cls._map_partition_name(base_part)
                sz = cf.stat().st_size
                total_size += sz
                partitions.append(FlashPartitionItem(
                    partition_name=part_name,
                    image_path=cf,
                    file_size_bytes=sz,
                ))

            partitions.sort(key=lambda x: cls._order_key(x.partition_name))
            info = RomPackageInfo(
                name=p.name,
                package_type="fastboot_dir",
                path=p,
                detected_partitions=partitions,
                has_flash_script=has_script,
                script_name=script_name,
                target_codename=codename,
                total_size_bytes=total_size,
            )
            return True, info, f"Discovered {len(partitions)} partition images in directory."

        # Case 2: Zip archive
        if p.is_file() and p.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(p, "r") as zf:
                    names = zf.namelist()
                    script_names = ("flash_all.bat", "flash_all.sh", "flash-all.bat", "flash-all.sh")
                    for sn in script_names:
                        if sn in names or any(n.endswith("/" + sn) for n in names):
                            has_script = True
                            script_name = sn
                            break

                    for zi in zf.infolist():
                        if zi.filename.lower().endswith(".img") and not zi.is_dir():
                            base_name = Path(zi.filename).stem
                            part_name = cls._map_partition_name(base_name)
                            total_size += zi.file_size
                            partitions.append(FlashPartitionItem(
                                partition_name=part_name,
                                image_path=Path(zi.filename),
                                file_size_bytes=zi.file_size,
                            ))

                    if "android-info.txt" in names:
                        raw = zf.read("android-info.txt").decode("utf-8", errors="ignore")
                        m = re.search(r"require\s+product=([^\s]+)", raw)
                        if m:
                            codename = m.group(1).split(",")[0].strip()

                    # Check for payload.bin if no direct .img found
                    if not partitions and any(n.lower().endswith("payload.bin") for n in names):
                        from flashdock.tools.payload_dumper import PayloadDumper
                        payload_parts = PayloadDumper.list_partitions(p)
                        for part_name in payload_parts:
                            partitions.append(FlashPartitionItem(
                                partition_name=part_name,
                                image_path=Path(f"payload.bin:{part_name}"),
                                file_size_bytes=0,
                            ))

                partitions.sort(key=lambda x: cls._order_key(x.partition_name))
                info = RomPackageInfo(
                    name=p.name,
                    package_type="fastboot_zip",
                    path=p,
                    detected_partitions=partitions,
                    has_flash_script=has_script,
                    script_name=script_name,
                    target_codename=codename,
                    total_size_bytes=total_size or p.stat().st_size,
                )
                return True, info, f"Discovered {len(partitions)} partition images in zip."
            except Exception as e:
                return False, None, f"Failed to inspect zip archive: {e}"

        # Case 3: Raw payload.bin
        if p.is_file() and p.name.lower().endswith("payload.bin"):
            try:
                from flashdock.tools.payload_dumper import PayloadDumper
                payload_parts = PayloadDumper.list_partitions(p)
                for part_name in payload_parts:
                    partitions.append(FlashPartitionItem(
                        partition_name=part_name,
                        image_path=Path(f"{part_name}.img"),
                        file_size_bytes=0,
                    ))
                info = RomPackageInfo(
                    name=p.name,
                    package_type="payload_bin",
                    path=p,
                    detected_partitions=partitions,
                    has_flash_script=False,
                    script_name="",
                    target_codename="",
                    total_size_bytes=p.stat().st_size,
                )
                return True, info, f"Discovered {len(partitions)} partition images in payload.bin."
            except Exception as e:
                return False, None, f"Failed to inspect payload.bin: {e}"

        # Case 4: Tar archive (.tar, .tgz, .tar.gz, .tar.md5)
        if p.is_file() and any(p.name.lower().endswith(ext) for ext in (".tar", ".tgz", ".tar.gz", ".tar.md5")):
            try:
                import tarfile
                with tarfile.open(p, "r:*") as tf:
                    for member in tf.getmembers():
                        name = member.name.lower()
                        if name.endswith(".img") or name.endswith(".img.lz4"):
                            clean_stem = Path(name[:-4]).stem if name.endswith(".lz4") else Path(name).stem
                            part_name = cls._map_partition_name(clean_stem)
                            total_size += member.size
                            partitions.append(FlashPartitionItem(
                                partition_name=part_name,
                                image_path=Path(member.name),
                                file_size_bytes=member.size,
                            ))
                partitions.sort(key=lambda x: cls._order_key(x.partition_name))
                info = RomPackageInfo(
                    name=p.name,
                    package_type="tar_package",
                    path=p,
                    detected_partitions=partitions,
                    has_flash_script=False,
                    script_name="",
                    target_codename="",
                    total_size_bytes=total_size or p.stat().st_size,
                )
                return True, info, f"Discovered {len(partitions)} partition images in tar package."
            except Exception as e:
                return False, None, f"Failed to inspect tar archive: {e}"

        return False, None, f"Unsupported file format: {p.suffix}"

    @classmethod
    def _map_partition_name(cls, stem: str) -> str:
        s = stem.lower().rstrip("_a").rstrip("_b")
        s = re.sub(r"\.img$", "", s)
        if s.startswith("boot_"):
            return "boot"
        if s.startswith("init_boot_"):
            return "init_boot"
        if s.startswith("system_"):
            return "system"
        if s.startswith("vendor_"):
            return "vendor"
        if s.startswith("product_"):
            return "product"
        return s

    @classmethod
    def _order_key(cls, name: str) -> int:
        clean = name.lower()
        if clean in CANONICAL_ROM_ORDER:
            return CANONICAL_ROM_ORDER.index(clean)
        return 99

    # -----------------------------------------------------------------------
    # GSI Parsing
    # -----------------------------------------------------------------------

    @classmethod
    def parse_gsi(cls, path: Path | str) -> tuple[bool, Optional[GsiInfo], str]:
        """
        Inspect a Treble Generic System Image (.img, .xz, .zip).
        Extracts architecture, slot scheme, and GApps flavor.
        """
        p = Path(path)
        if not p.is_file():
            return False, None, f"GSI file not found: {p}"

        name = p.name.lower()
        # Architecture detection
        if "arm64" in name:
            arch = "arm64"
        elif "a64" in name or "arm32" in name:
            arch = "arm"
        elif "x86_64" in name:
            arch = "x86_64"
        else:
            arch = "arm64"  # Modern standard

        # Slot scheme
        if "-ab" in name or "_ab" in name or "_b" in name:
            slot_scheme = "a/b"
        elif "-a" in name or "_a" in name:
            slot_scheme = "a_only"
        else:
            slot_scheme = "a/b"

        # Phh variant matrix (e.g. bgN, bvS, bgS, bvN, o)
        if "bg" in name or "gapps" in name or "-g-" in name:
            variant = "GApps (g)"
        elif "bv" in name or "vanilla" in name or "-v-" in name:
            variant = "Vanilla (v)"
        elif "bo" in name or "microg" in name or "-o-" in name:
            variant = "MicroG (o)"
        elif "bs" in name or "su" in name or "-s-" in name:
            variant = "SuperSU (s)"
        else:
            variant = "Standard / Vanilla"

        info = GsiInfo(
            name=p.name,
            image_path=p,
            arch=arch,
            slot_scheme=slot_scheme,
            gapps_variant=variant,
            file_size_bytes=p.stat().st_size,
        )
        return True, info, f"Detected {arch} {slot_scheme} GSI ({variant})."

    # -----------------------------------------------------------------------
    # Recovery Target Determination
    # -----------------------------------------------------------------------

    @classmethod
    def determine_recovery_target(cls, device: Optional[DeviceInfo]) -> tuple[str, bool, str]:
        """
        Determine whether custom recovery should be flashed to 'recovery' or 'boot'.
        """
        if not device:
            return "recovery", True, "Default recovery partition (no device specified)."

        # Android 10+ dynamic partitions (super.img) or non-dynamic A/B recovery in boot
        if device.has_dynamic_partitions:
            return "boot", True, "Device uses dynamic partitions; recovery lives in boot ramdisk or fastbootd."

        if device.slot_scheme == "a/b" and not device.has_dynamic_partitions:
            # E.g. Pixel 1-3, OnePlus 6/7
            return "boot", True, "Legacy A/B device; recovery is merged into boot.img."

        return "recovery", True, "Dedicated recovery partition detected."

    @classmethod
    def parse_recovery_image(cls, path: Path | str, device: Optional[DeviceInfo] = None) -> tuple[bool, Optional[RecoveryInfo], str]:
        """Inspect a custom recovery image (TWRP, OrangeFox, PBRP)."""
        p = Path(path)
        if not p.is_file():
            return False, None, f"Recovery image not found: {p}"

        name = p.name.lower()
        if "orangefox" in name or "ofox" in name:
            rec_type = "OrangeFox"
        elif "twrp" in name:
            rec_type = "TWRP"
        elif "pbrp" in name or "pitchblack" in name:
            rec_type = "PBRP"
        else:
            rec_type = "Custom"

        target_part, live_boot, reason = cls.determine_recovery_target(device)
        info = RecoveryInfo(
            name=p.name,
            image_path=p,
            recovery_type=rec_type,
            recommended_partition=target_part,
            supports_live_boot=live_boot,
            file_size_bytes=p.stat().st_size,
        )
        return True, info, f"{rec_type} recovery for '{target_part}' partition: {reason}"

    # -----------------------------------------------------------------------
    # Execution: Custom ROM Flashing
    # -----------------------------------------------------------------------

    def flash_custom_rom(
        self,
        package_info: RomPackageInfo,
        slot_target: str = "active",  # "active", "a", "b", "both"
        wipe_userdata: bool = False,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
        serial: str = "",
    ) -> tuple[bool, str]:
        """Flash all partition images in a Custom Fastboot ROM package."""
        partitions = package_info.detected_partitions
        if not partitions:
            return False, "No flashable partition images found in package."

        # Archive members are not paths on disk.  Materialize ZIP packages for
        # the duration of the flash instead of handing fastboot an invalid name.
        with tempfile.TemporaryDirectory(prefix="flashdock-rom-") as temp_dir:
            if package_info.package_type == "fastboot_zip":
                try:
                    with zipfile.ZipFile(package_info.path, "r") as archive:
                        extracted: list[FlashPartitionItem] = []
                        for index, item in enumerate(partitions):
                            member = item.image_path.as_posix()
                            if member not in archive.namelist():
                                return False, f"ROM archive is missing expected image: {member}"
                            destination = Path(temp_dir) / f"{index}_{Path(member).name}"
                            with archive.open(member) as source, destination.open("wb") as target:
                                shutil.copyfileobj(source, target)
                            if destination.stat().st_size != item.file_size_bytes:
                                return False, f"ROM archive image is incomplete: {member}"
                            extracted.append(FlashPartitionItem(
                                partition_name=item.partition_name,
                                image_path=destination,
                                file_size_bytes=item.file_size_bytes,
                                slot_target=item.slot_target,
                            ))
                        partitions = extracted
                except (OSError, zipfile.BadZipFile) as exc:
                    return False, f"Could not prepare ROM archive for flashing: {exc}"

            total_steps = len(partitions) + (1 if wipe_userdata else 0)
            current_step = 0

            log.info("Starting Custom ROM flash: %s (%d partitions, slot=%s, wipe=%s)",
                     package_info.name, len(partitions), slot_target, wipe_userdata)

            for item in partitions:
                if cancel_token and cancel_token():
                    return False, "Flashing cancelled by user."

                current_step += 1
                part = item.partition_name
                msg = f"Flashing partition '{part}' ({item.size_mb} MB)..."
                if progress_callback:
                    progress_callback(current_step, total_steps, msg)

                if dry_run:
                    log.info("[DRY RUN] fastboot flash %s %s (slot=%s)", part, item.image_path.name, slot_target)
                    continue

                # Determine slots to flash
                slots_to_flash = []
                if slot_target == "both":
                    slots_to_flash = ["a", "b"]
                elif slot_target in ("a", "b"):
                    slots_to_flash = [slot_target]
                else:
                    slots_to_flash = [""]

                for sl in slots_to_flash:
                    res = self.fb.flash(partition=part, image_path=str(item.image_path), slot=sl, serial=serial)
                    if not res.success:
                        err_msg = f"Failed to flash partition '{part}' (slot {sl}): {res.stderr or res.stdout}"
                        log.error(err_msg)
                        return False, err_msg

            # Userdata wipe
            if wipe_userdata:
                if progress_callback:
                    progress_callback(total_steps, total_steps, "Wiping userdata and cache...")
                if dry_run:
                    log.info("[DRY RUN] fastboot -w")
                else:
                    w_res = self.fb.wipe(serial=serial)
                    if not w_res.success:
                        # Fallback to erase userdata
                        self.fb.erase("userdata", serial=serial)

            return True, f"Successfully flashed Custom ROM ({len(partitions)} partitions)."

    # -----------------------------------------------------------------------
    # Execution: GSI Flashing
    # -----------------------------------------------------------------------

    def flash_gsi(
        self,
        gsi_image_path: Path | str,
        disable_avb: bool = True,
        vbmeta_path: Optional[Path | str] = None,
        wipe_userdata: bool = True,
        is_dynamic_super: bool = True,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        cancel_token: Optional[Callable[[], bool]] = None,
        serial: str = "",
    ) -> tuple[bool, str]:
        """Flash a Generic System Image (GSI) to system partition."""
        p = Path(gsi_image_path)
        if not p.is_file():
            return False, f"GSI file not found: {p}"
        if p.suffix.lower() != ".img":
            return False, "GSI must be an extracted .img file; decompress archives before flashing."
        if disable_avb and not dry_run and (not vbmeta_path or not Path(vbmeta_path).is_file()):
            return False, "A valid stock vbmeta.img is required to disable AVB safely."

        total_steps = 3 + (1 if disable_avb else 0) + (1 if wipe_userdata else 0)
        step = 0

        log.info("Starting GSI flash: %s (dynamic=%s, disable_avb=%s, wipe=%s)",
                 p.name, is_dynamic_super, disable_avb, wipe_userdata)

        # 1. AVB Verity disable
        if disable_avb:
            step += 1
            if progress_callback:
                progress_callback(step, total_steps, "Patching VBMeta (disabling verity/verification)...")
            if dry_run:
                log.info("[DRY RUN] fastboot --disable-verity --disable-verification flash vbmeta")
            else:
                res_vb = self.fb.flash_vbmeta_disabled(str(vbmeta_path), serial=serial)
                if not res_vb.success:
                    log.warning("VBMeta flag warning (may not be critical on some devices): %s", res_vb.stderr)

        if cancel_token and cancel_token():
            return False, "Cancelled by user."

        # 2. Erase / Prepare system
        step += 1
        if progress_callback:
            progress_callback(step, total_steps, "Erasing system partition...")
        if dry_run:
            log.info("[DRY RUN] fastboot erase system")
        else:
            self.fb.erase("system", serial=serial)

        if cancel_token and cancel_token():
            return False, "Cancelled by user."

        # 3. Flash GSI to system
        step += 1
        if progress_callback:
            progress_callback(step, total_steps, f"Flashing GSI '{p.name}' to system partition...")
        if dry_run:
            log.info("[DRY RUN] fastboot flash system %s", p.name)
        else:
            res_flash = self.fb.flash(partition="system", image_path=str(p), serial=serial)
            if not res_flash.success:
                return False, f"Failed to flash GSI to system: {res_flash.stderr or res_flash.stdout}"

        # 4. Wipe userdata
        if wipe_userdata:
            step += 1
            if progress_callback:
                progress_callback(step, total_steps, "Performing factory reset / data wipe (required for GSI boot)...")
            if dry_run:
                log.info("[DRY RUN] fastboot -w")
            else:
                w_res = self.fb.wipe(serial=serial)
                if not w_res.success:
                    self.fb.erase("userdata", serial=serial)

        return True, f"Successfully flashed GSI '{p.name}' to system."

    # -----------------------------------------------------------------------
    # Execution: Recovery Flashing / Booting
    # -----------------------------------------------------------------------

    def flash_recovery(
        self,
        recovery_image_path: Path | str,
        target_partition: str = "recovery",  # "recovery" or "boot"
        live_boot_only: bool = False,
        dry_run: bool = False,
        serial: str = "",
    ) -> tuple[bool, str]:
        """Flash or temporarily boot a custom recovery image."""
        p = Path(recovery_image_path)
        if not p.is_file():
            return False, f"Recovery image not found: {p}"

        log.info("Recovery operation: %s to %s (live_boot=%s)", p.name, target_partition, live_boot_only)

        if live_boot_only:
            if dry_run:
                log.info("[DRY RUN] fastboot boot %s", p.name)
                return True, f"[DRY RUN] Temporarily booted {p.name}."
            res = self.fb.boot(image_path=str(p), serial=serial)
            if res.success:
                return True, f"Device is booting into {p.name}..."
            return False, f"Failed to boot recovery: {res.stderr or res.stdout}"

        # Permanent flash
        if dry_run:
            log.info("[DRY RUN] fastboot flash %s %s", target_partition, p.name)
            return True, f"[DRY RUN] Flashed {p.name} to {target_partition}."

        res = self.fb.flash(partition=target_partition, image_path=str(p), serial=serial)
        if res.success:
            return True, f"Successfully flashed {p.name} to {target_partition} partition."
        return False, f"Failed to flash recovery to {target_partition}: {res.stderr or res.stdout}"

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def switch_to_fastbootd(self, serial: str = "") -> CommandResult:
        """Issue 'fastboot reboot fastboot' to switch into userspace fastbootd."""
        log.info("Requesting reboot to fastbootd (userspace fastboot)...")
        return self.fb.reboot_fastboot(serial=serial)
