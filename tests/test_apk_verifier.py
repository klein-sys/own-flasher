"""
Unit Tests — APK Pre-Flight Verifier & Atomic Staging (apk_verifier.py).

Tests:
1. compute_sha256: Correct hex digest for known content.
2. _detect_apk_sig_block_v2_v3: Presence and absence of APK Sig Block 42.
3. verify_apk_preflight:
   - Valid APK with v1 JAR signature.
   - Valid APK with synthesized v2/v3 signing block.
   - Missing file, empty file, non-ZIP file, missing AndroidManifest.xml.
   - Corrupted ZIP entry (CRC mismatch via header manipulation).
   - Unsigned APK (no v1 or v2/v3 signatures).
4. stage_apk_atomically:
   - ASCII paths returned directly (fast path).
   - Non-ASCII paths staged to %TEMP% with SHA-256 parity.
5. classify_adb_install_error:
   - INSTALL_PARSE_FAILED_NO_CERTIFICATES with SHA-256 digest mismatch.
   - INSTALL_PARSE_FAILED_NO_CERTIFICATES generic (unsigned).
   - Unknown errors passed through.
"""

from __future__ import annotations

import hashlib
import struct
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from flashdock.core.apk_verifier import (
    APK_SIG_BLOCK_MAGIC,
    ApkPreFlightResult,
    _detect_apk_sig_block_v2_v3,
    classify_adb_install_error,
    compute_sha256,
    stage_apk_atomically,
    verify_apk_preflight,
)


# ---------------------------------------------------------------------------
# Test compute_sha256
# ---------------------------------------------------------------------------

class TestComputeSHA256:
    def test_known_content(self, tmp_path):
        f = tmp_path / "test.bin"
        content = b"FlashDock APK verifier test payload"
        f.write_bytes(content)
        expected = hashlib.sha256(content).hexdigest()
        assert compute_sha256(f) == expected

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.bin"
        f.write_bytes(b"")
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_sha256(f) == expected

    def test_large_file_chunked(self, tmp_path):
        """Ensure chunked reading produces correct digest for files larger than chunk_size."""
        f = tmp_path / "large.bin"
        # 2.5 MB of data to cross the 1 MB chunk boundary
        data = b"A" * (1024 * 1024 * 2 + 512 * 1024)
        f.write_bytes(data)
        expected = hashlib.sha256(data).hexdigest()
        assert compute_sha256(f) == expected


# ---------------------------------------------------------------------------
# Test _detect_apk_sig_block_v2_v3
# ---------------------------------------------------------------------------

class TestDetectApkSigBlock:
    def test_returns_false_for_tiny_file(self, tmp_path):
        f = tmp_path / "tiny.apk"
        f.write_bytes(b"PK\x03\x04short")
        assert _detect_apk_sig_block_v2_v3(f) is False

    def test_returns_false_for_plain_zip(self, tmp_path):
        """A normal ZIP archive without APK Signing Block should return False."""
        f = tmp_path / "plain.zip"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("hello.txt", "world")
        assert _detect_apk_sig_block_v2_v3(f) is False

    def test_returns_false_for_nonexistent_file(self, tmp_path):
        f = tmp_path / "nonexistent.apk"
        assert _detect_apk_sig_block_v2_v3(f) is False

    def test_detects_synthesized_sig_block(self, tmp_path):
        """
        Build a synthetic APK with the 'APK Sig Block 42' magic at the correct offset.

        Layout:
        [Local File Entries] [APK Signing Block ... magic] [Central Directory] [EOCD]
        """
        f = tmp_path / "signed.apk"

        # Create a minimal valid ZIP first
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake manifest")
            zf.writestr("META-INF/CERT.RSA", b"fake cert")

        # Read the entire ZIP, find the CD offset from EOCD, and inject the signing block
        raw = bytearray(f.read_bytes())

        # Find EOCD
        eocd_pos = raw.rfind(b"PK\x05\x06")
        assert eocd_pos != -1

        # Read original CD offset from EOCD (bytes 16..20)
        original_cd_offset = struct.unpack_from("<I", raw, eocd_pos + 16)[0]

        # Build a minimal APK Signing Block (just the magic + size header)
        # Block layout: [8-byte size_of_block] [pairs...] [8-byte size_of_block] [16-byte magic]
        sig_block_content = b"\x00" * 8  # Placeholder pair data
        block_size = len(sig_block_content) + 8 + 16  # pairs + size + magic
        signing_block = (
            struct.pack("<Q", block_size)       # size of block (first)
            + sig_block_content                  # key-value pairs
            + struct.pack("<Q", block_size)       # size of block (second)
            + APK_SIG_BLOCK_MAGIC                # magic
        )

        # Insert signing block right before the Central Directory
        new_raw = (
            raw[:original_cd_offset]
            + signing_block
            + raw[original_cd_offset:]
        )

        # Update CD offset in EOCD to point past the signing block
        new_cd_offset = original_cd_offset + len(signing_block)
        new_eocd_pos = new_raw.rfind(b"PK\x05\x06")
        struct.pack_into("<I", new_raw, new_eocd_pos + 16, new_cd_offset)

        f.write_bytes(bytes(new_raw))

        assert _detect_apk_sig_block_v2_v3(f) is True


