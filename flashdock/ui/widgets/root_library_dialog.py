"""
FlashDock — Root Apps Library & Downloads Dialogs.

Provides:
* RootAppsLibraryDialog: Management dialog for locally stored root manager APKs
  in data/root_apps/ (view, add, delete, select for active rooting, install to phone).
* RootDownloadsDialog: Quick links and references for downloading official releases
  of Magisk, Magisk Alpha, Kitsune Mask, KernelSU, KernelSU Next, APatch, SukiSU.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import ROOT_APPS_DIR
from flashdock.core.rooting import ROOT_DOWNLOAD_URLS, RootingEngine
from flashdock.logger import get_logger

log = get_logger(__name__)


class RootAppsLibraryDialog(QDialog):
    """Dialog for inspecting, adding, deleting, and picking stored root manager APKs."""

    apk_selected = Signal(Path)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📦 Root Manager Applications Library")
        self.setMinimumSize(680, 440)
        self._setup_ui()
        self._load_stored_apks()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header
        header = QLabel("📦  Stored Root Applications (data/root_apps/)")
        header.setProperty("cssClass", "heading")
        layout.addWidget(header)

        desc = QLabel(
            "Manage your collection of root manager APKs (Magisk, Magisk Alpha, Kitsune Mask, "
            "KernelSU, APatch, SukiSU, or custom builds). Select any APK to use as your active root manager."
        )
        desc.setWordWrap(True)
        desc.setProperty("cssClass", "secondary")
        layout.addWidget(desc)

        # Table of APKs
        self._table = QTableWidget()
        self._table.setColumnCount(4)
        self._table.setHorizontalHeaderLabels(["App / File Name", "Size", "Date Modified", "Action"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._table.verticalHeader().setVisible(False)
        layout.addWidget(self._table, 1)

        # Bottom buttons
        btn_row = QHBoxLayout()

        btn_add = QPushButton("➕ Add Root APK to Library...")
        btn_add.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_add.setProperty("cssClass", "primary")
        btn_add.clicked.connect(self._on_add_apk)
        btn_row.addWidget(btn_add)

        btn_open_folder = QPushButton("📁 Open Storage Folder")
        btn_open_folder.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_open_folder.setProperty("cssClass", "secondary")
        btn_open_folder.clicked.connect(self._on_open_folder)
        btn_row.addWidget(btn_open_folder)

        btn_row.addStretch()

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setProperty("cssClass", "secondary")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)

        layout.addLayout(btn_row)

    def _load_stored_apks(self) -> None:
        ROOT_APPS_DIR.mkdir(parents=True, exist_ok=True)
        apks = list(sorted(ROOT_APPS_DIR.glob("*.apk")))
        self._table.setRowCount(len(apks))

        for row, apk in enumerate(apks):
            # Name
            item_name = QTableWidgetItem(f"📱  {apk.stem}")
            item_name.setToolTip(str(apk))
            self._table.setItem(row, 0, item_name)

            # Size
            size_mb = round(apk.stat().st_size / (1024 * 1024), 2)
            item_size = QTableWidgetItem(f"{size_mb} MB")
            item_size.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 1, item_size)

            # Modified date
            mtime = datetime.fromtimestamp(apk.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            item_date = QTableWidgetItem(mtime)
            item_date.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self._table.setItem(row, 2, item_date)

            # Action cell
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(4, 2, 4, 2)
            actions_layout.setSpacing(6)

            btn_select = QPushButton("Use Solution")
            btn_select.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_select.setProperty("cssClass", "primary")
            btn_select.clicked.connect(lambda _, p=apk: self._select_apk(p))
            actions_layout.addWidget(btn_select)

            btn_del = QPushButton("🗑️")
            btn_del.setToolTip("Delete APK from library")
            btn_del.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_del.setProperty("cssClass", "danger")
            btn_del.clicked.connect(lambda _, p=apk: self._delete_apk(p))
            actions_layout.addWidget(btn_del)

            self._table.setCellWidget(row, 3, actions_widget)

    def _select_apk(self, path: Path) -> None:
        self.apk_selected.emit(path)
        self.accept()

    def _delete_apk(self, path: Path) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Root APK",
            f"Are you sure you want to delete '{path.name}' from your root apps library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            RootingEngine.delete_custom_root_apk(path.name)
            self._load_stored_apks()

    def _on_add_apk(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Root Manager APK",
            "",
            "Android Package (*.apk);;All Files (*.*)",
        )
        if path:
            RootingEngine.create_custom_solution(path)
            self._load_stored_apks()

    def _on_open_folder(self) -> None:
        ROOT_APPS_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(ROOT_APPS_DIR))
        except Exception as e:
            log.warning("Could not open folder: %s", e)


class RootDownloadsDialog(QDialog):
    """Dialog showing direct links to official releases of all popular root solutions."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("🌐 Official Root Solution Download Links")
        self.setMinimumSize(640, 500)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header = QLabel("🌐  Official Root Solutions & Releases")
        header.setProperty("cssClass", "heading")
        layout.addWidget(header)

        desc = QLabel(
            "Download official APKs directly from their verified source repositories. "
            "After downloading, you can add them to FlashDock via 'Add Custom Root APK'."
        )
        desc.setWordWrap(True)
        desc.setProperty("cssClass", "secondary")
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(10)

        solutions_meta = [
            (
                "🌱 Magisk Official (Stable)",
                "Universal systemless root solution with Zygisk, DenyList, and module support by topjohnwu.",
                ROOT_DOWNLOAD_URLS["magisk"],
            ),
            (
                "⚡ Magisk Alpha",
                "Bleeding-edge Magisk branch by vvb2060 with enhanced isolation and pre-release Zygisk fixes.",
                ROOT_DOWNLOAD_URLS["magisk_alpha"],
            ),
            (
                "🦊 Kitsune Mask (Magisk Delta)",
                "Renowned Magisk fork by HuskyDG featuring native MagiskHide & SuList for maximum banking bypass.",
                ROOT_DOWNLOAD_URLS["kitsune"],
            ),
            (
                "🐤 Magisk Canary Channel",
                "Official upstream Canary channel of Magisk directly tracking master branch commits.",
                ROOT_DOWNLOAD_URLS["magisk_canary"],
            ),
            (
                "🐧 KernelSU Official",
                "Kernel-space root solution for GKI Linux 5.10+ devices by weishu with userspace invisibility.",
                ROOT_DOWNLOAD_URLS["kernelsu"],
            ),
            (
                "🚀 KernelSU Next",
                "Enhanced community fork of KernelSU with non-GKI backport and advanced module isolation.",
                ROOT_DOWNLOAD_URLS["kernelsu_next"],
            ),
            (
                "🛡️ APatch (KernelPatch)",
                "KernelPatch-based root by bmax121 without requiring GKI compilation, protected by SuperKey.",
                ROOT_DOWNLOAD_URLS["apatch"],
            ),
            (
                "🥷 SukiSU Ultra",
                "KernelSU stealth fork featuring customizable supath and deep anti-detection mechanisms.",
                ROOT_DOWNLOAD_URLS["sukisu"],
            ),
        ]

        for title, detail, url in solutions_meta:
            card = QFrame()
            card.setProperty("cssClass", "card")
            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)

            info_layout = QVBoxLayout()
            info_layout.setSpacing(4)
            lbl_title = QLabel(title)
            lbl_title.setProperty("cssClass", "subheading")
            info_layout.addWidget(lbl_title)

            lbl_detail = QLabel(detail)
            lbl_detail.setWordWrap(True)
            lbl_detail.setProperty("cssClass", "secondary")
            info_layout.addWidget(lbl_detail)
            card_layout.addLayout(info_layout, 1)

            btn_open = QPushButton("Open Release ↗")
            btn_open.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_open.setProperty("cssClass", "secondary")
            btn_open.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))
            card_layout.addWidget(btn_open)

            container_layout.addWidget(card)

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Close button
        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.CursorShape.PointingHandCursor)
        btn_close.setProperty("cssClass", "secondary")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)
