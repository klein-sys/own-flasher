"""
flashdock/ui/widgets/liquid_glass_widget.py
QPainter-based PySide6 Liquid Glass Sheet & Smoked-Obsidian Icon Droplet.
Implements cursor-reactive radial specular refraction + top-left 1.5px glass rim highlight.
"""

from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtCore import QEvent, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def enable_windows_acrylic_blur(hwnd: int, dark: bool = False) -> bool:
    """Windows 11 DWM Mica/Acrylic backdrop integration via dwmapi."""
    if sys.platform != "win32":
        return False
    import ctypes
    from ctypes import wintypes

    try:
        dwmapi = ctypes.windll.dwmapi
        window = wintypes.HWND(hwnd)
        dark_mode = ctypes.c_int(int(dark))
        acrylic = ctypes.c_int(3)
        dwmapi.DwmSetWindowAttribute(window, 20, ctypes.byref(dark_mode), 4)
        if dwmapi.DwmSetWindowAttribute(window, 38, ctypes.byref(acrylic), 4) != 0:
            return False
        margins = (ctypes.c_int * 4)(-1, -1, -1, -1)
        return dwmapi.DwmExtendFrameIntoClientArea(window, ctypes.byref(margins)) == 0
    except (AttributeError, OSError):
        return False


class LiquidGlassCanvas(QWidget):
    """Ambient field visible beneath every painted glass surface."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.dark_mode = False
        self.native_backdrop = False

    def set_dark_mode(self, dark: bool) -> None:
        self.dark_mode = dark
        self.update()

    def set_native_backdrop(self, enabled: bool) -> None:
        self.native_backdrop = enabled
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        w, h = self.width(), self.height()
        base = 22 if self.dark_mode else 220
        alpha = 222 if self.native_backdrop else 255
        painter.fillRect(self.rect(), QColor(base, base, base, alpha))
        for x, y, scale, gray, opacity in (
            (.13, .03, .64, 255, 42 if self.dark_mode else 235),
            (.89, .48, .43, 180 if self.dark_mode else 255, 27 if self.dark_mode else 185),
            (.39, 1.1, .55, 0 if self.dark_mode else 118, 92 if self.dark_mode else 68),
        ):
            field = QRadialGradient(QPointF(w * x, h * y), max(w, h, 1) * scale)
            field.setColorAt(0, QColor(gray, gray, gray, opacity))
            field.setColorAt(1, QColor(gray, gray, gray, 0))
            painter.fillRect(self.rect(), QBrush(field))


class ElidedLabel(QLabel):
    """Retain complete accessible text while fitting a compact glass control."""

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setFont(self.font())
        group = QPalette.ColorGroup.Active if self.isEnabled() else QPalette.ColorGroup.Disabled
        painter.setPen(self.palette().color(group, QPalette.ColorRole.WindowText))
        text = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width()
        )
        painter.drawText(self.contentsRect(), self.alignment(), text)


class LiquidGlassDroplet(QWidget):
    """32x32px 3D Smoked-Obsidian Liquid Glass Icon Lens with top specular arc."""

    def __init__(
        self,
        icon_source: str | QIcon,
        dark_mode: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self.dark_mode = dark_mode
        self._icon: Optional[QIcon] = None
        self.set_icon(icon_source)

    def set_icon(self, icon_source: str | QIcon) -> None:
        if isinstance(icon_source, QIcon):
            self._icon = icon_source
        elif isinstance(icon_source, str) and (icon_source.endswith(".svg") or icon_source.endswith(".png")):
            self._icon = QIcon(icon_source)
        elif isinstance(icon_source, str):
            try:
                from flashdock.ui.icon_assets import get_icon
                # Crisp white icon for smoked obsidian background
                self._icon = get_icon(icon_source, size=16, color="#FFFFFF")
            except Exception:
                self._icon = QIcon(icon_source)
        else:
            self._icon = QIcon()
        self.update()

    def set_dark_mode(self, dark: bool) -> None:
        self.dark_mode = dark
        self.update()

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.0, 1.0, float(self.width() - 2), float(self.height() - 2))

        path = QPainterPath()
        path.addRoundedRect(rect, 9.0, 9.0)

        # 1. Smoked Obsidian body gradient (#2C2C30 -> #050507)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(44, 44, 48, 245))
        grad.setColorAt(1.0, QColor(5, 5, 7, 252))
        p.fillPath(path, QBrush(grad))

        # 2. Top-arc specular lens reflection
        shine_rect = QRectF(rect.left() + 2.5, rect.top() + 1.5, rect.width() - 5.0, rect.height() * 0.42)
        shine_path = QPainterPath()
        shine_path.addRoundedRect(shine_rect, 6.0, 6.0)
        shine_grad = QLinearGradient(shine_rect.topLeft(), shine_rect.bottomLeft())
        shine_grad.setColorAt(0.0, QColor(255, 255, 255, 110))
        shine_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(shine_path, QBrush(shine_grad))

        # 3. Specular rim border (1.0px)
        rim = QLinearGradient(rect.topLeft(), rect.bottomRight())
        rim.setColorAt(0.0, QColor(255, 255, 255, 180))
        rim.setColorAt(1.0, QColor(255, 255, 255, 35))
        p.setPen(QPen(QBrush(rim), 1.0))
        p.drawPath(path)

        # 4. Crisp centered vector SVG icon (16x16)
        if self._icon and not self._icon.isNull():
            pix = self._icon.pixmap(QSize(16, 16))
            x = int((self.width() - 16) / 2)
            y = int((self.height() - 16) / 2)
            p.drawPixmap(x, y, pix)


class LiquidGlassSheet(QFrame):
    """iOS 26 / visionOS Specular Liquid Glass Container with cursor-tracking optical sheen."""

    def __init__(
        self,
        dark_mode: bool = False,
        radius: float = 18.0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.dark_mode = dark_mode
        self.radius = radius
        self._mouse_pos = QPointF(120.0, 40.0)
        self._hovered = False
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 10)
        shadow.setColor(QColor(0, 0, 0, 28 if not dark_mode else 110))
        self.setGraphicsEffect(shadow)

    def set_dark_mode(self, dark: bool) -> None:
        self.dark_mode = dark
        effect = self.graphicsEffect()
        if isinstance(effect, QGraphicsDropShadowEffect):
            effect.setColor(QColor(0, 0, 0, 28 if not dark else 110))
        self.update()

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._mouse_pos = event.position()
        self.update()
        super().mouseMoveEvent(event)

    def track_row(self, row: QPushButton) -> None:
        row.setMouseTracking(True)
        row.installEventFilter(self)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.MouseMove:
            self._mouse_pos = QPointF(watched.mapTo(self, event.position().toPoint()))
            self.update()
        return super().eventFilter(watched, event)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(1.0, 1.0, float(self.width() - 2), float(self.height() - 2))

        path = QPainterPath()
        path.addRoundedRect(rect, self.radius, self.radius)

        # 1. Translucent Liquid Glass base fill
        # Pearl Light: rgba(255,255,255,175) -> rgba(245,245,250,120)
        # Obsidian Dark: rgba(42,42,48,145) -> rgba(20,20,24,110)
        base_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if self.dark_mode:
            base_grad.setColorAt(0.0, QColor(42, 42, 48, 145))
            base_grad.setColorAt(0.55, QColor(28, 28, 32, 125))
            base_grad.setColorAt(1.0, QColor(20, 20, 24, 110))
        else:
            base_grad.setColorAt(0.0, QColor(255, 255, 255, 175))
            base_grad.setColorAt(0.55, QColor(250, 250, 252, 145))
            base_grad.setColorAt(1.0, QColor(245, 245, 250, 120))
        p.fillPath(path, QBrush(base_grad))

        # 2. Interactive cursor-tracking radial optical sheen
        if self._hovered:
            glint = QRadialGradient(self._mouse_pos, 240.0)
            glint.setColorAt(0.0, QColor(255, 255, 255, 120 if not self.dark_mode else 35))
            glint.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillPath(path, QBrush(glint))

        # 3. 1.5px Multi-stop Specular Rim Highlight (Top-left intense catch -> bottom refraction)
        # rgba(255,255,255,245) fading to rgba(255,255,255,60)
        rim_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if self.dark_mode:
            rim_grad.setColorAt(0.0, QColor(255, 255, 255, 245))
            rim_grad.setColorAt(0.45, QColor(255, 255, 255, 40))
            rim_grad.setColorAt(1.0, QColor(255, 255, 255, 60))
        else:
            rim_grad.setColorAt(0.0, QColor(255, 255, 255, 245))
            rim_grad.setColorAt(0.45, QColor(255, 255, 255, 120))
            rim_grad.setColorAt(1.0, QColor(255, 255, 255, 60))
        p.setPen(QPen(QBrush(rim_grad), 1.5))
        p.drawPath(path)


class LiquidGlassActionRow(QPushButton):
    """
    Zero-button-border, translucent liquid glass action row for a workstation tool.
    Hosts a 32x32 LiquidGlassDroplet, title, subtitle, and right chevron.
    Maintains 100% backward compatibility with ActionCardButton for test suites.
    """

    def __init__(
        self,
        action_id: str,
        icon: str,
        label: str,
        desc: str,
        category: str = "Device",
        dark_mode: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.action_id = action_id
        self.icon_str = icon
        self.label_str = label
        self.desc_str = desc
        self.category = category
        self.dark_mode = dark_mode

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(label)
        self.setAccessibleDescription(desc)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(54)
        self.setToolTip(f"<b>{label}</b> ({category.upper()})<br>{desc}")

        row_layout = QHBoxLayout(self)
        row_layout.setContentsMargins(6, 5, 7, 5)
        row_layout.setSpacing(6)

        # 1. Smoked Obsidian Icon Droplet (32x32)
        self.droplet = LiquidGlassDroplet(icon, dark_mode=dark_mode, parent=self)
        self.droplet.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row_layout.addWidget(self.droplet, 0, Qt.AlignmentFlag.AlignVCenter)

        # 2. Text layout: Title + Category Subtitle
        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(1)

        self.title_lbl = ElidedLabel(label)
        self.title_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.title_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self.title_lbl)

        self.desc_lbl = ElidedLabel(desc)
        self.desc_lbl.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.desc_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        text_layout.addWidget(self.desc_lbl)
        row_layout.addLayout(text_layout, 1)

        # 3. Badge label (kept for backward-compatibility with tests)
        self.badge_lbl = QLabel(category.upper())
        self.badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.badge_lbl.setVisible(False)
        row_layout.addWidget(self.badge_lbl)

        # 4. Subtle visionOS chevron indicator
        self.chevron_lbl = QLabel("›")
        self.chevron_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.chevron_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_layout.addWidget(self.chevron_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        self.apply_theme("dark" if dark_mode else "light")

    def apply_theme(self, theme: str) -> None:
        self.dark_mode = theme.lower() == "dark"
        self.droplet.set_dark_mode(self.dark_mode)
        ink = "255, 255, 255" if self.dark_mode else "0, 0, 0"
        text = "#f5f5f5" if self.dark_mode else "#171717"
        muted = "#b5b5b5" if self.dark_mode else "#545454"
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none; border-radius: 9px; padding: 0;
            }}
            QPushButton:enabled:hover, QPushButton:focus {{
                background: rgba({ink}, 22);
            }}
            QPushButton:enabled:pressed {{
                background: rgba({ink}, 38);
            }}
        """)
        self.title_lbl.setStyleSheet(
            f"font-size: 12px; font-weight: 600; color: {text}; background: transparent;"
        )
        self.desc_lbl.setStyleSheet(f"font-size: 10px; color: {muted}; background: transparent;")
        self.chevron_lbl.setStyleSheet(f"font-size: 16px; color: {muted}; background: transparent;")

    def set_offline_state(self, is_offline: bool, theme: str) -> None:
        self.setEnabled(not is_offline)
        self.setCursor(Qt.CursorShape.ForbiddenCursor if is_offline else Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Offline. This tool requires internet access." if is_offline else self.desc_str)
        self.apply_theme(theme)
        self.chevron_lbl.setText("–" if is_offline else "›")
