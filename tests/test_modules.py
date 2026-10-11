"""
Unit tests — Module Flasher & Bootloop Protection Engine.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock
import zipfile
import pytest

from flashdock.core.modules import ModuleInfo, ModuleInspectionResult, ModuleManager
from flashdock.tools.adb import ADB
from flashdock.tools.runner import CommandResult


class TestModuleParsing:
    def test_from_prop_text(self):
        prop_text = (
            "id=playintegrityfix\n"
            "name=Play Integrity Fix\n"
            "version=v15.9.9\n"
            "versionCode=15990\n"
            "author=chiteroman\n"
            "description=Fix Play Integrity verdicts on unlocked devices.\n"
        )
        mod = ModuleInfo.from_prop_text(prop_text, enabled=True)
        assert mod.id == "playintegrityfix"
        assert mod.name == "Play Integrity Fix"
        assert mod.version == "v15.9.9"
        assert mod.version_code == 15990
        assert mod.author == "chiteroman"
        assert mod.enabled is True

    def test_from_prop_text_fallback_defaults(self):
        mod = ModuleInfo.from_prop_text("id=simple_mod", enabled=False)
        assert mod.id == "simple_mod"
        assert mod.name == "simple_mod"
        assert mod.version == "1.0"
        assert mod.version_code == 0
        assert mod.author == "Unknown"
        assert mod.enabled is False


class TestModuleInspection:
    def test_inspect_valid_module_zip(self, tmp_path: Path):
        zip_path = tmp_path / "valid_mod.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr(
                "module.prop",
                "id=test_mod\nname=Test Module\nversion=1.0\nversionCode=100\nauthor=Tester\ndescription=A test module\n"
            )
            zf.writestr("service.sh", "echo 'starting service'")

        res = ModuleManager.inspect_module_zip(zip_path)
        assert res.is_valid_module is True
        assert res.module_info is not None
        assert res.module_info.id == "test_mod"
        assert res.module_info.has_service_sh is True
        assert res.file_count == 2

    def test_inspect_zip_with_system_and_post_fs_data(self, tmp_path: Path):
        zip_path = tmp_path / "risky_mod.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("module.prop", "id=risky\nname=Risky\n")
            zf.writestr("post-fs-data.sh", "#!/system/bin/sh")
            zf.writestr("system/etc/hosts", "127.0.0.1 localhost")

        res = ModuleManager.inspect_module_zip(zip_path)
        assert res.is_valid_module is True
        assert res.module_info.has_system_files is True
        assert res.module_info.has_post_fs_data is True
        assert any("post-fs-data" in w for w in res.warnings)
        assert any("system" in w for w in res.warnings)

    def test_inspect_missing_module_prop_fails(self, tmp_path: Path):
        zip_path = tmp_path / "not_a_module.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("some_file.txt", "hello")

        res = ModuleManager.inspect_module_zip(zip_path)
        assert res.is_valid_module is False
        assert any("module.prop" in w for w in res.warnings)

    def test_inspect_nonexistent_file(self, tmp_path: Path):
        res = ModuleManager.inspect_module_zip(tmp_path / "ghost.zip")
        assert res.is_valid_module is False
        assert any("not found" in w.lower() for w in res.warnings)


class TestModuleOperations:
    def test_list_installed_modules(self):
        mock_adb = MagicMock(spec=ADB)
        mock_adb.available = True
        mock_adb.shell.return_value = CommandResult(
            command=["adb", "shell"],
            return_code=0,
            stdout=(
                "---START---\n"
                "path=/data/adb/modules/zygisk_next\n"
                "disabled=0\n"
                "id=zygisk_next\n"
                "name=Zygisk Next\n"
                "version=1.0.5\n"
                "versionCode=105\n"
                "author=Dr-TSNG\n"
                "description=Standalone Zygisk implementation\n"
                "---END---\n"
                "---START---\n"
                "path=/data/adb/modules/shamiko\n"
                "disabled=1\n"
                "id=shamiko\n"
                "name=Shamiko\n"
                "version=v1.0.1\n"
                "versionCode=315\n"
                "author=LSPosed Devs\n"
                "description=Root hiding module\n"
                "---END---\n"
            ),
            stderr="",
            duration_ms=20,
        )

        modules = ModuleManager.list_installed_modules(mock_adb, serial="S1")
        assert len(modules) == 2

        m1 = next(m for m in modules if m.id == "zygisk_next")
        assert m1.enabled is True
        assert m1.name == "Zygisk Next"

        m2 = next(m for m in modules if m.id == "shamiko")
        assert m2.enabled is False
        assert m2.name == "Shamiko"

    def test_install_module_dry_run(self, tmp_path: Path):
        mgr = ModuleManager()
        mock_adb = MagicMock(spec=ADB)
        test_zip = tmp_path / "module.zip"
        test_zip.write_text("dummy")

        ok, msg = mgr.install_module(test_zip, mock_adb, root_framework="magisk", dry_run=True)
        assert ok is True
        assert "[DRY RUN]" in msg

    def test_enable_module(self):
        mock_adb = MagicMock(spec=ADB)
        mock_adb.shell.return_value = CommandResult(["adb", "shell"], 0, "", "", 10)
        ok, msg = ModuleManager.enable_module("my_module", mock_adb, serial="S1")
        assert ok is True
        assert "enabled" in msg
        mock_adb.shell.assert_called_once()
        assert "rm -f /data/adb/modules/my_module/disable" in mock_adb.shell.call_args[0][0]

    def test_disable_module(self):
        mock_adb = MagicMock(spec=ADB)
        mock_adb.shell.return_value = CommandResult(["adb", "shell"], 0, "", "", 10)
        ok, msg = ModuleManager.disable_module("my_module", mock_adb, serial="S1")
        assert ok is True
        assert "disabled" in msg
        mock_adb.shell.assert_called_once()
        assert "touch /data/adb/modules/my_module/disable" in mock_adb.shell.call_args[0][0]

    def test_remove_module(self):
        mock_adb = MagicMock(spec=ADB)
        mock_adb.shell.return_value = CommandResult(["adb", "shell"], 0, "", "", 10)
        ok, msg = ModuleManager.remove_module("my_module", mock_adb, serial="S1")
        assert ok is True
        assert "removed" in msg
        assert "rm -rf /data/adb/modules/my_module" in mock_adb.shell.call_args[0][0]

    def test_emergency_disable_all_modules(self):
        mock_adb = MagicMock(spec=ADB)
        mock_adb.shell.return_value = CommandResult(["adb", "shell"], 0, "", "", 10)
        ok, msg = ModuleManager.emergency_disable_all_modules(mock_adb, serial="S1")
        assert ok is True
        assert "emergency-disabled" in msg
        assert ".disable_all" in mock_adb.shell.call_args[0][0]

    def test_reboot_safe_mode(self):
        mock_adb = MagicMock(spec=ADB)
        mock_adb.reboot_safemode.return_value = CommandResult(["adb", "reboot"], 0, "", "", 10)
        res = ModuleManager.reboot_safe_mode(mock_adb, serial="S1")
        assert res.success is True
        mock_adb.reboot_safemode.assert_called_once_with(serial="S1")
