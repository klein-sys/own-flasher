"""
FlashDock — Pure-Python LZ4 Decompressor & Samsung Firmware Extractor.

Supports:
- LZ4 Standard Frame decompression (Magic 0x184D2204)
- LZ4 Legacy Frame decompression (Magic 0x184C2102)
- LZ4 Raw Block decompression
- Samsung AP / BL / CP / CSC *.tar.md5 and *.tar firmware extraction
- Automatic decompression of .img.lz4 partitions to clean .img files
"""

from __future__ import annotations

import io
import os
import struct
import tarfile
from pathlib import Path
from typing import BinaryIO, Callable, Optional

from flashdock.logger import get_logger

log = get_logger("tools.lz4_util")

LZ4_FRAME_MAGIC = 0x184D2204
LZ4_LEGACY_MAGIC = 0x184C2102


def decompress_lz4_block(src: bytes) -> bytes:
    """
    Decompresses a raw LZ4 block in pure Python without external C libraries.
    """
    dst = bytearray()
    src_len = len(src)
    i = 0

    while i < src_len:
        token = src[i]
        i += 1

        # 1. Literal length
        lit_len = token >> 4
        if lit_len == 15:
            while i < src_len and src[i] == 255:
                lit_len += 255
                i += 1
            if i < src_len:
                lit_len += src[i]
                i += 1

        if i + lit_len > src_len:
            # Reached boundary or truncated
            dst.extend(src[i:src_len])
            break

        dst.extend(src[i:i + lit_len])
        i += lit_len

        if i >= src_len:
            break

        # 2. Match offset (16-bit little endian)
        if i + 2 > src_len:
            break
        offset = src[i] | (src[i + 1] << 8)
        i += 2

        if offset == 0:
            raise ValueError("LZ4 match offset cannot be zero")
        if offset > len(dst):
            raise ValueError(f"LZ4 match offset {offset} exceeds output buffer size {len(dst)}")

        # 3. Match length
        match_len = (token & 0x0F) + 4
        if match_len == 19:
            while i < src_len and src[i] == 255:
                match_len += 255
                i += 1
            if i < src_len:
                match_len += src[i]
                i += 1

        # Copy matching sequence byte-by-byte to handle overlapping copies
        for _ in range(match_len):
            dst.append(dst[-offset])

    return bytes(dst)


def decompress_lz4_stream(
    in_stream: BinaryIO,
    out_stream: BinaryIO,
    progress_cb: Optional[Callable[[int], None]] = None,
) -> int:
    """
    Decompresses an LZ4 framed stream into an output stream.
    Returns total bytes written.
    """
    magic_bytes = in_stream.read(4)
    if len(magic_bytes) < 4:
        return 0

    magic = struct.unpack("<I", magic_bytes)[0]
    total_written = 0

    if magic == LZ4_FRAME_MAGIC:
        # Standard LZ4 Frame
        flg_bytes = in_stream.read(2)
        if len(flg_bytes) < 2:
            raise EOFError("Truncated LZ4 frame header")
        flg, bd = flg_bytes[0], flg_bytes[1]

        # Optional content size (8 bytes)
        if flg & 0x08:
            if len(in_stream.read(8)) < 8:
                raise EOFError("Truncated LZ4 content size")
        # Optional dict ID (4 bytes)
        if flg & 0x01:
            if len(in_stream.read(4)) < 4:
                raise EOFError("Truncated LZ4 dict ID")
        # Header checksum (1 byte)
        if len(in_stream.read(1)) < 1:
            raise EOFError("Truncated LZ4 header checksum")

        # Decompress data blocks
        while True:
            size_raw = in_stream.read(4)
            if len(size_raw) == 0:
                break
            if len(size_raw) < 4:
                raise EOFError("Truncated LZ4 block size")
            block_size = struct.unpack("<I", size_raw)[0]
            if block_size == 0:
                # EndMark reached
                break

            is_uncompressed = bool(block_size & 0x80000000)
            block_size &= 0x7FFFFFFF

            block_data = in_stream.read(block_size)
            if len(block_data) < block_size:
                raise EOFError("Truncated LZ4 block data")

            if is_uncompressed:
                out_stream.write(block_data)
                total_written += len(block_data)
            else:
                decompressed = decompress_lz4_block(block_data)
                out_stream.write(decompressed)
                total_written += len(decompressed)

            # Block checksum
            if flg & 0x10:
                if len(in_stream.read(4)) < 4:
                    raise EOFError("Truncated LZ4 block checksum")

            if progress_cb:
                progress_cb(total_written)

    elif magic == LZ4_LEGACY_MAGIC:
        # Legacy LZ4 Frame
        while True:
            size_raw = in_stream.read(4)
            if len(size_raw) < 4:
                break
            block_size = struct.unpack("<I", size_raw)[0]
            if block_size == 0:
                break
            block_data = in_stream.read(block_size)
            if not block_data:
                break
            decompressed = decompress_lz4_block(block_data)
            out_stream.write(decompressed)
            total_written += len(decompressed)
            if progress_cb:
                progress_cb(total_written)

    else:
        # Not a recognized LZ4 frame magic: attempt direct raw block decompression
        in_stream.seek(0)
        raw_data = in_stream.read()
        decompressed = decompress_lz4_block(raw_data)
        out_stream.write(decompressed)
        total_written = len(decompressed)

    return total_written


