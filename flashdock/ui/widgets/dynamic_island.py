"""
flashdock/ui/widgets/dynamic_island.py
iOS 26 / visionOS Smoked-Obsidian Dynamic Island & Segmented Lens Control.

Provides:
1. DynamicIslandPill: Centered smoked-obsidian capsule widget displaying real-time
   connection telemetry (● ADB • MediaTek ADB (serial) | Batt 84% • SoC MT6789 • Slot _A ⇄).
2. WriteSafetySwitch: Capsule safety toggle with Safe and Armed states.
3. LiquidGlassSegmentedControl: Lens filter pill for workstation workflow sheets.
4. ObsidianDynamicIslandBar: Top frosted navigation bar uniting all three controls.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from flashdock.core.device import DeviceInfo
from flashdock.ui.icon_assets import get_icon
from flashdock.ui.widgets.liquid_glass_widget import ElidedLabel


class DynamicIslandPill(QFrame):
    """
    Centered 3D Smoked-Obsidian Dynamic Island Pill with top specular reflection arc.
    Displays: ● ADB • MediaTek ADB (serial) | Batt 84% • SoC MT6789 • Slot _A ⇄
    """

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(36)
        self.setMinimumWidth(230)
        self.setMaximumWidth(640)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._hovered = False

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 90))
        self.setGraphicsEffect(shadow)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(8)

        # 1. Hardware Status Indicator Dot (●)
        self.dot_lbl = QLabel("●")
        self.dot_lbl.setStyleSheet("color: #8E8E93; font-size: 13px; background: transparent;")
        layout.addWidget(self.dot_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Primary Mode & Identity Label
        self.primary_lbl = ElidedLabel("No Device Connected")
        self.primary_lbl.setStyleSheet(
            "color: #FFFFFF; font-size: 12px; font-weight: 600; background: transparent;"
        )
        self.primary_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.primary_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

        # 3. Divider
        self.divider_lbl = QLabel("•")
        self.divider_lbl.setStyleSheet(
            "color: rgba(255, 255, 255, 0.35); font-size: 12px; font-weight: 300; background: transparent;"
        )
        layout.addWidget(self.divider_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        # 4. Telemetry (Battery, SoC, Slot)
        self.telemetry_lbl = ElidedLabel("Workstation Ready")
        self.telemetry_lbl.setStyleSheet(
            "color: #A1A1A6; font-size: 11.5px; font-weight: 500; background: transparent;"
        )
        self.telemetry_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.telemetry_lbl, 1, Qt.AlignmentFlag.AlignVCenter)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.clicked.emit()
        else:
            super().keyPressEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def update_device(self, info: Optional[DeviceInfo]) -> None:
        """Update Dynamic Island telemetry string and status glow."""
        if not info or info.mode == "not_connected":
            self.dot_lbl.setText("○")
            self.dot_lbl.setStyleSheet("color: #8E8E93; font-size: 13px; background: transparent;")
            self.primary_lbl.setText("No Device Connected")
            self.setToolTip("Open device details")
            self.telemetry_lbl.setText("Workstation Ready")
            self.update()
            return

        mode_upper = {
            "system": "ADB",
            "bootloader": "FASTBOOT",
            "mtk_brom": "MTK BROM",
            "qualcomm_edl": "QUALCOMM EDL",
            "unisoc_sprd": "UNISOC FDL",
        }.get(info.mode, info.mode.replace("_", " ").upper())
        self.dot_lbl.setText("●")
        self.dot_lbl.setStyleSheet("color: #ffffff; font-size: 13px; background: transparent;")

        # Primary label: MODE • Brand Model (serial)
        brand = info.brand or "Device"
        model = info.model or info.device or ""
        dev_desc = f"{brand} {model}".strip() if model else brand
        serial_str = f"({info.serial})" if info.serial else ""
        self.primary_lbl.setText(f"{mode_upper} • {dev_desc} {serial_str}".strip())

        # Telemetry: Batt XX% • SoC YYY • Slot _A ⇄
        telemetry_parts = []
        if info.battery_level >= 0:
            telemetry_parts.append(f"Batt {info.battery_level}%")

        soc = info.chipset if info.chipset and info.chipset != "unknown" else ""
        if not soc and info.hardware:
            soc = info.hardware
        if soc:
            telemetry_parts.append(f"SoC {soc.upper()}")

        if info.active_slot.lstrip("_").lower() in ("a", "b"):
            slot_name = f"Slot _{info.active_slot.lstrip('_').upper()} ⇄"
            telemetry_parts.append(slot_name)
        elif info.slot_scheme and info.slot_scheme != "unknown":
            telemetry_parts.append(f"Slot {info.slot_scheme}")

        if info.is_rooted:
            root_txt = f"ROOT: {info.root_method.upper()}" if info.root_method else "ROOT"
            telemetry_parts.append(root_txt)

        self.telemetry_lbl.setText(" • ".join(telemetry_parts) if telemetry_parts else "Connected")
        self.setToolTip(f"{self.primary_lbl.text()} | {self.telemetry_lbl.text()}")
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.0, 1.0, float(self.width() - 2), float(self.height() - 2))

        path = QPainterPath()
        path.addRoundedRect(rect, 17.0, 17.0)

        # 1. Smoked Obsidian body gradient
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(36, 36, 42, 235))
        grad.setColorAt(1.0, QColor(10, 10, 14, 250))
        p.fillPath(path, QBrush(grad))

        # 2. Top-arc specular reflection
        shine_rect = QRectF(rect.left() + 4.0, rect.top() + 1.5, rect.width() - 8.0, 14.0)
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, 7.0, 7.0)
        shine_grad = QLinearGradient(shine_rect.topLeft(), shine_rect.bottomLeft())
        shine_grad.setColorAt(0.0, QColor(255, 255, 255, 80))
        shine_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(shine_path, QBrush(shine_grad))

        # 3. Specular rim border (1.0px)
        rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
        rim.setColorAt(0.0, QColor(255, 255, 255, 120 if not self._hovered else 180))
        rim.setColorAt(0.5, QColor(255, 255, 255, 30))
        rim.setColorAt(1.0, QColor(255, 255, 255, 50))
        p.setPen(QPen(QBrush(rim), 1.0))
        p.drawPath(path)


class WriteSafetySwitch(QFrame):
    """
    Capsule safety toggle switch:
    - Safe state locks write-capable screen controls.
    - Armed state enables the existing workflow controls.
    """

    toggled = Signal(bool)

    def __init__(self, is_armed: bool = False, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.is_armed = is_armed
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 12, 0)
        layout.setSpacing(6)

        self.icon_lbl = QLabel()
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.icon_lbl)

        self.text_lbl = QLabel()
        self.text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(self.text_lbl)

        self._update_appearance()

    def set_armed(self, armed: bool) -> None:
        if self.is_armed != armed:
            self.is_armed = armed
            self._update_appearance()
            self.toggled.emit(self.is_armed)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_armed(not self.is_armed)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.set_armed(not self.is_armed)
        else:
            super().keyPressEvent(event)

    def _update_appearance(self) -> None:
        self.setAccessibleName("Write: Armed" if self.is_armed else "Write: Safe")
        icon = get_icon("unlock" if self.is_armed else "lock", 13, color="#FFFFFF")
        self.icon_lbl.setPixmap(icon.pixmap(13, 13))
        if self.is_armed:
            self.text_lbl.setText("Write: Armed")
            self.text_lbl.setStyleSheet(
                "color: #FFFFFF; font-size: 11px; font-weight: 700; background: transparent;"
            )
            self.setToolTip("Write tools are unlocked. Their individual safety checks still apply.")
        else:
            self.text_lbl.setText("Write: Safe")
            self.text_lbl.setStyleSheet(
                "color: #A1A1A6; font-size: 11px; font-weight: 600; background: transparent;"
            )
            self.setToolTip("Write tools are locked. Select this switch to enable their controls.")
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.0, 1.0, float(self.width() - 2), float(self.height() - 2))

        path = QPainterPath()
        path.addRoundedRect(rect, 15.0, 15.0)

        # Gradient background
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if self.is_armed:
            grad.setColorAt(0.0, QColor(70, 70, 70, 245))
            grad.setColorAt(1.0, QColor(35, 35, 35, 250))
            rim_color = QColor(255, 255, 255, 180)
        else:
            grad.setColorAt(0.0, QColor(36, 36, 42, 180))
            grad.setColorAt(1.0, QColor(18, 18, 22, 220))
            rim_color = QColor(255, 255, 255, 60)

        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(rim_color, 1.0))
        p.drawPath(path)


class LiquidGlassSegmentedControl(QFrame):
    """
    visionOS Inset Liquid Glass Segmented Lens Control.
    Enables switching between the four workflows and the complete tool list.
    """

    segment_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(34)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(3)

        self._buttons: dict[str, QPushButton] = {}
        self._active_key = "All"
        self.setObjectName("liquidSegmented")

        segments = [
            ("All", "All"),
            ("Inspect", "Inspect"),
            ("Daily", "ADB"),
            ("Root", "Root"),
            ("Flash", "Flash"),
        ]

        for key, label in segments:
            btn = QPushButton(label)
            btn.setProperty("liquidSegment", True)
            btn.setCheckable(True)
            btn.setChecked(key == "All")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFixedHeight(28)
            btn.clicked.connect(lambda checked, k=key: self._on_btn_clicked(k))
            self._layout.addWidget(btn)
            self._buttons[key] = btn


    def set_active_segment(self, key: str) -> None:
        if key in self._buttons:
            self._active_key = key
            for k, btn in self._buttons.items():
                btn.setChecked(k == key)

    def _on_btn_clicked(self, key: str) -> None:
        self.set_active_segment(key)
        self.segment_selected.emit(key)


class ObsidianDynamicIslandBar(QFrame):
    """
    Top frosted glass navigation header.
    Unites:
    - Left: Liquid Glass Segmented Lens Control
    - Center: Centered Dynamic Island Pill (Hardware status & telemetry)
    - Right: Write: Safe / Armed capsule switch
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.dark_mode = True
        self.setObjectName("topNavigationBar")

        layout = QGridLayout(self)
        self._grid = layout
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setHorizontalSpacing(12)
        self.lens_control = LiquidGlassSegmentedControl(self)
        self.island_pill = DynamicIslandPill(self)
        self.write_switch = WriteSafetySwitch(is_armed=False, parent=self)
        side_width = self.lens_control.sizeHint().width()
        layout.setColumnMinimumWidth(0, side_width)
        layout.setColumnMinimumWidth(2, side_width)
        layout.setColumnStretch(1, 1)
        layout.addWidget(self.lens_control, 0, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.island_pill, 0, 1)
        layout.addWidget(self.write_switch, 0, 2, Qt.AlignmentFlag.AlignRight)

    def set_dark_mode(self, dark: bool) -> None:
        self.dark_mode = dark
        self.lens_control.ensurePolished()
        for button in self.lens_control._buttons.values():
            button.ensurePolished()
        side_width = self.lens_control.sizeHint().width()
        self._grid.setColumnMinimumWidth(0, side_width)
        self._grid.setColumnMinimumWidth(2, side_width)
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(0.0, 0.0, float(self.width()), float(self.height()))

        # Translucent frosted glass bar
        p.fillRect(rect, QBrush(QColor(18, 18, 18, 160) if self.dark_mode else QColor(255, 255, 255, 165)))

        # 1px bottom specular divider
        p.setPen(QPen(QColor(255, 255, 255, 24), 1.0))
        p.drawLine(0, int(self.height() - 1), int(self.width()), int(self.height() - 1))
