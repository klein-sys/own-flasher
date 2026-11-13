"""Generate the monochrome SVG tool pack without importing Qt."""

from pathlib import Path


ICONS_SVG = {
    "check-phone": '<rect x="6" y="2" width="12" height="20" rx="2.5"/><path d="M9 10l2 2 4-4"/><path d="M10 18h4"/>',
    "safety-checklist": '<path d="M12 2l8 4v6c0 4.5-3.8 8.7-8 10-4.2-1.3-8-5.5-8-10V6l8-4z"/><path d="M9 12l2 2 4-4"/>',
    "backup-restore": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>',
    "diagnostics-tweaks": '<path d="M4 21v-7m0-4V3m8 18v-9m0-4V3m8 18v-5m0-4V3M1 14h6m2-6h6m2 8h6"/>',
    "sideload-apps": '<path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><path d="M7.5 4.21L12 6.81l4.5-2.6M12 22.08V12"/>',
    "screen-mirror": '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8m-4-4v4"/>',
    "wireless-adb": '<path d="M5 12.55a11 11 0 0114.08 0M1.42 9a16 16 0 0121.16 0M8.53 16.11a6 6 0 016.95 0"/><circle cx="12" cy="20" r="1.5"/>',
    "payload-dumper": '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6M12 18v-6m0 6l-2.5-2.5M12 18l2.5-2.5"/>',
    "root-phone": '<path d="M4 17l6-6-6-6m8 14h8M15 4l-4 7h5l-3 6 7-8h-5V4z"/>',
    "manage-modules": '<path d="M12 2L2 7l10 5 10-5-10-5zM2 12l10 5 10-5M2 17l10 5 10-5"/>',
    "fix-play-integrity": '<circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 5-5.5"/>',
    "fix-bricked": '<path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/>',
    "unlock-bootloader": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 017.8-1"/><circle cx="12" cy="16" r="1.5"/>',
    "flash-rom": '<rect x="5" y="5" width="14" height="14" rx="2"/><path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3M12 8v6m0 0l-2.5-2.5M12 14l2.5-2.5"/>',
    "mtk-unisoc": '<rect x="7" y="7" width="10" height="10" rx="1.5"/><rect x="10" y="10" width="4" height="4"/><path d="M9 3v4m6-4v4M9 17v4m6-4v4M3 9h4m-4 6h4m10-6h4m-4 6h4"/>',
    "return-stock": '<path d="M1 4v6h6m-3.49 5a9 9 0 102.13-9.36L1 10"/>',
}


def generate_icon_pack(output_dir: str | Path | None = None) -> None:
    base = Path(output_dir) if output_dir else Path(__file__).resolve().parents[1] / "assets" / "icons"
    base.mkdir(parents=True, exist_ok=True)
    for name, inner in ICONS_SVG.items():
        for variant, stroke in (("light", "#ffffff"), ("dark", "#000000")):
            svg = (
                '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
                f'viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
                'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
                f"{inner}</svg>\n"
            )
            (base / f"{name}_{variant}.svg").write_text(svg, encoding="utf-8")


if __name__ == "__main__":
    generate_icon_pack()
