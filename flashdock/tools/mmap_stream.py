"""
Zero-Copy Memory-Mapped (mmap) Streaming & Hardened Archive Extraction Utilities.

Provides:
  1. `MmapViewContext`: Zero-copy `mmap.mmap` + `memoryview` wrapper for high-speed
     local firmware parsing in `payload_dumper.py` and `lz4_util.py`, with automatic
     fallback to standard bytes/memoryview for empty or in-memory buffers.
  2. `safe_extract_zip` & `safe_extract_tar`: Path-traversal (Zip-Slip / Tar-Slip)
     and Python 3.12–3.14 PEP 706 `filter="data"` hardened archive extractors.
"""

from __future__ import annotations

from contextlib import contextmanager
import inspect
import mmap
from pathlib import Path
import tarfile
from typing import Iterator
import zipfile


class ArchiveSecurityError(ValueError):
    """Raised when an archive member attempts path traversal (Zip-Slip / Tar-Slip)."""


@contextmanager
def open_mmap_view(path: Path | str) -> Iterator[memoryview]:
    """
    Open a read-only zero-copy `memoryview` backed by `mmap.mmap` for `path`.
    Gracefully handles 0-byte files by yielding an empty `memoryview(b"")`.
    Deterministically closes both the memoryview and mmap handle on exit.
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found for mmap streaming: {file_path}")

    file_size = file_path.stat().st_size
    if file_size == 0:
        view = memoryview(b"")
        try:
            yield view
        finally:
            view.release()
        return

    with file_path.open("rb") as fh:
        mm = mmap.mmap(fh.fileno(), length=0, access=mmap.ACCESS_READ)
        view = memoryview(mm)
        try:
            yield view
        finally:
            try:
                view.release()
            except Exception:
                pass
            try:
                mm.close()
            except (BufferError, Exception):
                pass


def validate_safe_member_path(dest_dir: Path, member_name: str) -> Path:
    """
    Verify that `member_name` resolves strictly inside `dest_dir`.
    Raises `ArchiveSecurityError` on `../`, absolute paths, or drive-letter escapes.
    """
    clean_dest = dest_dir.resolve()
    normalized = member_name.replace("\\", "/")
    if normalized.startswith("/") or ":" in normalized.split("/")[0]:
        raise ArchiveSecurityError(
            f"Blocked absolute/drive path in archive member: {member_name!r}"
        )
    target_path = (clean_dest / normalized).resolve()
    if not target_path.is_relative_to(clean_dest):
        raise ArchiveSecurityError(
            f"Blocked path traversal (Zip-Slip) in archive member: {member_name!r}"
        )
    return target_path


def safe_extract_zip(
    zip_path: Path | str,
    dest_dir: Path | str,
    members: list[str] | None = None,
) -> list[Path]:
    """Extract a ZIP archive safely after validating every member against Zip-Slip."""
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with zipfile.ZipFile(zip_path, "r") as zf:
        target_names = members if members is not None else zf.namelist()
        for name in target_names:
            target = validate_safe_member_path(dest, name)
            info = zf.getinfo(name)
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info, "r") as src, target.open("wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                extracted.append(target)
    return extracted


def safe_extract_tar(
    tar_path: Path | str,
    dest_dir: Path | str,
) -> list[Path]:
    """
    Extract a TAR / `.tar.md5` archive safely using Python 3.12–3.14 PEP 706
    `filter="data"` and explicit Tar-Slip path validation.
    """
    dest = Path(dest_dir).resolve()
    dest.mkdir(parents=True, exist_ok=True)
    extracted: list[Path] = []

    with tarfile.open(tar_path, "r:*") as tf:
        for member in tf.getmembers():
            if member.issym() or member.islnk():
                raise ArchiveSecurityError(
                    f"Blocked symbolic/hard link in firmware tar archive: {member.name!r}"
                )
            target = validate_safe_member_path(dest, member.name)
            if member.isfile():
                extracted.append(target)

        sig = inspect.signature(tf.extractall)
        if "filter" in sig.parameters:
            tf.extractall(path=dest, filter="data")
        else:
            tf.extractall(path=dest)

    return extracted

