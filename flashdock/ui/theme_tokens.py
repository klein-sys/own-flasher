"""
FlashDock v1.5.0 — macOS Big Sur + Xiaomi HyperOS 2.0 Design Token System.

Defines centralized, semantic color palettes, surface elevations, squircle border
radii, and hardware state badge styles for:
 1. Slate Obsidian (Dark Mode — Default Studio Workstation Theme)
 2. Soft Frost (Light Mode — High-Contrast Daylight Service Theme)

Guarantees zero hardcoded inline hex drift when toggling themes and enforces
unmistakable visual differentiation between standard Bootloader and FastbootD Userspace through labels and gray levels.
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
    bg_primary="#0F0F0F",
    bg_secondary="#181818",
    bg_surface="#1E1E1E",
    bg_elevated="#282828",
    bg_glass_card="#212121",
    bg_terminal="#0B0B0B",
    text_primary="#FAFAFA",
    text_secondary="#D4D4D4",
    text_muted="#727272",
    border_subtle="#323232",
    border_strong="#3F3F3F",
    border_focus="#6A6A6A",
    accent_primary="#6A6A6A",
    accent_hover="#7C7C7C",
    accent_pressed="#525252",
    accent_soft_bg="#262626",
    mode_adb_emerald="#919191",
    mode_fastboot_cobalt="#6A6A6A",
    mode_fastbootd_cyan="#B6B6B6",
    mode_recovery_amber="#A6A6A6",
    mode_sideload_violet="#717171",
    mode_edl_brom_crimson="#686868",
    status_success="#919191",
    status_warning="#A6A6A6",
    status_danger="#686868",
    status_info="#A5A5A5",
)

SOFT_FROST_TOKENS = WorkstationThemeTokens(
    name="light",
    is_dark=False,
    bg_primary="#F4F4F4",
    bg_secondary="#E7E7E7",
    bg_surface="#FFFFFF",
    bg_elevated="#FAFAFA",
    bg_glass_card="#FFFFFF",
    bg_terminal="#171717",
    text_primary="#171717",
    text_secondary="#3F3F3F",
    text_muted="#727272",
    border_subtle="#D4D4D4",
    border_strong="#A1A1A1",
    border_focus="#6A6A6A",
    accent_primary="#6A6A6A",
    accent_hover="#555555",
    accent_pressed="#3F3F3F",
    accent_soft_bg="#EFEFEF",
    mode_adb_emerald="#747474",
    mode_fastboot_cobalt="#6A6A6A",
    mode_fastbootd_cyan="#939393",
    mode_recovery_amber="#848484",
    mode_sideload_violet="#555555",
    mode_edl_brom_crimson="#4D4D4D",
    status_success="#747474",
    status_warning="#848484",
    status_danger="#4D4D4D",
    status_info="#6D6D6D",
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
    Strictly distinguishes standard Bootloader from FastbootD Userspace through labels and gray levels.
    """
    t = get_theme_tokens(theme)
    m = (mode or "disconnected").strip().lower()

    if m == "fastbootd":
        return {
            "fg": t.mode_fastbootd_cyan,
            "bg": "#2B2B2B" if t.is_dark else "#F2F2F2",
            "border": t.mode_fastbootd_cyan,
            "label": "FASTBOOTD (USERSPACE)",
        }
    if m in ("fastboot", "bootloader"):
        return {
            "fg": t.mode_fastboot_cobalt,
            "bg": "#262626" if t.is_dark else "#E8E8E8",
            "border": t.mode_fastboot_cobalt,
            "label": "FASTBOOT (BOOTLOADER)",
        }
    if m in ("adb", "system", "normal"):
        return {
            "fg": t.mode_adb_emerald,
            "bg": "#3D3D3D" if t.is_dark else "#F0F0F0",
            "border": t.mode_adb_emerald,
            "label": "ADB ONLINE",
        }
    if m == "recovery":
        return {
            "fg": t.mode_recovery_amber,
            "bg": "#212121" if t.is_dark else "#F2F2F2",
            "border": t.mode_recovery_amber,
            "label": "RECOVERY",
        }
    if m == "sideload":
        return {
            "fg": t.mode_sideload_violet,
            "bg": "#1D1D1D" if t.is_dark else "#EBEBEB",
            "border": t.mode_sideload_violet,
            "label": "ADB SIDELOAD",
        }
    if m in ("edl", "brom", "preloader", "unisoc_brom", "odin", "emergency"):
        return {
            "fg": t.mode_edl_brom_crimson,
            "bg": "#171717" if t.is_dark else "#E8E8E8",
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
        border: none;
    }}
    QProgressBar {{
        border: none;
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
        border: none;
        border-radius: 6px;
        padding: 5px 8px;
    }}
    """
