"""
FlashDock — Brand Vector Asset Manager & Icon Provider.

Provides clean, professional vector SVG brand logos and badges for:
Tecno, Infinix, itel, Transsion, Google Pixel, Samsung, Xiaomi/Poco/Redmi,
OnePlus, Motorola, MediaTek, Qualcomm, Unisoc, and Generic Android.
Replaces informal emoji stickers with polished Apple HIG brand aesthetics.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from flashdock.constants import DATA_DIR
from flashdock.logger import get_logger

log = get_logger(__name__)

ASSETS_DIR = DATA_DIR / "assets" / "brands"

# High-resolution, clean SVG vector definitions for each brand
BRAND_SVGS: dict[str, str] = {
    "google": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
        <path fill="#4285F4" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
        <path fill="#34A853" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
        <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
        <path fill="#EA4335" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>""",

    "samsung": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 48">
        <rect width="120" height="48" rx="8" fill="#1428A0"/>
        <text x="60" y="32" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="900" font-size="21" letter-spacing="2.5" text-anchor="middle">SAMSUNG</text>
    </svg>""",

    "xiaomi": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
        <rect width="48" height="48" rx="10" fill="#FF6900"/>
        <rect x="14" y="14" width="5" height="20" rx="2.5" fill="#FFFFFF"/>
        <rect x="29" y="14" width="5" height="20" rx="2.5" fill="#FFFFFF"/>
        <rect x="14" y="14" width="20" height="5" rx="2.5" fill="#FFFFFF"/>
        <rect x="21" y="22" width="5" height="12" rx="2" fill="#FFFFFF"/>
    </svg>""",

    "tecno": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 48">
        <rect width="100" height="48" rx="8" fill="#0056B3"/>
        <text x="50" y="32" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="900" font-size="20" letter-spacing="3" text-anchor="middle">TECNO</text>
    </svg>""",

    "infinix": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 48">
        <rect width="110" height="48" rx="8" fill="#059669"/>
        <text x="55" y="31" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="800" font-size="18" letter-spacing="2" text-anchor="middle">INFINIX</text>
    </svg>""",

    "itel": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 48">
        <rect width="90" height="48" rx="8" fill="#DC2626"/>
        <text x="45" y="32" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="900" font-size="22" letter-spacing="1" text-anchor="middle">itel</text>
    </svg>""",

    "transsion": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 130 48">
        <rect width="130" height="48" rx="8" fill="#1E293B"/>
        <text x="65" y="30" fill="#38BDF8" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="800" font-size="15" letter-spacing="2" text-anchor="middle">TRANSSION</text>
    </svg>""",

    "oneplus": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
        <rect width="48" height="48" rx="8" fill="#F50514"/>
        <rect x="7" y="7" width="34" height="34" rx="4" fill="none" stroke="#FFFFFF" stroke-width="3"/>
        <text x="18" y="32" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="900" font-size="22">1</text>
        <path d="M30 18v8M26 22h8" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round"/>
    </svg>""",

    "motorola": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
        <circle cx="24" cy="24" r="22" fill="#001435"/>
        <path d="M12 32l6-16 6 10 6-10 6 16" fill="none" stroke="#007AFF" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>""",

    "mediatek": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 48">
        <rect width="120" height="48" rx="8" fill="#2563EB"/>
        <text x="60" y="31" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="800" font-size="17" letter-spacing="1.5" text-anchor="middle">MediaTek</text>
    </svg>""",

    "qualcomm": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 48">
        <rect width="120" height="48" rx="8" fill="#D92D20"/>
        <text x="60" y="31" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="800" font-size="16" letter-spacing="1" text-anchor="middle">Snapdragon</text>
    </svg>""",

    "unisoc": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 110 48">
        <rect width="110" height="48" rx="8" fill="#7C3AED"/>
        <text x="55" y="31" fill="#FFFFFF" font-family="-apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif" font-weight="800" font-size="17" letter-spacing="2" text-anchor="middle">UNISOC</text>
    </svg>""",

    "android": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
        <path fill="#3DDC84" d="M10 24h28v14c0 3.3-2.7 6-6 6H16c-3.3 0-6-2.7-6-6V24z"/>
        <path fill="#3DDC84" d="M12 21c0-6.6 5.4-12 12-12s12 5.4 12 12H12z"/>
        <circle cx="18" cy="15" r="2" fill="#FFFFFF"/>
        <circle cx="30" cy="15" r="2" fill="#FFFFFF"/>
        <line x1="16" y1="9" x2="12" y2="3" stroke="#3DDC84" stroke-width="2.5" stroke-linecap="round"/>
        <line x1="32" y1="9" x2="36" y2="3" stroke="#3DDC84" stroke-width="2.5" stroke-linecap="round"/>
    </svg>""",
}


