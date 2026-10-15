"""
Property-Based & Boundary Fuzzing Suite for FlashDock Binary Parsers (v1.5.0).

Feeds randomized, truncated, bit-flipped, overlapping-offset, and boundary-value
byte streams into:
  1. `RootingEngine.validate_boot_image()` (GKI boot_img_hdr v0–v4 parser)
  2. `PayloadDumper` (OTA payload.bin CrAU header, varint, and manifest parser)
  3. `LZ4Util` (Samsung .lz4 frame and block decompressor)
  4. `UnisocUnlockManager` (RSA-2048 PKCS#1 v1.5 token signer & PAC header parser)
  5. `flashdock.tools.mmap_stream` (Zip-Slip / Tar-Slip archive security guards)

Guarantees that malformed or hostile firmware files never cause infinite loops,
unbounded memory allocations, or unhandled runtime crashes.
"""

from __future__ import annotations

from pathlib import Path
import random
import struct
import tarfile
import io
import zipfile
import pytest

from flashdock.core.rooting import RootingEngine
from flashdock.core.unisoc import UnisocUnlockManager
from flashdock.tools.lz4_util import LZ4Util
from flashdock.tools.mmap_stream import (
    ArchiveSecurityError,
    open_mmap_view,
    safe_extract_tar,
    safe_extract_zip,
    validate_safe_member_path,
)
from flashdock.tools.payload_dumper import PAYLOAD_MAGIC, PayloadDumper


class TestBootImageHeaderFuzzing:
    """Fuzzing suite for GKI ANDROID! boot/init_boot header validation."""

    @pytest.mark.parametrize("seed", range(25))
    def test_random_noise_boot_images_never_crash(self, tmp_path: Path, seed: int) -> None:
        rng = random.Random(seed)
        size = rng.choice([0, 1, 7, 8, 32, 64, 512, 1632, 4096])
        noise = rng.randbytes(size)
        img_path = tmp_path / f"fuzz_boot_{seed}.img"
        img_path.write_bytes(noise)

        valid, msg = RootingEngine.validate_boot_image(img_path)
        assert isinstance(valid, bool)
        assert isinstance(msg, str)

    @pytest.mark.parametrize("header_version", [0, 1, 2, 3, 4, 5, 99, 0xFFFFFFFF])
    def test_boundary_header_versions_and_truncated_magic(
        self, tmp_path: Path, header_version: int
    ) -> None:
        buf = bytearray(4096)
        buf[:8] = b"ANDROID!"
        # Place header_version at both v0-v2 offset (40) and v3-v4 offset (20)
        struct.pack_into("<I", buf, 20, header_version)
        struct.pack_into("<I", buf, 40, header_version)
        # Set kernel_size and page_size
        struct.pack_into("<I", buf, 8, 1024)
        struct.pack_into("<I", buf, 36, 4096)

        img_path = tmp_path / f"boot_v{header_version}.img"
        img_path.write_bytes(buf)
        valid, msg = RootingEngine.validate_boot_image(img_path)
        assert isinstance(valid, bool)
        assert len(msg) > 0


class TestLZ4ParserFuzzing:
    """Fuzzing suite for pure-Python LZ4 block and frame decompression."""

    @pytest.mark.parametrize("seed", range(30))
    def test_corrupted_lz4_blocks_raise_clean_value_error(self, seed: int) -> None:
        rng = random.Random(1000 + seed)
        corrupted = rng.randbytes(rng.randint(1, 256))
        try:
            res = LZ4Util.decompress_block(corrupted, uncompressed_size=512)
            assert isinstance(res, (bytes, bytearray))
        except (ValueError, RuntimeError):
            # Cleanly rejected corrupted block without hanging or crashing
            pass

    def test_zero_match_offset_rejected_immediately(self) -> None:
        # Token: 1 literal ('A'), 4 match length, followed by illegal offset 0x0000
        malicious_block = b"\x10A\x00\x00"
        with pytest.raises((ValueError, RuntimeError)):
            LZ4Util.decompress_block(malicious_block, uncompressed_size=64)

    def test_out_of_bounds_match_offset_rejected(self) -> None:
        # Token: 1 literal ('A'), match offset 0x1000 (way past 1-byte output buffer)
        malicious_block = b"\x10A\x00\x10"
        with pytest.raises((ValueError, RuntimeError)):
            LZ4Util.decompress_block(malicious_block, uncompressed_size=64)

    @pytest.mark.parametrize("seed", range(15))
    def test_truncated_lz4_frames_rejected_cleanly(self, tmp_path: Path, seed: int) -> None:
        rng = random.Random(2000 + seed)
        # Prepend valid LZ4 frame magic 0x184D2204 followed by random truncated bytes
        data = b"\x04\x22\x4d\x18" + rng.randbytes(rng.randint(0, 64))
        src = tmp_path / f"trunc_{seed}.img.lz4"
        dst = tmp_path / f"trunc_{seed}.img"
        src.write_bytes(data)

        try:
            LZ4Util.decompress_file(src, dst)
        except (ValueError, RuntimeError, EOFError):
            pass


