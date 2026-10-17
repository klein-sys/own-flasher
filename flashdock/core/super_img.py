"""
Pure-Python Android Dynamic Partition (super.img) Inspector, Unpacker & Repacker.
Supports Android Sparse Containers (0xED26FF3A) and liblp Metadata (v10.0 - v10.2).
Zero external C-extensions.
"""
from __future__ import annotations

import hashlib
import mmap
import os
import struct
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Union

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

# --- Android Sparse Constants ---
SPARSE_HEADER_MAGIC = 0xED26FF3A
SPARSE_HEADER_FMT = "<I4H4I"  # 28 bytes
SPARSE_HEADER_SIZE = 28
CHUNK_HEADER_FMT = "<2H2I"    # 12 bytes
CHUNK_HEADER_SIZE = 12

CHUNK_TYPE_RAW = 0xCAC1
CHUNK_TYPE_FILL = 0xCAC2
CHUNK_TYPE_DONT_CARE = 0xCAC3
CHUNK_TYPE_CRC32 = 0xCAC4

# --- Android liblp Constants ---
LP_SECTOR_SIZE = 512
LP_PARTITION_RESERVED_BYTES = 4096
LP_METADATA_GEOMETRY_SIZE = 4096
LP_METADATA_GEOMETRY_MAGIC = 0x616C4467
LP_METADATA_GEOMETRY_FMT = "<2I32s3I"  # 52 bytes

LP_METADATA_HEADER_MAGIC = 0x414C5030
LP_METADATA_MAJOR_VERSION = 10
LP_METADATA_HEADER_V10_0_SIZE = 128
LP_METADATA_HEADER_V10_2_SIZE = 256

LP_TABLE_DESC_FMT = "<3I"              # 12 bytes (offset, num_entries, entry_size)
LP_PARTITION_FMT = "<36s4I"            # 52 bytes
LP_EXTENT_FMT = "<QIQI"                # 24 bytes
LP_GROUP_FMT = "<36sIQ"                # 48 bytes
LP_BLOCK_DEVICE_FMT = "<Q2IQ36sI"      # 64 bytes

LP_TARGET_TYPE_LINEAR = 0
LP_TARGET_TYPE_ZERO = 1

LP_PARTITION_ATTR_READONLY = 1 << 0
LP_PARTITION_ATTR_SLOT_SUFFIXED = 1 << 1
LP_PARTITION_ATTR_UPDATED = 1 << 2
LP_PARTITION_ATTR_DISABLED = 1 << 3

class SuperImageError(ValueError):
    """Raised when a super.img or sparse container is malformed or out of bounds."""

@dataclass(frozen=True)
class SparseChunk:
    chunk_type: int
    chunk_blocks: int
    total_bytes: int
    payload_offset: int
    payload_size: int
    output_offset: int
    output_size: int
    fill_value: int = 0

@dataclass(frozen=True)
class SparseHeaderInfo:
    major_version: int
    minor_version: int
    file_hdr_sz: int
    chunk_hdr_sz: int
    block_size: int
    total_blocks: int
    total_chunks: int
    image_checksum: int
    chunks: Tuple[SparseChunk, ...] = ()

    @property
    def expanded_size(self) -> int:
        return self.block_size * self.total_blocks

@dataclass(frozen=True)
class LpGeometry:
    metadata_max_size: int
    metadata_slot_count: int
    logical_block_size: int
    checksum_valid: bool

@dataclass(frozen=True)
class LpExtent:
    num_sectors: int
    target_type: int
    target_data: int
    target_source: int

    @property
    def byte_size(self) -> int:
        return self.num_sectors * LP_SECTOR_SIZE

    @property
    def physical_offset(self) -> int:
        return self.target_data * LP_SECTOR_SIZE

@dataclass(frozen=True)
class LpPartition:
    name: str
    attributes: int
    first_extent_index: int
    num_extents: int
    group_index: int
    group_name: str
    extents: Tuple[LpExtent, ...] = ()

    @property
    def total_size(self) -> int:
        return sum(ext.byte_size for ext in self.extents)

    @property
    def is_readonly(self) -> bool:
        return bool(self.attributes & LP_PARTITION_ATTR_READONLY)

