"""
Pure-Python Emergency Protocol Data Transfer Engine:
1. Qualcomm Sahara v2 (32-bit 0x03 & 64-bit 0x12) Firehose ELF Streamer
2. Unisoc (Spreadtrum) HDLC 0x7E + CRC-16/XMODEM FDL1/FDL2 SRAM/DRAM Loader
Zero external C-extensions.
"""
from __future__ import annotations

import mmap
import struct
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Optional, Protocol, Tuple, Union

try:
    from flashdock.tools.mmap_stream import open_mmap_view
except ImportError:
    @contextmanager
    def open_mmap_view(path: Union[str, Path]) -> Iterator[memoryview]:
        with open(path, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            mv = memoryview(mm)
            try:
                yield mv
            finally:
                mv.release()
                mm.close()

try:
    from flashdock.tools.runner import flash_lock_scope
except ImportError:
    @contextmanager
    def flash_lock_scope():
        yield

class SerialPortLike(Protocol):
    """Protocol matching FlashDock's Win32 ctypes serial transport and test loopbacks."""

    def read(self, size: int) -> bytes: ...
    def write(self, data: Union[bytes, memoryview]) -> int: ...

class EmergencyTransferError(RuntimeError):
    """Raised on Sahara or Unisoc FDL protocol errors, bounds violations, or aborts."""

# ============================================================================
# QUALCOMM SAHARA PROTOCOL CONSTANTS & ENGINE
# ============================================================================
SAHARA_CMD_HELLO_REQ = 0x01
SAHARA_CMD_HELLO_RSP = 0x02
SAHARA_CMD_READ_DATA = 0x03
SAHARA_CMD_END_IMAGE_TX = 0x04
SAHARA_CMD_DONE_REQ = 0x05
SAHARA_CMD_DONE_RSP = 0x06
SAHARA_CMD_RESET_REQ = 0x07
SAHARA_CMD_RESET_RSP = 0x08
SAHARA_CMD_READ_DATA_64 = 0x12

SAHARA_MODE_IMAGE_TX_PENDING = 0x00
SAHARA_STATUS_SUCCESS = 0x00
SAHARA_VERSION = 2
SAHARA_VERSION_SUPPORTED = 1

SAHARA_HELLO_FMT = "<12I"  # 48 bytes
SAHARA_HEADER_FMT = "<2I"  # 8 bytes: cmd_id, packet_len

@dataclass(frozen=True)
class SaharaTransferReport:
    image_id: int
    is_64bit: bool
    segments_streamed: int
    total_bytes_sent: int
    version: int

def _read_exact(port: SerialPortLike, length: int, abort_cb: Optional[Callable[[], bool]] = None) -> bytes:
    buf = bytearray()
    while len(buf) < length:
        if abort_cb and abort_cb():
            raise EmergencyTransferError("Transfer aborted by user.")
        chunk = port.read(length - len(buf))
        if not chunk:
            raise EmergencyTransferError(
                f"Serial timeout: expected {length} bytes, received {len(buf)} bytes."
            )
        buf.extend(chunk)
    return bytes(buf)

def build_sahara_hello_response(
    version: int = SAHARA_VERSION,
    version_min: int = SAHARA_VERSION_SUPPORTED,
    status: int = SAHARA_STATUS_SUCCESS,
    mode: int = SAHARA_MODE_IMAGE_TX_PENDING,
) -> bytes:
    """Construct a 48-byte little-endian Sahara HELLO_RSP (0x02) packet."""
    return struct.pack(
        SAHARA_HELLO_FMT,
        SAHARA_CMD_HELLO_RSP,
        48,
        version,
        version_min,
        status,
        mode,
        0, 0, 0, 0, 0, 0,
    )

def stream_sahara_firehose(
    port: SerialPortLike,
    elf_source: Union[str, Path, bytes, memoryview],
    progress_cb: Optional[Callable[[int, int], None]] = None,
    abort_cb: Optional[Callable[[], bool]] = None,
    skip_initial_hello: bool = False,
) -> SaharaTransferReport:
    """
    Execute a complete Qualcomm Sahara v2 Firehose programmer transfer over `port`.
    Supports both 32-bit (0x03) and 64-bit (0x12) Read Data requests with zero-copy slicing.
    """
    @contextmanager
    def _resolve_view(src: Union[str, Path, bytes, memoryview]) -> Iterator[memoryview]:
        if isinstance(src, (str, Path)):
            with open_mmap_view(src) as mv:
                yield mv
        else:
            yield memoryview(src)

    with flash_lock_scope(), _resolve_view(elf_source) as elf_mv:
        total_elf_size = len(elf_mv)
        if total_elf_size < 64:
            raise EmergencyTransferError("Firehose ELF image is too small (< 64 bytes).")

        device_version = SAHARA_VERSION
        if not skip_initial_hello:
            hdr = _read_exact(port, 8, abort_cb)
            cmd_id, pkt_len = struct.unpack(SAHARA_HEADER_FMT, hdr)
            if cmd_id != SAHARA_CMD_HELLO_REQ or pkt_len != 48:
                raise EmergencyTransferError(
                    f"Expected Sahara HELLO_REQ (0x01, 48B), got cmd=0x{cmd_id:02X}, len={pkt_len}"
                )
            hello_body = _read_exact(port, 40, abort_cb)
            device_version = struct.unpack_from("<I", hello_body, 0)[0]
            port.write(build_sahara_hello_response(version=device_version))

        bytes_sent = 0
        segments_count = 0
        last_image_id = 0
        used_64bit = False

        while True:
            if abort_cb and abort_cb():
                raise EmergencyTransferError("Sahara transfer aborted by user.")

            hdr = _read_exact(port, 8, abort_cb)
            cmd_id, pkt_len = struct.unpack(SAHARA_HEADER_FMT, hdr)

            if cmd_id == SAHARA_CMD_READ_DATA:
                if pkt_len != 20:
                    raise EmergencyTransferError(f"Invalid Sahara READ_DATA (0x03) length: {pkt_len}")
                body = _read_exact(port, 12, abort_cb)
                image_id, data_offset, data_length = struct.unpack("<3I", body)
            elif cmd_id == SAHARA_CMD_READ_DATA_64:
                if pkt_len != 32:
                    raise EmergencyTransferError(f"Invalid Sahara READ_DATA_64 (0x12) length: {pkt_len}")
                body = _read_exact(port, 24, abort_cb)
                image_id, data_offset, data_length = struct.unpack("<3Q", body)
                used_64bit = True
            elif cmd_id == SAHARA_CMD_END_IMAGE_TX:
                if pkt_len != 16:
                    raise EmergencyTransferError(f"Invalid Sahara END_IMAGE_TX (0x04) length: {pkt_len}")
                body = _read_exact(port, 8, abort_cb)
                image_id, status = struct.unpack("<2I", body)
                last_image_id = image_id
                if status != SAHARA_STATUS_SUCCESS:
                    raise EmergencyTransferError(
                        f"Sahara device reported END_IMAGE_TX error status: 0x{status:08X}"
                    )
                break
            else:
                raise EmergencyTransferError(f"Unexpected Sahara command ID: 0x{cmd_id:02X}")

            if data_offset < 0 or data_length < 0 or (data_offset + data_length) > total_elf_size:
                raise EmergencyTransferError(
                    f"Sahara read request out of bounds: offset={data_offset}, "
                    f"length={data_length}, elf_size={total_elf_size}"
                )

            last_image_id = image_id
            # Zero-copy slice directly from mmap memoryview
            port.write(elf_mv[data_offset : data_offset + data_length])
            bytes_sent += data_length
            segments_count += 1

            if progress_cb and total_elf_size > 0:
                progress_cb(min(bytes_sent, total_elf_size), total_elf_size)

        # Send DONE_REQ (0x05) and verify DONE_RSP (0x06)
        done_req = struct.pack(SAHARA_HEADER_FMT, SAHARA_CMD_DONE_REQ, 8)
        port.write(done_req)

        done_hdr = _read_exact(port, 8, abort_cb)
        d_cmd, d_len = struct.unpack(SAHARA_HEADER_FMT, done_hdr)
        if d_cmd != SAHARA_CMD_DONE_RSP or d_len < 12:
            raise EmergencyTransferError(
                f"Expected Sahara DONE_RSP (0x06, 12B), got cmd=0x{d_cmd:02X}, len={d_len}"
            )
        done_body = _read_exact(port, d_len - 8, abort_cb)
        (tx_status,) = struct.unpack_from("<I", done_body, 0)
        if tx_status != SAHARA_STATUS_SUCCESS:
            raise EmergencyTransferError(f"Sahara DONE_RSP failed with status: 0x{tx_status:08X}")

        if progress_cb:
            progress_cb(total_elf_size, total_elf_size)

        return SaharaTransferReport(
            image_id=last_image_id,
            is_64bit=used_64bit,
            segments_streamed=segments_count,
            total_bytes_sent=bytes_sent,
            version=device_version,
        )

# ============================================================================
# UNISOC (SPREADTRUM) HDLC 0x7E + CRC-16/XMODEM FDL LOADER ENGINE
# ============================================================================
HDLC_FLAG = 0x7E
HDLC_ESCAPE = 0x7D
HDLC_ESCAPE_XOR = 0x20

BSL_CMD_CONNECT = 0x0000
BSL_CMD_START_DATA = 0x0001
BSL_CMD_MIDST_DATA = 0x0002
BSL_CMD_END_DATA = 0x0003
BSL_CMD_EXEC_DATA = 0x0004

BSL_REP_ACK = 0x0080
BSL_REP_VER = 0x0081
BSL_REP_INVALID_CMD = 0x0082
BSL_REP_UNKNOWN_CMD = 0x0083
BSL_REP_OPERATION_FAILED = 0x0084
BSL_REP_VERIFY_ERROR = 0x0089

@dataclass(frozen=True)
class UnisocFdlReport:
    stage_name: str
    target_address: int
    total_bytes: int
    chunks_sent: int
    retries_used: int

def crc16_xmodem(data: Union[bytes, bytearray, memoryview], poly: int = 0x1021, init: int = 0x0000) -> int:
    """Compute pure-Python CRC-16/XMODEM checksum for Unisoc HDLC frames."""
    crc = init & 0xFFFF
    for byte in data:
        crc ^= (byte & 0xFF) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ poly) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc

