"""
FlashDock — Pure-Python APK Pre-Flight Verifier & Atomic Staging.

Validates APK archive integrity and signature presence before invoking
``adb install``, preventing ``INSTALL_PARSE_FAILED_NO_CERTIFICATES``
errors caused by:

1. In-place ZIP/manifest touching in %TEMP% (pipeline trap).
2. Unflushed Windows temp file handles (atomic I/O trap).
3. Corrupted or un-re-signed source APKs.

Uses 100% pure Python standard library — zero external C-extensions.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from flashdock.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APK_SIG_BLOCK_MAGIC = b"APK Sig Block 42"
EOCD_SIGNATURE = b"PK\x05\x06"


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ApkPreFlightResult:
    """Outcome of the APK pre-flight integrity and signature check."""

    ok: bool
    has_v2_v3_sig_block: bool
    has_v1_jar_sig: bool
    sha256: str
    error_reason: str = ""


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def compute_sha256(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 digest of a file in streaming 1 MB chunks."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _detect_apk_sig_block_v2_v3(file_path: Path) -> bool:
    """
    Pure-Python inspection for APK Signature Scheme v2/v3 ('APK Sig Block 42').

    The APK Signing Block is located immediately preceding the ZIP Central
    Directory. Its last 16 bytes must equal the magic string ``APK Sig Block 42``.
    """
    try:
        file_size = file_path.stat().st_size
        if file_size < 22:
            return False

        with open(file_path, "rb") as f:
            # Read last 64 KB to locate End of Central Directory (EOCD)
            read_size = min(file_size, 65557)
            f.seek(file_size - read_size)
            tail = f.read(read_size)

            eocd_pos = tail.rfind(EOCD_SIGNATURE)
            if eocd_pos == -1 or eocd_pos + 20 > len(tail):
                return False

            # Central directory offset is at byte offset 16..20 of EOCD (uint32 LE)
            cd_offset = struct.unpack("<I", tail[eocd_pos + 16 : eocd_pos + 20])[0]
            if cd_offset < 16 or cd_offset >= file_size:
                return False

            # The last 16 bytes of the APK Signing Block (right before cd_offset)
            # must equal 'APK Sig Block 42'
            f.seek(cd_offset - 16)
            magic = f.read(16)
            return magic == APK_SIG_BLOCK_MAGIC
    except OSError:
        return False


def verify_apk_preflight(apk_path: str | Path) -> ApkPreFlightResult:
    """
    Validate APK archive integrity and signature presence before calling ``adb install``.

    Checks performed (in order):
    1. File existence and non-zero size.
    2. Valid ZIP archive structure (``zipfile.is_zipfile``).
    3. Presence of ``AndroidManifest.xml`` inside the package.
    4. CRC-32 integrity across all internal ZIP entries (``zf.testzip()``).
    5. v1 JAR signature (``META-INF/*.RSA|.DSA|.EC``).
    6. v2/v3 APK Signing Block magic header (``APK Sig Block 42``).
    7. SHA-256 file digest computation for staging parity.
    """
    path = Path(apk_path)
    if not path.is_file() or path.stat().st_size == 0:
        return ApkPreFlightResult(
            ok=False,
            has_v2_v3_sig_block=False,
            has_v1_jar_sig=False,
            sha256="",
            error_reason=f"APK file is missing or empty: {path}",
        )

    if not zipfile.is_zipfile(path):
        return ApkPreFlightResult(
            ok=False,
            has_v2_v3_sig_block=False,
            has_v1_jar_sig=False,
            sha256="",
            error_reason="File is not a valid ZIP/APK archive (truncated or corrupted download).",
        )

    try:
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
            if "AndroidManifest.xml" not in names:
                return ApkPreFlightResult(
                    ok=False,
                    has_v2_v3_sig_block=False,
                    has_v1_jar_sig=False,
                    sha256="",
                    error_reason="Missing AndroidManifest.xml inside package.",
                )

            # Pure-Python CRC-32 check across all internal entries
            bad_entry = zf.testzip()
            if bad_entry is not None:
                return ApkPreFlightResult(
                    ok=False,
                    has_v2_v3_sig_block=False,
                    has_v1_jar_sig=False,
                    sha256="",
                    error_reason=f"Corrupted entry inside APK failed CRC check: {bad_entry}",
                )

            has_v1 = any(
                n.startswith("META-INF/") and n.upper().endswith((".RSA", ".DSA", ".EC"))
                for n in names
            )
    except zipfile.BadZipFile as exc:
        return ApkPreFlightResult(
            ok=False,
            has_v2_v3_sig_block=False,
            has_v1_jar_sig=False,
            sha256="",
            error_reason=f"Corrupted ZIP structure: {exc}",
        )

    has_v2_v3 = _detect_apk_sig_block_v2_v3(path)
    file_hash = compute_sha256(path)

    if not (has_v2_v3 or has_v1):
        return ApkPreFlightResult(
            ok=False,
            has_v2_v3_sig_block=False,
            has_v1_jar_sig=False,
            sha256=file_hash,
            error_reason="Unsigned APK detected (no v1 META-INF or v2/v3 APK Signing Block found).",
        )

    log.info(
        "APK pre-flight passed: %s (v1=%s, v2/v3=%s, sha256=%s…)",
        path.name,
        has_v1,
        has_v2_v3,
        file_hash[:12],
    )
    return ApkPreFlightResult(
        ok=True,
        has_v2_v3_sig_block=has_v2_v3,
        has_v1_jar_sig=has_v1,
        sha256=file_hash,
    )


def stage_apk_atomically(src_apk: str | Path) -> Path:
    """
    Stage APK to %TEMP% only if the original path contains non-ASCII characters
    that break older ``adb.exe`` builds.

    Enforces ``os.fsync()`` + SHA-256 parity check to prevent unflushed
    Windows temp file handle corruption (the root cause of
    ``INSTALL_PARSE_FAILED_NO_CERTIFICATES`` when staging via %TEMP%).

    Returns the path to use for ``adb install`` — either the original
    (fast path) or the verified staged copy.
    """
    src = Path(src_apk).resolve()

    # Fast path: if path is pure ASCII and not inside a temp bundle, use directly
    try:
        str(src).encode("ascii")
        return src
    except UnicodeEncodeError:
        pass

    log.info("Staging APK with non-ASCII path to %%TEMP%%: %s", src.name)
    src_hash = compute_sha256(src)
    fd, tmp_name = tempfile.mkstemp(prefix="flashdock_stage_", suffix=".apk")
    tmp_path = Path(tmp_name)

    try:
        with os.fdopen(fd, "wb") as dst_file, open(src, "rb") as src_file:
            shutil.copyfileobj(src_file, dst_file, length=1024 * 1024)
            dst_file.flush()
            os.fsync(dst_file.fileno())

        dst_hash = compute_sha256(tmp_path)
        if src_hash != dst_hash:
            tmp_path.unlink(missing_ok=True)
            raise IOError(
                f"Staging SHA-256 mismatch! Source ({src_hash[:12]}) != Staged ({dst_hash[:12]})"
            )
        log.info("Atomic staging complete: %s -> %s (SHA-256 verified)", src.name, tmp_path.name)
        return tmp_path
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def classify_adb_install_error(stderr_output: str, apk_path: Path) -> str:
    """
    Translate raw PackageManager failures into actionable Glass-Box diagnostics.

    Maps ``INSTALL_PARSE_FAILED_NO_CERTIFICATES`` and its SHA-256 digest
    variant to user-facing instructions with specific remediation steps.
    """
    if "INSTALL_PARSE_FAILED_NO_CERTIFICATES" in stderr_output:
        if "SHA-256 digest of contents did not verify" in stderr_output:
            return (
                "APK Signature Scheme v3 Verification Failed (Tampered or Corrupted APK).\n\n"
                f"File: {apk_path.name}\n"
                "Why this happened:\n"
                "\u2022 The APK contents were modified after signing (e.g. manifest/resource edit) "
                "without re-signing, OR\n"
                "\u2022 The APK download/extraction in %TEMP% is incomplete.\n\n"
                "How to fix:\n"
                "1. Re-download a clean copy of the APK if it was corrupted.\n"
                "2. If this is a modified/patched APK, re-sign it with apksigner (v2/v3) "
                "before installing, or enable CorePatch (LSPosed) on your rooted device "
                "to bypass signature digest verification."
            )
        return (
            "Missing APK Certificates (INSTALL_PARSE_FAILED_NO_CERTIFICATES).\n"
            "The APK is unsigned or uses a deprecated v1 signature rejected by Android 14."
        )
    return stderr_output.strip()
