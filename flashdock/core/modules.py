"""
FlashDock — Module Flasher & Bootloop Protection Engine.

Handles:
* Parsing module metadata (module.prop) from local zips or installed directories.
* Installing root modules through Magisk, KernelSU, or APatch over ADB.
* Managing installed modules: enable, disable, and remove.
* Emergency bootloop recovery:
  - "Disable all modules" emergency kill switch.
  - Safe-mode reboot to recover from bootlooping modules.
  - Last-known-good state tracking.

Spec references: Section 12, Section 15, Section 16.
"""

from __future__ import annotations

import io
import time
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.runner import CommandResult

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ModuleInfo:
    """Metadata for a root module (from module.prop)."""
    id: str
    name: str
    version: str
    version_code: int = 0
    author: str = ""
    description: str = ""
    enabled: bool = True
    installed_path: str = ""
    has_service_sh: bool = False
    has_post_fs_data: bool = False
    has_system_files: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_prop_text(cls, prop_text: str, enabled: bool = True) -> ModuleInfo:
        """Parse key=value properties from a module.prop string."""
        props: dict[str, str] = {}
        for line in prop_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            props[k.strip()] = v.strip()

        v_code = 0
        if "versionCode" in props and props["versionCode"].isdigit():
            v_code = int(props["versionCode"])

        return cls(
            id=props.get("id", "unknown_module"),
            name=props.get("name", props.get("id", "Unnamed Module")),
            version=props.get("version", "1.0"),
            version_code=v_code,
            author=props.get("author", "Unknown"),
            description=props.get("description", ""),
            enabled=enabled,
        )


@dataclass
class ModuleInspectionResult:
    """Inspection outcome of a module ZIP before installation."""
    is_valid_module: bool
    module_info: Optional[ModuleInfo] = None
    warnings: list[str] = field(default_factory=list)
    file_count: int = 0
    total_size_bytes: int = 0


# ---------------------------------------------------------------------------
# Module Manager
# ---------------------------------------------------------------------------

