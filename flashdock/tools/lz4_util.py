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
            break

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
            if offset <= len(dst):
                dst.append(dst[-offset])
            else:
                dst.append(0)

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
            return 0
        flg, bd = flg_bytes[0], flg_bytes[1]

        # Optional content size (8 bytes)
        if flg & 0x08:
            in_stream.read(8)
        # Optional dict ID (4 bytes)
        if flg & 0x01:
            in_stream.read(4)
        # Header checksum (1 byte)
        in_stream.read(1)

        # Decompress data blocks
        while True:
            size_raw = in_stream.read(4)
            if len(size_raw) < 4:
                break
            block_size = struct.unpack("<I", size_raw)[0]
            if block_size == 0:
                # EndMark reached
                break

            is_uncompressed = bool(block_size & 0x80000000)
            block_size &= 0x7FFFFFFF

            block_data = in_stream.read(block_size)
            if len(block_data) < block_size:
                break

            if is_uncompressed:
                out_stream.write(block_data)
                total_written += len(block_data)
            else:
                decompressed = decompress_lz4_block(block_data)
                out_stream.write(decompressed)
                total_written += len(decompressed)

            # Block checksum
            if flg & 0x10:
                in_stream.read(4)

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
