"""
Pure-Python OEM Workflow Stage-Gate Engine for:
1. Xiaomi HyperOS 2.0 (ADB Mi Binding, Fastboot Anti-Rollback ARB Interlock, A/B Slot Check)
2. Samsung Knox-Safe (Download Mode KG STATE / Warranty Bit Gate, .tar.md5 Verifier, HOME_CSC vs CSC)
Zero external C-extensions.
"""
from __future__ import annotations

import hashlib
import mmap
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple, Union

try:
    from flashdock.tools.mmap_stream import open_mmap_view
except ImportError:
    @contextmanager
    def open_mmap_view(path: Union[str, Path]) -> Iterator[memoryview]:
        with open(path, "rb") as f:
            mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            mv = memoryview(mm)
            try:
                yield mv
            finally:
                mv.release()
                mm.close()

class OemWorkflowError(ValueError):
    """Raised when an OEM workflow input or archive fails validation."""

@dataclass(frozen=True)
class StageGateResult:
    stage_id: str
    passed: bool
    severity: str  # "SAFE", "WARNING", "BLOCKED"
    headline: str
    detail: str

@dataclass(frozen=True)
class XiaomiFastbootState:
    product: str
    unlocked: bool
    arb_index: int
    current_slot: str
    serialno: str = ""

@dataclass(frozen=True)
class SamsungDownloadState:
    model: str
    kg_state: str          # "Checking", "Completed", "Prenormal", "Locked", "Broken"
    warranty_void: int     # 0 (0x0 Untripped) or 1 (0x1 Tripped)
    frp_lock: bool         # True if FRP Lock: ON
    oem_lock: bool         # True if OEM Lock: ON (L)

# ============================================================================
# XIAOMI HYPEROS 2.0 STAGE CHECKERS
# ============================================================================
def parse_fastboot_getvar_all(stderr_or_stdout: str) -> XiaomiFastbootState:
    """
    Parse `fastboot getvar all` output into a structured XiaomiFastbootState.
    Handles `(bootloader) var: value` and direct `var: value` lines.
    """
    kv: Dict[str, str] = {}
    for raw_line in stderr_or_stdout.splitlines():
        line = raw_line.strip()
        if line.startswith("(bootloader)"):
            line = line[len("(bootloader)") :].strip()
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip().lower()] = v.strip()

    product = kv.get("product", "unknown")
    unlocked = kv.get("unlocked", "no").lower() in ("yes", "true", "1")
    try:
        arb_index = int(kv.get("anti", "0"))
    except ValueError:
        arb_index = 0
    current_slot = kv.get("current-slot", "a").lower() or "a"
    serialno = kv.get("serialno", "")

    return XiaomiFastbootState(
        product=product,
        unlocked=unlocked,
        arb_index=arb_index,
        current_slot=current_slot,
        serialno=serialno,
    )

