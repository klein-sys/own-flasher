"""
FlashDock — Flashing Shield ("Do Not Unplug" lock screen).

A modal guard that covers the window during active flashing operations,
preventing accidental navigation, disconnection, or window closure.

Spec references: Section 21, Section 16.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCloseEvent, QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from flashdock.logger import get_logger
from flashdock.tools.runner import acquire_flash_lock, is_flash_locked, release_flash_lock

log = get_logger(__name__)


class FlashShieldDialog(QDialog):
    """
    Modal shield that locks the UI during flashing operations.
    Cannot be closed until the flash operation completes.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("⚡ FlashDock — Flash in Progress")
        self.setModal(True)
        self.setMinimumSize(620, 480)
        # Prevent standard window close button from letting user abort easily
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
        )

        self._is_active = True
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Danger Banner Frame
        banner_frame = QFrame()
        banner_frame.setProperty("cssClass", "danger_banner")
        banner_layout = QVBoxLayout(banner_frame)
        banner_layout.setSpacing(8)

        warn_title = QLabel("⚠️  FLASH IN PROGRESS — DO NOT UNPLUG")
        warn_title.setProperty("cssClass", "error")
        warn_title.setStyleSheet("font-size: 16px; font-weight: 800;")
        banner_layout.addWidget(warn_title)

        warn_sub = QLabel(
            "Firmware partitions are being written directly to device storage.\n"
            "Disconnecting the USB cable or closing FlashDock now WILL cause a soft or hard brick."
        )
        warn_sub.setWordWrap(True)
        warn_sub.setProperty("cssClass", "secondary")
        banner_layout.addWidget(warn_sub)

        layout.addWidget(banner_frame)

        # Status text & Progress Bar
        self._status_label = QLabel("Initializing flashing process...")
        self._status_label.setProperty("cssClass", "subheading")
        layout.addWidget(self._status_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        layout.addWidget(self._progress_bar)

        # Log stream display
        log_label = QLabel("Operation Console Output:")
        log_label.setProperty("cssClass", "secondary")
        layout.addWidget(log_label)

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setProperty("cssClass", "code_box")
        layout.addWidget(self._log_view, 1)

        # Bottom button row (initially hidden/disabled)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._close_btn = QPushButton("Done")
        self._close_btn.setEnabled(False)
        self._close_btn.setProperty("cssClass", "primary")
        self._close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self._close_btn)

        layout.addLayout(btn_layout)

    # -----------------------------------------------------------------------
    # Public controls
    # -----------------------------------------------------------------------

    def update_progress(self, message: str, percent: int) -> None:
        """Update status message and progress bar."""
        self._status_label.setText(message)
        self._progress_bar.setValue(max(0, min(100, percent)))
        self.append_log(message)

    def append_log(self, text: str) -> None:
        """Append line to the console viewer."""
        self._log_view.append(text)
        # Scroll to bottom
        sb = self._log_view.verticalScrollBar()
        sb.setValue(sb.maximum())

    def mark_completed(self, success: bool, message: str = "") -> None:
        """Mark flash operation finished and unlock the dialog."""
        self._is_active = False
        release_flash_lock()

        if success:
            self._status_label.setText(f"✅  {message or 'Flashing completed successfully!'}")
            self._status_label.setProperty("cssClass", "success")
            self._progress_bar.setValue(100)
        else:
            self._status_label.setText(f"❌  {message or 'Flashing operation failed!'}")
            self._status_label.setProperty("cssClass", "error")

        self._close_btn.setEnabled(True)
        self._close_btn.setText("Close Guard")

    # -----------------------------------------------------------------------
    # Guard protection
    # -----------------------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """Intercept any close request while flash is in progress."""
        if self._is_active or is_flash_locked():
            QMessageBox.critical(
                self,
                "Cannot Close",
                "A flash operation is currently active!\n\n"
                "Closing FlashDock now will disconnect the device mid-transfer and can PERMANENTLY BRICK your phone.\n"
                "Please wait for the operation to complete.",
            )
            event.ignore()
        else:
            event.accept()

    def reject(self) -> None:
        """Intercept ESC key or dialog cancellation."""
        if self._is_active or is_flash_locked():
            return
        super().reject()
