"""
FlashDock — Return to Stock & Safe Bootloader Relock Screen.

Guided workflow to restore stock factory firmware and safely relock bootloader:
1. Factory Firmware Selector (directories, ZIP archives, Pixel factory images).
2. Package inspection & compatibility check with connected phone.
3. OEM-compliant partition flash ordering with dynamic slot & wipe controls.
4. Flashing execution protected by FlashShield modal guard.
5. Strict Anti-Relock Gate: boots safe relock only after 100% verified flash,
   blocking cross-region ROMs and unsafe devices from hard-bricking.
6. In-depth anti-brick guides & recovery instructions.

Spec references: Section 14, Section 16, Section 21.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import CONFIRMATION_WORD
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.return_stock import (
    RELOCK_CONFIRMATION_WORD,
    RelockCheckResult,
    ReturnStockEngine,
    ReturnStockResult,
    StockFlashOptions,
    StockPackageInfo,
)
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.icon_assets import create_icon_label, get_icon
from flashdock.ui.widgets.flash_shield import FlashShieldDialog

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Background Worker for Flashing
# ---------------------------------------------------------------------------

class ReturnStockWorker(QThread):
    """Executes firmware flashing in a background thread."""

    progress_signal = Signal(int, int, str, str, str)  # current, total, partition, status, message
    finished_signal = Signal(object)  # ReturnStockResult

    def __init__(
        self,
        engine: ReturnStockEngine,
        device: DeviceInfo,
        package: StockPackageInfo,
        options: StockFlashOptions,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._engine = engine
        self._device = device
        self._package = package
        self._options = options
        self._is_cancelled = False

    def cancel(self) -> None:
        self.requestInterruption()
        self._is_cancelled = True

    def run(self) -> None:
        def _cb(curr: int, tot: int, part: str, st: str, msg: str) -> None:
            self.progress_signal.emit(curr, tot, part, st, msg)

        def _cancel_check() -> bool:
            return self._is_cancelled or self.isInterruptionRequested()

        res = self._engine.flash_stock(
            device=self._device,
            package=self._package,
            options=self._options,
            progress_callback=_cb,
            cancel_requested=_cancel_check,
        )
        self.finished_signal.emit(res)


# ---------------------------------------------------------------------------
# Relock Confirmation Dialog
# ---------------------------------------------------------------------------

class RelockConfirmationDialog(QDialog):
    """Guarded modal dialog for typed bootloader relocking confirmation."""

    def __init__(
        self,
        device: DeviceInfo,
        command: str,
        warnings: list[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device = device
        self._command = command
        self._warnings = warnings

        self.setWindowTitle("Relock Bootloader Confirmation")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Danger Banner
        # Danger Banner
        banner = QFrame()
        banner.setProperty("cssClass", "danger_banner")
        b_lay = QVBoxLayout(banner)
        b_lay.setSpacing(6)
        b_title_row = QHBoxLayout()
        b_title_row.setSpacing(8)
        b_title_row.addWidget(create_icon_label("warning", 18))
        b_title = QLabel("EXTREME CAUTION: Bootloader Relock")
        b_title.setProperty("cssClass", "error")
        b_title_row.addWidget(b_title)
        b_title_row.addStretch()
        b_lay.addLayout(b_title_row)

        b_desc = QLabel(
            "Relocking the bootloader will restore full hardware verification. "
            "If your partitions contain any unofficial modifications, custom recovery, or cross-region ROMs, "
            "this will PERMANENTLY BRICK YOUR PHONE into an unbootable state."
        )
        b_desc.setWordWrap(True)
        b_desc.setProperty("cssClass", "error")
        b_lay.addWidget(b_desc)
        layout.addWidget(banner)

        # Phone action explanation
        info_label = QLabel(
            "<b>What happens next on your phone:</b><br>"
            "1. FlashDock will send the relock command to fastboot.<br>"
            "2. Your phone screen will display a prompt: <i>'Lock the bootloader?'</i><br>"
            "3. Use the <b>Volume buttons</b> to highlight <b>'LOCK THE BOOTLOADER'</b> and press <b>Power</b> to confirm.<br>"
            "4. Your phone will wipe user data and reboot to stock system."
        )
        info_label.setWordWrap(True)
        info_label.setProperty("cssClass", "card")
        layout.addWidget(info_label)

        if self._warnings:
            w_text = "\n".join(f"• {w}" for w in self._warnings)
            w_label = QLabel(f"<b>Notices:</b>\n{w_text}")
            w_label.setWordWrap(True)
            w_label.setProperty("cssClass", "warning")
            layout.addWidget(w_label)

        # Input confirmation
        prompt_label = QLabel(
            f"Type <b>{RELOCK_CONFIRMATION_WORD}</b> in all caps to confirm bootloader relock:"
        )
        prompt_label.setProperty("cssClass", "subheading")
        layout.addWidget(prompt_label)

        self._input = QLineEdit()
        self._input.setPlaceholderText(f"Type {RELOCK_CONFIRMATION_WORD} here")
        self._input.textChanged.connect(self._validate_input)
        layout.addWidget(self._input)

        # Buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("cssClass", "secondary")
        self._cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self._cancel_btn)

        self._confirm_btn = QPushButton("Relock Bootloader Now")
        self._confirm_btn.setIcon(get_icon("lock", 16))
        self._confirm_btn.setEnabled(False)
        self._confirm_btn.setProperty("cssClass", "danger")
        self._confirm_btn.clicked.connect(self.accept)
        btn_box.addWidget(self._confirm_btn)

        layout.addLayout(btn_box)

    def _validate_input(self, text: str) -> None:
        self._confirm_btn.setEnabled(text.strip() == RELOCK_CONFIRMATION_WORD)


# ---------------------------------------------------------------------------
# Main Return to Stock Screen
# ---------------------------------------------------------------------------

class ReturnStockScreen(QWidget):
    """The Return to Stock & Bootloader Relock screen."""

    def __init__(
        self,
        device_mgr: DeviceManager,
        adb: ADB,
        fastboot: Fastboot,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb
        self._fb = fastboot
        self._engine = ReturnStockEngine(fastboot=self._fb)

        self._current_device: Optional[DeviceInfo] = None
        self._current_pkg: Optional[StockPackageInfo] = None
        self._last_flash_result: Optional[ReturnStockResult] = None
        self._worker: Optional[ReturnStockWorker] = None
        self._shield: Optional[FlashShieldDialog] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Header
        t_box = QHBoxLayout()
        t_box.setSpacing(10)
        t_box.addWidget(create_icon_label("return_stock", 22))
        title = QLabel("Return to Stock & Safe Bootloader Relock")
        title.setProperty("cssClass", "heading")
        t_box.addWidget(title)
        t_box.addStretch()
        layout.addLayout(t_box)

        self._subtitle = QLabel(
            "Restore pure OEM factory firmware, wipe custom modifications, and safely relock bootloader."
        )
        self._subtitle.setProperty("cssClass", "muted")
        layout.addWidget(self._subtitle)

        # Tab Widget
        self._tabs = QTabWidget()

        self._tab_flash = QWidget()
        self._tab_relock = QWidget()
        self._tab_guide = QWidget()

        self._setup_flash_tab()
        self._setup_relock_tab()
        self._setup_guide_tab()

        self._tabs.addTab(self._tab_flash, get_icon("flash", 16), "Restore Factory Firmware")
        self._tabs.addTab(self._tab_relock, get_icon("lock", 16), "Safe Bootloader Relock")
        self._tabs.addTab(self._tab_guide, get_icon("book", 16), "Stock Guides & Recovery")

        layout.addWidget(self._tabs, 1)

    # -----------------------------------------------------------------------
    # Tab 1: Restore Factory Firmware
    # -----------------------------------------------------------------------

    def _setup_flash_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 1. Device Status Card
        dev_card = QFrame()
        dev_card.setProperty("cssClass", "card")
        d_lay = QHBoxLayout(dev_card)

        info_col = QVBoxLayout()
        info_col.setSpacing(4)
        self._dev_title_label = QLabel("No device connected")
        self._dev_title_label.setProperty("cssClass", "subheading")
        info_col.addWidget(self._dev_title_label)

        self._dev_detail_label = QLabel("Connect an Android phone via USB to begin.")
        self._dev_detail_label.setProperty("cssClass", "muted")
        info_col.addWidget(self._dev_detail_label)
        d_lay.addLayout(info_col, 1)

        self._reboot_fb_btn = QPushButton("Reboot to Fastboot")
        self._reboot_fb_btn.setIcon(get_icon("refresh", 16))
        self._reboot_fb_btn.setEnabled(False)
        self._reboot_fb_btn.setProperty("cssClass", "secondary")
        self._reboot_fb_btn.clicked.connect(self._reboot_to_fastboot)
        d_lay.addWidget(self._reboot_fb_btn)

        layout.addWidget(dev_card)

        # 2. Package Selector
        pkg_group = QGroupBox("1. Stock Firmware Package")
        pkg_lay = QVBoxLayout(pkg_group)
        pkg_lay.setSpacing(10)

        path_row = QHBoxLayout()
        self._pkg_path_edit = QLineEdit()
        self._pkg_path_edit.setPlaceholderText("Select factory image directory or ZIP archive...")
        self._pkg_path_edit.setClearButtonEnabled(True)
        path_row.addWidget(self._pkg_path_edit, 1)

        browse_dir_btn = QPushButton("Browse Folder")
        browse_dir_btn.setIcon(get_icon("folder", 16))
        browse_dir_btn.setProperty("cssClass", "secondary")
        browse_dir_btn.clicked.connect(self._browse_folder)
        path_row.addWidget(browse_dir_btn)

        browse_zip_btn = QPushButton("Browse ZIP")
        browse_zip_btn.setIcon(get_icon("folder", 16))
        browse_zip_btn.setProperty("cssClass", "secondary")
        browse_zip_btn.clicked.connect(self._browse_zip)
        path_row.addWidget(browse_zip_btn)

        pkg_lay.addLayout(path_row)

        # Package Summary Card
        self._pkg_summary_card = QFrame()
        self._pkg_summary_card.setProperty("cssClass", "card_subtle")
        sum_lay = QVBoxLayout(self._pkg_summary_card)
        sum_lay.setSpacing(6)

        self._pkg_summary_title = QLabel("No package loaded.")
        self._pkg_summary_title.setProperty("cssClass", "muted")
        sum_lay.addWidget(self._pkg_summary_title)

        # Table of partition images
        self._part_table = QTableWidget(0, 3)
        self._part_table.setHorizontalHeaderLabels(["Partition", "Image File / Source", "Size"])
        self._part_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._part_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._part_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._part_table.setMaximumHeight(140)
        self._part_table.setAlternatingRowColors(True)
        self._part_table.setVisible(False)
        sum_lay.addWidget(self._part_table)

        pkg_lay.addWidget(self._pkg_summary_card)
        layout.addWidget(pkg_group)

        # 3. Flashing Options
        opt_group = QGroupBox("2. Flashing Options")
        opt_lay = QVBoxLayout(opt_group)
        opt_lay.setSpacing(8)

        slot_row = QHBoxLayout()
        slot_label = QLabel("Target Slot:")
        slot_label.setProperty("cssClass", "muted")
        slot_row.addWidget(slot_label)

        self._slot_combo = QComboBox()
        self._slot_combo.addItems([
            "Active Slot (Recommended)",
            "Slot A",
            "Slot B",
            "Both Slots (Complete A/B restore)",
        ])
        slot_row.addWidget(self._slot_combo)
        slot_row.addStretch()
        opt_lay.addLayout(slot_row)

        self._wipe_cb = QCheckBox("Wipe user data (Recommended: prevents bootloops from leftover app data)")
        self._wipe_cb.setChecked(True)
        opt_lay.addWidget(self._wipe_cb)

        self._dry_run_cb = QCheckBox("Dry-run mode (Simulate flash commands without modifying device)")
        opt_lay.addWidget(self._dry_run_cb)

        self._reboot_cb = QCheckBox("Auto reboot to system when complete")
        self._reboot_cb.setChecked(False)
        opt_lay.addWidget(self._reboot_cb)

        layout.addWidget(opt_group)

        # 4. Action Bar & Console
        action_row = QHBoxLayout()
        self._flash_btn = QPushButton("Flash Stock Firmware")
        self._flash_btn.setIcon(get_icon("flash", 16))
        self._flash_btn.setEnabled(False)
        self._flash_btn.setMinimumHeight(44)
        self._flash_btn.setProperty("cssClass", "primary")
        self._flash_btn.clicked.connect(self._start_flash)
        action_row.addWidget(self._flash_btn, 1)

        layout.addLayout(action_row)

        # Progress bar
        self._prog_bar = QProgressBar()
        self._prog_bar.setRange(0, 100)
        self._prog_bar.setValue(0)
        self._prog_bar.setTextVisible(True)
        self._prog_bar.setVisible(False)
        layout.addWidget(self._prog_bar)

        # Live Console
        console_label = QLabel("Console Output:")
        console_label.setProperty("cssClass", "muted")
        layout.addWidget(console_label)

        self._console_edit = QTextEdit()
        self._console_edit.setReadOnly(True)
        self._console_edit.setMinimumHeight(120)
        self._console_edit.setProperty("cssClass", "code_box")
        layout.addWidget(self._console_edit)

        scroll.setWidget(content)
        self._tab_flash.setLayout(QVBoxLayout())
        self._tab_flash.layout().addWidget(scroll)

    # -----------------------------------------------------------------------
    # Tab 2: Safe Bootloader Relock
    # -----------------------------------------------------------------------

    def _setup_relock_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Gate Status Card
        self._gate_card = QFrame()
        self._gate_card.setProperty("cssClass", "danger_banner")
        g_lay = QVBoxLayout(self._gate_card)
        g_lay.setSpacing(8)

        self._gate_status_label = QLabel("Relock Gate: PROHIBITED")
        self._gate_status_label.setProperty("cssClass", "error")
        g_lay.addWidget(self._gate_status_label)

        self._gate_reason_label = QLabel(
            "Relocking is locked until 100% clean stock firmware has been successfully flashed in this session."
        )
        self._gate_reason_label.setWordWrap(True)
        self._gate_reason_label.setProperty("cssClass", "error")
        g_lay.addWidget(self._gate_reason_label)

        layout.addWidget(self._gate_card)

        # Danger explanation
        rules_box = QGroupBox("Anti-Brick Relocking Safety Rules")
        r_lay = QVBoxLayout(rules_box)
        r_lay.setSpacing(8)

        r1 = QLabel("<b>Never relock with modified partitions:</b> Root kernels, TWRP, or custom ROMs will fail Android Verified Boot (AVB) signature checks upon relock, causing an unbootable bootloop or EDL brick.")
        r1.setWordWrap(True)
        r_lay.addWidget(r1)

        r2 = QLabel("<b>Xiaomi Cross-Region Hazard:</b> Relocking a Chinese phone running Global/EEA ROM results in instant brick ('This MIUI version can\\'t be installed on this device'). Only relock with ROM matching hardware region.")
        r2.setWordWrap(True)
        r2.setProperty("cssClass", "error")
        r_lay.addWidget(r2)

        r3 = QLabel("<b>Samsung Knox Warning:</b> Samsung Knox status is a physical hardware e-fuse. Relocking does NOT restore Knox or Samsung Pay.")
        r3.setWordWrap(True)
        r3.setProperty("cssClass", "warning")
        r_lay.addWidget(r3)

        rules_box.setLayout(r_lay)
        layout.addWidget(rules_box)

        # Relock Execution Section
        exec_box = QGroupBox("Relock Command Execution")
        e_lay = QVBoxLayout(exec_box)
        e_lay.setSpacing(10)

        self._relock_cmd_label = QLabel("Recommended command: fastboot flashing lock")
        self._relock_cmd_label.setProperty("cssClass", "code_text")
        e_lay.addWidget(self._relock_cmd_label)

        self._relock_btn = QPushButton("Relock Bootloader")
        self._relock_btn.setIcon(get_icon("lock", 16))
        self._relock_btn.setEnabled(False)
        self._relock_btn.setMinimumHeight(42)
        self._relock_btn.setProperty("cssClass", "danger")
        self._relock_btn.clicked.connect(self._prompt_relock)
        e_lay.addWidget(self._relock_btn)

        layout.addWidget(exec_box)
        layout.addStretch()

        scroll.setWidget(content)
        self._tab_relock.setLayout(QVBoxLayout())
        self._tab_relock.layout().addWidget(scroll)

    # -----------------------------------------------------------------------
    # Tab 3: Stock Guides & Recovery
    # -----------------------------------------------------------------------

    def _setup_guide_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        guide_text = QLabel(
            "<h2>Returning to Stock & OEM Firmware Guide</h2>"
            "<p>Returning to pure factory firmware is the safest way to restore your device to factory state, "
            "receive official Over-The-Air (OTA) updates, and pass hardware integrity checks.</p>"
            "<h3>1. Where to download authentic factory images:</h3>"
            "<ul>"
            "  <li><b>Google Pixel:</b> Official Google Developers factory images (download the 'Factory Image' .zip, not OTA zip).</li>"
            "  <li><b>Xiaomi / Redmi / POCO:</b> Official Fastboot ROM (tgz archive containing flash_all.bat and images/ directory).</li>"
            "  <li><b>OnePlus:</b> Official OxygenOS fastboot / rollback package or extracted payload.bin.</li>"
            "  <li><b>Motorola:</b> Motorola Rescue and Smart Assistant (RSA) downloads official stock images.</li>"
            "  <li><b>Samsung:</b> Official SamFirm / Frija tools for Odin 4-file packages (AP, BL, CP, CSC).</li>"
            "</ul>"
            "<h3>2. Why partition order matters:</h3>"
            "<p>Flashing partitions in the wrong order can cause the device to reboot into an unbootable state mid-flash. "
            "FlashDock uses strict OEM order: <code>bootloader ➔ radio ➔ boot/init_boot ➔ dtbo ➔ recovery ➔ vbmeta ➔ super/system</code>.</p>"
            "<h3>3. How to fix a soft-bricked device:</h3>"
            "<ol>"
            "  <li>Hold <b>Volume Down + Power</b> to force boot into Fastboot mode.</li>"
            "  <li>Connect USB to PC and verify FlashDock detects device in 'bootloader' mode.</li>"
            "  <li>Select your matching factory package and click <b>'Flash Stock Firmware'</b>.</li>"
            "</ol>"
        )
        guide_text.setWordWrap(True)
        guide_text.setProperty("cssClass", "card")
        layout.addWidget(guide_text)
        layout.addStretch()

        scroll.setWidget(content)
        self._tab_guide.setLayout(QVBoxLayout())
        self._tab_guide.layout().addWidget(scroll)

    # -----------------------------------------------------------------------
    # Public device loader
    # -----------------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Update screen for the currently connected device."""
        self._current_device = device

        if not device or device.mode == "not_connected":
            self._dev_title_label.setText("No device connected")
            self._dev_detail_label.setText("Connect your phone via USB with USB debugging or in Fastboot.")
            self._reboot_fb_btn.setEnabled(False)
            self._flash_btn.setEnabled(False)
            self._update_relock_gate()
            return

        mode_badge = f"[{device.mode.upper()}]"
        name = device.model or device.device or device.serial
        brand = device.brand.title() if device.brand else "Android"
        self._dev_title_label.setText(f"{brand} {name} {mode_badge}")

        details = []
        if device.device:
            details.append(f"Codename: {device.device}")
        if getattr(device, "active_slot", ""):
            details.append(f"Slot: {device.active_slot}")
        if device.battery_level is not None and device.battery_level >= 0:
            details.append(f"Battery: {device.battery_level}%")
        self._dev_detail_label.setText(" | ".join(details) or f"Serial: {device.serial}")

        # Enable reboot to fastboot if in system mode
        self._reboot_fb_btn.setEnabled(device.mode == "system")

        # Re-evaluate firmware compatibility if package is loaded
        self._validate_package_compatibility()
        self._update_relock_gate()

    # -----------------------------------------------------------------------
    # Package browse & validation
    # -----------------------------------------------------------------------

    def _browse_folder(self) -> None:
        dir_path = QFileDialog.getExistingDirectory(self, "Select Stock Firmware Directory")
        if dir_path:
            self._load_package(Path(dir_path))

    def _browse_zip(self) -> None:
        zip_path, _ = QFileDialog.getOpenFileName(
            self, "Select Stock Firmware ZIP", "", "ZIP Archives (*.zip)"
        )
        if zip_path:
            self._load_package(Path(zip_path))

    def _load_package(self, path: Path) -> None:
        self._pkg_path_edit.setText(str(path))
        self._console_edit.append(f"Inspecting stock firmware: {path.name}...")

        pkg = self._engine.parse_stock_package(path)
        self._current_pkg = pkg

        # Update package summary UI
        if not pkg.is_valid:
            err = "; ".join(pkg.errors)
            self._pkg_summary_title.setText(f"Invalid package: {err}")
            self._pkg_summary_title.setProperty("cssClass", "error")
            self._part_table.setVisible(False)
            self._flash_btn.setEnabled(False)
            return

        sum_text = (
            f"<b>Valid Factory Package:</b> {pkg.partition_count} partitions detected "
            f"({pkg.total_size_mb} MB total)"
        )
        if pkg.target_codename:
            sum_text += f" | Target codename: <b>{pkg.target_codename}</b>"
        if pkg.build_id:
            sum_text += f" | Build: {pkg.build_id}"

        self._pkg_summary_title.setText(sum_text)
        self._pkg_summary_title.setProperty("cssClass", "success")

        # Populate partition table
        ordered = self._engine.get_flash_order(pkg.images)
        self._part_table.setRowCount(len(ordered))
        for row, part in enumerate(ordered):
            img = pkg.images[part]
            self._part_table.setItem(row, 0, QTableWidgetItem(part))
            src_text = f"Archive: {img.archive_inner_path}" if img.in_archive else img.file_path.name
            self._part_table.setItem(row, 1, QTableWidgetItem(src_text))
            self._part_table.setItem(row, 2, QTableWidgetItem(f"{img.size_mb} MB"))

        self._part_table.setVisible(True)
        self._validate_package_compatibility()

    def _validate_package_compatibility(self) -> None:
        """Check compatibility between loaded package and current device."""
        if not self._current_pkg or not self._current_pkg.is_valid:
            self._flash_btn.setEnabled(False)
            return

        if not self._current_device or self._current_device.mode == "not_connected":
            self._flash_btn.setEnabled(False)
            return

        res = self._engine.check_firmware_compatibility(self._current_device, self._current_pkg)
        if res.is_blocked:
            self._console_edit.append(f"Compatibility warning: {res.message}")
            self._flash_btn.setEnabled(False)
        else:
            self._console_edit.append(f"Firmware verified compatible with {self._current_device.model or self._current_device.device}.")
            self._flash_btn.setEnabled(True)

    # -----------------------------------------------------------------------
    # Relock Gate Evaluation
    # -----------------------------------------------------------------------

    def _update_relock_gate(self) -> None:
        """Check relock safety and update tab 2 gate card and button."""
        res = self._engine.check_relock_safety(
            device=self._current_device,
            flash_result=self._last_flash_result,
        )
        self._relock_cmd_label.setText(f"Recommended command: {res.recommended_command}")

        if res.can_relock:
            self._gate_card.setProperty("cssClass", "card")
            self._gate_status_label.setText("Relock Gate: READY TO RELOCK")
            self._gate_status_label.setProperty("cssClass", "success")
            self._gate_reason_label.setText(
                "Pure stock partitions were successfully flashed. You can safely relock your bootloader."
            )
            self._gate_reason_label.setProperty("cssClass", "muted")
            self._relock_btn.setEnabled(True)
        else:
            self._gate_card.setProperty("cssClass", "danger_banner")
            self._gate_status_label.setText("Relock Gate: PROHIBITED")
            self._gate_status_label.setProperty("cssClass", "error")
            self._gate_reason_label.setText(
                " • " + "\n • ".join(res.reasons) if res.reasons else "Relocking conditions not met."
            )
            self._gate_reason_label.setProperty("cssClass", "error")
            self._relock_btn.setEnabled(False)

    # -----------------------------------------------------------------------
    # Actions & Execution
    # -----------------------------------------------------------------------

    @Slot()
    def _reboot_to_fastboot(self) -> None:
        if not self._current_device:
            return
        serial = self._current_device.serial
        self._console_edit.append(f"Rebooting device {serial} to bootloader...")
        res = self._adb.reboot(target="bootloader", serial=serial)
        if res.success:
            self._console_edit.append("Command sent. Waiting for fastboot...")
            QMessageBox.information(
                self, "Rebooting", "Device is rebooting into Bootloader mode. Please wait."
            )
        else:
            QMessageBox.warning(self, "Reboot failed", f"Could not reboot: {res.stderr}")

    @Slot()
    def _start_flash(self) -> None:
        if not self._current_pkg or not self._current_device:
            return

        dry_run = self._dry_run_cb.isChecked()

        # Typed confirmation if NOT dry run
        if not dry_run:
            typed, ok = self._prompt_typed_confirmation()
            if not ok or typed != CONFIRMATION_WORD:
                QMessageBox.warning(
                    self,
                    "Flashing Aborted",
                    f"You must type '{CONFIRMATION_WORD}' in all caps to confirm destructive flashing.",
                )
                return

        # Prepare options
        slot_text = self._slot_combo.currentText()
        target_slot = ""
        if "Slot A" in slot_text:
            target_slot = "a"
        elif "Slot B" in slot_text:
            target_slot = "b"
        elif "Both Slots" in slot_text:
            target_slot = "both"

        options = StockFlashOptions(
            target_slot=target_slot,
            wipe_data=self._wipe_cb.isChecked(),
            dry_run=dry_run,
            auto_reboot=self._reboot_cb.isChecked(),
        )

        # Show FlashShield modal lock
        self._shield = FlashShieldDialog(self)
        self._shield.set_title("Restoring Stock Firmware")
        self._shield.set_status("Preparing partitions...")
        self._shield.set_progress(0)

        # Start worker
        self._worker = ReturnStockWorker(
            engine=self._engine,
            device=self._current_device,
            package=self._current_pkg,
            options=options,
            parent=self,
        )
        self._worker.progress_signal.connect(self._on_flash_progress)
        self._worker.finished_signal.connect(self._on_flash_finished)
        self._worker.start()

        self._prog_bar.setVisible(True)
        self._prog_bar.setValue(0)
        self._shield.exec()

    def _prompt_typed_confirmation(self) -> tuple[str, bool]:
        dlg = QDialog(self)
        dlg.setWindowTitle("Confirm Return to Stock Flashing")
        dlg.setModal(True)
        dlg.setMinimumWidth(440)
        lay = QVBoxLayout(dlg)
        lay.setSpacing(12)

        msg = QLabel(
            "<b>Destructive Operation Warning</b><br>"
            "Flashing factory firmware will overwrite existing OS partitions. "
            "If 'Wipe user data' is checked, all apps, photos, and files will be permanently erased.<br><br>"
            f"To proceed, please type <b>{CONFIRMATION_WORD}</b> below:"
        )
        msg.setWordWrap(True)
        msg.setProperty("cssClass", "secondary")
        lay.addWidget(msg)

        input_box = QLineEdit()
        input_box.setPlaceholderText(f"Type {CONFIRMATION_WORD}")
        lay.addWidget(input_box)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        c_btn = QPushButton("Cancel")
        c_btn.setProperty("cssClass", "secondary")
        c_btn.clicked.connect(dlg.reject)
        btn_row.addWidget(c_btn)

        ok_btn = QPushButton("Proceed with Flashing")
        ok_btn.setProperty("cssClass", "primary")
        ok_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(ok_btn)

        lay.addLayout(btn_row)

        res = dlg.exec()
        return input_box.text().strip(), res == QDialog.DialogCode.Accepted

    @Slot(int, int, str, str, str)
    def _on_flash_progress(self, curr: int, tot: int, part: str, status: str, msg: str) -> None:
        pct = int((curr / max(1, tot)) * 100)
        self._prog_bar.setValue(pct)
        log_line = f"[{curr}/{tot}] {part}: {status.upper()} — {msg}"
        self._console_edit.append(log_line)

        if self._shield:
            self._shield.set_progress(pct)
            self._shield.set_status(f"Step {curr}/{tot}: Flashing {part}...")
            self._shield.append_log(log_line)

    @Slot(object)
    def _on_flash_finished(self, result: ReturnStockResult) -> None:
        self._last_flash_result = result
        self._prog_bar.setValue(100 if result.success else self._prog_bar.value())

        if result.success:
            self._console_edit.append(
                f"Return-to-Stock completed successfully! ({result.successful_steps} steps succeeded)"
            )
            if self._shield:
                self._shield.finish(True, "All factory partitions flashed successfully!")
        else:
            self._console_edit.append(
                f"Return-to-Stock failed: {result.error_message}"
            )
            if self._shield:
                self._shield.finish(False, f"Flashing failed: {result.error_message}")

        # Update relock gate based on result
        self._update_relock_gate()

    @Slot()
    def _prompt_relock(self) -> None:
        if not self._current_device:
            return

        res = self._engine.check_relock_safety(
            device=self._current_device,
            flash_result=self._last_flash_result,
        )
        if not res.can_relock:
            QMessageBox.warning(
                self,
                "Relock Prohibited",
                "Bootloader relocking is prohibited:\n" + "\n".join(res.reasons),
            )
            return

        # Show confirmation dialog
        dlg = RelockConfirmationDialog(
            device=self._current_device,
            command=res.recommended_command,
            warnings=res.warnings,
            parent=self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        # Execute relock command
        dry_run = self._dry_run_cb.isChecked()
        self._console_edit.append(f"Executing relock command: '{res.recommended_command}' (dry_run={dry_run})...")
        lock_res = self._engine.execute_relock(
            device=self._current_device,
            command=res.recommended_command,
            dry_run=dry_run,
        )

        if lock_res.success:
            self._console_edit.append("Relock command executed successfully!")
            QMessageBox.information(
                self,
                "Relock Initiated",
                "Relock command sent to device!\n\n"
                "Look at your phone screen now:\n"
                "Use the Volume keys to select 'LOCK THE BOOTLOADER' and press the Power key to confirm.",
            )
        else:
            self._console_edit.append(f"Relock command failed: {lock_res.stderr}")
            QMessageBox.critical(
                self,
                "Relock Failed",
                f"Relock command failed:\n{lock_res.stderr or lock_res.stdout}",
            )