def evaluate_xiaomi_hyperos_arb_gate(
    device_state: XiaomiFastbootState,
    target_rom_arb: int,
    expected_product: Optional[str] = None,
) -> StageGateResult:
    """
    Evaluate Xiaomi HyperOS 2.0 Fastboot Anti-Rollback (ARB) & Bootloader Unlock readiness.
    Strictly blocks flashing if `target_rom_arb < device_state.arb_index` to prevent EDL hard-bricks.
    """
    if expected_product and device_state.product.lower() != expected_product.lower():
        return StageGateResult(
            stage_id="xiaomi_arb_gate",
            passed=False,
            severity="BLOCKED",
            headline="Product Codename Mismatch",
            detail=(
                f"Connected device is '{device_state.product}', but ROM targets '{expected_product}'."
            ),
        )

    if not device_state.unlocked:
        return StageGateResult(
            stage_id="xiaomi_arb_gate",
            passed=False,
            severity="BLOCKED",
            headline="Bootloader Locked (HyperOS 2.0 Gate)",
            detail=(
                "Device bootloader is locked (`unlocked: no`). Complete Mi Community binding "
                "and unlock before flashing Fastboot images."
            ),
        )

    if target_rom_arb < device_state.arb_index:
        return StageGateResult(
            stage_id="xiaomi_arb_gate",
            passed=False,
            severity="BLOCKED",
            headline=f"CRITICAL ARB TRIPWIRE: Target ARB ({target_rom_arb}) < Device ARB ({device_state.arb_index})",
            detail=(
                f"Flashing ARB {target_rom_arb} onto a fuse-locked ARB {device_state.arb_index} board "
                "will permanently hard-brick the Primary Bootloader."
            ),
        )

    if target_rom_arb > device_state.arb_index:
        return StageGateResult(
            stage_id="xiaomi_arb_gate",
            passed=True,
            severity="WARNING",
            headline=f"ARB Fuse Increment Warning ({device_state.arb_index} -> {target_rom_arb})",
            detail=(
                f"Safe to flash, but this ROM will permanently increment hardware ARB e-fuse "
                f"from {device_state.arb_index} to {target_rom_arb} on slot '{device_state.current_slot}'."
            ),
        )

    return StageGateResult(
        stage_id="xiaomi_arb_gate",
        passed=True,
        severity="SAFE",
        headline=f"HyperOS 2.0 ARB Verified (ARB={device_state.arb_index}, Slot={device_state.current_slot.upper()})",
        detail="Bootloader unlocked, codename matched, and Anti-Rollback index is equal and safe.",
    )

# ============================================================================
# SAMSUNG KNOX-SAFE & ODIN (.tar.md5) STAGE CHECKERS
# ============================================================================
_TAR_MD5_TRAILER_RE = re.compile(rb"^([0-9a-fA-F]{32})\s+([^\r\n]+)[\r\n]*$")

def evaluate_samsung_knox_gate(
    state: SamsungDownloadState,
    is_custom_binary: bool = False,
) -> StageGateResult:
    """
    Evaluate Samsung Download Mode security flags (FRP, OEM Lock, KG STATE, and Knox Warranty Bit).
    """
    kg_norm = state.kg_state.strip().upper()
    if state.frp_lock:
        return StageGateResult(
            stage_id="samsung_knox_gate",
            passed=False,
            severity="BLOCKED",
            headline="FRP Lock Active (Factory Reset Protection)",
            detail="FRP Lock is ON. Enable OEM Unlocking in Developer Options before flashing.",
        )

    if is_custom_binary:
        if state.oem_lock:
            return StageGateResult(
                stage_id="samsung_knox_gate",
                passed=False,
                severity="BLOCKED",
                headline="OEM Lock Active — Custom Binary Blocked",
                detail="Hold Volume Up in Download Mode to unlock the bootloader before flashing custom images.",
            )
        if kg_norm in ("PRENORMAL", "LOCKED"):
            return StageGateResult(
                stage_id="samsung_knox_gate",
                passed=False,
                severity="BLOCKED",
                headline=f"Knox Guard `{state.kg_state}` — Custom Binary Blocked",
                detail=(
                    f"KG STATE is '{state.kg_state}'. Boot to OneUI, connect to Wi-Fi for 5 minutes, "
                    "and verify OEM Unlocking is visible in Developer Options to clear Prenormal state."
                ),
            )
        if state.warranty_void == 0:
            return StageGateResult(
                stage_id="samsung_knox_gate",
                passed=True,
                severity="WARNING",
                headline="Knox Warranty Bit Untripped (0x0 -> Will Become 0x1)",
                detail=(
                    "KG State allows custom binaries, but flashing will permanently trip the hardware "
                    "Knox e-fuse to 0x1 (disabling Samsung Pay, Pass, and Secure Folder)."
                ),
            )

    return StageGateResult(
        stage_id="samsung_knox_gate",
        passed=True,
        severity="SAFE",
        headline=f"Knox-Safe Ready (KG: {state.kg_state}, Warranty: 0x{state.warranty_void:X})",
        detail="Official signed Odin packages or verified target binaries can be safely staged.",
    )

