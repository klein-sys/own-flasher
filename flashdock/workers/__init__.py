"""
FlashDock — Asynchronous Background Workers Package.

Contains dedicated QThread workers for:
- Hardware and USB/COM port device monitoring (DeviceMonitorWorker)
- Asynchronous firmware and partition flashing (FlashEngineWorker)
"""

from flashdock.workers.device_monitor import (
    DeviceMonitorWorker,
    HardwareMode,
    HARDWARE_VID_PID_MAP,
    identify_hardware_device,
)
from flashdock.workers.flash_engine import (
    CRITICAL_CALIBRATION_PARTITIONS,
    FlashEngineWorker,
    FlashOperationType,
    FlashTask,
)

__all__ = [
    "DeviceMonitorWorker",
    "HardwareMode",
    "HARDWARE_VID_PID_MAP",
    "identify_hardware_device",
    "FlashEngineWorker",
    "FlashOperationType",
    "FlashTask",
    "CRITICAL_CALIBRATION_PARTITIONS",
]
