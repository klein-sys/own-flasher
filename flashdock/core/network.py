"""
FlashDock — Network / connectivity helpers.

Detects whether the PC is online by probing lightweight "generate 204"
endpoints (Google and Microsoft).  Runs checks in a background thread
and exposes a signal-friendly API so the UI can react instantly.

Usage
-----
    from flashdock.core.network import NetworkMonitor

    monitor = NetworkMonitor()
    monitor.status_changed.connect(on_status_changed)   # PySide6 signal
    monitor.start()
    ...
    print(monitor.is_online)
"""

from __future__ import annotations

import socket
import threading
import time
from typing import Callable, Optional
from urllib.request import urlopen, Request
from urllib.error import URLError

from flashdock.constants import (
    CONNECTIVITY_CHECK_TIMEOUT,
    CONNECTIVITY_CHECK_URLS,
    CONNECTIVITY_RECHECK_INTERVAL,
)
from flashdock.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Pure check function (no Qt dependency)
# ---------------------------------------------------------------------------
def check_connectivity(
    urls: Optional[list[str]] = None,
    timeout: int = CONNECTIVITY_CHECK_TIMEOUT,
) -> bool:
    """Return ``True`` if any of the *urls* respond within *timeout* seconds.

    Tries each URL in order and returns on the first success.  This is
    designed to be cheap — the Google and MS endpoints return only a
    status code with no body.
    """
    urls = urls or CONNECTIVITY_CHECK_URLS
    for url in urls:
        try:
            req = Request(url, method="HEAD")
            with urlopen(req, timeout=timeout) as resp:
                # 204 = Google, 200 = Microsoft
                if resp.status in (200, 204):
                    return True
        except (URLError, OSError, socket.timeout):
            continue
    return False


# ---------------------------------------------------------------------------
# Threaded monitor (can be used with or without Qt)
# ---------------------------------------------------------------------------
class NetworkMonitor:
    """Background thread that periodically checks internet connectivity.

    Attributes
    ----------
    is_online : bool
        Latest known connectivity state.
    on_change : callable | None
        Optional callback ``(is_online: bool) -> None`` fired whenever the
        state changes.  Set this *before* calling :meth:`start`.
    """

    def __init__(
        self,
        interval: int = CONNECTIVITY_RECHECK_INTERVAL,
        on_change: Optional[Callable[[bool], None]] = None,
    ) -> None:
        self._interval = interval
        self.on_change = on_change
        self.is_online: bool = False
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ---- Public API -------------------------------------------------------

    def start(self) -> None:
        """Start the background polling thread."""
        if self._thread and self._thread.is_alive():
            log.debug("NetworkMonitor already running.")
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="NetworkMonitor"
        )
        self._thread.start()
        log.info("NetworkMonitor started (interval=%ds).", self._interval)

    def stop(self) -> None:
        """Stop the background thread gracefully."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=self._interval + 2)
            log.info("NetworkMonitor stopped.")

    def check_now(self) -> bool:
        """Run an immediate check (blocking) and update ``is_online``."""
        result = check_connectivity()
        self._update(result)
        return result

    @property
    def status_label(self) -> str:
        """Human-friendly label for the status bar."""
        return "Online" if self.is_online else "Offline"

    # ---- Internal ---------------------------------------------------------

    def _run(self) -> None:
        """Polling loop — exits when ``_stop_event`` is set."""
        while not self._stop_event.is_set():
            result = check_connectivity()
            self._update(result)
            # Sleep in small increments so we can stop quickly
            for _ in range(self._interval * 10):
                if self._stop_event.is_set():
                    return
                time.sleep(0.1)

    def _update(self, new_state: bool) -> None:
        old = self.is_online
        self.is_online = new_state
        if old != new_state:
            log.info("Connectivity changed: %s", "ONLINE" if new_state else "OFFLINE")
            if self.on_change:
                try:
                    self.on_change(new_state)
                except Exception:
                    log.exception("Error in on_change callback")
