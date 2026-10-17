"""
Non-blocking QThread Worker and High-DPI UI Card for Emergency Protocol Streaming
(Qualcomm Sahara Firehose ELF & Unisoc FDL1/FDL2 SRAM/DRAM Loader).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.emergency_transfer import (
    SerialPortLike,
    stream_sahara_firehose,
    stream_unisoc_fdl,
)

try:
    from flashdock.ui.dpi_layout import apply_anti_clipping_label, dp
except ImportError:
    def dp(val: int) -> int:
        return val
    def apply_anti_clipping_label(lbl: QLabel) -> None:
        lbl.setWordWrap(True)

class EmergencyTransferWorker(QThread):
    """Non-blocking worker for Sahara ELF or Unisoc FDL1/FDL2 serial streaming."""

    progress_changed = Signal(int, int)
    stage_changed = Signal(str)
    transfer_completed = Signal(object)
    transfer_failed = Signal(str)

    def __init__(
        self,
        port: SerialPortLike,
        protocol: str,
        binary_path: Union[str, Path, bytes],
        target_address: int = 0x5000,
        stage_name: str = "FDL1",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.port = port
        self.protocol = protocol.upper()
        self.binary_path = binary_path
        self.target_address = target_address
        self.stage_name = stage_name
        self._abort_requested = False

    def request_abort(self) -> None:
        self._abort_requested = True

    def is_aborted(self) -> bool:
        return self._abort_requested

    def run(self) -> None:
        try:
            if self.protocol == "SAHARA":
                self.stage_changed.emit("SAHARA • Handshake & Segment Demand Streaming")
                report = stream_sahara_firehose(
                    self.port,
                    self.binary_path,
                    progress_cb=lambda cur, tot: self.progress_changed.emit(cur, tot),
                    abort_cb=self.is_aborted,
                )
                self.transfer_completed.emit(report)
            elif self.protocol == "UNISOC_FDL":
                self.stage_changed.emit(
                    f"UNISOC {self.stage_name} • HDLC 0x7E Streaming @ 0x{self.target_address:08X}"
                )
                report = stream_unisoc_fdl(
                    self.port,
                    self.binary_path,
                    target_address=self.target_address,
                    stage_name=self.stage_name,
                    progress_cb=lambda cur, tot: self.progress_changed.emit(cur, tot),
                    abort_cb=self.is_aborted,
                )
                self.transfer_completed.emit(report)
            else:
                self.transfer_failed.emit(f"Unsupported emergency protocol: {self.protocol}")
        except Exception as exc:
            self.transfer_failed.emit(str(exc))

class EmergencyLoaderWidget(QFrame):
    """High-DPI anti-clipping widget for Sahara Firehose & Unisoc FDL1/FDL2 deployment."""

    start_requested = Signal(str, str, int)
    abort_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("EmergencyLoaderCard")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(dp(16), dp(16), dp(16), dp(16))
        layout.setSpacing(dp(10))

        top_row = QHBoxLayout()
        self.title_label = QLabel("Emergency BootROM Loader (Sahara / Unisoc FDL)")
        self.title_label.setMinimumHeight(dp(26))
        apply_anti_clipping_label(self.title_label)

        self.protocol_combo = QComboBox(self)
        self.protocol_combo.addItems([
            "SAHARA (Qualcomm Firehose ELF)",
            "UNISOC FDL1 (SRAM Init)",
            "UNISOC FDL2 (DRAM Flasher)",
        ])
        self.protocol_combo.setMinimumHeight(dp(30))

        top_row.addWidget(self.title_label, 1)
        top_row.addWidget(self.protocol_combo, 0)
        layout.addLayout(top_row)

        config_row = QHBoxLayout()
        self.path_input = QLineEdit(self)
        self.path_input.setPlaceholderText("Path to prog_firehose_*.elf or fdl1-sign.bin / fdl2-sign.bin")
        self.path_input.setMinimumHeight(dp(32))

        self.addr_input = QLineEdit("0x00005000", self)
        self.addr_input.setPlaceholderText("Load Addr (Hex)")
        self.addr_input.setMinimumHeight(dp(32))
        self.addr_input.setMaximumWidth(dp(140))

        config_row.addWidget(self.path_input, 1)
        config_row.addWidget(self.addr_input, 0)
        layout.addLayout(config_row)

        self.status_label = QLabel("Ready • Select programmer binary and target mode.")
        self.status_label.setMinimumHeight(dp(22))
        apply_anti_clipping_label(self.status_label)
        layout.addWidget(self.status_label)

        bottom_row = QHBoxLayout()
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setMinimumHeight(dp(20))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)

        self.start_btn = QPushButton("Stream Loader", self)
        self.start_btn.setMinimumHeight(dp(34))
        self.start_btn.clicked.connect(self._on_start_clicked)

        self.abort_btn = QPushButton("Abort", self)
        self.abort_btn.setMinimumHeight(dp(34))
        self.abort_btn.setEnabled(False)
        self.abort_btn.clicked.connect(self.abort_requested.emit)

        bottom_row.addWidget(self.progress_bar, 1)
        bottom_row.addWidget(self.start_btn, 0)
        bottom_row.addWidget(self.abort_btn, 0)
        layout.addLayout(bottom_row)

    def update_progress(self, current: int, total: int) -> None:
        if total > 0:
            pct = int((current * 100) / total)
            self.progress_bar.setValue(max(0, min(100, pct)))
            self.status_label.setText(f"Streaming: {current:,} / {total:,} bytes ({pct}%)")

    def _on_start_clicked(self) -> None:
        raw_addr = self.addr_input.text().strip()
        try:
            addr = int(raw_addr, 16) if raw_addr.lower().startswith("0x") else int(raw_addr)
        except ValueError:
            addr = 0x5000
        mode_text = self.protocol_combo.currentText()
        proto = "SAHARA" if mode_text.startswith("SAHARA") else "UNISOC_FDL"
        self.start_requested.emit(proto, self.path_input.text().strip(), addr)

### **Checkpoint 4: Mock COM Loopback & Adversarial Test Suite (tests/test_emergency_transfer_v160.py)**
