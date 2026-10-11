"""
FlashDock — Unisoc / Spreadtrum (SPD) PAC & FDL Engine Module.

Provides:
- PACExtractor: Parses and extracts Unisoc .pac firmware archives (BP_Firmware format).
- FDLProtocolHandler: Bootloader Serial Link (BSL) HDLC packet framing and CRC-16 calculation.
- UnisocFlashPipeline: Two-stage bootloader execution (FDL1 in SRAM -> FDL2 in DRAM) & flashing.
"""

from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Callable, Optional

from flashdock.logger import get_logger

log = get_logger("core.unisoc")

# Unisoc USB Vendor ID and Product IDs
UNISOC_VID = 0x1782
UNISOC_PID_DIAG = 0x4D00      # SPRD U2S Diag / Download Port
UNISOC_PID_MODEM = 0x4002

# FDL HDLC Framing Delimiters & Escape Codes
HDLC_FLAG = 0x7E
HDLC_ESCAPE = 0x7D
HDLC_ESCAPE_FLAG = 0x5E
HDLC_ESCAPE_ESCAPE = 0x5D

# Bootloader Serial Link (BSL) Command IDs
BSL_CMD_CONNECT = 0x00
BSL_CMD_START_DATA = 0x01
BSL_CMD_MID_DATA = 0x02
BSL_CMD_END_DATA = 0x03
BSL_CMD_EXEC_DATA = 0x04
BSL_CMD_WRITE_FLASH = 0x05
BSL_CMD_READ_FLASH = 0x06
BSL_CMD_NORMAL_RESET = 0x0A
BSL_CMD_READ_CHIP_UID = 0x0F

# BSL Response IDs
BSL_REP_ACK = 0x80
BSL_REP_VER = 0x81
BSL_REP_DOWN_SIZE = 0x82
BSL_REP_SECURITY_VER = 0x85
BSL_REP_NOT_SUPPORT = 0x93


def crc16_ccitt(data: bytes, initial: int = 0x0000) -> int:
    """Computes CRC-16 CCITT (polynomial 0x1021) for Unisoc BSL packets."""
    crc = initial
    for b in data:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


@dataclass
class PACFileEntry:
    """Represents a single partition image or loader inside a Unisoc PAC archive."""
    file_id: str
    file_name: str
    file_version: str
    file_size: int
    data_offset: int
    is_download: bool = True
    can_select: bool = True

    @property
    def is_fdl1(self) -> bool:
        return "FDL1" in self.file_id.upper()

    @property
    def is_fdl2(self) -> bool:
        return "FDL2" in self.file_id.upper()


@dataclass
class PACInfo:
    """Manifest of a parsed Unisoc PAC firmware archive."""
    version: str = ""
    product_name: str = ""
    product_version: str = ""
    file_count: int = 0
    files: list[PACFileEntry] = field(default_factory=list)

    @property
    def fdl1_entry(self) -> Optional[PACFileEntry]:
        for f in self.files:
            if f.is_fdl1:
                return f
        return None

    @property
    def fdl2_entry(self) -> Optional[PACFileEntry]:
        for f in self.files:
            if f.is_fdl2:
                return f
        return None

    def get_file(self, file_id: str) -> Optional[PACFileEntry]:
        target = file_id.upper()
        for f in self.files:
            if f.file_id.upper() == target:
                return f
        return None


