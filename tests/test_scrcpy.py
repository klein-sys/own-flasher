"""
Tests for scrcpy integration, screen mirroring manager, and dialog.
"""

from pathlib import Path
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from PySide6.QtWidgets import QApplication

from flashdock.core.device import DeviceInfo
from flashdock.tools.scrcpy import ScrcpyManager, SCRCPY_VERSION
from flashdock.ui.widgets.scrcpy_dialog import ScrcpyDialog


@pytest.fixture
def app():
    instance = QApplication.instance()
    if not instance:
        instance = QApplication([])
    return instance


def test_scrcpy_manager_not_installed(tmp_path: Path):
    mgr = ScrcpyManager(tools_dir=tmp_path)
    with patch("shutil.which", return_value=None):
        assert not mgr.is_installed()
        assert mgr.get_executable() is None
        assert mgr.get_version() == "Not Installed"


def test_scrcpy_manager_detected_local(tmp_path: Path):
    scrcpy_dir = tmp_path / "scrcpy"
    scrcpy_dir.mkdir(parents=True)
    fake_exe = scrcpy_dir / "scrcpy.exe"
    fake_exe.write_text("fake binary")

    mgr = ScrcpyManager(tools_dir=tmp_path)
    assert mgr.is_installed()
    assert mgr.get_executable() == fake_exe


def test_scrcpy_manager_launch_args(tmp_path: Path):
    scrcpy_dir = tmp_path / "scrcpy"
    scrcpy_dir.mkdir(parents=True)
    fake_exe = scrcpy_dir / "scrcpy.exe"
    fake_exe.write_text("fake binary")

    mgr = ScrcpyManager(tools_dir=tmp_path)

    with patch("subprocess.Popen") as mock_popen:
        rec_file = tmp_path / "recording.mp4"
        success, msg = mgr.launch(
            serial="TEST1234",
            stay_awake=True,
            turn_screen_off=True,
            audio=False,
            max_size=1080,
            record_path=rec_file,
        )
        assert success
        assert "TEST1234" in msg

        call_args = mock_popen.call_args[0][0]
        assert str(fake_exe) in call_args[0]
        assert "-s" in call_args and "TEST1234" in call_args
        assert "--stay-awake" in call_args
        assert "--turn-screen-off" in call_args
        assert "--no-audio" in call_args
        assert "-m" in call_args and "1080" in call_args
        assert "--record" in call_args and str(rec_file) in call_args


def test_scrcpy_dialog_ui(app, tmp_path: Path):
    scrcpy_dir = tmp_path / "scrcpy"
    scrcpy_dir.mkdir(parents=True)
    fake_exe = scrcpy_dir / "scrcpy.exe"
    fake_exe.write_text("fake binary")

    mgr = ScrcpyManager(tools_dir=tmp_path)
    dev = DeviceInfo(serial="DEV_001", brand="Google", model="Pixel 7", mode="system")

    dlg = ScrcpyDialog(manager=mgr, device=dev)
    assert dlg.windowTitle() == "🖥️ Screen Mirroring & Control (scrcpy)"
    assert dlg._launch_btn.isEnabled()
    assert not dlg._dl_btn.isVisible()
    dlg.close()
