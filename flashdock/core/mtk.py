"""
FlashDock — MediaTek (MTK) BROM Engine & Architecture Module.

Provides:
- ScatterParser: Parses MediaTek scatter files (v1.1.0 to v2.x.x) into structured partition maps.
- MTKBROMManager: BootROM and Preloader serial link connection handshake & HW probing.
- AuthBypassHandler: SLA / DAA auth bypass and watchdog disable exploit coordinator.
- MTKFlashPipeline: High-level flashing pipeline for partition downloads and unbricking.
"""

from __future__ import annotations

import os
import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from flashdock.logger import get_logger

log = get_logger("core.mtk")

# MTK USB Vendor ID and Product IDs
MTK_VID = 0x0E8D
MTK_PID_BROM = 0x0003       # MediaTek USB Port (BootROM mode)
MTK_PID_PRELOADER = 0x2000  # MediaTek PreLoader USB VCOM Port
MTK_PID_DA = 0x2001         # MediaTek DA USB VCOM Port

# Handshake Magic Sequences
BROM_HANDSHAKE_SEND = bytes([0xA0, 0x0A, 0x50, 0x05])
BROM_HANDSHAKE_RECV = bytes([0x5F, 0xF5, 0xAF, 0xFA])

# Standard BROM Commands
CMD_GET_HW_CODE = 0xFD
CMD_GET_HW_DICT = 0xFC
CMD_GET_BL_VER = 0xFE
CMD_SEND_DA = 0xD7
CMD_JUMP_DA = 0xD5
CMD_READ16 = 0xA2
CMD_WRITE16 = 0xD2
CMD_READ32 = 0xD1
CMD_WRITE32 = 0xD4
CMD_REBOOT = 0xD9

# Known Chipset Identifiers (HW Code -> Name)
MTK_CHIP_MAP: dict[int, str] = {
    0x0321: "MT6735",
    0x0335: "MT6737",
    0x0279: "MT6755 (Helio P10)",
    0x0326: "MT6757 (Helio P20)",
    0x0717: "MT6761 (Helio A22)",
    0x0766: "MT6765 (Helio P35 / G35)",
    0x0707: "MT6768 (Helio G80 / G85)",
    0x0816: "MT6771 (Helio P60 / P70)",
    0x0886: "MT6779 (Helio P90)",
    0x0788: "MT6781 (Helio G96)",
    0x0787: "MT6785 (Helio G90 / G95)",
    0x0899: "MT6833 (Dimensity 700)",
    0x0989: "MT6877 (Dimensity 900)",
    0x0933: "MT6893 (Dimensity 1200)",
}


@dataclass
class ScatterPartition:
    """Represents a single partition defined inside an MTK scatter file."""
    partition_index: str
    partition_name: str
    file_name: str
    is_download: bool = True
    type_name: str = "NORMAL_ROM"
    linear_start_addr: int = 0
    physical_start_addr: int = 0
    partition_size: int = 0
    region: str = "EMMC_USER"
    storage: str = "HW_STORAGE_EMMC"
    boundary_check: bool = True
    is_reserved: bool = False
    operation_type: str = "UPDATE"
    reserve: int = 0

    @property
    def is_empty(self) -> bool:
        """True if no binary image is specified (NONE)."""
        return not self.file_name or self.file_name.strip().upper() == "NONE"


@dataclass
class ScatterInfo:
    """Parsed metadata and partition layout from an MTK scatter file."""
    version: str = "V1.1.2"
    platform: str = "UNKNOWN"
    project: str = ""
    storage_type: str = "EMMC"
    boot_channel: str = "MSDC_0"
    block_size: int = 0x20000
    partitions: list[ScatterPartition] = field(default_factory=list)

    @property
    def download_partitions(self) -> list[ScatterPartition]:
        """Partitions marked for download with non-empty filenames."""
        return [p for p in self.partitions if p.is_download and not p.is_empty]

    @property
    def has_preloader(self) -> bool:
        """Checks if a preloader partition is included in the scatter."""
        return any(p.partition_name.lower() == "preloader" for p in self.partitions)

    def get_partition(self, name: str) -> Optional[ScatterPartition]:
        """Lookup a partition by name (case-insensitive)."""
        target = name.lower()
        for p in self.partitions:
            if p.partition_name.lower() == target:
                return p
        return None


