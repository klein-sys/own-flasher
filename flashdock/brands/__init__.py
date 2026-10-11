"""
FlashDock — Brand module base class and registry.

Each supported brand has a module that knows:
* How to unlock the bootloader (prerequisites, commands, gotchas).
* How to re-lock the bootloader.
* Brand-specific safety warnings.
* Where to find stock firmware.

Spec reference: Section 8.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Unlock step model
# ---------------------------------------------------------------------------
@dataclass
class UnlockStep:
    """One step in a bootloader unlock flow."""
    index: int
    title: str
    description: str
    action: str = ""           # "auto" = tool handles it, "manual" = user does it
    requires_mode: str = ""    # Device mode required (e.g. "bootloader")
    command_preview: str = ""  # Command that will run (shown to user)
    warning: str = ""          # Safety warning for this step
    completed: bool = False
    skipped: bool = False
    result: str = ""           # Outcome text after execution


@dataclass
class UnlockFlow:
    """Complete bootloader unlock procedure for a brand."""
    brand: str
    brand_display: str
    steps: list[UnlockStep] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    firmware_url: str = ""
    guide_url: str = ""
    supports_relock: bool = True
    wipes_data: bool = True
    waiting_period: str = ""   # e.g. "168 hours" for Xiaomi


# ---------------------------------------------------------------------------
# Base brand handler
# ---------------------------------------------------------------------------
class BrandHandler(ABC):
    """Abstract base for brand-specific logic."""

    @property
    @abstractmethod
    def brand_id(self) -> str:
        """Lowercase brand identifier (e.g. 'google', 'xiaomi')."""

    @property
    @abstractmethod
    def brand_display(self) -> str:
        """Human-readable brand name."""

    @abstractmethod
    def get_unlock_flow(self, device: DeviceInfo) -> UnlockFlow:
        """Return the unlock flow for this brand + device."""

    @abstractmethod
    def get_relock_flow(self, device: DeviceInfo) -> UnlockFlow:
        """Return the re-lock flow for this brand + device."""

    def get_firmware_url(self, device: DeviceInfo) -> str:
        """Return the URL to find stock firmware for this device."""
        return ""

    def get_warnings(self, device: DeviceInfo) -> list[str]:
        """Brand-specific safety warnings."""
        return []


# ---------------------------------------------------------------------------
# Brand registry
# ---------------------------------------------------------------------------
_registry: dict[str, BrandHandler] = {}


def register_brand(handler: BrandHandler) -> None:
    """Register a brand handler."""
    _registry[handler.brand_id] = handler
    log.debug("Registered brand handler: %s", handler.brand_id)


def get_brand_handler(brand_id: str) -> Optional[BrandHandler]:
    """Get a brand handler by ID."""
    return _registry.get(brand_id.lower())


def get_all_brands() -> list[BrandHandler]:
    """Return all registered brand handlers."""
    return list(_registry.values())


def get_handler_for_device(device: DeviceInfo) -> Optional[BrandHandler]:
    """Find the right brand handler for a device."""
    normalized = device.brand_normalized
    handler = get_brand_handler(normalized)
    if handler:
        return handler
    # Fall back to generic
    return get_brand_handler("generic")


# Automatically register all brand handlers
import flashdock.brands.google  # noqa: F401, E402
import flashdock.brands.xiaomi  # noqa: F401, E402
import flashdock.brands.samsung  # noqa: F401, E402
import flashdock.brands.transsion  # noqa: F401, E402
import flashdock.brands.others  # noqa: F401, E402
