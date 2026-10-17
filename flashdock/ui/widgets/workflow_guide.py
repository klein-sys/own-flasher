"""
FlashDock — Interactive Workflow & Function Guide Dialog.

Comprehensive guide showing how to use each of the 16 workstation functions,
the recommended safe flashing workflow, and how Android flashing works
under the hood to guarantee zero-brick operations.

Spec reference: Section 29 (User Additions) & Phase 24 / v1.3.3.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.ui.icon_assets import create_icon_label, get_icon, get_icon_pixmap


class WorkflowGuideDialog(QDialog):
    """Interactive modal guide detailing workflows, function references, and launchable action cards."""

    action_requested = Signal(str)

    _CATEGORY_COLORS = {
        "DEVICE": ("rgba(48, 209, 88, 0.18)", "#30D158"),
        "ROOT": ("rgba(191, 90, 242, 0.18)", "#BF5AF2"),
        "FLASHING": ("rgba(10, 132, 255, 0.18)", "#0A84FF"),
        "RESCUE": ("rgba(255, 69, 58, 0.18)", "#FF453A"),
    }

    _FUNCTION_GUIDE_DATA = [
        (
            "check_phone",
            "search",
            "Check my phone",
            "DEVICE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00E5FF, stop:1 #0097A7)",
            "Dispatches ADB shell getprop inspection and Fastboot getvar commands to query hardware architecture, partition slot scheme (A/B vs Virtual A/B), dynamic partitions support, Knox warranty bit, and real-time battery telemetry.",
            "1. Connect phone via USB with USB Debugging enabled in Developer Options.<br>2. If phone is in Fastboot mode, FlashDock will detect fastboot serial automatically.<br>3. Review chipset, slot scheme, and unlock status before flashing any images.",
            "Always use a direct USB 2.0/3.0 port on your computer motherboard (avoid unpowered USB hubs). Never disconnect cable during fastboot query operations.",
        ),
        (
            "checklist",
            "checklist",
            "Safety Checklist",
            "RESCUE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #059669, stop:1 #047857)",
            "Automated 18-step pre-flight diagnostic suite. Verifies device battery (≥ 60%), OEM unlocking developer toggle, USB driver handshakes, storage free space (≥ 2 GB), and active backup directories.",
            "1. Connect phone via USB debugging in normal System mode.<br>2. Click 'Run Pre-Flight Check' to evaluate all 18 safety checkpoints.<br>3. Inspect results: any red failures must be resolved before proceeding with root or flashing.",
            "Never bypass a failing battery check (< 60%). If a device loses power during partition writes, it can result in a hard brick.",
        ),
        (
            "unlock_bl",
            "unlock",
            "Unlock Bootloader",
            "FLASHING",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F59E0B, stop:1 #D97706)",
            "Dispatches brand-aware bootloader unlock sequences: Google Pixel ('fastboot flashing unlock'), Xiaomi Mi Unlock token guides, Motorola OEM unlock data codes, and Samsung Download mode OEM key steps.",
            "1. In phone Settings > Developer Options, enable 'OEM Unlocking' and 'USB Debugging'.<br>2. Reboot device into Bootloader / Fastboot mode.<br>3. Select your phone brand in FlashDock and click 'Begin Bootloader Unlock'.<br>4. Confirm the prompt on device screen using Volume keys and Power button.",
            "Unlocking the bootloader FACTORY RESETS the device and erases all internal storage. Always back up contacts, photos, and WhatsApp messages first.",
        ),
        (
            "root",
            "root",
            "Root my phone",
            "ROOT",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #A855F7, stop:1 #7E22CE)",
            "Detects Android OS version and kernel GKI scheme. On Android 13+ GKI kernels, safely targets init_boot.img; on older versions, targets boot.img. Extracts, patches via Magisk / KernelSU / APatch, and flashes cleanly.",
            "1. Ensure bootloader is already unlocked.<br>2. Select stock boot.img or init_boot.img matching your current build number.<br>3. Select preferred rooting framework (Magisk / KernelSU / APatch).<br>4. Click 'Root Device' and allow FlashDock to patch and flash the kernel.",
            "FlashDock automatically dumps a pre-root backup to data/backups/. Never flash a boot image from a different model or firmware build number.",
        ),
        (
            "flash_rom",
            "flash",
            "Flash ROM / GSI",
            "FLASHING",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563EB, stop:1 #1D4ED8)",
            "Chunked flashing engine for full custom ROM zip/tar packages, dynamic partition images (system, vendor, product via FastbootD), Treble GSIs (ARM64 A/B), and custom recoveries (TWRP/OrangeFox).",
            "1. Reboot device into Fastboot or FastbootD mode.<br>2. Choose target image (.img) or package (.zip).<br>3. Select target partition and slot (_a or _b).<br>4. Click 'Begin Flash' and wait for checksum verification and reboot prompt.",
            "For dynamic partitions (Android 10+), ensure phone is in FastbootD mode (screen reads 'FastbootD'). Flashing dynamic partitions in regular bootloader mode will fail.",
        ),
        (
            "modules",
            "modules",
            "Manage Modules",
            "ROOT",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EC4899, stop:1 #BE185D)",
            "Direct interface to Magisk, KernelSU, and APatch module paths (/data/adb/modules). Sideloads module ZIPs, toggles active status, reads module.prop descriptions, and features an Emergency Bootloop Kill-Switch.",
            "1. Connect rooted device in normal System mode with ADB authorized.<br>2. Browse active modules or click 'Install Module ZIP'.<br>3. Toggle switch next to any module to disable or uninstall.<br>4. Reboot device to apply changes.",
            "If an incompatible module causes a bootloop, reboot into Safe Mode or click 'Emergency Module Disable' from FlashDock's Unbrick menu.",
        ),
        (
            "diagnostics",
            "diagnostics",
            "Diagnostics & Tweaks",
            "DEVICE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00B4D8, stop:1 #0077B6)",
            "Non-root system tuning and telemetry diagnostics. Safely disables OEM and carrier bloatware via pm uninstall -k --user 0, queries battery cycle count and health, and adjusts UI animation scales.",
            "1. Connect device in normal System mode via ADB.<br>2. Choose Debloat preset (Safe / Aggressive / Custom).<br>3. Review list of carrier packages and click 'Apply Debloat'.<br>4. Adjust animation scale sliders for immediate UI responsiveness boost.",
            "Only disable packages listed under the Safe preset unless you are experienced. Disabling critical telephony or system UI services can trigger bootloops.",
        ),
        (
            "sideload",
            "box",
            "Sideload & App Manager",
            "DEVICE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #00C6FF, stop:1 #0072FF)",
            "Multi-package installer for APKs, split XAPKs, APKS, and recovery OTA ZIPs. Bypasses Android 14 minimum target SDK install restrictions (--bypass-low-target-sdk-block) and grants all runtime permissions (-g).",
            "1. In System mode: drag-and-drop any APK/XAPK to install or uninstall packages.<br>2. In Recovery mode: select 'Apply update from ADB' on phone, choose the OTA ZIP file in FlashDock, and click 'Start Sideload'.",
            "Never unplug USB cable during recovery OTA sideloading. Allow device screen to show 'Installation completed' before rebooting.",
        ),
        (
            "integrity",
            "integrity",
            "Fix Play Integrity",
            "ROOT",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #3B82F6, stop:1 #1E40AF)",
            "Play Integrity API attestation engine. Queries BASIC, DEVICE, and STRONG verdicts. Guides installation of PlayIntegrityFix, TrickyStore, and Shamiko with certified OEM device fingerprint profiles.",
            "1. Verify device is rooted with Zygisk enabled.<br>2. Click 'Run Integrity Diagnostics' to view current pass/fail status.<br>3. Apply recommended custom pif.json fingerprint profile or install module.<br>4. Clear Google Play Services storage and re-test.",
            "Google periodically revokes leaked fingerprint models. FlashDock allows you to import updated pif.json configs without having to reinstall your root modules.",
        ),
        (
            "backup",
            "backup",
            "Backup / Restore",
            "RESCUE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F97316, stop:1 #C2410C)",
            "Raw block partition dumping engine. Dumps critical calibration and radio blocks (efs, nvram, nvdata, persist, sec_efs) and takes full user data snapshots via ADB backup with SHA-256 validation.",
            "1. Connect device with ADB debugging authorized.<br>2. Choose backup scope: Calibration (EFS/NVRAM), Core Partitions (Boot/Recovery), or User Data.<br>3. Click 'Start Backup' and save backup archive locally.<br>4. Use Restore tab for 1-click recovery.",
            "Always dump an EFS/NVRAM backup before flashing any custom ROM or radio modem firmware. Losing EFS permanently erases your device IMEI.",
        ),
        (
            "unbrick",
            "unbrick",
            "Fix bricked phone",
            "RESCUE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EF4444, stop:1 #B91C1C)",
            "Emergency rescue station for bootloops, soft bricks, and corrupted slots. Offers 1-click slot switching (fastboot --set-active=other), AVB verification bypass (fastboot --disable-verity --disable-verification flash vbmeta), and module kill-switches.",
            "1. Force phone into Fastboot mode by holding Volume Down + Power.<br>2. Connect to PC and verify serial detection.<br>3. Try 'Switch Active A/B Slot' first to boot into the untouched slot.<br>4. If stuck on verification, flash clean vbmeta with AVB disabled.",
            "Try slot switching before wiping user data. A failed OTA update frequently leaves the alternate slot fully functional and bootable.",
        ),
        (
            "return_stock",
            "return_stock",
            "Return to Stock",
            "FLASHING",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0284C7, stop:1 #0369A1)",
            "Full factory restore engine. Extracts official OEM firmware (Google factory zip, Xiaomi fastboot tgz, Samsung Odin tar.md5, Motorola fastboot XML), flashes stock partitions cleanly, and validates integrity before safe relock.",
            "1. Download official stock firmware matching your exact model and regional code.<br>2. Select firmware archive in FlashDock.<br>3. Review partition flashing script and click 'Flash Stock Firmware'.<br>4. Allow phone to boot into stock OS once before relocking bootloader.",
            "NEVER relock the bootloader while running a custom ROM or modified boot image! Doing so will trigger AVB verification failure and permanently hard-brick the device.",
        ),
        (
            "mtk_unisoc",
            "mtk_unisoc",
            "MTK / Unisoc mode",
            "FLASHING",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #EA580C, stop:1 #C2410C)",
            "Low-level emergency hardware flashing engine. For MediaTek: uses BROM mode (0E8D:0003) with MTKClient / Preloader handshake to bypass SLA/DA and flash scatter files. For Unisoc: interfaces via FDL1/FDL2 to flash PAC packages.",
            "1. Power off device completely.<br>2. Load MTK scatter file or Unisoc PAC firmware archive.<br>3. Hold hardware test point or Volume buttons and insert USB cable to enter BROM / FDL mode.<br>4. FlashDock detects the COM serial port and writes partitions directly.",
            "Requires specialized low-level USB drivers. Use the 'Setup Laptop' wizard to ensure MediaTek VCOM and Unisoc SPRD drivers are installed.",
        ),
        (
            "scrcpy",
            "scrcpy",
            "Screen Mirror (scrcpy)",
            "DEVICE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6366F1, stop:1 #4338CA)",
            "Integrated high-speed screen mirroring and workstation control via scrcpy. Forwards video (H.264/H.265), audio stream, clipboard sync, and mouse/keyboard touch input over ADB with ultra-low latency.",
            "1. Connect phone via USB debugging in normal System mode.<br>2. Select display resolution, bit rate, and options (e.g. stay awake, screen off).<br>3. Click 'Launch Screen Mirror' to control device directly from your PC desktop.",
            "Screen mirroring requires normal System mode with ADB authorized. It is not available in Bootloader or Recovery mode.",
        ),
        (
            "downloads",
            "downloads",
            "Downloads & Tools",
            "DEVICE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #10B981, stop:1 #059669)",
            "Integrated toolchain and firmware repository downloader. Installs and updates Android platform-tools (adb, fastboot), OEM USB drivers (Google, Samsung, Xiaomi, Motorola, Qualcomm 9008, MTK VCOM), and Magisk/KernelSU binaries.",
            "1. Ensure computer has active internet connection.<br>2. Select required tool, driver, or recovery image.<br>3. Click 'Install' or 'Update' to download, verify SHA-256 hash, and deploy directly into FlashDock's toolchain directory.",
            "If Qualcomm 9008 or MediaTek COM ports display a yellow warning mark in Windows Device Manager, reinstall drivers from this menu.",
        ),
        (
            "logs_help",
            "logs_help",
            "Logs & Help",
            "DEVICE",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #8B5CF6, stop:1 #6D28D9)",
            "Real-time workstation activity log with automatic serial number and IMEI sanitization for privacy. Includes interactive troubleshooting guides and 1-click diagnostic report export.",
            "1. View real-time console logs and error streams.<br>2. Click 'Export Sanitized Log' to save a shareable log file without leaking private serial numbers.<br>3. Consult built-in troubleshooting guides for step-by-step solutions to common errors.",
            "When asking for assistance online or on forums, always share sanitized logs rather than raw output to protect your hardware identifiers.",
        ),
        (
            "unisoc_unlock",
            "unlock",
            "Unisoc & Transsion Unlock",
            "FLASHING",
            "qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #F97316, stop:1 #EA580C)",
            "Pure-Python RSA-2048 PKCS#1 v1.5 token signer and Anti-Red-State vbmeta patcher. Generates signature.bin from 'fastboot oem get_identifier_token' and patches vbmeta flags to disable verification for Infinix, Tecno, itel, and Unisoc hardware.",
            "1. Obtain identifier token in Fastboot: fastboot oem get_identifier_token.<br>2. Paste token into Unisoc Unlocker card and load private RSA key (or use default).<br>3. Flash generated signature.bin with 'fastboot flashing unlock_bootloader signature.bin'.<br>4. Select stock vbmeta.img and click 'Patch vbmeta' to disable flags 0x01/0x02 and prevent bootloop Red State.",
            "Always patch vbmeta before booting custom GSI images on Unisoc devices to permanently neutralize DM-Verity Red-State boot failure.",
        ),
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📖 FlashDock — Workflow & Function Guide")
        self.setWindowIcon(get_icon("book", 16))
        self.setMinimumSize(880, 620)
        self.setStyleSheet("background-color: #0F141C; color: #E6EDF3;")
        self._cards_list: list[tuple[str, QFrame]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        header.setSpacing(10)
        icon = create_icon_label("book", 24)
        header.addWidget(icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("FlashDock Interactive Guide & Safe Workflows")
        title.setProperty("cssClass", "heading")
        title.setStyleSheet("font-size: 15px; font-weight: 700; color: #E6EDF3;")
        title_box.addWidget(title)
        subtitle = QLabel("Learn how each function operates, why it works, and how to avoid mistakes.")
        subtitle.setProperty("cssClass", "secondary")
        subtitle.setStyleSheet("font-size: 11.5px; color: #8E8E93;")
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        layout.addLayout(header)

        # Tabs
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid rgba(255, 255, 255, 0.08);
                border-radius: 10px;
                background: #141820;
            }
            QTabBar::tab {
                background: #181E26;
                color: #8E8E93;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                padding: 6px 14px;
                font-size: 11.5px;
                font-weight: 600;
                margin-right: 4px;
            }
            QTabBar::tab:selected {
                background: #141820;
                color: #0A84FF;
                border-color: rgba(255, 255, 255, 0.12);
            }
        """)

        tabs.addTab(self._build_workflow_tab(), "Recommended Safe Workflow")
        tabs.setTabIcon(0, get_icon("flash", 14))
        tabs.addTab(self._build_functions_tab(), "Functions Reference")
        tabs.setTabIcon(1, get_icon("tools", 14))
        tabs.addTab(self._build_under_the_hood_tab(), "How It Works & Anti-Brick Rules")
        tabs.setTabIcon(2, get_icon("integrity", 14))

        layout.addWidget(tabs, 1)

        # Close button row
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton("Got it, Close Guide")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #212836;
                border: 1px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 6px 18px;
                font-size: 12px;
                font-weight: 600;
                color: #E6EDF3;
            }
            QPushButton:hover {
                background-color: #2D3748;
                border-color: #0A84FF;
                color: #0A84FF;
            }
        """)
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def _build_workflow_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        steps = [
            ("Step 1: Check My Phone", "Connect your device and verify connection mode, codename, chipset, battery (≥ 60%), and active slot."),
            ("Step 2: Pre-Flash Checklist", "Run the 18 automated safety checks: confirm USB debugging, driver installation, and battery health."),
            ("Step 3: Backup Partitions", "Always dump critical partitions (boot, efs, persist) and ADB data before flashing any modifications."),
            ("Step 4: Unlock Bootloader", "Follow the brand-aware unlock wizard (Google, Xiaomi token, Samsung Download, etc.). Note: unlocking wipes data."),
            ("Step 5: Root or Flash Custom ROM", "Patch boot/init_boot with Magisk/KernelSU/APatch or flash clean custom ROM / GSI images via fastboot."),
            ("Step 6: Root Modules & Integrity", "Install essential modules (Zygisk, Shamiko) and run the Integrity Fixer to pass Google Play Integrity."),
            ("Step 7: Return to Stock & Relock", "When selling or returning phone to factory state: re-flash 100% clean OEM stock firmware, then safely relock."),
        ]

        for title, desc in steps:
            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #181E26;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 10px;
                    padding: 10px 14px;
                }
            """)
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(4)
            t_label = QLabel(title)
            t_label.setStyleSheet("font-size: 13px; font-weight: 700; color: #E6EDF3;")
            c_lay.addWidget(t_label)
            d_label = QLabel(desc)
            d_label.setWordWrap(True)
            d_label.setStyleSheet("font-size: 12px; color: #8B949E; line-height: 1.4;")
            c_lay.addWidget(d_label)
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_functions_tab(self) -> QWidget:
        container = QWidget()
        top_lay = QVBoxLayout(container)
        top_lay.setContentsMargins(16, 14, 16, 14)
        top_lay.setSpacing(10)

        # Search / Filter Bar
        search_box = QHBoxLayout()
        search_box.setSpacing(8)
        search_ico = create_icon_label("search", 14, color="#8E8E93")
        search_box.addWidget(search_ico)

        self._func_search = QLineEdit()
        self._func_search.setPlaceholderText("Filter functions and tools (e.g. root, flash, bootloop, backup, driver)...")
        self._func_search.setClearButtonEnabled(True)
        self._func_search.setFixedHeight(30)
        self._func_search.setStyleSheet("""
            QLineEdit {
                background: #0F141C;
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                padding: 4px 10px;
                font-size: 11.5px;
                color: #E6EDF3;
            }
            QLineEdit:focus {
                border-color: #0A84FF;
            }
        """)
        self._func_search.textChanged.connect(self._filter_function_cards)
        search_box.addWidget(self._func_search, 1)
        top_lay.addLayout(search_box)

        # Scroll Area with all Action Cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 4, 0, 0)
        content_layout.setSpacing(10)

        self._cards_list.clear()

        for aid, ico, title, cat, grad, how_works, step_step, safety_tip in self._FUNCTION_GUIDE_DATA:
            card = QFrame()
            card.setStyleSheet("""
                QFrame.funcCard {
                    background: #181E26;
                    border: 1px solid rgba(255, 255, 255, 0.08);
                    border-radius: 12px;
                    padding: 12px 14px;
                }
                QFrame.funcCard:hover {
                    border-color: rgba(10, 132, 255, 0.4);
                }
            """)
            card.setProperty("class", "funcCard")
            c_lay = QVBoxLayout(card)
            c_lay.setContentsMargins(12, 12, 12, 12)
            c_lay.setSpacing(8)

            # Header Row
            hdr = QHBoxLayout()
            hdr.setSpacing(10)

            # Circular Chip
            chip = QFrame()
            chip.setFixedSize(28, 28)
            chip.setStyleSheet(f"background: {grad}; border-radius: 14px; border: none;")
            chip_lay = QHBoxLayout(chip)
            chip_lay.setContentsMargins(0, 0, 0, 0)
            chip_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            chip_icon = QLabel()
            chip_icon.setFixedSize(14, 14)
            chip_icon.setPixmap(get_icon_pixmap(ico, 14, 14, color="#FFFFFF"))
            chip_lay.addWidget(chip_icon)
            hdr.addWidget(chip)

            # Title
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("font-size: 13.5px; font-weight: 700; color: #E6EDF3;")
            hdr.addWidget(t_lbl)

            # Category Pill
            bg_tint, text_color = self._CATEGORY_COLORS.get(cat, ("rgba(255, 255, 255, 0.08)", "#8E8E93"))
            cat_badge = QLabel(cat)
            cat_badge.setStyleSheet(
                f"font-size: 9.5px; font-weight: 700; padding: 2px 7px; border-radius: 5px; "
                f"background-color: {bg_tint}; color: {text_color};"
            )
            hdr.addWidget(cat_badge)
            hdr.addStretch(1)

            # 1-Click Launch Button
            launch_btn = QPushButton("Launch This Tool ➔")
            launch_btn.setIcon(get_icon("chevron_right", 12, color="#FFFFFF"))
            launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            launch_btn.setStyleSheet("""
                QPushButton {
                    background-color: #0A84FF;
                    color: #FFFFFF;
                    border: none;
                    border-radius: 7px;
                    padding: 5px 12px;
                    font-size: 11.5px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #0071E3;
                }
                QPushButton:pressed {
                    background-color: #0056B3;
                }
            """)
            launch_btn.clicked.connect(lambda _, a=aid: self._on_launch_tool(a))
            hdr.addWidget(launch_btn)

            c_lay.addLayout(hdr)

            # Detail Breakdown
            body_lbl = QLabel(
                f"<div style='color: #0A84FF; font-weight: 600; font-size: 11.5px; margin-top: 4px; margin-bottom: 2px;'>How It Works (Under the Hood):</div>"
                f"<div style='color: #8B949E; font-size: 11.5px; line-height: 1.4; margin-bottom: 6px;'>{how_works}</div>"
                f"<div style='color: #34C759; font-weight: 600; font-size: 11.5px; margin-bottom: 2px;'>How to Use It (Step-by-Step Guide):</div>"
                f"<div style='color: #E6EDF3; font-size: 11.5px; line-height: 1.4; margin-bottom: 6px;'>{step_step}</div>"
                f"<div style='color: #FF9F0A; font-weight: 600; font-size: 11.5px; margin-bottom: 2px;'>Safety Checklist / Pro-Tips:</div>"
                f"<div style='color: #D29922; font-size: 11.5px; line-height: 1.4;'>{safety_tip}</div>"
            )
            body_lbl.setWordWrap(True)
            body_lbl.setTextFormat(Qt.TextFormat.RichText)
            c_lay.addWidget(body_lbl)

            content_layout.addWidget(card)
            self._cards_list.append((f"{aid} {title} {cat} {how_works}".lower(), card))

        content_layout.addStretch()
        scroll.setWidget(content)
        top_lay.addWidget(scroll, 1)

        return container

    def _filter_function_cards(self, text: str) -> None:
        """Dynamically filters the function guide cards based on search query."""
        query = text.strip().lower()
        for search_blob, card in self._cards_list:
            card.setVisible(not query or query in search_blob)

    def _on_launch_tool(self, action_id: str) -> None:
        """Emit action signal, close dialog, and switch main window page."""
        self.action_requested.emit(action_id)
        self.accept()

    def _build_under_the_hood_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        txt = QLabel(
            "<h2>How Android Flashing Works Under the Hood</h2>"
            "<p>Understanding the architecture behind flashing prevents mistakes and keeps your device 100% safe:</p>"
            "<h3>1. Android Verified Boot (AVB) & dm-verity</h3>"
            "<p>Modern Android uses AVB 2.0 to mathematically hash and sign partitions (<code>vbmeta</code>, <code>boot</code>, <code>system</code>). "
            "When the bootloader is locked, it strictly validates that the cryptographic signature matches the OEM's hardware public key. "
            "If you relock with modified partitions or the wrong region, AVB verification fails and the phone will <b>REFUSE TO BOOT</b> (hard brick).</p>"
            "<h3>2. The Golden Rule of Bootloader Relocking</h3>"
            "<ul>"
            "  <li><b>NEVER</b> relock with a custom ROM, TWRP, or root installed.</li>"
            "  <li><b>NEVER</b> relock a Xiaomi/Redmi device running cross-region ROM (e.g. Global ROM on Chinese hardware).</li>"
            "  <li><b>ONLY</b> relock after flashing 100% official stock firmware matching your device's exact region and hardware!</li>"
            "</ul>"
            "<h3>3. A/B Seamless Partition Slots</h3>"
            "<p>Devices with A/B slots have duplicate partitions (<code>boot_a</code>/<code>boot_b</code>, <code>system_a</code>/<code>system_b</code>). "
            "This allows seamless updates in the background. FlashDock detects your active slot and ensures you flash to the correct partition or both slots.</p>"
            "<h3>4. Dynamic Partitions (Super Partition)</h3>"
            "<p>Android 10+ groups <code>system</code>, <code>vendor</code>, and <code>product</code> inside a single large <code>super</code> partition. "
            "These dynamic partitions must be flashed in <b>FastbootD mode</b>, not regular bootloader mode. FlashDock handles this automatically.</p>"
        )
        txt.setWordWrap(True)
        txt.setStyleSheet("font-size: 12px; color: #8B949E; line-height: 1.5;")
        layout.addWidget(txt)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll
