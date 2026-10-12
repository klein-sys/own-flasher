"""
FlashDock — Universal Sideloading & App Manager Engine (Phase 23).

Provides:
1. Single & Batch APK Installation with advanced runtime flags (-r, -d, -g, -t, --user 0).
2. Google Play Protect & Android 14+ (SDK 34+) restriction bypasses (--bypass-low-target-sdk-block).
3. Split APK & Bundle Support (.xapk, .apks, .apkm) with automatic extraction,
   atomic 'adb install-multiple', and automated expansion OBB file placement into /sdcard/Android/obb/.
4. Recovery Mode OTA Sideload ('adb sideload <update.zip>') with byte-accurate progress parsing.
5. Pure-Python APK & XAPK Metadata Extractor (package name, version, SDK bounds, app icon).
6. Installed Package Inspector & Debloater (Pull APK, Clear Cache/Data, Force Stop, Disable/Freeze, Uninstall).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.runner import CommandResult

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ApkMetadata:
    """Parsed metadata for an APK or Split App Bundle."""
    package_name: str = ""
    version_name: str = ""
    version_code: int = 0
    min_sdk: int = 0
    target_sdk: int = 0
    app_label: str = ""
    is_split: bool = False
    file_path: str = ""
    file_size_bytes: int = 0
    split_names: list[str] = field(default_factory=list)
    obb_files: list[str] = field(default_factory=list)
    icon_bytes: Optional[bytes] = None

    @property
    def file_size_mb(self) -> float:
        return self.file_size_bytes / (1024 * 1024)

    @property
    def summary_line(self) -> str:
        name = self.app_label or self.package_name or Path(self.file_path).name
        v = f"v{self.version_name}" if self.version_name else f"code {self.version_code}"
        sdk = f"Min SDK {self.min_sdk}" if self.min_sdk else ""
        parts = [p for p in [name, v, sdk] if p]
        return " • ".join(parts)


@dataclass
class SideloadFlags:
    """Installation flags for ADB package manager."""
    grant_permissions: bool = True          # -g: Grant all runtime permissions
    allow_downgrade: bool = True            # -d: Allow version downgrade
    reinstall: bool = True                  # -r: Reinstall existing application
    bypass_low_sdk_block: bool = False      # --bypass-low-target-sdk-block (Android 14+ / SDK 34+)
    allow_test_packages: bool = False       # -t: Allow installing test packages
    install_user_0: bool = False            # --user 0: Install for primary user only

    def to_adb_args(self, device_sdk: int = 0) -> list[str]:
        """Convert flags to ADB install argument list."""
        args: list[str] = []
        if self.reinstall:
            args.append("-r")
        if self.allow_downgrade:
            args.append("-d")
        if self.grant_permissions:
            args.append("-g")
        if self.allow_test_packages:
            args.append("-t")
        if self.install_user_0:
            args.extend(["--user", "0"])
        # Android 14+ (SDK 34+) legacy app block bypass
        if self.bypass_low_sdk_block or device_sdk >= 34:
            args.append("--bypass-low-target-sdk-block")
        return args


@dataclass
class SideloadAppItem:
    """Representation of an installed package on the target device."""
    package_name: str
    path: str = ""
    is_system: bool = False
    is_enabled: bool = True
    category: str = "user"  # "user", "bloat", "system", "disabled"
    label: str = ""


# ---------------------------------------------------------------------------
# Pure-Python AXML (Binary AndroidManifest.xml) & Archive Metadata Extractor
# ---------------------------------------------------------------------------

class _AXMLParser:
    """Lightweight pure-Python binary Android XML parser to extract manifest metadata."""

    CHUNK_STRING_POOL = 0x0001
    CHUNK_XML_START_TAG = 0x0102

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.strings: list[str] = []
        self._parse_string_pool()

    def _parse_string_pool(self) -> None:
        if len(self.data) < 32:
            return
        
        # Seek string pool chunk header
        offset = 8
        while offset + 8 <= len(self.data):
            chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", self.data, offset)
            if chunk_type == self.CHUNK_STRING_POOL:
                string_count, style_count, flags, strings_start, styles_start = struct.unpack_from(
                    "<IIIII", self.data, offset + 8
                )
                is_utf8 = bool(flags & 0x00000100)

                offsets_start = offset + header_size
                string_offsets = []
                for i in range(string_count):
                    off_pos = offsets_start + i * 4
                    if off_pos + 4 <= len(self.data):
                        string_offsets.append(struct.unpack_from("<I", self.data, off_pos)[0])

                pool_strings_base = offset + strings_start
                for str_off in string_offsets:
                    curr = pool_strings_base + str_off
                    if curr >= len(self.data):
                        self.strings.append("")
                        continue

                    try:
                        if is_utf8:
                            # Skip utf16 length & utf8 length varints
                            p = curr
                            while p < len(self.data) and (self.data[p] & 0x80):
                                p += 1
                            p += 1
                            u8_len = self.data[p] if p < len(self.data) else 0
                            p += 1
                            str_bytes = self.data[p:p + u8_len]
                            self.strings.append(str_bytes.decode("utf-8", errors="replace"))
                        else:
                            u16_len = struct.unpack_from("<H", self.data, curr)[0]
                            curr += 2
                            str_bytes = self.data[curr:curr + (u16_len * 2)]
                            self.strings.append(str_bytes.decode("utf-16le", errors="replace"))
                    except Exception:
                        self.strings.append("")
                return
            offset += max(chunk_size, 8)

    def extract_manifest_attributes(self) -> dict[str, str | int]:
        """Scan XML elements and extract manifest attributes."""
        res: dict[str, str | int] = {}
        if not self.strings:
            return res

        offset = 8
        while offset + 8 <= len(self.data):
            chunk_type, header_size, chunk_size = struct.unpack_from("<HHI", self.data, offset)
            if chunk_type == self.CHUNK_XML_START_TAG:
                # Element chunk: line_number, comment, ns, name, attr_start, attr_size, attr_count
                if offset + 36 <= len(self.data):
                    _, _, _, tag_name_idx, attr_start, attr_size, attr_count = struct.unpack_from(
                        "<IIIIHHH", self.data, offset + 16
                    )
                    attr_base = offset + 16 + attr_start
                    for i in range(attr_count):
                        a_pos = attr_base + (i * attr_size)
                        if a_pos + 20 <= len(self.data):
                            _, name_idx, val_idx, val_type, val_data = struct.unpack_from(
                                "<IIIIi", self.data, a_pos
                            )
                            attr_name = self.strings[name_idx] if 0 <= name_idx < len(self.strings) else ""
                            attr_val = self.strings[val_idx] if 0 <= val_idx < len(self.strings) else ""

                            if attr_name == "package":
                                res["package"] = attr_val or self._resolve_str(val_data)
                            elif attr_name == "versionName":
                                res["versionName"] = attr_val or str(val_data)
                            elif attr_name == "versionCode":
                                res["versionCode"] = val_data
                            elif attr_name == "minSdkVersion":
                                res["minSdkVersion"] = val_data if val_type in (16, 17) else (int(attr_val) if attr_val.isdigit() else val_data)
                            elif attr_name == "targetSdkVersion":
                                res["targetSdkVersion"] = val_data if val_type in (16, 17) else (int(attr_val) if attr_val.isdigit() else val_data)
                            elif attr_name == "label":
                                if attr_val:
                                    res["label"] = attr_val
            offset += max(chunk_size, 8)

        # Fallback heuristic if attributes weren't directly mapped
        if "package" not in res:
            for s in self.strings:
                if re.match(r"^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)+$", s):
                    # Filter out standard Android schemas
                    if not s.startswith("http") and "android" not in s.split(".")[0]:
                        res["package"] = s
                        break
        return res

    def _resolve_str(self, idx: int) -> str:
        if 0 <= idx < len(self.strings):
            return self.strings[idx]
        return ""


def extract_apk_metadata(file_path: str | Path) -> ApkMetadata:
    """Extract metadata, version codes, split lists, and icon bytes from APK or Split Bundle."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    meta = ApkMetadata(
        file_path=str(path.resolve()),
        file_size_bytes=path.stat().st_size,
    )

    ext = path.suffix.lower()

    if not zipfile.is_zipfile(path):
        meta.package_name = path.stem
        meta.app_label = path.stem
        return meta

    try:
        with zipfile.ZipFile(path, "r") as zf:
            namelist = zf.namelist()

            # 1. Check for XAPK / APKM / APKS manifest.json
            if "manifest.json" in namelist:
                meta.is_split = True
                try:
                    manifest_data = json.loads(zf.read("manifest.json").decode("utf-8"))
                    meta.package_name = manifest_data.get("package_name", "")
                    meta.app_label = manifest_data.get("name", "")
                    meta.version_name = manifest_data.get("version_name", "")
                    vcode = manifest_data.get("version_code", 0)
                    meta.version_code = int(vcode) if str(vcode).isdigit() else 0
                    minsdk = manifest_data.get("min_sdk_version", 0)
                    meta.min_sdk = int(minsdk) if str(minsdk).isdigit() else 0
                    targetsdk = manifest_data.get("target_sdk_version", 0)
                    meta.target_sdk = int(targetsdk) if str(targetsdk).isdigit() else 0
                except Exception as e:
                    log.warning("Could not parse manifest.json in %s: %s", path.name, e)

            # Check for split APK contents
            apk_entries = [name for name in namelist if name.lower().endswith(".apk")]
            if len(apk_entries) > 1 or ext in (".xapk", ".apks", ".apkm"):
                meta.is_split = True
                meta.split_names = apk_entries

            # Check for expansion OBB files
            obb_entries = [name for name in namelist if name.lower().endswith(".obb")]
            meta.obb_files = obb_entries

            # Read App Icon if available
            for icon_cand in ("icon.png", "logo.png"):
                if icon_cand in namelist:
                    meta.icon_bytes = zf.read(icon_cand)
                    break

            # 2. Extract metadata from AndroidManifest.xml (from base APK or top-level)
            manifest_bytes: Optional[bytes] = None
            if "AndroidManifest.xml" in namelist:
                manifest_bytes = zf.read("AndroidManifest.xml")
            elif apk_entries:
                # Find base.apk or first apk
                base_cand = next((a for a in apk_entries if "base" in a.lower()), apk_entries[0])
                try:
                    sub_zip = zipfile.ZipFile(zf.open(base_cand))
                    if "AndroidManifest.xml" in sub_zip.namelist():
                        manifest_bytes = sub_zip.read("AndroidManifest.xml")
                    for ic in sub_zip.namelist():
                        if "ic_launcher" in ic.lower() and ic.lower().endswith(".png"):
                            meta.icon_bytes = sub_zip.read(ic)
                            break
                except Exception:
                    pass

            if manifest_bytes:
                parser = _AXMLParser(manifest_bytes)
                attrs = parser.extract_manifest_attributes()
                if not meta.package_name and attrs.get("package"):
                    meta.package_name = str(attrs["package"])
                if not meta.version_name and attrs.get("versionName"):
                    meta.version_name = str(attrs["versionName"])
                if not meta.version_code and attrs.get("versionCode"):
                    meta.version_code = int(attrs["versionCode"])
                if not meta.min_sdk and attrs.get("minSdkVersion"):
                    meta.min_sdk = int(attrs["minSdkVersion"])
                if not meta.target_sdk and attrs.get("targetSdkVersion"):
                    meta.target_sdk = int(attrs["targetSdkVersion"])
                if not meta.app_label and attrs.get("label"):
                    meta.app_label = str(attrs["label"])

            # Fallback icon search if still None
            if not meta.icon_bytes:
                for name in namelist:
                    if ("ic_launcher" in name.lower() or "app_icon" in name.lower()) and name.lower().endswith(".png"):
                        meta.icon_bytes = zf.read(name)
                        break

    except Exception as exc:
        log.warning("Metadata extraction failed for %s: %s", path.name, exc)

    if not meta.package_name:
        meta.package_name = path.stem.replace(".apk", "")
    if not meta.app_label:
        meta.app_label = meta.package_name

    return meta


