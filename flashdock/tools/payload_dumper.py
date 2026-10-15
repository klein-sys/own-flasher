"""
FlashDock — Android OTA payload.bin Streaming Extractor.

Supports:
- Parsing Android Delta/Full OTA payload.bin files
- Direct extraction from OTA ZIP archives without extracting payload.bin first
- Extracting individual partitions (boot, init_boot, vbmeta, recovery, system, vendor) in seconds
- Decompressing REPLACE (raw), REPLACE_BZ (bzip2), and REPLACE_XZ (lzma) operation payloads
"""

from __future__ import annotations

import bz2
import io
import lzma
import os
import struct
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Callable, Optional

from flashdock.logger import get_logger

log = get_logger("tools.payload_dumper")

PAYLOAD_MAGIC = b"CrAU"


# ---------------------------------------------------------------------------
# Minimal Pure-Python Protobuf Decoder
# ---------------------------------------------------------------------------

def _read_varint(stream: BinaryIO) -> int:
    val = 0
    shift = 0
    while True:
        b = stream.read(1)
        if not b:
            raise EOFError("Unexpected EOF while reading varint")
        byte = b[0]
        val |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            break
        shift += 7
    return val


def _parse_protobuf(data: bytes) -> list[tuple[int, int, bytes | int]]:
    """Returns list of (field_num, wire_type, raw_value)."""
    stream = io.BytesIO(data)
    fields = []
    while True:
        b = stream.read(1)
        if not b:
            break
        key = b[0]
        field_num = key >> 3
        wire_type = key & 0x07
        if wire_type == 0:  # Varint
            val = _read_varint(stream)
        elif wire_type == 1:  # 64-bit fixed
            val = struct.unpack("<Q", stream.read(8))[0]
        elif wire_type == 2:  # Length-delimited
            length = _read_varint(stream)
            val = stream.read(length)
        elif wire_type == 5:  # 32-bit fixed
            val = struct.unpack("<I", stream.read(4))[0]
        else:
            break
        fields.append((field_num, wire_type, val))
    return fields


@dataclass
class Extent:
    start_block: int = 0
    num_blocks: int = 0


@dataclass
class InstallOperation:
    op_type: int = 0  # 0: REPLACE, 1: REPLACE_BZ, 8: REPLACE_XZ
    data_offset: int = 0
    data_length: int = 0
    dst_extents: list[Extent] = field(default_factory=list)


@dataclass
class PartitionInfo:
    name: str = ""
    operations: list[InstallOperation] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Payload Dumper Engine
# ---------------------------------------------------------------------------

