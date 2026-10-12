"""
FlashDock — Custom ROM, GSI & Recovery Flashing Screen.

Comprehensive GUI for:
* Flashing Custom Fastboot ROMs with partition inspection & ordered safety sequencing.
* Flashing Treble Generic System Images (GSI) with dynamic fastbootd mode switching and AVB bypass.
* Flashing & Live-Booting Custom Recoveries (TWRP, OrangeFox, PBRP).
* Local ROM & GSI Repository library browser with device compatibility matching pills.
* Modal FlashShield protection and typed confirmations for all destructive flashes.

Spec references: Section 12, Section 13, Section 29.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import GSIS_DIR, ROMS_DIR
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.repository import RepositoryManager, StoredItem
from flashdock.core.rom_flasher import (
    GsiInfo,
    RecoveryInfo,
    RomFlasher,
    RomPackageInfo,
)
from flashdock.core.safety import SafetyEngine
from flashdock.logger import get_logger
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.icon_assets import create_icon_label, get_icon
from flashdock.ui.widgets.flash_shield import FlashShieldDialog

log = get_logger(__name__)


class RomConfirmationDialog(QDialog):
    """Safety confirmation modal requiring typed 'FLASH' text."""

    def __init__(self, action_description: str, target_details: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm Destructive Flash")
        self.setFixedWidth(460)
        self._setup_ui(action_description, target_details)

    def _setup_ui(self, desc: str, details: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        warn_box = QFrame()
        warn_box.setProperty("cssClass", "danger_banner")
        wb_layout = QVBoxLayout(warn_box)
        t_row = QHBoxLayout()
        t_row.setSpacing(6)
        t_row.addWidget(create_icon_label("warning", 16))
        t = QLabel("CRITICAL OPERATION WARNING")
        t.setProperty("cssClass", "error")
        t.setStyleSheet("font-weight: 700; font-size: 13px;")
        t_row.addWidget(t)
        t_row.addStretch()
        wb_layout.addLayout(t_row)

        msg = QLabel(
            f"{desc}\n\nTarget: {details}\n\n"
            "Modifying core firmware partitions will overwrite existing system components. "
            "Ensure you have a complete stock backup before proceeding."
        )
        msg.setWordWrap(True)
        msg.setProperty("cssClass", "secondary")
        wb_layout.addWidget(msg)
        layout.addWidget(warn_box)

        lbl_instruct = QLabel('To confirm and proceed, type "FLASH" below:')
        lbl_instruct.setProperty("cssClass", "secondary")
        layout.addWidget(lbl_instruct)

        self._edit_confirm = QLineEdit()
        self._edit_confirm.setPlaceholderText('Type "FLASH" to unlock...')
        layout.addWidget(self._edit_confirm)

        btn_row = QHBoxLayout()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_cancel.setProperty("cssClass", "secondary")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self._btn_flash = QPushButton("Execute Flash")
        self._btn_flash.setIcon(get_icon("flash", 16))
        self._btn_flash.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_flash.setEnabled(False)
        self._btn_flash.setProperty("cssClass", "danger")
        btn_flash = self._btn_flash
        btn_flash.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_flash)
        layout.addLayout(btn_row)

        self._edit_confirm.textChanged.connect(self._on_text_changed)

    def _on_text_changed(self, text: str) -> None:
        self._btn_flash.setEnabled(text.strip().upper() == "FLASH")


class FlashRomScreen(QWidget):
    """Custom ROM, GSI, and Recovery Flashing Screen."""

    def __init__(
        self,
        device_mgr: DeviceManager,
        fastboot: Fastboot,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._fb = fastboot
        self._rom_flasher = RomFlasher(fastboot)
        self._repo_mgr = RepositoryManager()
        self._current_device: Optional[DeviceInfo] = None

        self._parsed_rom: Optional[RomPackageInfo] = None
        self._parsed_gsi: Optional[GsiInfo] = None
        self._parsed_recovery: Optional[RecoveryInfo] = None

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Header
        h_box = QHBoxLayout()
        h_box.setSpacing(10)
        h_box.addWidget(create_icon_label("flash", 22))
        header = QLabel("Flash ROM · Treble GSI · Custom Recovery")
        header.setProperty("cssClass", "heading")
        h_box.addWidget(header)
        h_box.addStretch()
        layout.addLayout(h_box)

        self._device_banner = QLabel("No device connected. Connect your phone in Fastboot or Fastbootd mode.")
        self._device_banner.setProperty("cssClass", "secondary")
        layout.addWidget(self._device_banner)

        # Tabs
        self._tabs = QTabWidget()

        self._tab_custom_rom = QWidget()
        self._tab_gsi = QWidget()
        self._tab_recovery = QWidget()
        self._tab_library = QWidget()
        self._tab_guides = QWidget()

        self._setup_custom_rom_tab()
        self._setup_gsi_tab()
        self._setup_recovery_tab()
        self._setup_library_tab()
        self._setup_guides_tab()

        self._tabs.addTab(self._tab_custom_rom, get_icon("flash", 16), "Custom ROM")
        self._tabs.addTab(self._tab_gsi, get_icon("phone", 16), "Treble GSI")
        self._tabs.addTab(self._tab_recovery, get_icon("tools", 16), "Custom Recovery")
        self._tabs.addTab(self._tab_library, get_icon("folder", 16), "Local ROM Library")
        self._tabs.addTab(self._tab_guides, get_icon("book", 16), "Guides & Help")

        layout.addWidget(self._tabs, 1)

    # -----------------------------------------------------------------------
    # Tab 1: Custom ROM Flasher
    # -----------------------------------------------------------------------

    def _setup_custom_rom_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Package picker card
        picker_card = QFrame()
        picker_card.setProperty("cssClass", "card")
        pc_layout = QVBoxLayout(picker_card)
        pc_layout.setSpacing(10)

        lbl_title = QLabel("1. Select Fastboot ROM Package")
        lbl_title.setProperty("cssClass", "subheading")
        pc_layout.addWidget(lbl_title)

        row_pick = QHBoxLayout()
        self._edit_rom_path = QLineEdit()
        self._edit_rom_path.setPlaceholderText("Select extracted ROM folder or fastboot .zip package...")
        self._edit_rom_path.setClearButtonEnabled(True)
        row_pick.addWidget(self._edit_rom_path, 1)

        btn_browse_folder = QPushButton("Browse Folder...")
        btn_browse_folder.setIcon(get_icon("folder", 16))
        btn_browse_folder.setProperty("cssClass", "secondary")
        btn_browse_folder.clicked.connect(self._on_browse_rom_folder)
        row_pick.addWidget(btn_browse_folder)

        btn_browse_zip = QPushButton("Browse ZIP...")
        btn_browse_zip.setIcon(get_icon("folder", 16))
        btn_browse_zip.setProperty("cssClass", "secondary")
        btn_browse_zip.clicked.connect(self._on_browse_rom_zip)
        row_pick.addWidget(btn_browse_zip)

        pc_layout.addLayout(row_pick)

        self._lbl_rom_info = QLabel("No package loaded.")
        self._lbl_rom_info.setProperty("cssClass", "secondary")
        pc_layout.addWidget(self._lbl_rom_info)
        layout.addWidget(picker_card)

        # Partition Inspection Table
        table_card = QFrame()
        table_card.setProperty("cssClass", "card")
        tc_layout = QVBoxLayout(table_card)
        tc_layout.setSpacing(8)

        lbl_tbl = QLabel("2. Partition Flash Schedule")
        lbl_tbl.setProperty("cssClass", "subheading")
        tc_layout.addWidget(lbl_tbl)

        self._rom_table = QTableWidget()
        self._rom_table.setColumnCount(3)
        self._rom_table.setHorizontalHeaderLabels(["Partition", "Image File", "Size (MB)"])
        self._rom_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._rom_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._rom_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._rom_table.verticalHeader().setVisible(False)
        self._rom_table.setMaximumHeight(180)
        tc_layout.addWidget(self._rom_table)
        layout.addWidget(table_card)

        # Options Card
        opt_card = QFrame()
        opt_card.setProperty("cssClass", "card")
        oc_layout = QVBoxLayout(opt_card)
        oc_layout.setSpacing(8)

        lbl_opt = QLabel("3. Flashing Options")
        lbl_opt.setProperty("cssClass", "subheading")
        oc_layout.addWidget(lbl_opt)

        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("Target Slot:"))
        self._combo_slot = QComboBox()
        self._combo_slot.addItems(["Active Slot (Auto)", "Slot A", "Slot B", "Both Slots (A and B)"])
        opt_row.addWidget(self._combo_slot)
        opt_row.addSpacing(20)

        self._chk_wipe = QCheckBox("Wipe Userdata (-w) [Clean Install]")
        self._chk_wipe.setChecked(True)
        opt_row.addWidget(self._chk_wipe)

        self._chk_dry_run = QCheckBox("Dry-run Simulation")
        opt_row.addWidget(self._chk_dry_run)

        self._chk_reboot = QCheckBox("Auto-reboot upon completion")
        self._chk_reboot.setChecked(True)
        opt_row.addWidget(self._chk_reboot)
        opt_row.addStretch()

        oc_layout.addLayout(opt_row)
        layout.addWidget(opt_card)

        # Action button
        self._btn_flash_rom = QPushButton("Flash Custom ROM")
        self._btn_flash_rom.setIcon(get_icon("flash", 16))
        self._btn_flash_rom.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_flash_rom.setProperty("cssClass", "primary")
        self._btn_flash_rom.clicked.connect(self._on_flash_custom_rom)
        layout.addWidget(self._btn_flash_rom)

        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_custom_rom)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

    # -----------------------------------------------------------------------
    # Tab 2: Treble GSI Flasher
    # -----------------------------------------------------------------------

    def _setup_gsi_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Fastbootd Mode Switcher Card
        fb_card = QFrame()
        fb_card.setProperty("cssClass", "card")
        fb_layout = QHBoxLayout(fb_card)
        self._lbl_fb_mode = QLabel("Current Mode: Checking...")
        self._lbl_fb_mode.setProperty("cssClass", "subheading")
        fb_layout.addWidget(self._lbl_fb_mode, 1)

        self._btn_switch_fastbootd = QPushButton("Reboot to FastbootD (Userspace)")
        self._btn_switch_fastbootd.setIcon(get_icon("refresh", 16))
        self._btn_switch_fastbootd.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_switch_fastbootd.setProperty("cssClass", "secondary")
        self._btn_switch_fastbootd.clicked.connect(self._on_switch_fastbootd)
        fb_layout.addWidget(self._btn_switch_fastbootd)
        layout.addWidget(fb_card)

        # GSI Image Picker Card
        gsi_card = QFrame()
        gsi_card.setProperty("cssClass", "card")
        gc_layout = QVBoxLayout(gsi_card)
        gc_layout.setSpacing(10)

        gc_title = QLabel("1. Select Generic System Image (GSI)")
        gc_title.setProperty("cssClass", "subheading")
        gc_layout.addWidget(gc_title)

        row_gsi = QHBoxLayout()
        self._edit_gsi_path = QLineEdit()
        self._edit_gsi_path.setPlaceholderText("Select GSI file (.img, .img.xz, .zip)...")
        self._edit_gsi_path.setClearButtonEnabled(True)
        row_gsi.addWidget(self._edit_gsi_path, 1)

        btn_browse_gsi = QPushButton("Browse GSI...")
        btn_browse_gsi.setIcon(get_icon("folder", 16))
        btn_browse_gsi.setProperty("cssClass", "secondary")
        btn_browse_gsi.clicked.connect(self._on_browse_gsi)
        row_gsi.addWidget(btn_browse_gsi)
        gc_layout.addLayout(row_gsi)

        self._lbl_gsi_badge = QLabel("No GSI loaded.")
        self._lbl_gsi_badge.setProperty("cssClass", "secondary")
        gc_layout.addWidget(self._lbl_gsi_badge)
        layout.addWidget(gsi_card)

        # VBMeta & Options Card
        vb_card = QFrame()
        vb_card.setProperty("cssClass", "card")
        vb_layout = QVBoxLayout(vb_card)
        vb_layout.setSpacing(8)

        vb_title = QLabel("2. Android Verified Boot (AVB) & Formatting")
        vb_title.setProperty("cssClass", "subheading")
        vb_layout.addWidget(vb_title)

        self._chk_disable_avb = QCheckBox("Patch VBMeta (--disable-verity --disable-verification) [Prevents dm-verity bootloop]")
        self._chk_disable_avb.setChecked(True)
        vb_layout.addWidget(self._chk_disable_avb)

        vb_row = QHBoxLayout()
        self._edit_vbmeta_path = QLineEdit()
        self._edit_vbmeta_path.setPlaceholderText("Optional: Select clean stock vbmeta.img (recommended for AVB patching)...")
        vb_row.addWidget(self._edit_vbmeta_path, 1)

        btn_vb = QPushButton("Browse vbmeta...")
        btn_vb.setIcon(get_icon("folder", 16))
        btn_vb.setProperty("cssClass", "secondary")
        btn_vb.clicked.connect(self._on_browse_vbmeta)
        vb_row.addWidget(btn_vb)
        vb_layout.addLayout(vb_row)

        self._chk_gsi_wipe = QCheckBox("Format Userdata / Factory Reset (Mandatory for first boot of new GSI)")
        self._chk_gsi_wipe.setChecked(True)
        vb_layout.addWidget(self._chk_gsi_wipe)

        self._chk_gsi_dry = QCheckBox("Dry-run Simulation")
        vb_layout.addWidget(self._chk_gsi_dry)

        layout.addWidget(vb_card)

        # Action button
        self._btn_flash_gsi = QPushButton("Flash Generic System Image (GSI)")
        self._btn_flash_gsi.setIcon(get_icon("flash", 16))
        self._btn_flash_gsi.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_flash_gsi.setProperty("cssClass", "primary")
        self._btn_flash_gsi.clicked.connect(self._on_flash_gsi)
        layout.addWidget(self._btn_flash_gsi)

        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_gsi)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

    # -----------------------------------------------------------------------
    # Tab 3: Custom Recovery Flasher
    # -----------------------------------------------------------------------

    def _setup_recovery_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Target Recommendation Card
        rec_card = QFrame()
        rec_card.setProperty("cssClass", "card")
        rc_layout = QVBoxLayout(rec_card)
        self._lbl_rec_target = QLabel("Target Partition: recovery (Dedicated recovery partition)")
        self._lbl_rec_target.setProperty("cssClass", "subheading")
        rc_layout.addWidget(self._lbl_rec_target)
        self._lbl_rec_note = QLabel(
            "Devices with Android 10+ dynamic partitions or A/B slots embed recovery into boot.img. "
            "FlashDock detects your device's exact partition scheme automatically."
        )
        self._lbl_rec_note.setWordWrap(True)
        self._lbl_rec_note.setProperty("cssClass", "secondary")
        rc_layout.addWidget(self._lbl_rec_note)
        layout.addWidget(rec_card)

        # Recovery File Picker Card
        rf_card = QFrame()
        rf_card.setProperty("cssClass", "card")
        rfc_layout = QVBoxLayout(rf_card)
        rfc_layout.setSpacing(10)

        rfc_title = QLabel("1. Select Custom Recovery Image (TWRP / OrangeFox)")
        rfc_title.setProperty("cssClass", "subheading")
        rfc_layout.addWidget(rfc_title)

        row_rec = QHBoxLayout()
        self._edit_rec_path = QLineEdit()
        self._edit_rec_path.setPlaceholderText("Select recovery .img file (e.g. twrp.img, recovery.img)...")
        self._edit_rec_path.setClearButtonEnabled(True)
        row_rec.addWidget(self._edit_rec_path, 1)

        btn_browse_rec = QPushButton("Browse Image...")
        btn_browse_rec.setIcon(get_icon("folder", 16))
        btn_browse_rec.setProperty("cssClass", "secondary")
        btn_browse_rec.clicked.connect(self._on_browse_recovery)
        row_rec.addWidget(btn_browse_rec)
        rfc_layout.addLayout(row_rec)

        self._lbl_rec_badge = QLabel("No recovery loaded.")
        self._lbl_rec_badge.setProperty("cssClass", "secondary")
        rfc_layout.addWidget(self._lbl_rec_badge)
        layout.addWidget(rf_card)

        # Flash Mode Selection Card
        mode_card = QFrame()
        mode_card.setProperty("cssClass", "card")
        mc_layout = QVBoxLayout(mode_card)
        mc_layout.setSpacing(8)

        mc_title = QLabel("2. Select Execution Mode")
        mc_title.setProperty("cssClass", "subheading")
        mc_layout.addWidget(mc_title)

        self._rec_group = QButtonGroup(self)
        self._rb_rec_flash = QRadioButton("Permanent Flash to Partition (fastboot flash recovery/boot)")
        self._rb_rec_flash.setChecked(True)
        self._rec_group.addButton(self._rb_rec_flash)
        mc_layout.addWidget(self._rb_rec_flash)

        self._rb_rec_boot = QRadioButton("Temporary Live Boot (fastboot boot recovery.img) [Zero-Risk RAM Test]")
        self._rec_group.addButton(self._rb_rec_boot)
        mc_layout.addWidget(self._rb_rec_boot)

        self._chk_rec_dry = QCheckBox("Dry-run Simulation")
        mc_layout.addWidget(self._chk_rec_dry)

        layout.addWidget(mode_card)

        # Action button
        self._btn_flash_recovery = QPushButton("Flash / Boot Custom Recovery")
        self._btn_flash_recovery.setIcon(get_icon("flash", 16))
        self._btn_flash_recovery.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_flash_recovery.setProperty("cssClass", "primary")
        self._btn_flash_recovery.clicked.connect(self._on_flash_recovery)
        layout.addWidget(self._btn_flash_recovery)

        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_recovery)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

    # -----------------------------------------------------------------------
    # Tab 4: Local ROM & GSI Library
    # -----------------------------------------------------------------------

    def _setup_library_tab(self) -> None:
        layout = QVBoxLayout(self._tab_library)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Action Row
        top_row = QHBoxLayout()
        btn_import_rom = QPushButton("Import ROM Package...")
        btn_import_rom.setIcon(get_icon("plus", 16))
        btn_import_rom.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import_rom.setProperty("cssClass", "primary")
        btn_import_rom.clicked.connect(self._on_import_rom)
        top_row.addWidget(btn_import_rom)

        btn_import_gsi = QPushButton("Import GSI Image...")
        btn_import_gsi.setIcon(get_icon("plus", 16))
        btn_import_gsi.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_import_gsi.setProperty("cssClass", "secondary")
        btn_import_gsi.clicked.connect(self._on_import_gsi)
        top_row.addWidget(btn_import_gsi)

        btn_open_storage = QPushButton("Open Storage Folder")
        btn_open_storage.setIcon(get_icon("folder", 16))
        btn_open_storage.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_storage.setProperty("cssClass", "secondary")
        btn_open_storage.clicked.connect(self._on_open_storage)
        top_row.addWidget(btn_open_storage)

        top_row.addStretch()

        btn_refresh = QPushButton("Refresh")
        btn_refresh.setIcon(get_icon("refresh", 16))
        btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_refresh.setProperty("cssClass", "secondary")
        btn_refresh.clicked.connect(self._refresh_library)
        top_row.addWidget(btn_refresh)

        layout.addLayout(top_row)

        # Library Table
        self._lib_table = QTableWidget()
        self._lib_table.setColumnCount(5)
        self._lib_table.setHorizontalHeaderLabels(["Name / Package", "Category", "Size", "Compatibility", "Action"])
        self._lib_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._lib_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._lib_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._lib_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._lib_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self._lib_table.verticalHeader().setVisible(False)
        layout.addWidget(self._lib_table, 1)

    # -----------------------------------------------------------------------
    # Tab 5: Guides & Help
    # -----------------------------------------------------------------------

    def _setup_guides_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        def add_guide_card(title: str, text: str):
            f = QFrame()
            f.setProperty("cssClass", "card")
            fl = QVBoxLayout(f)
            t = QLabel(title)
            t.setProperty("cssClass", "subheading")
            fl.addWidget(t)
            d = QLabel(text)
            d.setWordWrap(True)
            d.setProperty("cssClass", "secondary")
            fl.addWidget(d)
            layout.addWidget(f)

        add_guide_card(
            "Clean Flash vs. Dirty Flash",
            "• Clean Flash: Formats userdata (-w). Mandatory when switching ROM brands (e.g. MIUI to LineageOS) or upgrading major Android versions.\n"
            "• Dirty Flash: Flashes system/boot without wiping userdata. Only safe for minor updates of the exact same ROM build."
        )

        add_guide_card(
            "FastbootD & Dynamic Partitions Guide",
            "Android 10+ devices use a single physical 'super' partition containing logical sub-partitions (system, vendor, product).\n"
            "• Flashing dynamic 'system' GSI images requires FastbootD mode (userspace fastboot).\n"
            "• Use the 'Reboot to FastbootD' button on Tab 2 if your phone is in standard bootloader mode."
        )

        add_guide_card(
            "Treble GSI Variant Matrix",
            "Treble naming uses 3 to 4 letters: e.g. arm64_bgS\n"
            "• 1st: Architecture ('a64' = 32-bit binder on 64-bit CPU, 'arm64' = pure 64-bit).\n"
            "• 2nd: Slot scheme ('a' = A-only legacy, 'b' = A/B modern seamless).\n"
            "• 3rd: GApps flavor ('v' = vanilla, 'g' = Google Apps, 'o' = microG, 'f' = FOSS).\n"
            "• 4th: Superuser ('N' = no root, 'S' = built-in su, 'Z' = userdebug)."
        )

        add_guide_card(
            "Temporary Recovery Live-Booting",
            "Instead of permanently overwriting your phone's recovery or kernel, you can use 'Temporary Live Boot'. "
            "Fastboot streams the recovery image directly into device RAM and boots it. The internal storage remains completely untouched."
        )

        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_guides)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

    # -----------------------------------------------------------------------
    # Device State Updates
    # -----------------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Update flasher state when connected device changes."""
        self._current_device = device
        if not device or device.mode == "not_connected":
            self._device_banner.setText("No device connected. Connect your phone via USB in Fastboot or Fastbootd mode.")
            self._lbl_fb_mode.setText("Current Mode: Not Connected")
            self._refresh_library()
            return

        mode_str = device.mode.upper() if device.mode in ("fastboot", "fastbootd") else device.mode.title()
        bl_str = "Unlocked" if device.bootloader_state == "unlocked" else "LOCKED"
        bat_str = f"Battery: {device.battery_level}%" if device.battery_level >= 0 else "Battery: N/A"
        dyn_str = "Dynamic (Super)" if device.has_dynamic_partitions else "Static Partitions"
        code_str = f" ({device.device})" if device.device else ""
        self._device_banner.setText(
            f"{device.summary_line}{code_str} · Mode: {mode_str} · Bootloader: {bl_str} · Slot: {device.active_slot.upper()} · {dyn_str} · {bat_str}"
        )

        # Tab 2 fastbootd mode indicator
        if device.mode == "fastbootd":
            self._lbl_fb_mode.setText("Current Mode: FASTBOOTD (Userspace) — Ready to flash dynamic system!")
            self._lbl_fb_mode.setStyleSheet("font-size: 13px; font-weight: 700; color: #2ea043;")
            self._btn_switch_fastbootd.setEnabled(False)
        elif device.mode == "fastboot":
            self._lbl_fb_mode.setText("Current Mode: STANDARD FASTBOOT — Click switch to enter FastbootD for dynamic partitions.")
            self._lbl_fb_mode.setStyleSheet("font-size: 13px; font-weight: 700; color: #d29922;")
            self._btn_switch_fastbootd.setEnabled(True)
        else:
            self._lbl_fb_mode.setText(f"Current Mode: {device.mode.title()} (Reboot to fastboot required)")
            self._btn_switch_fastbootd.setEnabled(True)

        # Tab 3 Recovery recommendation
        target_part, live_boot, reason = self._rom_flasher.determine_recovery_target(device)
        self._lbl_rec_target.setText(f"Target Partition: {target_part} ({'Recovery in boot' if target_part == 'boot' else 'Dedicated recovery partition'})")
        self._lbl_rec_note.setText(reason)

        self._refresh_library()

    # -----------------------------------------------------------------------
    # Actions: Custom ROM
    # -----------------------------------------------------------------------

    def _on_browse_rom_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Extracted Fastboot ROM Folder", "")
        if folder:
            self._edit_rom_path.setText(folder)
            self._inspect_rom_package(folder)

    def _on_browse_rom_zip(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Fastboot ROM ZIP", "", "ROM Packages (*.zip *.tgz *.tar);;All Files (*.*)"
        )
        if path:
            self._edit_rom_path.setText(path)
            self._inspect_rom_package(path)

    def _inspect_rom_package(self, path_str: str) -> None:
        ok, info, msg = self._rom_flasher.parse_custom_rom(path_str)
        if ok and info:
            self._parsed_rom = info
            script_str = f" · Script: {info.script_name}" if info.has_flash_script else ""
            code_str = f" · Target: {info.target_codename}" if info.target_codename else ""
            self._lbl_rom_info.setText(
                f"{info.name} ({info.total_size_mb} MB) · {len(info.detected_partitions)} partitions{script_str}{code_str}"
            )

            # Populate table
            self._rom_table.setRowCount(len(info.detected_partitions))
            for row, item in enumerate(info.detected_partitions):
                self._rom_table.setItem(row, 0, QTableWidgetItem(item.partition_name))
                self._rom_table.setItem(row, 1, QTableWidgetItem(item.image_path.name))
                self._rom_table.setItem(row, 2, QTableWidgetItem(str(item.size_mb)))
        else:
            self._parsed_rom = None
            self._lbl_rom_info.setText(f"Error: {msg}")
            self._rom_table.setRowCount(0)

    def _on_flash_custom_rom(self) -> None:
        if not self._parsed_rom:
            QMessageBox.warning(self, "No ROM Selected", "Please select a valid Fastboot ROM package first.")
            return

        device = self._current_device
        if not device:
            QMessageBox.warning(self, "No Device", "Please connect a device in Fastboot mode.")
            return

        # Battery check
        bat_res = SafetyEngine.check_battery(device.battery_level)
        if bat_res.is_blocked:
            QMessageBox.warning(self, "Low Battery", bat_res.message)
            return

        # Target slot mapping
        idx = self._combo_slot.currentIndex()
        slot_map = ["active", "a", "b", "both"]
        target_slot = slot_map[idx]
        wipe_data = self._chk_wipe.isChecked()
        dry_run = self._chk_dry_run.isChecked()

        # Confirmation dialog
        confirm = RomConfirmationDialog(
            action_description=f"Flashing Custom ROM '{self._parsed_rom.name}' ({len(self._parsed_rom.detected_partitions)} partitions).",
            target_details=f"{device.summary_line} · Slot: {target_slot.upper()} · Wipe: {wipe_data}",
            parent=self,
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress("Starting ROM flashing...", 0)

        ok, msg = self._rom_flasher.flash_custom_rom(
            package_info=self._parsed_rom,
            slot_target=target_slot,
            wipe_userdata=wipe_data,
            dry_run=dry_run,
            progress_callback=lambda cur, tot, m: shield.update_progress(m, int(cur / tot * 100)),
            serial=device.serial,
        )

        shield.mark_completed(ok, msg)
        if ok and self._chk_reboot.isChecked() and not dry_run:
            self._fb.reboot(serial=device.serial)

    # -----------------------------------------------------------------------
    # Actions: Treble GSI
    # -----------------------------------------------------------------------

    def _on_switch_fastbootd(self) -> None:
        device = self._current_device
        serial = device.serial if device else ""
        res = self._rom_flasher.switch_to_fastbootd(serial=serial)
        if res.success:
            QMessageBox.information(
                self,
                "Rebooting to FastbootD",
                "Device reboot command sent.\nPlease wait a few seconds for the device to enter FastbootD mode.",
            )
        else:
            QMessageBox.warning(self, "Command Failed", f"Could not reboot to fastbootd: {res.stderr}")

    def _on_browse_gsi(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select GSI Image", "", "GSI Images (*.img *.xz *.zip *.gz);;All Files (*.*)"
        )
        if path:
            self._edit_gsi_path.setText(path)
            ok, info, msg = self._rom_flasher.parse_gsi(path)
            if ok and info:
                self._parsed_gsi = info
                self._lbl_gsi_badge.setText(
                    f"{info.name} ({info.size_mb} MB) · Arch: {info.arch} · Slot: {info.slot_scheme} · Flavor: {info.gapps_variant}"
                )
            else:
                self._parsed_gsi = None
                self._lbl_gsi_badge.setText(f"Error: {msg}")

    def _on_browse_vbmeta(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select VBMeta Image", "", "Boot Images (*.img);;All Files (*.*)")
        if path:
            self._edit_vbmeta_path.setText(path)

    def _on_flash_gsi(self) -> None:
        if not self._parsed_gsi:
            QMessageBox.warning(self, "No GSI Selected", "Please select a valid GSI image file first.")
            return

        device = self._current_device
        if not device:
            QMessageBox.warning(self, "No Device", "Please connect a device first.")
            return

        # Check mode for dynamic partitions
        if device.has_dynamic_partitions and device.mode != "fastbootd":
            reply = QMessageBox.question(
                self,
                "FastbootD Mode Required",
                "This device uses dynamic partitions (super.img). GSIs must be flashed in FastbootD mode.\n\n"
                "Would you like to reboot into FastbootD now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_switch_fastbootd()
                return

        bat_res = SafetyEngine.check_battery(device.battery_level)
        if bat_res.is_blocked:
            QMessageBox.warning(self, "Low Battery", bat_res.message)
            return

        confirm = RomConfirmationDialog(
            action_description=f"Flashing Generic System Image '{self._parsed_gsi.name}' to 'system' partition.",
            target_details=f"{device.summary_line} · Dynamic Super: {device.has_dynamic_partitions}",
            parent=self,
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress("Starting GSI flash...", 0)

        ok, msg = self._rom_flasher.flash_gsi(
            gsi_image_path=self._parsed_gsi.image_path,
            disable_avb=self._chk_disable_avb.isChecked(),
            vbmeta_path=self._edit_vbmeta_path.text().strip() or None,
            wipe_userdata=self._chk_gsi_wipe.isChecked(),
            is_dynamic_super=device.has_dynamic_partitions,
            dry_run=self._chk_gsi_dry.isChecked(),
            progress_callback=lambda cur, tot, m: shield.update_progress(m, int(cur / tot * 100)),
            serial=device.serial,
        )
        shield.mark_completed(ok, msg)

    # -----------------------------------------------------------------------
    # Actions: Custom Recovery
    # -----------------------------------------------------------------------

    def _on_browse_recovery(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Custom Recovery Image", "", "Recovery Images (*.img *.bin);;All Files (*.*)"
        )
        if path:
            self._edit_rec_path.setText(path)
            ok, info, msg = self._rom_flasher.parse_recovery_image(path, self._current_device)
            if ok and info:
                self._parsed_recovery = info
                self._lbl_rec_badge.setText(
                    f"{info.name} ({info.size_mb} MB) · Type: {info.recovery_type} · Recommended: {info.recommended_partition}"
                )
            else:
                self._parsed_recovery = None
                self._lbl_rec_badge.setText(f"Error: {msg}")

    def _on_flash_recovery(self) -> None:
        if not self._parsed_recovery:
            QMessageBox.warning(self, "No Recovery Selected", "Please select a valid recovery .img file first.")
            return

        device = self._current_device
        if not device:
            QMessageBox.warning(self, "No Device", "Please connect a device in Fastboot mode.")
            return

        live_boot = self._rb_rec_boot.isChecked()
        target_part = self._parsed_recovery.recommended_partition
        dry_run = self._chk_rec_dry.isChecked()

        action_name = "Live Booting Recovery into RAM" if live_boot else f"Flashing Recovery to '{target_part}'"
        reply = QMessageBox.question(
            self,
            f"Confirm {action_name}",
            f"{action_name} for '{self._parsed_recovery.name}'?\n\nTarget Device: {device.summary_line}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress(f"{action_name}...", 50)

        ok, msg = self._rom_flasher.flash_recovery(
            recovery_image_path=self._parsed_recovery.image_path,
            target_partition=target_part,
            live_boot_only=live_boot,
            dry_run=dry_run,
            serial=device.serial,
        )
        shield.mark_completed(ok, msg)

    # -----------------------------------------------------------------------
    # Actions: Library
    # -----------------------------------------------------------------------

    def _refresh_library(self) -> None:
        items: list[StoredItem] = []
        items.extend(self._repo_mgr.scan_roms())
        items.extend(self._repo_mgr.scan_gsis())

        self._lib_table.setRowCount(len(items))
        for row, item in enumerate(items):
            # Name
            item_name = QTableWidgetItem(f"  {item.name}")
            item_name.setIcon(get_icon("folder" if item.category == "rom" else "phone", 16))
            item_name.setToolTip(str(item.file_path))
            self._lib_table.setItem(row, 0, item_name)

            # Category
            cat_str = "Custom ROM" if item.category == "rom" else "Treble GSI"
            item_cat = QTableWidgetItem(cat_str)
            item_cat.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._lib_table.setItem(row, 1, item_cat)

            # Size
            item_size = QTableWidgetItem(f"{item.size_mb} MB")
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._lib_table.setItem(row, 2, item_size)

            # Compatibility
            is_compat, reason = item.is_compatible_with(self._current_device)
            item_comp = QTableWidgetItem("Compatible" if is_compat else reason)
            item_comp.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_comp.setForeground(Qt.GlobalColor.green if is_compat else Qt.GlobalColor.yellow)
            self._lib_table.setItem(row, 3, item_comp)

            # Action cell
            act_widget = QWidget()
            act_layout = QHBoxLayout(act_widget)
            act_layout.setContentsMargins(4, 2, 4, 2)
            act_layout.setSpacing(6)

            btn_use = QPushButton("Use in Flasher")
            btn_use.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_use.setProperty("cssClass", "primary")
            btn_use.clicked.connect(lambda _, it=item: self._use_library_item(it))
            act_layout.addWidget(btn_use)

            btn_del = QPushButton("Delete")
            btn_del.setIcon(get_icon("trash", 14))
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setProperty("cssClass", "danger")
            btn_del.clicked.connect(lambda _, it=item: self._delete_library_item(it))
            act_layout.addWidget(btn_del)

            self._lib_table.setCellWidget(row, 4, act_widget)

    def _use_library_item(self, item: StoredItem) -> None:
        if item.category == "rom":
            self._edit_rom_path.setText(str(item.file_path))
            self._inspect_rom_package(str(item.file_path))
            self._tabs.setCurrentIndex(0)
        elif item.category == "gsi":
            self._edit_gsi_path.setText(str(item.file_path))
            ok, info, msg = self._rom_flasher.parse_gsi(item.file_path)
            if ok and info:
                self._parsed_gsi = info
                self._lbl_gsi_badge.setText(
                    f"{info.name} ({info.size_mb} MB) · Arch: {info.arch} · Slot: {info.slot_scheme} · Flavor: {info.gapps_variant}"
                )
            self._tabs.setCurrentIndex(1)

    def _delete_library_item(self, item: StoredItem) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Stored Package",
            f"Are you sure you want to delete '{item.name}' from your local library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            RepositoryManager.delete_item(item.file_path)
            self._refresh_library()

    def _on_import_rom(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import ROM Package to Library", "", "ROM Packages (*.zip *.tgz *.tar);;All Files (*.*)"
        )
        if path:
            self._repo_mgr.import_rom(path)
            self._refresh_library()

    def _on_import_gsi(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import GSI Image to Library", "", "GSI Images (*.img *.xz *.zip *.gz);;All Files (*.*)"
        )
        if path:
            self._repo_mgr.import_gsi(path)
            self._refresh_library()

    def _on_open_storage(self) -> None:
        ROMS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(ROMS_DIR))
        except Exception as e:
            log.warning("Could not open ROM storage folder: %s", e)
