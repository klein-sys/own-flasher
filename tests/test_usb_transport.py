"""
Unit tests for FlashDock v1.5.0 Low-Level USB/Serial Hardware Transport (`usb_transport.py`).

Tests Qualcomm Sahara Hello packet parsing/building, MediaTek BROM 4-byte
echo handshakes, and Unisoc HDLC 0x7E framing & CRC-16/XMODEM verification.
"""

from __future__ import annotations

import struct
import pytest

from flashdock.tools.usb_transport import (
    MTK_BROM_HANDSHAKE_RX,
    SAHARA_CMD_HELLO_REQ,
    SAHARA_CMD_HELLO_RESP,
    SAHARA_HELLO_PACKET_SIZE,
    UNISOC_CMD_CONNECT,
    UNISOC_REP_VER,
    build_sahara_hello_response,
    crc16_xmodem,
    decode_unisoc_hdlc_frame,
    encode_unisoc_hdlc_frame,
    parse_sahara_hello,
    perform_mtk_brom_handshake,
    perform_sahara_hello_check,
    perform_unisoc_hdlc_ping,
)


class FakeSerialTransport:
    """In-memory mock transport for deterministic protocol handshake testing."""

    def __init__(self, port: str, rx_chunks: list[bytes]) -> None:
        self.port = port
        self._rx_chunks = list(rx_chunks)
        self.tx_Log: list[bytes] = []

    def __enter__(self) -> FakeSerialTransport:
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        pass

    def write(self, data: bytes) -> int:
        self.tx_Log.append(bytes(data))
        return len(data)

    def read(self, size: int) -> bytes:
        if not self._rx_chunks:
            return b""
        return self._rx_chunks.pop(0)[:size]


class TestQualcommSaharaProtocol:
    """Tests for Qualcomm EDL 9008 Sahara Hello framing."""

    def test_parse_and_build_sahara_hello(self) -> None:
        raw_hello = struct.pack(
            "<12I",
            SAHARA_CMD_HELLO_REQ,
            SAHARA_HELLO_PACKET_SIZE,
            2,  # version
            1,  # version_supported
            1024,  # max_cmd_packet_size
            0,  # mode: Image Transfer Pending
            0,
            0,
            0,
            0,
            0,
            0,
        )
        pkt = parse_sahara_hello(raw_hello)
        assert pkt.is_valid
        assert pkt.version == 2
        assert pkt.max_cmd_packet_size == 1024

        resp = build_sahara_hello_response(version=pkt.version)
        assert len(resp) == SAHARA_HELLO_PACKET_SIZE
        cmd, length = struct.unpack("<2I", resp[:8])
        assert cmd == SAHARA_CMD_HELLO_RESP
        assert length == SAHARA_HELLO_PACKET_SIZE

    def test_perform_sahara_hello_check_with_mock_transport(self) -> None:
        raw_hello = struct.pack(
            "<12I", SAHARA_CMD_HELLO_REQ, SAHARA_HELLO_PACKET_SIZE, 2, 1, 4096, 0, 0, 0, 0, 0, 0, 0
        )
        fake = FakeSerialTransport("COM9", [raw_hello])
        res = perform_sahara_hello_check("COM9", send_response=True, transport_factory=lambda _: fake)
        assert res.success is True
        assert res.protocol == "QUALCOMM_SAHARA"
        assert len(fake.tx_Log) == 1
        assert len(fake.tx_Log[0]) == 48


class TestMediaTekBromProtocol:
    """Tests for MediaTek BootROM 4-byte handshake verification."""

    def test_mtk_brom_handshake_success(self) -> None:
        chunks = [bytes([b]) for b in MTK_BROM_HANDSHAKE_RX]
        fake = FakeSerialTransport("COM4", chunks)
        res = perform_mtk_brom_handshake("COM4", transport_factory=lambda _: fake)
        assert res.success is True
        assert res.protocol == "MTK_BROM"
        assert b"".join(fake.tx_Log) == b"\xa0\x0a\x50\x05"

    def test_mtk_brom_handshake_mismatch_fails_cleanly(self) -> None:
        chunks = [b"\x5f", b"\xf5", b"\x00", b"\xfa"]
        fake = FakeSerialTransport("COM4", chunks)
        res = perform_mtk_brom_handshake("COM4", transport_factory=lambda _: fake)
        assert res.success is False
        assert "mismatch" in res.message.lower()


class TestUnisocHdlcProtocol:
    """Tests for Unisoc HDLC 0x7E framing, byte stuffing, and CRC-16/XMODEM."""

    def test_hdlc_encode_decode_with_escaped_bytes(self) -> None:
        # Payload containing 0x7E and 0x7D to test HDLC byte stuffing
        payload = b"SPRD3\x7e\x7dBOOT"
        frame = encode_unisoc_hdlc_frame(UNISOC_REP_VER, payload)
        assert frame.startswith(b"\x7e")
        assert frame.endswith(b"\x7e")

        cmd, decoded = decode_unisoc_hdlc_frame(frame)
        assert cmd == UNISOC_REP_VER
        assert decoded == payload

    def test_hdlc_corrupted_crc_raises_value_error(self) -> None:
        frame = bytearray(encode_unisoc_hdlc_frame(UNISOC_CMD_CONNECT, b"PING"))
        frame[-2] ^= 0xFF  # Flip CRC bits before trailing 0x7E
        with pytest.raises(ValueError, match="CRC-16"):
            decode_unisoc_hdlc_frame(frame)

    def test_perform_unisoc_hdlc_ping_success(self) -> None:
        ver_frame = encode_unisoc_hdlc_frame(UNISOC_REP_VER, b"SPRD3_BROM_V1.5")
        fake = FakeSerialTransport("COM12", [ver_frame])
        res = perform_unisoc_hdlc_ping("COM12", transport_factory=lambda _: fake)
        assert res.success is True
        assert res.details["version"] == "SPRD3_BROM_V1.5"
        assert fake.tx_Log == [b"\x7e"]