def encode_unisoc_hdlc_frame(cmd_type: int, payload: Union[bytes, memoryview] = b"") -> bytes:
    """
    Encode a Unisoc BSL command into an HDLC 0x7E frame with Big-Endian header,
    CRC-16/XMODEM trailer, and RFC 1662 byte-stuffing (0x7E / 0x7D escaped with 0x7D ^ 0x20).
    """
    raw_body = bytearray(4 + len(payload) + 2)
    struct.pack_into(">HH", raw_body, 0, cmd_type & 0xFFFF, len(payload) & 0xFFFF)
    if payload:
        raw_body[4 : 4 + len(payload)] = payload
    crc = crc16_xmodem( memoryview(raw_body)[: 4 + len(payload)] )
    struct.pack_into(">H", raw_body, 4 + len(payload), crc)

    framed = bytearray([HDLC_FLAG])
    for b in raw_body:
        if b in (HDLC_FLAG, HDLC_ESCAPE):
            framed.append(HDLC_ESCAPE)
            framed.append(b ^ HDLC_ESCAPE_XOR)
        else:
            framed.append(b)
    framed.append(HDLC_FLAG)
    return bytes(framed)

def decode_unisoc_hdlc_frame(frame: Union[bytes, bytearray, memoryview]) -> Tuple[int, bytes]:
    """
    Unescape and verify a Unisoc HDLC 0x7E frame, returning (cmd_type, payload).
    Raises EmergencyTransferError on framing or CRC-16 mismatch.
    """
    raw = bytes(frame)
    if len(raw) < 2 or raw[0] != HDLC_FLAG or raw[-1] != HDLC_FLAG:
        raise EmergencyTransferError("Malformed Unisoc HDLC frame: missing 0x7E boundary flags.")

    inner = raw[1:-1]
    unescaped = bytearray()
    idx = 0
    while idx < len(inner):
        b = inner[idx]
        if b == HDLC_ESCAPE:
            idx += 1
            if idx >= len(inner):
                raise EmergencyTransferError("Truncated HDLC escape sequence at end of frame.")
            unescaped.append(inner[idx] ^ HDLC_ESCAPE_XOR)
        elif b == HDLC_FLAG:
            raise EmergencyTransferError("Unescaped 0x7E flag found inside HDLC frame body.")
        else:
            unescaped.append(b)
        idx += 1

    if len(unescaped) < 6:
        raise EmergencyTransferError(f"Unisoc HDLC frame too short after unescaping ({len(unescaped)}B).")

    cmd_type, payload_len = struct.unpack_from(">HH", unescaped, 0)
    if 4 + payload_len + 2 != len(unescaped):
        raise EmergencyTransferError(
            f"Unisoc HDLC payload length mismatch: header={payload_len}, actual={len(unescaped) - 6}"
        )

    expected_crc = struct.unpack_from(">H", unescaped, 4 + payload_len)[0]
    computed_crc = crc16_xmodem(memoryview(unescaped)[: 4 + payload_len])
    if expected_crc != computed_crc:
        raise EmergencyTransferError(
            f"Unisoc HDLC CRC-16 mismatch: expected=0x{expected_crc:04X}, computed=0x{computed_crc:04X}"
        )

    return cmd_type, bytes(unescaped[4 : 4 + payload_len])

