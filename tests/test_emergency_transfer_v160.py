"""
Unit, Loopback State-Machine, and Fuzz Tests for Candidate 2:
Qualcomm Sahara (32/64-bit) & Unisoc HDLC FDL1/FDL2 Emergency Transfer Engine.
"""
from __future__ import annotations

import struct
from pathlib import Path
from typing import List

import pytest

from flashdock.core.emergency_transfer import (
    BSL_CMD_END_DATA,
    BSL_CMD_EXEC_DATA,
    BSL_CMD_MIDST_DATA,
    BSL_CMD_START_DATA,
    BSL_REP_ACK,
    BSL_REP_VERIFY_ERROR,
    EmergencyTransferError,
    SAHARA_CMD_DONE_REQ,
    SAHARA_CMD_DONE_RSP,
    SAHARA_CMD_END_IMAGE_TX,
    SAHARA_CMD_HELLO_REQ,
    SAHARA_CMD_HELLO_RSP,
    SAHARA_CMD_READ_DATA,
    SAHARA_CMD_READ_DATA_64,
    SAHARA_HELLO_FMT,
    SAHARA_STATUS_SUCCESS,
    crc16_xmodem,
    decode_unisoc_hdlc_frame,
    encode_unisoc_hdlc_frame,
    stream_sahara_firehose,
    stream_unisoc_fdl,
)

class MockSerialLoopback:
    """Deterministic in-memory serial port harness for testing Sahara & Unisoc state machines."""

    def __init__(self, rx_stream: bytes = b"") -> None:
        self._rx = bytearray(rx_stream)
        self.tx_packets: List[bytes] = []

    def queue_rx(self, data: bytes) -> None:
        self._rx.extend(data)

    def read(self, size: int) -> bytes:
        if not self._rx:
            return b""
        take = min(size, len(self._rx))
        out = bytes(self._rx[:take])
        del self._rx[:take]
        return out

    def write(self, data: bytes | memoryview) -> int:
        raw = bytes(data)
        self.tx_packets.append(raw)
        return len(raw)

def _make_sahara_hello_req() -> bytes:
    return struct.pack(SAHARA_HELLO_FMT, SAHARA_CMD_HELLO_REQ, 48, 2, 1, 0, 0, 0, 0, 0, 0, 0, 0)

def test_sahara_32bit_firehose_streaming_roundtrip(tmp_path: Path) -> None:
    elf_blob = b"\x7FELF_FIREHOSE_32BIT_SEGMENT_A_" * 64 + b"HASH_SEGMENT_B_" * 64
    elf_file = tmp_path / "prog_firehose_ddr.elf"
    elf_file.write_bytes(elf_blob)

    rx_script = b"".join([
        _make_sahara_hello_req(),
        struct.pack("<5I", SAHARA_CMD_READ_DATA, 20, 13, 0, 128),
        struct.pack("<5I", SAHARA_CMD_READ_DATA, 20, 13, 128, len(elf_blob) - 128),
        struct.pack("<4I", SAHARA_CMD_END_IMAGE_TX, 16, 13, SAHARA_STATUS_SUCCESS),
        struct.pack("<3I", SAHARA_CMD_DONE_RSP, 12, SAHARA_STATUS_SUCCESS),
    ])

    port = MockSerialLoopback(rx_script)
    progress_log = []
    report = stream_sahara_firehose(
        port,
        elf_file,
        progress_cb=lambda c, t: progress_log.append((c, t)),
    )

    assert report.is_64bit is False
    assert report.image_id == 13
    assert report.segments_streamed == 2
    assert report.total_bytes_sent == len(elf_blob)
    assert progress_log[-1] == (len(elf_blob), len(elf_blob))

    # Packet 0 = HELLO_RSP, Packet 1 & 2 = ELF slices, Packet 3 = DONE_REQ
    assert len(port.tx_packets) == 4
    assert struct.unpack_from("<I", port.tx_packets[0], 0)[0] == SAHARA_CMD_HELLO_RSP
    assert port.tx_packets[1] + port.tx_packets[2] == elf_blob
    assert struct.unpack("<2I", port.tx_packets[3]) == (SAHARA_CMD_DONE_REQ, 8)

