"""
FlashDock — Status bar widget.

The status bar sits at the bottom of the main window and shows:
  • Online / Offline indicator (with coloured dot)
  • Connected device summary (or "No device")
  • Active mode (Simple / Advanced / Dry-Run)
  • Database cache age
  • Tool versions (placeholder until Tools Manager)

It refreshes automatically via signals from the NetworkMonitor and
device-detection engine.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from flashdock.logger import get_logger

log = get_logger(__name__)


class StatusDot(QLabel):
    """A tiny coloured circle used as an online/device indicator."""

    _DOT_CSS = (
        "background-color: {color}; border-radius: 3px; "
        "min-width: 6px; max-width: 6px; "
        "min-height: 6px; max-height: 6px;"
    )

    def __init__(self, color: str = "#52525b", parent: QWidget | None = None):
        super().__init__(parent)
        self.set_color(color)

    def set_color(self, color: str) -> None:
        self.setStyleSheet(self._DOT_CSS.format(color=color))


class StatusBarWidget(QFrame):
    """Custom status bar displayed at the bottom of the main window.

    Rather than using the built-in ``QMainWindow.statusBar()`` (which
    is clunky), this is a styled ``QFrame`` that sits in the main
    layout and updates through public slots.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(30)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(16)

        # ---- Network indicator ----
        self._net_dot = StatusDot("#86868b")
        self._net_label = QLabel("Checking…")
        self._net_label.setProperty("cssClass", "secondary")
        self._net_label.setStyleSheet("font-size: 11px; font-weight: 500;")
        layout.addWidget(self._net_dot)
        layout.addWidget(self._net_label)

        layout.addWidget(self._separator())

        # ---- Device indicator ----
        self._dev_dot = StatusDot("#86868b")
        self._dev_label = QLabel("No device")
        self._dev_label.setProperty("cssClass", "secondary")
        self._dev_label.setStyleSheet("font-size: 11px;")
        layout.addWidget(self._dev_dot)
        layout.addWidget(self._dev_label)

        layout.addWidget(self._separator())

        # ---- Mode label ----
        self._mode_label = QLabel("Simple mode")
        self._mode_label.setProperty("cssClass", "subheading")
        self._mode_label.setStyleSheet("font-size: 11px; font-weight: 600;")
        layout.addWidget(self._mode_label)

        layout.addWidget(self._separator())

        # ---- Cache age ----
        self._cache_label = QLabel("Cache: —")
        self._cache_label.setProperty("cssClass", "secondary")
        self._cache_label.setStyleSheet("font-size: 11px; font-family: 'JetBrains Mono', 'Cascadia Code', monospace;")
        layout.addWidget(self._cache_label)

        layout.addStretch()

        # ---- Version ----
        from flashdock import __version__
        self._version_label = QLabel(f"v{__version__}")
        self._version_label.setProperty("cssClass", "secondary")
        self._version_label.setStyleSheet("font-size: 11px; font-family: 'JetBrains Mono', 'Cascadia Code', monospace;")
        layout.addWidget(self._version_label)

    # ---- Helpers -----------------------------------------------------------

    @staticmethod
    def _separator() -> QFrame:
        sep = QFrame()
        sep.setFixedHeight(12)
        sep.setFixedWidth(1)
        sep.setProperty("cssClass", "separator")
        return sep

    # ---- Public update slots -----------------------------------------------

    @Slot(bool)
    def update_network(self, is_online: bool) -> None:
        """Called by NetworkMonitor.on_change (marshalled to the UI thread)."""
        if is_online:
            self._net_dot.set_color("#22c55e")
            self._net_label.setText("Online")
            self._net_label.setStyleSheet("color: #22c55e; font-size: 11px; font-weight: 600;")
        else:
            self._net_dot.set_color("#ef4444")
            self._net_label.setText("Offline")
            self._net_label.setStyleSheet("color: #ef4444; font-size: 11px; font-weight: 600;")

    @Slot(str, str)
    def update_device(self, mode: str, summary: str) -> None:
        """Called when device detection runs."""
        if mode == "not_connected":
            self._dev_dot.set_color("#86868b")
            self._dev_label.setText("No device")
            self._dev_label.setProperty("cssClass", "secondary")
            self._dev_label.setStyleSheet("font-size: 11px;")
        else:
            self._dev_dot.set_color("#22c55e")
            text = summary if summary else f"Connected ({mode})"
            self._dev_label.setText(text)
            self._dev_label.setStyleSheet("font-size: 11px; font-weight: 600;")

    @Slot(str)
    def update_mode(self, mode_name: str) -> None:
        """Update the mode label (Simple / Advanced / Dry-Run)."""
        self._mode_label.setText(mode_name)

    @Slot(str)
    def update_cache_age(self, age_text: str) -> None:
        """Show how old the compatibility cache is."""
        self._cache_label.setText(f"Cache: {age_text}")
