---
title: "FlashDock — Master Architectural Upgrade, Hardening & v1.5.0 Release Plan"
type: execution-plan
status: ready
version: 1.5.0
date: 2026-10-15
skills_applied:
  # Primary Hardware, Android & Ecosystem Authorities
  - flashdock-workstation
  - android-cli
  - find-skills
  # Engineering Suite (.agents/skills/engineering/ & skills-from github)
  - engineering/ask-matt
  - engineering/code-review
  - engineering/codebase-design
  - engineering/diagnosing-bugs
  - engineering/domain-modeling
  - engineering/grill-with-docs
  - engineering/implement
  - engineering/implement-spec
  - engineering/improve-codebase-architecture
  - engineering/pr
  - engineering/prototype
  - engineering/research
  - engineering/retro
  - engineering/setup-matt-pocock-skills
  - engineering/tdd
  - engineering/to-spec
  - engineering/to-tickets
  - engineering/triage
  - engineering/wayfinder
  - engineering/wizard
  # Productivity Suite (.agents/skills/productivity/ & skills-from github)
  - productivity/grill-me
  - productivity/grilling
  - productivity/handoff
  - productivity/teach
  - productivity/to-questionnaire
  - productivity/wait-what
  - productivity/writing-for-agents
  # In-Progress Architecture & Writing Suite (.agents/skills/in-progress/)
  - in-progress/chief-of-staff
  - in-progress/claude-handoff
  - in-progress/loop-me
  - in-progress/setup-ts-deep-modules
  - in-progress/writing-beats
  - in-progress/writing-fragments
  - in-progress/writing-shape
  # Quality Guardrails & Tooling Suite (.agents/skills/misc/)
  - misc/git-guardrails-claude-code
  - misc/migrate-to-shoehorn
  - misc/scaffold-exercises
  - misc/setup-pre-commit
  # Platform, Repository & Customization Governance
  - permissioned-github
  - readme-gen
  - agy-customizations
  - antigravity_guide
tags:
  - flashdock
  - v1.5.0
  - codebase-hardening
  - zero-brick
  - async-qt6
  - fuzz-testing
  - mmap-streaming
  - win32-hardware-events
  - github-sync
---

# ROLE & OBJECTIVE
You are a **Principal Systems Architect, Senior Python/Qt6 Desktop Engineer, and Low-Level Android Firmware Security Specialist**. You have full access to the **FlashDock (v1.4.0)** repository (`https://github.com/klein-sys/own-flasher`).

Your mission is to execute an exhaustive, file-by-file **Codebase Audit, Vulnerability & Failure-Mode Analysis, Code Hardening Pass, and v1.5.0 Architectural Upgrade Plan**, and then **immediately implement all fixes and package the complete updated files into a single AI-3 Distribution & GitHub Sync Markdown Bundle**.

FlashDock services physical Android hardware at the bootloader, partition, and emergency boot-ROM levels; therefore, **systems reliability, concurrency safety, and zero-brick guarantees are absolute, non-negotiable laws.**

---

## MANDATORY AGENT SKILLS ACTIVATION & GOVERNING LAWS

Before auditing or writing any code, you must strictly activate and adhere to the following curated skills discovered and verified in `.agents/skills/` and `.agents/skills-from github/skills/`:

### 1. Primary Hardware, Android & Ecosystem Authorities
1. **`flashdock-workstation` (`.agents/skills/flashdock-workstation/SKILL.md`) — [PRIMARY WORKSTATION LAW]**:
   - **Zero-Brick Pre-Flight Gates**: Battery $\ge 30\%$, active partition slot confirmed (`_a`/`_b`), and mandatory auto-rescue calibration dumps (`efs`, `nvram`, `nvdata`, `persist`, `sec_efs`) with SHA-256 validation to `data/backups/emergency_preflash/`.
   - **Anti-Rollback & Anti-Relock Law**: Never allow bootloader relocking (`fastboot flashing lock`, `oem lock`) if a custom recovery, patched boot image, or cross-region firmware is installed.
   - **Asynchronous Qt6 Rule**: Zero synchronous subprocesses, heavy disk I/O, or registry polling on the PySide6 main GUI thread. All background routines must inherit from `QThread` and support cooperative cancellation (`requestInterruption()`, `isInterruptionRequested()`).
   - **Design Token Standard**: 100% vector SVG rendering via `flashdock.ui.icon_assets.get_icon()` dynamically generated on demand. Zero raw unicode emoji stickers.
   - **Release Pipeline Enforcement**: Bump version to `1.5.0` (`flashdock/__init__.py`, `constants.py`, `version_info.txt`, `README.md`, `read.md`, `handoff.md`), run `python scripts/release_build.py` (ensure 100% test pass), compile `dist/FlashDock-v1.5.0-windows-x64.zip`, and sync to GitHub `main` with release tags.