def decompress_lz4_file(
    src_path: Path | str,
    dst_path: Optional[Path | str] = None,
) -> Path:
    """
    Decompresses an .lz4 file to its uncompressed output file.
    If dst_path is not specified, strips .lz4 suffix.
    """
    src = Path(src_path)
    if not src.is_file():
        raise FileNotFoundError(f"LZ4 file not found: {src}")

    if dst_path:
        dst = Path(dst_path)
    else:
        out_name = src.name[:-4] if src.name.lower().endswith(".lz4") else f"{src.name}.out"
        dst = src.parent / out_name

    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(src, "rb") as f_in, open(dst, "wb") as f_out:
        decompress_lz4_stream(f_in, f_out)

    log.info("Decompressed %s -> %s (%d bytes)", src.name, dst.name, dst.stat().st_size)
    return dst


def extract_samsung_tar(
    tar_path: Path | str,
    dest_dir: Path | str,
    target_partitions: Optional[list[str]] = None,
    progress_cb: Optional[Callable[[str, int], None]] = None,
) -> list[Path]:
    """
    Extracts and automatically decompresses Samsung firmware tar archives
    (e.g. AP_*.tar.md5, BL_*.tar.md5).
    Converts *.img.lz4 entries directly into clean *.img partitions.
    """
    tar_p = Path(tar_path)
    if not tar_p.is_file():
        raise FileNotFoundError(f"Samsung tar file not found: {tar_p}")

    out_dir = Path(dest_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    # Open tar (tarfile ignores appended md5 checksum footer cleanly)
    with tarfile.open(tar_p, "r:*") as tar:
        members = tar.getmembers()
        total_members = len(members)

        for idx, member in enumerate(members, 1):
            name = member.name
            clean_stem = name.split(".")[0].lower()

            if target_partitions:
                targets_lower = [t.lower() for t in target_partitions]
                if clean_stem not in targets_lower and name.lower() not in targets_lower:
                    continue

            f_in = tar.extractfile(member)
            if not f_in:
                continue

            if name.lower().endswith(".lz4"):
                out_name = name[:-4]
                out_file = out_dir / out_name
                with open(out_file, "wb") as f_out:
                    decompress_lz4_stream(f_in, f_out)
                extracted.append(out_file)
                log.info("Extracted & decompressed %s -> %s", name, out_file.name)
            else:
                out_file = out_dir / name
                with open(out_file, "wb") as f_out:
                    while chunk := f_in.read(128 * 1024):
                        f_out.write(chunk)
                extracted.append(out_file)
                log.info("Extracted %s", name)

            if progress_cb:
                pct = int((idx / max(1, total_members)) * 100)
                progress_cb(name, pct)

    return extracted

def decompress_lz4_frame(data: bytes | BinaryIO) -> bytes:
    """Decompress an LZ4 framed byte sequence or stream into raw bytes."""
    if isinstance(data, (bytes, bytearray, memoryview)):
        in_stream = io.BytesIO(bytes(data))
    else:
        in_stream = data
    out_stream = io.BytesIO()
    decompress_lz4_stream(in_stream, out_stream)
    return out_stream.getvalue()


class LZ4Util:
    """Namespace providing static methods for LZ4 block, frame, and file decompression."""

    @staticmethod
    def decompress_block(src: bytes, uncompressed_size: int | None = None) -> bytes:
        res = decompress_lz4_block(src)
        if uncompressed_size is not None and len(res) > uncompressed_size:
            return res[:uncompressed_size]
        return res

    @staticmethod
    def decompress_frame(src: bytes | BinaryIO) -> bytes:
        return decompress_lz4_frame(src)

    @staticmethod
    def decompress_file(src_path: Path | str, dst_path: Path | str | None = None) -> Path:
        return decompress_lz4_file(src_path, dst_path)

    @staticmethod
    def decompress_stream(
        in_stream: BinaryIO,
        out_stream: BinaryIO,
        progress_cb: Optional[Callable[[int], None]] = None,
    ) -> int:
        return decompress_lz4_stream(in_stream, out_stream, progress_cb)


# ============================================================================
# v1.5.0 Zero-Copy mmap Streaming Extension
# ============================================================================
from flashdock.tools.mmap_stream import open_mmap_view as _open_mmap_view


def decompress_file_mmap(
    src_path: Path | str,
    dst_path: Path | str | None = None,
) -> Path:
    """Zero-copy mmap-backed LZ4 frame decompressor for local firmware files."""
    src = Path(src_path)
    dst = Path(dst_path) if dst_path is not None else src.with_suffix("")
    with _open_mmap_view(src) as view:
        raw_out = LZ4Util.decompress_frame(view) if hasattr(LZ4Util, "decompress_frame") else decompress_frame(view)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(raw_out)
    return dst
