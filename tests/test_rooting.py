"""
Unit tests — Rooting Engine.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from flashdock.core.device import DeviceInfo
from flashdock.core.rooting import RootingEngine, ROOT_PACKAGES
from flashdock.tools.adb import ADB
from flashdock.tools.fastboot import Fastboot
from flashdock.tools.runner import CommandResult


class TestRootCompatibility:
    def test_target_partition_legacy_android(self):
        device = DeviceInfo(android_version="11", sdk_version="30")
        assert RootingEngine.determine_target_partition(device) == "boot"

    def test_target_partition_android_12(self):
        device = DeviceInfo(android_version="12", sdk_version="31")
        assert RootingEngine.determine_target_partition(device) == "boot"

    def test_target_partition_android_13_init_boot(self):
        device = DeviceInfo(android_version="13", sdk_version="33")
        assert RootingEngine.determine_target_partition(device) == "init_boot"

    def test_target_partition_android_14_init_boot(self):
        device = DeviceInfo(android_version="14", sdk_version="34")
        assert RootingEngine.determine_target_partition(device) == "init_boot"

    def test_gki_kernel_recommends_kernelsu(self):
        device = DeviceInfo(
            android_version="13",
            sdk_version="33",
            kernel_version="5.10.157-android12-9-g39184",
            bootloader_state="unlocked",
        )
        report = RootingEngine.analyze_device(device)
        assert report.recommended_solution == "kernelsu"
        assert report.target_partition == "init_boot"
        ksu = next(s for s in report.solutions if s.solution_id == "kernelsu")
        assert ksu.status == "recommended"

    def test_legacy_kernel_marks_kernelsu_unsupported(self):
        device = DeviceInfo(
            android_version="10",
            sdk_version="29",
            kernel_version="4.19.110-perf",
            bootloader_state="unlocked",
        )
        report = RootingEngine.analyze_device(device)
        assert report.recommended_solution == "magisk"
        ksu = next(s for s in report.solutions if s.solution_id == "kernelsu")
        assert ksu.status == "unsupported"

    def test_locked_bootloader_warns(self):
        device = DeviceInfo(
            android_version="13",
            bootloader_state="locked",
        )
        report = RootingEngine.analyze_device(device)
        assert report.bootloader_unlocked is False
        assert any("LOCKED" in w for w in report.overall_warnings)


class TestPatchingPipeline:
    def test_prepare_patch_missing_file_fails(self, tmp_path: Path):
        engine = RootingEngine()
        device = DeviceInfo(serial="DEV1")
        ok, path, msg = engine.prepare_patch(
            stock_image_path=tmp_path / "missing_boot.img",
            solution_id="magisk",
            device=device,
            output_dir=tmp_path / "out",
        )
        assert ok is False
        assert "not found" in msg

    def test_prepare_patch_fails_closed_without_verified_patcher(self, tmp_path: Path):
        engine = RootingEngine()
        device = DeviceInfo(serial="DEV1", android_version="14", sdk_version="34")

        stock_file = tmp_path / "init_boot.img"
        stock_file.write_bytes(b"ORIGINAL_STOCK_INIT_BOOT_KERNEL")

        out_dir = tmp_path / "out"
        ok, patched_path, msg = engine.prepare_patch(
            stock_image_path=stock_file,
            solution_id="magisk",
            device=device,
            output_dir=out_dir,
            dry_run=False,
        )
        assert ok is False
        assert patched_path == ""
        assert "Automatic boot-image patching is unavailable" in msg


class TestFlashingAndVerification:
    def test_flash_patched_image(self, tmp_path: Path):
        engine = RootingEngine()
        mock_fb = MagicMock(spec=Fastboot)
        mock_fb.flash.return_value = CommandResult(
            command=["fastboot", "flash", "init_boot", "patched.img"],
            return_code=0,
            stdout="OKAY",
            stderr="",
            duration_ms=40,
        )

        test_img = tmp_path / "patched.img"
        test_img.write_text("kernel")

        res = engine.flash_patched_image(
            patched_image_path=test_img,
            target_partition="init_boot",
            fastboot=mock_fb,
            serial="SERIAL1",
        )
        assert res.success is True
        mock_fb.flash.assert_called_once()

    def test_verify_root_no_su(self):
        mock_adb = MagicMock(spec=ADB)
        mock_adb.shell.return_value = CommandResult(
            command=["adb", "shell", "which", "su"],
            return_code=1,
            stdout="",
            stderr="su: not found",
            duration_ms=10,
        )
        ok, msg = RootingEngine.verify_root(mock_adb, serial="S1")
        assert ok is False
        assert "not detected" in msg

    def test_verify_root_active(self):
        mock_adb = MagicMock(spec=ADB)

        def shell_side_effect(cmd, **kwargs):
            if "which su" in cmd:
                return CommandResult(["adb", "shell"], 0, "/system/bin/su\n", "", 10)
            if "su -c id" in cmd:
                return CommandResult(["adb", "shell"], 0, "uid=0(root) gid=0(root)\n", "", 10)
            if "su -v" in cmd:
                return CommandResult(["adb", "shell"], 0, "27.0:MAGISK\n", "", 10)
            return CommandResult(["adb", "shell"], 1, "", "", 10)

        mock_adb.shell.side_effect = shell_side_effect

        ok, msg = RootingEngine.verify_root(mock_adb, serial="S1")
        assert ok is True
        assert "Active root confirmed" in msg
        assert "uid=0(root)" in msg

    def test_unroot_pipeline(self, tmp_path: Path):
        engine = RootingEngine()
        mock_fb = MagicMock(spec=Fastboot)
        mock_adb = MagicMock(spec=ADB)
        mock_fb.flash.return_value = CommandResult(
            command=["fastboot", "flash", "boot", "boot.img"],
            return_code=0,
            stdout="OKAY",
            stderr="",
            duration_ms=40,
        )

        stock_file = tmp_path / "stock_boot.img"
        stock_file.write_text("clean_kernel")

        ok, msg = engine.unroot_device(
            stock_boot_path=stock_file,
            target_partition="boot",
            fastboot=mock_fb,
            adb=mock_adb,
            serial="S1",
        )
        assert ok is True
        mock_fb.flash.assert_called_once()
        assert mock_adb.uninstall.call_count >= 1


class TestRootSolutionsExtended:
    def test_all_standard_solutions_present(self):
        device = DeviceInfo(
            android_version="13",
            sdk_version="33",
            kernel_version="5.10.150",
            bootloader_state="unlocked",
        )
        report = RootingEngine.analyze_device(device)
        sol_ids = [s.solution_id for s in report.solutions]

        # Verify all built-in and extended community solutions
        assert "magisk" in sol_ids
        assert "magisk_alpha" in sol_ids
        assert "kitsune" in sol_ids
        assert "magisk_canary" in sol_ids
        assert "kernelsu" in sol_ids
        assert "kernelsu_next" in sol_ids
        assert "apatch" in sol_ids
        assert "sukisu" in sol_ids

    def test_root_download_urls_coverage(self):
        from flashdock.core.rooting import ROOT_DOWNLOAD_URLS
        for sol_id in ("magisk", "magisk_alpha", "kitsune", "magisk_canary", "kernelsu", "kernelsu_next", "apatch", "sukisu"):
            assert sol_id in ROOT_DOWNLOAD_URLS
            assert ROOT_DOWNLOAD_URLS[sol_id].startswith("http")

    def test_custom_solution_creation_and_discovery(self, tmp_path: Path, monkeypatch):
        from flashdock import constants
        test_root_apps = tmp_path / "root_apps"
        test_root_apps.mkdir()
        monkeypatch.setattr(constants, "ROOT_APPS_DIR", test_root_apps)
        import flashdock.core.rooting as rooting_mod
        monkeypatch.setattr(rooting_mod, "ROOT_APPS_DIR", test_root_apps)

        # Create dummy apk
        dummy_apk = tmp_path / "MyRootCustom_v1.apk"
        dummy_apk.write_bytes(b"FAKE_APK_CONTENT")

        # Create custom solution
        sol = RootingEngine.create_custom_solution(dummy_apk, target_partition="boot")
        assert "custom_" in sol.solution_id
        assert "MyRootCustom" in sol.name
        assert (test_root_apps / "MyRootCustom_v1.apk").is_file()

        # Discover stored apps
        stored = RootingEngine.discover_stored_root_apps()
        assert len(stored) == 1
        assert stored[0]["filename"] == "MyRootCustom_v1.apk"

        # Find local apk for solution
        found = RootingEngine.find_local_apk_for_solution("myrootcustom")
        assert found is not None
        assert found.name == "MyRootCustom_v1.apk"

        # Delete custom root apk
        deleted = RootingEngine.delete_custom_root_apk("MyRootCustom_v1.apk")
        assert deleted is True
        assert len(RootingEngine.discover_stored_root_apps()) == 0