2. **`android-cli` (`.agents/skills/android-cli/SKILL.md`) — [OFFICIAL ANDROID CLI & PLATFORM TOOLS LAW]**:
   - Governs low-level Android SDK management, ADB shell layout inspection, screen hierarchy capture, and end-to-end device journey testing directly against physical and virtual hardware targets.
3. **`find-skills` (`.agents/skills/find-skills/SKILL.md`) — [DYNAMIC SKILL EXTENSION & ECOSYSTEM CAPABILITY]**:
   - Integrates the open agent skills ecosystem (`npx skills`), allowing dynamic discovery, verification, and installation of specialized firmware, USB protocol, and packaging workflows.

### 2. Complete Engineering Suite (`.agents/skills/engineering/` & `.agents/skills-from github/skills/engineering/`)
4. **`engineering/ask-matt` (`.agents/skills/engineering/ask-matt/SKILL.md`) — [SKILLS META-ROUTER & TAXONOMY]**:
   - Meta-router over the engineering skill library; resolves phase boundaries, skill handoffs, and procedural selection throughout complex multi-stage refactoring workflows.
5. **`engineering/diagnosing-bugs` (`.agents/skills/engineering/diagnosing-bugs/SKILL.md`) — [FAILURE ANALYSIS DISCIPLINE]**:
   - Build tight, deterministic reproduction loops for all race conditions, pipe deadlocks, buffer exhaustion, and memory leaks before implementing patches.
   - Treat edge cases (pipe exhaustion, TOCTOU races, process tree termination) with scientific rigor rather than superficial try/except wrapping.
6. **`engineering/codebase-design` (`.agents/skills/engineering/codebase-design/SKILL.md`) — [DEEP MODULE SPECIFICATION]**:
   - Design **deep modules** with small interfaces and rich implementations (high leverage for callers, strict locality for maintainers).
   - Place clean **seams** where hardware transports, platform APIs, and parsers can be mocked, tested, or swapped without editing caller logic.
7. **`engineering/improve-codebase-architecture` (`.agents/skills/engineering/improve-codebase-architecture/SKILL.md`) — [ARCHITECTURAL DEEPENING & STREAMING]**:
   - Surface architectural friction and turn shallow pass-through wrappers into deep engines.
   - Enforce locality and eliminate leaking abstractions across seams (e.g., zero-copy `mmap` streaming for `payload_dumper.py` and `lz4_util.py`).
8. **`engineering/tdd` (`.agents/skills/engineering/tdd/SKILL.md`) — [VERIFICATION & FUZZING FIRST]**:
   - Construct property-based boundary tests and fuzzing suites in `tests/test_fuzz_parsers.py` before finalizing parser implementations to guarantee uncrashable binary parsing.
9. **`engineering/code-review` (`.agents/skills/engineering/code-review/SKILL.md`) — [STANDARDS & SMELL ELIMINATION]**:
   - Two-axis review of every change: Standards (Python 3.10–3.14 strict typing, PEP 706 `tarfile` data filters) and Spec (faithful execution of all Pillars).
   - Eliminate Fowler code smells: Primitive Obsession, Data Clumps, Shotgun Surgery, and Divergent Change.
10. **`engineering/implement-spec` (`.agents/skills/engineering/implement-spec/SKILL.md`) — [TASK GRAPH EXECUTION]**:
    - Execute the plan as an acyclic task graph across the frontier of ready modules, ensuring dependent subsystems integrate cleanly.
11. **`engineering/implement` (`.agents/skills/engineering/implement/SKILL.md`) — [PRODUCTION CODE REALIZATION]**:
    - Direct, uncompromising implementation of spec and ticket requirements; produces complete, robust, production-grade files without shortcuts or stubs.