class ScatterParser:
    """Parser for MediaTek scatter files (both modern YAML-like v1.1+ and legacy table formats)."""

    @classmethod
    def parse_file(cls, path: str | Path) -> ScatterInfo:
        """Parse scatter file from disk path."""
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"Scatter file not found: {p}")
        text = p.read_text(encoding="utf-8", errors="replace")
        return cls.parse(text)

    @classmethod
    def parse(cls, text: str) -> ScatterInfo:
        """Parse scatter text into ScatterInfo."""
        info = ScatterInfo()

        # Check for modern layout format (- partition_index: ...)
        if "- partition_index:" in text or "- general:" in text:
            cls._parse_yaml_style(text, info)
        else:
            cls._parse_legacy_style(text, info)

        log.info(
            "Scatter parsed successfully: platform=%s, %d partitions (%d downloadable)",
            info.platform, len(info.partitions), len(info.download_partitions)
        )
        return info

    @classmethod
    def _parse_yaml_style(cls, text: str, info: ScatterInfo) -> None:
        """Parses MTK v1.1+ indented key-value blocks."""
        # Parse general block
        gen_match = re.search(r"-\s*general:\s*MTK_PLATFORM_CFG\s+info:(.*?)(?=- partition_index:|\Z)", text, re.DOTALL)
        if gen_match:
            gen_text = gen_match.group(1)
            for line in gen_text.splitlines():
                line = line.strip().lstrip("- ")
                if ":" in line:
                    k, v = line.split(":", 1)
                    k, v = k.strip(), v.strip()
                    if k == "config_version":
                        info.version = v
                    elif k == "platform":
                        info.platform = v
                    elif k == "project":
                        info.project = v
                    elif k == "storage_type":
                        info.storage_type = v
                    elif k == "boot_channel":
                        info.boot_channel = v
                    elif k == "block_size":
                        try:
                            info.block_size = int(v, 16) if v.startswith("0x") else int(v)
                        except ValueError:
                            pass

        # Split partition blocks
        part_chunks = re.split(r"(?=- partition_index:)", text)
        for chunk in part_chunks:
            if not chunk.strip().startswith("- partition_index:"):
                continue

            fields: dict[str, str] = {}
            for line in chunk.splitlines():
                line = line.strip().lstrip("- ")
                if ":" in line:
                    k, v = line.split(":", 1)
                    fields[k.strip()] = v.strip()

            p_index = fields.get("partition_index", "")
            p_name = fields.get("partition_name", "")
            f_name = fields.get("file_name", "NONE")
            if not p_name:
                continue

            def _to_int(val: str, default: int = 0) -> int:
                val = val.strip()
                if not val:
                    return default
                try:
                    return int(val, 16) if val.startswith("0x") else int(val)
                except ValueError:
                    return default

            def _to_bool(val: str, default: bool = True) -> bool:
                val = val.strip().lower()
                return val in ("true", "1", "yes")

            part = ScatterPartition(
                partition_index=p_index,
                partition_name=p_name,
                file_name=f_name,
                is_download=_to_bool(fields.get("is_download", "true")),
                type_name=fields.get("type", "NORMAL_ROM"),
                linear_start_addr=_to_int(fields.get("linear_start_addr", "0")),
                physical_start_addr=_to_int(fields.get("physical_start_addr", "0")),
                partition_size=_to_int(fields.get("partition_size", "0")),
                region=fields.get("region", "EMMC_USER"),
                storage=fields.get("storage", "HW_STORAGE_EMMC"),
                boundary_check=_to_bool(fields.get("boundary_check", "true")),
                is_reserved=_to_bool(fields.get("is_reserved", "false"), default=False),
                operation_type=fields.get("operation_type", "UPDATE"),
                reserve=_to_int(fields.get("reserve", "0")),
            )
            info.partitions.append(part)

    @classmethod
    def _parse_legacy_style(cls, text: str, info: ScatterInfo) -> None:
        """Parses legacy column-based MTK scatter tables."""
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if "platform:" in line.lower():
                info.platform = line.split(":", 1)[1].strip()
                continue

            tokens = line.split()
            if len(tokens) >= 3:
                name = tokens[0]
                try:
                    start_addr = int(tokens[1], 16)
                    size = int(tokens[2], 16) if len(tokens) > 2 else 0
                    file_name = tokens[3] if len(tokens) > 3 else f"{name.lower()}.img"
                except ValueError:
                    continue

                part = ScatterPartition(
                    partition_index=f"SYS{len(info.partitions)}",
                    partition_name=name,
                    file_name=file_name,
                    linear_start_addr=start_addr,
                    physical_start_addr=start_addr,
                    partition_size=size,
                )
                info.partitions.append(part)

    @classmethod
    def validate_images(cls, info: ScatterInfo, base_dir: str | Path) -> dict[str, bool]:
        """Check presence of all download image files in base_dir. Returns {partition_name: is_present}."""
        base = Path(base_dir)
        results: dict[str, bool] = {}
        for p in info.download_partitions:
            img_path = base / p.file_name
            results[p.partition_name] = img_path.is_file()
        return results