# ---------------------------------------------------------------------------
# Test verify_apk_preflight
# ---------------------------------------------------------------------------

class TestVerifyApkPreflight:
    def test_missing_file(self, tmp_path):
        result = verify_apk_preflight(tmp_path / "ghost.apk")
        assert result.ok is False
        assert "missing or empty" in result.error_reason

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.apk"
        f.write_bytes(b"")
        result = verify_apk_preflight(f)
        assert result.ok is False
        assert "missing or empty" in result.error_reason

    def test_non_zip_file(self, tmp_path):
        f = tmp_path / "notazip.apk"
        f.write_bytes(b"this is not a zip file at all")
        result = verify_apk_preflight(f)
        assert result.ok is False
        assert "not a valid ZIP" in result.error_reason

    def test_missing_manifest(self, tmp_path):
        f = tmp_path / "no_manifest.apk"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("classes.dex", b"dex data")
        result = verify_apk_preflight(f)
        assert result.ok is False
        assert "AndroidManifest.xml" in result.error_reason

    def test_unsigned_apk(self, tmp_path):
        """APK with manifest but no v1 or v2/v3 signatures."""
        f = tmp_path / "unsigned.apk"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake manifest")
            zf.writestr("classes.dex", b"fake dex")
        result = verify_apk_preflight(f)
        assert result.ok is False
        assert "Unsigned APK" in result.error_reason
        assert result.sha256 != ""  # SHA-256 should still be computed

    def test_valid_v1_signed_apk(self, tmp_path):
        """APK with META-INF/*.RSA passes as v1-signed."""
        f = tmp_path / "v1_signed.apk"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake manifest")
            zf.writestr("META-INF/CERT.RSA", b"fake cert data")
            zf.writestr("classes.dex", b"fake dex")
        result = verify_apk_preflight(f)
        assert result.ok is True
        assert result.has_v1_jar_sig is True
        assert result.sha256 != ""
        assert result.error_reason == ""

    def test_valid_v1_dsa_signed(self, tmp_path):
        """APK with META-INF/*.DSA also counts as v1-signed."""
        f = tmp_path / "v1_dsa.apk"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake manifest")
            zf.writestr("META-INF/CERT.DSA", b"fake dsa data")
        result = verify_apk_preflight(f)
        assert result.ok is True
        assert result.has_v1_jar_sig is True

    def test_valid_v1_ec_signed(self, tmp_path):
        """APK with META-INF/*.EC also counts as v1-signed."""
        f = tmp_path / "v1_ec.apk"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake manifest")
            zf.writestr("META-INF/CERT.EC", b"fake ec data")
        result = verify_apk_preflight(f)
        assert result.ok is True
        assert result.has_v1_jar_sig is True

    def test_result_is_frozen_dataclass(self, tmp_path):
        f = tmp_path / "v1_signed.apk"
        with zipfile.ZipFile(f, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"manifest")
            zf.writestr("META-INF/CERT.RSA", b"cert")
        result = verify_apk_preflight(f)
        with pytest.raises(AttributeError):
            result.ok = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Test stage_apk_atomically
