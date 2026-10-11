"""
FlashDock — Workstation & Laptop Setup Wizard Modal Dialog.

Guides user through preparing their Windows laptop before flashing:
1. Google Android Platform-Tools (ADB & Fastboot) verification & 1-click install.
2. Essential Windows USB Drivers (Google, Samsung, Qualcomm 9008, MTK VCOM).
3. Laptop USB port & power management best practices.
4. Live connection test.
"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import DRIVERS_DIR, TOOLS_DIR
from flashdock.core.tools_manager import DriverManager, PlatformToolsManager
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot

log = get_logger(__name__)


class _DownloadWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(bool, str)

    def __init__(self, manager: PlatformToolsManager) -> None:
        super().__init__()
        self.manager = manager

    def run(self) -> None:
        def _on_prog(cur: int, tot: int) -> None:
            self.progress.emit(cur, tot)

        ok, msg = self.manager.download_and_install_platform_tools(progress_callback=_on_prog)
        self.finished.emit(ok, msg)


class SetupWizardDialog(QDialog):
    """Interactive laptop setup wizard ensuring all prerequisites are installed."""

    def __init__(
        self,
        adb: ADB,
        fastboot: Fastboot,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("🛠️ Laptop & Workstation Setup Wizard")
        self.resize(760, 600)
        self.setMinimumSize(640, 480)

        self._adb = adb
        self._fastboot = fastboot
        self._tools_mgr = PlatformToolsManager(adb=adb, fastboot=fastboot)
        self._driver_mgr = DriverManager()

        self._current_step = 0
        self._worker: Optional[_DownloadWorker] = None

        self._setup_ui()
        self._update_step_view()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # Header with Step Indicator
        header = QVBoxLayout()
        header.setSpacing(4)
        title = QLabel("🛠️ Laptop & Workstation Setup Wizard")
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1D1D1F;")
        header.addWidget(title)

        self._subtitle = QLabel("Prepare your Windows laptop for safe, reliable Android flashing.")
        self._subtitle.setStyleSheet("font-size: 13px; color: #8E8E93;")
        header.addWidget(self._subtitle)
        main_layout.addLayout(header)

        # Step Breadcrumbs Bar
        self._steps_bar = QHBoxLayout()
        self._steps_bar.setSpacing(8)
        self._step_labels = [
            "1. Platform-Tools",
            "2. USB Drivers",
            "3. USB Best Practices",
            "4. Verify Connection",
        ]
        self._step_widgets = []
        for idx, text in enumerate(self._step_labels):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                "padding: 6px 14px; border-radius: 6px; font-weight: 600; font-size: 12px; "
                "background: #E5E7EB; color: #6B7280;"
            )
            self._steps_bar.addWidget(lbl)
            self._step_widgets.append(lbl)
        self._steps_bar.addStretch()
        main_layout.addLayout(self._steps_bar)

        # Stacked Pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._create_step1_tools())
        self._stack.addWidget(self._create_step2_drivers())
        self._stack.addWidget(self._create_step3_hardware())
        self._stack.addWidget(self._create_step4_verify())
        main_layout.addWidget(self._stack, 1)

        # Navigation Footer
        footer = QHBoxLayout()
        self._btn_prev = QPushButton("◀ Back")
        self._btn_prev.setStyleSheet(
            "QPushButton { background: #E5E7EB; color: #374151; border-radius: 8px; padding: 8px 18px; font-weight: 600; } "
            "QPushButton:hover { background: #D1D5DB; }"
        )
        self._btn_prev.clicked.connect(self._go_prev)
        footer.addWidget(self._btn_prev)

        footer.addStretch()

        self._btn_next = QPushButton("Next ▶")
        self._btn_next.setStyleSheet(
            "QPushButton { background: #007AFF; color: #FFFFFF; border-radius: 8px; padding: 8px 24px; font-weight: 600; } "
            "QPushButton:hover { background: #0062CC; }"
        )
        self._btn_next.clicked.connect(self._go_next)
        footer.addWidget(self._btn_next)

        main_layout.addLayout(footer)

    def _update_step_view(self) -> None:
        self._stack.setCurrentIndex(self._current_step)
        self._btn_prev.setEnabled(self._current_step > 0)
        if self._current_step == len(self._step_labels) - 1:
            self._btn_next.setText("Finish Setup ✓")
        else:
            self._btn_next.setText("Next ▶")

        for idx, lbl in enumerate(self._step_widgets):
            if idx == self._current_step:
                lbl.setStyleSheet(
                    "padding: 6px 14px; border-radius: 6px; font-weight: 700; font-size: 12px; "
                    "background: #007AFF; color: #FFFFFF;"
                )
            elif idx < self._current_step:
                lbl.setStyleSheet(
                    "padding: 6px 14px; border-radius: 6px; font-weight: 600; font-size: 12px; "
                    "background: #D1FAE5; color: #065F46;"
                )
            else:
                lbl.setStyleSheet(
                    "padding: 6px 14px; border-radius: 6px; font-weight: 600; font-size: 12px; "
                    "background: #F3F4F6; color: #9CA3AF;"
                )

    def _go_prev(self) -> None:
        if self._current_step > 0:
            self._current_step -= 1
            self._update_step_view()

    def _go_next(self) -> None:
        if self._current_step < len(self._step_labels) - 1:
            self._current_step += 1
            self._update_step_view()
        else:
            self.accept()

    # ---- Step 1: Platform-Tools ----
    def _create_step1_tools(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(14)

        card = QFrame()
        card.setStyleSheet("background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; padding: 16px;")
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(10)

        t_lbl = QLabel("📦 Android Platform-Tools (ADB & Fastboot)")
        t_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #111827;")
        c_lay.addWidget(t_lbl)

        d_lbl = QLabel(
            "ADB and Fastboot are the primary communication tools between your laptop and your phone. "
            "FlashDock uses them to detect devices, unlock bootloaders, send commands, and flash ROMs."
        )
        d_lbl.setStyleSheet("font-size: 13px; color: #4B5563;")
        d_lbl.setWordWrap(True)
        c_lay.addWidget(d_lbl)

        self._tools_status_lbl = QLabel("Checking platform-tools status...")
        self._tools_status_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #1F2937;")
        c_lay.addWidget(self._tools_status_lbl)

        self._tools_prog = QProgressBar()
        self._tools_prog.setVisible(False)
        c_lay.addWidget(self._tools_prog)

        btn_row = QHBoxLayout()
        self._btn_dl_tools = QPushButton("⬇️ Download & Install Platform-Tools")
        self._btn_dl_tools.setStyleSheet(
            "QPushButton { background: #10B981; color: #FFFFFF; font-weight: 700; border-radius: 8px; padding: 10px 18px; } "
            "QPushButton:hover { background: #059669; }"
        )
        self._btn_dl_tools.clicked.connect(self._download_tools)
        btn_row.addWidget(self._btn_dl_tools)
        btn_row.addStretch()
        c_lay.addLayout(btn_row)

        lay.addWidget(card)
        lay.addStretch()
        self._refresh_step1_status()
        return w

    def _refresh_step1_status(self) -> None:
        adb_ok = self._adb.available
        fb_ok = self._fastboot.available
        if adb_ok and fb_ok:
            self._tools_status_lbl.setText("✅ Platform-Tools are installed and ready to use!")
            self._tools_status_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #059669;")
            self._btn_dl_tools.setText("🔄 Re-install / Update Platform-Tools")
        else:
            self._tools_status_lbl.setText("⚠️ Platform-Tools are missing or not detected.")
            self._tools_status_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #D97706;")

    def _download_tools(self) -> None:
        self._btn_dl_tools.setEnabled(False)
        self._tools_prog.setVisible(True)
        self._tools_prog.setValue(0)
        self._tools_status_lbl.setText("Downloading latest platform-tools from Google...")

        self._worker = _DownloadWorker(self._tools_mgr)
        self._worker.progress.connect(self._on_tools_prog)
        self._worker.finished.connect(self._on_tools_finished)
        self._worker.start()

    def _on_tools_prog(self, cur: int, tot: int) -> None:
        if tot > 0:
            self._tools_prog.setValue(int(cur / tot * 100))

    def _on_tools_finished(self, ok: bool, msg: str) -> None:
        self._tools_prog.setVisible(False)
        self._btn_dl_tools.setEnabled(True)
        if ok:
            self._refresh_step1_status()
        else:
            self._tools_status_lbl.setText(f"❌ Installation failed: {msg}")

    # ---- Step 2: Drivers ----
    def _create_step2_drivers(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(10)

        desc = QLabel(
            "Windows requires specific USB drivers to recognize your phone in different modes "
            "(ADB, Bootloader, Fastboot, Samsung Odin, Qualcomm 9008, and MediaTek BROM)."
        )
        desc.setStyleSheet("font-size: 13px; color: #4B5563;")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        c = QWidget()
        c_lay = QVBoxLayout(c)
        c_lay.setSpacing(8)

        drivers = self._driver_mgr.get_all_drivers()
        for d in drivers:
            card = QFrame()
            card.setStyleSheet("background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 10px;")
            h = QHBoxLayout(card)
            info = QVBoxLayout()
            lbl = QLabel(f"<b>{d.name}</b> <span style='color:#6B7280;'>({d.brand})</span>")
            lbl.setStyleSheet("font-size: 13px; color: #111827;")
            sub = QLabel(d.description)
            sub.setStyleSheet("font-size: 11px; color: #6B7280;")
            sub.setWordWrap(True)
            info.addWidget(lbl)
            info.addWidget(sub)
            h.addLayout(info, 1)

            btn = QPushButton("Install / Portal")
            btn.setStyleSheet(
                "QPushButton { background: #007AFF; color: #FFFFFF; font-weight: 600; border-radius: 6px; padding: 6px 14px; font-size: 12px; } "
                "QPushButton:hover { background: #0062CC; }"
            )
            btn.clicked.connect(lambda _, did=d.id: self._install_driver(did))
            h.addWidget(btn)
            c_lay.addWidget(card)

        scroll.setWidget(c)
        lay.addWidget(scroll, 1)
        return w

    def _install_driver(self, driver_id: str) -> None:
        ok, msg = self._driver_mgr.download_driver(driver_id)
        if not ok:
            pkg = self._driver_mgr.get_driver(driver_id)
            if pkg and pkg.official_portal_url:
                webbrowser.open(pkg.official_portal_url)

    # ---- Step 3: USB Best Practices ----
    def _create_step3_hardware(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        items = [
            ("🔌 Connect Directly to Laptop", "Do NOT use unpowered USB hubs or keyboard passthrough ports. Fastboot transfers high-speed sparse chunk images up to 4GB; unpowered hubs frequently drop packets and can corrupt system partitions."),
            ("⚡ Prefer USB 2.0 / USB-A Ports", "Some older fastboot bootloaders (especially Xiaomi and Motorola) have handshake bugs with USB 3.2 Gen 2 ports. If fastboot hangs on '<waiting for any device>', switch to a standard USB 2.0 port or use a USB 2.0 cable."),
            ("🔋 Laptop Power & Sleep Settings", "Disable laptop sleep or USB selective suspend in Windows Power Options. If your laptop enters standby during a 5-minute Super partition flash, the write stream is severed and bricks the phone."),
            ("📱 Battery Level ≥ 50%", "Never start flashing with a low battery. If flashing fails and the phone is left in a bootloop without OS charging drivers, recovering battery charge requires disassembly or battery replacement."),
        ]

        for title, body in items:
            card = QFrame()
            card.setStyleSheet("background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; padding: 12px;")
            c_lay = QVBoxLayout(card)
            c_lay.setSpacing(4)
            t = QLabel(f"<b>{title}</b>")
            t.setStyleSheet("font-size: 14px; color: #1F2937;")
            b = QLabel(body)
            b.setStyleSheet("font-size: 12px; color: #4B5563;")
            b.setWordWrap(True)
            c_lay.addWidget(t)
            c_lay.addWidget(b)
            lay.addWidget(card)

        lay.addStretch()
        return w

    # ---- Step 4: Verify Connection ----
    def _create_step4_verify(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(14)

        card = QFrame()
        card.setStyleSheet("background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 10px; padding: 16px;")
        c_lay = QVBoxLayout(card)
        c_lay.setSpacing(8)

        t = QLabel("🎉 Workstation Setup Complete!")
        t.setStyleSheet("font-size: 16px; font-weight: 700; color: #166534;")
        c_lay.addWidget(t)

        d = QLabel(
            "Your laptop is now configured with the proper tools and guidelines. "
            "Connect your Android phone with a quality USB cable to begin servicing."
        )
        d.setStyleSheet("font-size: 13px; color: #15803D;")
        d.setWordWrap(True)
        c_lay.addWidget(d)

        lay.addWidget(card)

        test_card = QFrame()
        test_card.setStyleSheet("background: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; padding: 16px;")
        t_lay = QVBoxLayout(test_card)
        t_lay.setSpacing(10)

        test_title = QLabel("🔍 Test Phone Connection Now:")
        test_title.setStyleSheet("font-size: 14px; font-weight: 600; color: #111827;")
        t_lay.addWidget(test_title)

        self._test_status_lbl = QLabel("Plug your phone in via USB and click 'Test Connection'.")
        self._test_status_lbl.setStyleSheet("font-size: 12px; color: #4B5563;")
        t_lay.addWidget(self._test_status_lbl)

        btn_test = QPushButton("🔄 Test Connection (ADB & Fastboot)")
        btn_test.setStyleSheet(
            "QPushButton { background: #007AFF; color: #FFFFFF; font-weight: 600; border-radius: 6px; padding: 8px 18px; } "
            "QPushButton:hover { background: #0062CC; }"
        )
        btn_test.clicked.connect(self._run_connection_test)
        t_lay.addWidget(btn_test)

        lay.addWidget(test_card)
        lay.addStretch()
        return w

    def _run_connection_test(self) -> None:
        found_devices = []
        if self._adb.available:
            for dev in self._adb.devices():
                found_devices.append(f"ADB: {dev.serial} ({dev.state})")
        if self._fastboot.available:
            for dev in self._fastboot.devices():
                found_devices.append(f"Fastboot: {dev.serial} ({dev.mode})")

        if found_devices:
            self._test_status_lbl.setText("✅ Detected device(s):\n" + "\n".join(found_devices))
            self._test_status_lbl.setStyleSheet("font-size: 13px; font-weight: 600; color: #059669;")
        else:
            self._test_status_lbl.setText("⚠️ No devices detected yet. Ensure USB debugging is ON and cable is firmly connected.")
            self._test_status_lbl.setStyleSheet("font-size: 12px; color: #D97706;")
