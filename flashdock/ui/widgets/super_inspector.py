"""
Non-blocking QThread Worker and High-DPI UI Inspector for Android super.img.
Place in flashdock/ui/widgets/super_inspector.py
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.super_img import (
    SuperImageError,
    SuperMetadataSummary,
    open_mmap_view,
    parse_super_metadata,
    unpack_super_partition,
)

try:
    from flashdock.ui.dpi_layout import dp, apply_anti_clipping_label
except ImportError:
    def dp(val: int) -> int:
        return val
    def apply_anti_clipping_label(lbl: QLabel) -> None:
        lbl.setWordWrap(True)

try:
    from flashdock.ui.theme_tokens import PALETTE
except ImportError:
    PALETTE = {
        "surface_card": "#1A1D24",
        "border_subtle": "#2A2F3A",
        "text_primary": "#F3F4F6",
        "text_secondary": "#9CA3AF",
        "accent_primary": "#3B82F6",
        "status_success": "#10B981",
    }

class SuperUnpackWorker(QThread):
    """Non-blocking background worker for inspecting and extracting super.img partitions."""

    progress_changed = Signal(int, int)
    inspection_ready = Signal(object)
    unpack_finished = Signal(str, int)
    error_occurred = Signal(str)

    def __init__(
        self,
        super_path: str | Path,
        extract_partition: Optional[str] = None,
        output_path: Optional[str | Path] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.super_path = Path(super_path)
        self.extract_partition = extract_partition
        self.output_path = Path(output_path) if output_path else None

    def run(self) -> None:
        try:
            if self.extract_partition and self.output_path:
                written = unpack_super_partition(
                    self.super_path,
                    self.extract_partition,
                    self.output_path,
                    progress_cb=lambda cur, tot: self.progress_changed.emit(cur, tot),
                )
                self.unpack_finished.emit(str(self.output_path), written)
            else:
                with open_mmap_view(self.super_path) as mv:
                    summary = parse_super_metadata(mv)
                self.inspection_ready.emit(summary)
        except Exception as exc:
            self.error_occurred.emit(str(exc))

class SuperImageInspectorWidget(QFrame):
    """High-DPI anti-clipping Inspector & GSI Swapper widget for super.img."""

    partition_extract_requested = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("SuperImageInspectorCard")
        self._summary: Optional[SuperMetadataSummary] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(dp(16), dp(16), dp(16), dp(16))
        layout.setSpacing(dp(12))

        header_row = QHBoxLayout()
        self.title_label = QLabel("Dynamic Partition Inspector (super.img)")
        self.title_label.setMinimumHeight(dp(26))
        apply_anti_clipping_label(self.title_label)

        self.badge_label = QLabel("IDLE")
        self.badge_label.setMinimumHeight(dp(24))
        self.badge_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        header_row.addWidget(self.title_label, 1)
        header_row.addWidget(self.badge_label, 0)
        layout.addLayout(header_row)

        self.meta_label = QLabel("Drop or select a raw/sparse super.img to inspect LP metadata.")
        self.meta_label.setMinimumHeight(dp(22))
        apply_anti_clipping_label(self.meta_label)
        layout.addWidget(self.meta_label)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Partition", "Group", "Extents", "Size (MiB)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setMinimumHeight(dp(160))
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.table)

        action_row = QHBoxLayout()
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimumHeight(dp(20))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.extract_btn = QPushButton("Extract Selected Partition", self)
        self.extract_btn.setMinimumHeight(dp(34))
        self.extract_btn.setEnabled(False)
        self.extract_btn.clicked.connect(self._on_extract_clicked)

        action_row.addWidget(self.progress_bar, 1)
        action_row.addWidget(self.extract_btn, 0)
        layout.addLayout(action_row)

    def load_summary(self, summary: SuperMetadataSummary) -> None:
        """Populate table and status badges from parsed SuperMetadataSummary."""
        self._summary = summary
        fmt_tag = "SPARSE" if summary.is_sparse else "RAW"
        chk_ok = summary.geometry.checksum_valid and summary.header_checksum_valid and summary.tables_checksum_valid
        self.badge_label.setText(f"{fmt_tag} • LP v{summary.major_version}.{summary.minor_version}")
        self.meta_label.setText(
            f"Block Size: {summary.geometry.logical_block_size}B | "
            f"Slots: {summary.geometry.metadata_slot_count} | "
            f"SHA-256 Verified: {'YES' if chk_ok else 'NO'}"
        )

        self.table.setRowCount(len(summary.partitions))
        for row, part in enumerate(summary.partitions):
            size_mib = part.total_size / (1024 * 1024)
            self.table.setItem(row, 0, QTableWidgetItem(part.name))
            self.table.setItem(row, 1, QTableWidgetItem(part.group_name))
            self.table.setItem(row, 2, QTableWidgetItem(str(part.num_extents)))
            self.table.setItem(row, 3, QTableWidgetItem(f"{size_mib:.2f}"))

        self.extract_btn.setEnabled(len(summary.partitions) > 0)

    def _on_extract_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0 and self.table.rowCount() > 0:
            row = 0
        item = self.table.item(row, 0)
        if item is not None:
            self.partition_extract_requested.emit(item.text())

### **Checkpoint 4: Synthetic Round-Trip, Fuzzing & High-DPI Test Suite (tests/test_super_img_v160.py)**