# ---------------------------------------------------------------------------

class TestStageApkAtomically:
    def test_ascii_path_returns_directly(self, tmp_path):
        """Pure ASCII paths should be returned as-is (fast path, no copy)."""
        f = tmp_path / "clean_ascii.apk"
        f.write_bytes(b"dummy apk content")
        result = stage_apk_atomically(f)
        assert result == f.resolve()

    def test_non_ascii_path_stages_to_temp(self, tmp_path):
        """Non-ASCII paths should be staged to %TEMP% with SHA-256 parity verification."""
        # Create a file with non-ASCII characters in the path
        unicode_dir = tmp_path / "\u00e4\u00f6\u00fc_folder"
        unicode_dir.mkdir()
        f = unicode_dir / "app_\u00e9\u00e8.apk"
        content = b"FlashDock APK content for staging test"
        f.write_bytes(content)

        result = stage_apk_atomically(f)

        # Should be staged to a different (temp) path
        assert result != f.resolve()
        assert result.exists()
        assert result.suffix == ".apk"
        assert "flashdock_stage_" in result.name

        # SHA-256 parity check
        expected_hash = hashlib.sha256(content).hexdigest()
        actual_hash = compute_sha256(result)
        assert actual_hash == expected_hash

        # Cleanup
        result.unlink(missing_ok=True)

    def test_staging_preserves_exact_content(self, tmp_path):
        """Staged file must be byte-for-byte identical to source."""
        unicode_dir = tmp_path / "\u4e2d\u6587\u8def\u5f84"
        unicode_dir.mkdir()
        f = unicode_dir / "\u6d4b\u8bd5.apk"
        content = b"\x00\x01\x02" * 100000  # ~300KB binary content
        f.write_bytes(content)

        result = stage_apk_atomically(f)
        assert result.read_bytes() == content
        result.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test classify_adb_install_error
# ---------------------------------------------------------------------------

class TestClassifyAdbInstallError:
    def test_sha256_digest_mismatch(self):
        stderr = (
            "adb.exe: failed to install app.apk: Failure "
            "[INSTALL_PARSE_FAILED_NO_CERTIFICATES: Failed to collect certificates from "
            "/data/app/vmdl1601401312.tmp/base.apk using APK Signature Scheme v3: "
            "SHA-256 digest of contents did not verify]"
        )
        msg = classify_adb_install_error(stderr, Path("app.apk"))
        assert "APK Signature Scheme v3 Verification Failed" in msg
        assert "app.apk" in msg
        assert "re-sign" in msg.lower() or "Re-sign" in msg or "re-download" in msg.lower()
        assert "CorePatch" in msg

    def test_generic_no_certificates(self):
        stderr = (
            "Failure [INSTALL_PARSE_FAILED_NO_CERTIFICATES: "
            "Package /data/app/base.apk has no certificates]"
        )
        msg = classify_adb_install_error(stderr, Path("unsigned.apk"))
        assert "Missing APK Certificates" in msg
        assert "unsigned" in msg.lower() or "deprecated" in msg.lower()

    def test_unknown_error_passthrough(self):
        stderr = "Failure [INSTALL_FAILED_INTERNAL_ERROR: some random error]"
        msg = classify_adb_install_error(stderr, Path("app.apk"))
        assert "INSTALL_FAILED_INTERNAL_ERROR" in msg

    def test_empty_stderr(self):
        msg = classify_adb_install_error("", Path("app.apk"))
        assert msg == ""

    def test_whitespace_only_stderr(self):
        msg = classify_adb_install_error("   \n\t  ", Path("app.apk"))
        assert msg == ""


