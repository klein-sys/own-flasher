"""
FlashDock — Phase 16 Automated Production Release Builder.

Orchestrates verification, PyInstaller compilation, ZIP packaging, and
SHA-256 checksum calculation for the standalone Windows distribution.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT_DIR / "dist"
BUILD_DIR = ROOT_DIR / "build"
APP_DIR = DIST_DIR / "FlashDock_App"


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hex digest of a given file."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    print("=" * 70)
    print("  [FlashDock v1.0.0] Production Release Build Pipeline")
    print("=" * 70)

    # 1. Verify tests
    print("\n[1/4] Running automated test verification...")
    pytest_res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
    )
    combined_out = (pytest_res.stdout or "") + (pytest_res.stderr or "")
    if "FAILED" in combined_out or "ERROR" in combined_out or ("passed" not in combined_out):
        print(f"[X] Error: Test suite failed! Output:\n{combined_out}")
        return 1
    
    # Extract passed count
    for line in combined_out.splitlines():
        if "passed in" in line:
            print(f"  [OK] {line.strip()}")
            break
    else:
        print("  [OK] All test suites passed.")

    # 2. Terminate any running FlashDock processes and invoke PyInstaller
    if sys.platform == "win32":
        try:
            subprocess.run(["taskkill", "/F", "/IM", "FlashDock.exe"], capture_output=True)
        except Exception:
            pass

    print("\n[2/4] Compiling standalone Windows distribution via PyInstaller...")
    spec_path = ROOT_DIR / "flashdock.spec"
    pyinstaller_res = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", str(spec_path)],
        cwd=ROOT_DIR,
    )
    if pyinstaller_res.returncode != 0:
        print("[X] Error: PyInstaller build failed!")
        return 1

    exe_path = APP_DIR / "FlashDock.exe"
    if not exe_path.exists():
        print(f"[X] Error: Compiled executable not found at {exe_path}")
        return 1

    exe_size_mb = exe_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] Compiled: {exe_path.name} ({exe_size_mb:.2f} MB)")

    # 3. Create release zip archive
    zip_name = "FlashDock-v1.0.0-windows-x64.zip"
    zip_path = DIST_DIR / zip_name
    print(f"\n[3/4] Creating distribution archive: {zip_name}...")

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in APP_DIR.rglob("*"):
            if file.is_file():
                rel_path = file.relative_to(APP_DIR)
                arcname = Path("FlashDock") / rel_path
                zf.write(file, str(arcname))

    zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"  [OK] Created archive: {zip_path.name} ({zip_size_mb:.2f} MB)")

    # 4. Generate SHA256 checksums
    print("\n[4/4] Calculating SHA-256 integrity checksums...")
    sums_file = DIST_DIR / "SHA256SUMS.txt"
    exe_hash = compute_sha256(exe_path)
    zip_hash = compute_sha256(zip_path)

    sums_text = (
        f"{exe_hash}  FlashDock/FlashDock.exe\n"
        f"{zip_hash}  {zip_name}\n"
    )
    sums_file.write_text(sums_text, encoding="utf-8")
    print(f"  [OK] Checksums saved to: {sums_file.name}")
    print(f"       FlashDock.exe: {exe_hash}")
    print(f"       Release ZIP:   {zip_hash}")

    print("\n" + "=" * 70)
    print("  [SUCCESS] FlashDock v1.0.0 Release Build Complete!")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
