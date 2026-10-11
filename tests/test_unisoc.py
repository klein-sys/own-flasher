"""
Unit tests for flashdock.core.unisoc (Unisoc / Spreadtrum PAC & FDL Engine).
"""

import struct
from pathlib import Path
import pytest
from flashdock.core.unisoc import (
    PACExtractor,
    PACInfo,
    PACFileEntry,
    FDLProtocolHandler,
    MockUnisocTransport,
    UnisocFlashPipeline,
    crc16_ccitt,
    BSL_CMD_CONNECT,
    BSL_REP_ACK,
)


def _build_synthetic_pac(out_path: Path) -> None:
    """Helper to create a valid minimal Unisoc PAC binary for testing."""
    ver_str = "BP_Firmware_R1.0".encode("utf-16le").ljust(48, b"\x00")
    prd_name = "SP9863A".encode("utf-16le").ljust(512, b"\x00")
    prd_ver = "Android12_V1".encode("utf-16le").ljust(500, b"\x00")

    header_size = 48 + 4 + 512 + 500 + 4 + 4  # 1072 bytes
    file_count = 3
    file_table_offset = header_size

    # Payloads
    fdl1_data = b"MOCK_FDL1_PAYLOAD_SRAM"
    fdl2_data = b"MOCK_FDL2_PAYLOAD_DRAM"
    boot_data = b"MOCK_ANDROID_BOOT_IMAGE_DATA_PADDING"

    entry_size = 4 + 512 + 512 + 500 + 20  # 1548 bytes
    payload_start = file_table_offset + (entry_size * file_count)

    fdl1_offset = payload_start
    fdl2_offset = fdl1_offset + len(fdl1_data)
    boot_offset = fdl2_offset + len(fdl2_data)

    def _make_entry(file_id: str, file_name: str, size: int, offset: int) -> bytes:
        e_size = struct.pack("<I", entry_size)
        e_id = file_id.encode("utf-16le").ljust(512, b"\x00")
        e_name = file_name.encode("utf-16le").ljust(512, b"\x00")
        e_ver = "1.0".encode("utf-16le").ljust(500, b"\x00")
        # nFileSize, nFileFlag (1=download), nCheckFlag, dwDataOffset, bCanSel (1)
        tail = struct.pack("<IIIII", size, 1, 0, offset, 1)
        return e_size + e_id + e_name + e_ver + tail

    with open(out_path, "wb") as f:
        # Header
        f.write(ver_str)
        f.write(struct.pack("<I", header_size))
        f.write(prd_name)
        f.write(prd_ver)
        f.write(struct.pack("<I", file_count))
        f.write(struct.pack("<I", file_table_offset))

        # File table
        f.write(_make_entry("FDL1", "fdl1-dl.bin", len(fdl1_data), fdl1_offset))
        f.write(_make_entry("FDL2", "fdl2-dl.bin", len(fdl2_data), fdl2_offset))
        f.write(_make_entry("BOOT", "boot.img", len(boot_data), boot_offset))

        # Payloads
        f.write(fdl1_data)
        f.write(fdl2_data)
        f.write(boot_data)


def test_crc16_ccitt():
    test_data = b"123456789"
    crc = crc16_ccitt(test_data, initial=0x0000)
    assert isinstance(crc, int)
    assert 0 <= crc <= 0xFFFF


def test_hdlc_packet_framing():
    payload = b"\x7EHello\x7DWorld\x7E"
    cmd_type = BSL_CMD_CONNECT

    # Encode with HDLC framing & escaping
    encoded = FDLProtocolHandler.encode_packet(cmd_type, payload)
    assert encoded.startswith(b"\x7E")
    assert encoded.endswith(b"\x7E")

    # Decode and verify payload integrity
    decoded_cmd, decoded_payload = FDLProtocolHandler.decode_packet(encoded)
    assert decoded_cmd == cmd_type
    assert decoded_payload == payload


def test_pac_extractor(tmp_path: Path):
    pac_file = tmp_path / "test_firmware.pac"
    _build_synthetic_pac(pac_file)

    info = PACExtractor.parse_pac(pac_file)
    assert "SP9863A" in info.product_name
    assert "Android12" in info.product_version
    assert len(info.files) == 3

    assert info.fdl1_entry is not None
    assert info.fdl1_entry.file_name == "fdl1-dl.bin"
    assert info.fdl2_entry is not None
    assert info.fdl2_entry.file_name == "fdl2-dl.bin"

    # Extract single file
    extract_dir = tmp_path / "extracted"
    out_boot = PACExtractor.extract_file(pac_file, "BOOT", extract_dir)
    assert out_boot is not None
    assert out_boot.exists()
    assert out_boot.read_bytes() == b"MOCK_ANDROID_BOOT_IMAGE_DATA_PADDING"

    # Extract all files
    all_files = PACExtractor.extract_all(pac_file, extract_dir)
    assert len(all_files) == 3
    file_names = [p.name for p in all_files]
    assert "fdl1-dl.bin" in file_names
    assert "fdl2-dl.bin" in file_names
    assert "boot.img" in file_names


def test_unisoc_flash_pipeline(tmp_path: Path):
    pac_file = tmp_path / "firmware.pac"
    _build_synthetic_pac(pac_file)
    extract_dir = tmp_path / "unpack"

    transport = MockUnisocTransport()
    pipeline = UnisocFlashPipeline(transport=transport)

    assert pipeline.connected is False
    assert pipeline.connect() is True
    assert pipeline.connected is True

    progress_events = []
    def on_prog(file_id, pct):
        progress_events.append((file_id, pct))

    success = pipeline.flash_pac(pac_file, extract_dir, progress_cb=on_prog)
    assert success is True
    assert transport.stage == 2  # Both FDL1 and FDL2 executed
    assert len(progress_events) >= 1
    assert any(e[0] == "BOOT" for e in progress_events)
