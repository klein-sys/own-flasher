"""
FlashDock — Local Software & File Repository Manager.

Manages persistent local storage and compatibility cataloging for:
* ROMs & GSIs (data/roms/, data/gsis/)
* Root modules & manager APKs (data/modules/, data/root_apps/)
* Device USB drivers (data/drivers/)
* Android service tools (data/tools/)

Automatically filters and highlights files compatible with the connected phone.

Spec reference: Section 29 (User Additions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
import shutil
import zipfile

from flashdock.constants import (
    DRIVERS_DIR,
    GSIS_DIR,
    MODULES_DIR,
    ROMS_DIR,
    ROOT_APPS_DIR,
    TOOLS_DIR,
)
from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger

log = get_logger(__name__)


@dataclass
class StoredItem:
    """A file or package stored in the local FlashDock repository."""
    id: str
    name: str
    category: str  # "rom", "gsi", "module", "root_app", "driver", "tool"
    file_path: Path
    size_bytes: int
    version: str = ""
    description: str = ""
    target_arch: str = ""  # e.g. "arm64", "arm", "all"
    target_slot: str = ""  # e.g. "a/b", "a_only", "any"
    target_codename: str = ""  # e.g. "cheetah", "lynx", "any"
    requires_dynamic: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 2)

    def is_compatible_with(self, device: Optional[DeviceInfo]) -> tuple[bool, str]:
        """Check if this item is compatible with the connected device."""
        if not device or device.mode == "not_connected":
            return True, "No device connected (unfiltered)"

        # Codename check for device-specific ROMs
        if self.target_codename and self.target_codename.lower() != "any":
            dev_code = (device.device or "").strip().lower()
            if dev_code and dev_code != self.target_codename.lower():
                return False, f"Requires device '{self.target_codename}', connected is '{dev_code}'"

        # Architecture check (e.g. GSI arm64 vs arm)
        if self.target_arch and self.target_arch != "all":
            dev_abi = (device.cpu_abi or "").lower()
            if self.target_arch == "arm64" and "arm64" not in dev_abi and dev_abi:
                return False, f"Requires 64-bit ARM CPU, phone is '{dev_abi}'"

        # Slot scheme check (A/B vs A-only)
        if self.target_slot and self.target_slot != "any":
            if self.target_slot == "a/b" and device.slot_scheme == "a_only":
                return False, "Requires A/B slot device, phone is A-only"

        # Dynamic partitions check
        if self.requires_dynamic and not device.has_dynamic_partitions:
            return False, "Requires dynamic partitions (super.img)"

        return True, "Compatible with connected phone"


class RepositoryManager:
    """Manages files stored locally in FlashDock and evaluates compatibility."""

    def __init__(self) -> None:
        self._ensure_directories()

    @staticmethod
    def _ensure_directories() -> None:
        for p in (ROMS_DIR, GSIS_DIR, MODULES_DIR, ROOT_APPS_DIR, DRIVERS_DIR, TOOLS_DIR):
            p.mkdir(parents=True, exist_ok=True)

    def scan_all(self) -> list[StoredItem]:
        """Scan all local directories and return cataloged items."""
        items: list[StoredItem] = []
        items.extend(self.scan_roms())
        items.extend(self.scan_gsis())
        items.extend(self.scan_modules())
        items.extend(self.scan_root_apps())
        items.extend(self.scan_drivers())
        items.extend(self.scan_tools())
        return items

    def scan_roms(self) -> list[StoredItem]:
        items: list[StoredItem] = []
        for f in ROMS_DIR.glob("*"):
            if f.is_file() and f.suffix.lower() in (".zip", ".tgz", ".tar"):
                items.append(StoredItem(
                    id=f.stem,
                    name=f.name,
                    category="rom",
                    file_path=f,
                    size_bytes=f.stat().st_size,
                    description="Custom / Stock ROM package",
                ))
        return items

    def scan_gsis(self) -> list[StoredItem]:
        items: list[StoredItem] = []
        for f in GSIS_DIR.glob("*"):
            if f.is_file() and f.suffix.lower() in (".img", ".xz", ".gz", ".zip"):
                is_arm64 = "arm64" in f.name.lower() or "a64" not in f.name.lower()
                items.append(StoredItem(
                    id=f.stem,
                    name=f.name,
                    category="gsi",
                    file_path=f,
                    size_bytes=f.stat().st_size,
                    target_arch="arm64" if is_arm64 else "arm",
                    target_slot="a/b",
                    description="Generic System Image (GSI)",
                ))
        return items

    def scan_modules(self) -> list[StoredItem]:
        items: list[StoredItem] = []
        for f in MODULES_DIR.glob("*.zip"):
            mod_id = f.stem
            name = f.stem
            version = ""
            desc = "Root module ZIP"
            try:
                with zipfile.ZipFile(f, "r") as zf:
                    if "module.prop" in zf.namelist():
                        text = zf.read("module.prop").decode("utf-8", errors="ignore")
                        for line in text.splitlines():
                            if line.startswith("id="):
                                mod_id = line.split("=", 1)[1].strip()
                            elif line.startswith("name="):
                                name = line.split("=", 1)[1].strip()
                            elif line.startswith("version="):
                                version = line.split("=", 1)[1].strip()
                            elif line.startswith("description="):
                                desc = line.split("=", 1)[1].strip()
            except Exception:
                pass

            items.append(StoredItem(
                id=mod_id,
                name=name,
                category="module",
                file_path=f,
                size_bytes=f.stat().st_size,
                version=version,
                description=desc,
            ))
        return items

    def scan_root_apps(self) -> list[StoredItem]:
        items: list[StoredItem] = []
        for f in ROOT_APPS_DIR.glob("*.apk"):
            lower = f.name.lower()
            name = "Magisk" if "magisk" in lower else ("KernelSU" if "ksu" in lower or "kernelsu" in lower else ("APatch" if "apatch" in lower else f.stem))
            items.append(StoredItem(
                id=f.stem,
                name=f"{name} Manager",
                category="root_app",
                file_path=f,
                size_bytes=f.stat().st_size,
                description=f"{name} Root Manager APK",
            ))
        return items

    def scan_drivers(self) -> list[StoredItem]:
        items: list[StoredItem] = []
        for f in DRIVERS_DIR.glob("*"):
            if f.is_file():
                items.append(StoredItem(
                    id=f.stem,
                    name=f.name,
                    category="driver",
                    file_path=f,
                    size_bytes=f.stat().st_size,
                    description="USB / Fastboot / EDL Driver package",
                ))
        return items

    def scan_tools(self) -> list[StoredItem]:
        items: list[StoredItem] = []
        for f in TOOLS_DIR.glob("*"):
            if f.is_file() or f.is_dir():
                items.append(StoredItem(
                    id=f.stem,
                    name=f.name,
                    category="tool",
                    file_path=f,
                    size_bytes=f.stat().st_size if f.is_file() else 0,
                    description="Android service utility binary / tool",
                ))
        return items

    def import_rom(self, source_path: Path | str) -> StoredItem:
        """Copy a ROM package into data/roms/ and catalog it."""
        src = Path(source_path)
        dest = ROMS_DIR / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        return StoredItem(
            id=dest.stem,
            name=dest.name,
            category="rom",
            file_path=dest,
            size_bytes=dest.stat().st_size,
            description="Imported ROM package",
        )

    def import_gsi(self, source_path: Path | str) -> StoredItem:
        """Copy a GSI image into data/gsis/ and catalog it."""
        src = Path(source_path)
        dest = GSIS_DIR / src.name
        if src.resolve() != dest.resolve():
            shutil.copy2(src, dest)
        is_arm64 = "arm64" in dest.name.lower() or "a64" not in dest.name.lower()
        return StoredItem(
            id=dest.stem,
            name=dest.name,
            category="gsi",
            file_path=dest,
            size_bytes=dest.stat().st_size,
            target_arch="arm64" if is_arm64 else "arm",
            target_slot="a/b",
            description="Imported Generic System Image (GSI)",
        )

    @staticmethod
    def delete_item(item_path: Path | str) -> bool:
        """Delete a file from the repository."""
        p = Path(item_path)
        if p.is_file():
            try:
                p.unlink()
                log.info("Deleted repository item: %s", p)
                return True
            except Exception as e:
                log.warning("Could not delete item %s: %s", p, e)
        return False
