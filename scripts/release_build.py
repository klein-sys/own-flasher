"""Test and build the FlashDock Windows distribution in an isolated staging directory."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import sysconfig
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from flashdock import __version__


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def promote_outputs(staging: Path, output: Path, names: tuple[str, ...]) -> None:
    """Keep the previous build and restore it if promotion fails."""
    archive = output / "archive" / datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%fZ")
    previous: list[str] = []
    installed: list[str] = []
    try:
        for name in names:
            existing = output / name
            if existing.exists():
                archive.mkdir(parents=True, exist_ok=True)
                existing.rename(archive / name)
                previous.append(name)
        for name in names:
            (staging / name).rename(output / name)
            installed.append(name)
    except OSError:
        for name in reversed(installed):
            (output / name).rename(staging / name)
        for name in reversed(previous):
            (archive / name).rename(output / name)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=ROOT_DIR / "dist")
    args = parser.parse_args()
    if sysconfig.get_platform() != "win-amd64":
        parser.error("An x64 Windows Python environment is required.")

    test_env = os.environ.copy()
    test_env["QT_QPA_PLATFORM"] = "offscreen"
    test_result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-q"], cwd=ROOT_DIR, env=test_env
    )
    if test_result.returncode:
        return test_result.returncode

    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    archive_name = f"FlashDock-v{__version__}-windows-x64.zip"
    checksum_name = f"FlashDock-v{__version__}-SHA256SUMS.txt"
    with TemporaryDirectory(prefix=".build-", dir=output) as temp:
        staging = Path(temp)
        result = subprocess.run(
            [
                sys.executable, "-m", "PyInstaller", "--noconfirm",
                "--distpath", str(staging), "--workpath", str(staging / "work"),
                str(ROOT_DIR / "flashdock.spec"),
            ],
            cwd=ROOT_DIR,
        )
        if result.returncode:
            return result.returncode

        app = staging / "FlashDock_Dist"
        required = ("FlashDock.exe", "_internal/PySide6/plugins/platforms/qwindows.dll",
                    "_internal/flashdock/ui/liquid_glass_bw.qss")
        for name in required:
            if not (app / name).is_file():
                raise FileNotFoundError(f"Missing packaged runtime file: {name}")
        shutil.copy2(ROOT_DIR / "Run-FlashDock.bat", app)
        shutil.copy2(ROOT_DIR / "WINDOWS-QUICKSTART.md", app)

        archive_path = staging / archive_name
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as bundle:
            for path in sorted(app.rglob("*")):
                if path.is_file():
                    bundle.write(path, path.relative_to(app).as_posix())
        with ZipFile(archive_path) as bundle:
            bad_entry = bundle.testzip()
            if bad_entry is not None:
                raise OSError(f"ZIP integrity check failed for {bad_entry}")

        checksum = f"{sha256(archive_path)}  {archive_name}\n"
        (staging / checksum_name).write_text(checksum, encoding="ascii")
        (staging / "SHA256SUMS.txt").write_text(checksum, encoding="ascii")
        promote_outputs(staging, output, (app.name, archive_name, checksum_name, "SHA256SUMS.txt"))

    print(f"Built FlashDock v{__version__} in {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
