"""
FlashDock -- Bootloader unlock wizard screen.

Step-by-step guided UI for unlocking (or re-locking) the bootloader,
with brand-specific flows, safety warnings, and dry-run support.

Spec reference: Section 8.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flashdock.brands import (
    UnlockFlow,
    UnlockStep,
    get_handler_for_device,
)
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)

# Import brand modules to trigger registration
import flashdock.brands.google  # noqa: F401
import flashdock.brands.xiaomi  # noqa: F401
import flashdock.brands.samsung  # noqa: F401
import flashdock.brands.others  # noqa: F401


# ---------------------------------------------------------------------------
# Step widget
# ---------------------------------------------------------------------------
class _StepWidget(QFrame):
    """One step card in the wizard."""

    execute_requested = Signal(int)  # step index

    def __init__(self, step: UnlockStep, parent: QWidget | None = None):
        super().__init__(parent)
        self._step = step
        self.setProperty("cssClass", "card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)

        # Header: step number + title + status
        header = QHBoxLayout()
        header.setSpacing(10)

        num = QLabel(f"Step {step.index}")
        num.setProperty("cssClass", "code_text")
        num.setFixedWidth(55)
        header.addWidget(num)

        title = QLabel(step.title)
        title.setProperty("cssClass", "subheading")
        header.addWidget(title, 1)

        badge = QLabel("auto" if step.action == "auto" else "manual")
        badge.setProperty("cssClass", "code_text" if step.action == "auto" else "muted")
        header.addWidget(badge)

        layout.addLayout(header)

        # Description
        desc = QLabel(step.description)
        desc.setWordWrap(True)
        desc.setProperty("cssClass", "muted")
        layout.addWidget(desc)

        # Command preview
        if step.command_preview:
            cmd_frame = QFrame()
            cmd_frame.setProperty("cssClass", "code_box")
            cmd_layout = QHBoxLayout(cmd_frame)
            cmd_layout.setContentsMargins(8, 4, 8, 4)
            cmd_label = QLabel(f"$ {step.command_preview}")
            cmd_label.setProperty("cssClass", "code_text")
            cmd_layout.addWidget(cmd_label)
            layout.addWidget(cmd_frame)

        # Warning
        if step.warning:
            warn = QLabel(f"⚠️  {step.warning}")
            warn.setWordWrap(True)
            warn.setProperty("cssClass", "warn_banner")
            layout.addWidget(warn)

        # Action button (for auto steps)
        if step.action == "auto":
            btn_row = QHBoxLayout()
            self._exec_btn = QPushButton("▶  Execute this step")
            self._exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._exec_btn.setProperty("cssClass", "primary")
            self._exec_btn.clicked.connect(lambda: self.execute_requested.emit(step.index))
            btn_row.addWidget(self._exec_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

        # Result area (hidden until step runs)
        self._result_label = QLabel("")
        self._result_label.setWordWrap(True)
        self._result_label.setProperty("cssClass", "success")
        self._result_label.hide()
        layout.addWidget(self._result_label)

    def mark_completed(self, result: str = "") -> None:
        self._step.completed = True
        self._result_label.setText(f"✅  {result or 'Completed'}")
        self._result_label.setProperty("cssClass", "success")
        self._result_label.show()
        if hasattr(self, "_exec_btn"):
            self._exec_btn.setEnabled(False)
            self._exec_btn.setText("Done")

    def mark_failed(self, error: str = "") -> None:
        self._result_label.setText(f"❌  {error or 'Failed'}")
        self._result_label.setProperty("cssClass", "error")
        self._result_label.show()


# ---------------------------------------------------------------------------
# Unlock wizard screen
# ---------------------------------------------------------------------------
class UnlockScreen(QWidget):
    """The bootloader unlock wizard page."""

    def __init__(
        self,
        device_mgr: DeviceManager,
        adb: ADB,
        fastboot: Fastboot,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb
        self._fb = fastboot
        self._flow: Optional[UnlockFlow] = None
        self._step_widgets: list[_StepWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(12)

        # Header
        title = QLabel("🔓  Bootloader Unlock Wizard")
        title.setProperty("cssClass", "heading")
        layout.addWidget(title)

        self._subtitle = QLabel("Connect a device to begin.")
        self._subtitle.setProperty("cssClass", "muted")
        layout.addWidget(self._subtitle)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(10)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Load the unlock wizard for the detected device."""
        self._clear_content()

        if not device or device.mode == "not_connected":
            self._subtitle.setText("No device connected. Plug in your phone to begin.")
            placeholder = QLabel("Connect a phone via USB to see the unlock wizard for your brand.")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setProperty("cssClass", "muted")
            self._content_layout.insertWidget(0, placeholder)
            return

        # Already unlocked?
        if device.bootloader_state == "unlocked":
            self._subtitle.setText(f"{device.summary_line} -- Bootloader is already UNLOCKED")
            info = QLabel(
                "✅  Your bootloader is already unlocked.\n\n"
                "You can proceed to rooting, flashing ROMs, or other tasks.\n"
                "If you want to RE-LOCK the bootloader, use 'Return to Stock'."
            )
            info.setWordWrap(True)
            info.setProperty("cssClass", "card")
            self._content_layout.insertWidget(0, info)
            return

        # Get brand handler
        handler = get_handler_for_device(device)
        if not handler:
            self._subtitle.setText("Unknown brand. Using generic unlock flow.")
            from flashdock.brands import get_brand_handler
            handler = get_brand_handler("generic")
            if not handler:
                return

        self._flow = handler.get_unlock_flow(device)
        self._subtitle.setText(
            f"{self._flow.brand_display} unlock flow for {device.summary_line}"
        )
        self._build_flow_ui()

    def _build_flow_ui(self) -> None:
        """Build the wizard UI from the current flow."""
        if not self._flow:
            return

        flow = self._flow

        # Warnings banner
        if flow.warnings:
            warn_text = "\n".join(f"  - {w}" for w in flow.warnings)
            warn = QLabel(f"⚠️  IMPORTANT WARNINGS:\n{warn_text}")
            warn.setWordWrap(True)
            warn.setProperty("cssClass", "danger_banner")
            self._content_layout.insertWidget(self._content_layout.count() - 1, warn)

        # Prerequisites
        if flow.prerequisites:
            prereq_frame = QFrame()
            prereq_frame.setProperty("cssClass", "card")
            prereq_layout = QVBoxLayout(prereq_frame)
            prereq_layout.setContentsMargins(12, 8, 12, 8)
            prereq_layout.setSpacing(4)
            prereq_title = QLabel("📋  Prerequisites")
            prereq_title.setProperty("cssClass", "subheading")
            prereq_layout.addWidget(prereq_title)
            for p in flow.prerequisites:
                item = QLabel(f"  - {p}")
                item.setWordWrap(True)
                item.setProperty("cssClass", "muted")
                prereq_layout.addWidget(item)
            self._content_layout.insertWidget(self._content_layout.count() - 1, prereq_frame)

        # Data wipe warning
        if flow.wipes_data:
            wipe = QLabel(
                "🗑️  THIS PROCESS WILL ERASE ALL DATA ON YOUR PHONE.\n"
                "     Back up everything before proceeding."
            )
            wipe.setWordWrap(True)
            wipe.setProperty("cssClass", "warn_banner")
            self._content_layout.insertWidget(self._content_layout.count() - 1, wipe)

        # Waiting period notice
        if flow.waiting_period:
            wait = QLabel(f"⏳  Waiting period required: {flow.waiting_period}")
            wait.setProperty("cssClass", "info_banner")
            self._content_layout.insertWidget(self._content_layout.count() - 1, wait)

        # Steps
        steps_title = QLabel(f"Steps ({len(flow.steps)} total)")
        steps_title.setProperty("cssClass", "subheading")
        self._content_layout.insertWidget(self._content_layout.count() - 1, steps_title)

        self._step_widgets = []
        for step in flow.steps:
            sw = _StepWidget(step)
            sw.execute_requested.connect(self._on_step_execute)
            self._step_widgets.append(sw)
            self._content_layout.insertWidget(self._content_layout.count() - 1, sw)

        # Links
        if flow.firmware_url or flow.guide_url:
            links = QLabel(
                f"{'📥  Firmware: ' + flow.firmware_url if flow.firmware_url else ''}"
                f"{'  |  ' if flow.firmware_url and flow.guide_url else ''}"
                f"{'📖  Guide: ' + flow.guide_url if flow.guide_url else ''}"
            )
            links.setWordWrap(True)
            links.setProperty("cssClass", "muted")
            self._content_layout.insertWidget(self._content_layout.count() - 1, links)

    def _on_step_execute(self, step_index: int) -> None:
        """Execute an auto step."""
        if not self._flow:
            return

        step = next((s for s in self._flow.steps if s.index == step_index), None)
        if not step:
            return

        widget = next((w for w in self._step_widgets if w._step.index == step_index), None)
        if not widget:
            return

        device = self._device_mgr.device
        if not device:
            QMessageBox.warning(self, "No device", "No device connected.")
            return

        serial = device.serial

        # Confirm before destructive commands
        if step.warning:
            reply = QMessageBox.warning(
                self,
                f"Step {step.index}: {step.title}",
                f"{step.warning}\n\nCommand: {step.command_preview}\n\nProceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        log.info("Executing unlock step %d: %s", step.index, step.title)

        # Handle mode switching if needed
        if step.requires_mode and device.mode != step.requires_mode:
            log.info("Switching to %s mode for step %d", step.requires_mode, step.index)
            success = self._device_mgr.switch_to_mode(step.requires_mode)
            if not success:
                widget.mark_failed(f"Could not switch to {step.requires_mode} mode.")
                return

        # Execute the command
        success = False
        result_text = ""

        cmd = step.command_preview.lower()
        if "reboot bootloader" in cmd and "adb" in cmd:
            res = self._adb.reboot_bootloader(serial=serial)
            success = res.success
            result_text = "Rebooted to bootloader" if success else res.stderr

        elif "reboot" in cmd and "adb" in cmd:
            res = self._adb.reboot(serial=serial)
            success = res.success
            result_text = "Rebooted" if success else res.stderr

        elif "flashing unlock" in cmd:
            res = self._fb.flashing_unlock(serial=serial)
            success = res.success
            result_text = "Unlock command sent" if success else res.stderr

        elif "oem unlock" in cmd:
            if "<" in cmd:
                code, ok = QInputDialog.getText(
                    self,
                    "Enter Unlock Code",
                    "Enter the unlock code received from the manufacturer website:\n"
                    "(e.g. Motorola or Sony)",
                )
                if not ok or not code.strip():
                    widget.mark_failed("Unlock cancelled: no code provided.")
                    return
                res = self._fb.oem_unlock(code=code.strip(), serial=serial)
            else:
                res = self._fb.oem_unlock(serial=serial)
            success = res.success
            result_text = "OEM unlock command sent" if success else res.stderr

        elif "oem lock" in cmd:
            res = self._fb.oem_lock(serial=serial)
            success = res.success
            result_text = "Lock command sent" if success else res.stderr

        elif "flashing lock" in cmd:
            res = self._fb.flashing_lock(serial=serial)
            success = res.success
            result_text = "Lock command sent" if success else res.stderr

        elif "get_unlock_data" in cmd:
            res = self._fb._run(["oem", "get_unlock_data"], serial=serial, action="oem_get_unlock_data")
            success = res.success
            result_text = res.output if success else res.stderr

        else:
            result_text = f"Unknown command: {step.command_preview}"
            widget.mark_failed(result_text)
            return

        if success:
            widget.mark_completed(result_text)
        else:
            widget.mark_failed(result_text)

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._content_layout.addStretch()
        self._step_widgets = []
        self._flow = None
