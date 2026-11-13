"""
FlashDock — System Self-Test Diagnostics Modal Dialog.

Phase 16 Release Hardening: Apple HIG modal displaying system health checks,
toolchain availability, filesystem permissions, and driver status with full
dark/light theme adaptability and 1-click Setup Wizard launcher.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from flashdock.config import Config
from flashdock.core.selftest import SystemSelfTester, SelfTestReport, SelfTestResult
from flashdock.logger import get_logger
from flashdock.ui.icon_assets import create_icon_label, get_icon, get_icon_pixmap

log = get_logger(__name__)


class SelfTestDialog(QDialog):
    """Apple HIG System Health & Toolchain Self-Test Dialog."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("System Health & Toolchain Self-Test")
        self.setWindowIcon(get_icon("flash", 16))
        self.resize(780, 620)
        self.setMinimumSize(660, 500)

        self._config = Config.load()
        self.tester = SystemSelfTester()
        self.latest_report: SelfTestReport | None = None

        self._build_ui()
        self.run_diagnostics()

    def _is_dark(self) -> bool:
        return self._config.get("theme", "dark").lower() != "light"

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # Header
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title_box = QHBoxLayout()
        title_box.setSpacing(8)
        flash_ico = create_icon_label("flash", 22)
        title_box.addWidget(flash_ico)
        title = QLabel("System Health & Self-Test")
        title.setObjectName("titleLabel")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        title_box.addWidget(title)
        title_box.addStretch()
        header_layout.addLayout(title_box)

        subtitle = QLabel(
            "Verifies runtime prerequisites, ADB/Fastboot toolchains, filesystem permissions, and network readiness."
        )
        subtitle.setObjectName("subtitleLabel")
        subtitle.setStyleSheet("color: #8E8E8E; font-size: 13px;")
        subtitle.setWordWrap(True)
        header_layout.addWidget(subtitle)

        main_layout.addLayout(header_layout)

        # Summary Bar Card
        self.summary_card = QFrame()
        self.summary_card.setObjectName("summaryCard")
        summary_layout = QHBoxLayout(self.summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)

        self.status_icon_label = QLabel()
        self.status_icon_label.setFixedSize(28, 28)
        self.status_icon_label.setPixmap(get_icon_pixmap("refresh", 28, color="#8E8E8E"))
        summary_layout.addWidget(self.status_icon_label)

        status_text_layout = QVBoxLayout()
        self.summary_title = QLabel("Running system diagnostics...")
        self.summary_title.setStyleSheet("font-size: 15px; font-weight: 700;")
        self.summary_details = QLabel("Please wait while FlashDock checks dependencies.")
        self.summary_details.setStyleSheet("font-size: 12px; color: #8E8E8E;")
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
        footer_layout.setSpacing(10)

        self.btn_rerun = QPushButton("Re-run Self-Test")
        self.btn_rerun.setIcon(get_icon("refresh", 14))
        self.btn_rerun.setStyleSheet(
            "QPushButton { background: rgba(255, 255, 255, 0.08); color: #E5E5E5; border-radius: 8px; padding: 8px 16px; font-weight: 600; } "
            "QPushButton:hover { background: rgba(255, 255, 255, 0.15); }"
        )
        self.btn_rerun.clicked.connect(self.run_diagnostics)
        footer_layout.addWidget(self.btn_rerun)

        self.btn_copy = QPushButton("Copy Diagnostics Report")
        self.btn_copy.setIcon(get_icon("copy", 14))
        self.btn_copy.setStyleSheet(
            "QPushButton { background: rgba(255, 255, 255, 0.08); color: #E5E5E5; border-radius: 8px; padding: 8px 16px; font-weight: 600; } "
            "QPushButton:hover { background: rgba(255, 255, 255, 0.15); }"
        )
        self.btn_copy.clicked.connect(self._copy_report)
        footer_layout.addWidget(self.btn_copy)

        footer_layout.addStretch()

        self.btn_close = QPushButton("Done")
        self.btn_close.setStyleSheet(
            "QPushButton { background: #6A6A6A; color: #FFFFFF; border-radius: 8px; padding: 8px 24px; font-weight: 600; } "
            "QPushButton:hover { background: #555555; }"
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
        dark = self._is_dark()

        # Update Summary Card
        if report.is_healthy:
            self.status_icon_label.setPixmap(get_icon_pixmap("check", 28, color="#ADADAD"))
            self.summary_title.setText(f"System Ready — {report.passed_count}/{report.total_count} Checks Passed")
            self.summary_details.setText(f"{report.warn_count} non-critical warnings. Workstation is operational.")
            if dark:
                self.summary_card.setStyleSheet(
                    "QFrame#summaryCard { background: #222222; border-radius: 12px; border: none; padding: 12px; color: #ADADAD; }"
                )
            else:
                self.summary_card.setStyleSheet(
                    "QFrame#summaryCard { background: #FAFAFA; border-radius: 12px; border: none; padding: 12px; color: #515151; }"
                )
        else:
            self.status_icon_label.setPixmap(get_icon_pixmap("warning", 28, color="#8E8E8E"))
            self.summary_title.setText(f"Prerequisites Incomplete — {report.fail_count} Failed")
            self.summary_details.setText(f"{report.passed_count} passed, {report.warn_count} warnings. Review failures below.")
            if dark:
                self.summary_card.setStyleSheet(
                    "QFrame#summaryCard { background: #1A1A1A; border-radius: 12px; border: none; padding: 12px; color: #8E8E8E; }"
                )
            else:
                self.summary_card.setStyleSheet(
                    "QFrame#summaryCard { background: #F5F5F5; border-radius: 12px; border: none; padding: 12px; color: #363636; }"
                )

        # Clear existing card widgets
        while self.cards_layout.count() > 1:
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add result cards
        for res in report.results:
            card = self._create_result_card(res, dark)
            self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)

        self.btn_rerun.setEnabled(True)
        self.btn_rerun.setText("Re-run Self-Test")
        self.btn_rerun.setIcon(get_icon("refresh", 14))

    def _create_result_card(self, result: SelfTestResult, dark: bool) -> QFrame:
        card = QFrame()
        if dark:
            bg = "#1C1C1C"
            border = "#2C2C2C"
            text_color = "#F2F2F2"
            sub_color = "#AEAEAE"
            badge_bg = "rgba(166, 166, 166, 0.2)"
            badge_fg = "#A6A6A6"
            badge_text = "PASS"

            if result.status == "WARN":
                border = "rgba(169, 169, 169, 0.3)"
                badge_bg = "rgba(169, 169, 169, 0.2)"
                badge_fg = "#A9A9A9"
                badge_text = "WARN"
            elif result.status == "FAIL":
                border = "rgba(108, 108, 108, 0.3)"
                badge_bg = "rgba(108, 108, 108, 0.2)"
                badge_fg = "#6C6C6C"
                badge_text = "FAIL"
        else:
            bg = "#FFFFFF"
            border = "#E5E5E5"
            text_color = "#1D1D1D"
            sub_color = "#6E6E6E"
            badge_bg = "#F1F1F1"
            badge_fg = "#676767"
            badge_text = "PASS"

            if result.status == "WARN":
                bg = "#FBFBFB"
                border = "#E4E4E4"
                badge_bg = "#F2F2F2"
                badge_fg = "#626262"
                badge_text = "WARN"
            elif result.status == "FAIL":
                bg = "#F5F5F5"
                border = "#D5D5D5"
                badge_bg = "#E8E8E8"
                badge_fg = "#3D3D3D"
                badge_text = "FAIL"

        card.setStyleSheet(
            f"QFrame {{ background: {bg}; border-radius: 10px; border: none; padding: 12px; }}"
        )
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Top row: Name + Category badge + Status badge
        top_row = QHBoxLayout()
        name_lbl = QLabel(result.name)
        name_lbl.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {text_color};")
        top_row.addWidget(name_lbl)

        cat_lbl = QLabel(result.category)
        cat_lbl.setStyleSheet(
            "background: rgba(142, 142, 142, 0.15); color: #8E8E8E; border-radius: 4px; padding: 2px 6px; font-size: 11px;"
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
        detail_lbl.setStyleSheet(f"font-size: 12px; color: {sub_color};")
        detail_lbl.setWordWrap(True)
        layout.addWidget(detail_lbl)

        # Remediation if available
        if result.remediation:
            fix_lbl = QLabel(f"Suggestion: {result.remediation}")
            fix_lbl.setStyleSheet("font-size: 12px; color: #A9A9A9; font-style: italic;")
            fix_lbl.setWordWrap(True)
            layout.addWidget(fix_lbl)

        return card

    def _copy_report(self) -> None:
        if self.latest_report:
            clipboard = QApplication.clipboard()
            clipboard.setText(self.latest_report.format_text())
            self.btn_copy.setText("Copied!")
            self.btn_copy.setIcon(get_icon("check", 14))
            QApplication.processEvents()
