"""
FlashDock — Application-wide logger.

Features
--------
* Rotating file handler  (10 MB × 5 backups by default)
* Console handler with colour-coded levels
* Serial-number masking in exported logs
* Structured per-command logging for flash operations
* Thread-safe

Usage
-----
    from flashdock.logger import get_logger
    log = get_logger(__name__)
    log.info("Device detected: %s", codename)
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from flashdock.constants import (
    LOG_BACKUP_COUNT,
    LOG_DATE_FMT,
    LOG_MAX_BYTES,
    LOGS_DIR,
)

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_initialized = False
_init_lock = threading.Lock()
_log_file_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Custom formatter with optional colour
# ---------------------------------------------------------------------------
class _ColorFormatter(logging.Formatter):
    """Adds ANSI colour codes for console output on Windows 10+."""

    COLORS = {
        logging.DEBUG:    "\033[36m",   # cyan
        logging.INFO:     "\033[32m",   # green
        logging.WARNING:  "\033[33m",   # yellow
        logging.ERROR:    "\033[31m",   # red
        logging.CRITICAL: "\033[1;31m", # bold red
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, "")
        message = super().format(record)
        return f"{color}{message}{self.RESET}"


# ---------------------------------------------------------------------------
# Serial-number mask filter (applied only when exporting)
# ---------------------------------------------------------------------------
# Matches common ADB serial formats:  hex serials, ip:port, and "emulator-XXXX"
_SERIAL_RE = re.compile(
    r"\b([A-Z0-9]{6,}[A-Za-z0-9]*)\b"    # hex-ish serial like ZY22FV6BKR
    r"|(\d{1,3}(?:\.\d{1,3}){3}:\d+)"     # 192.168.1.2:5555
    r"|(emulator-\d+)"                      # emulator-5554
)


def mask_serials(text: str) -> str:
    """Replace anything that looks like a device serial with [SERIAL]."""
    return _SERIAL_RE.sub("[SERIAL]", text)


# ---------------------------------------------------------------------------
# Action logger — structured logging for flash operations
# ---------------------------------------------------------------------------
class ActionRecord:
    """Immutable record of a single command/action for the action log."""

    __slots__ = (
        "timestamp", "action", "command", "device_serial",
        "result", "output", "duration_ms",
    )

    def __init__(
        self,
        action: str,
        command: str,
        device_serial: str = "",
        result: str = "",
        output: str = "",
        duration_ms: int = 0,
    ) -> None:
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.action = action
        self.command = command
        self.device_serial = device_serial
        self.result = result
        self.output = output
        self.duration_ms = duration_ms

    def to_dict(self) -> dict:
        return {s: getattr(self, s) for s in self.__slots__}

    def to_masked_dict(self) -> dict:
        """Same as to_dict() but with serials replaced."""
        d = self.to_dict()
        d["device_serial"] = "[SERIAL]"
        d["command"] = mask_serials(d["command"])
        d["output"] = mask_serials(d["output"])
        return d


class ActionLog:
    """Thread-safe list of ActionRecords kept in memory and flushed to the
    main log file.  Also used by the Crash Recovery system (later phase)."""

    def __init__(self) -> None:
        self._records: list[ActionRecord] = []
        self._lock = threading.Lock()
        self._logger = logging.getLogger("flashdock.actions")

    def record(self, rec: ActionRecord) -> None:
        with self._lock:
            self._records.append(rec)
        self._logger.info(
            "[%s] %s → %s (%d ms)",
            rec.action, rec.command, rec.result, rec.duration_ms,
        )

    @property
    def records(self) -> list[ActionRecord]:
        with self._lock:
            return list(self._records)

    def export_masked(self) -> list[dict]:
        """Return all records with serials removed — safe for forum posts."""
        return [r.to_masked_dict() for r in self.records]


# Singleton action log
action_log = ActionLog()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def _ensure_log_dir() -> Path:
    """Create the logs directory and return the path to today's log file."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    return LOGS_DIR / f"flashdock_{today}.log"


def setup_logging(level: int = logging.DEBUG, console: bool = True) -> Path:
    """
    Configure the root ``flashdock`` logger.

    Called once at startup.  Returns the path to the current log file.
    """
    global _initialized, _log_file_path

    with _init_lock:
        if _initialized:
            return _log_file_path  # type: ignore[return-value]

        log_file = _ensure_log_dir()
        _log_file_path = log_file

        root = logging.getLogger("flashdock")
        root.setLevel(level)
        root.propagate = False  # Don't leak into the default root logger.

        # --- File handler (rotating) ---
        fmt = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt=LOG_DATE_FMT,
        )
        fh = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        root.addHandler(fh)

        # --- Console handler (coloured) ---
        if console:
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(
                _ColorFormatter(
                    fmt="%(asctime)s | %(levelname)-8s | %(message)s",
                    datefmt=LOG_DATE_FMT,
                )
            )
            root.addHandler(ch)

        _initialized = True
        root.info("Logger initialised — log file: %s", log_file)
        return log_file


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the ``flashdock`` namespace.

    If ``setup_logging()`` hasn't been called yet, it is called with
    defaults so that nothing is ever lost.
    """
    if not _initialized:
        setup_logging()
    return logging.getLogger(name if name.startswith("flashdock") else f"flashdock.{name}")


def get_log_file_path() -> Optional[Path]:
    """Return the path to the current log file, or None if not yet set up."""
    return _log_file_path
