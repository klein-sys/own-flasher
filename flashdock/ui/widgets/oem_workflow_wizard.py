"""
High-DPI Interactive OEM Workflow Wizard Card for Xiaomi HyperOS 2.0 & Samsung Knox-Safe.
Validates live stage gates before unlocking the next flashing step.
"""
from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flashdock.core.oem_workflows import StageGateResult
from flashdock.ui.oem_svg_assets import OEM_WORKFLOW_SVGS

try:
    from flashdock.ui.dpi_layout import apply_anti_clipping_label, dp
except ImportError:
    def dp(val: int) -> int:
        return val
    def apply_anti_clipping_label(lbl: QLabel) -> None:
        lbl.setWordWrap(True)

class OemWorkflowWizardWidget(QFrame):
    """
    Interactive stage-gate wizard for Xiaomi HyperOS 2.0 and Samsung Knox-Safe procedures.
    """

    stage_unlocked = Signal(str, int)
    workflow_completed = Signal(str)

    XIAOMI_STEPS: List[str] = [
        "Step 1/3: Mi Community Account Binding & HyperOS 2.0 Quota Check (ADB)",
        "Step 2/3: Fastboot Mode & Anti-Rollback (ARB) Fuse Interlock (VOL- + PWR)",
        "Step 3/3: Active A/B Slot Verification & Flash Trigger Ready",
    ]

    SAMSUNG_STEPS: List[str] = [
        "Step 1/3: Odin Download Mode & Knox Guard (KG STATE) Gate (VOL+ & VOL- + USB)",
        "Step 2/3: Streaming .tar.md5 Trailing Checksum Integrity Gate",
        "Step 3/3: HOME_CSC (Keep Data) vs CSC (Factory Reset) Confirmation",
    ]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("OemWorkflowWizardCard")
        self._current_oem = "XIAOMI_HYPEROS"
        self._current_step = 0
        self._last_gate: Optional[StageGateResult] = None
        self._setup_ui()
        self._refresh_step_view()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(dp(16), dp(16), dp(16), dp(16))
        layout.setSpacing(dp(12))

        header_row = QHBoxLayout()
        self.title_label = QLabel("OEM Interactive Stage-Gate Guide")
        self.title_label.setMinimumHeight(dp(26))
        apply_anti_clipping_label(self.title_label)

        self.oem_selector = QComboBox(self)
        self.oem_selector.addItems([
            "Xiaomi HyperOS 2.0 (ARB Safe)",
            "Samsung Knox-Safe (Odin / Tar.MD5)",
        ])
        self.oem_selector.setMinimumHeight(dp(30))
        self.oem_selector.currentIndexChanged.connect(self._on_oem_changed)

        header_row.addWidget(self.title_label, 1)
        header_row.addWidget(self.oem_selector, 0)
        layout.addLayout(header_row)

        self.step_banner = QLabel(self)
        self.step_banner.setMinimumHeight(dp(28))
        apply_anti_clipping_label(self.step_banner)
        layout.addWidget(self.step_banner)

        self.svg_info_label = QLabel(self)
        self.svg_info_label.setMinimumHeight(dp(24))
        apply_anti_clipping_label(self.svg_info_label)
        layout.addWidget(self.svg_info_label)

        self.gate_headline_label = QLabel("Stage Check Pending • Run hardware/package gate check.")
        self.gate_headline_label.setMinimumHeight(dp(24))
        apply_anti_clipping_label(self.gate_headline_label)
        layout.addWidget(self.gate_headline_label)

        self.gate_detail_label = QLabel(
            "Next step remains locked until the current OEM safety gate passes."
        )
        self.gate_detail_label.setMinimumHeight(dp(36))
        apply_anti_clipping_label(self.gate_detail_label)
        layout.addWidget(self.gate_detail_label)

        btn_row = QHBoxLayout()
        self.prev_btn = QPushButton("Previous Step", self)
        self.prev_btn.setMinimumHeight(dp(34))
        self.prev_btn.clicked.connect(self._on_prev_clicked)

        self.next_btn = QPushButton("Next Step (Locked)", self)
        self.next_btn.setMinimumHeight(dp(34))
        self.next_btn.setEnabled(False)
        self.next_btn.clicked.connect(self._on_next_clicked)

        btn_row.addWidget(self.prev_btn, 0)
        btn_row.addStretch(1)
        btn_row.addWidget(self.next_btn, 0)
        layout.addLayout(btn_row)

    @property
    def current_step_index(self) -> int:
        return self._current_step

    @property
    def active_steps(self) -> List[str]:
        return self.XIAOMI_STEPS if self._current_oem == "XIAOMI_HYPEROS" else self.SAMSUNG_STEPS

    def apply_gate_result(self, result: StageGateResult) -> None:
        """Update the wizard with a live StageGateResult and unlock Next if passed."""
        self._last_gate = result
        self.gate_headline_label.setText(f"[{result.severity}] {result.headline}")
        self.gate_detail_label.setText(result.detail)
        self.next_btn.setEnabled(result.passed)
        if result.passed:
            is_last = self._current_step >= len(self.active_steps) - 1
            self.next_btn.setText("Complete Workflow" if is_last else "Proceed to Next Step")
        else:
            self.next_btn.setText("Next Step (Blocked)")

    def _on_oem_changed(self, idx: int) -> None:
        self._current_oem = "XIAOMI_HYPEROS" if idx == 0 else "SAMSUNG_KNOX"
        self._current_step = 0
        self._last_gate = None
        self._refresh_step_view()

    def _on_prev_clicked(self) -> None:
        if self._current_step > 0:
            self._current_step -= 1
            self._last_gate = None
            self._refresh_step_view()

    def _on_next_clicked(self) -> None:
        if not self._last_gate or not self._last_gate.passed:
            return
        if self._current_step < len(self.active_steps) - 1:
            self._current_step += 1
            self._last_gate = None
            self._refresh_step_view()
            self.stage_unlocked.emit(self._current_oem, self._current_step)
        else:
            self.workflow_completed.emit(self._current_oem)

    def _refresh_step_view(self) -> None:
        steps = self.active_steps
        self.step_banner.setText(steps[self._current_step])
        if self._current_oem == "XIAOMI_HYPEROS":
            svg_key = "xiaomi_fastboot_combo"
            combo_desc = "Hardware Key Diagram: Hold Volume Down + Power to enter Fastboot Mode."
        else:
            svg_key = "samsung_download_combo"
            combo_desc = "Hardware Key Diagram: Hold Volume Up + Volume Down while connecting USB-C."
        assert svg_key in OEM_WORKFLOW_SVGS
        self.svg_info_label.setText(combo_desc)
        self.prev_btn.setEnabled(self._current_step > 0)
        self.next_btn.setEnabled(False)
        self.next_btn.setText("Next Step (Locked)")

### **Checkpoint 4: Unit, Stage-Gate, Checksum & High-DPI Test Suite (tests/test_oem_workflows_v160.py)**