12. **`engineering/pr` (`.agents/skills/engineering/pr/SKILL.md`) — [PULL REQUEST & RELEASE NOTES ARCHETYPE]**:
    - Formats GitHub Release Notes and PR summaries using the high-signal template: Call-Tree Summary, Before/After Evidence, Door classification (one-way vs two-way), and Blast Radius analysis.
13. **`engineering/domain-modeling` (`.agents/skills/engineering/domain-modeling/SKILL.md`) — [DOMAIN TAXONOMY & ADRS]**:
    - Build and maintain FlashDock's domain terminology (partition maps, EDL handshakes, sparse chunks, vbmeta flags) and document architectural decisions via structured ADRs.
14. **`engineering/grill-with-docs` (`.agents/skills/engineering/grill-with-docs/SKILL.md`) — [INTERACTIVE ARCHITECTURAL SHARPENING]**:
    - Relentless technical inquiry to stress-test designs while generating living ADRs and glossary documentation.
15. **`engineering/prototype` (`.agents/skills/engineering/prototype/SKILL.md`) — [LOW-LEVEL PROTOCOL PROTOTYPING]**:
    - Build throwaway test harnesses to validate low-level binary framing (Unisoc BROM challenge-response, Odin v3/v4 framing, WinUSB bulk transfers) before committing production modules.
16. **`engineering/research` (`.agents/skills/engineering/research/SKILL.md`) — [PRIMARY SOURCE VERIFICATION]**:
    - Investigate firmware structures against authoritative primary sources (AOSP `system/core/fastboot`, Android Verified Boot 2.0 specs, Linux USB subsystem docs) and capture findings in repository markdown.
17. **`engineering/retro` (`.agents/skills/engineering/retro/SKILL.md`) — [POST-SPRINT RETROSPECTIVE]**:
    - Conduct structured retrospectives on completed sprints to evaluate stability, test coverage, and execution velocity.
18. **`engineering/setup-matt-pocock-skills` (`.agents/skills/engineering/setup-matt-pocock-skills/SKILL.md`) — [ENGINEERING VOCABULARY SETUP]**:
    - Configures repository issue trackers, triage labels, and domain doc layouts for uniform engineering skill execution.
19. **`engineering/to-spec` (`.agents/skills/engineering/to-spec/SKILL.md`) — [SPECIFICATION SYNTHESIS]**:
    - Synthesizes conversational context and technical requirements into structured, actionable engineering specifications.
20. **`engineering/to-tickets` (`.agents/skills/engineering/to-tickets/SKILL.md`) — [TRACER-BULLET TICKETING]**:
    - Deconstructs large specifications into dependency-ordered tracer-bullet tickets with explicit blocking edges.
21. **`engineering/triage` (`.agents/skills/engineering/triage/SKILL.md`) — [BUG TRIAGE & STATE MACHINE]**:
    - Manages issue triage through structured verification states, separating genuine firmware regressions from driver or cable faults.
22. **`engineering/wayfinder` (`.agents/skills/engineering/wayfinder/SKILL.md`) — [STRATEGIC MILESTONE NAVIGATION]**:
    - Maps complex multi-session architectural evolutions as a network of decision tickets, resolving blockers sequentially until the milestone is clear.
23. **`engineering/wizard` (`.agents/skills/engineering/wizard/SKILL.md`) — [INTERACTIVE GUIDED SCRIPTS]**:
    - Generates interactive, guided command-line wizards for human-in-the-loop firmware recovery steps (e.g., test-point shorting, emergency EDL button combinations).

### 3. Complete Productivity Suite (`.agents/skills/productivity/` & `.agents/skills-from github/skills/productivity/`)
24. **`productivity/writing-for-agents` (`.agents/skills/productivity/writing-for-agents/SKILL.md`) — [AGENT EXECUTION RIGOR]**:
    - Eliminates premature completion risks by defining strict, checkable, and exhaustive completion criteria across all output sections.
25. **`productivity/handoff` (`.agents/skills/productivity/handoff/SKILL.md`) — [AGENT COMPACTION & RESUME STATE]**:
    - Keeps handoff documentation tightly synchronized so future agent sessions or subagents can continue seamlessly without losing context.
26. **`productivity/grill-me` (`.agents/skills/productivity/grill-me/SKILL.md`) — [INTENT CLARIFICATION & STRESS TESTING]**:
    - Conducts structured interviews to pressure-test execution plans, uncover hidden edge cases, and resolve architectural ambiguities.