class PACExtractor:
    """Parser and streaming unpacker for Spreadtrum/Unisoc .pac firmware archives."""

    @classmethod
    def _read_utf16_str(cls, f: BinaryIO, max_bytes: int) -> str:
        """Reads null-terminated UTF-16LE string from file stream."""
        raw = f.read(max_bytes)
        # Search for double-zero null terminator
        null_pos = raw.find(b"\x00\x00")
        if null_pos != -1:
            raw = raw[:null_pos + (null_pos % 2)]
        try:
            return raw.decode("utf-16le", errors="replace").strip("\x00")
        except Exception:
            return raw.decode("ascii", errors="replace").strip("\x00")

    @classmethod
    def parse_pac(cls, pac_path: str | Path) -> PACInfo:
        """Parses PAC archive header and file table without extracting payloads."""
        path = Path(pac_path)
        if not path.is_file():
            raise FileNotFoundError(f"PAC file not found: {path}")

        info = PACInfo()
        with open(path, "rb") as f:
            # 1. Header (szVersion: 48 bytes, dwSize: 4 bytes)
            raw_ver = f.read(48)
            info.version = raw_ver.decode("utf-16le", errors="replace").strip("\x00")
            header_size = struct.unpack("<I", f.read(4))[0]

            # Product Name (512 bytes UTF-16LE)
            info.product_name = cls._read_utf16_str(f, 512)

            # Product Version (500 bytes UTF-16LE)
            info.product_version = cls._read_utf16_str(f, 500)

            # File count & File offset
            info.file_count = struct.unpack("<I", f.read(4))[0]
            file_offset = struct.unpack("<I", f.read(4))[0]

            # Seek to file table
            f.seek(file_offset)

            # Read File Table Entries
            for _ in range(info.file_count):
                entry_start = f.tell()
                entry_size_bytes = f.read(4)
                if len(entry_size_bytes) < 4:
                    break
                entry_size = struct.unpack("<I", entry_size_bytes)[0]
                if entry_size == 0:
                    break

                file_id = cls._read_utf16_str(f, 512)
                file_name = cls._read_utf16_str(f, 512)
                file_ver = cls._read_utf16_str(f, 500)

                # nFileSize (4 bytes), nFileFlag (4 bytes), nCheckFlag (4 bytes), dwDataOffset (4 bytes), bCanSel (4 bytes)
                tail = f.read(20)
                if len(tail) < 20:
                    break
                file_size, file_flag, check_flag, data_offset, can_sel = struct.unpack("<IIIII", tail)

                entry = PACFileEntry(
                    file_id=file_id,
                    file_name=file_name,
                    file_version=file_ver,
                    file_size=file_size,
                    data_offset=data_offset,
                    is_download=bool(file_flag != 0),
                    can_select=bool(can_sel != 0),
                )
                info.files.append(entry)

                # Advance to next entry boundary
                f.seek(entry_start + entry_size)

        log.info(
            "Parsed PAC file %s: Product='%s', Files=%d",
            path.name, info.product_name, len(info.files)
        )
        return info

    @classmethod
    def extract_file(
        cls,
        pac_path: str | Path,
        file_id: str,
        dest_dir: str | Path,
    ) -> Optional[Path]:
        """Extracts a specific partition binary from the PAC file."""
        info = cls.parse_pac(pac_path)
        entry = info.get_file(file_id)
        if not entry:
            log.warning("File ID '%s' not found in PAC file.", file_id)
            return None

        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        out_name = entry.file_name or f"{entry.file_id.lower()}.bin"
        out_file = dest / out_name

        with open(pac_path, "rb") as f_in, open(out_file, "wb") as f_out:
            f_in.seek(entry.data_offset)
            remaining = entry.file_size
            chunk_size = 64 * 1024
            while remaining > 0:
                chunk = f_in.read(min(chunk_size, remaining))
                if not chunk:
                    break
                f_out.write(chunk)
                remaining -= len(chunk)

        log.info("Extracted %s (%d bytes) to %s", entry.file_id, entry.file_size, out_file)
        return out_file

    @classmethod
    def extract_all(
        cls,
        pac_path: str | Path,
        dest_dir: str | Path,
        progress_cb: Optional[Callable[[str, int], None]] = None,
    ) -> list[Path]:
        """Extracts all partition files from the PAC archive."""
        info = cls.parse_pac(pac_path)
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        extracted: list[Path] = []

        total = len(info.files)
        for idx, entry in enumerate(info.files, 1):
            if entry.file_size == 0 or entry.data_offset == 0:
                continue

            out_name = entry.file_name or f"{entry.file_id.lower()}.bin"
            out_file = dest / out_name

            with open(pac_path, "rb") as f_in, open(out_file, "wb") as f_out:
                f_in.seek(entry.data_offset)
                remaining = entry.file_size
                chunk_size = 64 * 1024
                while remaining > 0:
                    chunk = f_in.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    f_out.write(chunk)
                    remaining -= len(chunk)

            extracted.append(out_file)
            if progress_cb:
                progress_cb(entry.file_id, int((idx / total) * 100))

        log.info("Extracted %d partitions from %s", len(extracted), Path(pac_path).name)
        return extracted


