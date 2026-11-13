"""Broadcast existing device snapshots to the workstation's Qt views."""

from PySide6.QtCore import QObject, Signal, Slot

from flashdock.core.device import DeviceInfo


class DeviceStateBroadcaster(QObject):
    """Publish telemetry on the owning thread and report identity transitions."""

    state_updated = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._last_identity: tuple[str, str] | None = None

    @Slot(object)
    def publish(self, device: DeviceInfo | None) -> bool:
        identity = (device.mode, device.serial) if device else None
        changed = identity != self._last_identity
        self._last_identity = identity
        # Battery, slot and hardware properties can change on the same device.
        self.state_updated.emit(device)
        return changed