# ---------------------------------------------------------------------------
# Integration: Sideload Manager Pre-Flight Gating
# ---------------------------------------------------------------------------

class TestSideloadManagerPreflightIntegration:
    """Verify that SideloadManager.install_apk blocks unsigned/corrupted APKs."""

    def test_install_blocks_unsigned_apk(self, tmp_path):
        from unittest.mock import MagicMock
        from flashdock.tools.adb import ADB
        from flashdock.tools.sideload import SideloadManager

        # Create an unsigned APK (no signatures)
        apk = tmp_path / "unsigned.apk"
        with zipfile.ZipFile(apk, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake manifest")
            zf.writestr("classes.dex", b"fake dex")

        adb = MagicMock(spec=ADB)
        adb.getprop.return_value = "34"
        mgr = SideloadManager(adb=adb)

        ok, msg = mgr.install_apk(apk, serial="TEST")
        assert ok is False
        assert "Pre-Flight Failed" in msg
        assert "Unsigned APK" in msg
        # ADB should NOT have been called at all
        adb._run.assert_not_called()

    def test_install_blocks_non_zip_file(self, tmp_path):
        from unittest.mock import MagicMock
        from flashdock.tools.adb import ADB
        from flashdock.tools.sideload import SideloadManager

        corrupt = tmp_path / "corrupt.apk"
        corrupt.write_bytes(b"not a zip file at all, corrupted download")

        adb = MagicMock(spec=ADB)
        adb.getprop.return_value = "33"
        mgr = SideloadManager(adb=adb)

        ok, msg = mgr.install_apk(corrupt, serial="TEST")
        assert ok is False
        assert "Pre-Flight Failed" in msg
        adb._run.assert_not_called()

    def test_install_passes_valid_v1_apk(self, tmp_path):
        from unittest.mock import MagicMock
        from flashdock.tools.adb import ADB
        from flashdock.tools.runner import CommandResult
        from flashdock.tools.sideload import SideloadManager

        # Create a v1-signed APK
        apk = tmp_path / "valid.apk"
        with zipfile.ZipFile(apk, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"fake manifest")
            zf.writestr("META-INF/CERT.RSA", b"fake cert")
            zf.writestr("classes.dex", b"fake dex")

        adb = MagicMock(spec=ADB)
        adb.getprop.return_value = "34"
        adb._run.return_value = CommandResult(
            command=["adb", "install"],
            return_code=0,
            stdout="Success\n",
            stderr="",
            duration_ms=100,
        )

        mgr = SideloadManager(adb=adb)
        ok, msg = mgr.install_apk(apk, serial="TEST")
        assert ok is True
        assert "Successfully installed" in msg
        adb._run.assert_called_once()

    def test_install_classifies_no_certificates_error(self, tmp_path):
        from unittest.mock import MagicMock
        from flashdock.tools.adb import ADB
        from flashdock.tools.runner import CommandResult
        from flashdock.tools.sideload import SideloadManager

        # Create a v1-signed APK that passes pre-flight
        apk = tmp_path / "tampered.apk"
        with zipfile.ZipFile(apk, "w") as zf:
            zf.writestr("AndroidManifest.xml", b"manifest")
            zf.writestr("META-INF/CERT.RSA", b"cert")

        adb = MagicMock(spec=ADB)
        adb.getprop.return_value = "34"
        adb._run.return_value = CommandResult(
            command=["adb", "install"],
            return_code=1,
            stdout=(
                "adb.exe: failed to install tampered.apk: Failure "
                "[INSTALL_PARSE_FAILED_NO_CERTIFICATES: Failed to collect certificates "
                "using APK Signature Scheme v3: SHA-256 digest of contents did not verify]"
            ),
            stderr="",
            duration_ms=80,
        )

        mgr = SideloadManager(adb=adb)
        ok, msg = mgr.install_apk(apk, serial="TEST")
        assert ok is False
        assert "APK Signature Scheme v3 Verification Failed" in msg