def _ensure_assets() -> None:
    """Save vector assets to data directory if not already created."""
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for name, svg_data in BRAND_SVGS.items():
        file_path = ASSETS_DIR / f"{name}.svg"
        if not file_path.exists():
            try:
                file_path.write_text(svg_data.strip(), encoding="utf-8")
            except Exception as e:
                log.debug("Could not write brand SVG %s: %s", name, e)


_ensure_assets()


def get_brand_pixmap(brand_name: str, width: int = 40, height: int = 24) -> QPixmap:
    """Render high-resolution vector brand logo as a QPixmap."""
    key = (brand_name or "").lower().strip()
    if "tecno" in key:
        raw_key = "tecno"
    elif "infinix" in key:
        raw_key = "infinix"
    elif "itel" in key:
        raw_key = "itel"
    elif "transsion" in key:
        raw_key = "transsion"
    elif "xiaomi" in key or "redmi" in key or "poco" in key:
        raw_key = "xiaomi"
    elif "samsung" in key:
        raw_key = "samsung"
    elif "google" in key or "pixel" in key:
        raw_key = "google"
    elif "oneplus" in key:
        raw_key = "oneplus"
    elif "motorola" in key or "moto" in key:
        raw_key = "motorola"
    elif "mediatek" in key or "mtk" in key:
        raw_key = "mediatek"
    elif "qualcomm" in key or "snapdragon" in key:
        raw_key = "qualcomm"
    elif "unisoc" in key or "spreadtrum" in key:
        raw_key = "unisoc"
    else:
        raw_key = "android"

    svg_data = BRAND_SVGS.get(raw_key, BRAND_SVGS["android"])
    renderer = QSvgRenderer(QByteArray(svg_data.encode("utf-8")))

    pixmap = QPixmap(width, height)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderer.render(painter)
    painter.end()

    return pixmap


def get_brand_badge(brand_name: str, width: int = 40, height: int = 24) -> QPixmap:
    """Convenience alias for get_brand_pixmap."""
    return get_brand_pixmap(brand_name, width=width, height=height)


def get_brand_icon(brand_name: str, size: int = 32) -> QIcon:
    """Return a QIcon for the specified brand."""
    pix = get_brand_pixmap(brand_name, width=size, height=size)
    return QIcon(pix)


class BrandBadgeWidget(QFrame):
    """Refined Apple HIG horizontal brand badge with vector logo and title."""

    def __init__(self, brand_name: str, model_name: str = "", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            "background-color: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.12); "
            "border-radius: 8px; padding: 4px 10px;"
        )
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 8, 4)
        layout.setSpacing(8)

        self._icon_lbl = QLabel()
        pix = get_brand_pixmap(brand_name, width=48, height=22)
        self._icon_lbl.setPixmap(pix)
        layout.addWidget(self._icon_lbl)

        display_text = brand_name.title() if brand_name else "Android"
        if model_name:
            display_text += f" — {model_name}"

        self._text_lbl = QLabel(display_text)
        self._text_lbl.setStyleSheet("font-weight: 600; font-size: 13px; color: #FFFFFF;")
        layout.addWidget(self._text_lbl)
        layout.addStretch()

    def update_brand(self, brand_name: str, model_name: str = "") -> None:
        pix = get_brand_pixmap(brand_name, width=48, height=22)
        self._icon_lbl.setPixmap(pix)
        display_text = brand_name.title() if brand_name else "Android"
        if model_name:
            display_text += f" — {model_name}"
        self._text_lbl.setText(display_text)


# Re-export vector icon methods for unified image asset access
from flashdock.ui.icon_assets import create_icon_label, get_icon, get_icon_pixmap
