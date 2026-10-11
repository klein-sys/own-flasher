"""
FlashDock — Core Device Monitor Module.

Re-exports the DeviceMonitorWorker and hardware mapping definitions from
flashdock.workers.device_monitor for architectural modularity.
"""

from flashdock.workers.device_monitor import (
    DeviceMonitorWorker,
    HardwareMode,
    HardwareProfile,
    HARDWARE_VID_PID_MAP,
    identify_hardware_device,
)

__all__ = [
    "DeviceMonitorWorker",
    "HardwareMode",
    "HardwareProfile",
    "HARDWARE_VID_PID_MAP",
    "identify_hardware_device",
]