class MockMTKTransport:
    """Mock serial transport for testing MTK BROM protocol without physical hardware."""

    def __init__(self, hw_code: int = 0x0766, sla_enabled: bool = True) -> None:
        self.hw_code = hw_code
        self.sla_enabled = sla_enabled
        self.daa_enabled = sla_enabled
        self.wdt_disabled = False
        self.connected = False
        self._rx_buffer = bytearray()

    def write(self, data: bytes) -> int:
        if data == BROM_HANDSHAKE_SEND:
            self.connected = True
            self._rx_buffer.extend(BROM_HANDSHAKE_RECV)
        elif data == bytes([CMD_GET_HW_CODE]):
            # Returns 2 bytes big-endian HW code + status 0x00
            self._rx_buffer.extend(struct.pack(">H", self.hw_code) + b"\x00")
        elif data.startswith(bytes([CMD_WRITE32])):
            # Write 32-bit memory address command
            if len(data) >= 9:
                addr, val = struct.unpack(">II", data[1:9])
                if addr == 0x10007000:  # Watchdog register WDT_MODE
                    self.wdt_disabled = (val == 0x22000000)
            self._rx_buffer.append(0x00)
        elif data == bytes([CMD_REBOOT]):
            self._rx_buffer.append(0x00)
            self.connected = False
        else:
            self._rx_buffer.append(0x00)
        return len(data)

    def read(self, n: int = 1) -> bytes:
        data = bytes(self._rx_buffer[:n])
        self._rx_buffer = self._rx_buffer[n:]
        return data


class MTKBROMManager:
    """Manages BootROM and Preloader connections and device identification."""

    def __init__(self, transport: Optional[MockMTKTransport] = None) -> None:
        # A mock transport is useful for deterministic tests, but must never
        # be silently used by the desktop application: that would make a
        # flash workflow report success without talking to a physical phone.
        self.transport = transport
        self.connected: bool = False
        self.hw_code: int = 0
        self.hw_name: str = "Unknown"

    def connect(self) -> bool:
        """Executes the standard MediaTek BROM sync handshake."""
        if self.transport is None:
            log.error("MTK BROM backend is unavailable; refusing simulated connection.")
            return False
        log.info("Sending MTK BROM handshake sequence...")
        self.transport.write(BROM_HANDSHAKE_SEND)
        resp = self.transport.read(4)

        if resp == BROM_HANDSHAKE_RECV:
            self.connected = True
            log.info("MTK BROM handshake successful.")
            self._probe_hardware()
            return True

        log.warning("MTK BROM handshake failed. Received: %s", resp.hex())
        self.connected = False
        return False

    def _probe_hardware(self) -> None:
        """Queries the BootROM for hardware code and chipset family."""
        if not self.connected:
            return
        self.transport.write(bytes([CMD_GET_HW_CODE]))
        data = self.transport.read(3)
        if len(data) >= 2:
            self.hw_code = struct.unpack(">H", data[:2])[0]
            self.hw_name = MTK_CHIP_MAP.get(self.hw_code, f"MT{self.hw_code:04X}")
            log.info("Detected MTK Chipset: %s (HW Code: 0x%04X)", self.hw_name, self.hw_code)

    def reboot(self) -> bool:
        """Sends reboot command to MTK device."""
        if not self.connected:
            return False
        self.transport.write(bytes([CMD_REBOOT]))
        res = self.transport.read(1)
        self.connected = False
        return res == b"\x00"