def test_sahara_64bit_firehose_out_of_order_segments() -> None:
    elf_blob = b"\x7FELF_64_HEADER_" * 32 + b"CODE_SEG_" * 100
    rx_script = b"".join([
        _make_sahara_hello_req(),
        # Pull tail segment first, then header segment (realistic PBL ELF behavior)
        struct.pack("<2I3Q", SAHARA_CMD_READ_DATA_64, 32, 21, 256, 512),
        struct.pack("<2I3Q", SAHARA_CMD_READ_DATA_64, 32, 21, 0, 256),
        struct.pack("<4I", SAHARA_CMD_END_IMAGE_TX, 16, 21, SAHARA_STATUS_SUCCESS),
        struct.pack("<3I", SAHARA_CMD_DONE_RSP, 12, SAHARA_STATUS_SUCCESS),
    ])

    port = MockSerialLoopback(rx_script)
    report = stream_sahara_firehose(port, elf_blob)

    assert report.is_64bit is True
    assert report.image_id == 21
    assert report.segments_streamed == 2
    assert report.total_bytes_sent == 768
    assert port.tx_packets[1] == elf_blob[256:768]
    assert port.tx_packets[2] == elf_blob[0:256]

def test_sahara_rejects_out_of_bounds_read_request() -> None:
    elf_blob = b"\x7FELF_SMALL" * 10
    rx_script = b"".join([
        _make_sahara_hello_req(),
        struct.pack("<2I3Q", SAHARA_CMD_READ_DATA_64, 32, 1, 0, len(elf_blob) + 4096),
    ])
    port = MockSerialLoopback(rx_script)
    with pytest.raises(EmergencyTransferError, match="out of bounds"):
        stream_sahara_firehose(port, elf_blob)

def test_unisoc_hdlc_byte_stuffing_and_crc_roundtrip() -> None:
    # Include multiple 0x7E and 0x7D bytes in payload to exercise RFC 1662 byte stuffing
    tricky_payload = b"\x00\x7E\x7D\x7E\xFF\x7D\x5E\x7D\x5D\x42"
    framed = encode_unisoc_hdlc_frame(BSL_CMD_MIDST_DATA, tricky_payload)

    assert framed[0] == 0x7E and framed[-1] == 0x7E
    # Ensure no unescaped 0x7E exists inside the interior of the frame
    assert 0x7E not in framed[1:-1]

    cmd, decoded_payload = decode_unisoc_hdlc_frame(framed)
    assert cmd == BSL_CMD_MIDST_DATA
    assert decoded_payload == tricky_payload

def test_unisoc_hdlc_corrupted_crc_rejected() -> None:
    framed = bytearray(encode_unisoc_hdlc_frame(BSL_CMD_START_DATA, b"\x00\x00\x50\x00\x00\x00\x10\x00"))
    framed[-2] ^= 0xFF  # Flip bits inside the CRC-16 checksum
    with pytest.raises(EmergencyTransferError, match="CRC-16 mismatch"):
        decode_unisoc_hdlc_frame(framed)

def test_unisoc_fdl_streaming_with_nak_retry_recovery(tmp_path: Path) -> None:
    fdl_data = b"UNISOC_FDL1_PAYLOAD_\x7E\x7D_" * 60  # 1,380 bytes -> 2 chunks @ 1024B
    fdl_path = tmp_path / "fdl1-sign.bin"
    fdl_path.write_bytes(fdl_data)

    ack_frame = encode_unisoc_hdlc_frame(BSL_REP_ACK)
    nak_frame = encode_unisoc_hdlc_frame(BSL_REP_VERIFY_ERROR)

    # Sequence: ACK start -> NAK chunk 1 once -> ACK chunk 1 retry -> ACK chunk 2 -> ACK end -> ACK exec
    rx_script = b"".join([
        ack_frame,  # START_DATA ACK
        nak_frame,  # MIDST_DATA chunk 0 transient CRC error
        ack_frame,  # MIDST_DATA chunk 0 retry succeeds
        ack_frame,  # MIDST_DATA chunk 1 succeeds
        ack_frame,  # END_DATA ACK
        ack_frame,  # EXEC_DATA ACK
    ])

    port = MockSerialLoopback(rx_script)
    report = stream_unisoc_fdl(
        port,
        fdl_path,
        target_address=0x00005000,
        stage_name="FDL1",
        chunk_size=1024,
        max_retries=3,
    )

    assert report.stage_name == "FDL1"
    assert report.target_address == 0x00005000
    assert report.total_bytes == len(fdl_data)
    assert report.chunks_sent == 2
    assert report.retries_used == 1

    # Verify all transmitted frames decode cleanly
    decoded_cmds = [decode_unisoc_hdlc_frame(pkt)[0] for pkt in port.tx_packets]
    assert decoded_cmds == [
        BSL_CMD_START_DATA,
        BSL_CMD_MIDST_DATA,  # initial attempt
        BSL_CMD_MIDST_DATA,  # retry attempt
        BSL_CMD_MIDST_DATA,  # chunk 2
        BSL_CMD_END_DATA,
        BSL_CMD_EXEC_DATA,
    ]
