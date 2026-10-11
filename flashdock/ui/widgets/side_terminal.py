"""
FlashDock — Side Activity Terminal (Live Process Display).

A non-editable, read-only side console displaying real-time command execution,
device detection events, fastboot/adb outputs, and flashing progress.

Spec reference: Section 29 (User Additions).
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SideTerminalHandler(logging.Handler):
    """Logging handler that emits formatted records to the side terminal."""

    ROUTINE_POLL_KEYWORDS = (
        "adb_devices",
        "fastboot_devices",
        "devices -l",
        "fastboot.exe devices",
        "adb.exe devices",
        "fastboot devices",
    )

    def __init__(self, callback, filter_routine_polls: bool = True) -> None:
        super().__init__()
        self._callback = callback
        self.filter_routine_polls = filter_routine_polls

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if self.filter_routine_polls:
                msg_lower = msg.lower()
                for keyword in self.ROUTINE_POLL_KEYWORDS:
                    if keyword in msg_lower:
                        return

            formatted = self.format(record)
            level = record.levelname.lower()
            self._callback(formatted, level)
        except Exception:
            pass


class SideTerminalWidget(QWidget):
    """
    Read-only side activity terminal displaying what's happening under the hood.
    """

    log_signal = Signal(str, str)  # message, level

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(320)
        self._is_collapsed = False
        self._filter_polls = True
        self._handler_ref: Optional[SideTerminalHandler] = None
        self._setup_ui()
        self._connect_signals()

    def set_handler(self, handler: SideTerminalHandler) -> None:
        """Store reference to the logging handler for live filter toggling."""
        self._handler_ref = handler

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(34)
        h_lay = QHBoxLayout(header)
        h_lay.setContentsMargins(10, 0, 8, 0)
        h_lay.setSpacing(6)

        self._title_label = QLabel("LIVE TELEMETRY")
        self._title_label.setProperty("cssClass", "subheading")
        self._title_label.setStyleSheet("font-size: 11px; font-weight: 700; letter-spacing: 0.6px;")
        h_lay.addWidget(self._title_label)

        h_lay.addStretch()

        # Routine Polling Filter toggle button (silences spam every 2s)
        self._poll_toggle_btn = QPushButton("🔇 Quiet")
        self._poll_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._poll_toggle_btn.setToolTip("Quiet mode: Hides repetitive background device polls when idle")
        self._poll_toggle_btn.setStyleSheet(
            "padding: 2px 7px; font-size: 10px; min-height: 18px; border-radius: 4px; "
            "background: rgba(10, 132, 255, 0.15); color: #0A84FF; border: 1px solid rgba(10, 132, 255, 0.3);"
        )
        self._poll_toggle_btn.clicked.connect(self._toggle_poll_filtering)
        h_lay.addWidget(self._poll_toggle_btn)

        # Clear button
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet("padding: 2px 8px; font-size: 11px; min-height: 18px;")
        self._clear_btn.clicked.connect(self.clear)
        h_lay.addWidget(self._clear_btn)

        # Collapse / Expand toggle button
        self._toggle_btn = QPushButton("»")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setToolTip("Hide / Show Terminal")
        self._toggle_btn.setFixedSize(24, 22)
        self._toggle_btn.setStyleSheet("font-weight: bold; font-size: 11px; padding: 0;")
        self._toggle_btn.clicked.connect(self._toggle_collapse)
        h_lay.addWidget(self._toggle_btn)

        layout.addWidget(header)

        # Terminal text display (strictly read-only)
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)  # Cannot be edited or touched by user
        self._text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._text_edit, 1)

        # Initial greeting banner
        self.append_line("⚡ FlashDock live activity telemetry initialized.", level="info")
        self.append_line("Quiet mode active (routine background polls muted when idle).\n", level="info")

    def _toggle_poll_filtering(self) -> None:
        self._filter_polls = not self._filter_polls
        if self._handler_ref:
            self._handler_ref.filter_routine_polls = self._filter_polls

        if self._filter_polls:
            self._poll_toggle_btn.setText("🔇 Quiet")
            self._poll_toggle_btn.setToolTip("Quiet mode: Hides repetitive background device polls when idle")
            self._poll_toggle_btn.setStyleSheet(
                "padding: 2px 7px; font-size: 10px; min-height: 18px; border-radius: 4px; "
                "background: rgba(10, 132, 255, 0.15); color: #0A84FF; border: 1px solid rgba(10, 132, 255, 0.3);"
            )
            self.append_line("🔇 Routine background polling filtered.", level="info")
        else:
            self._poll_toggle_btn.setText("🔊 Verbose")
            self._poll_toggle_btn.setToolTip("Verbose mode: Shows all background health checks and raw device polls")
            self._poll_toggle_btn.setStyleSheet(
                "padding: 2px 7px; font-size: 10px; min-height: 18px; border-radius: 4px; "
                "background: rgba(255, 159, 10, 0.15); color: #FF9F0A; border: 1px solid rgba(255, 159, 10, 0.3);"
            )
            self.append_line("🔊 Verbose mode enabled (showing all background device polls).", level="info")

    def _connect_signals(self) -> None:
        self.log_signal.connect(self._append_formatted)

    def _toggle_collapse(self) -> None:
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self.setFixedWidth(40)
            self._text_edit.setVisible(False)
            self._clear_btn.setVisible(False)
            self._title_label.setText("📟")
            self._toggle_btn.setText("«")
        else:
            self.setFixedWidth(320)
            self._text_edit.setVisible(True)
            self._clear_btn.setVisible(True)
            self._title_label.setText("LIVE TELEMETRY")
            self._toggle_btn.setText("»")

    @Slot()
    def clear(self) -> None:
        self._text_edit.clear()

    def append_line(self, text: str, level: str = "info") -> None:
        """Thread-safe public method to log a line to the terminal."""
        self.log_signal.emit(text, level)

    @Slot(str, str)
    def _append_formatted(self, text: str, level: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        prefix = f"[{now}]"

        color_map = {
            "info": "#a1a1aa",     # Neutral secondary
            "command": "#3b82f6",  # SaaS Blue
            "warning": "#eab308",  # Amber
            "error": "#ef4444",    # Destructive Red
            "critical": "#dc2626", # Deep Red
        }
        color = color_map.get(level.lower(), "#f4f4f5")

        # HTML formatting for colored log lines
        clean_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_line = f"<span style='color:#52525b;'>{prefix}</span> <span style='color:{color};'>{clean_text}</span>"
        self._text_edit.appendHtml(html_line)

        # Auto-scroll to bottom
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)