27. **`productivity/grilling` (`.agents/skills/productivity/grilling/SKILL.md`) — [SYSTEMATIC EDGE-CASE GRILLING]**:
    - Rigorously questions every assumption regarding firmware flashing safety, partition offsets, and hardware timeout handling.
28. **`productivity/teach` (`.agents/skills/productivity/teach/SKILL.md`) — [IN-WORKSPACE KNOWLEDGE TRANSFER]**:
    - Generates clear, contextual tutorials and conceptual explanations for users and engineers working within the FlashDock workspace.
29. **`productivity/to-questionnaire` (`.agents/skills/productivity/to-questionnaire/SKILL.md`) — [DECISION QUESTIONNAIRE GENERATION]**:
    - Converts open architectural tradeoffs into structured, easily answered questionnaires when human domain choices are required.
30. **`productivity/wait-what` (`.agents/skills/productivity/wait-what/SKILL.md`) — [RAPID COURSE CORRECTION]**:
    - Immediately flags when an agent's approach has drifted off course or misunderstood critical hardware parameters, enforcing instant re-pitching.

### 4. Architecture Evolution & In-Progress Suite (`.agents/skills/in-progress/`)
31. **`in-progress/chief-of-staff` (`.agents/skills/in-progress/chief-of-staff/SKILL.md`) — [MULTI-AGENT COORDINATION]**:
    - Coordinates parallel subagents, task boundaries, and execution pacing for extensive multi-component sprints.
32. **`in-progress/claude-handoff` (`.agents/skills/in-progress/claude-handoff/SKILL.md`) — [ACTIVE TASK TRANSFER]**:
    - Packages in-flight state and outstanding test evidence for seamless transfer across agent runtimes.
33. **`in-progress/loop-me` (`.agents/skills/in-progress/loop-me/SKILL.md`) — [WORKFLOW SPECIFICATION LOOPS]**:
    - Guides iterative refinement loops for newly added flasher workflows and firmware extraction utilities.
34. **`in-progress/setup-ts-deep-modules` (`.agents/skills/in-progress/setup-ts-deep-modules/SKILL.md`) — [MODULE BOUNDARY ENFORCEMENT]**:
    - Enforces strict module isolation, preventing leaky internal dependencies across subsystem boundaries.
35. **`in-progress/writing-beats` (`.agents/skills/in-progress/writing-beats/SKILL.md`) — [TECHNICAL WALKTHROUGH BEATS]**:
    - Structures release guides and firmware instructions into sequentially grounded steps where concepts are established before use.
36. **`in-progress/writing-fragments` (`.agents/skills/in-progress/writing-fragments/SKILL.md`) — [RAW INSIGHT CAPTURE]**:
    - Captures raw low-level debugging insights, USB trace outputs, and binary disassembly notes prior to formal documentation.
37. **`in-progress/writing-shape` (`.agents/skills/in-progress/writing-shape/SKILL.md`) — [TECHNICAL DOCUMENTATION SHAPING]**:
    - Shapes raw firmware audit logs and benchmark figures into clear, cohesive technical changelogs and manuals.

### 5. Quality Guardrails & Tooling Suite (`.agents/skills/misc/`)
38. **`misc/git-guardrails-claude-code` (`.agents/skills/misc/git-guardrails-claude-code/SKILL.md`) — [DESTRUCTIVE GIT GUARD]**:
    - Enforces safety hooks blocking destructive git commands (`git push --force`, `git reset --hard`, `git clean -fdx`) on production branches.
39. **`misc/migrate-to-shoehorn` (`.agents/skills/misc/migrate-to-shoehorn/SKILL.md`) — [TYPE ASSERTION HARDENING]**:
    - Eliminates unsafe type casting and loose mock objects in unit test suites in favor of strongly-typed partial fixtures.
40. **`misc/scaffold-exercises` (`.agents/skills/misc/scaffold-exercises/SKILL.md`) — [TEST SUITE SCAFFOLDING]**:
    - Scaffolds modular test structures, fixtures, and regression cases ensuring full coverage of newly added parsing logic.
41. **`misc/setup-pre-commit` (`.agents/skills/misc/setup-pre-commit/SKILL.md`) — [PRE-COMMIT VERIFICATION GATES]**:
    - Integrates automated pre-commit verification hooks for code formatting, static type checking, and test suites prior to git commits.

