"""
FlashDock — Checklist screen.

Displays a green/red checklist of everything needed before flashing:
phone settings, files, and safety items.  Auto-checked items show
live results; manual items show guidance.

Spec reference: Section 7.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.checklist import (
    CheckItem,
    ChecklistResult,
    ChecklistRunner,
    CheckStatus,
)
from flashdock.core.device import DeviceInfo
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.ui.icon_assets import create_icon_label, get_icon

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Colour palette for statuses
# ---------------------------------------------------------------------------
_STATUS_COLORS = {
    CheckStatus.PASS: "#3fb950",
    CheckStatus.FAIL: "#f85149",
    CheckStatus.WARN: "#d29922",
    CheckStatus.SKIP: "#8b949e",
    CheckStatus.INFO: "#58a6ff",
}

_CATEGORY_LABELS = {
    "phone_settings": "Phone Settings",
    "files":          "Files to Have Ready",
    "safety":         "Safety",
}

_CATEGORY_ICONS = {
    "phone_settings": "phone",
    "files":          "folder",
    "safety":         "shield",
}

_STATUS_ICON_NAMES = {
    CheckStatus.PASS: ("check", "#3fb950"),
    CheckStatus.FAIL: ("cross", "#f85149"),
    CheckStatus.WARN: ("warning", "#d29922"),
    CheckStatus.SKIP: ("info", "#8b949e"),
    CheckStatus.INFO: ("info", "#58a6ff"),
}

_CATEGORY_ORDER = ["phone_settings", "files", "safety"]


# ---------------------------------------------------------------------------
# Individual check item widget
# ---------------------------------------------------------------------------
class _CheckItemWidget(QFrame):
    """One row in the checklist — icon, label, detail, fix hint."""

    def __init__(self, item: CheckItem, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("cssClass", "card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        # Top row: icon + label + auto/manual badge
        top = QHBoxLayout()
        top.setSpacing(8)

        icon_name, icon_col = _STATUS_ICON_NAMES.get(item.status, ("check", "#3fb950"))
        icon_lbl = create_icon_label(icon_name, 18, color=icon_col)
        top.addWidget(icon_lbl)

        label = QLabel(item.label)
        label.setProperty("cssClass", "subheading")
        top.addWidget(label, 1)

        if not item.auto_checked:
            badge = QLabel("manual")
            badge.setProperty("cssClass", "muted")
            top.addWidget(badge)

        layout.addLayout(top)

        # Detail line
        if item.detail:
            detail = QLabel(item.detail)
            detail.setWordWrap(True)
            detail.setProperty("cssClass", "muted")
            layout.addWidget(detail)

        # Fix hint (shown only for non-passing items)
        if item.fix_hint and item.status in (CheckStatus.FAIL, CheckStatus.WARN, CheckStatus.INFO):
            hint_frame = QFrame()
            hint_frame.setProperty("cssClass", "warn_banner")
            hint_layout = QHBoxLayout(hint_frame)
            hint_layout.setContentsMargins(8, 6, 8, 6)
            hint_layout.setSpacing(6)
            hint_layout.addWidget(create_icon_label("info", 14))

            hint_label = QLabel(item.fix_hint)
            hint_label.setWordWrap(True)
            hint_label.setProperty("cssClass", "warning")
            hint_layout.addWidget(hint_label, 1)
            layout.addWidget(hint_frame)


# ---------------------------------------------------------------------------
# Category section
# ---------------------------------------------------------------------------
class _CategorySection(QFrame):
    """A collapsible section for one checklist category."""

    def __init__(self, category: str, items: list[CheckItem], parent: QWidget | None = None):
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header with category label and pass/fail counts
        header = QHBoxLayout()
        header.setSpacing(8)

        cat_icon_name = _CATEGORY_ICONS.get(category, "check")
        header.addWidget(create_icon_label(cat_icon_name, 16))

        title = QLabel(_CATEGORY_LABELS.get(category, category.title()))
        title.setProperty("cssClass", "subheading")
        header.addWidget(title)

        pass_count = sum(1 for i in items if i.status == CheckStatus.PASS)
        fail_count = sum(1 for i in items if i.status == CheckStatus.FAIL)
        total = len(items)

        stats = QLabel(f"{pass_count}/{total} passed")
        stats.setProperty("cssClass", "success" if fail_count == 0 else "error")
        header.addWidget(stats)
        header.addStretch()

        layout.addLayout(header)

        # Items
        for item in items:
            widget = _CheckItemWidget(item)
            layout.addWidget(widget)


# ---------------------------------------------------------------------------
# Main checklist screen
# ---------------------------------------------------------------------------
class ChecklistScreen(QWidget):
    """The full checklist page — shown when the user clicks 'Checklist'."""

    def __init__(
        self,
        adb: ADB,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._adb = adb
        self._result: Optional[ChecklistResult] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 12)
        layout.setSpacing(12)

        # ---- Header ----
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_h = QHBoxLayout()
        title_h.setSpacing(8)
        title_h.addWidget(create_icon_label("checklist", 22))
        title = QLabel("Pre-Flash Checklist")
        title.setProperty("cssClass", "heading")
        title_h.addWidget(title)
        header_row.addLayout(title_h)
        header_row.addStretch()

        self._refresh_btn = QPushButton("Re-check")
        self._refresh_btn.setIcon(get_icon("refresh", 14))
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setProperty("cssClass", "primary")
        self._refresh_btn.clicked.connect(lambda: self.run_checks(self._last_device))
        header_row.addWidget(self._refresh_btn)

        layout.addLayout(header_row)

        # ---- Summary bar ----
        self._summary_label = QLabel("")
        self._summary_label.setProperty("cssClass", "muted")
        layout.addWidget(self._summary_label)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(8)
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        # ---- Scroll area for checklist items ----
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        layout.addWidget(self._scroll, 1)

        self._last_device: Optional[DeviceInfo] = None

        # Placeholder text
        placeholder = QLabel(
            "Click 'Re-check' or open this screen with a device connected\n"
            "to run the automated pre-flash checklist."
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setProperty("cssClass", "muted")
        self._content_layout.insertWidget(0, placeholder)

    def run_checks(self, device: Optional[DeviceInfo] = None) -> ChecklistResult:
        """Run all checks and rebuild the UI."""
        self._last_device = device

        runner = ChecklistRunner(adb=self._adb, device=device)
        self._result = runner.run()

        self._rebuild_ui()
        return self._result

    def _rebuild_ui(self) -> None:
        """Clear and rebuild the checklist display."""
        # Clear existing widgets
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._result:
            return

        result = self._result

        # Summary
        self._summary_label.setText(
            f"{result.summary}  |  Device: {result.device_model or 'None'}"
        )

        # Progress bar
        if result.total > 0:
            pct = int((result.pass_count / result.total) * 100)
            self._progress.setValue(pct)

        # Group items by category and render in order
        by_cat: dict[str, list[CheckItem]] = {}
        for item in result.items:
            by_cat.setdefault(item.category, []).append(item)

        for cat in _CATEGORY_ORDER:
            items = by_cat.get(cat, [])
            if items:
                section = _CategorySection(cat, items)
                self._content_layout.addWidget(section)

        self._content_layout.addStretch()
        log.info("Checklist UI rebuilt: %s", result.summary)
