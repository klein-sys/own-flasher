"""
FlashDock — Crash Recovery Modal Dialog.

Phase 16 Release Hardening: Displays when an unhandled exception occurs,
presenting a masked traceback, option to copy sanitized crash report, open crash
logs folder, or restart FlashDock cleanly.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from flashdock import __app_name__, __version__
from flashdock.constants import LOGS_DIR
from flashdock.ui.icon_assets import create_icon_label, get_icon


class CrashDialog(QDialog):
    """Apple HIG non-fatal Crash Recovery Dialog."""

    def __init__(
        self,
        report_text: str,
        crash_log_path: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"{__app_name__} — Unexpected Error Encountered")
        self.resize(680, 500)
        self.setMinimumSize(540, 400)

        self.report_text = report_text
        self.crash_log_path = crash_log_path

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header banner card
        header_card = QFrame()
        header_card.setStyleSheet(
            "background: #FEF2F2; border-radius: 12px; border: 1px solid #FECACA; padding: 12px;"
        )
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(8, 8, 8, 8)
        h_layout.setSpacing(12)

        icon_lbl = create_icon_label("warning", 32, color="#DC2626")
        h_layout.addWidget(icon_lbl)

        v_head = QVBoxLayout()
        v_head.setSpacing(2)
        title_lbl = QLabel(f"{__app_name__} Encountered an Unexpected Problem")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #991B1B;")
        desc_lbl = QLabel(
            "An error occurred during operation. The application prevented a crash. "
            "A diagnostic dump has been saved with sensitive device identifiers masked."
        )
        desc_lbl.setStyleSheet("font-size: 12px; color: #7F1D1D;")
        desc_lbl.setWordWrap(True)
        v_head.addWidget(title_lbl)
        v_head.addWidget(desc_lbl)
        h_layout.addLayout(v_head, 1)

        layout.addWidget(header_card)

        # Traceback viewer
        tb_label = QLabel("Sanitized Diagnostic Traceback:")
        tb_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1D1D1F;")
        layout.addWidget(tb_label)

        self.traceback_view = QTextEdit()
        self.traceback_view.setReadOnly(True)
        self.traceback_view.setPlainText(self.report_text)
        self.traceback_view.setStyleSheet(
            "QTextEdit { background: #1C1C1E; color: #F2F2F7; font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 11px; border-radius: 8px; border: 1px solid #2C2C2E; padding: 10px; }"
        )
        layout.addWidget(self.traceback_view, 1)

        # Footer Buttons
        footer = QHBoxLayout()
        footer.setSpacing(10)

        self.btn_copy = QPushButton("Copy Error Report")
        self.btn_copy.setIcon(get_icon("copy", 14))
        self.btn_copy.setStyleSheet(
            "QPushButton { background: #E5E5EA; color: #1D1D1F; border-radius: 8px; padding: 8px 14px; font-weight: 600; } "
            "QPushButton:hover { background: #D1D1D6; }"
        )
        self.btn_copy.clicked.connect(self._copy_error)
        footer.addWidget(self.btn_copy)

        self.btn_open_folder = QPushButton("Open Logs Folder")
        self.btn_open_folder.setIcon(get_icon("folder", 14))
        self.btn_open_folder.setStyleSheet(
            "QPushButton { background: #E5E5EA; color: #1D1D1F; border-radius: 8px; padding: 8px 14px; font-weight: 600; } "
            "QPushButton:hover { background: #D1D1D6; }"
        )
        self.btn_open_folder.clicked.connect(self._open_logs_folder)
        footer.addWidget(self.btn_open_folder)

        footer.addStretch()

        self.btn_restart = QPushButton("Restart FlashDock")
        self.btn_restart.setIcon(get_icon("refresh", 14, color="#FFFFFF"))
        self.btn_restart.setStyleSheet(
            "QPushButton { background: #007AFF; color: #FFFFFF; border-radius: 8px; padding: 8px 18px; font-weight: 600; } "
            "QPushButton:hover { background: #0062CC; }"
        )
        self.btn_restart.clicked.connect(self._restart_app)
        footer.addWidget(self.btn_restart)

        self.btn_close = QPushButton("Ignore & Continue")
        self.btn_close.setStyleSheet(
            "QPushButton { background: transparent; color: #86868B; border: 1px solid #C7C7CC; border-radius: 8px; padding: 8px 14px; } "
            "QPushButton:hover { background: #E5E5EA; color: #1D1D1F; }"
        )
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)

        layout.addLayout(footer)

    def _copy_error(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report_text)
        self.btn_copy.setText("Copied!")
        self.btn_copy.setIcon(get_icon("check", 14))

    def _open_logs_folder(self) -> None:
        try:
            if sys.platform == "win32":
                os.startfile(str(LOGS_DIR))
            else:
                subprocess.Popen(["xdg-open", str(LOGS_DIR)])
        except Exception:
            pass

    def _restart_app(self) -> None:
        """Restarts the current Python process."""
        try:
            python = sys.executable
            os.execl(python, python, *sys.argv)
        except Exception:
            self.accept()