### 6. Platform, Repository & Customization Governance
42. **`permissioned-github` (`.agents/skills/permissioned-github/SKILL.md`) — [AUTHORITATIVE GITHUB PROTOCOL]**:
    - Directs all GitHub interactions through authoritative `gh` CLI commands specifying `-R klein-sys/own-flasher` and standard `git` branch/tag operations. Prohibits ad-hoc scripts or insecure tokens.
43. **`readme-gen` (`.agents/skills/Readme-gen/SKILL.md`) — [REPOSITORY DOCUMENTATION INTEGRITY]**:
    - Updates `README.md` and repository documentation grounded in verified codebase evidence. Reflects the v1.5.0 architecture with tech stack badges, Mermaid flow diagrams, setup guides, and test commands.
44. **`agy-customizations` (`.agents/skills/agy-customizations/SKILL.md`) — [ANTIGRAVITY CUSTOMIZATION SYSTEM]**:
    - Guides the configuration, structure, and loading hierarchy of skills, rules, plugins, hooks, and MCP servers across global and workspace roots.
45. **`antigravity_guide` (`.agents/skills/antigravity_guide/SKILL.md`) — [ANTIGRAVITY PLATFORM REFERENCE]**:
    - Complete reference for Antigravity IDE, CLI, SDK, slash commands, and multi-agent coordination capabilities.

---

### Strict Operational Rules
1. **No Placeholders or Hand-Waving**: Every bug you identify must be accompanied by exact file paths, line numbers, root-cause mechanics, and **100% complete, drop-in, production-ready Python/Qt6 code patches**. Never write `# TODO`, `pass`, or `# ... existing code ...` inside your file outputs.
2. **Evidence-Grounded Analysis**: Inspect the actual implementation in the workspace before diagnosing. Cross-reference callers, signal/slot signatures, and unit tests.
3. **Preserve Design & Safety Mandates**:
   - Maintain 100% vector SVG rendering (`flashdock/ui/icon_assets.py`) — zero raw unicode emoji stickers.
   - Maintain 100% non-blocking GUI execution — zero synchronous subprocess or heavy disk I/O on the main PySide6 thread.
   - Maintain zero external C-extension dependencies for core parsers (pure-Python standard library for RSA-2048, LZ4, Protobuf OTA payload, and GKI headers).

---

## PILLAR 1: FAILURE MODE & EDGE-CASE ERROR ANALYSIS

Perform a deep-dive static and architectural audit across the following four domains. Trace every execution path under worst-case hardware, OS, and user conditions:

### 1.1 Subprocess, Pipe I/O & Archive Parser Hazards
- **Pipe Buffer Deadlocks (`flashdock/tools/runner.py`, `adb.py`, `fastboot.py`)**:
  - Audit how `subprocess.run` and `subprocess.Popen` capture `stdout` and `stderr`. During multi-gigabyte `super.img` sparse writes or verbose `adb logcat` / `fastboot` streams, check if sequential reading or unbuffered pipes can exhaust the 64 KB Win32 anonymous pipe buffer and deadlock the child process.
- **Zombie Processes & Orphaned Subtrees (`runner.py`, `scrcpy.py`, `flash_engine.py`)**:
  - When a user yanks the USB cable mid-flash, cancels a task, or closes FlashDock, verify whether `adb.exe`, `fastboot.exe`, or `scrcpy.exe` child processes hang indefinitely in the background holding USB/COM handles. Check if `subprocess.TimeoutExpired` handlers properly terminate the entire process tree (e.g., via Win32 Job Objects or `taskkill /F /T /PID`) rather than leaving zombie children.
- **Pure-Python Parser Stalls & Memory Exhaustion (`payload_dumper.py`, `lz4_util.py`, `return_stock.py`, `unisoc.py`)**:
  - **`payload_dumper.py`**: Audit varint decoding (`_read_varint`), protobuf wire-type skipping, and `bz2`/`lzma` decompression streams against truncated or corrupted `.bin` / `.zip` files. Verify that an unexpected EOF or malformed manifest length cannot trigger an infinite loop (`while True` reading `b""`) or allocate a multi-gigabyte `bytearray` in RAM all at once.
  - **`lz4_util.py`**: Audit block and frame decompression for maliciously crafted or corrupted match offsets (`offset == 0` or `offset > len(dst)`), overlapping copy loops, and unvalidated uncompressed size headers in Samsung `.tar.md5` archives.
  - **`return_stock.py` & `rom_flasher.py`**: Check `zipfile` and `tarfile` extraction routines for Zip-Slip (path traversal via `../`), disk space exhaustion in `tempfile.TemporaryDirectory`, and unclosed file handles on extraction failure.