@dataclass(frozen=True)
class LpGroup:
    name: str
    flags: int
    maximum_size: int

@dataclass(frozen=True)
class LpBlockDevice:
    first_logical_sector: int
    alignment: int
    alignment_offset: int
    size: int
    partition_name: str
    flags: int

@dataclass(frozen=True)
class SuperMetadataSummary:
    is_sparse: bool
    geometry: LpGeometry
    major_version: int
    minor_version: int
    header_checksum_valid: bool
    tables_checksum_valid: bool
    partitions: Tuple[LpPartition, ...]
    groups: Tuple[LpGroup, ...]
    block_devices: Tuple[LpBlockDevice, ...]

def _decode_cstr(raw: bytes) -> str:
    return raw.split(b"\x00", 1)[0].decode("utf-8", errors="replace")

def _encode_cstr(text: str, length: int = 36) -> bytes:
    encoded = text.encode("utf-8")[: length - 1]
    return encoded.ljust(length, b"\x00")

def is_sparse_image(buf: Union[bytes, memoryview]) -> bool:
    if len(buf) < SPARSE_HEADER_SIZE:
        return False
    (magic,) = struct.unpack_from("<I", buf, 0)
    return magic == SPARSE_HEADER_MAGIC

def parse_sparse_header(buf: Union[bytes, memoryview]) -> SparseHeaderInfo:
    """Validate and parse an Android sparse container header and all chunk descriptors."""
    buf_len = len(buf)
    if buf_len < SPARSE_HEADER_SIZE:
        raise SuperImageError("Buffer too small for Android sparse header.")

    (
        magic,
        major,
        minor,
        file_hdr_sz,
        chunk_hdr_sz,
        blk_sz,
        total_blks,
        total_chunks,
        checksum,
    ) = struct.unpack_from(SPARSE_HEADER_FMT, buf, 0)

    if magic != SPARSE_HEADER_MAGIC:
        raise SuperImageError(f"Invalid sparse magic: 0x{magic:08X}")
    if major != 1:
        raise SuperImageError(f"Unsupported sparse major version: {major}")
    if file_hdr_sz < SPARSE_HEADER_SIZE or chunk_hdr_sz < CHUNK_HEADER_SIZE:
        raise SuperImageError("Invalid sparse header or chunk header size.")
    if blk_sz == 0 or (blk_sz % 4) != 0:
        raise SuperImageError(f"Invalid sparse block size: {blk_sz}")

    cursor = file_hdr_sz
    out_offset = 0
    chunks: List[SparseChunk] = []

    for idx in range(total_chunks):
        if cursor + chunk_hdr_sz > buf_len:
            raise SuperImageError(f"Truncated sparse chunk header at index {idx}.")
        chunk_type, _res, chunk_sz, total_sz = struct.unpack_from(
            CHUNK_HEADER_FMT, buf, cursor
        )
        if total_sz < chunk_hdr_sz:
            raise SuperImageError(f"Chunk {idx} total_sz ({total_sz}) smaller than header.")
        if cursor + total_sz > buf_len:
            raise SuperImageError(f"Chunk {idx} extends past end of file.")

        payload_offset = cursor + chunk_hdr_sz
        payload_size = total_sz - chunk_hdr_sz
        out_size = chunk_sz * blk_sz
        fill_val = 0

        if chunk_type == CHUNK_TYPE_RAW:
            if payload_size != out_size:
                raise SuperImageError(
                    f"RAW chunk {idx} size mismatch: payload={payload_size}, expected={out_size}"
                )
        elif chunk_type == CHUNK_TYPE_FILL:
            if payload_size != 4:
                raise SuperImageError(f"FILL chunk {idx} must have a 4-byte payload.")
            (fill_val,) = struct.unpack_from("<I", buf, payload_offset)
        elif chunk_type == CHUNK_TYPE_DONT_CARE:
            if payload_size != 0:
                raise SuperImageError(f"DONT_CARE chunk {idx} must have 0 payload bytes.")
        elif chunk_type == CHUNK_TYPE_CRC32:
            if payload_size != 4:
                raise SuperImageError(f"CRC32 chunk {idx} must have 4 payload bytes.")
            out_size = 0
        else:
            raise SuperImageError(f"Unknown sparse chunk type: 0x{chunk_type:04X}")

        chunks.append(
            SparseChunk(
                chunk_type=chunk_type,
                chunk_blocks=chunk_sz,
                total_bytes=total_sz,
                payload_offset=payload_offset,
                payload_size=payload_size,
                output_offset=out_offset,
                output_size=out_size,
                fill_value=fill_val,
            )
        )
        out_offset += out_size
        cursor += total_sz

    expected_expanded = total_blks * blk_sz
    if out_offset != expected_expanded:
        raise SuperImageError(
            f"Sparse output block mismatch: accumulated {out_offset}B vs header {expected_expanded}B"
        )

    return SparseHeaderInfo(
        major_version=major,
        minor_version=minor,
        file_hdr_sz=file_hdr_sz,
        chunk_hdr_sz=chunk_hdr_sz,
        block_size=blk_sz,
        total_blocks=total_blks,
        total_chunks=total_chunks,
        image_checksum=checksum,
        chunks=tuple(chunks),
    )