# ---------------------------------------------------------------------------
# Sideload Manager Class
# ---------------------------------------------------------------------------

class SideloadManager:
    """Orchestrates single, split, and recovery sideloading via ADB."""

    def __init__(self, adb: Optional[ADB] = None, dry_run: bool = False) -> None:
        self.adb = adb or ADB()
        self.dry_run = dry_run

    def get_device_sdk(self, serial: str = "") -> int:
        """Fetch target device SDK API level."""
        sdk_str = self.adb.getprop("ro.build.version.sdk", serial=serial)
        if sdk_str and sdk_str.strip().isdigit():
            return int(sdk_str.strip())
        return 0

    def install_apk(
        self,
        apk_path: str | Path,
        flags: Optional[SideloadFlags] = None,
        serial: str = "",
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        """Install single APK with runtime permission and restriction bypass flags."""
        path = Path(apk_path)
        if not path.is_file():
            return False, f"File not found: {path}"

        flags = flags or SideloadFlags()
        dev_sdk = self.get_device_sdk(serial=serial)
        extra_args = flags.to_adb_args(device_sdk=dev_sdk)

        cmd = ["install"] + extra_args + [str(path.resolve())]
        if progress_cb:
            progress_cb(f"Executing: adb {' '.join(cmd)}")

        res = self.adb._run(cmd, serial=serial, timeout=300, action="sideload_install_apk")
        output = res.output

        if "success" in output.lower():
            if progress_cb:
                progress_cb(f"Success: Installed {path.name}")
            return True, f"Successfully installed {path.name}"

        # Error diagnostics
        err_msg = res.stderr or res.stdout
        if "INSTALL_FAILED_DEPRECATED_SDK_VERSION" in output:
            err_msg = (
                "Android 14+ blocked this legacy APK because its target SDK is too old.\n"
                "Enable 'Bypass Android 14+ Low SDK block' to force-install."
            )
        elif "INSTALL_FAILED_VERSION_DOWNGRADE" in output:
            err_msg = "Device has a newer version installed. Enable 'Allow version downgrade (-d)'."
        elif "INSTALL_FAILED_ALREADY_EXISTS" in output:
            err_msg = "Package already exists. Enable 'Reinstall existing application (-r)'."
        elif "INSTALL_FAILED_INSUFFICIENT_STORAGE" in output:
            err_msg = "Device has insufficient free internal storage."

        if progress_cb:
            progress_cb(f"Failed: {err_msg}")
        return False, err_msg

    def install_split_bundle(
        self,
        bundle_path: str | Path,
        flags: Optional[SideloadFlags] = None,
        serial: str = "",
        progress_cb: Optional[Callable[[str], None]] = None,
    ) -> tuple[bool, str]:
        """Unpack .xapk / .apks bundle, run 'install-multiple', and place expansion OBBs."""
        path = Path(bundle_path)
        if not path.is_file():
            return False, f"Bundle file not found: {path}"

        flags = flags or SideloadFlags()
        dev_sdk = self.get_device_sdk(serial=serial)
        extra_args = flags.to_adb_args(device_sdk=dev_sdk)

        temp_dir = Path(tempfile.mkdtemp(prefix="flashdock_bundle_"))
        try:
            if progress_cb:
                progress_cb(f"Unpacking bundle: {path.name}...")

            with zipfile.ZipFile(path, "r") as zf:
                zf.extractall(temp_dir)

            # Find all APK files in extracted folder
            apk_files = list(temp_dir.rglob("*.apk"))
            if not apk_files:
                return False, f"No APK files found inside bundle: {path.name}"

            # Sort so base APK comes first
            apk_files.sort(key=lambda p: (0 if "base" in p.name.lower() else 1, p.name))
            apk_paths_str = [str(p.resolve()) for p in apk_files]

            if progress_cb:
                progress_cb(f"Installing {len(apk_files)} split packages via adb install-multiple...")

            cmd = ["install-multiple"] + extra_args + apk_paths_str
            res = self.adb._run(cmd, serial=serial, timeout=600, action="sideload_install_multiple")

            if "success" not in res.output.lower():
                err = res.stderr or res.stdout
                if "INSTALL_FAILED_DEPRECATED_SDK_VERSION" in res.output:
                    err = "Android 14+ blocked this split bundle. Enable 'Bypass Low SDK block'."
                if progress_cb:
                    progress_cb(f"Install-multiple failed: {err}")
                return False, f"Split installation failed: {err}"

            # Push expansion OBB files if present
            obb_files = list(temp_dir.rglob("*.obb"))
            if obb_files:
                if progress_cb:
                    progress_cb(f"Found {len(obb_files)} OBB expansion files. Transferring...")

                # Parse package name from metadata or directory structure
                meta = extract_apk_metadata(path)
                pkg_name = meta.package_name

                remote_obb_dir = f"/sdcard/Android/obb/{pkg_name}"
                self.adb.shell(f"mkdir -p {remote_obb_dir}", serial=serial)

                for obb in obb_files:
                    if progress_cb:
                        progress_cb(f"Pushing {obb.name} -> {remote_obb_dir}...")
                    push_res = self.adb.push(str(obb.resolve()), f"{remote_obb_dir}/{obb.name}", serial=serial)
                    if not push_res.success:
                        log.warning("Failed to push OBB %s: %s", obb.name, push_res.stderr)

            if progress_cb:
                progress_cb(f"Success: Installed split bundle {path.name}")
            return True, f"Successfully installed {path.name} with {len(apk_files)} splits."

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def sideload_ota_zip(
        self,
        zip_path: str | Path,
        serial: str = "",
        progress_cb: Optional[Callable[[int, str], None]] = None,
    ) -> tuple[bool, str]:
        """Sideload full OTA update or recovery package with live percentage parsing."""
        path = Path(zip_path)
        if not path.is_file():
            return False, f"OTA ZIP file not found: {path}"

        if progress_cb:
            progress_cb(0, f"Preparing recovery sideload: {path.name}...")

        # Execute adb sideload
        cmd = ["sideload", str(path.resolve())]
        res = self.adb._run(cmd, serial=serial, timeout=1800, action="adb_sideload_ota")

        # Parse output for serving progress
        out = res.output
        pct = 100 if res.success else 0
        matches = re.findall(r"\(~(\d+)%\)", out)
        if matches:
            pct = int(matches[-1])

        if res.success or "total xfer:" in out.lower() or "success" in out.lower():
            if progress_cb:
                progress_cb(100, f"OTA Sideload complete: {path.name}")
            return True, f"Successfully sideloaded {path.name}"

        err = res.stderr or res.stdout
        if "device not found" in err.lower() or "no devices" in err.lower():
            err = "Device not detected in recovery or sideload mode. Reboot to Recovery first."
        if progress_cb:
            progress_cb(pct, f"Sideload failed: {err}")
        return False, err

    def list_installed_packages(
        self,
        serial: str = "",
        filter_type: str = "3rd_party",
    ) -> list[SideloadAppItem]:
        """List packages on device (filter_type: '3rd_party', 'system', 'disabled', 'all')."""
        args = ["pm", "list", "packages", "-f", "-u"]
        if filter_type == "3rd_party":
            args = ["pm", "list", "packages", "-3", "-f"]
        elif filter_type == "system":
            args = ["pm", "list", "packages", "-s", "-f"]
        elif filter_type == "disabled":
            args = ["pm", "list", "packages", "-d", "-f"]

        res = self.adb.shell(" ".join(args), serial=serial)
        if not res.success:
            return []

        # Get disabled set
        res_dis = self.adb.shell("pm list packages -d", serial=serial)
        dis_set = {
            line.replace("package:", "").strip()
            for line in res_dis.stdout.splitlines() if line.strip()
        }

        items: list[SideloadAppItem] = []
        for line in res.stdout.splitlines():
            line = line.strip()
            if not line.startswith("package:"):
                continue
            raw = line[len("package:"):]
            path = ""
            pkg = raw
            if "=" in raw:
                parts = raw.rsplit("=", 1)
                path = parts[0].strip()
                pkg = parts[1].strip()

            is_system = filter_type == "system" or ("/system/" in path or "/product/" in path)
            is_enabled = pkg not in dis_set

            cat = "disabled" if not is_enabled else ("system" if is_system else "user")
            label = pkg.split(".")[-1].replace("_", " ").title()

            items.append(SideloadAppItem(
                package_name=pkg,
                path=path,
                is_system=is_system,
                is_enabled=is_enabled,
                category=cat,
                label=label,
            ))

        items.sort(key=lambda x: x.package_name)
        return items

    def manage_package(
        self,
        package_name: str,
        action: str,
        serial: str = "",
        dest_dir: Optional[str | Path] = None,
    ) -> tuple[bool, str]:
        """Execute maintenance / debloat action on an installed application."""
        if not package_name:
            return False, "No package specified"

        if action == "pull":
            # 1. Query remote path
            path_res = self.adb.shell(f"pm path {package_name}", serial=serial)
            if not path_res.success or not path_res.stdout:
                return False, f"Could not locate APK path for {package_name}"
            remote_path = ""
            for l in path_res.stdout.splitlines():
                if l.startswith("package:"):
                    remote_path = l.replace("package:", "").strip()
                    break
            if not remote_path:
                return False, f"Invalid remote path output for {package_name}"

            dest = Path(dest_dir or tempfile.gettempdir()) / f"{package_name}.apk"
            pull_res = self.adb.pull(remote_path, str(dest.resolve()), serial=serial)
            if pull_res.success:
                return True, f"Extracted APK to: {dest.resolve()}"
            return False, pull_res.stderr or pull_res.stdout

        elif action == "clear":
            res = self.adb.shell(f"pm clear {package_name}", serial=serial)
            if "success" in res.output.lower():
                return True, f"Cleared cache and data for {package_name}"
            return False, res.output

        elif action == "force_stop":
            res = self.adb.shell(f"am force-stop {package_name}", serial=serial)
            return True, f"Force-stopped {package_name}"

        elif action == "disable":
            res = self.adb.shell(f"pm disable-user --user 0 {package_name}", serial=serial)
            if "disabled" in res.output.lower() or res.success:
                return True, f"Disabled (frozen) {package_name}"
            return False, res.output

        elif action == "enable":
            res = self.adb.shell(f"pm enable {package_name}", serial=serial)
            if "enabled" in res.output.lower() or res.success:
                return True, f"Re-enabled {package_name}"
            return False, res.output

        elif action == "uninstall":
            res = self.adb.shell(f"pm uninstall -k --user 0 {package_name}", serial=serial)
            if "success" in res.output.lower():
                return True, f"Uninstalled {package_name} for current user"
            # Fallback to standard uninstall
            res2 = self.adb.uninstall(package_name, serial=serial)
            if res2.success:
                return True, f"Completely uninstalled {package_name}"
            return False, res2.output or res.output

        return False, f"Unknown action: {action}"
