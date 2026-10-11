"""
FlashDock — Fix Bricked Phone & Bootloop Rescue Screen (UnbrickScreen).

Provides a dedicated, safety-first emergency workstation for:
1. ⚡ Fix Bootloop (Magisk/KernelSU module kill-switch, Safe Mode, A/B slot rollback, cache wipe).
2. 🔧 Partition & Boot Image Restorer (flash stock boot/vbmeta/init_boot to recover from bad patches).
3. 🚑 Unbrick Guides & Low-Level Rescue (EDL 9008, MTK BROM, Samsung Download mode).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.bootloop_fixer import BootloopFixer
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)


class UnbrickScreen(QWidget):
    """Dedicated screen for Bootloop recovery and emergency unbricking."""

    # Navigation signal to request parent window to switch pages
    navigate_to_page = Signal(int)

    def __init__(
        self,
        device_mgr: Optional[DeviceManager] = None,
        adb: Optional[ADB] = None,
        fastboot: Optional[Fastboot] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb or ADB()
        self._fastboot = fastboot or Fastboot()
        self._fixer = BootloopFixer(adb=self._adb, fastboot=self._fastboot)

        self._current_device: Optional[DeviceInfo] = None

        self._build_ui()

    # -------------------------------------------------------------------------
    # UI Construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(16)

        # Header Row
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title = QLabel("🔧 Fix Bricked Phone & Bootloop Rescue")
        title.setProperty("cssClass", "heading")
        title_col.addWidget(title)

        subtitle = QLabel(
            "Emergency toolkit to recover from bootloops, faulty root modules, corrupted boot partitions, and bricks."
        )
        subtitle.setProperty("cssClass", "muted")
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col, 1)

        # Device Indicator Badge
        self._device_badge = QLabel("No device connected")
        self._device_badge.setStyleSheet(
            "background-color: #242426; border: 1px solid #38383A; "
            "border-radius: 6px; padding: 6px 12px; font-size: 12px; color: #8E8E93;"
        )
        header_row.addWidget(self._device_badge)

        root_layout.addLayout(header_row)

        # 3-Tab Widget
        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_bootloop_tab(), "⚡ Fix Bootloop")
        self._tabs.addTab(self._build_partition_repair_tab(), "🔧 Boot Partition Restorer")
        self._tabs.addTab(self._build_guides_tab(), "🚑 Hardware & Unbrick Guides")
        root_layout.addWidget(self._tabs, 1)

        # Bottom Status Label
        self._status_label = QLabel("Ready")
        self._status_label.setProperty("cssClass", "muted")
        root_layout.addWidget(self._status_label)

    # -------------------------------------------------------------------------
    # Tab 1: Fix Bootloop (Emergency Rescue)
    # -------------------------------------------------------------------------

    def _build_bootloop_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Emergency Alert Banner
        banner = QFrame()
        banner.setProperty("cssClass", "card_subtle")
        b_box = QVBoxLayout(banner)
        b_title = QLabel("💡 Bootloop Troubleshooting & Triage Guide")
        b_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #FF9F0A;")
        b_desc = QLabel(
            "• <b>90% of bootloops after rooting</b> are caused by incompatible Magisk / KernelSU / APatch modules.\n"
            "• Click <b>'Disable All Active Modules'</b> below — this instantly disables modules without touching photos or apps.\n"
            "• If stuck after an OTA or custom ROM flash, use <b>'Switch Active Slot (A/B)'</b> to roll back to the previously working slot."
        )
        b_desc.setProperty("cssClass", "muted")
        b_box.addWidget(b_title)
        b_box.addWidget(b_desc)
        layout.addWidget(banner)

        # Group 1: Root Module Kill-Switch
        group_modules = QGroupBox("Root Module Kill-Switch (Magisk / KernelSU / APatch)")
        m_box = QVBoxLayout(group_modules)
        m_box.setSpacing(10)

        m_desc = QLabel(
            "Safely neutralize faulty modules via ADB without wiping userdata or factory resetting."
        )
        m_desc.setProperty("cssClass", "muted")
        m_box.addWidget(m_desc)

        btn_row_m = QHBoxLayout()
        btn_row_m.setSpacing(10)

        btn_disable_mods = QPushButton("🧹 Disable All Root Modules (Kill-Switch)")
        btn_disable_mods.setProperty("cssClass", "primary")
        btn_disable_mods.setMinimumHeight(36)
        btn_disable_mods.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_disable_mods.setToolTip("Creates .disable flag in /data/adb/modules/. Preserves all user data.")
        btn_disable_mods.clicked.connect(self._on_disable_modules)
        btn_row_m.addWidget(btn_disable_mods)

        btn_remove_mods = QPushButton("🗑️ Remove All Root Modules")
        btn_remove_mods.setMinimumHeight(36)
        btn_remove_mods.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_remove_mods.setToolTip("Deletes all module folders from /data/adb/modules/ to ensure clean boot.")
        btn_remove_mods.clicked.connect(self._on_remove_modules)
        btn_row_m.addWidget(btn_remove_mods)

        m_box.addLayout(btn_row_m)
        layout.addWidget(group_modules)

        # Group 2: System Boot Modes & Safe Mode
        group_boot = QGroupBox("Safe Mode & Android OS Recovery")
        b_layout = QVBoxLayout(group_boot)
        b_layout.setSpacing(10)

        btn_row_b = QHBoxLayout()
        btn_row_b.setSpacing(10)

        btn_safemode = QPushButton("🛡️ Reboot to Safe Mode (ADB)")
        btn_safemode.setMinimumHeight(36)
        btn_safemode.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_safemode.setToolTip("Boots Android OS with 3rd-party apps and services disabled.")
        btn_safemode.clicked.connect(self._on_reboot_safemode)
        btn_row_b.addWidget(btn_safemode)

        btn_rec = QPushButton("⚡ Reboot to Recovery Mode")
        btn_rec.setMinimumHeight(36)
        btn_rec.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_rec.clicked.connect(self._on_reboot_recovery)
        btn_row_b.addWidget(btn_rec)

        b_layout.addLayout(btn_row_b)
        layout.addWidget(group_boot)

        # Group 3: Fastboot A/B Slot Switcher & Rollback
        group_slots = QGroupBox("Fastboot A/B Slot Rollback & Bootloader Tools")
        s_layout = QVBoxLayout(group_slots)
        s_layout.setSpacing(10)

        self._slot_status_lbl = QLabel("Slot status: Connect device in Fastboot mode to query active slot.")
        self._slot_status_lbl.setProperty("cssClass", "muted")
        s_layout.addWidget(self._slot_status_lbl)

        btn_row_s = QHBoxLayout()
        btn_row_s.setSpacing(10)

        btn_query_slot = QPushButton("🔍 Check Active Slot")
        btn_query_slot.setMinimumHeight(36)
        btn_query_slot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_query_slot.clicked.connect(self._on_check_slot)
        btn_row_s.addWidget(btn_query_slot)

        btn_switch_a = QPushButton("🔄 Switch Active Slot to 'A'")
        btn_switch_a.setMinimumHeight(36)
        btn_switch_a.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_switch_a.clicked.connect(lambda: self._on_switch_slot("a"))
        btn_row_s.addWidget(btn_switch_a)

        btn_switch_b = QPushButton("🔄 Switch Active Slot to 'B'")
        btn_switch_b.setMinimumHeight(36)
        btn_switch_b.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_switch_b.clicked.connect(lambda: self._on_switch_slot("b"))
        btn_row_s.addWidget(btn_switch_b)

        s_layout.addLayout(btn_row_s)

        btn_row_cache = QHBoxLayout()
        btn_row_cache.setSpacing(10)

        btn_erase_cache = QPushButton("🧹 Wipe Fastboot Cache Partition")
        btn_erase_cache.setMinimumHeight(36)
        btn_erase_cache.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_erase_cache.clicked.connect(self._on_erase_cache)
        btn_row_cache.addWidget(btn_erase_cache)

        btn_continue = QPushButton("🚀 Resume Normal Boot (fastboot continue)")
        btn_continue.setMinimumHeight(36)
        btn_continue.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_continue.clicked.connect(self._on_continue_boot)
        btn_row_cache.addWidget(btn_continue)

        s_layout.addLayout(btn_row_cache)
        layout.addWidget(group_slots)

        layout.addStretch(1)
        scroll.setWidget(container)

        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # -------------------------------------------------------------------------
    # Tab 2: Boot Partition Restorer
    # -------------------------------------------------------------------------

    def _build_partition_repair_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        card = QFrame()
        card.setProperty("cssClass", "card")
        c_box = QVBoxLayout(card)
        c_box.setSpacing(10)

        c_title = QLabel("🛠️ Restore Clean Stock Boot / VBMeta Image")
        c_title.setProperty("cssClass", "subheading")
        c_box.addWidget(c_title)

        c_desc = QLabel(
            "If your phone bootloops after patching a boot image or updating Magisk/KernelSU/APatch, "
            "flashing your original unmodified stock <code>boot.img</code> or <code>init_boot.img</code> restores the boot chain."
        )
        c_desc.setWordWrap(True)
        c_box.addWidget(c_desc)

        # Image File Picker
        pick_row = QHBoxLayout()
        self._boot_img_input = QLineEdit()
        self._boot_img_input.setPlaceholderText("Select stock boot.img or init_boot.img...")
        pick_row.addWidget(self._boot_img_input, 1)

        btn_browse = QPushButton("📁 Browse...")
        btn_browse.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_browse.clicked.connect(self._on_browse_boot_image)
        pick_row.addWidget(btn_browse)
        c_box.addLayout(pick_row)

        # Target Partition Selection Buttons
        part_row = QHBoxLayout()
        part_row.setSpacing(10)

        btn_flash_boot = QPushButton("⚡ Flash to 'boot' Partition")
        btn_flash_boot.setProperty("cssClass", "primary")
        btn_flash_boot.setMinimumHeight(36)
        btn_flash_boot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_flash_boot.clicked.connect(lambda: self._on_flash_partition("boot"))
        part_row.addWidget(btn_flash_boot)

        btn_flash_init_boot = QPushButton("⚡ Flash to 'init_boot' Partition")
        btn_flash_init_boot.setMinimumHeight(36)
        btn_flash_init_boot.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_flash_init_boot.clicked.connect(lambda: self._on_flash_partition("init_boot"))
        part_row.addWidget(btn_flash_init_boot)

        btn_flash_vbmeta = QPushButton("🛡️ Flash vbmeta (Disable Verity)")
        btn_flash_vbmeta.setMinimumHeight(36)
        btn_flash_vbmeta.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_flash_vbmeta.clicked.connect(self._on_flash_vbmeta_disabled)
        part_row.addWidget(btn_flash_vbmeta)

        c_box.addLayout(part_row)
        layout.addWidget(card)

        # Direct Return to Stock CTA Card
        cta_card = QFrame()
        cta_card.setProperty("cssClass", "card_subtle")
        cta_box = QHBoxLayout(cta_card)
        cta_box.setSpacing(12)

        cta_text = QLabel(
            "<b>Need a full factory restore?</b> Reflash entire official stock firmware (Google, Xiaomi, Samsung, etc.)."
        )
        cta_text.setProperty("cssClass", "muted")
        cta_box.addWidget(cta_text, 1)

        btn_go_return_stock = QPushButton("🏠 Open Return to Stock")
        btn_go_return_stock.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_go_return_stock.clicked.connect(lambda: self.navigate_to_page.emit(7))  # PAGE_RETURN_STOCK = 7
        cta_box.addWidget(btn_go_return_stock)

        layout.addWidget(cta_card)
        layout.addStretch(1)
        return tab

    # -------------------------------------------------------------------------
    # Tab 3: Hardware & Unbrick Guides
    # -------------------------------------------------------------------------

    def _build_guides_tab(self) -> QWidget:
        tab = QWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Soft Brick
        card_soft = QFrame()
        card_soft.setProperty("cssClass", "card")
        s_box = QVBoxLayout(card_soft)
        s_box.addWidget(QLabel("📱 <b>Soft Brick (Phone turns on, boots to Fastboot or Recovery)</b>"))
        s_desc = QLabel(
            "1. If device reboots repeatedly to recovery: Wipe dalvik/cache or factory reset userdata in recovery.\n"
            "2. If stuck in Fastboot mode: Check active slot or flash clean stock boot.img.\n"
            "3. If corrupted dm-verity message appears: Flash stock vbmeta with --disable-verity."
        )
        s_desc.setProperty("cssClass", "muted")
        s_box.addWidget(s_desc)
        layout.addWidget(card_soft)

        # Qualcomm EDL
        card_edl = QFrame()
        card_edl.setProperty("cssClass", "card")
        e_box = QVBoxLayout(card_edl)
        e_box.addWidget(QLabel("⚡ <b>Qualcomm Emergency Download (EDL 9008 Mode)</b>"))
        e_desc = QLabel(
            "• Applicable for Snapdragon devices that show a completely black screen or are recognized as 'Qualcomm HS-USB QDLoader 9008' (VID 05C6 PID 9008).\n"
            "• Recovery Method: Requires manufacturer-specific unbrick firehose tool (e.g. OnePlus MSM Download Tool, Xiaomi MiFlash Auth, Lenovo LMSA)."
        )
        e_desc.setProperty("cssClass", "muted")
        e_box.addWidget(e_desc)
        layout.addWidget(card_edl)

        # MediaTek BROM
        card_brom = QFrame()
        card_brom.setProperty("cssClass", "card")
        b_box = QVBoxLayout(card_brom)
        b_title_row = QHBoxLayout()
        b_title_row.addWidget(QLabel("⚙️ <b>MediaTek BootROM (BROM / Preloader Mode)</b>"), 1)
        btn_open_mtk = QPushButton("⚙️ Open MTK / Unisoc Flasher")
        btn_open_mtk.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_mtk.clicked.connect(lambda: self.navigate_to_page.emit(10))  # PAGE_MTK_UNISOC = 10
        b_title_row.addWidget(btn_open_mtk)
        b_box.addLayout(b_title_row)

        b_desc = QLabel(
            "• For MediaTek devices (VID 0E8D PID 0003), use FlashDock's built-in <b>MTK BROM Flasher</b> to bypass SLA/DAA security and flash scatter files."
        )
        b_desc.setProperty("cssClass", "muted")
        b_box.addWidget(b_desc)
        layout.addWidget(card_brom)

        layout.addStretch(1)
        scroll.setWidget(container)

        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        return tab

    # -------------------------------------------------------------------------
    # Action Slots
    # -------------------------------------------------------------------------

    @Slot()
    def _on_disable_modules(self) -> None:
        serial = self._current_device.serial if self._current_device else None
        self._status_label.setText("Triggering root module kill-switch...")
        success, msg = self._fixer.disable_root_modules_adb(serial=serial)
        self._status_label.setText(msg.splitlines()[0] if msg else "Completed")
        if success:
            QMessageBox.information(self, "Module Kill-Switch", msg)
        else:
            QMessageBox.warning(self, "Module Kill-Switch", msg)

    @Slot()
    def _on_remove_modules(self) -> None:
        serial = self._current_device.serial if self._current_device else None
        reply = QMessageBox.question(
            self,
            "Clear All Root Modules",
            "This will delete all folders inside /data/adb/modules/.\n\n"
            "Your photos and apps will NOT be touched, but installed Magisk/KernelSU modules will be removed.\n\n"
            "Proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status_label.setText("Clearing /data/adb/modules...")
        success, msg = self._fixer.remove_root_modules_adb(serial=serial)
        self._status_label.setText(msg)
        if success:
            QMessageBox.information(self, "Remove Modules", msg)
        else:
            QMessageBox.warning(self, "Remove Modules", msg)

    @Slot()
    def _on_reboot_safemode(self) -> None:
        serial = self._current_device.serial if self._current_device else None
        success, msg = self._fixer.reboot_safe_mode(serial=serial)
        self._status_label.setText(msg)
        if success:
            QMessageBox.information(self, "Safe Mode", msg)
        else:
            QMessageBox.warning(self, "Safe Mode", msg)

    @Slot()
    def _on_reboot_recovery(self) -> None:
        if self._device_mgr:
            self._device_mgr.reboot("recovery")
            self._status_label.setText("Rebooting to recovery mode...")
        elif self._adb.available:
            serial = self._current_device.serial if self._current_device else None
            self._adb.reboot(serial=serial, mode="recovery")
            self._status_label.setText("Rebooting to recovery mode...")

    @Slot()
    def _on_check_slot(self) -> None:
        serial = self._current_device.serial if self._current_device else None
        slot = self._fixer.get_current_fastboot_slot(serial=serial)
        if slot:
            self._slot_status_lbl.setText(f"Active Fastboot Slot: <b>Slot {slot.upper()}</b>")
            self._status_label.setText(f"Active Fastboot Slot: Slot {slot.upper()}")
        else:
            self._slot_status_lbl.setText("Could not query slot. Ensure device is connected in Fastboot mode.")
            self._status_label.setText("Could not query slot.")

    @Slot(str)
    def _on_switch_slot(self, target_slot: str) -> None:
        serial = self._current_device.serial if self._current_device else None
        reply = QMessageBox.question(
            self,
            f"Switch to Slot {target_slot.upper()}",
            f"Switch active slot to '{target_slot.upper()}'?\n\n"
            "This can unbrick your phone if the current slot has corrupted firmware.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status_label.setText(f"Switching slot to {target_slot.upper()}...")
        success, msg = self._fixer.switch_active_slot(target_slot, serial=serial)
        self._status_label.setText(msg.splitlines()[0] if msg else "Completed")
        if success:
            QMessageBox.information(self, "Slot Switch", msg)
            self._slot_status_lbl.setText(f"Active Fastboot Slot: <b>Slot {target_slot.upper()}</b>")
        else:
            QMessageBox.warning(self, "Slot Switch Failed", msg)

    @Slot()
    def _on_erase_cache(self) -> None:
        serial = self._current_device.serial if self._current_device else None
        success, msg = self._fixer.erase_fastboot_cache(serial=serial)
        self._status_label.setText(msg)
        if success:
            QMessageBox.information(self, "Erase Cache", msg)
        else:
            QMessageBox.warning(self, "Erase Cache Failed", msg)

    @Slot()
    def _on_continue_boot(self) -> None:
        serial = self._current_device.serial if self._current_device else None
        success, msg = self._fixer.fastboot_continue_boot(serial=serial)
        self._status_label.setText(msg)
        if success:
            QMessageBox.information(self, "Resume Boot", msg)
        else:
            QMessageBox.warning(self, "Resume Boot Failed", msg)

    @Slot()
    def _on_browse_boot_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Stock Boot or VBMeta Image",
            str(Path.home()),
            "Android Image Files (*.img);;All Files (*.*)",
        )
        if path:
            self._boot_img_input.setText(path)

    @Slot(str)
    def _on_flash_partition(self, partition: str) -> None:
        img_path = self._boot_img_input.text().strip()
        if not img_path or not Path(img_path).exists():
            QMessageBox.warning(self, "Missing Image", "Please select a valid image file first.")
            return

        serial = self._current_device.serial if self._current_device else None
        reply = QMessageBox.question(
            self,
            f"Flash '{partition}'",
            f"Flash '{Path(img_path).name}' to partition '{partition}' via Fastboot?\n\nProceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status_label.setText(f"Flashing {partition}...")
        try:
            cmd = [str(self._fastboot.binary_path)]
            if serial:
                cmd.extend(["-s", serial])
            cmd.extend(["flash", partition, img_path])

            import subprocess
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            out = (res.stdout + res.stderr).strip()
            if res.returncode == 0 or "finished" in out.lower() or "ok" in out.lower():
                QMessageBox.information(self, "Flash Succeeded", f"Partition '{partition}' flashed successfully!\n\n{out}")
                self._status_label.setText(f"Flashed {partition} successfully.")
            else:
                QMessageBox.warning(self, "Flash Failed", f"Fastboot error flashing {partition}:\n\n{out}")
                self._status_label.setText("Flash operation failed.")
        except Exception as exc:
            QMessageBox.warning(self, "Flash Error", str(exc))

    @Slot()
    def _on_flash_vbmeta_disabled(self) -> None:
        img_path = self._boot_img_input.text().strip()
        if not img_path or not Path(img_path).exists():
            QMessageBox.warning(self, "Missing Image", "Please select a valid vbmeta.img file first.")
            return

        serial = self._current_device.serial if self._current_device else None
        success, msg = self._fixer.disable_verity_vbmeta(img_path, serial=serial)
        if success:
            QMessageBox.information(self, "vbmeta Flashed", msg)
        else:
            QMessageBox.warning(self, "Flash vbmeta Failed", msg)

    # -------------------------------------------------------------------------
    # Device State Updates
    # -------------------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Update indicators when connected device changes."""
        self._current_device = device
        if device and device.mode != "not_connected":
            brand = (device.brand or "").strip()
            model = (device.model or "").strip()
            dev_text = f"📱 {brand} {model} [{device.mode.upper()}]"
            self._device_badge.setText(dev_text)

            if device.mode in ("bootloader", "fastboot", "fastbootd"):
                self._on_check_slot()
        else:
            self._device_badge.setText("No device connected")
            self._slot_status_lbl.setText("Slot status: Connect device in Fastboot mode to query active slot.")
