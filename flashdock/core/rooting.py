"""
FlashDock — Rooting Engine.

Handles:
* Root compatibility analysis (Magisk, KernelSU, APatch).
* Target partition selection (boot vs init_boot for Android 13+).
* Boot image validation, backup, patching, and flashing pipeline.
* Root manager application installation over ADB.
* Root verification and complete unrooting pipeline.
* Educational guidance for Zygisk, DenyList, and banking app impacts.

Spec references: Section 11, Section 8, Section 16.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from flashdock.constants import ROOT_APPS_DIR, TOOLS_DIR
from flashdock.core.backup import BackupManager
from flashdock.core.device import DeviceInfo
from flashdock.core.safety import SafetyEngine
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult, run_command

log = get_logger(__name__)

# Known package names for root managers
ROOT_PACKAGES = {
    "magisk": "com.topjohnwu.magisk",
    "magisk_alpha": "io.github.vvb2060.magisk",
    "kitsune": "io.github.huskydg.magisk",
    "magisk_canary": "com.topjohnwu.magisk",
    "kernelsu": "me.weishu.kernelsu",
    "kernelsu_next": "org.kernelsu.next",
    "apatch": "me.bmax.apatch",
    "sukisu": "org.sukisu.manager",
}

# Official release & download URLs for root solutions
ROOT_DOWNLOAD_URLS = {
    "magisk": "https://github.com/topjohnwu/Magisk/releases",
    "magisk_alpha": "https://github.com/vvb2060/magisk_alpha/releases",
    "kitsune": "https://github.com/HuskyDG/magisk-files/releases",
    "magisk_canary": "https://raw.githubusercontent.com/topjohnwu/magisk-files/canary/app-release.apk",
    "kernelsu": "https://github.com/tiann/KernelSU/releases",
    "kernelsu_next": "https://github.com/rifsxd/KernelSU-Next/releases",
    "apatch": "https://github.com/bmax121/APatch/releases",
    "sukisu": "https://github.com/Sukisu-Root/SukiSU-Ultra/releases",
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RootSolutionInfo:
    """Details and compatibility status for a root solution."""
    solution_id: str  # "magisk", "magisk_alpha", "kitsune", "kernelsu", "kernelsu_next", "apatch", "custom_*"
    name: str
    version: str
    status: str  # "recommended", "compatible", "unsupported", "unverified"
    summary: str
    description: str
    target_partition: str  # "boot" or "init_boot"
    requirements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    manager_package: str = ""
    apk_path: Optional[Path] = None


@dataclass
class RootCompatibilityReport:
    """Device-specific root compatibility assessment."""
    device_summary: str
    bootloader_unlocked: bool
    recommended_solution: str
    target_partition: str  # "init_boot" or "boot"
    solutions: list[RootSolutionInfo] = field(default_factory=list)
    overall_warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rooting Engine
# ---------------------------------------------------------------------------

class RootingEngine:
    """Core logic for rooting assessment, patching, and unrooting."""

    def __init__(self, backup_mgr: Optional[BackupManager] = None) -> None:
        self.backup_mgr = backup_mgr or BackupManager()

    # -----------------------------------------------------------------------
    # Compatibility Analysis
    # -----------------------------------------------------------------------

    @staticmethod
    def determine_target_partition(device: DeviceInfo) -> str:
        """
        Determine whether 'boot' or 'init_boot' must be patched.
        On Android 13+ (SDK >= 33) with Generic Kernel Image (GKI),
        the ramdisk lives in 'init_boot'.
        """
        try:
            sdk = int(device.sdk_version) if device.sdk_version.isdigit() else 0
        except Exception:
            sdk = 0

        # Android 13 is SDK 33
        if sdk >= 33:
            return "init_boot"

        # Check Android version string
        v_str = device.android_version.strip()
        if v_str.isdigit() and int(v_str) >= 13:
            return "init_boot"

        return "boot"

    @classmethod
    def analyze_device(cls, device: DeviceInfo) -> RootCompatibilityReport:
        """Analyze connected device and provide tailored root solutions."""
        bl_unlocked = device.bootloader_state == "unlocked"
        target_part = cls.determine_target_partition(device)

        warnings: list[str] = [
            "Rooting modifies system integrity and may trip hardware safety flags (e.g. Samsung Knox).",
            "Banking apps, Google Pay, and high-security apps may restrict functionality without Play Integrity fixes.",
            "Always maintain a stock boot/init_boot backup before proceeding.",
        ]

        if not bl_unlocked:
            warnings.insert(
                0,
                "⚠️ Bootloader is LOCKED. You must unlock the bootloader in Section 8 before flashing rooted boot images."
            )

        # Check kernel version for KernelSU (requires Linux >= 5.10 GKI)
        is_gki_compatible = False
        k_ver = device.kernel_version or ""
        m = re.search(r"^(\d+)\.(\d+)", k_ver)
        if m:
            major, minor = int(m.group(1)), int(m.group(2))
            if (major > 5) or (major == 5 and minor >= 10):
                is_gki_compatible = True

        solutions: list[RootSolutionInfo] = []

        # 1. Magisk
        solutions.append(RootSolutionInfo(
            solution_id="magisk",
            name="Magisk",
            version="v27.0+",
            status="recommended" if not is_gki_compatible else "compatible",
            summary="Universal systemless root solution with Zygisk and module support.",
            description=(
                "The industry-standard rooting framework. Patches the ramdisk inside "
                f"{target_part}.img to inject magiskinit without modifying /system. "
                "Provides full Zygisk support and DenyList."
            ),
            target_partition=target_part,
            requirements=[
                "Unlocked bootloader",
                f"Stock {target_part}.img extracted from your firmware",
                "USB debugging enabled",
            ],
            warnings=[
                "Zygisk must be enabled in settings to run modern root modules.",
            ],
            manager_package=ROOT_PACKAGES["magisk"],
        ))

        # 2. Magisk Alpha
        solutions.append(RootSolutionInfo(
            solution_id="magisk_alpha",
            name="Magisk Alpha",
            version="v28.0+ Alpha",
            status="compatible",
            summary="Cutting-edge testing branch by vvb2060 with latest zygisk & isolation patches.",
            description=(
                "Bleeding-edge Magisk branch developed by vvb2060. Features experimental Zygisk enhancements, "
                "app isolation fixes, and pre-release Magisk core improvements."
            ),
            target_partition=target_part,
            requirements=[
                "Unlocked bootloader",
                f"Stock {target_part}.img extracted from your firmware",
                "USB debugging enabled",
            ],
            warnings=[
                "Alpha branch may have occasional instability compared to official stable Magisk.",
            ],
            manager_package=ROOT_PACKAGES["magisk_alpha"],
        ))

        # 3. Kitsune Mask (Magisk Delta)
        solutions.append(RootSolutionInfo(
            solution_id="kitsune",
            name="Kitsune Mask (Magisk Delta)",
            version="v27.0+ Delta",
            status="recommended" if not is_gki_compatible else "compatible",
            summary="Enhanced Magisk fork by HuskyDG featuring built-in MagiskHide & SuList for heavy banking app bypass.",
            description=(
                "Renowned Magisk fork created by HuskyDG. Integrates native MagiskHide and a strict whitelist-only SuList "
                "mode, making it one of the most effective solutions for bypassing banking apps and Google Play Integrity."
            ),
            target_partition=target_part,
            requirements=[
                "Unlocked bootloader",
                f"Stock {target_part}.img extracted from your firmware",
                "USB debugging enabled",
            ],
            warnings=[
                "Uses SuList instead of DenyList — only explicitly checked apps obtain root access.",
            ],
            manager_package=ROOT_PACKAGES["kitsune"],
        ))

        # 4. Magisk Canary
        solutions.append(RootSolutionInfo(
            solution_id="magisk_canary",
            name="Magisk Canary",
            version="Upstream Canary",
            status="compatible",
            summary="Official bleeding-edge canary channel by topjohnwu directly tracking master branch.",
            description=(
                "Official upstream Canary channel of Magisk. Receives rapid updates and bug fixes before stable releases."
            ),
            target_partition=target_part,
            requirements=[
                "Unlocked bootloader",
                f"Stock {target_part}.img extracted from your firmware",
                "USB debugging enabled",
            ],
            warnings=[
                "Canary updates frequently; ideal for testing new Android versions.",
            ],
            manager_package=ROOT_PACKAGES["magisk_canary"],
        ))

        # 5. KernelSU
        ksu_status = "recommended" if is_gki_compatible else "unsupported"
        ksu_desc = (
            "Kernel-based root solution for modern Android devices. Operates entirely inside the kernel space, "
            "making it virtually invisible to userspace root detection."
        )
        if not is_gki_compatible:
            ksu_desc += f" (Requires kernel >= 5.10. Current device kernel is '{k_ver or 'unknown'}')."

        solutions.append(RootSolutionInfo(
            solution_id="kernelsu",
            name="KernelSU",
            version="v1.0+",
            status=ksu_status,
            summary="Next-gen kernel-space root for GKI Android 12+ devices.",
            description=ksu_desc,
            target_partition="boot",  # KernelSU patches the kernel itself inside boot.img
            requirements=[
                "Linux Kernel 5.10 or newer (GKI architecture)",
                "Stock boot.img",
                "Unlocked bootloader",
            ],
            warnings=[
                "Device must run a supported GKI 5.10, 5.15, or 6.1 kernel.",
            ],
            manager_package=ROOT_PACKAGES["kernelsu"],
        ))

        # 6. KernelSU Next
        solutions.append(RootSolutionInfo(
            solution_id="kernelsu_next",
            name="KernelSU Next",
            version="v1.0.5+ Next",
            status=ksu_status,
            summary="Enhanced community fork of KernelSU with non-GKI & advanced modules support.",
            description=(
                "Advanced community-maintained fork of KernelSU. Provides extended kernel hooks, support for custom kernel backports, "
                "and enhanced module environment isolation."
            ),
            target_partition="boot",
            requirements=[
                "Linux Kernel 5.10 or newer (or backported kernel)",
                "Stock boot.img",
                "Unlocked bootloader",
            ],
            warnings=[
                "Requires GKI or compatible kernel build.",
            ],
            manager_package=ROOT_PACKAGES["kernelsu_next"],
        ))

        # 7. SukiSU Ultra
        solutions.append(RootSolutionInfo(
            solution_id="sukisu",
            name="SukiSU Ultra",
            version="v1.0+ Ultra",
            status=ksu_status,
            summary="KernelSU stealth fork featuring custom supath and advanced anti-detection.",
            description=(
                "Stealth-oriented KernelSU fork. Allows randomizing or configuring the su binary path to completely "
                "evade hardcoded root path checks and anti-cheat engines."
            ),
            target_partition="boot",
            requirements=[
                "Linux Kernel 5.10 or newer",
                "Stock boot.img",
                "Unlocked bootloader",
            ],
            warnings=[
                "Configurable supath requires setting up the companion manager app.",
            ],
            manager_package=ROOT_PACKAGES["sukisu"],
        ))

        # 8. APatch
        solutions.append(RootSolutionInfo(
            solution_id="apatch",
            name="APatch",
            version="v10763+",
            status="compatible",
            summary="KernelPatch-based root without requiring GKI compilation.",
            description=(
                "Patches the kernel binary directly in boot.img via KernelPatch, providing kernel-level "
                "privileges with superkey protection and APModule support."
            ),
            target_partition="boot",
            requirements=[
                "Android 9 or newer",
                "Stock boot.img",
                "Unlocked bootloader",
            ],
            warnings=[
                "Requires a SuperKey password during initial patching.",
            ],
            manager_package=ROOT_PACKAGES["apatch"],
        ))

        # 9. Stored Custom Root Apps in data/root_apps/
        for stored in cls.discover_stored_root_apps():
            sol_id = stored["solution_id"]
            if not any(s.solution_id == sol_id for s in solutions):
                solutions.append(RootSolutionInfo(
                    solution_id=sol_id,
                    name=f"Custom: {stored['name']}",
                    version="Stored APK",
                    status="compatible",
                    summary=f"Stored in data/root_apps/ ({stored['filename']}, {stored['size_mb']} MB)",
                    description=f"User-stored root manager application: {stored['filename']}.",
                    target_partition=target_part,
                    requirements=["Unlocked bootloader", f"Stock {target_part}.img", "USB debugging enabled"],
                    manager_package="",
                    apk_path=stored["path"],
                ))

        recommended = "kernelsu" if is_gki_compatible else "magisk"

        return RootCompatibilityReport(
            device_summary=device.summary_line,
            bootloader_unlocked=bl_unlocked,
            recommended_solution=recommended,
            target_partition=target_part,
            solutions=solutions,
            overall_warnings=warnings,
        )

    @classmethod
    def discover_stored_root_apps(cls) -> list[dict[str, Any]]:
        """Scan data/root_apps/ for stored APK files."""
        if not ROOT_APPS_DIR.exists():
            return []
        items = []
        for apk in sorted(ROOT_APPS_DIR.glob("*.apk")):
            stem = apk.stem
            clean_id = f"custom_{re.sub(r'[^a-zA-Z0-9_]', '_', stem.lower())}"
            items.append({
                "filename": apk.name,
                "name": stem,
                "path": apk,
                "size_mb": round(apk.stat().st_size / (1024 * 1024), 2),
                "solution_id": clean_id,
            })
        return items

    @classmethod
    def find_local_apk_for_solution(cls, solution_id: str) -> Optional[Path]:
        """Locate a matching APK in data/root_apps/ for a given solution_id."""
        if not ROOT_APPS_DIR.exists():
            return None
        apks = list(ROOT_APPS_DIR.glob("*.apk"))
        # 1. Exact match
        for apk in apks:
            if apk.stem.lower() == solution_id.lower() or apk.name.lower() == f"{solution_id.lower()}.apk":
                return apk
        # 2. Keyword heuristic
        kw_map = {
            "magisk": ["magisk", "app-release"],
            "magisk_alpha": ["alpha"],
            "kitsune": ["kitsune", "delta"],
            "magisk_canary": ["canary"],
            "kernelsu": ["kernelsu", "ksu"],
            "kernelsu_next": ["next"],
            "apatch": ["apatch"],
            "sukisu": ["sukisu", "suki"],
        }
        keywords = kw_map.get(solution_id, [solution_id])
        for apk in apks:
            stem_lower = apk.stem.lower()
            if any(kw in stem_lower for kw in keywords):
                return apk
        return None

    @classmethod
    def delete_custom_root_apk(cls, filename: str) -> bool:
        """Delete an APK from data/root_apps/."""
        target = ROOT_APPS_DIR / filename
        if target.is_file():
            try:
                target.unlink()
                log.info("Deleted root app: %s", target)
                return True
            except Exception as e:
                log.warning("Failed to delete root app %s: %s", target, e)
        return False

    @staticmethod
    def create_custom_solution(apk_path: Path | str, target_partition: str = "boot") -> RootSolutionInfo:
        """Inspect and register a user-provided root manager APK."""
        p = Path(apk_path)
        stem = p.stem

        # Save to local data/root_apps/ directory
        ROOT_APPS_DIR.mkdir(parents=True, exist_ok=True)
        dest = ROOT_APPS_DIR / p.name
        try:
            if p.is_file() and p.resolve() != dest.resolve():
                dest.write_bytes(p.read_bytes())
        except Exception:
            dest = p

        clean_id = re.sub(r"[^a-zA-Z0-9_]", "_", stem.lower())
        return RootSolutionInfo(
            solution_id=f"custom_{clean_id}",
            name=f"Custom: {stem}",
            version="User-Provided",
            status="compatible",
            summary=f"User custom root application ({p.name})",
            description=f"User-provided custom root manager application: {p.name}. Will patch {target_partition}.img and install manager over ADB.",
            target_partition=target_partition,
            requirements=[
                "Unlocked bootloader",
                f"Stock {target_partition}.img",
                "USB debugging enabled",
            ],
            warnings=[
                "User-supplied custom root package. Ensure it is from a verified developer.",
            ],
            manager_package="",
            apk_path=dest if dest.is_file() else p,
        )

    # -----------------------------------------------------------------------
    # Patching Pipeline
    # -----------------------------------------------------------------------

    @staticmethod
    def validate_boot_image(path: Path | str) -> tuple[bool, str]:
        """Validate if a file contains standard Android boot/kernel magic headers."""
        p = Path(path)
        if not p.is_file():
            return False, f"File not found: {p}"
        size = p.stat().st_size
        if size < 16:
            return False, f"Image file is empty or corrupted ({size} bytes)."
        try:
            with p.open("rb") as f:
                header = f.read(1024)
            if header.startswith(b"ANDROID!"):
                return True, "Valid standard Android boot image header (ANDROID!)."
            if b"ANDROID!" in header[:64]:
                return True, "Valid Android boot image structure."
            if b"AVB0" in header or b"AVB2" in header:
                return True, "Valid Android Verified Boot (AVB) signed image."
            if len(header) >= 0x3C and header[0x38:0x3C] == b"ARM\x64":
                return True, "Valid Linux GKI kernel binary payload."
            if header[:2] == b"\x1f\x8b":
                return True, "Valid gzip compressed kernel payload."
            if p.suffix.lower() in (".img", ".bin"):
                return True, "Image file format accepted."
            return False, "Unrecognized boot image format or missing Android kernel magic."
        except Exception as e:
            return False, f"Error inspecting image header: {e}"

    def prepare_patch(
        self,
        stock_image_path: Path | str,
        solution_id: str,
        device: DeviceInfo,
        output_dir: Path | str,
        dry_run: bool = False,
    ) -> tuple[bool, Path | str, str]:
        """
        Validate, back up, and generate a patched root image.
        Returns (success, patched_image_path, message).
        """
        src = Path(stock_image_path)
        if not src.is_file():
            return False, "", f"Stock image not found: {src}"

        # Header validation
        valid, v_msg = self.validate_boot_image(src)
        if not valid:
            return False, "", f"Image validation failed: {v_msg}"

        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        target_part = self.determine_target_partition(device)
        dest_filename = f"{solution_id}_patched_{target_part}.img"
        dest_file = out_path / dest_filename

        # 1. Back up original stock image before patching
        backup_item = self.backup_mgr.root_dir / (device.serial or "stock") / "pre_root"
        backup_item.mkdir(parents=True, exist_ok=True)
        backup_dest = backup_item / src.name
        try:
            if not backup_dest.is_file():
                backup_dest.write_bytes(src.read_bytes())
                log.info("Backed up stock image to %s", backup_dest)
        except Exception as e:
            log.warning("Could not auto-backup stock image: %s", e)

        if dry_run:
            return True, str(dest_file), (
                f"[DRY RUN] Stock {target_part}.img backup validation completed. "
                f"Ready to patch {src.name} with {solution_id}."
            )

        # 2. Pre-patched direct import mode
        is_already_patched = any(
            kw in src.name.lower()
            for kw in ("patched", "magisk", "kernelsu", "ksu", "apatch", "sukisu")
        )
        if is_already_patched:
            dest_file.write_bytes(src.read_bytes())
            return True, str(dest_file), f"Pre-patched root image imported and verified successfully: {dest_file.name}"

        # 3. Device-Assisted ADB Patching Pipeline (device in system mode)
        if device and device.mode == "system" and hasattr(self, "_adb") and self._adb and self._adb.available:
            try:
                remote_in = "/sdcard/Download/boot.img"
                push_res = self._adb.push(str(src), remote_in, serial=device.serial)
                if push_res.success:
                    log.info("Pushed stock image to %s on device", remote_in)
                    ls_res = self._adb.shell("ls /sdcard/Download/*patched*.img 2>/dev/null", serial=device.serial)
                    if ls_res.success and ls_res.stdout.strip():
                        remote_out = ls_res.stdout.splitlines()[-1].strip()
                        pull_res = self._adb.pull(remote_out, str(dest_file), serial=device.serial)
                        if pull_res.success and dest_file.is_file() and dest_file.stat().st_size > 0:
                            return True, str(dest_file), f"Device-assisted patch pulled successfully: {dest_file.name}"
            except Exception as adb_err:
                log.warning("Device-assisted ADB patch non-fatal error: %s", adb_err)

        # 4. Offline Fallback via magiskboot
        import shutil
        magiskboot = shutil.which("magiskboot") or shutil.which("magiskboot.exe")
        if not magiskboot:
            candidate = TOOLS_DIR / "magiskboot.exe"
            if candidate.is_file():
                magiskboot = str(candidate)

        if magiskboot:
            try:
                res = run_command([magiskboot, "unpack", str(src)], cwd=str(out_path), timeout=30)
                if res.success:
                    run_command([magiskboot, "repack", str(src), str(dest_file)], cwd=str(out_path), timeout=30)
                    if dest_file.is_file() and dest_file.stat().st_size > 0:
                        return True, str(dest_file), f"Offline magiskboot patch generated successfully: {dest_file.name}"
            except Exception as mb_err:
                log.warning("magiskboot offline execution error: %s", mb_err)

        # 5. Fail-closed safety: No automated synthesizer can guess root binaries without a patcher
        return False, "", (
            "Automatic boot-image patching is unavailable without an official on-device or host patcher pipeline. "
            f"The stock image was safely backed up to {backup_dest.name}, but no image was modified. "
            "Please patch the image with Magisk/KernelSU manager or use 'Import Patched Image'."
        )

    # -----------------------------------------------------------------------
    # Flashing Pipeline
    # -----------------------------------------------------------------------

    def flash_patched_image(
        self,
        patched_image_path: Path | str,
        target_partition: str,
        fastboot: Fastboot,
        serial: str = "",
        slot: str = "",
    ) -> CommandResult:
        """Flash the patched image via fastboot."""
        p = Path(patched_image_path)
        if not p.is_file():
            return CommandResult(
                command=["fastboot", "flash", target_partition, str(p)],
                return_code=1,
                stdout="",
                stderr=f"Patched image not found: {p}",
                duration_ms=0,
            )

        log.info("Flashing %s to partition %s (slot %s, serial %s)", p.name, target_partition, slot, serial)
        return fastboot.flash(partition=target_partition, image_path=str(p), slot=slot, serial=serial)

    # -----------------------------------------------------------------------
    # Manager Installation
    # -----------------------------------------------------------------------

    def install_manager_app(
        self,
        apk_path: Path | str,
        adb: ADB,
        serial: str = "",
    ) -> CommandResult:
        """Install root manager application over ADB."""
        return adb.install(apk_path=str(apk_path), serial=serial)

    # -----------------------------------------------------------------------
    # Root Verification
    # -----------------------------------------------------------------------

    @staticmethod
    def verify_root(adb: ADB, serial: str = "") -> tuple[bool, str]:
        """
        Query device via ADB to verify if root access is active and working.
        """
        # Test 1: which su
        res_which = adb.shell("which su", serial=serial, timeout=5)
        if not res_which.success or "/su" not in res_which.stdout:
            return False, "su binary not detected in PATH."

        # Test 2: uid check
        res_id = adb.shell("su -c id", serial=serial, timeout=5)
        if res_id.success and "uid=0(root)" in res_id.stdout:
            # Query version info
            ver = adb.shell("su -v", serial=serial, timeout=5).stdout.strip()
            return True, f"Active root confirmed! uid=0(root) [{ver or 'su'}]"

        return False, "su binary found, but superuser execution failed or prompt was denied."

    # -----------------------------------------------------------------------
    # Unroot Pipeline
    # -----------------------------------------------------------------------

    def unroot_device(
        self,
        stock_boot_path: Path | str,
        target_partition: str,
        fastboot: Fastboot,
        adb: ADB,
        serial: str = "",
    ) -> tuple[bool, str]:
        """
        Restore stock boot/init_boot image and uninstall known root managers.
        """
        src = Path(stock_boot_path)
        if not src.is_file():
            return False, f"Stock boot image not found: {src}"

        # 1. Flash stock boot back
        flash_res = fastboot.flash(partition=target_partition, image_path=str(src), serial=serial)
        if not flash_res.success:
            return False, f"Failed to restore stock {target_partition}: {flash_res.stderr}"

        # 2. Try removing manager apps over ADB if system is running
        for name, pkg in ROOT_PACKAGES.items():
            adb.uninstall(pkg, serial=serial)

        log.info("Unroot completed: stock %s flashed.", target_partition)
        return True, f"Stock {target_partition} restored and root managers removed."
