"""
FlashDock — Interactive Workflow & Function Guide Dialog.

Comprehensive guide showing how to use each of the 13 functions,
the recommended safe flashing workflow, and how Android flashing works
under the hood to guarantee zero-brick operations.

Spec reference: Section 29 (User Additions).
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class WorkflowGuideDialog(QDialog):
    """Interactive modal guide detailing workflows and function references."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📖 FlashDock — Workflow & Function Guide")
        self.setMinimumSize(780, 560)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(14)

        # Header
        header = QHBoxLayout()
        icon = QLabel("📖")
        icon.setStyleSheet("font-size: 24px;")
        header.addWidget(icon)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("FlashDock Interactive Guide & Safe Workflows")
        title.setProperty("cssClass", "heading")
        title_box.addWidget(title)
        subtitle = QLabel("Learn how each function operates, why it works, and how to avoid mistakes.")
        subtitle.setProperty("cssClass", "secondary")
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        layout.addLayout(header)

        # Tabs
        tabs = QTabWidget()

        tabs.addTab(self._build_workflow_tab(), "⚡ Recommended Safe Workflow")
        tabs.addTab(self._build_functions_tab(), "🛠️ 13 Functions Reference")
        tabs.addTab(self._build_under_the_hood_tab(), "🛡️ How It Works & Anti-Brick Rules")

        layout.addWidget(tabs, 1)

        # Close button
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton("Got it, Close Guide")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setProperty("cssClass", "primary")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

    def _build_workflow_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        steps = [
            ("Step 1: Check My Phone 🔍", "Connect your device and verify connection mode, codename, chipset, battery (≥ 60%), and active slot."),
            ("Step 2: Pre-Flash Checklist ✅", "Run the 18 automated safety checks: confirm USB debugging, driver installation, and battery health."),
            ("Step 3: Backup Partitions 💼", "Always dump critical partitions (boot, efs, persist) and ADB data before flashing any modifications."),
            ("Step 4: Unlock Bootloader 🔓", "Follow the brand-aware unlock wizard (Google, Xiaomi token, Samsung Download, etc.). Note: unlocking wipes data."),
            ("Step 5: Root or Flash Custom ROM 💾🌱", "Patch boot/init_boot with Magisk/KernelSU/APatch or flash clean custom ROM / GSI images via fastboot."),
            ("Step 6: Root Modules & Integrity 🛡️", "Install essential modules (Zygisk, Shamiko) and run the Integrity Fixer to pass Google Play Integrity."),
            ("Step 7: Return to Stock & Relock 🏠", "When selling or returning phone to factory state: re-flash 100% clean OEM stock firmware, then safely relock."),
        ]

        for title, desc in steps:
            card = QFrame()
            card.setProperty("cssClass", "card")
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(4)
            t_label = QLabel(title)
            t_label.setProperty("cssClass", "subheading")
            c_lay.addWidget(t_label)
            d_label = QLabel(desc)
            d_label.setWordWrap(True)
            d_label.setProperty("cssClass", "secondary")
            c_lay.addWidget(d_label)
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_functions_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        funcs = [
            ("🔍 Check my phone", "Detects device via ADB or Fastboot. Builds full hardware profile (chipset, slot scheme, GKI kernel, and OS modification status)."),
            ("✅ Checklist", "18-step pre-flight check covering files, drivers, backup readiness, and battery to prevent preventable errors."),
            ("🔓 Unlock bootloader", "Brand-specific unlock flows: Pixel standard flashing unlock, Xiaomi token prompts, Samsung Download mode, Motorola OEM codes."),
            ("🌱 Root my phone", "GKI kernel detection, boot vs init_boot targeting (Android 13+), automatic pre-root backup, patch pipeline, and unrooting."),
            ("💾 Flash ROM / GSI / Recovery", "Flashes full custom ROMs, dynamic Super partitions, Treble GSIs (arm64 A/B), and TWRP/OrangeFox custom recoveries."),
            ("📦 Modules", "Inspects and flashes root ZIPs, discovers installed modules across Magisk/KernelSU/APatch, and provides emergency bootloop kill-switch."),
            ("🛡️ Fix Integrity", "Diagnoses Google Play Integrity verdicts (Basic, Device, Strong) and guides fingerprint spoofing to pass banking app checks."),
            ("💼 Backup / Restore", "Raw block partition dumps over ADB/Fastboot, full user app/data backup, metadata catalog, and 1-click restore."),
            ("🔧 Fix bricked phone", "Emergency recovery for bootloops, soft bricks, and corrupted partitions using fastboot and EDL/BROM recovery."),
            ("🏠 Return to Stock", "Restores pure factory OEM firmware, wipes custom modifications, and provides guarded bootloader relocking."),
            ("⚙️ MTK / Unisoc mode", "Low-level hardware flashing for MediaTek (BROM / MTKClient) and Unisoc (PAC files / SPD Research Download)."),
            ("⬇️ Downloads & Updates", "Manages platform-tools, drivers (ADB, Fastboot, Samsung, EDL 9008), and firmware finder repository."),
            ("📋 Logs & Help", "Real-time action log with automatic serial number masking for safe sharing and troubleshooting guides."),
        ]

        for name, detail in funcs:
            card = QFrame()
            card.setProperty("cssClass", "card")
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(2)
            n_label = QLabel(name)
            n_label.setProperty("cssClass", "subheading")
            c_lay.addWidget(n_label)
            d_label = QLabel(detail)
            d_label.setWordWrap(True)
            d_label.setProperty("cssClass", "secondary")
            c_lay.addWidget(d_label)
            layout.addWidget(card)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_under_the_hood_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        txt = QLabel(
            "<h2>🛡️ How Android Flashing Works Under the Hood</h2>"
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
        txt.setProperty("cssClass", "secondary")
        layout.addWidget(txt)
        layout.addStretch()

        scroll.setWidget(content)
        return scroll
