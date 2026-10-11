"""
Unit tests for flashdock.core.mtk (MediaTek BROM Engine & Scatter Parser).
"""

import pytest
from pathlib import Path
from flashdock.core.mtk import (
    ScatterParser,
    ScatterInfo,
    ScatterPartition,
    MTKBROMManager,
    MockMTKTransport,
    AuthBypassHandler,
    MTKFlashPipeline,
)

SAMPLE_SCATTER_V11 = """
############################################################################################################
#
#  General Setting
#
############################################################################################################
- general: MTK_PLATFORM_CFG
  info:
    - config_version: V1.1.2
      platform: MT6765
      project: k65v1_64_bsp
      storage_type: EMMC
      boot_channel: MSDC_0
      block_size: 0x20000
############################################################################################################
#
#  Layout Setting
#
############################################################################################################
- partition_index: SYS0
  partition_name: preloader
  file_name: preloader_k65v1_64_bsp.bin
  is_download: true
  type: SV5_BL_BIN
  linear_start_addr: 0x0
  physical_start_addr: 0x0
  partition_size: 0x40000
  region: EMMC_BOOT_1
  storage: HW_STORAGE_EMMC
  boundary_check: true
  is_reserved: false
  operation_type: BOOTLOADERS
  reserve: 0x00

- partition_index: SYS1
  partition_name: boot
  file_name: boot.img
  is_download: true
  type: NORMAL_ROM
  linear_start_addr: 0x40000
  physical_start_addr: 0x40000
  partition_size: 0x2000000
  region: EMMC_USER
  storage: HW_STORAGE_EMMC
  boundary_check: true
  is_reserved: false
  operation_type: UPDATE
  reserve: 0x00

- partition_index: SYS2
  partition_name: empty_part
  file_name: NONE
  is_download: false
  type: NONE
  linear_start_addr: 0x2040000
  physical_start_addr: 0x2040000
  partition_size: 0x100000
"""

SAMPLE_LEGACY_SCATTER = """
platform: MT6580
PRELOADER 0x0 0x40000 preloader.bin
BOOT 0x40000 0x1000000 boot.img
RECOVERY 0x1040000 0x1000000 recovery.img
"""


def test_parse_v11_scatter():
    info = ScatterParser.parse(SAMPLE_SCATTER_V11)
    assert info.platform == "MT6765"
    assert info.project == "k65v1_64_bsp"
    assert info.storage_type == "EMMC"
    assert info.has_preloader is True
    assert len(info.partitions) == 3

    # Check downloadable partitions
    downloadable = info.download_partitions
    assert len(downloadable) == 2
    assert downloadable[0].partition_name == "preloader"
    assert downloadable[0].file_name == "preloader_k65v1_64_bsp.bin"
    assert downloadable[0].partition_size == 0x40000
    assert downloadable[1].partition_name == "boot"
    assert downloadable[1].file_name == "boot.img"


def test_parse_legacy_scatter():
    info = ScatterParser.parse(SAMPLE_LEGACY_SCATTER)
    assert info.platform == "MT6580"
    assert len(info.partitions) == 3
    boot = info.get_partition("BOOT")
    assert boot is not None
    assert boot.file_name == "boot.img"
    assert boot.linear_start_addr == 0x40000


def test_validate_images(tmp_path: Path):
    info = ScatterParser.parse(SAMPLE_SCATTER_V11)
    # Create boot.img but not preloader
    (tmp_path / "boot.img").write_bytes(b"\x00" * 1024)

    results = ScatterParser.validate_images(info, tmp_path)
    assert results["boot"] is True
    assert results["preloader"] is False


def test_brom_manager_connect_and_probe():
    transport = MockMTKTransport(hw_code=0x0766)
    brom = MTKBROMManager(transport=transport)

    assert brom.connected is False
    assert brom.connect() is True
    assert brom.connected is True
    assert brom.hw_code == 0x0766
    assert "MT6765" in brom.hw_name

    assert brom.reboot() is True
    assert brom.connected is False


def test_auth_bypass_handler():
    transport = MockMTKTransport(hw_code=0x0766, sla_enabled=True)
    brom = MTKBROMManager(transport=transport)
    assert brom.connect() is True

    auth = AuthBypassHandler(brom)
    assert auth.bypassed is False
    assert auth.bypass_sla_daa() is True
    assert auth.bypassed is True
    assert transport.wdt_disabled is True
    assert transport.sla_enabled is False
    assert transport.daa_enabled is False


def test_mtk_flash_pipeline(tmp_path: Path):
    scatter = ScatterParser.parse(SAMPLE_SCATTER_V11)
    (tmp_path / "preloader_k65v1_64_bsp.bin").write_bytes(b"\x00" * 512)
    (tmp_path / "boot.img").write_bytes(b"\x00" * 2048)

    transport = MockMTKTransport(hw_code=0x0766)
    brom = MTKBROMManager(transport=transport)
    auth = AuthBypassHandler(brom)
    pipeline = MTKFlashPipeline(brom, auth)

    progress_events = []
    def on_prog(part, pct, size):
        progress_events.append((part, pct, size))

    pipeline.progress_callback = on_prog

    # Flash without allow_preloader: preloader should be skipped for safety
    success = pipeline.execute_flash(scatter, tmp_path, allow_preloader=False)
    assert success is True
    flashed_parts = [e[0] for e in progress_events]
    assert "boot" in flashed_parts
    assert "preloader" not in flashed_parts

    # Flash with allow_preloader
    progress_events.clear()
    success2 = pipeline.execute_flash(scatter, tmp_path, allow_preloader=True)
    assert success2 is True
    flashed_parts2 = [e[0] for e in progress_events]
    assert "preloader" in flashed_parts2
    assert "boot" in flashed_parts2
