"""
FlashDock — Constants used across the entire application.

All hard-coded values (paths, defaults, limits) live here so they are
easy to find and change.  Nothing in this file should import from any
other FlashDock module to avoid circular imports.
"""

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Application metadata
# ---------------------------------------------------------------------------
APP_NAME = "FlashDock"
APP_VERSION = "1.3.3"
APP_AUTHOR = "FlashDock Contributors"
APP_DESCRIPTION = (
    "Personal, one-click Android service toolbox for Windows."
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# When running from source the root is the repo folder.
# When frozen (PyInstaller) sys._MEIPASS points to the temp extraction dir,
# but user data must stay in a stable location so we use APPDATA.
if getattr(sys, "frozen", False):
    # Running as compiled .exe
    APP_DIR = Path(sys._MEIPASS)
    # User data goes into %LOCALAPPDATA%\FlashDock
    DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / APP_NAME
else:
    # Running from source
    APP_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = APP_DIR / "data"

TOOLS_DIR = DATA_DIR / "tools"
DRIVERS_DIR = DATA_DIR / "drivers"
ROMS_DIR = DATA_DIR / "roms"
GSIS_DIR = DATA_DIR / "gsis"
MODULES_DIR = DATA_DIR / "modules"
ROOT_APPS_DIR = DATA_DIR / "root_apps"
BACKUPS_DIR = DATA_DIR / "backups"
LOGS_DIR = DATA_DIR / "logs"
CRASHES_DIR = DATA_DIR / "crashes"
CACHE_DIR = DATA_DIR / "cache"
PROFILES_DIR = DATA_DIR / "profiles"
DB_PATH = DATA_DIR / "flashdock.db"
CONFIG_PATH = DATA_DIR / "config.json"
RESOURCES_DIR = APP_DIR / "resources"
ICONS_DIR = RESOURCES_DIR / "icons"
LICENSES_DIR = RESOURCES_DIR / "licenses"

# Ensure runtime directories exist
for _dir in (DATA_DIR, TOOLS_DIR, DRIVERS_DIR, ROMS_DIR, GSIS_DIR, MODULES_DIR, ROOT_APPS_DIR, BACKUPS_DIR, LOGS_DIR, CRASHES_DIR, CACHE_DIR, PROFILES_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Safety defaults
# ---------------------------------------------------------------------------
MIN_BATTERY_PERCENT = 60  # Block flashing below this level.
DEVICE_TIMEOUT_SECONDS = 120  # How long to wait for a device after reboot.
ADB_POLL_INTERVAL_MS = 2000  # How often to poll for device state.
CONFIRMATION_WORD = "FLASH"  # Typed confirmation for destructive actions.

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
CONNECTIVITY_CHECK_URLS = [
    "https://connectivitycheck.gstatic.com/generate_204",
    "https://clients3.google.com/generate_204",
    "https://www.msftconnecttest.com/connecttest.txt",
]
CONNECTIVITY_CHECK_TIMEOUT = 5  # seconds
CONNECTIVITY_RECHECK_INTERVAL = 30  # seconds between automatic rechecks

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per log file
LOG_BACKUP_COUNT = 5  # Number of rotated log files to keep
LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"

# ---------------------------------------------------------------------------
# Database / cache
# ---------------------------------------------------------------------------
CACHE_STALE_DAYS = 7  # Show "cache is X days old" warning after this

# ---------------------------------------------------------------------------
# Allowed tools (used by the Tools Manager in a later phase)
# ---------------------------------------------------------------------------
# Minimal set needed for Phase 1 detection
PLATFORM_TOOLS_VERSION = "35.0.2"  # Minimum recommended version

# ---------------------------------------------------------------------------
# Modes the phone can be in
# ---------------------------------------------------------------------------
DEVICE_MODES = [
    "system",        # Booted into Android OS
    "recovery",      # Recovery mode (stock or custom)
    "bootloader",    # Fastboot / bootloader mode
    "fastbootd",     # FastbootD (userspace fastboot)
    "download",      # Samsung download mode
    "edl",           # Qualcomm EDL / 9008 mode
    "brom",          # MTK BROM mode
    "sideload",      # ADB sideload mode
    "unauthorized",  # ADB visible but not authorized
    "offline",       # ADB sees it but can't talk to it
    "not_connected", # Nothing detected
]

# ---------------------------------------------------------------------------
# Brand identifiers (lowercase, used by brand modules)
# ---------------------------------------------------------------------------
BRANDS = [
    "google",
    "samsung",
    "xiaomi",
    "redmi",
    "poco",
    "oneplus",
    "oppo",
    "realme",
    "motorola",
    "sony",
    "nokia",
    "asus",
    "tecno",
    "infinix",
    "itel",
    "huawei",
    "vivo",
    "nothing",
    "fairphone",
    "unknown",
]

# ---------------------------------------------------------------------------
# Chipset families
# ---------------------------------------------------------------------------
CHIPSETS = [
    "snapdragon",
    "exynos",
    "mediatek",
    "unisoc",
    "tensor",
    "kirin",
    "unknown",
]
