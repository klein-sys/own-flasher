"""
Unit, Round-Trip, and Adversarial Fuzz Tests for Candidate 1:
Dynamic Partition Management (super.img Unpacker/Repacker).
"""
from __future__ import annotations

import struct
from pathlib import Path

import pytest

from flashdock.core.super_img import (
    LP_METADATA_GEOMETRY_MAGIC,
    LP_METADATA_HEADER_MAGIC,
    SPARSE_HEADER_MAGIC,
    SuperImageError,
    build_super_image,
    is_sparse_image,
    parse_sparse_header,
    parse_super_metadata,
    unsparse_to_file,
    unpack_super_partition,
)

def test_build_and_parse_raw_super_roundtrip(tmp_path: Path) -> None:
    payloads = {
        "system_a": b"ANDROID_SYSTEM_GSI_PAYLOAD_" * 400,
        "vendor_a": b"VENDOR_HAL_BINARY_BLOCK_" * 250,
        "product_a": b"PRODUCT_OVERLAY_DATA_" * 120,
    }
    raw_bytes = build_super_image(payloads, as_sparse=False)
    assert not is_sparse_image(raw_bytes)

    summary = parse_super_metadata(raw_bytes)
    assert not summary.is_sparse
    assert summary.geometry.checksum_valid is True
    assert summary.header_checksum_valid is True
    assert summary.tables_checksum_valid is True
    assert len(summary.partitions) == 3

    super_file = tmp_path / "super_raw.img"
    super_file.write_bytes(raw_bytes)

    for name, original in payloads.items():
        out_img = tmp_path / f"{name}.img"
        written = unpack_super_partition(super_file, name, out_img)
        extracted = out_img.read_bytes()
        assert written == len(extracted)
        assert extracted.startswith(original)

def test_build_and_parse_sparse_super_roundtrip(tmp_path: Path) -> None:
    payloads = {
        "system_a": b"\xAA\x55\xF0\x0F" * 2048,
        "vendor_a": b"MTK_UNISOC_QCOM_VENDOR" * 300,
    }
    sparse_bytes = build_super_image(payloads, as_sparse=True)
    assert is_sparse_image(sparse_bytes)

    s_info = parse_sparse_header(sparse_bytes)
    assert s_info.major_version == 1
    assert s_info.total_chunks == 1

    summary = parse_super_metadata(sparse_bytes)
    assert summary.is_sparse is True
    assert summary.geometry.checksum_valid is True
    assert summary.header_checksum_valid is True
    assert summary.tables_checksum_valid is True

    sparse_path = tmp_path / "super_sparse.img"
    sparse_path.write_bytes(sparse_bytes)

    # Extract directly from sparse image without pre-unsparsing
    out_sys = tmp_path / "system_a.img"
    unpack_super_partition(sparse_path, "system_a", out_sys)
    assert out_sys.read_bytes().startswith(payloads["system_a"])

    # Also test full unsparse_to_file conversion
    unsparsed_path = tmp_path / "super_unsparsed.img"
    total_unsparsed = unsparse_to_file(sparse_bytes, unsparsed_path)
    assert total_unsparsed == s_info.expanded_size
    raw_summary = parse_super_metadata(unsparsed_path.read_bytes())
    assert raw_summary.is_sparse is False
    assert len(raw_summary.partitions) == 2

def test_group_size_budget_enforcement() -> None:
    with pytest.raises(SuperImageError, match="exceed group maximum"):
        build_super_image(
            {"system_a": b"X" * 8192},
            group_max_size=4096,
        )

@pytest.mark.parametrize(
    "bad_blob",
    [
        b"",
        b"SHORT",
        struct.pack("<I", SPARSE_HEADER_MAGIC) + b"\x00" * 24,  # zero block size / bad major
        b"\x00" * 16384,  # missing LpMetadataGeometry magic
    ],
    ids=["empty", "short", "bad_sparse_hdr", "zeroed_16k"],
)
def test_adversarial_malformed_headers_rejected(bad_blob: bytes) -> None:
    with pytest.raises(SuperImageError):
        parse_super_metadata(bad_blob)

def test_malformed_extent_out_of_bounds_rejected() -> None:
    raw_bytes = bytearray(build_super_image({"system_a": b"VALID" * 200}, as_sparse=False))
    # Corrupt the extent's num_sectors (located right after the 1-entry partition table at 12288 + 128 + 52)
    ext_offset = 12288 + 128 + 52
    struct.pack_into("<Q", raw_bytes, ext_offset, 0xFFFFFFFF)  # Huge sector count
    with pytest.raises(SuperImageError, match="exceeds image size"):
        parse_super_metadata(raw_bytes)
