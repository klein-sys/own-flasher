"""
FlashDock — Configuration manager.

Reads and writes ``config.json`` in the data directory.  Provides typed
access to every setting with sensible defaults so the app always works
even on first run or with a missing / corrupted config file.

Thread-safe: reads are lock-free (immutable snapshots), writes acquire a
reentrant lock and flush to disk immediately.
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from flashdock.constants import CONFIG_PATH, DATA_DIR
from flashdock.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Default configuration — every key must appear here with its default.
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    # --- General ---
    "app_mode": "simple",           # "simple" | "advanced"
    "dry_run": False,               # Global dry-run toggle
    "dark_mode": True,              # UI theme
    "first_run": True,              # Show disclaimer on first launch
    "language": "en",               # UI language (only "en" for v1.0)
    "disclaimer_accepted": False,   # User accepted the risk disclaimer

    # --- Device ---
    "locked_serial": None,          # Serial number lock for multi-device safety
    "last_device_serial": None,     # Most recently used device

    # --- Paths (overrides — empty means use the constant defaults) ---
    "custom_tools_dir": "",
    "custom_backups_dir": "",

    # --- Network ---
    "offline_mode": False,          # Force offline (ignore connectivity)
    "connectivity_recheck_sec": 30, # Auto-recheck interval

    # --- Safety ---
    "auto_backup_before_flash": True,
    "min_battery_percent": 60,
    "block_unverified_files": True, # Require double-confirm for unknowns

    # --- Logging ---
    "log_level": "DEBUG",           # DEBUG | INFO | WARNING | ERROR
    "mask_serials_on_export": True,

    # --- Tools Manager ---
    "tool_install_dir": "",         # Empty → use TOOLS_DIR constant
    "check_tool_updates_on_start": True,

    # --- Window state (saved on exit, restored on launch) ---
    "window_width": 1100,
    "window_height": 750,
    "window_x": None,
    "window_y": None,
}


# ---------------------------------------------------------------------------
# Config class
# ---------------------------------------------------------------------------
class Config:
    """Persistent JSON-backed configuration store.

    Usage::

        cfg = Config.load()           # Load or create config.json
        mode = cfg.get("app_mode")    # Read a value
        cfg.set("dry_run", True)      # Write + flush to disk
        cfg.save()                    # Explicit save (also done by .set())
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or CONFIG_PATH
        self._data: dict[str, Any] = deepcopy(_DEFAULTS)
        self._lock = threading.RLock()

    # ---- Load / Save -------------------------------------------------------

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        """Load config from disk, merging with defaults for any missing keys."""
        cfg = cls(path)
        cfg._path.parent.mkdir(parents=True, exist_ok=True)

        if cfg._path.exists():
            try:
                with open(cfg._path, "r", encoding="utf-8") as fh:
                    disk_data = json.load(fh)
                # Merge: disk values override defaults; unknown keys are kept
                cfg._data.update(disk_data)
                log.info("Configuration loaded from %s", cfg._path)
            except (json.JSONDecodeError, OSError) as exc:
                log.warning(
                    "Could not read config file (%s). Using defaults.", exc
                )
        else:
            log.info(
                "No config file found at %s — creating with defaults.",
                cfg._path,
            )
            cfg.save()

        return cfg

    def save(self) -> None:
        """Flush current state to disk."""
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(self._path, "w", encoding="utf-8") as fh:
                    json.dump(self._data, fh, indent=2, ensure_ascii=False)
                log.debug("Configuration saved to %s", self._path)
            except OSError as exc:
                log.error("Failed to save config: %s", exc)

    # ---- Getters / Setters -------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for *key*, falling back to *default* (or the
        built-in default if *default* is ``None``)."""
        val = self._data.get(key)
        if val is None:
            return default if default is not None else _DEFAULTS.get(key)
        return val

    def set(self, key: str, value: Any, *, save: bool = True) -> None:
        """Set *key* to *value* and optionally flush to disk."""
        with self._lock:
            self._data[key] = value
            if save:
                self.save()

    def reset(self, key: str) -> None:
        """Reset a single key to its default value."""
        with self._lock:
            self._data[key] = deepcopy(_DEFAULTS.get(key))
            self.save()

    def reset_all(self) -> None:
        """Reset every setting to defaults and save."""
        with self._lock:
            self._data = deepcopy(_DEFAULTS)
            self.save()

    # ---- Convenience typed accessors --------------------------------------

    @property
    def is_simple_mode(self) -> bool:
        return self.get("app_mode") == "simple"

    @property
    def is_advanced_mode(self) -> bool:
        return self.get("app_mode") == "advanced"

    @property
    def dry_run(self) -> bool:
        return bool(self.get("dry_run"))

    @property
    def dark_mode(self) -> bool:
        return bool(self.get("dark_mode"))

    @property
    def first_run(self) -> bool:
        return bool(self.get("first_run"))

    @property
    def disclaimer_accepted(self) -> bool:
        return bool(self.get("disclaimer_accepted"))

    @property
    def locked_serial(self) -> Optional[str]:
        return self.get("locked_serial")

    @property
    def offline_forced(self) -> bool:
        return bool(self.get("offline_mode"))

    @property
    def tools_dir(self) -> Path:
        custom = self.get("custom_tools_dir")
        if custom:
            return Path(custom)
        from flashdock.constants import TOOLS_DIR
        return TOOLS_DIR

    @property
    def backups_dir(self) -> Path:
        custom = self.get("custom_backups_dir")
        if custom:
            return Path(custom)
        from flashdock.constants import BACKUPS_DIR
        return BACKUPS_DIR

    # ---- Dunder -----------------------------------------------------------

    def __repr__(self) -> str:
        return f"<Config path={self._path} keys={len(self._data)}>"
