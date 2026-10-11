"""
FlashDock — Subprocess runner shared by all tool wrappers.

Every external command (adb, fastboot, mtkclient, …) goes through this
module so that:

* Dry-run mode is respected globally.
* Every command is logged via the ActionLog.
* Timeouts are enforced.
* Output is captured consistently.
* The "do not unplug" lock can block new commands during a flash.
"""

from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from flashdock.logger import ActionRecord, action_log, get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Global flash lock — only one flash operation at a time (Section 3 rule)
# ---------------------------------------------------------------------------
_flash_lock = threading.Lock()


def acquire_flash_lock(timeout: float = 0) -> bool:
    """Try to acquire the global flash lock.  Returns True on success."""
    return _flash_lock.acquire(timeout=timeout)


def release_flash_lock() -> None:
    """Release the global flash lock."""
    try:
        _flash_lock.release()
    except RuntimeError:
        pass  # Already released


def is_flash_locked() -> bool:
    """Return True if a flash operation is in progress."""
    if _flash_lock.acquire(blocking=False):
        _flash_lock.release()
        return False
    return True


# ---------------------------------------------------------------------------
# Command result
# ---------------------------------------------------------------------------
@dataclass
class CommandResult:
    """Immutable result of a subprocess execution."""

    command: list[str]
    return_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False
    dry_run: bool = False

    @property
    def success(self) -> bool:
        return self.return_code == 0 and not self.timed_out

    @property
    def output(self) -> str:
        """Combined stdout + stderr for convenience."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return "\n".join(parts)

    @property
    def command_str(self) -> str:
        return " ".join(self.command)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
def run_command(
    cmd: list[str],
    *,
    timeout: int = 60,
    dry_run: bool = False,
    action_name: str = "command",
    device_serial: str = "",
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    input_data: Optional[str] = None,
) -> CommandResult:
    """Execute *cmd* as a subprocess and return a :class:`CommandResult`.

    Parameters
    ----------
    cmd : list[str]
        The command and its arguments.
    timeout : int
        Maximum seconds before the process is killed.
    dry_run : bool
        If True, log the command but do not execute it.
    action_name : str
        Human-readable label for the ActionLog (e.g. "flash_boot").
    device_serial : str
        Serial number of the target device (for logging).
    cwd : Path | None
        Working directory for the subprocess.
    env : dict | None
        Extra environment variables merged with os.environ.
    input_data : str | None
        Data to send to the process's stdin.
    """
    cmd_str = " ".join(cmd)

    # --- Dry run ---
    if dry_run:
        log.info("[DRY RUN] %s", cmd_str)
        result = CommandResult(
            command=cmd,
            return_code=0,
            stdout=f"[DRY RUN] Would execute: {cmd_str}",
            stderr="",
            duration_ms=0,
            dry_run=True,
        )
        action_log.record(
            ActionRecord(
                action=action_name,
                command=cmd_str,
                device_serial=device_serial,
                result="dry_run",
                duration_ms=0,
            )
        )
        return result

    # --- Real execution ---
    log.debug("Running: %s", cmd_str)
    start = time.monotonic()
    timed_out = False

    import os
    full_env = os.environ.copy()
    if env:
        full_env.update(env)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=full_env,
            input=input_data,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        stdout = proc.stdout or ""
        stderr = proc.stderr or ""
        return_code = proc.returncode
    except subprocess.TimeoutExpired:
        log.warning("Command timed out after %ds: %s", timeout, cmd_str)
        stdout = ""
        stderr = f"Command timed out after {timeout}s"
        return_code = -1
        timed_out = True
    except FileNotFoundError:
        log.debug("Binary not found: %s", cmd[0])
        stdout = ""
        stderr = f"Binary not found: {cmd[0]}"
        return_code = -1
    except OSError as exc:
        log.error("OS error running %s: %s", cmd[0], exc)
        stdout = ""
        stderr = str(exc)
        return_code = -1

    elapsed_ms = int((time.monotonic() - start) * 1000)

    result = CommandResult(
        command=cmd,
        return_code=return_code,
        stdout=stdout.strip(),
        stderr=stderr.strip(),
        duration_ms=elapsed_ms,
        timed_out=timed_out,
    )

    # Log it
    status = "success" if result.success else f"error (rc={return_code})"
    action_log.record(
        ActionRecord(
            action=action_name,
            command=cmd_str,
            device_serial=device_serial,
            result=status,
            output=result.output[:500],  # Truncate for the log
            duration_ms=elapsed_ms,
        )
    )

    if result.success:
        log.debug("OK (%dms): %s", elapsed_ms, cmd_str)
    else:
        log.warning("FAIL (rc=%d, %dms): %s — %s",
                     return_code, elapsed_ms, cmd_str, result.stderr[:200])

    return result
