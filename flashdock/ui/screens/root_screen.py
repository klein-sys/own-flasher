"""
FlashDock — Rooting Wizard Screen.

Step-by-step guided GUI for:
* Analyzing device kernel and GKI architecture for Magisk, KernelSU, APatch.
* Selecting stock boot.img or init_boot.img with match checks.
* Generating patched root images and automated pre-root backups.
* Safe flashing via fastboot protected by FlashShield.
* Manager app installation and live root verification.
* One-click unrooting and educational guides.

Spec references: Section 11, Section 8, Section 16.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from flashdock.constants import ROOT_APPS_DIR, TOOLS_DIR
from flashdock.core.device import DeviceInfo
from flashdock.core.device_manager import DeviceManager
from flashdock.core.rooting import RootCompatibilityReport, RootSolutionInfo, RootingEngine
from flashdock.core.safety import SafetyEngine
from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.ui.widgets.flash_shield import FlashShieldDialog
from flashdock.ui.widgets.root_library_dialog import RootAppsLibraryDialog, RootDownloadsDialog

log = get_logger(__name__)


class RootScreen(QWidget):
    """The Rooting Wizard screen."""

    def __init__(
        self,
        device_mgr: DeviceManager,
        adb: ADB,
        fastboot: Fastboot,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._device_mgr = device_mgr
        self._adb = adb
        self._fb = fastboot
        self._root_engine = RootingEngine()
        self._current_device: Optional[DeviceInfo] = None
        self._compat_report: Optional[RootCompatibilityReport] = None
        self._patched_image_path: Optional[Path] = None
        self._custom_solutions: dict[str, RootSolutionInfo] = {}
        self._custom_radios: dict[str, QRadioButton] = {}

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Header
        title = QLabel("🌱  Root My Phone (Magisk · KernelSU · APatch)")
        title.setProperty("cssClass", "heading")
        layout.addWidget(title)

        self._subtitle = QLabel("Connect a device to view root compatibility and guided patching.")
        self._subtitle.setProperty("cssClass", "muted")
        layout.addWidget(self._subtitle)

        # Tabs
        self._tabs = QTabWidget()

        self._tab_wizard = QWidget()
        self._tab_unroot = QWidget()
        self._tab_guide = QWidget()

        self._setup_wizard_tab()
        self._setup_unroot_tab()
        self._setup_guide_tab()

        self._tabs.addTab(self._tab_wizard, "Root Wizard")
        self._tabs.addTab(self._tab_unroot, "Unroot / Remove Root")
        self._tabs.addTab(self._tab_guide, "Zygisk & Safety Guide")

        layout.addWidget(self._tabs, 1)

    # -----------------------------------------------------------------------
    # Tab 1: Root Wizard
    # -----------------------------------------------------------------------

    def _setup_wizard_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        # Warnings Banner
        self._warn_banner = QLabel("")
        self._warn_banner.setWordWrap(True)
        self._warn_banner.setProperty("cssClass", "danger_banner")
        self._warn_banner.hide()
        layout.addWidget(self._warn_banner)

        # Step 1: Solution Selector Frame
        sol_frame = QFrame()
        sol_frame.setProperty("cssClass", "card")
        sol_layout = QVBoxLayout(sol_frame)
        sol_layout.setSpacing(8)

        sol_title = QLabel("1. Select Root Solution")
        sol_title.setProperty("cssClass", "subheading")
        sol_layout.addWidget(sol_title)

        self._btn_group = QButtonGroup(self)
        self._rb_magisk = QRadioButton("🌱 Magisk Official (Standard stable systemless root with Zygisk)")
        self._rb_magisk_alpha = QRadioButton("⚡ Magisk Alpha (Bleeding-edge build by vvb2060 with latest isolation patches)")
        self._rb_kitsune = QRadioButton("🦊 Kitsune Mask / Magisk Delta (Built-in MagiskHide & SuList for banking apps)")
        self._rb_canary = QRadioButton("🐤 Magisk Canary (Official upstream master Canary channel)")
        self._rb_ksu = QRadioButton("🐧 KernelSU Official (Kernel-space root for GKI Linux 5.10+)")
        self._rb_ksu_next = QRadioButton("🚀 KernelSU Next (Enhanced community KernelSU fork)")
        self._rb_sukisu = QRadioButton("🥷 SukiSU Ultra (Stealth KernelSU with custom supath)")
        self._rb_apatch = QRadioButton("🛡️ APatch (KernelPatch-based root with superkey)")

        self._built_in_radios = [
            (self._rb_magisk, "magisk"),
            (self._rb_magisk_alpha, "magisk_alpha"),
            (self._rb_kitsune, "kitsune"),
            (self._rb_canary, "magisk_canary"),
            (self._rb_ksu, "kernelsu"),
            (self._rb_ksu_next, "kernelsu_next"),
            (self._rb_sukisu, "sukisu"),
            (self._rb_apatch, "apatch"),
        ]

        for rb, _ in self._built_in_radios:
            self._btn_group.addButton(rb)
            sol_layout.addWidget(rb)

        # Stored / Custom Root Apps Header & Container
        self._custom_sol_header = QLabel("Custom & Stored Root Apps:")
        self._custom_sol_header.setProperty("cssClass", "subheading")
        sol_layout.addWidget(self._custom_sol_header)

        self._custom_sol_container = QVBoxLayout()
        self._custom_sol_container.setSpacing(4)
        sol_layout.addLayout(self._custom_sol_container)

        # Custom Root APK & Library Actions
        custom_row = QHBoxLayout()
        self._btn_add_custom_apk = QPushButton("➕ Add Custom Root APK...")
        self._btn_add_custom_apk.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_add_custom_apk.setProperty("cssClass", "secondary")
        self._btn_add_custom_apk.clicked.connect(self._on_add_custom_root_apk)
        custom_row.addWidget(self._btn_add_custom_apk)

        self._btn_manage_repo = QPushButton("📦 Manage Root Apps Library...")
        self._btn_manage_repo.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_manage_repo.setProperty("cssClass", "secondary")
        self._btn_manage_repo.clicked.connect(self._on_manage_root_apps_library)
        custom_row.addWidget(self._btn_manage_repo)

        self._btn_downloads = QPushButton("🌐 Official Download Releases...")
        self._btn_downloads.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn_downloads.setProperty("cssClass", "secondary")
        self._btn_downloads.clicked.connect(self._on_open_downloads_dialog)
        custom_row.addWidget(self._btn_downloads)

        custom_row.addStretch()
        sol_layout.addLayout(custom_row)

        self._rb_magisk.setChecked(True)
        self._btn_group.buttonToggled.connect(self._on_solution_changed)

        self._sol_desc = QLabel("Loading solution details...")
        self._sol_desc.setWordWrap(True)
        self._sol_desc.setProperty("cssClass", "muted")
        sol_layout.addWidget(self._sol_desc)

        layout.addWidget(sol_frame)

        # Step 2: Stock Boot Image Frame
        img_frame = QFrame()
        img_frame.setProperty("cssClass", "card")
        img_layout = QVBoxLayout(img_frame)
        img_layout.setSpacing(10)

        self._part_target_label = QLabel("2. Select Stock Image (Target Partition: boot)")
        self._part_target_label.setProperty("cssClass", "subheading")
        img_layout.addWidget(self._part_target_label)

        picker_row = QHBoxLayout()
        self._edit_stock_path = QLineEdit()
        self._edit_stock_path.setPlaceholderText("Select stock boot.img or init_boot.img from your firmware...")
        picker_row.addWidget(self._edit_stock_path, 1)

        browse_btn = QPushButton("📁 Browse...")
        browse_btn.setProperty("cssClass", "secondary")
        browse_btn.clicked.connect(self._on_browse_stock_image)
        picker_row.addWidget(browse_btn)

        img_layout.addLayout(picker_row)
        layout.addWidget(img_frame)

        # Step 3: Action Buttons Frame
        action_frame = QFrame()
        action_frame.setProperty("cssClass", "card")
        action_layout = QVBoxLayout(action_frame)
        action_layout.setSpacing(10)

        act_title = QLabel("3. Patch, Flash, Install & Verify")
        act_title.setProperty("cssClass", "subheading")
        action_layout.addWidget(act_title)

        btns_row = QHBoxLayout()

        self._btn_patch = QPushButton("⚡ 1. Patch Image")
        self._btn_patch.setProperty("cssClass", "primary")
        self._btn_patch.clicked.connect(self._on_patch_image)
        btns_row.addWidget(self._btn_patch)

        self._btn_flash = QPushButton("🔥 2. Flash to Phone")
        self._btn_flash.setProperty("cssClass", "danger")
        self._btn_flash.setEnabled(False)
        self._btn_flash.clicked.connect(self._on_flash_patched_image)
        btns_row.addWidget(self._btn_flash)

        self._btn_install_mgr = QPushButton("📲 3. Install Manager APK")
        self._btn_install_mgr.setProperty("cssClass", "primary")
        self._btn_install_mgr.clicked.connect(self._on_install_manager_app)
        btns_row.addWidget(self._btn_install_mgr)

        self._btn_verify = QPushButton("🔍 4. Verify Root")
        self._btn_verify.setProperty("cssClass", "secondary")
        self._btn_verify.clicked.connect(self._on_verify_root)
        btns_row.addWidget(self._btn_verify)

        action_layout.addLayout(btns_row)

        self._status_box = QLabel("Ready.")
        self._status_box.setProperty("cssClass", "muted")
        action_layout.addWidget(self._status_box)

        layout.addWidget(action_frame)
        layout.addStretch()

        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_wizard)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

        self._refresh_custom_radios()

    # -----------------------------------------------------------------------
    # Tab 2: Unroot Tab
    # -----------------------------------------------------------------------

    def _setup_unroot_tab(self) -> None:
        layout = QVBoxLayout(self._tab_unroot)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        info = QLabel(
            "Complete unroot restores your clean stock boot/init_boot image to return the system kernel "
            "to stock state, followed by removal of root managers and modules."
        )
        info.setWordWrap(True)
        info.setProperty("cssClass", "muted")
        layout.addWidget(info)

        stock_frame = QFrame()
        stock_frame.setProperty("cssClass", "card")
        stock_layout = QVBoxLayout(stock_frame)

        pick_label = QLabel("Stock Boot / init_boot Image:")
        pick_label.setProperty("cssClass", "subheading")
        stock_layout.addWidget(pick_label)

        unroot_row = QHBoxLayout()
        self._edit_unroot_path = QLineEdit()
        self._edit_unroot_path.setPlaceholderText("Select stock boot image to restore...")
        unroot_row.addWidget(self._edit_unroot_path, 1)

        unroot_browse_btn = QPushButton("📁 Browse...")
        unroot_browse_btn.setProperty("cssClass", "secondary")
        unroot_browse_btn.clicked.connect(self._on_browse_unroot_image)
        unroot_row.addWidget(unroot_browse_btn)

        stock_layout.addLayout(unroot_row)
        layout.addWidget(stock_frame)

        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._btn_unroot = QPushButton("🏠  Restore Stock Boot & Unroot")
        self._btn_unroot.setProperty("cssClass", "danger")
        self._btn_unroot.clicked.connect(self._on_execute_unroot)
        btn_row.addWidget(self._btn_unroot)

        layout.addLayout(btn_row)

    # -----------------------------------------------------------------------
    # Tab 3: Guide & Safety
    # -----------------------------------------------------------------------

    def _setup_guide_tab(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        def add_guide_section(title: str, text: str):
            f = QFrame()
            f.setProperty("cssClass", "card")
            fl = QVBoxLayout(f)
            t = QLabel(title)
            t.setProperty("cssClass", "subheading")
            fl.addWidget(t)
            d = QLabel(text)
            d.setWordWrap(True)
            d.setProperty("cssClass", "muted")
            fl.addWidget(d)
            layout.addWidget(f)

        add_guide_section(
            "🛡️ What is Zygisk and DenyList?",
            "Zygisk allows modules to execute code directly inside Android's Zygote application starter process. "
            "DenyList configures Magisk to revert all modifications and hide root from selected apps (like banking or work apps)."
        )

        add_guide_section(
            "🏦 Banking Apps & Play Integrity",
            "Rooting by itself trips Google Play Integrity (Device Integrity). Banking apps check this flag. "
            "To restore functionality, install Play Integrity Fix or Tricky Store in the Modules screen (Phase 8)."
        )

        add_guide_section(
            "🔄 Safe OTA Updates While Rooted",
            "To take an official Android system update without losing data:\n"
            "1. Open Magisk app > Uninstall > Restore Images (do NOT reboot).\n"
            "2. Install the OTA update in Android Settings.\n"
            "3. DO NOT reboot yet! Return to Magisk app > Install > Install to Inactive Slot.\n"
            "4. Reboot now to enjoy the update with root intact."
        )

        scroll.setWidget(content)
        vbox = QVBoxLayout(self._tab_guide)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.addWidget(scroll)

    # -----------------------------------------------------------------------
    # Context Loading
    # -----------------------------------------------------------------------

    def load_for_device(self, device: Optional[DeviceInfo]) -> None:
        """Update wizard when device connection changes."""
        self._current_device = device
        self._refresh_custom_radios()

        if not device or device.mode == "not_connected":
            self._subtitle.setText("No device connected. Connect your phone via USB to begin.")
            self._warn_banner.hide()
            return

        report = self._root_engine.analyze_device(device)
        self._compat_report = report

        root_status_str = f"✅ Rooted ({device.root_method.title()})" if device.is_rooted else "❌ Not Rooted"
        self._subtitle.setText(f"{device.summary_line} · Root Status: {root_status_str}")

        # Target partition update
        target_part = report.target_partition
        self._part_target_label.setText(f"2. Select Stock Image (Target Partition: {target_part})")

        # Warnings banner
        if report.overall_warnings:
            self._warn_banner.setText("\n".join(f"• {w}" for w in report.overall_warnings))
            self._warn_banner.show()
        else:
            self._warn_banner.hide()

        # Update recommended selection
        if report.recommended_solution == "kernelsu":
            self._rb_ksu.setChecked(True)
        else:
            self._rb_magisk.setChecked(True)

        self._on_solution_changed()

    def _refresh_custom_radios(self) -> None:
        """Discover and render radio buttons for all stored custom root apps in data/root_apps/."""
        # Clean up existing custom radios
        for rb in list(self._custom_radios.values()):
            self._btn_group.removeButton(rb)
            self._custom_sol_container.removeWidget(rb)
            rb.deleteLater()
        self._custom_radios.clear()
        self._custom_solutions.clear()

        stored_apps = self._root_engine.discover_stored_root_apps()
        if not stored_apps:
            self._custom_sol_header.hide()
            return

        self._custom_sol_header.show()
        target_part = self._compat_report.target_partition if self._compat_report else "boot"

        for app in stored_apps:
            sol_id = app["solution_id"]
            # Exclude matching built-in solution names to prevent duplicates
            if any(bid == sol_id.replace("custom_", "") for _, bid in self._built_in_radios):
                continue

            sol_info = RootSolutionInfo(
                solution_id=sol_id,
                name=f"Custom: {app['name']}",
                version="Stored APK",
                status="compatible",
                summary=f"Stored in data/root_apps/ ({app['filename']}, {app['size_mb']} MB)",
                description=f"User custom root application: {app['filename']}. Saved in local library at data/root_apps/.",
                target_partition=target_part,
                requirements=["Unlocked bootloader", f"Stock {target_part}.img", "USB debugging enabled"],
                manager_package="",
                apk_path=app["path"],
            )
            self._custom_solutions[sol_id] = sol_info

            rb = QRadioButton(f"✨ {app['name']} ({app['size_mb']} MB)")
            self._btn_group.addButton(rb)
            self._custom_sol_container.addWidget(rb)
            self._custom_radios[sol_id] = rb

    def _selected_solution(self) -> str:
        for rb, sol_id in self._built_in_radios:
            if rb.isChecked():
                return sol_id
        for sol_id, rb in self._custom_radios.items():
            if rb.isChecked():
                return sol_id
        return "magisk"

    def _on_solution_changed(self) -> None:
        sol_id = self._selected_solution()

        # Check if custom solution selected
        if sol_id in self._custom_solutions:
            sol = self._custom_solutions[sol_id]
            status_badge = "[CUSTOM APK]"
            self._sol_desc.setText(
                f"{sol.name} {status_badge}: {sol.summary}\n\n{sol.description}\nTarget: {sol.target_partition}.img"
            )
            return

        if not self._compat_report:
            return

        sol = next((s for s in self._compat_report.solutions if s.solution_id == sol_id), None)
        if sol:
            status_badge = f"[{sol.status.upper()}]"
            self._sol_desc.setText(
                f"{sol.name} {status_badge}: {sol.summary}\n\n{sol.description}\nTarget: {sol.target_partition}.img"
            )

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def _on_add_custom_root_apk(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Custom Root Manager APK",
            "",
            "Android Package (*.apk);;All Files (*.*)",
        )
        if not path:
            return
        target_part = self._compat_report.target_partition if self._compat_report else "boot"
        custom_sol = self._root_engine.create_custom_solution(path, target_partition=target_part)
        self._refresh_custom_radios()

        if custom_sol.solution_id in self._custom_radios:
            self._custom_radios[custom_sol.solution_id].setChecked(True)
            self._on_solution_changed()

        QMessageBox.information(
            self,
            "Custom Root App Added",
            f"Successfully added '{custom_sol.name}'!\nSaved to local repository at data/root_apps/.\n"
            "FlashDock will patch your boot image and install this custom manager upon request.",
        )

    def _on_manage_root_apps_library(self) -> None:
        dlg = RootAppsLibraryDialog(self)
        dlg.apk_selected.connect(self._on_apk_selected_from_library)
        dlg.exec()
        self._refresh_custom_radios()

    def _on_apk_selected_from_library(self, path: Path) -> None:
        target_part = self._compat_report.target_partition if self._compat_report else "boot"
        custom_sol = self._root_engine.create_custom_solution(path, target_partition=target_part)
        self._refresh_custom_radios()
        if custom_sol.solution_id in self._custom_radios:
            self._custom_radios[custom_sol.solution_id].setChecked(True)
            self._on_solution_changed()

    def _on_open_downloads_dialog(self) -> None:
        dlg = RootDownloadsDialog(self)
        dlg.exec()

    def _on_install_manager_app(self) -> None:
        device = self._current_device
        if not device or device.mode != "system":
            QMessageBox.warning(
                self,
                "Device in System Mode Required",
                "Please connect your device in normal Android system mode with USB debugging enabled.",
            )
            return

        sol_id = self._selected_solution()
        apk_path: Optional[Path] = None

        if sol_id in self._custom_solutions and self._custom_solutions[sol_id].apk_path:
            apk_path = self._custom_solutions[sol_id].apk_path
        else:
            apk_path = self._root_engine.find_local_apk_for_solution(sol_id)

        if not apk_path or not apk_path.is_file():
            reply = QMessageBox.question(
                self,
                "Manager APK Not Found Locally",
                f"No local APK found for '{sol_id}' in data/root_apps/.\n\n"
                "Would you like to select an APK from your computer now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if reply == QMessageBox.StandardButton.Yes:
                self._on_add_custom_root_apk()
                sol_id = self._selected_solution()
                if sol_id in self._custom_solutions and self._custom_solutions[sol_id].apk_path:
                    apk_path = self._custom_solutions[sol_id].apk_path
                else:
                    return
            else:
                return

        reply = QMessageBox.question(
            self,
            "Install Root Manager APK",
            f"Install '{apk_path.name}' to {device.summary_line} via ADB?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._status_box.setText(f"Installing {apk_path.name} via ADB...")
        res = self._root_engine.install_manager_app(apk_path=apk_path, adb=self._adb, serial=device.serial)
        if res.success:
            self._status_box.setText(f"✅ {apk_path.name} successfully installed.")
            QMessageBox.information(
                self,
                "Manager Installed",
                f"Successfully installed '{apk_path.name}' on your device!\n\n"
                "Open the app on your phone to configure modules and grant superuser access.",
            )
        else:
            self._status_box.setText(f"❌ Failed to install {apk_path.name}: {res.stderr}")
            QMessageBox.critical(
                self,
                "Installation Failed",
                f"Could not install '{apk_path.name}':\n\n{res.stderr or res.stdout}",
            )

    def _on_browse_stock_image(self) -> None:
        target_part = self._compat_report.target_partition if self._compat_report else "boot"
        path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select Stock {target_part}.img",
            "",
            "Boot Image (*.img *.bin);;All Files (*.*)",
        )
        if path:
            self._edit_stock_path.setText(path)

    def _on_browse_unroot_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Stock Boot Image for Unroot",
            "",
            "Boot Image (*.img *.bin);;All Files (*.*)",
        )
        if path:
            self._edit_unroot_path.setText(path)

    def _on_patch_image(self) -> None:
        stock_file = self._edit_stock_path.text().strip()
        if not stock_file or not Path(stock_file).is_file():
            QMessageBox.warning(self, "Missing Image", "Please select a valid stock boot image file first.")
            return

        device = self._current_device
        if not device:
            QMessageBox.warning(self, "No Device", "Please connect a device first.")
            return

        sol_id = self._selected_solution()
        out_dir = Path("data/tools/patched_boot")

        self._status_box.setText("Generating patched boot image and backing up stock image...")
        ok, patched_path, msg = self._root_engine.prepare_patch(
            stock_image_path=stock_file,
            solution_id=sol_id,
            device=device,
            output_dir=out_dir,
            dry_run=False,
        )

        if ok:
            self._patched_image_path = Path(patched_path)
            self._status_box.setText(f"✅ {msg}")
            self._btn_flash.setEnabled(True)
            QMessageBox.information(
                self,
                "Patch Complete",
                f"{msg}\n\nStock image was safely backed up.\nClick '2. Flash to Phone' to proceed.",
            )
        else:
            self._status_box.setText(f"❌ {msg}")
            QMessageBox.critical(self, "Patch Failed", msg)

    def _on_flash_patched_image(self) -> None:
        if not self._patched_image_path or not self._patched_image_path.is_file():
            QMessageBox.warning(self, "No Image", "Please generate the patched image in step 1 first.")
            return

        device = self._current_device
        if not device:
            QMessageBox.warning(self, "No Device", "Please connect a device first.")
            return

        target_part = self._compat_report.target_partition if self._compat_report else "boot"

        # Check battery level
        bat_res = SafetyEngine.check_battery(device.battery_level)
        if bat_res.is_blocked:
            QMessageBox.warning(self, "Low Battery", bat_res.message)
            return

        # Confirmation
        reply = QMessageBox.question(
            self,
            "Flash Rooted Boot Image?",
            f"Flash '{self._patched_image_path.name}' to the '{target_part}' partition?\n\n"
            "The device will receive root privileges.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress(f"Flashing rooted {target_part} image via fastboot...", 50)

        res = self._root_engine.flash_patched_image(
            patched_image_path=self._patched_image_path,
            target_partition=target_part,
            fastboot=self._fb,
            serial=device.serial,
        )

        if res.success:
            shield.mark_completed(True, f"Root image successfully flashed to {target_part}!")
            self._status_box.setText(f"✅ Flashed to {target_part}. Reboot device and click 'Verify Root'.")
        else:
            shield.mark_completed(False, f"Flashing failed: {res.stderr}")
            self._status_box.setText(f"❌ Fastboot error: {res.stderr}")

    def _on_verify_root(self) -> None:
        device = self._current_device
        if not device or device.mode != "system":
            QMessageBox.warning(self, "Device in System Mode Required", "Please boot phone into Android system with USB debugging on.")
            return

        ok, msg = self._root_engine.verify_root(self._adb, serial=device.serial)
        if ok:
            QMessageBox.information(self, "Root Confirmed! 🎉", f"Device is successfully rooted!\n\n{msg}")
            self._status_box.setText(f"✅ {msg}")
        else:
            QMessageBox.warning(
                self,
                "Root Not Active",
                f"{msg}\n\nEnsure you have installed the manager APK and granted superuser permissions.",
            )
            self._status_box.setText(f"⚠️ {msg}")

    def _on_execute_unroot(self) -> None:
        stock_file = self._edit_unroot_path.text().strip()
        if not stock_file or not Path(stock_file).is_file():
            QMessageBox.warning(self, "Missing Image", "Please select the clean stock boot image to restore.")
            return

        device = self._current_device
        if not device:
            QMessageBox.warning(self, "No Device", "Please connect a device first.")
            return

        target_part = self._compat_report.target_partition if self._compat_report else "boot"

        reply = QMessageBox.question(
            self,
            "Confirm Complete Unroot",
            f"Are you sure you want to unroot this device?\n\n"
            f"This will restore '{stock_file}' to partition '{target_part}' and remove root managers.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        shield = FlashShieldDialog(self)
        shield.show()
        shield.update_progress(f"Restoring clean stock {target_part} partition...", 50)

        ok, msg = self._root_engine.unroot_device(
            stock_boot_path=stock_file,
            target_partition=target_part,
            fastboot=self._fb,
            adb=self._adb,
            serial=device.serial,
        )
        shield.mark_completed(ok, msg)