### 1.2 Concurrency, Thread Safety & Qt6 Lifecycle Bugs
- **Hardware Polling vs. Active Flashing Race Conditions (`device_monitor.py`, `device_manager.py`, `flash_shield.py`, `runner.py`)**:
  - Audit the synchronization between `DeviceMonitorWorker` (1.5s polling loop), `DeviceManager`, and active flashing workers (`FlashEngineWorker`, `RomFlashWorker`, `GsiFlashWorker`, `RootFlashWorker`, `BackupWorker`, `UnisocWorker`).
  - Verify whether a Time-of-Check to Time-of-Use (TOCTOU) race exists where `DeviceMonitorWorker` fires `adb devices` or `fastboot devices` at the exact millisecond a screen worker initiates a partition write or bootloader reboot—causing USB bus contention or `fastboot` command failure.
  - Check if `acquire_flash_lock()` / `release_flash_lock()` is thread-safe (protected by a `threading.Lock` or counting semaphore) and guaranteed to release even if an unhandled exception occurs inside a worker thread.
- **`QThread` Lifecycle & C++ Teardown Violations (`main_window.py` & all `ui/screens/*.py`)**:
  - Audit every custom `QThread` subclass across all screens (`flash_rom_screen.py`, `root_screen.py`, `backup_screen.py`, `mtk_unisoc_screen.py`, `downloads_screen.py`, `sideload_screen.py`).
  - Identify any local `QThread` references that can be garbage-collected by Python while the underlying Qt C++ thread is still running (`QThread: Destroyed while thread is still running`), or threads that are not cooperatively stopped and waited on (`wait()`) during `MainWindow.closeEvent()`.
- **High-Frequency Telemetry UI Starvation (`side_terminal.py`, `logger/__init__.py`)**:
  - Trace what happens when a background worker emits hundreds of `log_emitted` signals per second. Check if `SideTerminalWidget` performs synchronous DOM/HTML insertion and `QPlainTextEdit` re-layout on every single line without line-count capping (`maximumBlockCount`) or 30–60 Hz timer batching, which can freeze the Qt event loop.

### 1.3 Hardware Protocol & Low-Level Recovery Edge Cases
- **Fastboot vs. FastbootD State Ambiguity (`device.py`, `fastboot.py`, `rom_flasher.py`)**:
  - Verify how `is-userspace` is queried and cached. If a device transitions from Bootloader (`fastboot`) to Userspace (`fastbootd`) during dynamic partition (`super`, `system`, `product`) flashing, verify that FlashDock re-validates the mode and waits for USB re-enumeration before issuing `fastboot flash` or `fastboot resize-logical-partition`.
- **Interrupted A/B Slot Switching & Unbootable States (`main_window.py`, `bootloop_fixer.py`, `flash_engine.py`)**:
  - Audit `set_active_slot` / `--set-active` execution. Check how FlashDock handles bootloaders that report `Slot _b is unbootable` or require `fastboot: usage: unknown command` fallback syntax (`fastboot set_active b` vs `fastboot --set-active=b`).
- **Partial `vbmeta` & Anti-Red-State Writes (`unisoc.py`, `rom_flasher.py`, `bootloop_fixer.py`)**:
  - Audit `generate_disabled_vbmeta()` and `flash_vbmeta_disabled()`. Verify that the generated 256-byte AVB 2.0 header (`AVB0`) has the exact big-endian magic, version, and flags offset (`offset 123 = 0x03`) required by strict BootROMs, and check what happens if `vbmeta_system` or `vbmeta_vendor` remain enabled while root `vbmeta` is disabled.
