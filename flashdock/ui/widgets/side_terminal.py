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

from flashdock.ui.icon_assets import get_icon


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
    collapse_requested = Signal()   # Emitted when the header collapse button is clicked

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(600)
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
        self._poll_toggle_btn = QPushButton("Quiet")
        self._poll_toggle_btn.setIcon(get_icon("info", 11, color="#737373"))
        self._poll_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._poll_toggle_btn.setToolTip("Quiet mode: Hides repetitive background device polls when idle")
        self._poll_toggle_btn.setStyleSheet(
            "padding: 2px 7px; font-size: 10px; min-height: 18px; border-radius: 4px; "
            "background: rgba(115, 115, 115, 0.15); color: #737373; border: none;"
        )
        self._poll_toggle_btn.clicked.connect(self._toggle_poll_filtering)
        h_lay.addWidget(self._poll_toggle_btn)

        # Clear button
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.setStyleSheet("padding: 2px 8px; font-size: 11px; min-height: 18px;")
        self._clear_btn.clicked.connect(self.clear)
        h_lay.addWidget(self._clear_btn)

        # Collapse / Expand toggle button in terminal header (Fix 18)
        self._toggle_btn = QPushButton("»")
        self._toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._toggle_btn.setToolTip("Hide Terminal (reclaim workspace canvas)")
        self._toggle_btn.setFixedSize(24, 22)
        self._toggle_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
                font-size: 13px;
                padding: 0;
                background: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
                color: #8E8E8E;
            }
            QPushButton:hover {
                background: rgba(115, 115, 115, 0.2);
                color: #737373;
                border-color: #737373;
            }
        """)
        self._toggle_btn.clicked.connect(self._on_toggle_clicked)
        h_lay.addWidget(self._toggle_btn)

        layout.addWidget(header)

        # Terminal text display (strictly read-only recessed Obsidian Console)
        self._text_edit = QPlainTextEdit()
        self._text_edit.setReadOnly(True)  # Cannot be edited or touched by user
        self._text_edit.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._text_edit.setMaximumBlockCount(5000)  # Capped buffer to prevent memory bloat / layout freeze
        self._text_edit.setStyleSheet(
            "QPlainTextEdit { background-color: #0B0B0B; border: none; "
            "border-radius: 12px; margin: 4px 8px 8px 8px; padding: 8px; color: #ECECEC; "
            "font-family: 'JetBrains Mono', 'Cascadia Code', 'SF Pro Display', Consolas, monospace; "
            "font-size: 11.5px; selection-background-color: #737373; }"
        )
        layout.addWidget(self._text_edit, 1)

        # Initial greeting banner
        self.append_line("FlashDock live activity telemetry initialized.", level="info")
        self.append_line("Quiet mode active (routine background polls muted when idle).\n", level="info")

    def _toggle_poll_filtering(self) -> None:
        self._filter_polls = not self._filter_polls
        if self._handler_ref:
            self._handler_ref.filter_routine_polls = self._filter_polls

        if self._filter_polls:
            self._poll_toggle_btn.setText("Quiet")
            self._poll_toggle_btn.setIcon(get_icon("info", 11, color="#737373"))
            self._poll_toggle_btn.setToolTip("Quiet mode: Hides repetitive background device polls when idle")
            self._poll_toggle_btn.setStyleSheet(
                "padding: 3px 10px; font-size: 10px; min-height: 20px; border-radius: 10px; "
                "background: rgba(115, 115, 115, 0.15); color: #737373; border: none;"
            )
            self.append_line("Routine background polling filtered.", level="info")
        else:
            self._poll_toggle_btn.setText("Verbose")
            self._poll_toggle_btn.setIcon(get_icon("info", 11, color="#A9A9A9"))
            self._poll_toggle_btn.setToolTip("Verbose mode: Shows all background health checks and raw device polls")
            self._poll_toggle_btn.setStyleSheet(
                "padding: 3px 10px; font-size: 10px; min-height: 20px; border-radius: 10px; "
                "background: rgba(169, 169, 169, 0.15); color: #A9A9A9; border: none;"
            )
            self.append_line("Verbose mode enabled (showing all background device polls).", level="info")

    def _connect_signals(self) -> None:
        self.log_signal.connect(self._append_formatted)

    def _on_toggle_clicked(self) -> None:
        self.collapse_requested.emit()

    def _toggle_collapse(self) -> None:
        self._is_collapsed = not self._is_collapsed
        if self._is_collapsed:
            self.setMinimumWidth(40)
            self.setMaximumWidth(40)
            self._text_edit.setVisible(False)
            self._clear_btn.setVisible(False)
            self._poll_toggle_btn.setVisible(False)
            self._title_label.setText("LOG")
            self._toggle_btn.setText("«")
        else:
            self.setMinimumWidth(260)
            self.setMaximumWidth(600)
            self._text_edit.setVisible(True)
            self._clear_btn.setVisible(True)
            self._poll_toggle_btn.setVisible(True)
            self._title_label.setText("LIVE TELEMETRY")
            self._toggle_btn.setText("»")

    @Slot()
    def clear(self) -> None:
        self._text_edit.clear()

    def append_line(self, text: str, level: str = "info") -> None:
        """Thread-safe public method to log a line to the terminal."""
        self.log_signal.emit(text, level)

    def append_colored_stream(self, level: str, message: str) -> None:
        """Stream log message with explicit colored GSM Suite prefix."""
        self.log_signal.emit(message, level)

    @Slot(str, str)
    def _append_formatted(self, text: str, level: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        time_tag = f"<span style='color:#939393;'>[{now}]</span>"
        lvl_key = level.upper().strip()

        # Prefix color mapping & Glowing Status Pills:
        # Electric Blue [INFO], Warm Amber [WARN], Emerald Green [SUCCESS], Crimson Red [ERROR]
        prefix_styles = {
            "INFO": ("#737373", "rgba(115, 115, 115, 0.18)", "rgba(115, 115, 115, 0.35)", "[INFO]"),
            "WARN": ("#A9A9A9", "rgba(169, 169, 169, 0.18)", "rgba(169, 169, 169, 0.35)", "[WARN]"),
            "WARNING": ("#A9A9A9", "rgba(169, 169, 169, 0.18)", "rgba(169, 169, 169, 0.35)", "[WARN]"),
            "SUCCESS": ("#A6A6A6", "rgba(166, 166, 166, 0.18)", "rgba(166, 166, 166, 0.35)", "[SUCCESS]"),
            "ERROR": ("#6C6C6C", "rgba(108, 108, 108, 0.18)", "rgba(108, 108, 108, 0.35)", "[ERROR]"),
            "CRITICAL": ("#6C6C6C", "rgba(108, 108, 108, 0.18)", "rgba(108, 108, 108, 0.35)", "[CRITICAL]"),
            "COMMAND": ("#7A7A7A", "rgba(122, 122, 122, 0.18)", "rgba(122, 122, 122, 0.35)", "[CMD]"),
        }

        fg_color, bg_pill, border_pill, tag_text = prefix_styles.get(
            lvl_key, ("#939393", "rgba(147, 147, 147, 0.15)", "rgba(147, 147, 147, 0.3)", f"[{lvl_key}]")
        )
        prefix_badge = (
            f"<span style='background: {bg_pill}; color: {fg_color}; border: none; "
            f"border-radius: 4px; padding: 1px 4px; font-weight: 700; font-size: 10px;'>{tag_text}</span>"
        )

        # HTML formatting for colored log lines
        clean_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        html_line = f"{time_tag} {prefix_badge} <span style='color:#ECECEC;'>{clean_text}</span>"
        self._text_edit.appendHtml(html_line)

        # Auto-scroll to bottom
        self._text_edit.moveCursor(QTextCursor.MoveOperation.End)


# ============================================================================
# v1.5.0 High-Frequency Telemetry Capping (5,000 blocks)
# ============================================================================
MAX_TERMINAL_BLOCKS_V150 = 5000
