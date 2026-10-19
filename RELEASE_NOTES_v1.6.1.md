# FlashDock v1.6.1 Release Notes

## Summary

Upgrades **FlashDock** from `v1.6.0` to `v1.6.1` with the complete implementation of the APK Pre-Flight Verifier, Atomic Staging, and Android 14 APK Signature Scheme v3 Diagnostics, resolving `INSTALL_PARSE_FAILED_NO_CERTIFICATES` sideloading errors.

1. **Pure-Python APK Pre-Flight Verifier (`flashdock/core/apk_verifier.py`)**:
   - Zero-modification passthrough: prevents in-place zip modifications and timestamp re-compressions that invalidate cryptographic signature digests.
   - Streaming SHA-256 computation in 1 MB chunks without memory bloat.
   - Pure-Python ZIP Central Directory and End-of-Central-Directory (`PK\x05\x06`) parsing with APK Signature Scheme v2/v3 magic header detection (`APK Sig Block 42`).
   - Comprehensive internal CRC-32 integrity inspection across all archive entries via `zipfile.testzip()`.
   - Rejection of corrupt or missing manifests (`AndroidManifest.xml`) before wasting USB bandwidth.

2. **Atomic Staging with Parity Verification (`stage_apk_atomically`)**:
   - Fast path: directly passes pure-ASCII paths to `adb install` with zero temp file staging.
   - Controlled staging: only stages to `%TEMP%` when non-ASCII path characters would break Windows CLI utilities.
   - Strict `flush()`, `os.fsync()`, and SHA-256 parity verification against unflushed Windows file handle buffers.

3. **Glass-Box Sideload Error Classification (`classify_adb_install_error`)**:
   - Translates raw PackageManager `INSTALL_PARSE_FAILED_NO_CERTIFICATES` failures into actionable, human-readable diagnostics.
   - Specifically isolates `SHA-256 digest of contents did not verify` failures caused by modified APKs or incomplete extractions, providing exact remediation instructions for re-signing or CorePatch usage on rooted devices.

4. **Sideload Screen Live Telemetry (`flashdock/ui/screens/sideload_screen.py`)**:
   - Live pre-flight inspection logs displaying package signature status (v1 JAR / v2/v3 APK Sig Block) and SHA-256 hash immediately upon file selection.

---

## Architecture & Subsystem Tree

```text
FlashDock Sideload Subsystem
 ├── flashdock.core.apk_verifier
 │    ├── compute_sha256()                      [Streaming 1 MB chunk SHA-256 calculator]
 │    ├── _detect_apk_sig_block_v2_v3()         [Pure-Python APK Sig Block 42 detector]
 │    ├── verify_apk_preflight()                [Pre-flight CRC-32 & signature integrity gate]
 │    ├── stage_apk_atomically()                [Non-ASCII safe staging with fsync & parity]
 │    └── classify_adb_install_error()          [Actionable PackageManager error translator]
 ├── flashdock.tools.sideload
 │    ├── install_apk()                         [Pre-flight verification + atomic staging gate]
 │    └── install_split_bundle()                [Base APK pre-flight gate for bundle installs]
 └── flashdock.ui.screens.sideload_screen
      └── _on_file_selected()                   [High-DPI live pre-flight inspection & telemetry]
```

---

## File Manifest & Deliverables

1. **Core Verification Engine**:
   - `flashdock/core/apk_verifier.py` (272 lines): Pure-Python APK pre-flight verifier, atomic staging, and error classification.
2. **Toolchain Integration**:
   - `flashdock/tools/sideload.py`: Integrated `verify_apk_preflight()`, `stage_apk_atomically()`, and `classify_adb_install_error()`.
3. **UI Enhancements**:
   - `flashdock/ui/screens/sideload_screen.py`: Live pre-flight feedback in metadata inspection card.
4. **Test Suite**:
   - `tests/test_apk_verifier.py` (28 unit & integration tests).
   - `tests/test_sideload.py`: Updated mock tests for pre-flight compatibility (15 tests).
5. **Configuration & Distribution**:
   - `flashdock/__init__.py`: Bumped to `1.6.1`.
   - `flashdock/constants.py`: Bumped `APP_VERSION` to `1.6.1`.
   - `version_info.txt` & `scripts/version_info.txt`: Bumped to `1.6.1.0`.
   - `flashdock.spec`: Registered `flashdock.core.apk_verifier` in `hidden_imports`.
   - `README.md` & `handoff.md`: Synchronized documentation, badges, and verification results.

---

## Test & Release Verification

- **Total Passing Tests**: **684 passing tests** across 56 test modules (100% pass rate with zero failures and zero regressions).
- **Pure-Python Standard Library**: Zero external C-extensions.
- **Stand-alone Executable**: Compiled via PyInstaller 6.13 with Authenticode SHA-256 code signing.