- **Driver Elevation & Raw Partition Dump Edge Cases (`tools_manager.py`, `backup.py`)**:
  - In `tools_manager.py`: Audit `_execute_pnputil_install()` and PowerShell `-Verb RunAs` elevation. Check for path-escaping bugs when workspace paths contain spaces or apostrophes, non-English Windows locale output where `"Failed to add"` is translated, and `pnputil` exit code `3010` (`ERROR_SUCCESS_REBOOT_REQUIRED`) being misinterpreted as a failure.
  - In `backup.py`: Audit raw partition dumping (`dd if=/dev/block/by-name/...`) over ADB in both rooted System mode (`su -c`) and custom Recovery mode (`uid=0`). Verify that binary/stdout corruption (CRLF `\r\n` translation on Windows) cannot corrupt dumped `.img` files and invalidate SHA-256 calibration backups.

### 1.4 Python 3.10–3.14 Compatibility & Typing Audit
- **Python 3.14 Strictness**:
  - Audit `tarfile.extractall()` calls for Python 3.12–3.14 PEP 706 `filter="data"` requirements and deprecation/security behavior.
  - Audit `winreg` key enumeration loops in `device_monitor.py` to ensure `winreg.OpenKey` handles are deterministically closed via context managers (`with winreg.OpenKey(...)`) so registry handles never leak across thousands of 1.5s polling cycles.
  - Check `ctypes` windll calls, type annotations (`from __future__ import annotations`), and `PySide6` `@Slot` decorators for signature mismatches that cause silent signal drop-outs in Qt 6.10.

---

## PILLAR 2: DEPENDENCY, BINARY & ENVIRONMENT AUDIT

1. **Packaging & PyInstaller Spec (`requirements.txt`, `flashdock.spec`, `scripts/release_build.py`)**:
   - Inspect `flashdock.spec` and `requirements.txt`. Verify that all new modules (`payload_dumper`, `lz4_util`, `sideload`, `unisoc`, `header_inspector_dialog`, `reboot_switchboard`, etc.) and required Qt6 plugins (`Qt6Svg`, `qsvg.dll`, `qwindows.dll`) are explicitly bundled so the standalone `FlashDock.exe` never crashes with `ModuleNotFoundError` or blank SVG icons on a clean Windows machine without Python installed.
2. **External Toolchain Sandboxing & Verification (`tools_manager.py`, `constants.py`)**:
   - Audit how `adb.exe`, `fastboot.exe`, and `scrcpy.exe` are resolved (`data/tools/platform-tools/` vs. system `PATH`).
   - Check if `PATH` hijacking (DLL/binary planting in the working directory) is possible, and verify how FlashDock handles corrupted downloads or partial zip extractions when auto-installing `platform-tools`.
3. **Windows OS & Security Environment (`scripts/sign_app.ps1`, `scripts/dist_helpers/*.bat`)**:
   - Audit `sign_app.ps1` and the `.bat` helper launchers for PowerShell execution policy blocks, non-admin certificate store errors, and NTFS `Zone.Identifier` alternate data stream stripping.

---

## PILLAR 3: CONCRETE REMEDIATION & CODE HARDENING

Execute fixes across the codebase using defensive engineering patterns:
- Thread-safe reentrant locks (`threading.RLock` / `QMutexLocker`) around shared state and flash locks.
- Deterministic resource cleanup (`with` context managers for files, `winreg` keys, temp directories, and flash locks).
- Non-blocking pipe readers or bounded timeouts with process-tree termination on subprocess hangs.
- Strict input/header bounds checking before memory allocation in binary parsers.

---

## PILLAR 4: ARCHITECTURAL & FEATURE ADVANCEMENTS (v1.5.0 UPGRADES)

Implement and integrate the following four **FlashDock v1.5.0** architectural upgrades directly into the codebase:

1. **Event-Driven Win32 Hardware Notifications (Replacing/Augmenting 1.5s Polling)**:
   - Implement a hybrid `DeviceMonitorWorker` that hooks into native Windows `WM_DEVICECHANGE` (`DBT_DEVICEARRIVAL`, `DBT_DEVICEREMOVECOMPLETE`) or uses event-driven signaling, reducing idle CPU/registry polling while triggering instant (<50ms) hardware state resolution when a BROM/EDL/Fastboot device is plugged in.
2. **Zero-Copy `mmap` Streaming in Binary Extractors (`payload_dumper.py` & `lz4_util.py`)**:
   - Refactor `PayloadDumper` and `LZ4Util` to support Python's `mmap.mmap` and `memoryview` zero-copy slices when reading local firmware archives, eliminating redundant buffer copies and maximizing NVMe extraction throughput.
