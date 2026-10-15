"""
Unit & Qt6 UI/UX Verification Suite for FlashDock v1.5.0 (Pillar 1).

Tests:
 1. Slate Obsidian (Dark) & Soft Frost (Light) semantic token completeness.
 2. Unmistakable visual differentiation between Bootloader (#007AFF Cobalt)
    and FastbootD Userspace (#00E5FF Electric Cyan).
 3. High-DPI `QScrollArea`, `QSplitter`, and modal dialog geometry helpers.
 4. HiDPI vector SVG icon generation across `icon_assets.py` and `brand_assets.py`.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
import pytest

from flashdock.ui.brand_assets import get_brand_icon
from flashdock.ui.dpi_layout import (
    MIN_BUTTON_HEIGHT_PX,
    MIN_CENTRAL_CANVAS_WIDTH_PX,
    MIN_SIDE_TERMINAL_WIDTH_PX,
    apply_responsive_screen_geometry,
    configure_frameless_scroll_area,
    harden_modal_dialog,
    harden_splitter_geometry,
)
from flashdock.ui.icon_assets import get_icon
from flashdock.ui.theme_tokens import (
    SLATE_OBSIDIAN_TOKENS,
    SOFT_FROST_TOKENS,
    build_workstation_supplemental_qss,
    get_mode_badge_palette,
    get_theme_tokens,
)


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestThemeTokensAndModeBadges:
    """Tests for macOS Big Sur + HyperOS 2.0 theme tokens and mode pill differentiation."""

    def test_dark_and_light_theme_tokens(self) -> None:
        dark = get_theme_tokens("dark")
        light = get_theme_tokens("light")
        assert dark == SLATE_OBSIDIAN_TOKENS
        assert light == SOFT_FROST_TOKENS
        assert dark.is_dark is True
        assert light.is_dark is False
        assert dark.accent_primary == "#007AFF"
        assert light.accent_primary == "#007AFF"

    def test_bootloader_vs_fastbootd_distinct_colors(self) -> None:
        fb_boot = get_mode_badge_palette("fastboot", "dark")
        fb_user = get_mode_badge_palette("fastbootd", "dark")

        assert fb_boot["fg"] == "#007AFF"
        assert fb_user["fg"] == "#00E5FF"
        assert fb_boot["fg"] != fb_user["fg"]
        assert "BOOTLOADER" in fb_boot["label"]
        assert "USERSPACE" in fb_user["label"]

    def test_supplemental_qss_contains_scroll_and_focus_rules(self) -> None:
        qss = build_workstation_supplemental_qss("dark")
        assert "QScrollArea" in qss
        assert "QSplitter::handle" in qss
        assert "#007AFF" in qss


class TestHighDpiLayoutAndSplitterHardening:
    """Tests for High-DPI widget geometry, scroll areas, and splitter anti-clipping."""

    def test_configure_frameless_scroll_area(self, qapp: QApplication) -> None:
        scroll = QScrollArea()
        configure_frameless_scroll_area(scroll)
        assert scroll.widgetResizable() is True

    def test_apply_responsive_screen_geometry_enforces_min_heights(self, qapp: QApplication) -> None:
        screen = QWidget()
        layout = QVBoxLayout(screen)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        btn = QPushButton("Flash")
        inp = QLineEdit()
        layout.addWidget(btn)
        layout.addWidget(inp)

        apply_responsive_screen_geometry(screen)
        assert btn.minimumHeight() >= MIN_BUTTON_HEIGHT_PX
        assert inp.minimumHeight() >= MIN_BUTTON_HEIGHT_PX
        assert layout.spacing() >= 10

    def test_harden_splitter_geometry_prevents_collapsing(self, qapp: QApplication) -> None:
        splitter = QSplitter()
        canvas = QWidget()
        terminal = QWidget()
        splitter.addWidget(canvas)
        splitter.addWidget(terminal)

        harden_splitter_geometry(splitter)
        assert splitter.childrenCollapsible() is False
        assert canvas.minimumWidth() == MIN_CENTRAL_CANVAS_WIDTH_PX
        assert terminal.minimumWidth() == MIN_SIDE_TERMINAL_WIDTH_PX

    def test_harden_modal_dialog(self, qapp: QApplication) -> None:
        dlg = QDialog()
        harden_modal_dialog(dlg, min_width=540, min_height=380)
        assert dlg.minimumWidth() >= 540
        assert dlg.minimumHeight() >= 380


class TestVectorSvgAssetsHiDpi:
    """Tests that all SVG icons and brand badges render cleanly without raw emojis."""

    @pytest.mark.parametrize("icon_name", ["shield", "bolt", "terminal", "check", "warning", "cpu"])
    def test_get_icon_returns_valid_qicon(self, qapp: QApplication, icon_name: str) -> None:
        icon = get_icon(icon_name, size=24)
        assert not icon.isNull()

    @pytest.mark.parametrize("brand_id", ["google", "xiaomi", "samsung", "transsion", "nothing"])
    def test_get_brand_icon_returns_valid_qicon(self, qapp: QApplication, brand_id: str) -> None:
        icon = get_brand_icon(brand_id, size=28)
        assert not icon.isNull()
