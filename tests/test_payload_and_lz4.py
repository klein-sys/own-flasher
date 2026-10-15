"""
Unit tests for flashdock.tools.lz4_util and flashdock.tools.payload_dumper.
"""

import io
import struct
import tarfile
import zipfile
from pathlib import Path

import pytest
from flashdock.tools.lz4_util import (
    decompress_lz4_block,
    decompress_lz4_file,
    decompress_lz4_stream,
    extract_samsung_tar,
    LZ4_FRAME_MAGIC,
    LZ4_LEGACY_MAGIC,
)
from flashdock.tools.payload_dumper import (
    PAYLOAD_MAGIC,
    PayloadDumper,
)


# ---------------------------------------------------------------------------
# LZ4 Tests
# ---------------------------------------------------------------------------

def test_lz4_block_decompression_literal():
    raw = b"FlashDock Pure Python LZ4 Engine Test String."
    token = (len(raw) << 4) if len(raw) < 15 else 0xF0
    if len(raw) < 15:
        encoded = bytes([token]) + raw
    else:
        encoded = bytes([token, len(raw) - 15]) + raw

    res = decompress_lz4_block(encoded)
    assert res == raw


def test_lz4_block_decompression_match():
    # Repeated sequence
    # 3 literals ('ABC'), offset 3, match 33 bytes -> total 36 bytes of 'ABCABC...'
    token = (3 << 4) | 15
    encoded = bytes([token]) + b"ABC" + bytes([3, 0]) + bytes([14])
    res = decompress_lz4_block(encoded)
    assert res == b"ABC" * 12


def test_samsung_tar_lz4_extraction(tmp_path: Path):
    tar_path = tmp_path / "AP_TEST.tar.md5"
    out_dir = tmp_path / "unpacked"

    # Construct synthetic tar with a .lz4 file and a plain .img
    boot_content = b"ORIGINAL_BOOT_IMAGE_KERNEL_DATA"
    token = (len(boot_content) << 4) if len(boot_content) < 15 else 0xF0
    boot_lz4_block = bytes([token, len(boot_content) - 15]) + boot_content

    # Wrap in legacy LZ4 frame
    legacy_frame = struct.pack("<I", LZ4_LEGACY_MAGIC) + struct.pack("<I", len(boot_lz4_block)) + boot_lz4_block

    vbmeta_content = b"ORIGINAL_VBMETA_PAYLOAD"

    with tarfile.open(tar_path, "w") as tar:
        ti_boot = tarfile.TarInfo("boot.img.lz4")
        ti_boot.size = len(legacy_frame)
        tar.addfile(ti_boot, io.BytesIO(legacy_frame))

        ti_vb = tarfile.TarInfo("vbmeta.img")
        ti_vb.size = len(vbmeta_content)
        tar.addfile(ti_vb, io.BytesIO(vbmeta_content))

    # Append mock MD5 trailer to emulate real Samsung firmware
    with open(tar_path, "ab") as f:
        f.write(b"0123456789abcdef0123456789abcdef")

    extracted = extract_samsung_tar(tar_path, out_dir)
    assert len(extracted) == 2

    boot_out = out_dir / "boot.img"
    assert boot_out.is_file()
    assert boot_out.read_bytes() == boot_content

    vb_out = out_dir / "vbmeta.img"
    assert vb_out.is_file()
    assert vb_out.read_bytes() == vbmeta_content


# ---------------------------------------------------------------------------
# Payload Dumper Tests
# ---------------------------------------------------------------------------

def _build_synthetic_payload(dest_file: Path, partition_name: str = "boot", data: bytes = b"PAYLOAD_KERNEL_IMAGE"):
    """Creates a valid synthetic payload.bin with 1 partition and REPLACE op."""
    # Protobuf for InstallOperation:
    # op_type=0 (REPLACE), data_offset=0, data_length=len(data)
    # dst_extents: start_block=0, num_blocks=1
    # Extent protobuf: field 1: start_block, field 2: num_blocks
    ext_bytes = bytes([(1 << 3) | 0, 0, (2 << 3) | 0, 1])
    op_bytes = bytes([
        (1 << 3) | 0, 0,  # op_type = 0
        (2 << 3) | 0, 0,  # data_offset = 0
        (3 << 3) | 0, len(data),  # data_length
        (6 << 3) | 2, len(ext_bytes),  # dst_extents
    ]) + ext_bytes

    # PartitionUpdate protobuf: field 1: name, field 6: operation
    p_name_bytes = partition_name.encode("utf-8")
    part_bytes = bytes([
        (1 << 3) | 2, len(p_name_bytes),
    ]) + p_name_bytes + bytes([
        (6 << 3) | 2, len(op_bytes),
    ]) + op_bytes

    # DeltaArchiveManifest: field 1: block_size (4096), field 5: partition
    manifest_bytes = bytes([
        (1 << 3) | 0, 0x80, 0x20,  # block_size = 4096 (varint 0x1000)
        (5 << 3) | 2, len(part_bytes),
    ]) + part_bytes

    # Payload Header:
    # Magic: CrAU (4 bytes)
    # Version: 2 (8 bytes)
    # Manifest size: len(manifest_bytes) (8 bytes)
    # Metadata sig size: 0 (4 bytes)
    header = PAYLOAD_MAGIC + struct.pack(">QQI", 2, len(manifest_bytes), 0)

    dest_file.write_bytes(header + manifest_bytes + data)


def test_payload_dumper_direct_bin(tmp_path: Path):
    payload_bin = tmp_path / "payload.bin"
    sample_kernel = b"ANDROID_BOOT_IMAGE_DATA_EXTRACTED_FROM_OTA"
    _build_synthetic_payload(payload_bin, "boot", sample_kernel)

    parts = PayloadDumper.list_partitions(payload_bin)
    assert parts == ["boot"]

    out_dir = tmp_path / "out"
    extracted = PayloadDumper.extract_partitions(payload_bin, out_dir)
    assert len(extracted) == 1
    assert extracted[0].name == "boot.img"
    assert extracted[0].read_bytes().startswith(sample_kernel)


def test_payload_dumper_inside_zip(tmp_path: Path):
    ota_zip = tmp_path / "Pixel_OTA_Update.zip"
    payload_bin = tmp_path / "payload.bin"
    sample_init = b"INIT_BOOT_IMAGE_DATA"
    _build_synthetic_payload(payload_bin, "init_boot", sample_init)

    with zipfile.ZipFile(ota_zip, "w") as z:
        z.write(payload_bin, "payload.bin")

    parts = PayloadDumper.list_partitions(ota_zip)
    assert parts == ["init_boot"]

    out_dir = tmp_path / "out_zip"
    extracted = PayloadDumper.extract_partitions(ota_zip, out_dir, target_partitions=["init_boot"])
    assert len(extracted) == 1
    assert extracted[0].name == "init_boot.img"
    assert extracted[0].read_bytes().startswith(sample_init)
