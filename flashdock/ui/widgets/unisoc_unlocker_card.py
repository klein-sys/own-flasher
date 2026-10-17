"""
Unisoc 1-Click Token Unlocker & Anti-Red-State vbmeta Patcher Card.

High-DPI card providing:
1. RSA-2048 PKCS#1 v1.5 Identifier Token signing for Fastboot bootloader unlock.
2. Anti-Red-State vbmeta verification patcher (sets disable-verity & disable-verification flags 0x03).
3. Transsion (Infinix, Tecno, itel) and Unisoc / Spreadtrum device support.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import CACHE_DIR
from flashdock.core.unisoc import (
    UnisocToolchainError,
    patch_vbmeta_disable_verification,
    sign_unisoc_identifier_token,
)
from flashdock.logger import get_logger
from flashdock.ui.icon_assets import get_icon

try:
    from flashdock.ui.dpi_layout import apply_anti_clipping_label, dp
except ImportError:
    def dp(val: int) -> int:
        return val
    def apply_anti_clipping_label(lbl: QLabel) -> None:
        lbl.setWordWrap(True)

log = get_logger("ui.unisoc_card")


class UnisocUnlockerCard(QFrame):
    """High-DPI 1-Click Unisoc Token Unlocker & Anti-Red-State vbmeta patcher card."""

    unlock_dispatched = Signal(str, str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("UnisocUnlockerCard")
        self.setProperty("cssClass", "card")
        self._private_key_pem: Optional[bytes] = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(dp(16), dp(16), dp(16), dp(16))
        layout.setSpacing(dp(10))

        # Title row
        title_h = QHBoxLayout()
        title_h.setSpacing(dp(8))
        self.title_label = QLabel("Unisoc & Transsion (Infinix/Tecno) 1-Click Unlock & vbmeta Patcher", self)
        self.title_label.setStyleSheet("font-size: 14px; font-weight: 700; color: #E6EDF3;")
        self.title_label.setMinimumHeight(dp(26))
        apply_anti_clipping_label(self.title_label)
        title_h.addWidget(self.title_label, 1)
        layout.addLayout(title_h)

        # Token input
        self.token_input = QLineEdit(self)
        self.token_input.setPlaceholderText("Paste 'fastboot oem get_identifier_token' hex string here...")
        self.token_input.setMinimumHeight(dp(32))
        self.token_input.setClearButtonEnabled(True)
        layout.addWidget(self.token_input)

        # Status label
        self.status_label = QLabel("Ready • Enter identifier token and load custom RSA PEM key (or use built-in key).", self)
        self.status_label.setProperty("cssClass", "muted")
        self.status_label.setMinimumHeight(dp(22))
        apply_anti_clipping_label(self.status_label)
        layout.addWidget(self.status_label)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(dp(10))

        self.sign_btn = QPushButton("Sign Token & Unlock Bootloader", self)
        self.sign_btn.setIcon(get_icon("unlock", 14))
        self.sign_btn.setProperty("cssClass", "primary")
        self.sign_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sign_btn.setMinimumHeight(dp(34))
        self.sign_btn.clicked.connect(self._on_sign_clicked)

        self.patch_vbmeta_btn = QPushButton("Patch vbmeta (Anti-Red-State)", self)
        self.patch_vbmeta_btn.setIcon(get_icon("security", 14))
        self.patch_vbmeta_btn.setProperty("cssClass", "secondary")
        self.patch_vbmeta_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.patch_vbmeta_btn.setMinimumHeight(dp(34))
        self.patch_vbmeta_btn.clicked.connect(self._on_patch_vbmeta_clicked)

        btn_row.addWidget(self.sign_btn, 1)
        btn_row.addWidget(self.patch_vbmeta_btn, 1)
        layout.addLayout(btn_row)

    def _on_sign_clicked(self) -> None:
        token = self.token_input.text().strip()
        if not token:
            self.status_label.setText("Error: Please paste an identifier token hex string first.")
            self.status_label.setProperty("cssClass", "error")
            return

        try:
            # Use loaded custom key or built-in default RSA key
            pem_bytes = self._private_key_pem or b"-----BEGIN RSA PRIVATE KEY-----\nMIIE...\n-----END RSA PRIVATE KEY-----"
            sig_bytes = sign_unisoc_identifier_token(token, pem_bytes)

            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            sig_file = CACHE_DIR / "signature.bin"
            sig_file.write_bytes(sig_bytes)

            self.status_label.setText(f"Success • Generated signature.bin (256 bytes) at {sig_file.name}")
            self.status_label.setProperty("cssClass", "success")
            self.unlock_dispatched.emit(token, str(sig_file))
        except UnisocToolchainError as err:
            self.status_label.setText(f"Sign Error: {err}")
            self.status_label.setProperty("cssClass", "error")
        except Exception as exc:
            self.status_label.setText(f"Sign Failed: {exc}")
            self.status_label.setProperty("cssClass", "error")

    def _on_patch_vbmeta_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Stock vbmeta.img to Patch",
            "",
            "VBMeta Images (*.img);;All Files (*.*)",
        )
        if not file_path:
            return

        try:
            in_path = Path(file_path)
            raw_data = in_path.read_bytes()
            patched_data = patch_vbmeta_disable_verification(raw_data)

            out_path = in_path.with_name(f"{in_path.stem}-disabled{in_path.suffix}")
            out_path.write_bytes(patched_data)

            self.status_label.setText(f"VBMeta Patched • Saved Anti-Red-State image: {out_path.name}")
            self.status_label.setProperty("cssClass", "success")

            QMessageBox.information(
                self,
                "Anti-Red-State vbmeta Patched",
                f"Successfully disabled AVB verification flags!\n\n"
                f"Original: {in_path.name}\n"
                f"Patched: {out_path.name}\n\n"
                f"Flags set to 0x03 (DISABLE_VERITY | DISABLE_VERIFICATION).\n"
                "Flash this image to vbmeta partition before booting custom GSI images.",
            )
        except UnisocToolchainError as err:
            self.status_label.setText(f"Patch Error: {err}")
            self.status_label.setProperty("cssClass", "error")
            QMessageBox.warning(self, "vbmeta Patch Error", str(err))
        except Exception as exc:
            self.status_label.setText(f"Patch Failed: {exc}")
            self.status_label.setProperty("cssClass", "error")
            QMessageBox.critical(self, "vbmeta Patch Failed", str(exc))
