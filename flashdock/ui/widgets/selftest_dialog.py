"""
FlashDock — System Self-Test Diagnostics Modal Dialog.

Phase 16 Release Hardening: Apple HIG modal displaying system health checks,
toolchain availability, filesystem permissions, and driver status.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.selftest import SystemSelfTester, SelfTestReport, SelfTestResult
from flashdock.logger import get_logger

log = get_logger(__name__)


class SelfTestDialog(QDialog):
    """Apple HIG System Health & Toolchain Self-Test Dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("System Health & Toolchain Self-Test")
        self.resize(720, 580)
        self.setMinimumSize(600, 480)

        self.tester = SystemSelfTester()
        self.latest_report: SelfTestReport | None = None

        self._build_ui()
        self.run_diagnostics()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title = QLabel("⚡ System Health & Self-Test")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header_layout.addWidget(title)

        subtitle = QLabel(
            "Verifies runtime prerequisites, ADB/Fastboot toolchains, filesystem permissions, and network readiness."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setStyleSheet("color: #86868B; font-size: 13px;")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        main_layout.addLayout(header_layout)

        # Summary Bar Card
        self.summary_card = QFrame()
        self.summary_card.setObjectName("cardFrame")
        self.summary_card.setStyleSheet(
            "QFrame#cardFrame { background: #FFFFFF; border-radius: 12px; border: 1px solid #E5E5EA; padding: 14px; }"
        )
        summary_layout = QHBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(12, 10, 12, 10)

        self.status_icon_label = QLabel("⏳")
        self.status_icon_label.setStyleSheet("font-size: 28px;")
        summary_layout.addWidget(self.status_icon_label)

        status_text_layout = QVBoxLayout()
        self.summary_title = QLabel("Running system diagnostics...")
        self.summary_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #1D1D1F;")
        self.summary_details = QLabel("Please wait while FlashDock checks dependencies.")
        self.summary_details.setStyleSheet("font-size: 12px; color: #6E6E73;")
        status_text_layout.addWidget(self.summary_title)
        status_text_layout.addWidget(self.summary_details)
        summary_layout.addLayout(status_text_layout, 1)

        main_layout.addWidget(self.summary_card)

        # Scroll Area for Check Results
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet("background: transparent;")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.addStretch()

        self.scroll_area.setWidget(self.cards_container)
        main_layout.addWidget(self.scroll_area, 1)

        # Action Buttons Footer
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(12)

        self.btn_rerun = QPushButton("🔄 Re-run Self-Test")
        self.btn_rerun.setStyleSheet(
            "QPushButton { background: #E5E5EA; color: #1D1D1F; border-radius: 8px; padding: 8px 16px; font-weight: 600; } "
            "QPushButton:hover { background: #D1D1D6; }"
        )
        self.btn_rerun.clicked.connect(self.run_diagnostics)
        footer_layout.addWidget(self.btn_rerun)

        self.btn_copy = QPushButton("📋 Copy Diagnostics Report")
        self.btn_copy.setStyleSheet(
            "QPushButton { background: #E5E5EA; color: #1D1D1F; border-radius: 8px; padding: 8px 16px; font-weight: 600; } "
            "QPushButton:hover { background: #D1D1D6; }"
        )
        self.btn_copy.clicked.connect(self._copy_report)
        footer_layout.addWidget(self.btn_copy)

        footer_layout.addStretch()

        self.btn_close = QPushButton("Done")
        self.btn_close.setStyleSheet(
            "QPushButton { background: #007AFF; color: #FFFFFF; border-radius: 8px; padding: 8px 24px; font-weight: 600; } "
            "QPushButton:hover { background: #0062CC; }"
        )
        self.btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(self.btn_close)

        main_layout.addLayout(footer_layout)

    def run_diagnostics(self) -> None:
        """Executes all diagnostics and populates the cards."""
        self.btn_rerun.setEnabled(False)
        self.btn_rerun.setText("Running...")
        QApplication.processEvents()

        report = self.tester.run_all_checks()
        self.latest_report = report

        # Update Summary Card
        if report.is_healthy:
            self.status_icon_label.setText("✅")
            self.summary_title.setText(f"System Ready — {report.passed_count}/{report.total_count} Checks Passed")
            self.summary_details.setText(f"{report.warn_count} non-critical warnings. Workstation is operational.")
            self.summary_card.setStyleSheet(
                "QFrame#cardFrame { background: #F0FDF4; border-radius: 12px; border: 1px solid #BBF7D0; padding: 14px; }"
            )
        else:
            self.status_icon_label.setText("⚠️")
            self.summary_title.setText(f"Prerequisites Incomplete — {report.fail_count} Failed")
            self.summary_details.setText(f"{report.passed_count} passed, {report.warn_count} warnings. Review failures below.")
            self.summary_card.setStyleSheet(
                "QFrame#cardFrame { background: #FEF2F2; border-radius: 12px; border: 1px solid #FECACA; padding: 14px; }"
            )

        # Clear existing card widgets
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add result cards
        for res in report.results:
            card = self._create_result_card(res)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        self.btn_rerun.setEnabled(True)
        self.btn_rerun.setText("🔄 Re-run Self-Test")

    def _create_result_card(self, result: SelfTestResult) -> QFrame:
        card = QFrame()
        bg = "#FFFFFF"
        border = "#E5E5EA"
        badge_bg = "#E8F5E9"
        badge_fg = "#2E7D32"
        badge_text = "PASS"

        if result.status == "WARN":
            bg = "#FFFBEB"
            border = "#FDE68A"
            badge_bg = "#FEF3C7"
            badge_fg = "#B45309"
            badge_text = "WARN"
        elif result.status == "FAIL":
            bg = "#FEF2F2"
            border = "#FECACA"
            badge_bg = "#FEE2E2"
            badge_fg = "#B91C1C"
            badge_text = "FAIL"

        card.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 10px; border: 1px solid {border}; padding: 12px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Top row: Name + Category badge + Status badge
        top_row = QHBoxLayout()
        name_lbl = QLabel(result.name)
        name_lbl.setStyleSheet("font-size: 14px; font-weight: 600; color: #1D1D1F;")
        top_row.addWidget(name_lbl)

        cat_lbl = QLabel(result.category)
        cat_lbl.setStyleSheet(
            "background: #F2F2F7; color: #6E6E73; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
        )
        top_row.addWidget(cat_lbl)

        top_row.addStretch()

        badge_lbl = QLabel(badge_text)
        badge_lbl.setStyleSheet(
            f"background: {badge_bg}; color: {badge_fg}; font-weight: 700; border-radius: 4px; padding: 2px 8px; font-size: 11px;"
        )
        top_row.addWidget(badge_lbl)
        layout.addLayout(top_row)

        # Detail text
        detail_lbl = QLabel(result.detail)
        detail_lbl.setStyleSheet("font-size: 12px; color: #3A3A3C;")
        detail_lbl.setWordWrap(True)
        layout.addWidget(detail_lbl)

        # Remediation if available
        if result.remediation:
            fix_lbl = QLabel(f"💡 Suggestion: {result.remediation}")
            fix_lbl.setStyleSheet("font-size: 12px; color: #D97706; font-style: italic;")
            fix_lbl.setWordWrap(True)
            layout.addWidget(fix_lbl)

        return card

    def _copy_report(self) -> None:
        if self.latest_report:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.latest_report.format_text())
            self.btn_copy.setText("✓ Copied!")
            QApplication.processEvents()
