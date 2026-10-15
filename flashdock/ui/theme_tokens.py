"""
FlashDock v1.5.0 — macOS Big Sur + Xiaomi HyperOS 2.0 Design Token System.

Defines centralized, semantic color palettes, surface elevations, squircle border
radii, and hardware state badge styles for:
 1. Slate Obsidian (Dark Mode — Default Studio Workstation Theme)
 2. Soft Frost (Light Mode — High-Contrast Daylight Service Theme)

Guarantees zero hardcoded inline hex drift when toggling themes and enforces
unmistakable visual differentiation between standard Bootloader (`#007AFF` Cobalt)
and FastbootD Userspace (`#00E5FF` Electric Cyan).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkstationThemeTokens:
    """Complete semantic token set for a FlashDock UI theme."""

    name: str
    is_dark: bool
    # Surfaces
    bg_primary: str
    bg_secondary: str
    bg_surface: str
    bg_elevated: str
    bg_glass_card: str
    bg_terminal: str
    # Typography
    text_primary: str
    text_secondary: str
    text_muted: str
    # Borders & Dividers
    border_subtle: str
    border_strong: str
    border_focus: str
    # Brand & Interactive Accents (macOS Big Sur + HyperOS 2.0)
    accent_primary: str
    accent_hover: str
    accent_pressed: str
    accent_soft_bg: str
    # Hardware Connection Mode Tokens
    mode_adb_emerald: str
    mode_fastboot_cobalt: str
    mode_fastbootd_cyan: str
    mode_recovery_amber: str
    mode_sideload_violet: str
    mode_edl_brom_crimson: str
    # Semantic Status
    status_success: str
    status_warning: str
    status_danger: str
    status_info: str


SLATE_OBSIDIAN_TOKENS = WorkstationThemeTokens(
    name="dark",
    is_dark=True,
    bg_primary="#0B0F17",
    bg_secondary="#111827",
    bg_surface="#161F30",
    bg_elevated="#1E293B",
    bg_glass_card="#192234",
    bg_terminal="#080B11",
    text_primary="#F8FAFC",
    text_secondary="#CBD5E1",
    text_muted="#64748B",
    border_subtle="#26334D",
    border_strong="#334155",
    border_focus="#007AFF",
    accent_primary="#007AFF",
    accent_hover="#2589FF",
    accent_pressed="#005ECB",
    accent_soft_bg="#13284C",
    mode_adb_emerald="#10B981",
    mode_fastboot_cobalt="#007AFF",
    mode_fastbootd_cyan="#00E5FF",
    mode_recovery_amber="#F59E0B",
    mode_sideload_violet="#8B5CF6",
    mode_edl_brom_crimson="#EF4444",
    status_success="#10B981",
    status_warning="#F59E0B",
    status_danger="#EF4444",
    status_info="#38BDF8",
)

SOFT_FROST_TOKENS = WorkstationThemeTokens(
    name="light",
    is_dark=False,
    bg_primary="#F1F5F9",
    bg_secondary="#E2E8F0",
    bg_surface="#FFFFFF",
    bg_elevated="#F8FAFC",
    bg_glass_card="#FFFFFF",
    bg_terminal="#0F172A",
    text_primary="#0F172A",
    text_secondary="#334155",
    text_muted="#64748B",
    border_subtle="#CBD5E1",
    border_strong="#94A3B8",
    border_focus="#007AFF",
    accent_primary="#007AFF",
    accent_hover="#0062CC",
    accent_pressed="#004999",
    accent_soft_bg="#E0F2FE",
    mode_adb_emerald="#059669",
    mode_fastboot_cobalt="#007AFF",
    mode_fastbootd_cyan="#00B8D4",
    mode_recovery_amber="#D97706",
    mode_sideload_violet="#7C3AED",
    mode_edl_brom_crimson="#DC2626",
    status_success="#059669",
    status_warning="#D97706",
    status_danger="#DC2626",
    status_info="#0284C7",
)


def get_theme_tokens(theme: str = "dark") -> WorkstationThemeTokens:
    """Return the semantic `WorkstationThemeTokens` for `'dark'` or `'light'`."""
    normalized = (theme or "dark").strip().lower()
    if normalized == "light":
        return SOFT_FROST_TOKENS
    return SLATE_OBSIDIAN_TOKENS


def get_mode_badge_palette(mode: str, theme: str = "dark") -> dict[str, str]:
    """
    Return `(fg_color, bg_color, border_color, label)` for any Android hardware mode.
    Strictly distinguishes standard Bootloader (`#007AFF` Cobalt) from
    FastbootD Userspace (`#00E5FF` Electric Cyan).
    """
    t = get_theme_tokens(theme)
    m = (mode or "disconnected").strip().lower()

    if m == "fastbootd":
        return {
            "fg": t.mode_fastbootd_cyan,
            "bg": "#083344" if t.is_dark else "#E0F7FA",
            "border": t.mode_fastbootd_cyan,
            "label": "FASTBOOTD (USERSPACE)",
        }
    if m in ("fastboot", "bootloader"):
        return {
            "fg": t.mode_fastboot_cobalt,
            "bg": "#13284C" if t.is_dark else "#DBEAFE",
            "border": t.mode_fastboot_cobalt,
            "label": "FASTBOOT (BOOTLOADER)",
        }
    if m in ("adb", "system", "normal"):
        return {
            "fg": t.mode_adb_emerald,
            "bg": "#064E3B" if t.is_dark else "#D1FAE5",
            "border": t.mode_adb_emerald,
            "label": "ADB ONLINE",
        }
    if m == "recovery":
        return {
            "fg": t.mode_recovery_amber,
            "bg": "#451A03" if t.is_dark else "#FEF3C7",
            "border": t.mode_recovery_amber,
            "label": "RECOVERY",
        }
    if m == "sideload":
        return {
            "fg": t.mode_sideload_violet,
            "bg": "#2E1065" if t.is_dark else "#EDE9FE",
            "border": t.mode_sideload_violet,
            "label": "ADB SIDELOAD",
        }
    if m in ("edl", "brom", "preloader", "unisoc_brom", "odin", "emergency"):
        return {
            "fg": t.mode_edl_brom_crimson,
            "bg": "#450A0A" if t.is_dark else "#FEE2E2",
            "border": t.mode_edl_brom_crimson,
            "label": f"EMERGENCY ({m.upper()})",
        }
    return {
        "fg": t.text_muted,
        "bg": t.bg_elevated,
        "border": t.border_subtle,
        "label": "DISCONNECTED",
    }


def build_workstation_supplemental_qss(theme: str = "dark") -> str:
    """
    Generate supplemental macOS Big Sur + HyperOS 2.0 QSS rules that harden
    scroll areas, splitter handles, focus rings, and High-DPI control spacing.
    """
    t = get_theme_tokens(theme)
    return f"""
    /* v1.5.0 macOS Big Sur + HyperOS 2.0 Surface & Focus Polish */
    QScrollArea {{
        border: none;
        background: transparent;
    }}
    QSplitter::handle {{
        background-color: {t.border_subtle};
    }}
    QSplitter::handle:hover {{
        background-color: {t.accent_primary};
    }}
    QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus, QTextEdit:focus, QListWidget:focus {{
        border: 1px solid {t.border_focus};
    }}
    QProgressBar {{
        border: 1px solid {t.border_subtle};
        border-radius: 6px;
        background-color: {t.bg_secondary};
        text-align: center;
        color: {t.text_primary};
        font-weight: 600;
        min-height: 14px;
    }}
    QProgressBar::chunk {{
        background-color: {t.accent_primary};
        border-radius: 5px;
    }}
    QToolTip {{
        background-color: {t.bg_elevated};
        color: {t.text_primary};
        border: 1px solid {t.border_strong};
        border-radius: 6px;
        padding: 5px 8px;
    }}
    """