def verify_samsung_tar_md5(path_or_buf: Union[str, Path, bytes, memoryview]) -> Tuple[bool, str, str]:
    """
    Verify a Samsung Odin `.tar.md5` archive by streaming the `.tar` body and comparing
    its MD5 digest against the trailing `<32-hex-md5>  <filename>` line.
    Returns (is_valid, expected_md5, computed_md5).
    """
    @contextmanager
    def _resolve_view(src: Union[str, Path, bytes, memoryview]) -> Iterator[memoryview]:
        if isinstance(src, (str, Path)):
            with open_mmap_view(src) as mv:
                yield mv
        else:
            yield memoryview(src)

    with _resolve_view(path_or_buf) as mv:
        total_len = len(mv)
        if total_len < 512 + 36:
            raise OemWorkflowError("Buffer too small to be a valid Samsung .tar.md5 package.")

        # Search the last 256 bytes for the newline boundary preceding the MD5 trailer
        tail_len = min(total_len, 256)
        tail_bytes = bytes(mv[total_len - tail_len :])

        # Strip trailing CR/LF first to find the start of the last line
        stripped_tail = tail_bytes.rstrip(b"\r\n")
        last_nl = stripped_tail.rfind(b"\n")
        if last_nl != -1:
            trailer_rel = last_nl + 1
            trailer_line = tail_bytes[trailer_rel:]
            tar_body_len = (total_len - tail_len) + trailer_rel
        else:
            # Trailer starts at the beginning of tail_bytes if file has no earlier newlines
            match_pos = re.search(rb"[0-9a-fA-F]{32}\s+[^\r\n]+[\r\n]*$", tail_bytes)
            if not match_pos:
                raise OemWorkflowError("Missing trailing MD5 checksum line in .tar.md5 archive.")
            trailer_line = tail_bytes[match_pos.start() :]
            tar_body_len = (total_len - tail_len) + match_pos.start()

        m = _TAR_MD5_TRAILER_RE.match(trailer_line)
        if not m:
            raise OemWorkflowError("Malformed trailing MD5 signature format in .tar.md5 archive.")

        expected_md5 = m.group(1).decode("ascii").lower()

        hasher = hashlib.md5()
        chunk_sz = 1024 * 1024  # 1 MiB zero-copy slices
        offset = 0
        while offset < tar_body_len:
            end = min(offset + chunk_sz, tar_body_len)
            hasher.update(mv[offset:end])
            offset = end

        computed_md5 = hasher.hexdigest().lower()
        return (expected_md5 == computed_md5), expected_md5, computed_md5

def classify_samsung_csc_package(filename: Union[str, Path]) -> StageGateResult:
    """
    Classify whether a Samsung CSC package preserves `/userdata` (`HOME_CSC_*`)
    or performs a full factory reset (`CSC_*`).
    """
    name = Path(filename).name.upper()
    if name.startswith("HOME_CSC"):
        return StageGateResult(
            stage_id="samsung_csc_mode",
            passed=True,
            severity="SAFE",
            headline="HOME_CSC Selected — User Data Preserved",
            detail="In-place upgrade mode active. Internal storage and `/userdata` will NOT be wiped.",
        )
    if name.startswith("CSC_"):
        return StageGateResult(
            stage_id="samsung_csc_mode",
            passed=True,
            severity="WARNING",
            headline="Standard CSC Selected — Full Factory Reset!",
            detail=(
                "Flashing `CSC_*.tar.md5` repartitions and wipes `/userdata`. "
                "Switch to `HOME_CSC_*.tar.md5` if you want to keep user files."
            ),
        )
    return StageGateResult(
        stage_id="samsung_csc_mode",
        passed=False,
        severity="BLOCKED",
        headline="Unrecognized CSC Package Naming",
        detail=f"Expected `HOME_CSC_*.tar.md5` or `CSC_*.tar.md5`, got '{Path(filename).name}'.",
    )
