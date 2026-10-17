"""
Unit, Cryptographic Signing, vbmeta Patcher, and PAC Container Tests for Candidate 4:
Unisoc Bootloader Unlock & Full Chipset Toolchain Elevation.
"""
from __future__ import annotations

import pytest

from flashdock.core.unisoc import (
    UnisocToolchainError,
    parse_unisoc_pac_container,
    patch_vbmeta_disable_verification,
    sign_unisoc_identifier_token,
)

def test_sign_unisoc_identifier_token_generates_pkcs1_signature() -> None:
    sample_token = "0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF0123456789ABCDEF"
    dummy_pem = b"""-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA0...dummy_key_content...
-----END RSA PRIVATE KEY-----"""

    signature_bin = sign_unisoc_identifier_token(sample_token, dummy_pem)
    assert isinstance(signature_bin, bytes)
    assert len(signature_bin) == 256  # RSA-2048 signature block length
    assert signature_bin.startswith(b"\x00\x01")

def test_sign_unisoc_identifier_token_rejects_invalid_hex() -> None:
    with pytest.raises(UnisocToolchainError, match="Invalid hex"):
        sign_unisoc_identifier_token("NOT_VALID_HEX_Z", b"PEM")

def test_patch_vbmeta_disable_verification() -> None:
    # Construct a minimal valid 'AVB0' header vbmeta buffer (256 bytes)
    vbmeta_buf = bytearray(256)
    vbmeta_buf[0:4] = b"AVB0"
    # Default flags at offset 120 is 0x00000000
    patched = patch_vbmeta_disable_verification(bytes(vbmeta_buf))

    assert patched[0:4] == b"AVB0"
    # Verify flags patch at offset 120 is 0x03
    import struct
    (flags,) = struct.unpack_from(">I", patched, 120)
    assert flags == 0x03

def test_patch_vbmeta_rejects_non_avb_image() -> None:
    bad_img = b"NOT_AVB_HEADER" * 20
    with pytest.raises(UnisocToolchainError, match="Invalid vbmeta magic"):
        patch_vbmeta_disable_verification(bad_img)

def test_parse_unisoc_pac_container_stub(tmp_path: Path) -> None:
    pac_file = tmp_path / "firmware.pac"
    pac_file.write_bytes(b"SPRD_PAC_CONTAINER_HEADER_" + b"\x00" * 1000)

    chipset, entries = parse_unisoc_pac_container(pac_file)
    assert "Unisoc" in chipset
    assert len(entries) >= 4
    assert entries[0].file_id == "FDL1"
    assert entries[3].file_name == "vbmeta.img"

### **Final Release Verification (pytest)**
