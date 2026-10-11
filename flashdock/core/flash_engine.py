"""
FlashDock — Core Flash Engine Module.

Re-exports FlashEngineWorker and FlashTask from flashdock.workers.flash_engine
for clean separation of concerns and architectural consistency.
"""

from flashdock.workers.flash_engine import (
    CRITICAL_CALIBRATION_PARTITIONS,
    FlashEngineWorker,
    FlashOperationType,
    FlashTask,
)

__all__ = [
    "CRITICAL_CALIBRATION_PARTITIONS",
    "FlashEngineWorker",
    "FlashOperationType",
    "FlashTask",
]