class PayloadDumper:
    """Streaming Android OTA payload.bin partition extractor."""

    @classmethod
    def _parse_operation(cls, raw_bytes: bytes) -> InstallOperation:
        op = InstallOperation()
        fields = _parse_protobuf(raw_bytes)
        for f_num, w_type, val in fields:
            if f_num == 1 and isinstance(val, int):
                op.op_type = val
            elif f_num == 2 and isinstance(val, int):
                op.data_offset = val
            elif f_num == 3 and isinstance(val, int):
                op.data_length = val
            elif f_num == 6 and isinstance(val, bytes):
                # Submessage Extent
                ext_fields = _parse_protobuf(val)
                ext = Extent()
                for ef_num, _, ef_val in ext_fields:
                    if ef_num == 1 and isinstance(ef_val, int):
                        ext.start_block = ef_val
                    elif ef_num == 2 and isinstance(ef_val, int):
                        ext.num_blocks = ef_val
                op.dst_extents.append(ext)
        return op

    @classmethod
    def _parse_partition(cls, raw_bytes: bytes) -> PartitionInfo:
        part = PartitionInfo()
        fields = _parse_protobuf(raw_bytes)
        for f_num, w_type, val in fields:
            if f_num == 1 and isinstance(val, bytes):
                part.name = val.decode("utf-8", errors="replace").strip("\x00")
            elif f_num == 6 and isinstance(val, bytes):
                part.operations.append(cls._parse_operation(val))
        return part

    @classmethod
    def parse_manifest(
        cls,
        stream: BinaryIO,
    ) -> tuple[int, int, list[PartitionInfo]]:
        """
        Parses payload.bin header and returns:
        (block_size, data_offset_base, list_of_partitions).
        """
        magic = stream.read(4)
        if magic != PAYLOAD_MAGIC:
            raise ValueError(f"Invalid payload.bin magic: expected 'CrAU', got {magic!r}")

        version = struct.unpack(">Q", stream.read(8))[0]
        manifest_size = struct.unpack(">Q", stream.read(8))[0]

        meta_sig_size = 0
        if version >= 2:
            meta_sig_size = struct.unpack(">I", stream.read(4))[0]

        manifest_raw = stream.read(manifest_size)
        data_offset_base = stream.tell() + meta_sig_size

        # Parse Manifest
        block_size = 4096
        partitions: list[PartitionInfo] = []

        manifest_fields = _parse_protobuf(manifest_raw)
        for f_num, w_type, val in manifest_fields:
            if f_num == 1 and isinstance(val, int):
                block_size = val
            elif f_num == 5 and isinstance(val, bytes):
                part = cls._parse_partition(val)
                if part.name:
                    partitions.append(part)

        log.info("Parsed payload.bin: %d partitions found, block_size=%d", len(partitions), block_size)
        return block_size, data_offset_base, partitions

    @classmethod
    def list_partitions(cls, payload_source: Path | str) -> list[str]:
        """Returns the list of partition names inside payload.bin or OTA zip."""
        path = Path(payload_source)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")

        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as z:
                payload_entry = next((n for n in z.namelist() if n.lower().endswith("payload.bin")), None)
                if not payload_entry:
                    return []
                with z.open(payload_entry) as f:
                    _, _, partitions = cls.parse_manifest(f)
                    return [p.name for p in partitions]

        with open(path, "rb") as f:
            _, _, partitions = cls.parse_manifest(f)
            return [p.name for p in partitions]

    @classmethod
    def extract_partitions(
        cls,
        payload_source: Path | str,
        dest_dir: Path | str,
        target_partitions: Optional[list[str]] = None,
        progress_cb: Optional[Callable[[str, int], None]] = None,
    ) -> list[Path]:
        """
        Extracts selected partitions from payload.bin into dest_dir as .img files.
        If target_partitions is None or empty, extracts all partitions.
        """
        path = Path(payload_source)
        if not path.is_file():
            raise FileNotFoundError(f"Source file not found: {path}")

        out_dir = Path(dest_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        extracted: list[Path] = []

        # Target lower-case set
        targets = [t.lower().replace(".img", "") for t in target_partitions] if target_partitions else None

        # Check if source is a ZIP file containing payload.bin
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path, "r") as z:
                payload_entry = next((n for n in z.namelist() if n.lower().endswith("payload.bin")), None)
                if not payload_entry:
                    log.warning("No payload.bin found inside OTA zip archive %s", path.name)
                    return []
                # For streaming seek, extract payload.bin to temp directory if needed, or open stream
                with z.open(payload_entry) as f_in:
                    block_size, data_base, all_parts = cls.parse_manifest(f_in)

                # Extract partition operations using zip seek
                selected = [p for p in all_parts if not targets or p.name.lower() in targets]
                for idx, part in enumerate(selected, 1):
                    out_img = out_dir / f"{part.name}.img"
                    with z.open(payload_entry) as f_in, open(out_img, "wb") as f_out:
                        for op in part.operations:
                            f_in.seek(data_base + op.data_offset)
                            raw_chunk = f_in.read(op.data_length)
                            data = cls._decompress_op_data(op.op_type, raw_chunk)

                            for ext in op.dst_extents:
                                f_out.seek(ext.start_block * block_size)
                                write_len = min(len(data), ext.num_blocks * block_size)
                                f_out.write(data[:write_len])
                                data = data[write_len:]

                    extracted.append(out_img)
                    log.info("Extracted %s -> %s (%d bytes)", part.name, out_img.name, out_img.stat().st_size)
                    if progress_cb:
                        progress_cb(part.name, int((idx / len(selected)) * 100))

            return extracted

        # Direct payload.bin file
        with open(path, "rb") as f_in:
            block_size, data_base, all_parts = cls.parse_manifest(f_in)
            selected = [p for p in all_parts if not targets or p.name.lower() in targets]

            for idx, part in enumerate(selected, 1):
                out_img = out_dir / f"{part.name}.img"
                with open(out_img, "wb") as f_out:
                    for op in part.operations:
                        f_in.seek(data_base + op.data_offset)
                        raw_chunk = f_in.read(op.data_length)
                        data = cls._decompress_op_data(op.op_type, raw_chunk)

                        for ext in op.dst_extents:
                            f_out.seek(ext.start_block * block_size)
                            write_len = min(len(data), ext.num_blocks * block_size)
                            f_out.write(data[:write_len])
                            data = data[write_len:]

                extracted.append(out_img)
                log.info("Extracted %s -> %s (%d bytes)", part.name, out_img.name, out_img.stat().st_size)
                if progress_cb:
                    progress_cb(part.name, int((idx / len(selected)) * 100))

        return extracted

    @staticmethod
    def _decompress_op_data(op_type: int, raw_bytes: bytes) -> bytes:
        """Decompresses operation chunk according to op_type."""
        if op_type == 0:  # REPLACE (Raw uncompressed)
            return raw_bytes
        elif op_type == 1:  # REPLACE_BZ (bzip2)
            try:
                return bz2.decompress(raw_bytes)
            except Exception as e:
                log.warning("bzip2 decompress error: %s", e)
                return raw_bytes
        elif op_type == 8:  # REPLACE_XZ (lzma/xz)
            try:
                return lzma.decompress(raw_bytes)
            except Exception as e:
                log.warning("lzma decompress error: %s", e)
                return raw_bytes
        return raw_bytes
