"""
FlashDock — scrcpy Mirror & Phone Control Dialog.

Provides quick configuration and launch controls for Android screen mirroring,
audio forwarding, and recording session options.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.tools.scrcpy import ScrcpyManager


class _ScrcpyDownloadThread(QThread):
    progress = Signal(int, int)
    finished_result = Signal(bool, str)

    def __init__(self, manager: ScrcpyManager) -> None:
        super().__init__()
        self._manager = manager

    def run(self) -> None:
        success, msg = self._manager.download_and_install(
            progress_callback=self.progress.emit
        )
        self.finished_result.emit(success, msg)


class ScrcpyDialog(QDialog):
    """Configuration and launch dialog for scrcpy screen mirroring."""

    def __init__(
        self,
        manager: ScrcpyManager,
        device: Optional[DeviceInfo] = None,
        adb_path: Optional[Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._manager = manager
        self._device = device
        self._adb_path = adb_path
        self._dl_thread: Optional[_ScrcpyDownloadThread] = None

        self.setWindowTitle("🖥️ Screen Mirroring & Control (scrcpy)")
        self.resize(520, 480)
        self._setup_ui()
        self._refresh_status()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # Header
        title = QLabel("🖥️ Screen Mirroring & Device Control")
        title.setProperty("cssClass", "heading")
        layout.addWidget(title)

        subtitle = QLabel("High performance, ultra-low latency screen display and interaction via scrcpy.")
        subtitle.setProperty("cssClass", "muted")
        layout.addWidget(subtitle)

        # Device badge card
        dev_card = QFrame()
        dev_card.setProperty("cssClass", "card_subtle")
        d_lay = QHBoxLayout(dev_card)
        d_lay.setContentsMargins(12, 10, 12, 10)
        if self._device:
            serial_str = self._device.serial or "Default Device"
            brand = self._device.brand or ""
            model = self._device.model or ""
            model_str = f"{brand} {model}".strip() or "Android Device"
            self._device_lbl = QLabel(f"📱 <b>Target:</b> {model_str}  <span style='color:#8E8E93;'>({serial_str})</span>")
        else:
            self._device_lbl = QLabel("📱 <b>Target:</b> <span style='color:#E5A93C;'>No Device Connected</span> — connect phone via USB")
        d_lay.addWidget(self._device_lbl)
        layout.addWidget(dev_card)

        # Status & Version Card
        self._status_frame = QFrame()
        self._status_frame.setProperty("cssClass", "card_subtle")
        s_lay = QVBoxLayout(self._status_frame)
        s_lay.setContentsMargins(12, 10, 12, 10)
        self._status_lbl = QLabel("Checking scrcpy binary...")
        s_lay.addWidget(self._status_lbl)

        # Download progress bar
        self._prog_bar = QProgressBar()
        self._prog_bar.setVisible(False)
        self._prog_bar.setTextVisible(True)
        s_lay.addWidget(self._prog_bar)
        layout.addWidget(self._status_frame)

        # Mirroring Options Group
        opt_frame = QFrame()
        opt_frame.setProperty("cssClass", "card_subtle")
        opt_lay = QVBoxLayout(opt_frame)
        opt_lay.setContentsMargins(14, 12, 14, 12)
        opt_lay.setSpacing(10)

        opt_title = QLabel("⚙️ Mirroring Options")
        opt_title.setStyleSheet("font-weight: 600; font-size: 13px;")
        opt_lay.addWidget(opt_title)

        self._stay_awake_cb = QCheckBox("Keep device awake while mirroring (--stay-awake)")
        self._stay_awake_cb.setChecked(True)
        opt_lay.addWidget(self._stay_awake_cb)

        self._turn_off_cb = QCheckBox("Turn device screen off while mirroring (--turn-screen-off, saves battery)")
        self._turn_off_cb.setChecked(False)
        opt_lay.addWidget(self._turn_off_cb)

        self._audio_cb = QCheckBox("Forward device audio to PC (Android 11+)")
        self._audio_cb.setChecked(True)
        opt_lay.addWidget(self._audio_cb)

        # Resolution limit dropdown
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("Max Resolution:"))
        self._res_combo = QComboBox()
        self._res_combo.addItem("Native (Full Quality)", 0)
        self._res_combo.addItem("1080p (Fast)", 1920)
        self._res_combo.addItem("720p (Ultra Fast / Low Latency)", 1280)
        res_row.addWidget(self._res_combo, 1)
        opt_lay.addLayout(res_row)

        # Record session row
        rec_row = QHBoxLayout()
        self._record_cb = QCheckBox("Record mirror session to MP4:")
        self._record_cb.toggled.connect(self._toggle_recording)
        rec_row.addWidget(self._record_cb)

        self._record_path_input = QLineEdit()
        self._record_path_input.setPlaceholderText("Select output .mp4 file path...")
        self._record_path_input.setEnabled(False)
        rec_row.addWidget(self._record_path_input, 1)

        self._record_browse_btn = QPushButton("Browse...")
        self._record_browse_btn.setEnabled(False)
        self._record_browse_btn.clicked.connect(self._browse_record_file)
        rec_row.addWidget(self._record_browse_btn)
        opt_lay.addLayout(rec_row)

        layout.addWidget(opt_frame)

        # Action Buttons Row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._dl_btn = QPushButton("⬇️ Download scrcpy (GitHub v3.1)")
        self._dl_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dl_btn.clicked.connect(self._start_download)
        btn_row.addWidget(self._dl_btn)

        self._launch_btn = QPushButton("🚀 Start Screen Mirroring")
        self._launch_btn.setProperty("cssClass", "primary")
        self._launch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._launch_btn.setMinimumHeight(38)
        self._launch_btn.clicked.connect(self._on_launch)
        btn_row.addWidget(self._launch_btn, 1)

        close_btn = QPushButton("Close")
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.close)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    def _refresh_status(self) -> None:
        is_inst = self._manager.is_installed()
        if is_inst:
            exe = self._manager.get_executable()
            ver = self._manager.get_version()
            self._status_lbl.setText(
                f"✅ <b>scrcpy is Ready:</b> {ver}<br>"
                f"<span style='color:#8E8E93; font-size:11px;'>Location: {exe}</span>"
            )
            self._dl_btn.setVisible(False)
            self._launch_btn.setEnabled(True)
        else:
            self._status_lbl.setText(
                "⚠️ <b>scrcpy is not installed.</b> Click Download below for automatic 1-click setup from official GitHub releases."
            )
            self._dl_btn.setVisible(True)
            self._launch_btn.setEnabled(False)

    def _toggle_recording(self, checked: bool) -> None:
        self._record_path_input.setEnabled(checked)
        self._record_browse_btn.setEnabled(checked)
        if checked and not self._record_path_input.text():
            default_path = Path.home() / "Videos" / "scrcpy_recording.mp4"
            self._record_path_input.setText(str(default_path))

    def _browse_record_file(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Mirroring Recording",
            str(Path.home() / "Videos" / "scrcpy_recording.mp4"),
            "MP4 Video (*.mp4)",
        )
        if path:
            self._record_path_input.setText(path)

    @Slot()
    def _start_download(self) -> None:
        self._dl_btn.setEnabled(False)
        self._prog_bar.setVisible(True)
        self._prog_bar.setValue(0)
        self._status_lbl.setText("Downloading scrcpy bundle from GitHub...")

        self._dl_thread = _ScrcpyDownloadThread(self._manager)
        self._dl_thread.progress.connect(self._on_dl_progress)
        self._dl_thread.finished_result.connect(self._on_dl_finished)
        self._dl_thread.start()

    def _on_dl_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            pct = int((downloaded / total) * 100)
            self._prog_bar.setValue(pct)
            self._prog_bar.setFormat(f"%p% ({downloaded // 1048576}MB / {total // 1048576}MB)")

    def _on_dl_finished(self, success: bool, message: str) -> None:
        self._prog_bar.setVisible(False)
        self._dl_btn.setEnabled(True)
        if success:
            QMessageBox.information(self, "scrcpy Installed", message)
            self._refresh_status()
        else:
            QMessageBox.warning(self, "Download Failed", message)
            self._refresh_status()

    @Slot()
    def _on_launch(self) -> None:
        if not self._device or not self._device.serial:
            QMessageBox.information(
                self,
                "Device Required",
                "Please connect your Android device via USB with USB Debugging enabled before launching screen mirror.",
            )
            return
        serial = self._device.serial
        stay_awake = self._stay_awake_cb.isChecked()
        turn_screen_off = self._turn_off_cb.isChecked()
        audio = self._audio_cb.isChecked()
        max_size = self._res_combo.currentData()
        record_path = Path(self._record_path_input.text().strip()) if self._record_cb.isChecked() and self._record_path_input.text().strip() else None

        success, msg = self._manager.launch(
            serial=serial,
            stay_awake=stay_awake,
            turn_screen_off=turn_screen_off,
            audio=audio,
            max_size=max_size,
            record_path=record_path,
            adb_path=self._adb_path,
        )
        if success:
            self.accept()
        else:
            QMessageBox.warning(self, "scrcpy Launch Error", msg)
