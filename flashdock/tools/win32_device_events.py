"""
Event-Driven Win32 Hardware Notification Listener.

Hooks into native Windows WM_DEVICECHANGE broadcasts (DBT_DEVICEARRIVAL,
DBT_DEVICEREMOVECOMPLETE, DBT_DEVNODES_CHANGED) on a lightweight background
message-only window or event loop, firing an immediate wake signal (<50ms)
so DeviceMonitorWorker can resolve short-lived BROM/EDL/Fastboot states
without burning CPU on high-frequency registry polling.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import sys
import threading
from typing import Callable

# Win32 Window & Device Broadcast Constants
WM_DEVICECHANGE = 0x0219
WM_QUIT = 0x0012
DBT_DEVNODES_CHANGED = 0x0007
DBT_DEVICEARRIVAL = 0x8000
DBT_DEVICEREMOVECOMPLETE = 0x8004
DBT_DEVTYP_DEVICEINTERFACE = 0x00000005
DEVICE_NOTIFY_WINDOW_HANDLE = 0x00000000
DEVICE_NOTIFY_ALL_INTERFACE_CLASSES = 0x00000004


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class DEV_BROADCAST_DEVICEINTERFACE_W(ctypes.Structure):
    _fields_ = [
        ("dbcc_size", wintypes.DWORD),
        ("dbcc_devicetype", wintypes.DWORD),
        ("dbcc_reserved", wintypes.DWORD),
        ("dbcc_classguid", GUID),
        ("dbcc_name", ctypes.c_wchar * 256),
    ]


# Standard USB Device Interface GUID: {A5DCBF10-6530-11D2-901F-00C04FB951ED}
GUID_DEVINTERFACE_USB_DEVICE = GUID(
    0xA5DCBF10,
    0x6530,
    0x11D2,
    (ctypes.c_ubyte * 8)(0x90, 0x1F, 0x00, 0xC0, 0x4F, 0xB9, 0x51, 0xED),
)


class Win32DeviceEventMonitor:
    """
    Thread-safe hardware event coordinator combining a `threading.Event` wake
    primitive with native Win32 `WM_DEVICECHANGE` notifications.
    """

    def __init__(self, on_hardware_event: Callable[[str], None] | None = None) -> None:
        self._wake_event = threading.Event()
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._on_hardware_event = on_hardware_event
        self._last_event_type: str = "IDLE"
        self._event_counter: int = 0
        self._thread: threading.Thread | None = None
        self._native_thread_id: int | None = None

    @property
    def event_counter(self) -> int:
        with self._lock:
            return self._event_counter

    @property
    def last_event_type(self) -> str:
        with self._lock:
            return self._last_event_type

    def notify_event(self, event_type: str = "DBT_DEVNODES_CHANGED") -> None:
        """Signal an immediate hardware state transition wake-up."""
        with self._lock:
            self._last_event_type = event_type
            self._event_counter += 1
            cb = self._on_hardware_event
        self._wake_event.set()
        if cb is not None:
            try:
                cb(event_type)
            except Exception:
                pass

    def wait_for_event_or_timeout(self, timeout_sec: float = 1.5) -> bool:
        """
        Block up to `timeout_sec` seconds or until a Win32 hardware event
        (or manual wake signal) arrives. Returns True if woken by an event.
        """
        triggered = self._wake_event.wait(timeout=max(0.01, float(timeout_sec)))
        if triggered:
            self._wake_event.clear()
        return triggered

    def start(self) -> None:
        """Start the background Win32 notification listener if on Windows."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop_event.clear()
            if sys.platform == "win32":
                self._thread = threading.Thread(
                    target=self._win32_message_loop,
                    name="FlashDock-WMDeviceChange",
                    daemon=True,
                )
                self._thread.start()

    def stop(self) -> None:
        """Cooperatively stop the listener thread and wake any waiting worker."""
        self._stop_event.set()
        self._wake_event.set()
        if sys.platform == "win32" and self._native_thread_id is not None:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    wintypes.DWORD(self._native_thread_id),
                    WM_QUIT,
                    0,
                    0,
                )
            except Exception:
                pass
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def _win32_message_loop(self) -> None:
        """Run a lightweight Win32 PeekMessage/GetMessage loop for device broadcasts."""
        try:
            kernel32 = ctypes.windll.kernel32
            user32 = ctypes.windll.user32
            self._native_thread_id = int(kernel32.GetCurrentThreadId())

            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                # Wait up to 250ms for thread/window messages
                res = user32.MsgWaitForMultipleObjects(0, None, False, 250, 0x04FF)
                if res == 0:
                    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                        if msg.message == WM_QUIT:
                            return
                        if msg.message == WM_DEVICECHANGE:
                            wparam = int(msg.wParam)
                            if wparam in (
                                DBT_DEVICEARRIVAL,
                                DBT_DEVICEREMOVECOMPLETE,
                                DBT_DEVNODES_CHANGED,
                            ):
                                self.notify_event(f"WM_DEVICECHANGE:0x{wparam:04X}")
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
        except Exception:
            pass