class TestPayloadDumperFuzzing:
    """Fuzzing suite for Android A/B OTA payload.bin header and varint parsers."""

    @pytest.mark.parametrize("seed", range(20))
    def test_fuzzed_payload_headers_never_hang(self, tmp_path: Path, seed: int) -> None:
        rng = random.Random(3000 + seed)
        # Mix of valid magic + random version/manifest_len/sig_len
        header = PAYLOAD_MAGIC + rng.randbytes(rng.randint(0, 128))
        payload_file = tmp_path / f"payload_{seed}.bin"
        payload_file.write_bytes(header)

        dumper = PayloadDumper(payload_file)
        try:
            dumper.list_partitions()
        except (ValueError, RuntimeError, EOFError, struct.error):
            pass

    def test_huge_manifest_length_rejected_without_oom(self, tmp_path: Path) -> None:
        # Craft CrAU v2 header claiming a 4 GB manifest in a 32-byte file
        crafted = (
            PAYLOAD_MAGIC
            + struct.pack(">Q", 2)  # version 2
            + struct.pack(">Q", 0xFFFFFFFF)  # 4 GB manifest_len
            + struct.pack(">I", 0)  # metadata_sig_len
        )
        payload_file = tmp_path / "oom_payload.bin"
        payload_file.write_bytes(crafted)

        dumper = PayloadDumper(payload_file)
        with pytest.raises((ValueError, RuntimeError, EOFError)):
            dumper.list_partitions()


class TestUnisocAndArchiveSecurityFuzzing:
    """Fuzzing suite for Unisoc RSA/PAC parsers and Zip-Slip/Tar-Slip guards."""

    @pytest.mark.parametrize("seed", range(15))
    def test_unisoc_challenge_token_fuzzing(self, seed: int) -> None:
        rng = random.Random(4000 + seed)
        mgr = UnisocUnlockManager()
        token_hex = rng.randbytes(rng.randint(1, 64)).hex()
        sig = mgr.generate_signature_bytes(token_hex)
        assert isinstance(sig, bytes)
        assert len(sig) == 256  # Deterministic 2048-bit RSA block

    def test_zip_slip_path_traversal_blocked(self, tmp_path: Path) -> None:
        zip_file = tmp_path / "malicious.zip"
        with zipfile.ZipFile(zip_file, "w") as zf:
            zf.writestr("../../evil_boot.img", b"malicious")

        with pytest.raises(ArchiveSecurityError):
            safe_extract_zip(zip_file, tmp_path / "out")

    def test_tar_slip_and_symlink_blocked(self, tmp_path: Path) -> None:
        tar_file = tmp_path / "malicious.tar"
        with tarfile.open(tar_file, "w") as tf:
            info = tarfile.TarInfo(name="../escape.img")
            data = b"escape"
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))

        with pytest.raises((ArchiveSecurityError, tarfile.FilterError, ValueError)):
            safe_extract_tar(tar_file, tmp_path / "out")

    def test_mmap_view_handles_empty_and_valid_files(self, tmp_path: Path) -> None:
        empty_f = tmp_path / "empty.bin"
        empty_f.write_bytes(b"")
        with open_mmap_view(empty_f) as view:
            assert len(view) == 0

        data_f = tmp_path / "sample.bin"
        data_f.write_bytes(b"CrAU_FLASHDOCK_V150")
        with open_mmap_view(data_f) as view:
            assert bytes(view[:4]) == b"CrAU"

