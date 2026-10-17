"""
Unit, Stage-Gate Interlock, Checksum, and High-DPI UI Tests for Candidate 3:
OEM Interactive Workflow Guides (Xiaomi HyperOS 2.0 & Samsung Knox-Safe).
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from flashdock.core.oem_workflows import (
    OemWorkflowError,
    SamsungDownloadState,
    StageGateResult,
    classify_samsung_csc_package,
    evaluate_samsung_knox_gate,
    evaluate_xiaomi_hyperos_arb_gate,
    parse_fastboot_getvar_all,
    verify_samsung_tar_md5,
)
from flashdock.ui.oem_svg_assets import OEM_WORKFLOW_SVGS

def test_parse_xiaomi_fastboot_getvar_all() -> None:
    sample_output = """
(bootloader) product: houji
(bootloader) unlocked: yes
(bootloader) anti: 4
(bootloader) current-slot: b
(bootloader) serialno: 9a8b7c6d
all: Done!!
"""
    state = parse_fastboot_getvar_all(sample_output)
    assert state.product == "houji"
    assert state.unlocked is True
    assert state.arb_index == 4
    assert state.current_slot == "b"
    assert state.serialno == "9a8b7c6d"

def test_xiaomi_hyperos_arb_tripwire_blocks_downgrade() -> None:
    state = parse_fastboot_getvar_all(
        "(bootloader) product: garnet\n(bootloader) unlocked: yes\n(bootloader) anti: 4\n"
    )
    # Target ROM has ARB 3 (< Device ARB 4) -> MUST BLOCK to prevent hard brick
    blocked = evaluate_xiaomi_hyperos_arb_gate(state, target_rom_arb=3, expected_product="garnet")
    assert blocked.passed is False
    assert blocked.severity == "BLOCKED"
    assert "CRITICAL ARB TRIPWIRE" in blocked.headline

    # Equal ARB (4 == 4) -> SAFE
    safe = evaluate_xiaomi_hyperos_arb_gate(state, target_rom_arb=4, expected_product="garnet")
    assert safe.passed is True
    assert safe.severity == "SAFE"

    # Higher ARB (5 > 4) -> Passed with fuse increment WARNING
    warn = evaluate_xiaomi_hyperos_arb_gate(state, target_rom_arb=5, expected_product="garnet")
    assert warn.passed is True
    assert warn.severity == "WARNING"

def test_xiaomi_hyperos_blocks_locked_or_mismatched_product() -> None:
    locked_state = parse_fastboot_getvar_all(
        "(bootloader) product: duchamp\n(bootloader) unlocked: no\n(bootloader) anti: 1\n"
    )
    res_locked = evaluate_xiaomi_hyperos_arb_gate(locked_state, target_rom_arb=1)
    assert res_locked.passed is False
    assert res_locked.severity == "BLOCKED"

    res_mismatch = evaluate_xiaomi_hyperos_arb_gate(
        locked_state, target_rom_arb=1, expected_product="mondrian"
    )
    assert res_mismatch.passed is False
    assert "Mismatch" in res_mismatch.headline

def test_samsung_knox_prenormal_blocks_custom_binaries() -> None:
    prenormal = SamsungDownloadState(
        model="SM-S928B",
        kg_state="Prenormal",
        warranty_void=0,
        frp_lock=False,
        oem_lock=False,
    )
    # Official Odin firmware is allowed even under Prenormal if FRP is off
    official_res = evaluate_samsung_knox_gate(prenormal, is_custom_binary=False)
    assert official_res.passed is True
    assert official_res.severity == "SAFE"

    # Custom binary (e.g. Magisk/TWRP tar) MUST BE BLOCKED when KG STATE is Prenormal
    custom_res = evaluate_samsung_knox_gate(prenormal, is_custom_binary=True)
    assert custom_res.passed is False
    assert custom_res.severity == "BLOCKED"
    assert "Prenormal" in custom_res.headline

def test_samsung_knox_warranty_bit_0x0_warns_before_custom_flash() -> None:
    checking_untripped = SamsungDownloadState(
        model="SM-A556E",
        kg_state="Checking",
        warranty_void=0,
        frp_lock=False,
        oem_lock=False,
    )
    res = evaluate_samsung_knox_gate(checking_untripped, is_custom_binary=True)
    assert res.passed is True
    assert res.severity == "WARNING"
    assert "0x0 -> Will Become 0x1" in res.headline

def test_samsung_tar_md5_streaming_verification(tmp_path: Path) -> None:
    fake_tar_body = b"USTAR_SAMSUNG_BOOT_IMG_LZ4_PAYLOAD_" * 64  # > 2048 bytes
    digest = hashlib.md5(fake_tar_body).hexdigest()
    trailer = f"{digest}  AP_S928BXXU1AX_CL123.tar\n".encode("ascii")

    valid_pkg = tmp_path / "AP_S928BXXU1AX_CL123.tar.md5"
    valid_pkg.write_bytes(fake_tar_body + trailer)

    ok, exp, comp = verify_samsung_tar_md5(valid_pkg)
    assert ok is True
    assert exp == comp == digest

    # Corrupt 1 byte in the tar body and confirm MD5 mismatch is caught
    corrupted = bytearray(fake_tar_body + trailer)
    corrupted[100] ^= 0xFF
    ok_bad, exp_bad, comp_bad = verify_samsung_tar_md5(corrupted)
    assert ok_bad is False
    assert exp_bad != comp_bad

def test_samsung_csc_vs_home_csc_classification() -> None:
    keep = classify_samsung_csc_package("HOME_CSC_OMC_OXM_S928B.tar.md5")
    assert keep.passed is True
    assert keep.severity == "SAFE"
    assert "Preserved" in keep.headline

    wipe = classify_samsung_csc_package("CSC_OMC_OXM_S928B.tar.md5")
    assert wipe.passed is True
    assert wipe.severity == "WARNING"
    assert "Factory Reset" in wipe.headline

def test_oem_vector_svg_assets_are_well_formed() -> None:
    for key, svg in OEM_WORKFLOW_SVGS.items():
        assert svg.strip().startswith("<svg"), f"{key} missing <svg> root"
        assert svg.strip().endswith("</svg>"), f"{key} missing </svg> closing tag"
        assert "viewBox=" in svg

### **Verification & Next Step**
