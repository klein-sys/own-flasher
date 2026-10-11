"""
FlashDock — scrcpy Manager & Screen Mirroring Controller.

Manages detection, downloading, verification, and launching of Genymobile scrcpy
for ultra-low latency screen mirroring, phone control, audio forwarding, and recording.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Callable, Optional
import urllib.request
import zipfile

from flashdock.constants import TOOLS_DIR

log = get_logger = logging.getLogger("flashdock.scrcpy")

# Official Genymobile scrcpy 64-bit Windows release
SCRCPY_RELEASE_URL = (
    "https://github.com/Genymobile/scrcpy/releases/download/v3.1/scrcpy-win64-v3.1.zip"
)
SCRCPY_VERSION = "v3.1"


class ScrcpyManager:
    """Manages the scrcpy binary lifecycle and process execution."""

    def __init__(self, tools_dir: Optional[Path] = None) -> None:
        self.tools_dir = tools_dir or TOOLS_DIR
        self.scrcpy_dir = self.tools_dir / "scrcpy"

    def get_executable(self) -> Optional[Path]:
        """Return the path to scrcpy.exe if installed, otherwise None."""
        # 1. Check FlashDock local tools directory
        candidates = [
            self.scrcpy_dir / "scrcpy.exe",
            self.tools_dir / "scrcpy.exe",
        ]
        # Also check subfolders if extracted with release folder name
        if self.scrcpy_dir.exists():
            for exe in self.scrcpy_dir.rglob("scrcpy.exe"):
                candidates.insert(0, exe)

        for c in candidates:
            if c.exists() and c.is_file():
                return c

        # 2. Check system PATH
        system_scrcpy = shutil.which("scrcpy")
        if system_scrcpy:
            return Path(system_scrcpy)

        return None

    def is_installed(self) -> bool:
        """Check if scrcpy executable is available."""
        return self.get_executable() is not None

    def get_version(self) -> str:
        """Query installed scrcpy version."""
        exe = self.get_executable()
        if not exe:
            return "Not Installed"
        try:
            res = subprocess.run(
                [str(exe), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            out = res.stdout + res.stderr
            lines = out.strip().splitlines()
            if lines:
                return lines[0].strip()
            return SCRCPY_VERSION
        except Exception:
            return SCRCPY_VERSION

    def download_and_install(
        self,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> tuple[bool, str]:
        """Download official scrcpy Windows bundle from GitHub and extract."""
        self.scrcpy_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.tools_dir / "scrcpy-latest.zip"

        try:
            log.info("Downloading scrcpy %s from %s...", SCRCPY_VERSION, SCRCPY_RELEASE_URL)
            req = urllib.request.Request(
                SCRCPY_RELEASE_URL,
                headers={"User-Agent": "FlashDock/1.0 (Windows)"},
            )
            with urllib.request.urlopen(req, timeout=45) as resp, open(zip_path, "wb") as out_file:
                total_size = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

            log.info("scrcpy downloaded (%d bytes). Extracting to %s...", downloaded, self.scrcpy_dir)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(self.scrcpy_dir)

            zip_path.unlink(missing_ok=True)

            # Move files up if extracted into a nested 'scrcpy-win64-vX.X' directory
            nested_dirs = [d for d in self.scrcpy_dir.iterdir() if d.is_dir() and "scrcpy" in d.name.lower()]
            if nested_dirs:
                nested = nested_dirs[0]
                for item in nested.iterdir():
                    dest = self.scrcpy_dir / item.name
                    if not dest.exists():
                        shutil.move(str(item), str(dest))

            exe = self.get_executable()
            if exe:
                return True, f"scrcpy installed successfully to {exe.parent}."
            return True, f"scrcpy extracted to {self.scrcpy_dir}."

        except Exception as exc:
            log.error("Failed to download or install scrcpy: %s", exc)
            zip_path.unlink(missing_ok=True)
            return False, f"Failed to download scrcpy: {exc}"

    def launch(
        self,
        serial: Optional[str] = None,
        stay_awake: bool = True,
        turn_screen_off: bool = False,
        audio: bool = True,
        record_path: Optional[Path] = None,
        max_size: int = 0,
        bit_rate: int = 0,
        adb_path: Optional[Path] = None,
    ) -> tuple[bool, str]:
        """Launch scrcpy process with target flags."""
        exe = self.get_executable()
        if not exe:
            return False, "scrcpy is not installed. Please download it first via FlashDock Tools."

        cmd = [str(exe)]
        if serial:
            cmd.extend(["-s", serial])
        if stay_awake:
            cmd.append("--stay-awake")
        if turn_screen_off:
            cmd.append("--turn-screen-off")
        if not audio:
            cmd.append("--no-audio")
        if max_size > 0:
            cmd.extend(["-m", str(max_size)])
        if bit_rate > 0:
            cmd.extend(["-b", f"{bit_rate}M"])
        if record_path:
            cmd.extend(["--record", str(record_path)])

        env = os.environ.copy()
        if adb_path and adb_path.exists():
            env["ADB"] = str(adb_path)
            # Add ADB folder to PATH so scrcpy finds adb.exe
            env["PATH"] = str(adb_path.parent) + os.pathsep + env.get("PATH", "")

        log.info("Launching scrcpy command: %s", " ".join(cmd))
        try:
            # Launch detached so FlashDock doesn't block while mirroring
            if sys.platform == "win32":
                subprocess.Popen(
                    cmd,
                    env=env,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            else:
                subprocess.Popen(cmd, env=env)

            return True, f"scrcpy screen mirroring started for {serial or 'device'}."
        except Exception as exc:
            log.error("Failed to launch scrcpy: %s", exc)
            return False, f"Error launching scrcpy: {exc}"