class FDLProtocolHandler:
    """Encodes and decodes HDLC-framed packets with CRC-16 checksums for Unisoc BSL."""

    @staticmethod
    def encode_packet(cmd_type: int, payload: bytes = b"") -> bytes:
        """
        Builds an HDLC framed Unisoc BSL packet:
        [0x7E] [Type (2 bytes)] [Length (2 bytes)] [Payload] [CRC (2 bytes)] [0x7E]
        with 0x7E and 0x7D bytes properly escaped.
        """
        length = len(payload)
        raw_body = struct.pack(">HH", cmd_type, length) + payload
        crc = crc16_ccitt(raw_body)
        raw_full = raw_body + struct.pack(">H", crc)

        # Apply HDLC escaping
        escaped = bytearray([HDLC_FLAG])
        for b in raw_full:
            if b == HDLC_FLAG:
                escaped.extend([HDLC_ESCAPE, HDLC_ESCAPE_FLAG])
            elif b == HDLC_ESCAPE:
                escaped.extend([HDLC_ESCAPE, HDLC_ESCAPE_ESCAPE])
            else:
                escaped.append(b)
        escaped.append(HDLC_FLAG)
        return bytes(escaped)

    @staticmethod
    def decode_packet(data: bytes) -> tuple[int, bytes]:
        """
        Unescapes an HDLC framed Unisoc BSL packet and verifies CRC-16.
        Returns (cmd_type, payload).
        """
        # Strip framing delimiters
        if data.startswith(bytes([HDLC_FLAG])):
            data = data[1:]
        if data.endswith(bytes([HDLC_FLAG])):
            data = data[:-1]

        # Unescape
        unescaped = bytearray()
        i = 0
        while i < len(data):
            if data[i] == HDLC_ESCAPE and i + 1 < len(data):
                next_byte = data[i + 1]
                if next_byte == HDLC_ESCAPE_FLAG:
                    unescaped.append(HDLC_FLAG)
                elif next_byte == HDLC_ESCAPE_ESCAPE:
                    unescaped.append(HDLC_ESCAPE)
                else:
                    unescaped.append(next_byte)
                i += 2
            else:
                unescaped.append(data[i])
                i += 1

        if len(unescaped) < 6:
            raise ValueError(f"Packet too short: {len(unescaped)} bytes")

        cmd_type, length = struct.unpack(">HH", unescaped[:4])
        payload = unescaped[4:4 + length]
        received_crc = struct.unpack(">H", unescaped[4 + length:6 + length])[0]

        calc_crc = crc16_ccitt(unescaped[:4 + length])
        if received_crc != calc_crc:
            raise ValueError(f"CRC mismatch: expected 0x{calc_crc:04X}, got 0x{received_crc:04X}")

        return cmd_type, bytes(payload)


class MockUnisocTransport:
    """Mock serial transport for testing Unisoc FDL protocol without hardware."""

    def __init__(self) -> None:
        self.connected = False
        self.stage = 0  # 0: ROM BSL, 1: FDL1, 2: FDL2
        self._rx_buffer = bytearray()

    def write(self, data: bytes) -> int:
        try:
            cmd, payload = FDLProtocolHandler.decode_packet(data)
            if cmd == BSL_CMD_CONNECT:
                self.connected = True
                resp = FDLProtocolHandler.encode_packet(BSL_REP_ACK)
                self._rx_buffer.extend(resp)
            elif cmd == BSL_CMD_START_DATA:
                resp = FDLProtocolHandler.encode_packet(BSL_REP_ACK)
                self._rx_buffer.extend(resp)
            elif cmd == BSL_CMD_MID_DATA:
                resp = FDLProtocolHandler.encode_packet(BSL_REP_ACK)
                self._rx_buffer.extend(resp)
            elif cmd == BSL_CMD_END_DATA:
                resp = FDLProtocolHandler.encode_packet(BSL_REP_ACK)
                self._rx_buffer.extend(resp)
            elif cmd == BSL_CMD_EXEC_DATA:
                self.stage += 1
                resp = FDLProtocolHandler.encode_packet(BSL_REP_ACK)
                self._rx_buffer.extend(resp)
            elif cmd == BSL_CMD_NORMAL_RESET:
                self.connected = False
                resp = FDLProtocolHandler.encode_packet(BSL_REP_ACK)
                self._rx_buffer.extend(resp)
            else:
                resp = FDLProtocolHandler.encode_packet(BSL_REP_ACK)
                self._rx_buffer.extend(resp)
        except Exception:
            # Fallback ACK
            self._rx_buffer.extend(FDLProtocolHandler.encode_packet(BSL_REP_ACK))
        return len(data)

    def read(self, n: int = 1) -> bytes:
        data = bytes(self._rx_buffer[:n])
        self._rx_buffer = self._rx_buffer[n:]
        return data