3. **Low-Level Protocol Layer Expansion (`flashdock/tools/usb_transport.py`, `mtk.py`, `unisoc.py`)**:
   - Implement a pure-Python `ctypes` WinUSB / SetupAPI / Serial transport abstraction (`flashdock/tools/usb_transport.py`) capable of performing real hardware handshakes (Qualcomm Sahara Hello packet `0x01`, MTK BROM `0xA0 0x0A 0x50 0x05` echo check, and Unisoc HDLC `0x7E` ping) directly over Win32 `CreateFileW` / `DeviceIoControl` handles without requiring external `pyusb` or `pyserial` C-dependencies.
4. **Property-Based Binary Parser Fuzzing Suite (`tests/test_fuzz_parsers.py`)**:
   - Write a comprehensive unit and fuzzing test module that feeds randomized, truncated, bit-flipped, and boundary-value byte streams into `RootingEngine.validate_boot_image()`, `PayloadDumper`, `LZ4Util`, `UnisocUnlockManager`, and `PartitionHeaderInspectorDialog` to guarantee that malformed firmware files never raise unhandled exceptions.

---

## PILLAR 5: IMMEDIATE EXECUTION & AI-3 DISTRIBUTION BUNDLE (CRITICAL OUTPUT FORMAT)

Do NOT stop at diagnosing or suggesting patches. **Execute all fixes and v1.5.0 upgrades immediately**, update the repository files, and format your entire final response as a single, self-contained **Master Implementation & GitHub Distribution Markdown Document** designed to be handed directly to **AI-3** (an automated file-management and GitHub deployment agent).

Structure your final Markdown output using these exact 5 top-level sections:

### Section 1: `# 1. Prioritized Defect & Risk Matrix`
Output the comprehensive Markdown table ranking every identified bug, vulnerability, or edge-case hazard:
| ID | Severity (`CRITICAL` / `HIGH` / `MEDIUM` / `LOW`) | File & Line(s) | Failure Trigger / Scenario | Root Cause Analysis | Exact Remediation Implemented |

### Section 2: `# 2. File Manifest & Action Plan for AI-3`
Provide a strict checklist of every file in the repository that AI-3 needs to `MODIFY`, `CREATE`, or `DELETE`, using exact relative paths from the repository root (e.g., `flashdock/tools/runner.py`, `flashdock/tools/usb_transport.py`, `tests/test_fuzz_parsers.py`, `flashdock.spec`, `README.md`).

### Section 3: `# 3. Complete Production File Contents for AI-3`
For **every single file** listed in Section 2, output a sub-header with its exact relative path (`### File: path/to/file.py`) followed by the **complete, 100% unabridged file content** inside a fenced code block (or exact, cleanly applicable unified diff if the file exceeds output token limits, though full file replacements are strongly preferred so AI-3 can overwrite files deterministically without merge conflicts).

### Section 4: `# 4. Verification & Test Suite Commands for AI-3`
Provide the exact PowerShell command sequence for AI-3 to execute after writing the files to verify the build:
- Running the full existing + new fuzzing test suite (`python -m pytest tests/ -q`).
- Verifying PyInstaller spec compilation and SHA-256 signing (`python scripts/release_build.py`).

### Section 5: `# 5. Git & GitHub Deployment Instructions for AI-3`
Provide a copy-pasteable PowerShell script block and release metadata for AI-3 to sync the changes to `https://github.com/klein-sys/own-flasher` (adhering strictly to `.agents/skills/permissioned-github/SKILL.md` and `.agents/skills/engineering/pr/SKILL.md`):
1. Exact `git status`, `git add`, and structured conventional commit command (`git commit -m "feat(v1.5.0): ..."`).
2. Version tag creation (`git tag -a v1.5.0 -m "..."`) and `git push origin main --tags` (or `gh` CLI commands targeted to `-R klein-sys/own-flasher`).
3. A complete, polished **GitHub Release Notes / Pull Request Body** formatted according to `.agents/skills/engineering/pr/SKILL.md` (Summary with Call-Tree, Evidence Before/After, Door: Two-Way, Blast Radius) and `.agents/skills/Readme-gen/SKILL.md`.

Begin your audit and implementation now.
