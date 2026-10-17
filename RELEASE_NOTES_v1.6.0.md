# FlashDock v1.6.0 Release Notes

## Summary

Upgrades **FlashDock** from `v1.5.0` to `v1.6.0` with the complete implementation of the Milestone 1.6.0 specification across all 4 Candidate Milestones:
1. **Dynamic Partition Management (`super.img` Sparse & liblp Unpacker/Repacker)**: Pure-Python standard library implementation for Android dynamic partition headers, LP metadata tables, zero-copy sparse-to-raw conversion, partition extraction, and group budget repacking.
2. **Full Emergency Protocol Data Transfer**: Low-level chunked data streaming over Qualcomm Sahara (32-bit and 64-bit ELF segments via commands `0x03` and `0x12`) and Unisoc HDLC (FDL1/FDL2 two-stage loading with `0x7E` framing and BSL state machine).
3. **OEM Interactive Workflow Guides**: Xiaomi HyperOS 2.0 (Fastboot Anti-Rollback tripwires, A/B slot integrity checks) and Samsung Knox-Safe (KG/RMM state, Warranty Bit 0x0 gate, streaming `.tar.md5` checksum validation, `HOME_CSC` vs `CSC` classification) with 100% dynamic vector SVG hardware button illustrations.
4. **Unisoc Bootloader Unlock & Full Chipset Toolchain Elevation**: Pure-Python RSA-2048 PKCS#1 v1.5 identifier token signing, anti-Red-State `vbmeta` verification patcher (`0x03` flag override), and standalone `UnisocUnlockerCard` with deep integration into `unlock_screen.py`, `mtk_unisoc_screen.py`, and `workflow_guide.py`.

---

## Architecture & Subsystem Tree

```text
FlashDock Core & UI Subsystems
 ├── flashdock.core.super_img
 │    ├── unpack_super_image()                   [Pure-Python sparse-to-raw & LP partition extractor]
 │    ├── repack_super_image()                   [LP metadata geometry & group budget repacker]
 │    └── SuperImageInspectorWidget              [High-DPI dynamic group breakdown & QThread unpacker]
 ├── flashdock.core.emergency_transfer
 │    ├── stream_qualcomm_sahara_elf()           [Sahara Cmd 0x03/0x12 32/64-bit ELF streaming]
 │    ├── stream_unisoc_fdl()                    [Unisoc HDLC 0x7E framing + BSL chunk sequencing]
 │    └── EmergencyLoaderCard                    [Non-blocking QThread protocol transfer card]
 ├── flashdock.core.oem_workflows
 │    ├── XiaomiHyperOsGateEngine                [Fastboot ARB tripwire & slot-switch safety guard]
 │    ├── SamsungKnoxSafeGateEngine              [Knox warranty bit 0x0 & streaming tar.md5 verifier]
 │    ├── oem_svg_assets.py                      [100% Vector SVG hardware key-combination diagrams]
 │    └── OemWorkflowWizard                      [High-DPI stage-gate interactive wizard card]
 └── flashdock.core.unisoc
      ├── sign_unisoc_identifier_token()         [Pure-Python RSA-2048 PKCS#1 v1.5 token signer]
      ├── patch_vbmeta_disable_verification()    [Offset 120 flags -> 0x03 Anti-Red-State patcher]
      ├── parse_unisoc_pac_container()           [PAC firmware archive parser & entry extractor]
      └── UnisocUnlockerCard                     [1-Click Fastboot unlock & vbmeta patcher card]
```

---

## File Manifest & Deliverables

1. **Candidate 1: Dynamic Partition Management**:
   - `flashdock/core/super_img.py` (751 lines): LP metadata, sparse decompression, unpacking, and repacking.
   - `flashdock/ui/widgets/super_inspector.py` (176 lines): High-DPI inspector card with `SuperUnpackWorker`.
   - `tests/test_super_img_v160.py`: 8 unit and property tests.
2. **Candidate 2: Full Emergency Protocol Data Transfer**:
   - `flashdock/core/emergency_transfer.py` (454 lines): Sahara ELF streaming and Unisoc HDLC transfer.
   - `flashdock/ui/widgets/emergency_loader_card.py` (185 lines): High-DPI transfer card with `EmergencyStreamWorker`.
   - `tests/test_emergency_transfer_v160.py`: 6 protocol streaming tests.
3. **Candidate 3: OEM Interactive Workflow Guides**:
   - `flashdock/core/oem_workflows.py` (305 lines): HyperOS ARB and Samsung Knox-Safe engines.
   - `flashdock/ui/oem_svg_assets.py` (48 lines): Vector SVG hardware key diagrams.
   - `flashdock/ui/widgets/oem_workflow_wizard.py` (177 lines): Interactive stage-gate wizard.
   - `tests/test_oem_workflows_v160.py`: 8 workflow and safety gate tests.
4. **Candidate 4: Unisoc Bootloader Unlock & Toolchain Elevation**:
   - `flashdock/core/unisoc.py`: Appended RSA signer, vbmeta patcher, and PAC container parser.
   - `flashdock/ui/widgets/unisoc_unlocker_card.py` (140 lines): Token unlocker and vbmeta patcher card.
   - `flashdock/ui/screens/unlock_screen.py`: Integrated `UnisocUnlockerCard` into brand unlock flow.
   - `flashdock/ui/screens/mtk_unisoc_screen.py`: Integrated `UnisocUnlockerCard` into Unisoc tab.
   - `flashdock/ui/widgets/workflow_guide.py`: Added 17th function card for Unisoc & Transsion Unlock.
   - `tests/test_unisoc_toolchain_v160.py`: 5 cryptographic and toolchain tests.

---

## Test & Release Verification

- **Total Passing Tests**: 656 passing tests across 55 test modules with zero failures and zero regressions.
- **Pure-Python Standard Library**: Zero external C-extensions; 100% vector SVG rendering with zero raw emojis.
- **Stand-alone Executable**: Compiled via PyInstaller 6.13 with Authenticode SHA-256 code signing.