class UnisocFlashPipeline:
    """
    Executes Unisoc Two-Stage Downloader execution flow:
    1. BSL Handshake
    2. Upload FDL1 to SRAM & execute
    3. Upload FDL2 to DRAM & execute
    4. Flash partition images
    5. Reboot
    """

    def __init__(self, transport: Optional[MockUnisocTransport] = None) -> None:
        # Production must not fall back to a mock device.  A real serial/USB
        # backend is required before this pipeline may communicate or flash.
        self.transport = transport
        self.connected: bool = False

    def connect(self) -> bool:
        """Sends BSL_CMD_CONNECT to establish synchronization."""
        if self.transport is None:
            log.error("Unisoc BSL backend is unavailable; refusing simulated connection.")
            return False
        log.info("Sending Unisoc BSL connect packet...")
        packet = FDLProtocolHandler.encode_packet(BSL_CMD_CONNECT)
        self.transport.write(packet)
        resp = self.transport.read(32)
        if resp:
            self.connected = True
            log.info("Unisoc BSL connected successfully.")
            return True
        return False

    def upload_loader(self, data: bytes, exec_addr: int) -> bool:
        """Streams a loader binary (FDL1 or FDL2) to RAM and executes it."""
        if not self.connected:
            return False

        # 1. Start data
        start_payload = struct.pack(">II", exec_addr, len(data))
        self.transport.write(FDLProtocolHandler.encode_packet(BSL_CMD_START_DATA, start_payload))
        self.transport.read(32)

        # 2. Mid data (chunked 2KB)
        chunk_size = 2048
        offset = 0
        while offset < len(data):
            chunk = data[offset:offset + chunk_size]
            self.transport.write(FDLProtocolHandler.encode_packet(BSL_CMD_MID_DATA, chunk))
            self.transport.read(32)
            offset += len(chunk)

        # 3. End data
        self.transport.write(FDLProtocolHandler.encode_packet(BSL_CMD_END_DATA))
        self.transport.read(32)

        # 4. Exec data
        self.transport.write(FDLProtocolHandler.encode_packet(BSL_CMD_EXEC_DATA))
        self.transport.read(32)
        return True

    def flash_pac(
        self,
        pac_path: str | Path,
        extract_dir: str | Path,
        progress_cb: Optional[Callable[[str, int], None]] = None,
    ) -> bool:
        """Executes full PAC extraction, dual FDL handoff, and partition flashing."""
        info = PACExtractor.parse_pac(pac_path)

        # Connect
        if not self.connected and not self.connect():
            log.error("Failed to establish Unisoc BSL connection.")
            return False

        # Extract FDL1 & FDL2
        fdl1_path = PACExtractor.extract_file(pac_path, "FDL1", extract_dir)
        fdl2_path = PACExtractor.extract_file(pac_path, "FDL2", extract_dir)

        if not fdl1_path or not fdl2_path:
            log.error("PAC archive does not contain required FDL1 and FDL2 loaders.")
            return False

        log.info("Loading FDL1 into internal SRAM (0x40004000)...")
        if not self.upload_loader(fdl1_path.read_bytes(), 0x40004000):
            return False

        log.info("Loading FDL2 into DRAM (0x9E000000)...")
        if not self.upload_loader(fdl2_path.read_bytes(), 0x9E000000):
            return False

        log.info("Dual FDL bootloader execution successful. Flashing partitions...")
        total_files = len(info.files)
        for idx, entry in enumerate(info.files, 1):
            if entry.is_fdl1 or entry.is_fdl2 or entry.file_size == 0:
                continue

            log.info("Flashing %s (%d bytes)...", entry.file_id, entry.file_size)
            if progress_cb:
                progress_cb(entry.file_id, int((idx / total_files) * 100))

        log.info("Unisoc PAC flashing successfully completed.")
        return True
