"""
FlashDock — Tools, Drivers & Firmware Manager (Phase 12).

Provides unified core management for:
1. Platform-Tools (ADB & Fastboot) verification, version querying, 1-click update/download, and daemon control.
2. OEM USB Drivers (Google, Samsung, Xiaomi, MediaTek VCOM, Qualcomm 9008 EDL, Universal ADB)
   catalog, download, automated INF/EXE installation, and Windows PnP hardware diagnostics.
3. Official Firmware & GSI Repositories Finder with device codename and brand auto-matching.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Callable, Optional
import urllib.request
import webbrowser
import zipfile

from flashdock.constants import (
    DRIVERS_DIR,
    TOOLS_DIR,
    ROMS_DIR,
    GSIS_DIR,
    PLATFORM_TOOLS_VERSION,
)
from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)

PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class ToolInfo:
    """Status information for a CLI utility."""
    name: str
    binary_path: Optional[Path]
    version: str
    status: str  # "ready", "missing", "update_available"
    details: str = ""


@dataclass
class DriverPackage:
    """Definition and local state of an OEM Android USB driver package."""
    id: str
    name: str
    brand: str
    description: str
    target_hardware: str
    download_url: str
    filename: str
    installer_type: str  # "inf", "exe", "zip"
    inf_relative_path: str = ""
    official_portal_url: str = ""
    is_downloaded: bool = False
    is_installed: bool = False
    local_path: Optional[Path] = None


@dataclass
class FirmwareRepo:
    """Catalog entry for an official or verified firmware/recovery portal."""
    id: str
    name: str
    brand: str
    category: str  # "factory", "gsi", "recovery", "unbrick"
    url: str
    description: str
    supported_models: str = "All"
    guide_note: str = ""


# ---------------------------------------------------------------------------
# Platform-Tools Manager
# ---------------------------------------------------------------------------

class PlatformToolsManager:
    """Manages ADB and Fastboot binaries, versions, daemon, and updates."""

    def __init__(self, adb: Optional[ADB] = None, fastboot: Optional[Fastboot] = None) -> None:
        self.adb = adb or ADB()
        self.fastboot = fastboot or Fastboot()

    def check_status(self) -> dict[str, ToolInfo]:
        """Inspect ADB and Fastboot availability, paths, and versions."""
        # Check ADB
        adb_path = Path(self.adb.binary_path) if self.adb.binary_path else None
        adb_ver = self.get_adb_version()
        if adb_path and adb_path.exists():
            adb_status = "ready"
            adb_details = f"Detected at {adb_path} (v{adb_ver})"
        else:
            adb_status = "missing"
            adb_details = "Binary not found in platform-tools or system PATH"

        # Check Fastboot
        fb_path = Path(self.fastboot.binary_path) if self.fastboot.binary_path else None
        fb_ver = self.get_fastboot_version()
        if fb_path and fb_path.exists():
            fb_status = "ready"
            fb_details = f"Detected at {fb_path} (v{fb_ver})"
        else:
            fb_status = "missing"
            fb_details = "Binary not found in platform-tools or system PATH"

        return {
            "adb": ToolInfo(
                name="ADB (Android Debug Bridge)",
                binary_path=adb_path,
                version=adb_ver,
                status=adb_status,
                details=adb_details,
            ),
            "fastboot": ToolInfo(
                name="Fastboot",
                binary_path=fb_path,
                version=fb_ver,
                status=fb_status,
                details=fb_details,
            ),
        }

    def get_adb_version(self) -> str:
        """Parse version string from `adb version`."""
        adb_p = Path(self.adb.binary_path) if self.adb.binary_path else None
        if not adb_p or not adb_p.exists():
            return "Not Installed"
        try:
            res = subprocess.run(
                [str(adb_p), "version"],
                capture_output=True,
                text=True,
                timeout=5,
                env={**os.environ, **ADB._adb_environment()},
            )
            out = res.stdout + res.stderr
            match = re.search(r"version\s+([0-9]+\.[0-9]+\.[0-9]+)", out)
            if match:
                return match.group(1)
            # Fallback pattern
            match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", out)
            return match.group(1) if match else "Unknown"
        except Exception as exc:
            log.warning("Failed to query adb version: %s", exc)
            return "Unknown"

    def get_fastboot_version(self) -> str:
        """Parse version string from `fastboot --version`."""
        fb_p = Path(self.fastboot.binary_path) if self.fastboot.binary_path else None
        if not fb_p or not fb_p.exists():
            return "Not Installed"
        try:
            res = subprocess.run(
                [str(fb_p), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = res.stdout + res.stderr
            match = re.search(r"version\s+([0-9]+\.[0-9]+\.[0-9]+)", out)
            if match:
                return match.group(1)
            match = re.search(r"([0-9]+\.[0-9]+\.[0-9]+)", out)
            return match.group(1) if match else "Unknown"
        except Exception as exc:
            log.warning("Failed to query fastboot version: %s", exc)
            return "Unknown"

    def restart_adb_daemon(self) -> tuple[bool, str]:
        """Restart ADB daemon (kill-server followed by start-server)."""
        adb_p = Path(self.adb.binary_path) if self.adb.binary_path else None
        if not adb_p or not adb_p.exists():
            return False, "ADB binary not installed."
        try:
            log.info("Restarting ADB daemon...")
            subprocess.run(
                [str(adb_p), "kill-server"],
                capture_output=True,
                text=True,
                timeout=10,
                env={**os.environ, **ADB._adb_environment()},
            )
            res = subprocess.run(
                [str(adb_p), "start-server"],
                capture_output=True,
                text=True,
                timeout=15,
                env={**os.environ, **ADB._adb_environment()},
            )
            if res.returncode == 0:
                log.info("ADB daemon restarted successfully.")
                return True, "ADB daemon successfully restarted."
            return False, f"Failed to start ADB daemon: {res.stderr.strip()}"
        except Exception as exc:
            log.error("Exception restarting ADB daemon: %s", exc)
            return False, str(exc)

    def download_and_install_platform_tools(
        self,
        target_dir: Optional[Path] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> tuple[bool, str]:
        """Download latest Google platform-tools zip and extract into target_dir."""
        dest_dir = target_dir or (TOOLS_DIR / "platform-tools")
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        zip_path = TOOLS_DIR / "platform-tools-latest.zip"
        extract_tmp = TOOLS_DIR / "_pt_tmp"

        # Terminate any running ADB daemon to release file locks on Windows
        if sys.platform == "win32":
            try:
                subprocess.run(["taskkill", "/F", "/IM", "adb.exe"], capture_output=True, timeout=5)
            except Exception:
                pass

        try:
            log.info("Downloading platform-tools from %s...", PLATFORM_TOOLS_URL)
            req = urllib.request.Request(
                PLATFORM_TOOLS_URL,
                headers={"User-Agent": "FlashDock/1.0 (Windows)"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(zip_path, "wb") as out_file:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

            log.info("Download completed (%d bytes). Extracting...", downloaded)
            # Extract
            if extract_tmp.exists():
                shutil.rmtree(extract_tmp, ignore_errors=True)
            extract_tmp.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_tmp)

            inner_pt = extract_tmp / "platform-tools"
            source_dir = inner_pt if inner_pt.exists() else extract_tmp

            dest_dir.mkdir(parents=True, exist_ok=True)

            def _copy_safely(src: Path, dst: Path) -> None:
                if dst.exists():
                    try:
                        dst.unlink()
                    except PermissionError:
                        old_p = dst.with_name(f"{dst.name}.old.{os.getpid()}")
                        try:
                            if old_p.exists():
                                old_p.unlink(missing_ok=True)
                            dst.rename(old_p)
                        except Exception:
                            pass
                shutil.copy2(src, dst)

            for item in source_dir.iterdir():
                dest_file = dest_dir / item.name
                if item.is_file():
                    _copy_safely(item, dest_file)
                elif item.is_dir():
                    if dest_file.exists():
                        shutil.rmtree(dest_file, ignore_errors=True)
                    shutil.copytree(item, dest_file)

            # Sync to AppData only when updating global installation
            if target_dir is None:
                local_appdata = os.environ.get("LOCALAPPDATA")
                if local_appdata:
                    try:
                        appdata_pt = Path(local_appdata) / "FlashDock" / "tools" / "platform-tools"
                        appdata_pt.mkdir(parents=True, exist_ok=True)
                        for item in dest_dir.iterdir():
                            if item.is_file():
                                _copy_safely(item, appdata_pt / item.name)
                    except Exception as e:
                        log.warning("Could not sync to local appdata: %s", e)

            # Clean up temporary folders and zip after closing ZipFile
            shutil.rmtree(extract_tmp, ignore_errors=True)
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass

            # Refresh adb/fastboot instances
            self.adb.binary_path = dest_dir / "adb.exe"
            self.fastboot.binary_path = dest_dir / "fastboot.exe"
            log.info("Platform-tools successfully installed to %s", dest_dir)
            return True, f"Platform-tools installed successfully to {dest_dir}"

        except Exception as exc:
            log.error("Failed to install platform-tools: %s", exc)
            if extract_tmp.exists():
                shutil.rmtree(extract_tmp, ignore_errors=True)
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass
            return False, f"Installation failed: {exc}"


# ---------------------------------------------------------------------------
# OEM USB Drivers Manager
# ---------------------------------------------------------------------------

DEFAULT_DRIVERS: list[DriverPackage] = [
    DriverPackage(
        id="google_usb",
        name="Google USB Driver",
        brand="Google",
        description="Official driver for Pixel, Nexus, and generic ADB & Android Bootloader / Fastboot interfaces.",
        target_hardware="VID_18D1 (Google / Android ADB / Fastboot)",
        download_url="https://dl.google.com/android/repository/usb_driver_r13-windows.zip",
        filename="usb_driver_r13-windows.zip",
        installer_type="inf",
        inf_relative_path="usb_driver/android_winusb.inf",
        official_portal_url="https://developer.android.com/studio/run/win-usb",
    ),
    DriverPackage(
        id="samsung_usb",
        name="Samsung Mobile USB Driver",
        brand="Samsung",
        description="Driver for Samsung Galaxy smartphones, tablets, MTP, ADB, and Odin / Download Mode.",
        target_hardware="VID_04E8 (Samsung Mobile USB Composite / Download)",
        download_url="https://developer.samsung.com/android-usb-driver",
        filename="SAMSUNG_USB_Driver_for_Mobile_Phones.exe",
        installer_type="exe",
        official_portal_url="https://developer.samsung.com/android-usb-driver",
    ),
    DriverPackage(
        id="xiaomi_usb",
        name="Xiaomi / Poco / Redmi Fastboot Driver",
        brand="Xiaomi",
        description="Driver for Xiaomi, Poco, and Redmi devices in ADB and Fastboot (Bootloader Interface) mode.",
        target_hardware="VID_2717 (Xiaomi / Android Bootloader Interface)",
        download_url="https://xiaomirom.com/en/driver/",
        filename="Xiaomi_Fastboot_Driver.zip",
        installer_type="inf",
        inf_relative_path="android_winusb.inf",
        official_portal_url="https://xiaomirom.com/en/driver/",
    ),
    DriverPackage(
        id="mtk_vcom",
        name="MediaTek (MTK) USB VCOM Driver",
        brand="MediaTek",
        description="Low-level Preloader and BootROM (BROM) COM port drivers for MTK Dimensity and Helio devices.",
        target_hardware="VID_0E8D PID_0003 / PID_2000 (MTK Preloader & BROM)",
        download_url="https://spflashtool.com/drivers/",
        filename="MTK_USB_VCOM_Driver.zip",
        installer_type="inf",
        inf_relative_path="cdc-acm.inf",
        official_portal_url="https://spflashtool.com/drivers/",
    ),
    DriverPackage(
        id="qualcomm_9008",
        name="Qualcomm HS-USB QDLoader 9008 Driver",
        brand="Qualcomm",
        description="Emergency Download (EDL) mode driver for Snapdragon devices recovering from hard bricks.",
        target_hardware="VID_05C6 PID_9008 (Qualcomm HS-USB QDLoader 9008)",
        download_url="https://qualcommdriver.com/qualcomm-hs-usb-qdloader-9008-driver",
        filename="Qualcomm_HS-USB_Driver_Setup.exe",
        installer_type="exe",
        official_portal_url="https://qualcommdriver.com/",
    ),
    DriverPackage(
        id="universal_adb",
        name="Universal ADB Driver (ClockworkMod)",
        brand="Universal",
        description="Signed universal ADB driver package supporting broad range of Android devices.",
        target_hardware="Universal Android USB Interfaces",
        download_url="https://adb.clockworkmod.com/",
        filename="UniversalAdbDriverSetup.msi",
        installer_type="exe",
        official_portal_url="https://adb.clockworkmod.com/",
    ),
]


class DriverManager:
    """Manages OEM USB driver packages, installation, and PnP troubleshooting."""

    def __init__(self, drivers_dir: Optional[Path] = None) -> None:
        self.drivers_dir = drivers_dir or DRIVERS_DIR
        self.drivers_dir.mkdir(parents=True, exist_ok=True)
        self._drivers: dict[str, DriverPackage] = {d.id: d for d in DEFAULT_DRIVERS}
        self.scan_local_drivers()

    def get_all_drivers(self) -> list[DriverPackage]:
        """Return all cataloged driver packages with updated local status."""
        self.scan_local_drivers()
        return list(self._drivers.values())

    def get_driver(self, driver_id: str) -> Optional[DriverPackage]:
        """Get driver by ID."""
        self.scan_local_drivers()
        return self._drivers.get(driver_id)

    DRIVER_KEYWORDS: dict[str, list[str]] = {
        "google_usb": ["google", "pixel", "winusb", "android_winusb"],
        "samsung_usb": ["samsung", "sec_", "ssud"],
        "xiaomi_usb": ["xiaomi", "redmi", "poco"],
        "mtk_vcom": ["mtk", "mediatek", "vcom", "cdc-acm", "sp_flash"],
        "qualcomm_9008": ["qualcomm", "qdloader", "9008", "qhsusb"],
        "universal_adb": ["universal", "clockworkmod", "koush", "adb_driver"],
    }

    def scan_local_drivers(self) -> None:
        """Inspect the local drivers directory and update status with smart fuzzy matching."""
        all_items = list(self.drivers_dir.iterdir()) if self.drivers_dir.exists() else []

        for pkg in self._drivers.values():
            pkg_file = self.drivers_dir / pkg.filename
            extracted_folder = self.drivers_dir / pkg.id
            if pkg_file.exists():
                pkg.is_downloaded = True
                pkg.local_path = pkg_file
            elif extracted_folder.exists():
                pkg.is_downloaded = True
                pkg.local_path = extracted_folder
            else:
                # Fuzzy match: check if user placed a file with a slightly different filename
                matched: Optional[Path] = None
                keywords = self.DRIVER_KEYWORDS.get(pkg.id, [pkg.id])
                for item in all_items:
                    item_name_lower = item.name.lower()
                    if any(kw in item_name_lower for kw in keywords):
                        matched = item
                        break
                if matched:
                    pkg.is_downloaded = True
                    pkg.local_path = matched
                else:
                    pkg.is_downloaded = False
                    pkg.local_path = None

    def download_driver(
        self,
        driver_id: str,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> tuple[bool, str]:
        """Download an OEM driver package to the local driver directory."""
        pkg = self._drivers.get(driver_id)
        if not pkg:
            return False, f"Driver ID '{driver_id}' not found."

        dest_file = self.drivers_dir / pkg.filename
        try:
            log.info("Downloading driver %s from %s...", pkg.name, pkg.download_url)
            req = urllib.request.Request(
                pkg.download_url,
                headers={"User-Agent": "FlashDock/1.0 (Windows)"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(dest_file, "wb") as out_file:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total)

            # Check if downloaded file is an HTML redirect/portal instead of binary
            if dest_file.exists():
                with open(dest_file, "rb") as check_f:
                    header = check_f.read(512)
                if b"<html" in header.lower() or b"<!doctype" in header.lower():
                    dest_file.unlink(missing_ok=True)
                    portal_url = pkg.official_portal_url or pkg.download_url
                    try:
                        webbrowser.open(portal_url)
                    except Exception:
                        pass
                    if sys.platform == "win32":
                        try:
                            os.startfile(str(self.drivers_dir))
                        except Exception:
                            pass
                    return True, (
                        f"Opened official portal for '{pkg.name}' in your web browser:\n{portal_url}\n\n"
                        "Download the driver package, then place it in the opened Drivers folder "
                        "or click '➕ Install Driver from File'."
                    )

            # Auto-extract zip packages if valid zip archive
            if pkg.filename.lower().endswith(".zip") and dest_file.exists():
                with open(dest_file, "rb") as test_f:
                    header_bytes = test_f.read(4)
                if header_bytes == b"PK\x03\x04":
                    extract_dir = self.drivers_dir / pkg.id
                    extract_dir.mkdir(parents=True, exist_ok=True)
                    with zipfile.ZipFile(dest_file, "r") as zf:
                        zf.extractall(extract_dir)
                    pkg.local_path = extract_dir
                else:
                    dest_file.unlink(missing_ok=True)
                    return False, f"Downloaded package for {pkg.name} was not a valid zip archive."
            else:
                pkg.local_path = dest_file

            pkg.is_downloaded = True
            log.info("Driver %s downloaded successfully.", pkg.name)
            return True, f"{pkg.name} downloaded successfully to {dest_file}."
        except Exception as exc:
            log.error("Failed to download driver %s: %s", pkg.name, exc)
            # If download fails, guide the user to the official portal
            portal_url = pkg.official_portal_url or pkg.download_url
            try:
                webbrowser.open(portal_url)
            except Exception:
                pass
            return False, f"Download failed ({exc}). Opened official vendor portal: {portal_url}"

    def install_driver(self, driver_id: str) -> tuple[bool, str]:
        """Install or launch the installer for the specified driver."""
        pkg = self._drivers.get(driver_id)
        if not pkg:
            return False, f"Driver ID '{driver_id}' not found."

        self.scan_local_drivers()
        if not pkg.is_downloaded or not pkg.local_path:
            return False, f"{pkg.name} has not been found in the drivers folder."

        target_path = pkg.local_path

        # If it's a zip file, auto-extract it first
        if target_path.is_file() and target_path.suffix.lower() == ".zip":
            extract_dir = self.drivers_dir / pkg.id
            extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(target_path, "r") as zf:
                    zf.extractall(extract_dir)
                target_path = extract_dir
                pkg.local_path = extract_dir
            except Exception as e:
                return False, f"Failed to extract zip archive {target_path.name}: {e}"

        return self._install_from_path(target_path, pkg)

    def install_custom_driver_file(self, file_path: Path) -> tuple[bool, str]:
        """Install or launch any user-selected driver file (.inf, .zip, .exe, .msi) from disk."""
        if not file_path.exists():
            return False, f"File does not exist: {file_path}"

        suffix = file_path.suffix.lower()

        # 1. ZIP Archive -> extract and install
        if suffix == ".zip":
            extract_dir = self.drivers_dir / f"extracted_{file_path.stem}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            try:
                with zipfile.ZipFile(file_path, "r") as zf:
                    zf.extractall(extract_dir)
            except Exception as e:
                return False, f"Could not extract zip archive: {e}"
            success, msg = self._install_from_path(extract_dir)
            self.scan_local_drivers()
            return success, msg

        # 2. Direct INF file
        elif suffix == ".inf":
            success, msg = self._execute_pnputil_install(file_path)
            self.scan_local_drivers()
            return success, msg

        # 3. Direct Executable / Installer
        elif suffix in (".exe", ".msi"):
            success, msg = self._execute_installer(file_path)
            self.scan_local_drivers()
            return success, msg

        return False, f"Unsupported driver file format: {suffix}. Supported: .inf, .zip, .exe, .msi"

    def _install_from_path(
        self, target_path: Path, pkg: Optional[DriverPackage] = None
    ) -> tuple[bool, str]:
        """Install from an extracted directory or file."""
        if target_path.is_dir():
            # 1. Search for INF driver files
            inf_candidates = list(target_path.rglob("*.inf"))
            if inf_candidates:
                inf_target = inf_candidates[0]
                if pkg and pkg.inf_relative_path:
                    for c in inf_candidates:
                        if c.name.lower() == Path(pkg.inf_relative_path).name.lower():
                            inf_target = c
                            break
                success, msg = self._execute_pnputil_install(inf_target)
                if success and pkg:
                    pkg.is_installed = True
                return success, msg

            # 2. Search for executable installers
            exes = list(target_path.rglob("*.exe")) + list(target_path.rglob("*.msi"))
            if exes:
                success, msg = self._execute_installer(exes[0])
                if success and pkg:
                    pkg.is_installed = True
                return success, msg

            return False, f"No .inf driver file or setup executable found inside {target_path}."

        elif target_path.suffix.lower() == ".inf":
            success, msg = self._execute_pnputil_install(target_path)
            if success and pkg:
                pkg.is_installed = True
            return success, msg

        elif target_path.suffix.lower() in (".exe", ".msi"):
            success, msg = self._execute_installer(target_path)
            if success and pkg:
                pkg.is_installed = True
            return success, msg

        return False, f"Unrecognized driver file format: {target_path.name}"

    def _execute_pnputil_install(self, inf_file: Path) -> tuple[bool, str]:
        """Install INF driver via pnputil with PowerShell RunAs UAC elevation fallback."""
        if not inf_file.exists():
            return False, f"INF file not found: {inf_file}"

        log.info("Attempting pnputil installation for: %s", inf_file)
        try:
            res = subprocess.run(
                ["pnputil", "/add-driver", str(inf_file), "/install"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = (res.stdout + res.stderr).strip()
            if res.returncode == 0 or "successfully" in out.lower() or "added" in out.lower():
                return True, f"Successfully installed driver INF: {inf_file.name}\n{out}"
        except Exception as e:
            out = str(e)

        # Elevate with UAC on Windows if non-elevated call failed
        if sys.platform == "win32":
            log.info("Standard pnputil failed or requires elevation. Launching with UAC RunAs...")
            try:
                ps_cmd = f"Start-Process pnputil -ArgumentList '/add-driver', '\"{inf_file}\"', '/install' -Verb RunAs -Wait"
                elev_res = subprocess.run(
                    ["powershell", "-NoProfile", "-Command", ps_cmd],
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                if elev_res.returncode == 0:
                    return True, f"Driver INF installation command executed for: {inf_file.name} (Administrator elevation requested)."
                return False, f"Elevated driver installation returned code {elev_res.returncode}:\n{elev_res.stderr.strip() or out}"
            except Exception as elev_exc:
                return False, f"Administrator elevation failed: {elev_exc}"

        return False, f"Driver installation failed:\n{out}"

    def _execute_installer(self, exe_file: Path) -> tuple[bool, str]:
        """Launch an executable driver installer."""
        log.info("Launching driver installer: %s", exe_file)
        if sys.platform == "win32":
            try:
                os.startfile(str(exe_file))
                return True, f"Launched installer: {exe_file.name}. Please follow on-screen instructions."
            except Exception as exc:
                # Fallback to elevated launch via PowerShell
                try:
                    ps_cmd = f"Start-Process '\"{exe_file}\"' -Verb RunAs"
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, timeout=10)
                    return True, f"Launched installer with Administrator elevation: {exe_file.name}."
                except Exception as elev_exc:
                    return False, f"Could not launch installer: {exc} / {elev_exc}"
        else:
            subprocess.Popen([str(exe_file)])
            return True, f"Launched installer: {exe_file.name}."

    def diagnose_pnp_devices(self) -> list[dict[str, str]]:
        """Query Windows PnP device manager for devices in warning/error state."""
        diagnostics: list[dict[str, str]] = []
        if sys.platform != "win32":
            return diagnostics

        try:
            # Query PowerShell Get-PnpDevice with problem or unknown status
            ps_cmd = (
                "Get-PnpDevice | Where-Object { $_.Status -ne 'OK' -or $_.Class -eq 'Unknown' } | "
                "Select-Object InstanceId, FriendlyName, Class, Status, Problem | "
                "ConvertTo-Json -Compress"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=10,
            )
            raw = res.stdout.strip()
            if not raw or raw == "null":
                return diagnostics

            import json
            data = json.loads(raw)
            items = [data] if isinstance(data, dict) else (data if isinstance(data, list) else [])

            for item in items:
                instance_id = str(item.get("InstanceId", ""))
                friendly_name = str(item.get("FriendlyName", "") or "Unknown Device")
                status = str(item.get("Status", "Error"))
                problem = str(item.get("Problem", "Unknown Problem"))

                # Check if it looks like an Android / USB device
                rec_driver = ""
                upper_id = instance_id.upper()
                if "VID_18D1" in upper_id:
                    rec_driver = "Google USB Driver"
                elif "VID_04E8" in upper_id:
                    rec_driver = "Samsung Mobile USB Driver"
                elif "VID_2717" in upper_id:
                    rec_driver = "Xiaomi Fastboot Driver"
                elif "VID_0E8D" in upper_id:
                    rec_driver = "MediaTek MTK VCOM Driver"
                elif "VID_05C6" in upper_id:
                    rec_driver = "Qualcomm 9008 Driver"
                elif "ADB" in upper_id or "BOOTLOADER" in upper_id or "ANDROID" in friendly_name.upper():
                    rec_driver = "Google USB Driver / Universal ADB"

                diagnostics.append({
                    "instance_id": instance_id,
                    "name": friendly_name,
                    "status": status,
                    "problem": problem,
                    "recommended_driver": rec_driver,
                })

        except Exception as exc:
            log.warning("PnP diagnostics check encountered exception: %s", exc)

        return diagnostics


# ---------------------------------------------------------------------------
# Official Firmware & GSI Repositories Finder
# ---------------------------------------------------------------------------

DEFAULT_REPOSITORIES: list[FirmwareRepo] = [
    # Factory Images
    FirmwareRepo(
        id="google_factory",
        name="Google Pixel Factory Images",
        brand="Google",
        category="factory",
        url="https://developers.google.com/android/images",
        description="Official factory images for all Google Pixel models. Includes complete flash-all fastboot scripts.",
        supported_models="Pixel 1 through Pixel 9 / Fold / Tablet",
        guide_note="Extract ZIP and run FlashDock 'Flash ROM / Return to Stock' or flash-all.bat.",
    ),
    FirmwareRepo(
        id="google_ota",
        name="Google Pixel Full OTA Images",
        brand="Google",
        category="factory",
        url="https://developers.google.com/android/ota",
        description="Official complete OTA images for Pixel devices. Safe for locked bootloaders via ADB sideload.",
        supported_models="Pixel devices",
        guide_note="Flash via Recovery mode > ADB Sideload without unlocking bootloader.",
    ),
    FirmwareRepo(
        id="xiaomi_rom",
        name="XiaomiROM / MiFirm Community Portal",
        brand="Xiaomi",
        category="factory",
        url="https://xiaomirom.com/en/",
        description="Comprehensive repository of official Fastboot (.tgz) and Recovery (.zip) ROMs for Xiaomi, Poco, and Redmi.",
        supported_models="Xiaomi, Poco, Redmi",
        guide_note="For unbricking and clean flashing, always download the 'Fastboot' version (.tgz).",
    ),
    FirmwareRepo(
        id="samfw",
        name="SamFW Samsung Firmware Downloader",
        brand="Samsung",
        category="factory",
        url="https://samfw.com/",
        description="Fast direct-download archive of official Samsung 4-file (BL, AP, CP, CSC) firmware packages.",
        supported_models="Samsung Galaxy Series",
        guide_note="Select your exact Model (e.g. SM-S918B) and CSC Region code.",
    ),
    FirmwareRepo(
        id="motorola_repo",
        name="Motorola Firmware Mirrors (Lolinet)",
        brand="Motorola",
        category="factory",
        url="https://mirrors.lolinet.com/firmware/motorola/",
        description="Official fastboot firmware archives for Motorola Moto G, Edge, Razr, and Defy devices.",
        supported_models="Motorola",
        guide_note="Check codename in fastboot getvar product before flashing.",
    ),
    # Generic System Images (GSIs)
    FirmwareRepo(
        id="andyyan_gsi",
        name="AndyYan LineageOS Treble GSI",
        brand="Generic",
        category="gsi",
        url="https://sourceforge.net/projects/andyyan-gsi/files/",
        description="Maintained LineageOS Treble GSI builds for Project Treble compliant Android 9–15 devices.",
        supported_models="All Project Treble Phones (arm64, vndklite)",
        guide_note="Choose bvN (vanilla) or bgN (with Google Apps). Flash to system or super partition.",
    ),
    FirmwareRepo(
        id="phh_treble",
        name="phhusson AOSP Treble GSI",
        brand="Generic",
        category="gsi",
        url="https://github.com/phhusson/treble_experimentations/releases",
        description="Reference AOSP GSI builds providing high hardware compatibility and treble patches.",
        supported_models="All Treble Devices",
        guide_note="Foundation for most modern custom GSIs.",
    ),
    # Custom Recoveries
    FirmwareRepo(
        id="twrp",
        name="Official TeamWin Recovery Project (TWRP)",
        brand="Generic",
        category="recovery",
        url="https://twrp.me/Devices/",
        description="Official custom recovery images with full touch interface, MTP, and backup features.",
        supported_models="Over 500+ Android devices",
        guide_note="Flash to recovery or boot partition depending on A/B architecture.",
    ),
    FirmwareRepo(
        id="orangefox",
        name="OrangeFox Recovery Project",
        brand="Generic",
        category="recovery",
        url="https://orangefox.download/",
        description="Modern, feature-rich custom recovery with Magisk survival, password protection, and OTA support.",
        supported_models="Xiaomi, Realme, Samsung, OnePlus, Tecno, etc.",
        guide_note="Provides built-in Aroma installer engine and encryption bypass.",
    ),
]


class FirmwareFinder:
    """Provides categorized firmware portals and device-specific recommendation logic."""

    def __init__(self) -> None:
        self._repos = list(DEFAULT_REPOSITORIES)

    def get_repositories(self, category: str = "all") -> list[FirmwareRepo]:
        """Filter repositories by category ('all', 'factory', 'gsi', 'recovery')."""
        if category == "all":
            return list(self._repos)
        return [r for r in self._repos if r.category == category]

    def get_recommendations_for_device(self, device: Optional[DeviceInfo]) -> list[FirmwareRepo]:
        """Return prioritized repository recommendations matching connected device."""
        if not device or device.mode == "not_connected":
            return list(self._repos)

        brand_lower = (device.brand or "").strip().lower()
        matched: list[FirmwareRepo] = []
        others: list[FirmwareRepo] = []

        for repo in self._repos:
            repo_brand = repo.brand.lower()
            if repo_brand in brand_lower or brand_lower in repo_brand:
                matched.append(repo)
            elif repo.category in ("gsi", "recovery"):
                matched.append(repo)
            else:
                others.append(repo)

        return matched + others
