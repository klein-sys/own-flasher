"""
FlashDock — Play Integrity Fixer & Fingerprint Spoofer Screen (Phase 14).

Provides a comprehensive GUI for:
1. Play Integrity diagnostics (bootloader state, SELinux, root/Zygisk, active pif.json).
2. Built-in certified fingerprint profile vault with 1-click injection to /data/adb/pif.json.
3. Automated Google Play Services cache flush to refresh certification verdicts.
4. Magisk DenyList / Zygisk banking application root hiding manager.
5. Interactive pif.json editor, file import/export, and Play Integrity architecture guide.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.integrity import (
    BUILTIN_PROFILES,
    RECOMMENDED_PROTECTED_PACKAGES,
    FingerprintProfile,
    IntegrityDiagnostic,
    PlayIntegrityFixer,
)
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.ui.icon_assets import create_icon_label, get_icon

log = get_logger(__name__)


class IntegrityScreen(QWidget):
    """Play Integrity Fixer, Diagnostics and Fingerprint Spoofer Screen."""

    navigate_to_page = Signal(int)

    def __init__(
        self,
        device_mgr: DeviceManager,
        adb: ADB,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb
        self._fixer = PlayIntegrityFixer(adb=adb)
        self._current_device: Optional[DeviceInfo] = None
        self._diagnostic: Optional[IntegrityDiagnostic] = None
        self._selected_profile: FingerprintProfile = BUILTIN_PROFILES[0]

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)

        # -------------------------------------------------------------
        # Header Row
        # -------------------------------------------------------------
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        header_icon = create_icon_label("integrity", 24)
        header_row.addWidget(header_icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Play Integrity Fixer & Fingerprint Spoofer")
        title.setProperty("cssClass", "heading")
        title.setStyleSheet("font-size: 18px; font-weight: 700;")
        title_box.addWidget(title)

        self._subtitle = QLabel(
            "Diagnose Play Integrity status, inject certified fingerprints, and protect banking apps."
        )
        self._subtitle.setStyleSheet("color: #8E8E93; font-size: 12px;")
        title_box.addWidget(self._subtitle)
        header_row.addLayout(title_box, 1)

        self._redetect_btn = QPushButton("Re-Diagnose")
        self._redetect_btn.setIcon(get_icon("refresh", 14))
        self._redetect_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._redetect_btn.setStyleSheet(
            "QPushButton { background-color: rgba(10, 132, 255, 0.12); color: #0A84FF; "
            "border: 1px solid rgba(10, 132, 255, 0.3); border-radius: 8px; padding: 6px 14px; font-weight: 600; } "
            "QPushButton:hover { background-color: rgba(10, 132, 255, 0.22); }"
        )
        self._redetect_btn.clicked.connect(self._run_diagnostics)
        header_row.addWidget(self._redetect_btn)

        layout.addLayout(header_row)

        # -------------------------------------------------------------
        # Diagnostics Verdict Cards (Basic, Device, Strong, System State)
        # -------------------------------------------------------------
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(12)

        self._card_basic = self._create_verdict_card(
            "Basic Integrity", "MEETS_BASIC_INTEGRITY", "Checking...", "Basic OS and bootloader checks"
        )
        self._card_device = self._create_verdict_card(
            "Device Integrity", "MEETS_DEVICE_INTEGRITY", "Checking...", "Certified profile & CTS verification"
        )
        self._card_strong = self._create_verdict_card(
            "Strong Integrity", "MEETS_STRONG_INTEGRITY", "Hardware Locked", "Requires factory locked Keystore"
        )
        self._card_sys = self._create_verdict_card(
            "System & Root State", "Security Environment", "No Device", "Bootloader, SELinux & Zygisk"
        )

        cards_layout.addWidget(self._card_basic["frame"], 1)
        cards_layout.addWidget(self._card_device["frame"], 1)
        cards_layout.addWidget(self._card_strong["frame"], 1)
        cards_layout.addWidget(self._card_sys["frame"], 1)
        layout.addLayout(cards_layout)

        # -------------------------------------------------------------
        # Tabbed Workstation: Fingerprint Injector / Banking Guard / Guide
        # -------------------------------------------------------------
        self._tabs = QTabWidget()
        self._tab_injector = QWidget()
        self._tab_banking = QWidget()
        self._tab_guide = QWidget()

        self._setup_injector_tab()
        self._setup_banking_tab()
        self._setup_guide_tab()

        self._tabs.addTab(self._tab_injector, get_icon("root", 16), "Fingerprint Vault & Injector")
        self._tabs.addTab(self._tab_banking, get_icon("shield", 16), "Banking & Root Hiding Guard")
        self._tabs.addTab(self._tab_guide, get_icon("book", 16), "Integrity Architecture Guide")

        layout.addWidget(self._tabs, 1)

    # -----------------------------------------------------------------
    # Verdict Card Builder & Updaters
    # -----------------------------------------------------------------

    def _create_verdict_card(self, title: str, subtitle: str, initial_val: str, desc: str) -> dict:
        frame = QFrame()
        frame.setFixedHeight(70)
        frame.setStyleSheet(
            "QFrame { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); "
            "border-radius: 10px; padding: 6px 12px; }"
        )
        vbox = QVBoxLayout(frame)
        vbox.setContentsMargins(10, 6, 10, 6)
        vbox.setSpacing(2)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 10px; font-weight: 700; color: #8E8E93; text-transform: uppercase;")
        top_row.addWidget(t_lbl, 1)

        val_lbl = QLabel(initial_val)
        val_lbl.setStyleSheet("font-size: 13px; font-weight: 800; color: #FFFFFF;")
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top_row.addWidget(val_lbl)
        vbox.addLayout(top_row)

        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("font-size: 10.5px; color: #8E8E93;")
        desc_lbl.setWordWrap(True)
        vbox.addWidget(desc_lbl)

        return {"frame": frame, "title": t_lbl, "value": val_lbl, "desc": desc_lbl}

    def _update_card_verdict(self, card: dict, verdict: str, note: str = "") -> None:
        v_upper = verdict.upper()
        if "PASS" in v_upper:
            color = "#30D158"  # Apple HIG Green
            icon = "PASS"
        elif "FAIL" in v_upper:
            color = "#FF453A"  # Apple HIG Red
            icon = "FAIL"
        elif "WARNING" in v_upper or "WARN" in v_upper:
            color = "#FF9F0A"  # Apple HIG Orange
            icon = "WARNING"
        else:
            color = "#8E8E93"  # Gray
            icon = f"{verdict}"

        card["value"].setText(icon)
        card["value"].setStyleSheet(f"font-size: 13px; font-weight: 800; color: {color};")
        if note:
            card["desc"].setText(note)

    # -----------------------------------------------------------------
    # Tab 1: Fingerprint Vault & Injector
    # -----------------------------------------------------------------

    def _setup_injector_tab(self) -> None:
        c_layout = QHBoxLayout(self._tab_injector)
        c_layout.setContentsMargins(12, 12, 12, 12)
        c_layout.setSpacing(14)

        # Left Column: Profile Selector & Table
        left_col = QVBoxLayout()
        left_col.setSpacing(10)

        # Profile Selector Box
        profile_box = QGroupBox("1. Select Verified Certified Fingerprint")
        profile_box.setStyleSheet("font-weight: 600; font-size: 13px;")
        pb_layout = QVBoxLayout(profile_box)
        pb_layout.setContentsMargins(12, 14, 12, 12)
        pb_layout.setSpacing(8)

        sel_row = QHBoxLayout()
        sel_row.setSpacing(8)

        lbl = QLabel("Profile:")
        lbl.setStyleSheet("font-size: 12px; font-weight: 600;")
        sel_row.addWidget(lbl)

        self._profile_combo = QComboBox()
        self._profile_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._profile_combo.setMinimumHeight(30)
        for p in BUILTIN_PROFILES:
            self._profile_combo.addItem(f"{p.name} (API {p.first_api_level})", p.id)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_selected)
        sel_row.addWidget(self._profile_combo, 1)

        import_btn = QPushButton("Import")
        import_btn.setIcon(get_icon("folder", 13))
        import_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        import_btn.setToolTip("Import a custom pif.json from your computer")
        import_btn.clicked.connect(self._import_pif_file)
        sel_row.addWidget(import_btn)

        export_btn = QPushButton("Export")
        export_btn.setIcon(get_icon("folder", 13))
        export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        export_btn.setToolTip("Save the current profile configuration to a local pif.json")
        export_btn.clicked.connect(self._export_pif_file)
        sel_row.addWidget(export_btn)

        pb_layout.addLayout(sel_row)

        # Profile Properties Table
        self._props_table = QTableWidget()
        self._props_table.setColumnCount(2)
        self._props_table.setHorizontalHeaderLabels(["Property", "Spoofed Value"])
        self._props_table.horizontalHeader().setStretchLastSection(True)
        self._props_table.verticalHeader().setVisible(False)
        self._props_table.setAlternatingRowColors(True)
        self._props_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        pb_layout.addWidget(self._props_table, 1)

        left_col.addWidget(profile_box, 1)
        c_layout.addLayout(left_col, 1)

        # Right Column: Raw Preview & Injection Actions
        right_col = QVBoxLayout()
        right_col.setSpacing(10)

        # Raw JSON Editor Toggle & Area
        json_box = QGroupBox("2. pif.json Preview & Editor")
        json_box.setStyleSheet("font-weight: 600; font-size: 13px;")
        jb_layout = QVBoxLayout(json_box)
        jb_layout.setContentsMargins(12, 14, 12, 12)
        jb_layout.setSpacing(6)

        self._json_edit = QPlainTextEdit()
        self._json_edit.setStyleSheet(
            "font-family: Consolas, 'Courier New', monospace; font-size: 11.5px; "
            "background-color: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 6px; padding: 6px;"
        )
        jb_layout.addWidget(self._json_edit, 1)
        right_col.addWidget(json_box, 1)

        # Injection Action Area
        action_box = QGroupBox("3. Device Injection & Cache Reset")
        action_box.setStyleSheet("font-weight: 600; font-size: 13px;")
        ab_layout = QVBoxLayout(action_box)
        ab_layout.setContentsMargins(12, 14, 12, 12)
        ab_layout.setSpacing(8)

        self._clear_cache_cb = QCheckBox("Automatically kill GMS background processes and flush Play Services cache")
        self._clear_cache_cb.setChecked(True)
        self._clear_cache_cb.setStyleSheet("font-size: 12px;")
        ab_layout.addWidget(self._clear_cache_cb)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)

        self._inject_btn = QPushButton("Apply & Inject pif.json")
        self._inject_btn.setIcon(get_icon("rocket", 14))
        self._inject_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._inject_btn.setMinimumHeight(36)
        self._inject_btn.setStyleSheet(
            "QPushButton { background-color: #30D158; color: #FFFFFF; font-weight: 700; font-size: 12.5px; "
            "border-radius: 8px; padding: 6px 16px; } "
            "QPushButton:hover { background-color: #28B94E; } "
            "QPushButton:disabled { background-color: #2C2C2E; color: #555558; }"
        )
        self._inject_btn.clicked.connect(self._inject_pif)
        btn_row.addWidget(self._inject_btn, 1)

        self._flush_cache_btn = QPushButton("Flush GMS Cache")
        self._flush_cache_btn.setIcon(get_icon("trash", 14))
        self._flush_cache_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._flush_cache_btn.setMinimumHeight(36)
        self._flush_cache_btn.setStyleSheet(
            "QPushButton { background-color: rgba(255, 159, 10, 0.15); color: #FF9F0A; font-weight: 600; "
            "border: 1px solid rgba(255, 159, 10, 0.3); border-radius: 8px; padding: 6px 12px; } "
            "QPushButton:hover { background-color: rgba(255, 159, 10, 0.25); }"
        )
        self._flush_cache_btn.clicked.connect(self._clear_gms_cache)
        btn_row.addWidget(self._flush_cache_btn)

        self._read_pif_btn = QPushButton("Read Active")
        self._read_pif_btn.setIcon(get_icon("refresh", 14))
        self._read_pif_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._read_pif_btn.setMinimumHeight(36)
        self._read_pif_btn.setStyleSheet(
            "QPushButton { background-color: rgba(255, 255, 255, 0.08); color: #FFFFFF; font-weight: 600; "
            "border: 1px solid rgba(255, 255, 255, 0.15); border-radius: 8px; padding: 6px 12px; } "
            "QPushButton:hover { background-color: rgba(255, 255, 255, 0.15); }"
        )
        self._read_pif_btn.clicked.connect(self._read_active_pif)
        btn_row.addWidget(self._read_pif_btn)

        ab_layout.addLayout(btn_row)

        self._inject_log_lbl = QLabel("Ready. Select a profile and click 'Apply & Inject pif.json'.")
        self._inject_log_lbl.setStyleSheet("font-size: 11px; color: #8E8E93;")
        self._inject_log_lbl.setWordWrap(True)
        ab_layout.addWidget(self._inject_log_lbl)

        right_col.addWidget(action_box)
        c_layout.addLayout(right_col, 1)

        # Initial populate
        self._populate_profile_table(self._selected_profile)

    # -----------------------------------------------------------------
    # Tab 2: Banking & App Protection (DenyList)
    # -----------------------------------------------------------------

    def _setup_banking_tab(self) -> None:
        outer_lay = QVBoxLayout(self._tab_banking)
        outer_lay.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        desc = QLabel(
            "Prevent banking, payments, and high-security apps from detecting unlocked bootloaders or root.\n"
            "FlashDock configures Magisk DenyList / Zygisk process unmounting for maximum stealth."
        )
        desc.setStyleSheet("color: #8E8E93; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Quick Add Group
        quick_box = QGroupBox("Recommended Apps Protection")
        quick_box.setStyleSheet("font-weight: 600; font-size: 13px;")
        qb_layout = QVBoxLayout(quick_box)
        qb_layout.setContentsMargins(12, 16, 12, 12)
        qb_layout.setSpacing(10)

        grid = QGridLayout()
        grid.setSpacing(10)

        cols = 2
        for idx, (pkg, name) in enumerate(RECOMMENDED_PROTECTED_PACKAGES):
            app_card = QFrame()
            app_card.setStyleSheet(
                "QFrame { background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.1); "
                "border-radius: 8px; padding: 6px 10px; min-height: 44px; }"
            )
            c_lay = QHBoxLayout(app_card)
            c_lay.setContentsMargins(6, 4, 6, 4)
            c_lay.setSpacing(8)

            info_col = QVBoxLayout()
            info_col.setSpacing(1)
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #FFFFFF;")
            pkg_lbl = QLabel(pkg)
            pkg_lbl.setStyleSheet("font-size: 10px; color: #8E8E93;")
            info_col.addWidget(name_lbl)
            info_col.addWidget(pkg_lbl)
            c_lay.addLayout(info_col, 1)

            btn = QPushButton("Protect")
            btn.setIcon(get_icon("shield", 12))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton { background-color: rgba(10, 132, 255, 0.15); color: #0A84FF; font-weight: 600; font-size: 11px; "
                "border: 1px solid rgba(10, 132, 255, 0.3); border-radius: 6px; padding: 5px 12px; } "
                "QPushButton:hover { background-color: #0A84FF; color: #FFFFFF; }"
            )
            btn.clicked.connect(lambda _, p=pkg: self._add_denylist_pkg(p))
            c_lay.addWidget(btn)

            r = idx // cols
            c_idx = idx % cols
            grid.addWidget(app_card, r, c_idx)

        qb_layout.addLayout(grid)
        layout.addWidget(quick_box)

        # Custom package add
        custom_box = QGroupBox("Add Custom Package to DenyList")
        custom_box.setStyleSheet("font-weight: 600; font-size: 13px;")
        cb_layout = QHBoxLayout(custom_box)
        cb_layout.setContentsMargins(12, 16, 12, 12)
        cb_layout.setSpacing(10)

        self._custom_pkg_input = QLineEdit()
        self._custom_pkg_input.setPlaceholderText("Enter Android package name (e.g. com.starlingbank.android)")
        self._custom_pkg_input.setMinimumHeight(36)
        cb_layout.addWidget(self._custom_pkg_input, 1)

        add_custom_btn = QPushButton("Add to DenyList")
        add_custom_btn.setIcon(get_icon("plus", 14))
        add_custom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        add_custom_btn.setStyleSheet(
            "QPushButton { background-color: #0A84FF; color: #FFFFFF; font-weight: 600; "
            "border-radius: 6px; padding: 8px 16px; min-height: 20px; } "
            "QPushButton:hover { background-color: #0071E3; }"
        )
        add_custom_btn.clicked.connect(self._add_custom_denylist_pkg)
        cb_layout.addWidget(add_custom_btn)

        layout.addWidget(custom_box)

        # Log
        self._banking_log = QLabel("Ready. Click any app above to add it to Magisk DenyList.")
        self._banking_log.setStyleSheet("font-size: 12px; color: #8E8E93;")
        self._banking_log.setWordWrap(True)
        layout.addWidget(self._banking_log)

        layout.addStretch(1)
        scroll.setWidget(container)
        outer_lay.addWidget(scroll)

    # -----------------------------------------------------------------
    # Tab 3: Guide & Architecture
    # -----------------------------------------------------------------

    def _setup_guide_tab(self) -> None:
        layout = QVBoxLayout(self._tab_guide)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(14)

        guide_cards = [
            (
                "Play Integrity Verdicts Explained",
                "1. MEETS_BASIC_INTEGRITY: Device runs genuine Android without known tampering.\n"
                "2. MEETS_DEVICE_INTEGRITY: Device matches CTS certified Google build. Passing this restores Google Wallet contactless payments, banking logins, and Play Store certification.\n"
                "3. MEETS_STRONG_INTEGRITY: Enforced via hardware keystore attestation in the TEE/Titan chip. Once the bootloader is unlocked, hardware keys report unlocked state. (Passing Basic + Device is sufficient for 99.9% of all banking apps!).",
            ),
            (
                "Why FIRST_API_LEVEL <= 32 Triggers Software Attestation",
                "Google introduced mandatory hardware-backed key attestation starting with Android 13 (API 33).\n"
                "By spoofing build properties of certified stock devices launched on Android 12 or older (such as Pixel 5 or POCO F1), Google Play Services is forced to fallback to software-backed key evaluation, successfully passing MEETS_DEVICE_INTEGRITY even on unlocked bootloaders!",
            ),
            (
                "Recommended Stealth Setup for Maximum Compatibility",
                "1. Root via Magisk (Zygisk enabled) or KernelSU / APatch.\n"
                "2. Install PlayIntegrityFix module (chiteroman) or PlayIntegrityNext.\n"
                "3. Inject a certified fingerprint using FlashDock's Fingerprint Vault.\n"
                "4. Clear Google Play Services cache (handled automatically by FlashDock).\n"
                "5. Enable Shamiko module or configure Magisk DenyList for banking apps.",
            ),
        ]

        for title, text in guide_cards:
            box = QFrame()
            box.setStyleSheet(
                "background-color: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.08); "
                "border-radius: 10px; padding: 14px;"
            )
            b_layout = QVBoxLayout(box)
            b_layout.setSpacing(6)

            t = QLabel(title)
            t.setStyleSheet("font-size: 13px; font-weight: 700; color: #FFFFFF;")
            b_layout.addWidget(t)

            b = QLabel(text)
            b.setStyleSheet("font-size: 12px; color: #8E8E93; line-height: 1.4;")
            b.setWordWrap(True)
            b_layout.addWidget(b)

            c_layout.addWidget(box)

        c_layout.addStretch(1)
        scroll.setWidget(container)
        layout.addWidget(scroll)

    # -----------------------------------------------------------------
    # Logic & Event Handlers
    # -----------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Called by MainWindow when device state changes or screen is opened."""
        self._current_device = device
        self._run_diagnostics()

    def _run_diagnostics(self) -> None:
        """Run ADB diagnostics on connected device."""
        self._diagnostic = self._fixer.diagnose_device(self._current_device)
        diag = self._diagnostic

        # Update cards
        if not self._current_device or self._current_device.mode == "not_connected":
            self._subtitle.setText("No device connected. Connect phone via USB debugging.")
            self._update_card_verdict(self._card_basic, "Unknown", "Connect phone via USB")
            self._update_card_verdict(self._card_device, "Unknown", "Connect phone via USB")
            self._card_sys["value"].setText("Disconnected")
            self._card_sys["desc"].setText("Plug in USB cable to analyze")
            return

        self._subtitle.setText(
            f"Device: {self._current_device.model} ({self._current_device.serial}) · "
            f"Bootloader: {diag.bootloader_status} · SELinux: {diag.selinux_status} · Root: {diag.root_type}"
        )

        self._update_card_verdict(
            self._card_basic,
            diag.verdict_basic,
            "SELinux Enforcing" if diag.selinux_status.lower() == "enforcing" else f"SELinux {diag.selinux_status}",
        )

        dev_note = "Certified Fingerprint Active" if (diag.pif_module_installed or diag.custom_pif_active) else "Unlocked BL (Needs Spoof)"
        self._update_card_verdict(self._card_device, diag.verdict_device, dev_note)

        # System state card
        self._card_sys["value"].setText(f"BL: {diag.bootloader_status}")
        self._card_sys["desc"].setText(f"Root: {diag.root_type} | Zygisk: {'Active' if diag.zygisk_active else 'Off'}")

        if diag.custom_pif_active:
            self._inject_log_lbl.setText(
                f"Active pif.json detected on device: {diag.current_spoofed_model or 'Custom build'}"
            )

    def _populate_profile_table(self, profile: FingerprintProfile) -> None:
        """Populate the properties table and raw JSON editor with profile details."""
        p_dict = profile.to_pif_dict()
        self._props_table.setRowCount(len(p_dict))
        for row, (k, v) in enumerate(p_dict.items()):
            item_k = QTableWidgetItem(k)
            item_k.setFlags(item_k.flags() & ~Qt.ItemFlag.ItemIsEditable)
            item_v = QTableWidgetItem(str(v))
            item_v.setFlags(item_v.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self._props_table.setItem(row, 0, item_k)
            self._props_table.setItem(row, 1, item_v)

        self._json_edit.setPlainText(profile.to_pif_json(indent=2))

    def _on_profile_selected(self, index: int) -> None:
        """Handle dropdown selection of a built-in profile."""
        if 0 <= index < len(BUILTIN_PROFILES):
            self._selected_profile = BUILTIN_PROFILES[index]
            self._populate_profile_table(self._selected_profile)

    def _import_pif_file(self) -> None:
        """Import a custom pif.json from file system."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import custom pif.json",
            "",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return

        try:
            content = Path(path).read_text(encoding="utf-8")
            parsed = json.loads(content)
            if not isinstance(parsed, dict) or "FINGERPRINT" not in parsed:
                QMessageBox.warning(self, "Invalid Format", "pif.json must be a JSON object containing 'FINGERPRINT'.")
                return

            self._json_edit.setPlainText(json.dumps(parsed, indent=2))
            # Populate table from parsed
            self._props_table.setRowCount(len(parsed))
            for row, (k, v) in enumerate(parsed.items()):
                item_k = QTableWidgetItem(str(k))
                item_v = QTableWidgetItem(str(v))
                self._props_table.setItem(row, 0, item_k)
                self._props_table.setItem(row, 1, item_v)

            self._inject_log_lbl.setText(f"Imported custom pif.json from: {Path(path).name}")
            log.info("Imported pif.json from %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Import Error", f"Failed to parse JSON file:\n{exc}")

    def _export_pif_file(self) -> None:
        """Export current pif.json to disk."""
        content = self._json_edit.toPlainText().strip()
        if not content:
            QMessageBox.warning(self, "Empty Profile", "No pif.json content to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save pif.json",
            "pif.json",
            "JSON Files (*.json);;All Files (*.*)",
        )
        if not path:
            return

        try:
            Path(path).write_text(content, encoding="utf-8")
            QMessageBox.information(self, "Saved", f"Exported pif.json successfully to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{exc}")

    def _inject_pif(self) -> None:
        """Apply and write pif.json to device /data/adb/pif.json."""
        if not self._current_device or self._current_device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect an Android device in System mode.")
            return

        json_str = self._json_edit.toPlainText().strip()
        clear_gms = self._clear_cache_cb.isChecked()

        self._inject_log_lbl.setText("Injecting pif.json to device...")
        self._inject_btn.setEnabled(False)

        def _do_inject() -> None:
            ok, msg = self._fixer.inject_pif_json(
                serial=self._current_device.serial,
                pif_json_str=json_str,
                clear_gms=clear_gms,
            )
            self._inject_btn.setEnabled(True)
            if ok:
                self._inject_log_lbl.setText(f"{msg}")
                QMessageBox.information(self, "Injection Successful", msg)
                self._run_diagnostics()
            else:
                self._inject_log_lbl.setText(f"Injection Failed: {msg}")
                QMessageBox.warning(self, "Injection Failed", msg)

        QTimer.singleShot(50, _do_inject)

    def _clear_gms_cache(self) -> None:
        """Flush Google Play Services cache."""
        if not self._current_device or self._current_device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect an Android device in System mode.")
            return

        ok, msg = self._fixer.clear_gms_cache(self._current_device.serial)
        if ok:
            self._inject_log_lbl.setText(f"{msg}")
            QMessageBox.information(self, "GMS Cache Cleared", msg)
        else:
            self._inject_log_lbl.setText(f"{msg}")
            QMessageBox.warning(self, "Cache Flush Error", msg)

    def _read_active_pif(self) -> None:
        """Read active /data/adb/pif.json from device."""
        if not self._current_device or self._current_device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect an Android device.")
            return

        pif_data = self._fixer.read_device_pif(self._current_device.serial)
        if pif_data:
            self._json_edit.setPlainText(json.dumps(pif_data, indent=2))
            self._props_table.setRowCount(len(pif_data))
            for row, (k, v) in enumerate(pif_data.items()):
                self._props_table.setItem(row, 0, QTableWidgetItem(str(k)))
                self._props_table.setItem(row, 1, QTableWidgetItem(str(v)))
            self._inject_log_lbl.setText(f"Loaded active pif.json from device ({pif_data.get('MODEL', 'Custom')})")
        else:
            self._inject_log_lbl.setText("No active /data/adb/pif.json found on device (or root denied).")
            QMessageBox.information(
                self,
                "No Custom pif.json",
                "No custom pif.json was found on /data/adb/pif.json on this device.\n"
                "You can inject one of the built-in profiles above.",
            )

    def _add_denylist_pkg(self, package_name: str) -> None:
        """Add package to Magisk DenyList."""
        if not self._current_device or self._current_device.mode == "not_connected":
            QMessageBox.warning(self, "No Device", "Please connect an Android device in System mode.")
            return

        ok, msg = self._fixer.add_package_to_denylist(self._current_device.serial, package_name)
        if ok:
            self._banking_log.setText(f"{msg}")
        else:
            self._banking_log.setText(f"{msg}")

    def _add_custom_denylist_pkg(self) -> None:
        """Add custom package entered in line edit."""
        pkg = self._custom_pkg_input.text().strip()
        if not pkg:
            QMessageBox.warning(self, "Missing Package", "Please enter a valid Android package name.")
            return
        self._add_denylist_pkg(pkg)
        self._custom_pkg_input.clear()
