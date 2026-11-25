# FlashDock — Engineering Handoff & Session State

- **Current Version**: `v1.7.4` (Monochrome Liquid Glass workstation)
- **Repository**: `https://github.com/klein-sys/own-flasher`
- **Runtime**: Python 3.10–3.14 (verified on Python 3.14.7) | PySide6 (Qt 6.12) | Windows 10/11 x64
- **Test Suite Status**: 698 tests in the publication snapshot across 57 test modules.

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

### Milestone 1.6.1: APK Pre-Flight Verifier & Android 14 v3 Signature Protection
- **Core Engine (`flashdock/core/apk_verifier.py`)**:
  - Implemented 100% pure-Python APK pre-flight verifier (`verify_apk_preflight()`) adhering to zero-external C extensions.
  - Zero-modification passthrough: prevents in-place zip modification / timestamp re-compression that invalidates cryptographic signature digests.
  - Pure-Python streaming SHA-256 computation (`compute_sha256()`).
  - Pure-Python ZIP Central Directory and End-of-Central-Directory (`PK\x05\x06`) parsing with APK Signature Scheme v2/v3 magic header detection (`APK Sig Block 42`).
  - Comprehensive internal CRC-32 integrity inspection via `zipfile.testzip()`.
  - Atomic staging (`stage_apk_atomically()`): stages APKs to `%TEMP%` strictly when required for non-ASCII path characters with mandatory `flush()`, `os.fsync()`, and SHA-256 parity verification.
  - Glass-Box diagnostic classification (`classify_adb_install_error()`): maps raw `INSTALL_PARSE_FAILED_NO_CERTIFICATES` (including `SHA-256 digest of contents did not verify`) to actionable troubleshooting remediation steps.
- **Sideload Engine & UI Integration**:
  - `flashdock/tools/sideload.py`: Integrated pre-flight gate and atomic staging into `install_apk()` and `install_split_bundle()`. Integrated error classification into stderr handling.
  - `flashdock/ui/screens/sideload_screen.py`: Live pre-flight telemetry and signature block status (v1 JAR / v2/v3 APK Sig Block) in file inspection card.
- **Test Verification (`tests/test_apk_verifier.py` & `tests/test_sideload.py`)**:
  - 28 new tests in `test_apk_verifier.py` covering hash verification, signing block detection, CRC failures, atomic staging parity, and error classification.
  - Updated `test_sideload.py` with 15 passing tests. Total suite: 684/684 tests passing.

---

## 2. Version Synchronization & Release Verification

- **Version Synchronized**:
  - `flashdock/__init__.py`: `__version__ = "1.7.0"`
  - `flashdock/constants.py`: `APP_VERSION = "1.7.0"`
  - `version_info.txt`: `filevers=(1, 7, 0, 0)`, `prodvers=(1, 7, 0, 0)`
  - `scripts/version_info.txt`: `filevers=(1, 7, 0, 0)`, `prodvers=(1, 7, 0, 0)`
  - `flashdock.spec`: Registered `flashdock.core.apk_verifier` in `hidden_imports`.
- **Release Commands**:
  ```powershell
  # 1. Run the complete test suite
  python -m pytest tests/ -q

  # 2. Compile standalone Windows executable & ZIP distribution
  python scripts/release_build.py
  ```

### Milestone 1.7.0 — Monochrome Liquid Glass

- Phase 0 inspected the root `.agents` catalog and loaded the FlashDock workstation instructions before edits. The architecture maps `MainWindow` to the existing screen stack, `DeviceMonitorWorker` and `FlashEngineWorker`, with theme selection in `ui/styles.py` and vector rendering in `ui/icon_assets.py`.
- Four workflow sheets replace the individual home cards and OEM strip. Existing tool routes include Downloads and Logs & Help. Wireless ADB remains in Diagnostics and firmware extraction remains in its existing workflow.
- The island consumes existing `DeviceInfo` snapshots through queued Qt signals and `DeviceStateBroadcaster`. Hardware emergency modes take priority. Slot telemetry is read-only.
- Write-capable screen controls start locked and return to Safe after a device identity or mode change. Workflow validation remains in the existing engines.
- The compact sidebar has no scroll area. The activity console starts collapsed and retains the footer/header toggle.
- DWM Acrylic is requested through pointer-safe Windows calls. Unsupported systems use the painted ambient canvas.
- The icon generator produces 32 SVG files. The stylesheet and icons are included in `flashdock.spec`.
- The test fixtures close test-owned windows within the shared Qt application's lifetime. The local package starts through the normal application entry point in an offscreen check and reports FileVersion/ProductVersion 1.7.0.0.
- The build is unsigned and stored at `dist/liquid-glass-v1.7.0/FlashDock_Dist/FlashDock.exe`. The 52.1 MiB ZIP is `dist/FlashDock-v1.7.0-windows-x64.zip`. Source and bundled copies of the stylesheet and all 32 SVG files match byte for byte. The ZIP CRC check passed.
- Native DWM appearance has not been visually checked on the live desktop. Long tool forms and data lists still scroll. Dashboard previews use sample telemetry.
- The local working tree contains separate APK verifier, device-manager, and sideload edits. The publication snapshot covers Liquid Glass and the source launcher.

### Milestone 1.7.1 — Safe mode file selection

- APK and recovery ZIP drop zones remain available in Write: Safe. Device-changing actions require Write: Armed and a compatible ADB connection.

### Milestone 1.7.2 — APK integrity checks

- Inspect packages off the UI thread and keep installation disabled until validation passes. Reject unreadable archive entries without modifying the selected file. Preserve the original APK when installing from a relative path.

### Milestone 1.7.3 - Install review

- Keep readiness and the Arm Write action visible during package selection. Compare the installed app version and review the target, package, and options before writing.

### Milestone 1.7.4 — Windows distribution and developer handoff

- Run `Setup-FlashDock.bat` then `build.bat` in a clean source folder. The build verifies tests, stages the Windows runtime, and keeps a previous build in `dist/archive/` when replacing it.
- The Windows and developer ZIPs have separate quick starts and a shared release checksum file. Read [DEVELOPER-SETUP.md](DEVELOPER-SETUP.md) to continue work on another PC.