def unsparse_to_file(
    sparse_buf: Union[bytes, memoryview],
    output_path: Union[str, Path],
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> int:
    """Convert an Android sparse buffer into a raw image file on disk."""
    info = parse_sparse_header(sparse_buf)
    total_bytes = info.expanded_size
    written = 0
    mv = memoryview(sparse_buf)

    with open(output_path, "wb") as out_f:
        out_f.truncate(total_bytes)
        for chunk in info.chunks:
            if chunk.chunk_type == CHUNK_TYPE_RAW:
                out_f.seek(chunk.output_offset)
                out_f.write(mv[chunk.payload_offset : chunk.payload_offset + chunk.payload_size])
            elif chunk.chunk_type == CHUNK_TYPE_FILL:
                out_f.seek(chunk.output_offset)
                pattern = struct.pack("<I", chunk.fill_value) * (info.block_size // 4)
                for _ in range(chunk.chunk_blocks):
                    out_f.write(pattern)
            elif chunk.chunk_type == CHUNK_TYPE_DONT_CARE:
                # File is already pre-allocated/zero-filled via truncate
                pass
            written += chunk.output_size
            if progress_cb and total_bytes > 0:
                progress_cb(written, total_bytes)

    return total_bytes

def read_logical_range_from_sparse(
    sparse_buf: Union[bytes, memoryview],
    info: SparseHeaderInfo,
    start_offset: int,
    length: int,
) -> bytes:
    """Read an arbitrary logical byte range directly from a sparse image without full unsparsing."""
    if start_offset < 0 or length < 0 or start_offset + length > info.expanded_size:
        raise SuperImageError("Logical read range exceeds expanded sparse image bounds.")
    if length == 0:
        return b""

    out = bytearray(length)
    end_offset = start_offset + length
    mv = memoryview(sparse_buf)

    for chunk in info.chunks:
        if chunk.output_size == 0:
            continue
        c_start = chunk.output_offset
        c_end = c_start + chunk.output_size
        if c_end <= start_offset:
            continue
        if c_start >= end_offset:
            break

        overlap_start = max(start_offset, c_start)
        overlap_end = min(end_offset, c_end)
        overlap_len = overlap_end - overlap_start
        dst_pos = overlap_start - start_offset
        rel_in_chunk = overlap_start - c_start

        if chunk.chunk_type == CHUNK_TYPE_RAW:
            src_pos = chunk.payload_offset + rel_in_chunk
            out[dst_pos : dst_pos + overlap_len] = mv[src_pos : src_pos + overlap_len]
        elif chunk.chunk_type == CHUNK_TYPE_FILL:
            fill_bytes = struct.pack("<I", chunk.fill_value)
            for i in range(overlap_len):
                out[dst_pos + i] = fill_bytes[(rel_in_chunk + i) & 3]
        elif chunk.chunk_type == CHUNK_TYPE_DONT_CARE:
            # bytearray is already zero-initialized
            pass

    return bytes(out)

def _locate_geometry_and_header(buf: Union[bytes, memoryview]) -> Tuple[int, int]:
    """Locate LpMetadataGeometry offset and Slot 0 LpMetadataHeader offset."""
    candidates = [LP_PARTITION_RESERVED_BYTES, 0]
    for geom_off in candidates:
        if geom_off + LP_METADATA_GEOMETRY_SIZE * 2 <= len(buf):
            (magic,) = struct.unpack_from("<I", buf, geom_off)
            if magic == LP_METADATA_GEOMETRY_MAGIC:
                return geom_off, geom_off + (LP_METADATA_GEOMETRY_SIZE * 2)
    raise SuperImageError("LpMetadataGeometry magic (0x616C4467) not found in image.")

def parse_super_metadata(buf: Union[bytes, memoryview]) -> SuperMetadataSummary:
    """
    Parse liblp metadata from either a raw super.img or an Android sparse super.img.
    Performs strict bounds and SHA-256 integrity checks.
    """
    sparse = is_sparse_image(buf)
    if sparse:
        sparse_info = parse_sparse_header(buf)
        # Read first 256 KiB of logical space (covers reserved + geometries + metadata slots)
        probe_len = min(sparse_info.expanded_size, 262144)
        logical_head = read_logical_range_from_sparse(buf, sparse_info, 0, probe_len)
        total_image_bytes = sparse_info.expanded_size
        view = memoryview(logical_head)
    else:
        total_image_bytes = len(buf)
        view = memoryview(buf)

    geom_off, hdr_off = _locate_geometry_and_header(view)
    geom_struct_size = struct.calcsize(LP_METADATA_GEOMETRY_FMT)
    if geom_off + geom_struct_size > len(view):
        raise SuperImageError("Truncated LpMetadataGeometry struct.")

    (
        g_magic,
        g_struct_sz,
        g_checksum,
        metadata_max_size,
        metadata_slot_count,
        logical_block_size,
    ) = struct.unpack_from(LP_METADATA_GEOMETRY_FMT, view, geom_off)

    if g_magic != LP_METADATA_GEOMETRY_MAGIC or g_struct_sz < geom_struct_size:
        raise SuperImageError("Corrupted LpMetadataGeometry header fields.")
    if logical_block_size == 0 or (logical_block_size % LP_SECTOR_SIZE) != 0:
        raise SuperImageError(f"Invalid LP logical_block_size: {logical_block_size}")

    # Verify Geometry SHA-256
    geom_copy = bytearray(view[geom_off : geom_off + geom_struct_size])
    geom_copy[8:40] = b"\x00" * 32
    geom_hash_ok = hashlib.sha256(geom_copy).digest() == g_checksum

    geometry = LpGeometry(
        metadata_max_size=metadata_max_size,
        metadata_slot_count=metadata_slot_count,
        logical_block_size=logical_block_size,
        checksum_valid=geom_hash_ok,
    )

    if hdr_off + LP_METADATA_HEADER_V10_0_SIZE > len(view):
        raise SuperImageError("Truncated LpMetadataHeader.")

    h_magic, h_major, h_minor, h_size = struct.unpack_from("<I2HI", view, hdr_off)
    if h_magic != LP_METADATA_HEADER_MAGIC:
        raise SuperImageError(f"Invalid LpMetadataHeader magic: 0x{h_magic:08X}")
    if h_major != LP_METADATA_MAJOR_VERSION:
        raise SuperImageError(f"Unsupported LP metadata major version: {h_major}")
    if h_size < LP_METADATA_HEADER_V10_0_SIZE or hdr_off + h_size > len(view):
        raise SuperImageError(f"Invalid LpMetadataHeader size: {h_size}")

    h_checksum = bytes(view[hdr_off + 12 : hdr_off + 44])
    tables_size = struct.unpack_from("<I", view, hdr_off + 44)[0]
    tables_checksum = bytes(view[hdr_off + 48 : hdr_off + 80])

    # Verify Header SHA-256
    hdr_copy = bytearray(view[hdr_off : hdr_off + h_size])
    hdr_copy[12:44] = b"\x00" * 32
    hdr_hash_ok = hashlib.sha256(hdr_copy).digest() == h_checksum

    tables_base = hdr_off + h_size
    if tables_base + tables_size > len(view):
        raise SuperImageError("LP descriptor tables exceed metadata buffer bounds.")

    tables_slice = view[tables_base : tables_base + tables_size]
    tables_hash_ok = hashlib.sha256(tables_slice).digest() == tables_checksum

    # Unpack the 4 table descriptors at hdr_off + 80
    part_desc = struct.unpack_from(LP_TABLE_DESC_FMT, view, hdr_off + 80)
    ext_desc = struct.unpack_from(LP_TABLE_DESC_FMT, view, hdr_off + 92)
    grp_desc = struct.unpack_from(LP_TABLE_DESC_FMT, view, hdr_off + 104)
    bdev_desc = struct.unpack_from(LP_TABLE_DESC_FMT, view, hdr_off + 116)

    def _validate_table(desc: Tuple[int, int, int], min_entry_sz: int, label: str) -> Tuple[int, int, int]:
        t_off, t_count, t_esz = desc
        if t_count == 0:
            return t_off, 0, t_esz
        if t_esz < min_entry_sz:
            raise SuperImageError(f"{label} entry size ({t_esz}) smaller than minimum ({min_entry_sz}).")
        total_t_bytes = t_count * t_esz
        if t_off < 0 or t_off + total_t_bytes > tables_size:
            raise SuperImageError(f"{label} table out of bounds inside tables region.")
        return t_off, t_count, t_esz

    p_off, p_cnt, p_esz = _validate_table(part_desc, 52, "Partitions")
    e_off, e_cnt, e_esz = _validate_table(ext_desc, 24, "Extents")
    g_off, g_cnt, g_esz = _validate_table(grp_desc, 48, "Groups")
    b_off, b_cnt, b_esz = _validate_table(bdev_desc, 64, "BlockDevices")

    # Parse Groups
    groups: List[LpGroup] = []
    for i in range(g_cnt):
        pos = tables_base + g_off + i * g_esz
        raw_name, g_flags, g_max = struct.unpack_from(LP_GROUP_FMT, view, pos)
        groups.append(LpGroup(name=_decode_cstr(raw_name), flags=g_flags, maximum_size=g_max))

    # Parse Block Devices
    block_devices: List[LpBlockDevice] = []
    for i in range(b_cnt):
        pos = tables_base + b_off + i * b_esz
        first_sec, align, align_off, b_size, raw_pname, b_flags = struct.unpack_from(
            LP_BLOCK_DEVICE_FMT, view, pos
        )
        block_devices.append(
            LpBlockDevice(
                first_logical_sector=first_sec,
                alignment=align,
                alignment_offset=align_off,
                size=b_size,
                partition_name=_decode_cstr(raw_pname),
                flags=b_flags,
            )
        )

    # Parse Extents
    extents: List[LpExtent] = []
    for i in range(e_cnt):
        pos = tables_base + e_off + i * e_esz
        num_sec, t_type, t_data, t_src = struct.unpack_from(LP_EXTENT_FMT, view, pos)
        ext = LpExtent(
            num_sectors=num_sec,
            target_type=t_type,
            target_data=t_data,
            target_source=t_src,
        )
        if t_type == LP_TARGET_TYPE_LINEAR:
            end_byte = ext.physical_offset + ext.byte_size
            if ext.physical_offset < 0 or end_byte > total_image_bytes:
                raise SuperImageError(
                    f"Extent {i} physical range [{ext.physical_offset}..{end_byte}] exceeds image size ({total_image_bytes})."
                )
        elif t_type != LP_TARGET_TYPE_ZERO:
            raise SuperImageError(f"Extent {i} has unknown target_type: {t_type}")
        extents.append(ext)

    # Parse Partitions
    partitions: List[LpPartition] = []
    for i in range(p_cnt):
        pos = tables_base + p_off + i * p_esz
        raw_name, attr, first_ext, num_ext, grp_idx = struct.unpack_from(LP_PARTITION_FMT, view, pos)
        if first_ext + num_ext > len(extents):
            raise SuperImageError(f"Partition {i} extent slice [{first_ext}+{num_ext}] out of bounds.")
        if grp_idx >= len(groups) and len(groups) > 0:
            raise SuperImageError(f"Partition {i} group_index {grp_idx} out of bounds.")
        grp_name = groups[grp_idx].name if groups else "default"
        part_extents = tuple(extents[first_ext : first_ext + num_ext])
        partitions.append(
            LpPartition(
                name=_decode_cstr(raw_name),
                attributes=attr,
                first_extent_index=first_ext,
                num_extents=num_ext,
                group_index=grp_idx,
                group_name=grp_name,
                extents=part_extents,
            )
        )

    return SuperMetadataSummary(
        is_sparse=sparse,
        geometry=geometry,
        major_version=h_major,
        minor_version=h_minor,
        header_checksum_valid=hdr_hash_ok,
        tables_checksum_valid=tables_hash_ok,
        partitions=tuple(partitions),
        groups=tuple(groups),
        block_devices=tuple(block_devices),
    )

def unpack_super_partition(
    super_path: Union[str, Path],
    partition_name: str,
    output_path: Union[str, Path],
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> int:
    """
    Extract a logical partition (e.g. 'system_a') from a raw or sparse super.img
    using zero-copy memoryviews under flash_lock_scope().
    """
    with flash_lock_scope(), open_mmap_view(super_path) as mv:
        summary = parse_super_metadata(mv)
        target = next((p for p in summary.partitions if p.name == partition_name), None)
        if target is None:
            available = ", ".join(p.name for p in summary.partitions)
            raise SuperImageError(f"Partition '{partition_name}' not found. Available: [{available}]")

        sparse_info = parse_sparse_header(mv) if summary.is_sparse else None
        total_bytes = target.total_size
        written = 0

        with open(output_path, "wb") as out_f:
            for ext in target.extents:
                b_size = ext.byte_size
                if ext.target_type == LP_TARGET_TYPE_ZERO:
                    out_f.seek(b_size, os.SEEK_CUR)
                elif summary.is_sparse and sparse_info is not None:
                    data = read_logical_range_from_sparse(mv, sparse_info, ext.physical_offset, b_size)
                    out_f.write(data)
                else:
                    start = ext.physical_offset
                    out_f.write(mv[start : start + b_size])
                written += b_size
                if progress_cb and total_bytes > 0:
                    progress_cb(written, total_bytes)

            out_f.truncate(total_bytes)

        return total_bytes

def build_super_image(
    partition_payloads: Dict[str, bytes],
    group_name: str = "qti_dynamic_partitions_a",
    group_max_size: int = 4 * 1024 * 1024 * 1024,
    block_size: int = 4096,
    as_sparse: bool = False,
) -> bytes:
    """
    Repack/build a compliant Android super.img (raw or sparse) from a dictionary of
    {partition_name: raw_bytes} with valid SHA-256 geometry, header, and table checksums.
    """
    alignment = 65536  # 64 KiB alignment for compact deterministic builds
    first_logical_sector = (LP_PARTITION_RESERVED_BYTES + LP_METADATA_GEOMETRY_SIZE * 2 + 65536 * 2) // LP_SECTOR_SIZE
    current_sector = first_logical_sector

    part_entries: List[bytes] = []
    extent_entries: List[bytes] = []
    data_chunks: List[Tuple[int, bytes]] = []

    total_group_bytes = sum(len(data) for data in partition_payloads.values())
    if group_max_size > 0 and total_group_bytes > group_max_size:
        raise SuperImageError(
            f"Combined partition payloads ({total_group_bytes}B) exceed group maximum ({group_max_size}B)."
        )

    for p_name, payload in partition_payloads.items():
        padded_len = ((len(payload) + LP_SECTOR_SIZE - 1) // LP_SECTOR_SIZE) * LP_SECTOR_SIZE
        padded_payload = payload.ljust(padded_len, b"\x00")
        num_sectors = padded_len // LP_SECTOR_SIZE

        first_ext_idx = len(extent_entries)
        num_exts = 1 if num_sectors > 0 else 0
        if num_sectors > 0:
            extent_entries.append(
                struct.pack(
                    LP_EXTENT_FMT,
                    num_sectors,
                    LP_TARGET_TYPE_LINEAR,
                    current_sector,
                    0,
                )
            )
            data_chunks.append((current_sector * LP_SECTOR_SIZE, padded_payload))
            current_sector += num_sectors
            # Align next partition to 4096B (8 sectors)
            rem = current_sector % (block_size // LP_SECTOR_SIZE)
            if rem != 0:
                current_sector += (block_size // LP_SECTOR_SIZE) - rem

        part_entries.append(
            struct.pack(
                LP_PARTITION_FMT,
                _encode_cstr(p_name, 36),
                LP_PARTITION_ATTR_READONLY | LP_PARTITION_ATTR_SLOT_SUFFIXED,
                first_ext_idx,
                num_exts,
                0,
            )
        )

    total_device_bytes = max(current_sector * LP_SECTOR_SIZE, first_logical_sector * LP_SECTOR_SIZE + block_size)

    group_entry = struct.pack(
        LP_GROUP_FMT,
        _encode_cstr(group_name, 36),
        1,
        group_max_size,
    )
    bdev_entry = struct.pack(
        LP_BLOCK_DEVICE_FMT,
        first_logical_sector,
        alignment,
        0,
        total_device_bytes,
        _encode_cstr("super", 36),
        0,
    )

    p_blob = b"".join(part_entries)
    e_blob = b"".join(extent_entries)
    g_blob = group_entry
    b_blob = bdev_entry

    p_off = 0
    e_off = p_off + len(p_blob)
    g_off = e_off + len(e_blob)
    b_off = g_off + len(g_blob)
    tables_blob = p_blob + e_blob + g_blob + b_blob
    tables_sha = hashlib.sha256(tables_blob).digest()

    header_Without_sha = bytearray(LP_METADATA_HEADER_V10_0_SIZE)
    struct.pack_into(
        "<I2HI",
        header_Without_sha,
        0,
        LP_METADATA_HEADER_MAGIC,
        LP_METADATA_MAJOR_VERSION,
        0,
        LP_METADATA_HEADER_V10_0_SIZE,
    )
    struct.pack_into("<I", header_Without_sha, 44, len(tables_blob))
    header_Without_sha[48:80] = tables_sha
    struct.pack_into(LP_TABLE_DESC_FMT, header_Without_sha, 80, p_off, len(part_entries), 52)
    struct.pack_into(LP_TABLE_DESC_FMT, header_Without_sha, 92, e_off, len(extent_entries), 24)
    struct.pack_into(LP_TABLE_DESC_FMT, header_Without_sha, 104, g_off, 1, 48)
    struct.pack_into(LP_TABLE_DESC_FMT, header_Without_sha, 116, b_off, 1, 64)

    hdr_sha = hashlib.sha256(header_Without_sha).digest()
    header_Without_sha[12:44] = hdr_sha
    slot_blob = bytes(header_Without_sha) + tables_blob

    # Build Geometry with valid SHA-256
    geom_raw = bytearray(struct.calcsize(LP_METADATA_GEOMETRY_FMT))
    struct.pack_into(
        LP_METADATA_GEOMETRY_FMT,
        geom_raw,
        0,
        LP_METADATA_GEOMETRY_MAGIC,
        len(geom_raw),
        b"\x00" * 32,
        65536,
        2,
        block_size,
    )
    geom_sha = hashlib.sha256(geom_raw).digest()
    geom_raw[8:40] = geom_sha
    geom_block = bytes(geom_raw).ljust(LP_METADATA_GEOMETRY_SIZE, b"\x00")

    raw_img = bytearray(total_device_bytes)
    raw_img[4096:8192] = geom_block
    raw_img[8192:12288] = geom_block
    raw_img[12288 : 12288 + len(slot_blob)] = slot_blob
    raw_img[12288 + 65536 : 12288 + 65536 + len(slot_blob)] = slot_blob

    for phys_off, chunk_bytes in data_chunks:
        raw_img[phys_off : phys_off + len(chunk_bytes)] = chunk_bytes

    if not as_sparse:
        return bytes(raw_img)

    # Wrap in a single-RAW-chunk Sparse Image for testing/flashing
    total_blks = total_device_bytes // block_size
    s_hdr = struct.pack(
        SPARSE_HEADER_FMT,
        SPARSE_HEADER_MAGIC,
        1,
        0,
        SPARSE_HEADER_SIZE,
        CHUNK_HEADER_SIZE,
        block_size,
        total_blks,
        1,
        0,
    )
    c_hdr = struct.pack(
        CHUNK_HEADER_FMT,
        CHUNK_TYPE_RAW,
        0,
        total_blks,
        CHUNK_HEADER_SIZE + len(raw_img),
    )
    return s_hdr + c_hdr + bytes(raw_img)