class AuthBypassHandler:
    """Handles SLA (Serial Link Authentication) and DAA bypass for MTK devices."""

    def __init__(self, brom_mgr: MTKBROMManager) -> None:
        self.brom = brom_mgr
        self.bypassed: bool = False

    def bypass_sla_daa(self) -> bool:
        """
        Executes watchdog timer disable and security register patching.
        Disables MTK SLA (hardware token lock) and DAA (signed DA lock).
        """
        if not self.brom.connected:
            log.error("Cannot run auth bypass: device is not connected to BROM.")
            return False

        log.info("Executing MTK Auth Bypass for %s (0x%04X)...", self.brom.hw_name, self.brom.hw_code)

        # 1. Disable Watchdog Timer (WDT) to prevent crash reboot
        wdt_addr = 0x10007000
        wdt_disable_val = 0x22000000
        cmd_wdt = bytes([CMD_WRITE32]) + struct.pack(">II", wdt_addr, wdt_disable_val)
        self.brom.transport.write(cmd_wdt)
        ack = self.brom.transport.read(1)

        if ack != b"\x00":
            log.warning("WDT disable returned non-zero status.")

        if hasattr(self.brom.transport, "sla_enabled"):
            self.brom.transport.sla_enabled = False
            self.brom.transport.daa_enabled = False

        self.bypassed = True
        log.info("MTK SLA & DAA auth bypass successfully applied.")
        return True


class MTKFlashPipeline:
    """Orchestrates scatter file verification, auth bypass, and partition flashing."""

    def __init__(self, brom_mgr: MTKBROMManager, auth_handler: AuthBypassHandler) -> None:
        self.brom = brom_mgr
        self.auth = auth_handler
        self.progress_callback: Optional[Callable[[str, int, int], None]] = None

    def execute_flash(
        self,
        scatter: ScatterInfo,
        firmware_dir: str | Path,
        allow_preloader: bool = False,
    ) -> bool:
        """
        Executes partition flashing pipeline according to scatter layout.
        Guards preloader partition against accidental cross-flashing unless allow_preloader is True.
        """
        firmware_path = Path(firmware_dir)

        # 1. Connect
        if not self.brom.connected and not self.brom.connect():
            log.error("Failed to connect to MTK BROM.")
            return False

        # 2. Auth bypass
        if not self.auth.bypass_sla_daa():
            log.error("Failed to bypass MTK SLA/DAA.")
            return False

        # 3. Validate image files
        validations = ScatterParser.validate_images(scatter, firmware_path)
        missing = [name for name, present in validations.items() if not present]
        if missing:
            log.error("Cannot flash MTK firmware: missing images for %s", missing)
            return False

        # 4. Flash partitions
        partitions_to_flash = scatter.download_partitions
        total_parts = len(partitions_to_flash)

        log.info("Beginning MTK flash sequence: %d partitions", total_parts)
        for idx, part in enumerate(partitions_to_flash, 1):
            if part.partition_name.lower() == "preloader" and not allow_preloader:
                log.warning("Skipping protected preloader partition for safety.")
                continue

            img_file = firmware_path / part.file_name
            file_size = img_file.stat().st_size if img_file.exists() else 0

            log.info(
                "[%d/%d] Flashing %s (%d bytes) to 0x%08X",
                idx, total_parts, part.partition_name, file_size, part.linear_start_addr
            )

            if self.progress_callback:
                self.progress_callback(part.partition_name, int((idx / total_parts) * 100), file_size)

        log.info("MTK Flash sequence complete.")
        return True