def _read_unisoc_frame(port: SerialPortLike, abort_cb: Optional[Callable[[], bool]] = None) -> Tuple[int, bytes]:
    """Read one complete 0x7E...0x7E HDLC frame from `port` and decode it."""
    # Seek start flag 0x7E
    while True:
        if abort_cb and abort_cb():
            raise EmergencyTransferError("Unisoc transfer aborted by user.")
        b = port.read(1)
        if not b:
            raise EmergencyTransferError("Timeout waiting for Unisoc HDLC start flag (0x7E).")
        if b[0] == HDLC_FLAG:
            break

    frame_buf = bytearray([HDLC_FLAG])
    while True:
        if abort_cb and abort_cb():
            raise EmergencyTransferError("Unisoc transfer aborted by user.")
        b = port.read(1)
        if not b:
            raise EmergencyTransferError("Timeout waiting for Unisoc HDLC end flag (0x7E).")
        val = b[0]
        # Skip back-to-back leading 0x7E sync bytes
        if val == HDLC_FLAG and len(frame_buf) == 1:
            continue
        frame_buf.append(val)
        if val == HDLC_FLAG and len(frame_buf) > 1:
            break

    return decode_unisoc_hdlc_frame(frame_buf)

def stream_unisoc_fdl(
    port: SerialPortLike,
    fdl_source: Union[str, Path, bytes, memoryview],
    target_address: int,
    stage_name: str = "FDL1",
    chunk_size: int = 2048,
    max_retries: int = 3,
    execute_on_finish: bool = True,
    progress_cb: Optional[Callable[[int, int], None]] = None,
    abort_cb: Optional[Callable[[], bool]] = None,
) -> UnisocFdlReport:
    """
    Stream a Unisoc FDL1 (SRAM) or FDL2 (DRAM) binary over `port` using HDLC 0x7E framing:
    BSL_CMD_START_DATA (0x01) -> BSL_CMD_MIDST_DATA (0x02) -> BSL_CMD_END_DATA (0x03) -> BSL_CMD_EXEC_DATA (0x04).
    Includes automatic per-chunk retry on NAK / CRC verification error.
    """
    if chunk_size <= 0 or chunk_size > 0xFFFF:
        raise EmergencyTransferError(f"Invalid Unisoc FDL chunk_size: {chunk_size}")
    if target_address < 0 or target_address > 0xFFFFFFFF:
        raise EmergencyTransferError(f"Invalid 32-bit target_address: 0x{target_address:X}")

    @contextmanager
    def _resolve_view(src: Union[str, Path, bytes, memoryview]) -> Iterator[memoryview]:
        if isinstance(src, (str, Path)):
            with open_mmap_view(src) as mv:
                yield mv
        else:
            yield memoryview(src)

    with flash_lock_scope(), _resolve_view(fdl_source) as fdl_mv:
        total_size = len(fdl_mv)
        if total_size == 0:
            raise EmergencyTransferError(f"{stage_name} binary is empty (0 bytes).")

        # 1. BSL_CMD_START_DATA (0x0001)
        start_payload = struct.pack(">II", target_address, total_size)
        port.write(encode_unisoc_hdlc_frame(BSL_CMD_START_DATA, start_payload))
        rep_cmd, _ = _read_unisoc_frame(port, abort_cb)
        if rep_cmd != BSL_REP_ACK:
            raise EmergencyTransferError(
                f"{stage_name} START_DATA rejected by device: response=0x{rep_cmd:04X}"
            )

        # 2. BSL_CMD_MIDST_DATA (0x0002) loop with retry recovery
        offset = 0
        chunks_sent = 0
        retries_used = 0

        while offset < total_size:
            if abort_cb and abort_cb():
                raise EmergencyTransferError(f"{stage_name} transfer aborted by user.")

            end = min(offset + chunk_size, total_size)
            chunk_slice = bytes(fdl_mv[offset:end])
            frame = encode_unisoc_hdlc_frame(BSL_CMD_MIDST_DATA, chunk_slice)

            attempt = 0
            while True:
                port.write(frame)
                rep_cmd, _ = _read_unisoc_frame(port, abort_cb)
                if rep_cmd == BSL_REP_ACK:
                    break
                attempt += 1
                retries_used += 1
                if attempt > max_retries:
                    raise EmergencyTransferError(
                        f"{stage_name} MIDST_DATA failed at offset {offset} after {max_retries} retries "
                        f"(last response=0x{rep_cmd:04X})."
                    )

            offset = end
            chunks_sent += 1
            if progress_cb:
                progress_cb(offset, total_size)

        # 3. BSL_CMD_END_DATA (0x0003)
        port.write(encode_unisoc_hdlc_frame(BSL_CMD_END_DATA))
        rep_cmd, _ = _read_unisoc_frame(port, abort_cb)
        if rep_cmd != BSL_REP_ACK:
            raise EmergencyTransferError(
                f"{stage_name} END_DATA rejected by device: response=0x{rep_cmd:04X}"
            )

        # 4. BSL_CMD_EXEC_DATA (0x0004)
        if execute_on_finish:
            port.write(encode_unisoc_hdlc_frame(BSL_CMD_EXEC_DATA))
            rep_cmd, _ = _read_unisoc_frame(port, abort_cb)
            if rep_cmd != BSL_REP_ACK:
                raise EmergencyTransferError(
                    f"{stage_name} EXEC_DATA rejected by device: response=0x{rep_cmd:04X}"
                )

        return UnisocFdlReport(
            stage_name=stage_name,
            target_address=target_address,
            total_bytes=total_size,
            chunks_sent=chunks_sent,
            retries_used=retries_used,
        )
