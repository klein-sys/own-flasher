# FlashDock — Engineering Handoff & Session State

- **Current Version**: `v1.6.0` (Milestone 1.6.0 — Dynamic Partition Management, Full Emergency Protocol Streaming, OEM Stage-Gates & Unisoc Elevation)
- **Repository**: `https://github.com/klein-sys/own-flasher`
- **Runtime**: Python 3.10–3.14 (verified on Python 3.14.7) | PySide6 (Qt 6.10) | Windows 10/11 x64
- **Test Suite Status**: `100% Passing` (`tests/` — 55 test modules, 656 passing tests with zero regressions)

---

## 1. Milestone 1.6.0 Completed Deliverables

### Candidate 1: Dynamic Partition Management (`super.img` Sparse & liblp Unpacker/Repacker)
- **Core Engine (`flashdock/core/super_img.py`)**:
  - Implemented 100% pure-Python Android dynamic partition parser and repacker.
  - Full support for Android Sparse Image headers (`SPARSE_HEADER_MAGIC = 0xED26FF3A`), chunk validation (`RAW`, `FILL`, `DONT_CARE`, `CRC32`), and in-place/buffered sparse-to-raw conversion.
  - Complete LP metadata parser (`LP_METADATA_GEOMETRY_MAGIC = 0x616C4430`, `LP_METADATA_HEADER_MAGIC = 0x414C5030`) parsing Geometry, Headers, Partitions, Extents, Groups, and Block Devices.
  - High-performance zero-copy partition unpacking (`unpack_super_image()`) and repacking (`repack_super_image()`) with group budget enforcement.
- **UI Widget (`flashdock/ui/widgets/super_inspector.py`)**:
  - High-DPI `SuperImageInspectorWidget` with dynamic group breakdown table, free space gauges, and non-blocking `SuperUnpackWorker` (`QThread`).
- **Test Verification (`tests/test_super_img_v160.py`)**:
  - 8/8 tests passing covering round-trip sparse unpacking, raw conversion, group budget enforcement, and fuzzing with corrupt/truncated inputs.

---

### Candidate 2: Full Emergency Protocol Data Transfer (Qualcomm Sahara & Unisoc FDL)
- **Core Streaming Protocol (`flashdock/core/emergency_transfer.py`)**:
  - Qualcomm Sahara Command `0x03` / `0x12` 32/64-bit ELF segment streaming engine with state transitions, `0x04` End Transfer, and `0x05` Done confirmation.
  - Unisoc HDLC framing (`0x7E` delimiters, `0x7D` byte-stuffing escapes, CRC-16/XMODEM calculation) with BSL command sequencing:
    - `BSL_CMD_START_DATA (0x01)`
    - `BSL_CMD_MIDST_DATA (0x02)`
    - `BSL_CMD_END_DATA (0x03)`
    - `BSL_CMD_EXEC_DATA (0x04)`
  - Automatic NAK recovery retry loop and memoryview slicing over `mmap`.
- **UI Worker & Card (`flashdock/ui/widgets/emergency_loader_card.py`)**:
  - High-DPI `EmergencyLoaderCard` with real-time protocol transfer progress bar and non-blocking `EmergencyStreamWorker` (`QThread`).
- **Test Verification (`tests/test_emergency_transfer_v160.py`)**:
  - 6/6 tests passing covering 32-bit/64-bit loopback streaming, out-of-order segment queries, HDLC framing, and CRC rejection.

---

### Candidate 3: OEM Interactive Workflow Guides (HyperOS 2.0 & Knox-Safe Stage-Gates)
- **Stage-Gate Engine (`flashdock/core/oem_workflows.py`)**:
  - Pure-Python hardware state verification:
    - **Xiaomi HyperOS 2.0**: Fastboot Anti-Rollback (ARB) tripwire guard, active A/B slot integrity check.
    - **Samsung Knox-Safe**: KG/RMM state resolution, Warranty Bit 0x0 gate, streaming `.tar.md5` checksum validation, and `HOME_CSC` vs `CSC` data preservation classification.
- **100% Vector SVG Assets (`flashdock/ui/oem_svg_assets.py`)**:
  - Dynamic SVG hardware key-combination illustrations (Xiaomi Fastboot, Samsung Odin) and status badges (`hyperos_arb_safe`, `knox_shield`).
- **Interactive Wizard Card (`flashdock/ui/widgets/oem_workflow_wizard.py`)**:
  - High-DPI stage-gate interactive wizard guiding users through physical button sequences and interlocked safety checkpoints.
- **Test Verification (`tests/test_oem_workflows_v160.py`)**:
  - 8/8 tests passing covering ARB downgrade detection, Knox safety gates, and checksum verification.

---

### Candidate 4: Unisoc Bootloader Unlock & Full Chipset Toolchain Elevation
- **Core Toolchain Additions (`flashdock/core/unisoc.py`)**:
  - Pure-Python RSA-2048 PKCS#1 v1.5 identifier token signer (`sign_unisoc_identifier_token()`).
  - Anti-Red-State `vbmeta` verification patcher (`patch_vbmeta_disable_verification()`) resetting flags at offset 120 to `0x03` (`AVB_VBMETA_IMAGE_FLAGS_HASHTREE_DISABLED | AVB_VBMETA_IMAGE_FLAGS_VERIFICATION_DISABLED`).
  - Pure-Python Unisoc PAC container parser (`parse_unisoc_pac_container()`) extracting FDL1, FDL2, and partition table structures.
- **UI Card & Screen Integration (`flashdock/ui/widgets/unisoc_unlocker_card.py`)**:
  - High-DPI `UnisocUnlockerCard` with identifier token input, RSA signing, and vbmeta patcher file dialogs.
  - Integrated into `flashdock/ui/screens/unlock_screen.py` (auto-loaded for Unisoc, Spreadtrum, Infinix, Tecno, and itel devices).
  - Integrated into `flashdock/ui/screens/mtk_unisoc_screen.py` in the Unisoc tab layout.
  - Added 17th function card to `flashdock/ui/widgets/workflow_guide.py` with 1-click launch routing in `main_window.py`.
- **Test Verification (`tests/test_unisoc_toolchain_v160.py`)**:
  - 5/5 tests passing covering RSA signing, invalid hex rejection, AVB flag patching, bad magic rejection, and PAC parsing.

---

## 2. Version Synchronization & Release Verification

- **Version Synchronized**:
  - `flashdock/__init__.py`: `__version__ = "1.6.0"`
  - `flashdock/constants.py`: `APP_VERSION = "1.6.0"`
  - `version_info.txt`: `filevers=(1, 6, 0, 0)`, `prodvers=(1, 6, 0, 0)`
  - `scripts/version_info.txt`: `filevers=(1, 6, 0, 0)`, `prodvers=(1, 6, 0, 0)`
  - `flashdock.spec`: Registered all 8 new modules in `hidden_imports`.
- **Release Commands**:
  ```powershell
  # 1. Run complete test suite (656 tests)
  python -m pytest tests/ -q

  # 2. Compile standalone Windows executable & ZIP distribution
  python scripts/release_build.py
  ```
