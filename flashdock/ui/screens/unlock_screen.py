"""
FlashDock -- Bootloader unlock wizard screen.

Step-by-step guided UI for unlocking (or re-locking) the bootloader,
with brand-specific flows, safety warnings, and dry-run support.

Spec reference: Section 8.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
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
from flashdock.ui.brand_assets import get_brand_badge
from flashdock.ui.icon_assets import create_icon_label, get_icon
from flashdock.ui.widgets.unisoc_unlocker_card import UnisocUnlockerCard

log = get_logger(__name__)

# Import brand modules to trigger registration
import flashdock.brands.google  # noqa: F401
import flashdock.brands.xiaomi  # noqa: F401
import flashdock.brands.samsung  # noqa: F401
import flashdock.brands.transsion  # noqa: F401
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
            warn_frame = QFrame(self)
            warn_frame.setProperty("cssClass", "warn_banner")
            warn_layout = QHBoxLayout(warn_frame)
            warn_layout.setContentsMargins(8, 4, 8, 4)
            warn_layout.setSpacing(6)
            warn_layout.addWidget(create_icon_label("warning", 14, parent=warn_frame))
            warn_label = QLabel(step.warning, warn_frame)
            warn_label.setWordWrap(True)
            warn_layout.addWidget(warn_label, 1)
            layout.addWidget(warn_frame)

        # Action button (for auto steps)
        if step.action == "auto":
            btn_row = QHBoxLayout()
            self._exec_btn = QPushButton("Execute this step", self)
            self._exec_btn.setIcon(get_icon("play", 14))
            self._exec_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._exec_btn.setProperty("cssClass", "primary")
            self._exec_btn.clicked.connect(lambda: self.execute_requested.emit(step.index))
            btn_row.addWidget(self._exec_btn)
            btn_row.addStretch()
            layout.addLayout(btn_row)

        # Result area (hidden until step runs)
        self._result_label = QLabel("", self)
        self._result_label.setWordWrap(True)
        self._result_label.setProperty("cssClass", "success")
        self._result_label.hide()
        layout.addWidget(self._result_label)

    def mark_completed(self, result: str = "") -> None:
        self._step.completed = True
        self._result_label.setText(result or "Completed")
        self._result_label.setProperty("cssClass", "success")
        self._result_label.show()
        if hasattr(self, "_exec_btn"):
            self._exec_btn.setEnabled(False)
            self._exec_btn.setText("Done")

    def mark_failed(self, error: str = "") -> None:
        self._result_label.setText(error or "Failed")
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
        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_h.addWidget(create_icon_label("unlock", 22))
        title = QLabel("Bootloader Unlock Wizard", self)
        title.setProperty("cssClass", "heading")
        title_h.addWidget(title)
        title_h.addStretch(1)
        layout.addLayout(title_h)

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
        """Load the unlock wizard for the detected device, or provide brand selector."""
        self._clear_content()

        if not device or device.mode == "not_connected":
            self._subtitle.setText("No device connected. Select your brand below to view guided unlock instructions or plug in your phone.")

            selector_card = QFrame(self._content)
            selector_card.setProperty("cssClass", "card")
            s_layout = QVBoxLayout(selector_card)
            s_layout.setContentsMargins(18, 16, 18, 16)
            s_layout.setSpacing(12)

            s_title_h = QHBoxLayout()
            s_title_h.setSpacing(8)
            s_title_h.addWidget(create_icon_label("phone", 18, parent=selector_card))
            s_title = QLabel("Browse Bootloader Unlock Guides by Brand", selector_card)
            s_title.setProperty("cssClass", "subheading")
            s_title_h.addWidget(s_title)
            s_title_h.addStretch(1)
            s_layout.addLayout(s_title_h)

            s_desc = QLabel(
                "No phone is currently connected with active USB Debugging. "
                "Select your phone brand below to view official prerequisites, OEM unlocking procedures, "
                "hardware key confirmation steps, and fastboot unlock commands:",
                selector_card,
            )
            s_desc.setWordWrap(True)
            s_desc.setProperty("cssClass", "muted")
            s_layout.addWidget(s_desc)

            brand_row = QHBoxLayout()
            brand_row.setSpacing(10)

            combo = QComboBox(selector_card)
            combo.setMinimumHeight(34)
            brands_list = [
                ("Unisoc / Spreadtrum (1-Click Token Unlock)", "unisoc"),
                ("Tecno Mobile (HiOS)", "tecno"),
                ("Infinix Mobility (XOS)", "infinix"),
                ("itel Mobile (itelOS)", "itel"),
                ("Xiaomi / Redmi / POCO (HyperOS / MIUI)", "xiaomi"),
                ("Google Pixel (Stock Android)", "google"),
                ("Samsung Galaxy (Knox / Download Mode)", "samsung"),
                ("OnePlus (OxygenOS)", "oneplus"),
                ("Motorola (Moto Bootloader)", "motorola"),
                ("Universal / Other Android", "generic"),
            ]
            for label, bid in brands_list:
                combo.addItem(label, bid)

            load_btn = QPushButton("View Unlock Guide", selector_card)
            load_btn.setIcon(get_icon("book", 14))
            load_btn.setProperty("cssClass", "primary")
            load_btn.setMinimumHeight(34)
            load_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            load_btn.clicked.connect(lambda: self._load_manual_brand(combo.currentData()))

            brand_row.addWidget(combo, 1)
            brand_row.addWidget(load_btn)
            s_layout.addLayout(brand_row)

            self._content_layout.insertWidget(0, selector_card)
            return

        # Already unlocked?
        if device.bootloader_state == "unlocked":
            self._subtitle.setText(f"{device.summary_line} -- Bootloader is already UNLOCKED")
            info = QLabel(
                "Your bootloader is already unlocked.\n\n"
                "You can proceed to rooting, flashing ROMs, or other tasks.\n"
                "If you want to RE-LOCK the bootloader, use 'Return to Stock'.",
                self._content,
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
        self._build_flow_ui(is_manual=False)

    def _load_manual_brand(self, brand_id: str) -> None:
        """Load unlock flow for a manually chosen brand without a connected device."""
        mock_device = DeviceInfo(
            serial="MANUAL-SELECTION",
            mode="system",
            brand=brand_id,
            model=f"{brand_id.title()} Device",
            bootloader_state="locked",
        )
        handler = get_handler_for_device(mock_device)
        if not handler:
            from flashdock.brands import get_brand_handler
            handler = get_brand_handler(brand_id) or get_brand_handler("generic")
        if not handler:
            return
        self._clear_content()
        self._flow = handler.get_unlock_flow(mock_device)
        self._subtitle.setText(f"{self._flow.brand_display} Bootloader Guide (Manual Preview)")
        self._build_flow_ui(is_manual=True)

    def _build_flow_ui(self, is_manual: bool = False) -> None:
        """Build the wizard UI from the current flow with brand badge."""
        if not self._flow:
            return

        flow = self._flow

        # Brand Badge Header Card
        brand_card = QFrame()
        brand_card.setProperty("cssClass", "card")
        bc_layout = QHBoxLayout(brand_card)
        bc_layout.setContentsMargins(14, 10, 14, 10)
        bc_layout.setSpacing(14)

        badge_lbl = QLabel()
        badge_pixmap = get_brand_badge(flow.brand_display, width=130, height=36)
        badge_lbl.setPixmap(badge_pixmap)
        bc_layout.addWidget(badge_lbl)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        bc_title = QLabel(f"{flow.brand_display} Bootloader Architecture")
        bc_title.setStyleSheet("font-weight: 600; font-size: 14px;")
        info_col.addWidget(bc_title)
        bc_sub = QLabel(
            "Follow each step carefully. Automated buttons require a connected device in Fastboot mode."
            if is_manual
            else "Guided unlock flow prepared for your connected device."
        )
        bc_sub.setProperty("cssClass", "muted")
        info_col.addWidget(bc_sub)
        bc_layout.addLayout(info_col, 1)

        if is_manual:
            back_btn = QPushButton("Change Brand", brand_card)
            back_btn.setIcon(get_icon("refresh", 14))
            back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            back_btn.clicked.connect(lambda: self.load_for_device(None))
            bc_layout.addWidget(back_btn)

        self._content_layout.insertWidget(self._content_layout.count() - 1, brand_card)

        # Warnings banner
        if flow.warnings:
            warn_card = QFrame(self._content)
            warn_card.setProperty("cssClass", "danger_banner")
            w_layout = QHBoxLayout(warn_card)
            w_layout.setContentsMargins(10, 8, 10, 8)
            w_layout.setSpacing(8)
            w_layout.addWidget(create_icon_label("warning", 18, parent=warn_card))
            warn_text = "\n".join(f"  - {w}" for w in flow.warnings)
            w_lbl = QLabel(f"IMPORTANT WARNINGS:\n{warn_text}", warn_card)
            w_lbl.setWordWrap(True)
            w_layout.addWidget(w_lbl, 1)
            self._content_layout.insertWidget(self._content_layout.count() - 1, warn_card)

        # Prerequisites
        if flow.prerequisites:
            prereq_frame = QFrame(self._content)
            prereq_frame.setProperty("cssClass", "card")
            prereq_layout = QVBoxLayout(prereq_frame)
            prereq_layout.setContentsMargins(12, 8, 12, 8)
            prereq_layout.setSpacing(6)

            pt_h = QHBoxLayout()
            pt_h.setSpacing(6)
            pt_h.addWidget(create_icon_label("checklist", 16, parent=prereq_frame))
            prereq_title = QLabel("Prerequisites", prereq_frame)
            prereq_title.setProperty("cssClass", "subheading")
            pt_h.addWidget(prereq_title)
            pt_h.addStretch(1)
            prereq_layout.addLayout(pt_h)

            for p in flow.prerequisites:
                item = QLabel(f"  - {p}", prereq_frame)
                item.setWordWrap(True)
                item.setProperty("cssClass", "muted")
                prereq_layout.addWidget(item)
            self._content_layout.insertWidget(self._content_layout.count() - 1, prereq_frame)

        # Data wipe warning
        if flow.wipes_data:
            wipe_card = QFrame(self._content)
            wipe_card.setProperty("cssClass", "warn_banner")
            wp_layout = QHBoxLayout(wipe_card)
            wp_layout.setContentsMargins(10, 8, 10, 8)
            wp_layout.setSpacing(8)
            wp_layout.addWidget(create_icon_label("trash", 18, parent=wipe_card))
            wipe_lbl = QLabel(
                "THIS PROCESS WILL ERASE ALL DATA ON YOUR PHONE.\nBack up everything before proceeding.",
                wipe_card,
            )
            wipe_lbl.setWordWrap(True)
            wp_layout.addWidget(wipe_lbl, 1)
            self._content_layout.insertWidget(self._content_layout.count() - 1, wipe_card)

        # Waiting period notice
        if flow.waiting_period:
            wait_card = QFrame(self._content)
            wait_card.setProperty("cssClass", "info_banner")
            wt_layout = QHBoxLayout(wait_card)
            wt_layout.setContentsMargins(10, 8, 10, 8)
            wt_layout.setSpacing(8)
            wt_layout.addWidget(create_icon_label("info", 16, parent=wait_card))
            wait_lbl = QLabel(f"Waiting period required: {flow.waiting_period}", wait_card)
            wt_layout.addWidget(wait_lbl, 1)
            self._content_layout.insertWidget(self._content_layout.count() - 1, wait_card)

        # Unisoc & Transsion 1-Click Unlocker Card
        if getattr(flow, "brand", "") in ("unisoc", "spreadtrum", "infinix", "tecno", "itel") or any(
            k in getattr(flow, "brand_display", "").lower() for k in ("unisoc", "spreadtrum", "infinix", "tecno", "itel")
        ):
            self._unisoc_card = UnisocUnlockerCard(self._content)
            self._unisoc_card.unlock_dispatched.connect(self._on_unisoc_unlock_dispatched)
            self._content_layout.insertWidget(self._content_layout.count() - 1, self._unisoc_card)

        # Steps
        steps_title = QLabel(f"Steps ({len(flow.steps)} total)", self._content)
        steps_title.setProperty("cssClass", "subheading")
        self._content_layout.insertWidget(self._content_layout.count() - 1, steps_title)

        self._step_widgets = []
        for step in flow.steps:
            sw = _StepWidget(step, parent=self._content)
            sw.execute_requested.connect(self._on_step_execute)
            self._step_widgets.append(sw)
            self._content_layout.insertWidget(self._content_layout.count() - 1, sw)

        # Links
        if flow.firmware_url or flow.guide_url:
            links = QLabel(
                f"{'Firmware: ' + flow.firmware_url if flow.firmware_url else ''}"
                f"{'  |  ' if flow.firmware_url and flow.guide_url else ''}"
                f"{'Guide: ' + flow.guide_url if flow.guide_url else ''}",
                self._content,
            )
            links.setWordWrap(True)
            links.setProperty("cssClass", "muted")
            self._content_layout.insertWidget(self._content_layout.count() - 1, links)

    def _on_unisoc_unlock_dispatched(self, token: str, sig_path: str) -> None:
        """Handle 1-click unlock dispatch from UnisocUnlockerCard."""
        device = self._device_mgr.device
        if device and device.mode == "fastboot" and getattr(device, "serial", ""):
            reply = QMessageBox.question(
                self,
                "Flash Unisoc Unlock Signature",
                f"Generated unlock signature ({Path(sig_path).name}).\n\n"
                f"Device {device.serial} is currently in Fastboot mode.\n"
                "Flash signature and unlock bootloader now?\n\n"
                "WARNING: This will wipe all user data on the device!",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                from flashdock.core.unisoc import UnisocUnlockManager
                res = UnisocUnlockManager.unlock_bootloader(self._fb, Path(sig_path), serial=device.serial)
                if res.success:
                    QMessageBox.information(self, "Bootloader Unlocked", "Unisoc bootloader unlock command succeeded!")
                else:
                    QMessageBox.warning(self, "Unlock Failed", f"fastboot flashing unlock_bootloader failed:\n\n{res.stderr}")
        else:
            QMessageBox.information(
                self,
                "Signature Ready",
                f"Unlock signature saved to:\n{sig_path}\n\n"
                "To finish unlocking, put your phone into Fastboot mode and run:\n"
                f"fastboot flashing unlock_bootloader {Path(sig_path).name}",
            )

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
        if not device or device.mode == "not_connected" or getattr(device, "serial", "") == "MANUAL-SELECTION":
            QMessageBox.information(
                self,
                "Device Required",
                f"Automated step execution requires a connected physical phone in "
                f"{step.requires_mode.title() if step.requires_mode else 'Fastboot'} mode.\n\n"
                "Please connect your device with USB Debugging enabled to execute this command."
            )
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

        elif "unlock_critical" in cmd:
            res = self._fb.flashing_unlock_critical(serial=serial)
            success = res.success
            result_text = "Unlock critical command sent" if success else res.stderr

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

        elif "get_identifier_token" in cmd:
            from flashdock.core.unisoc import UnisocUnlockManager
            ok, token, raw = UnisocUnlockManager.query_identifier_token(self._fb, serial=serial)
            success = ok
            if ok:
                ok_s, sig_file, msg = UnisocUnlockManager.sign_token(token)
                result_text = f"Unisoc Token extracted ({token[:16]}...) & signed -> {sig_file.name}"
            else:
                result_text = raw or "Failed to query Unisoc identifier token"

        elif "unlock_bootloader" in cmd:
            from flashdock.core.unisoc import UnisocUnlockManager
            from flashdock.constants import CACHE_DIR
            sig_file = CACHE_DIR / "signature.bin"
            if not sig_file.is_file():
                ok, token, raw = UnisocUnlockManager.query_identifier_token(self._fb, serial=serial)
                if ok:
                    UnisocUnlockManager.sign_token(token, output_path=sig_file)
            res = UnisocUnlockManager.unlock_bootloader(self._fb, sig_file, serial=serial)
            success = res.success
            result_text = "Unisoc bootloader unlocked successfully" if success else res.stderr

        elif "vbmeta" in cmd and ("disable" in cmd or "flash" in cmd):
            from flashdock.core.unisoc import UnisocUnlockManager
            res = UnisocUnlockManager.flash_disabled_vbmeta(self._fb, serial=serial)
            success = res.success
            result_text = "Flashed disabled vbmeta (Anti-Red State Active)" if success else res.stderr

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
