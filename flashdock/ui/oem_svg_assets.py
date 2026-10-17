"""
100% Vector SVG Hardware Key-Combination Diagrams and Status Badges
for Candidate 3 (Xiaomi HyperOS 2.0 Fastboot & Samsung Download Mode).
"""
from __future__ import annotations

from typing import Dict

SVG_KEYCOMBO_XIAOMI_FASTBOOT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 120" width="220" height="120">
  <rect x="70" y="10" width="80" height="100" rx="12" fill="#1A1D24" stroke="#3B82F6" stroke-width="2"/>
  <rect x="76" y="20" width="68" height="80" rx="6" fill="#111318"/>
  <!-- Volume Down Highlighted -->
  <rect x="150" y="42" width="6" height="18" rx="2" fill="#F59E0B"/>
  <!-- Power Button Highlighted -->
  <rect x="150" y="68" width="6" height="14" rx="2" fill="#10B981"/>
  <text x="110" y="55" fill="#F3F4F6" font-family="Segoe UI, sans-serif" font-size="9" text-anchor="middle">FASTBOOT</text>
  <text x="110" y="70" fill="#9CA3AF" font-family="Segoe UI, sans-serif" font-size="8" text-anchor="middle">VOL- + PWR</text>
</svg>"""

SVG_KEYCOMBO_SAMSUNG_DOWNLOAD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 120" width="220" height="120">
  <rect x="70" y="8" width="80" height="92" rx="12" fill="#1A1D24" stroke="#06B6D4" stroke-width="2"/>
  <rect x="76" y="16" width="68" height="74" rx="6" fill="#111318"/>
  <!-- Volume Up + Volume Down Highlighted -->
  <rect x="150" y="26" width="6" height="16" rx="2" fill="#06B6D4"/>
  <rect x="150" y="46" width="6" height="16" rx="2" fill="#06B6D4"/>
  <!-- USB-C Cable Insert -->
  <rect x="104" y="100" width="12" height="16" rx="2" fill="#10B981"/>
  <text x="110" y="50" fill="#F3F4F6" font-family="Segoe UI, sans-serif" font-size="9" text-anchor="middle">ODIN MODE</text>
  <text x="110" y="65" fill="#9CA3AF" font-family="Segoe UI, sans-serif" font-size="8" text-anchor="middle">VOL+ & VOL- + USB</text>
</svg>"""

SVG_BADGE_HYPEROS_ARB_SAFE = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <path d="M12 2L4 5v6.09c0 5.05 3.41 9.76 8 10.91 4.59-1.15 8-5.86 8-10.91V5l-8-3z" fill="#10B981" fill-opacity="0.2" stroke="#10B981" stroke-width="2"/>
  <path d="M9 12l2 2 4-4" fill="none" stroke="#10B981" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""

SVG_BADGE_KNOX_SHIELD = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">
  <rect x="4" y="11" width="16" height="10" rx="2" fill="#06B6D4" fill-opacity="0.2" stroke="#06B6D4" stroke-width="2"/>
  <path d="M8 11V7a4 4 0 018 0v4" fill="none" stroke="#06B6D4" stroke-width="2" stroke-linecap="round"/>
</svg>"""

OEM_WORKFLOW_SVGS: Dict[str, str] = {
    "xiaomi_fastboot_combo": SVG_KEYCOMBO_XIAOMI_FASTBOOT,
    "samsung_download_combo": SVG_KEYCOMBO_SAMSUNG_DOWNLOAD,
    "hyperos_arb_safe": SVG_BADGE_HYPEROS_ARB_SAFE,
    "knox_shield": SVG_BADGE_KNOX_SHIELD,
}