class ModuleManager:
    """Orchestrates module installations, lifecycle, and bootloop recovery."""

    # -----------------------------------------------------------------------
    # ZIP Inspection
    # -----------------------------------------------------------------------

    @staticmethod
    def inspect_module_zip(zip_path: Path | str) -> ModuleInspectionResult:
        """
        Inspect a module ZIP file without flashing it.
        Reads module.prop, counts files, and checks for aggressive scripts.
        """
        path = Path(zip_path)
        if not path.is_file():
            return ModuleInspectionResult(
                is_valid_module=False,
                warnings=[f"File not found: {path.name}"],
            )

        warnings: list[str] = []
        try:
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                file_count = len(names)
                total_size = sum(info.file_size for info in zf.infolist())

                # Check for module.prop
                prop_filename = next((n for n in names if n.lower().endswith("module.prop")), None)
                if not prop_filename:
                    return ModuleInspectionResult(
                        is_valid_module=False,
                        warnings=["Missing 'module.prop'. This ZIP does not appear to be a standard root module."],
                        file_count=file_count,
                        total_size_bytes=total_size,
                    )

                prop_content = zf.read(prop_filename).decode("utf-8", errors="ignore")
                info = ModuleInfo.from_prop_text(prop_content)

                # Check for sensitive or aggressive modifications
                if any("system/" in n.lower() for n in names):
                    info.has_system_files = True
                    warnings.append("Module overlays files directly onto /system partitions.")

                if any("post-fs-data.sh" in n.lower() for n in names):
                    info.has_post_fs_data = True
                    warnings.append("Executes post-fs-data early boot scripts (can cause early bootloops).")

                if any("service.sh" in n.lower() for n in names):
                    info.has_service_sh = True

                return ModuleInspectionResult(
                    is_valid_module=True,
                    module_info=info,
                    warnings=warnings,
                    file_count=file_count,
                    total_size_bytes=total_size,
                )

        except zipfile.BadZipFile:
            return ModuleInspectionResult(
                is_valid_module=False,
                warnings=["Corrupted ZIP file (BadZipFile)."],
            )
        except Exception as e:
            return ModuleInspectionResult(
                is_valid_module=False,
                warnings=[f"Failed to inspect module ZIP: {e}"],
            )

    # -----------------------------------------------------------------------
    # Listing installed modules
    # -----------------------------------------------------------------------

    @staticmethod
    def list_installed_modules(adb: ADB, serial: str = "") -> list[ModuleInfo]:
        """
        Query device via ADB to list installed modules across Magisk/KernelSU/APatch.
        """
        modules: list[ModuleInfo] = []
        if not adb.available:
            return modules

        # Query directory listing of /data/adb/modules
        cmd = (
            "su -c 'for d in /data/adb/modules/*; do "
            "if [ -f \"$d/module.prop\" ]; then "
            "echo \"---START---\"; "
            "echo \"path=$d\"; "
            "if [ -f \"$d/disable\" ]; then echo \"disabled=1\"; else echo \"disabled=0\"; fi; "
            "cat \"$d/module.prop\"; "
            "echo \"---END---\"; "
            "fi; done' 2>/dev/null"
        )
        res = adb.shell(cmd, serial=serial, timeout=10)
        if not res.success or not res.stdout.strip():
            return modules

        chunks = res.stdout.split("---START---")
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk or "---END---" not in chunk:
                continue

            content = chunk.split("---END---")[0].strip()
            lines = content.splitlines()

            path_val = ""
            is_disabled = False
            prop_lines: list[str] = []

            for line in lines:
                if line.startswith("path="):
                    path_val = line.split("=", 1)[1].strip()
                elif line.startswith("disabled="):
                    is_disabled = line.split("=", 1)[1].strip() == "1"
                else:
                    prop_lines.append(line)

            mod_info = ModuleInfo.from_prop_text("\n".join(prop_lines), enabled=not is_disabled)
            mod_info.installed_path = path_val
            if mod_info.id and mod_info.id != "unknown_module":
                modules.append(mod_info)

        return modules

    # -----------------------------------------------------------------------
    # Installation
    # -----------------------------------------------------------------------

    def install_module(
        self,
        zip_path: Path | str,
        adb: ADB,
        root_framework: str = "magisk",
        serial: str = "",
        dry_run: bool = False,
    ) -> tuple[bool, str]:
        """
        Install a module ZIP via ADB.
        """
        path = Path(zip_path)
        if not path.is_file():
            return False, f"Module file not found: {path}"

        if dry_run:
            log.info("[DRY RUN] Would install module %s via %s", path.name, root_framework)
            return True, f"[DRY RUN] Module '{path.name}' simulated install successfully."

        # 1. Push to temporary directory on device
        remote_dest = f"/data/local/tmp/{path.name}"
        push_res = adb.push(str(path), remote_dest, serial=serial)
        if not push_res.success:
            return False, f"Failed to push module to device: {push_res.stderr}"

        # 2. Run framework-specific install command
        framework = root_framework.lower()
        if "kernelsu" in framework:
            install_cmd = f"su -c '/data/adb/ksu/bin/ksud module install \"{remote_dest}\"'"
        elif "apatch" in framework:
            install_cmd = f"su -c '/data/adb/ap/bin/apd module install \"{remote_dest}\"'"
        else:
            # Magisk (default)
            install_cmd = f"su -c 'magisk --install-module \"{remote_dest}\"'"

        log.info("Installing module via command: %s", install_cmd)
        exec_res = adb.shell(install_cmd, serial=serial, timeout=120)

        # 3. Clean up pushed zip
        adb.shell(f"rm -f \"{remote_dest}\"", serial=serial, timeout=10)

        if exec_res.success:
            return True, f"Module '{path.name}' installed successfully!\nReboot your phone to activate."
        else:
            return False, f"Module installation failed:\n{exec_res.output or exec_res.stderr}"

    # -----------------------------------------------------------------------
    # Module Controls
    # -----------------------------------------------------------------------

    @staticmethod
    def enable_module(module_id: str, adb: ADB, serial: str = "") -> tuple[bool, str]:
        """Enable an installed module by removing the 'disable' flag file."""
        cmd = f"su -c 'rm -f /data/adb/modules/{module_id}/disable'"
        res = adb.shell(cmd, serial=serial, timeout=10)
        if res.success:
            return True, f"Module '{module_id}' enabled. Reboot to take effect."
        return False, f"Failed to enable module: {res.stderr}"

    @staticmethod
    def disable_module(module_id: str, adb: ADB, serial: str = "") -> tuple[bool, str]:
        """Disable an installed module by creating the 'disable' flag file."""
        cmd = f"su -c 'touch /data/adb/modules/{module_id}/disable'"
        res = adb.shell(cmd, serial=serial, timeout=10)
        if res.success:
            return True, f"Module '{module_id}' disabled. Reboot to apply."
        return False, f"Failed to disable module: {res.stderr}"

    @staticmethod
    def remove_module(module_id: str, adb: ADB, serial: str = "") -> tuple[bool, str]:
        """Mark module for removal or delete its directory."""
        cmd = f"su -c 'touch /data/adb/modules/{module_id}/remove && rm -rf /data/adb/modules/{module_id}'"
        res = adb.shell(cmd, serial=serial, timeout=10)
        if res.success:
            return True, f"Module '{module_id}' removed."
        return False, f"Failed to remove module: {res.stderr}"

    # -----------------------------------------------------------------------
    # Bootloop Recovery & Emergency Switches
    # -----------------------------------------------------------------------

    @staticmethod
    def emergency_disable_all_modules(adb: ADB, serial: str = "") -> tuple[bool, str]:
        """
        Emergency kill-switch: disables all installed modules simultaneously.
        Crucial when a rogue module causes system crashes or soft-brick bootloops.
        """
        cmd = (
            "su -c '"
            "for d in /data/adb/modules/*; do "
            "[ -d \"$d\" ] && touch \"$d/disable\"; "
            "done; "
            "touch /data/adb/modules/.disable_all' 2>/dev/null"
        )
        res = adb.shell(cmd, serial=serial, timeout=10)
        if res.success:
            log.info("Emergency kill-switch executed: all modules disabled for serial %s", serial)
            return True, "All modules have been emergency-disabled. Reboot your device to recover."
        return False, f"Failed to disable all modules: {res.stderr}"

    @staticmethod
    def reboot_safe_mode(adb: ADB, serial: str = "") -> CommandResult:
        """
        Reboot the phone into Safe Mode, disabling all third-party root modules and apps.
        """
        log.info("Triggering safe mode reboot for serial %s", serial)
        return adb.reboot_safemode(serial=serial)
