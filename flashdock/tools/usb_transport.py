"""
Pure-Python Win32 USB/Serial Hardware Transport & Low-Level Handshake Engine.

Implements zero-dependency ctypes bindings to kernel32.dll and setupapi.dll
to execute real wire-level protocol handshakes directly over Win32 COM/USB
device handles:
  1. Qualcomm EDL Sahara Hello Packet (Command 0x01) inspection & response.
  2. MediaTek BROM 4-byte Handshake (0xA0 0x0A 0x50 0x05 -> 0x5F 0xF5 0xAF 0xFA).
  3. Unisoc (Spreadtrum) BROM HDLC 0x7E Check-Baud & CRC-16/XMODEM framing.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import struct
import sys
from typing import Callable

# Win32 Constants
GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000
OPEN_EXISTING = 3
FILE_ATTRIBUTE_NORMAL = 0x00000080
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

# Protocol Constants
MTK_BROM_HANDSHAKE_TX = (0xA0, 0x0A, 0x50, 0x05)
MTK_BROM_HANDSHAKE_RX = (0x5F, 0xF5, 0xAF, 0xFA)

SAHARA_CMD_HELLO_REQ = 0x01
SAHARA_CMD_HELLO_RESP = 0x02
SAHARA_HEADER_SIZE = 8
SAHARA_HELLO_PACKET_SIZE = 48
SAHARA_VERSION_SUPPORTED = 2
SAHARA_STATUS_SUCCESS = 0x00

UNISOC_HDLC_FLAG = 0x7E
UNISOC_HDLC_ESCAPE = 0x7D
UNISOC_HDLC_ESCAPE_MASK = 0x20
UNISOC_CMD_CONNECT = 0x0000
UNISOC_REP_ACK = 0x0080
UNISOC_REP_VER = 0x0081


class COMMTIMEOUTS(ctypes.Structure):
    """Win32 COMMTIMEOUTS structure for serial/USB virtual COM port timeouts."""

    _fields_ = [
        ("ReadIntervalTimeout", wintypes.DWORD),
        ("ReadTotalTimeoutMultiplier", wintypes.DWORD),
        ("ReadTotalTimeoutConstant", wintypes.DWORD),
        ("WriteTotalTimeoutMultiplier", wintypes.DWORD),
        ("WriteTotalTimeoutConstant", wintypes.DWORD),
    ]


class DCB(ctypes.Structure):
    """Win32 Device Control Block (DCB) structure for serial port configuration."""

    _fields_ = [
        ("DCBlength", wintypes.DWORD),
        ("BaudRate", wintypes.DWORD),
        ("fFlags", wintypes.DWORD),
        ("wReserved", wintypes.WORD),
        ("XonLim", wintypes.WORD),
        ("XoffLim", wintypes.WORD),
        ("ByteSize", ctypes.c_ubyte),
        ("Parity", ctypes.c_ubyte),
        ("StopBits", ctypes.c_ubyte),
        ("XonChar", ctypes.c_char),
        ("XoffChar", ctypes.c_char),
        ("ErrorChar", ctypes.c_char),
        ("EofChar", ctypes.c_char),
        ("EvtChar", ctypes.c_char),
        ("wReserved1", wintypes.WORD),
    ]


@dataclass(frozen=True)
class SaharaHelloPacket:
    """Parsed 48-byte Qualcomm Sahara Hello Request packet (Command 0x01)."""

    command: int
    length: int
    version: int
    version_supported: int
    max_cmd_packet_size: int
    mode: int
    reserved: tuple[int, int, int, int, int, int]

    @property
    def is_valid(self) -> bool:
        return (
            self.command == SAHARA_CMD_HELLO_REQ
            and self.length == SAHARA_HELLO_PACKET_SIZE
            and self.version >= 1
        )


@dataclass(frozen=True)
class HandshakeResult:
    """Result of a low-level BootROM / Emergency Download hardware handshake."""

    success: bool
    protocol: str
    port: str
    message: str
    details: dict[str, object]


class Win32SerialTransport:
    """
    Pure-Python ctypes Win32 serial/COM port transport.
    Eliminates external pyserial/pyusb C-extension requirements.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 115200,
        timeout_ms: int = 1000,
    ) -> None:
        self.port = port.strip()
        self.baudrate = baudrate
        self.timeout_ms = max(50, int(timeout_ms))
        self._handle: int | None = None

    @property
    def device_path(self) -> str:
        if self.port.startswith("\\\\.\\"):
            return self.port
        return f"\\\\.\\{self.port}"

    def open(self) -> bool:
        if sys.platform != "win32":
            return False
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateFileW.restype = wintypes.HANDLE
        handle = kernel32.CreateFileW(
            self.device_path,
            GENERIC_READ | GENERIC_WRITE,
            0,
            None,
            OPEN_EXISTING,
            FILE_ATTRIBUTE_NORMAL,
            None,
        )
        if handle in (None, INVALID_HANDLE_VALUE, -1):
            self._handle = None
            return False

        self._handle = int(handle)
        self._configure_port()
        return True

    def _configure_port(self) -> None:
        if self._handle is None or sys.platform != "win32":
            return
        kernel32 = ctypes.windll.kernel32
        dcb = DCB()
        dcb.DCBlength = ctypes.sizeof(DCB)
        if kernel32.GetCommState(wintypes.HANDLE(self._handle), ctypes.byref(dcb)):
            dcb.BaudRate = self.baudrate
            dcb.ByteSize = 8
            dcb.Parity = 0  # NOPARITY
            dcb.StopBits = 0  # ONESTOPBIT
            dcb.fFlags = 0x0001  # fBinary
            kernel32.SetCommState(wintypes.HANDLE(self._handle), ctypes.byref(dcb))

        timeouts = COMMTIMEOUTS(
            ReadIntervalTimeout=50,
            ReadTotalTimeoutMultiplier=10,
            ReadTotalTimeoutConstant=self.timeout_ms,
            WriteTotalTimeoutMultiplier=10,
            WriteTotalTimeoutConstant=self.timeout_ms,
        )
        kernel32.SetCommTimeouts(wintypes.HANDLE(self._handle), ctypes.byref(timeouts))

    def write(self, data: bytes) -> int:
        if self._handle is None or sys.platform != "win32":
            raise OSError("Transport handle is not open.")
        if not data:
            return 0
        kernel32 = ctypes.windll.kernel32
        written = wintypes.DWORD(0)
        buf = ctypes.create_string_buffer(data, len(data))
        ok = kernel32.WriteFile(
            wintypes.HANDLE(self._handle),
            buf,
            len(data),
            ctypes.byref(written),
            None,
        )
        if not ok:
            raise OSError(f"Win32 WriteFile failed on {self.port}.")
        return int(written.value)

    def read(self, size: int) -> bytes:
        if self._handle is None or sys.platform != "win32":
            raise OSError("Transport handle is not open.")
        if size <= 0:
            return b""
        kernel32 = ctypes.windll.kernel32
        buf = ctypes.create_string_buffer(size)
        read_bytes = wintypes.DWORD(0)
        ok = kernel32.ReadFile(
            wintypes.HANDLE(self._handle),
            buf,
            size,
            ctypes.byref(read_bytes),
            None,
        )
        if not ok:
            raise OSError(f"Win32 ReadFile failed on {self.port}.")
        return buf.raw[: int(read_bytes.value)]

    def close(self) -> None:
        if self._handle is not None and sys.platform == "win32":
            try:
                ctypes.windll.kernel32.CloseHandle(wintypes.HANDLE(self._handle))
            except Exception:
                pass
        self._handle = None

    def __enter__(self) -> Win32SerialTransport:
        if not self.open():
            raise OSError(f"Unable to open Win32 device handle for {self.port}")
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        self.close()


# ============================================================================
# Low-Level Protocol Framing & Handshake Verifiers
# ============================================================================


def crc16_xmodem(data: bytes | bytearray | memoryview) -> int:
    """Compute CRC-16/XMODEM checksum used by Unisoc (Spreadtrum) HDLC BROM frames."""
    crc = 0x0000
    for byte in data:
        crc ^= (byte & 0xFF) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF


def encode_unisoc_hdlc_frame(cmd_type: int, payload: bytes = b"") -> bytes:
    """
    Encode a Unisoc HDLC packet:
      [0x7E] + escaped([cmd_be16][len_be16][payload][crc16_be16]) + [0x7E]
    """
    if len(payload) > 0xFFFF:
        raise ValueError("Unisoc HDLC payload exceeds 65535 bytes.")
    raw_body = struct.pack(">HH", cmd_type & 0xFFFF, len(payload)) + bytes(payload)
    crc = crc16_xmodem(raw_body)
    raw_with_crc = raw_body + struct.pack(">H", crc)

    escaped = bytearray([UNISOC_HDLC_FLAG])
    for b in raw_with_crc:
        if b in (UNISOC_HDLC_FLAG, UNISOC_HDLC_ESCAPE):
            escaped.append(UNISOC_HDLC_ESCAPE)
            escaped.append(b ^ UNISOC_HDLC_ESCAPE_MASK)
        else:
            escaped.append(b)
    escaped.append(UNISOC_HDLC_FLAG)
    return bytes(escaped)


def decode_unisoc_hdlc_frame(frame: bytes | bytearray | memoryview) -> tuple[int, bytes]:
    """
    Decode and verify a Unisoc HDLC frame, returning (cmd_type, payload).
    Raises ValueError on invalid framing, short packet, or CRC mismatch.
    """
    raw = bytes(frame)
    start = raw.find(bytes([UNISOC_HDLC_FLAG]))
    if start == -1:
        raise ValueError("Missing leading HDLC 0x7E flag.")
    end = raw.find(bytes([UNISOC_HDLC_FLAG]), start + 1)
    if end == -1:
        raise ValueError("Missing trailing HDLC 0x7E flag.")

    sliced = raw[start + 1 : end]
    unescaped = bytearray()
    i = 0
    while i < len(sliced):
        b = sliced[i]
        if b == UNISOC_HDLC_ESCAPE:
            if i + 1 >= len(sliced):
                raise ValueError("Truncated HDLC escape sequence.")
            unescaped.append(sliced[i + 1] ^ UNISOC_HDLC_ESCAPE_MASK)
            i += 2
        else:
            unescaped.append(b)
            i += 1

    if len(unescaped) < 6:
        raise ValueError(f"HDLC body too short ({len(unescaped)} bytes).")

    cmd_type, length = struct.unpack(">HH", unescaped[:4])
    payload = bytes(unescaped[4:-2])
    expected_crc = struct.unpack(">H", unescaped[-2:])[0]
    if len(payload) != length:
        raise ValueError(f"HDLC length mismatch: header={length}, actual={len(payload)}.")

    actual_crc = crc16_xmodem(unescaped[:-2])
    if actual_crc != expected_crc:
        raise ValueError(
            f"HDLC CRC-16 mismatch: expected=0x{expected_crc:04X}, actual=0x{actual_crc:04X}."
        )
    return cmd_type, payload


def parse_sahara_hello(data: bytes | bytearray | memoryview) -> SaharaHelloPacket:
    """Parse a 48-byte Qualcomm Sahara Hello Request packet (Command 0x01)."""
    raw = bytes(data)
    if len(raw) < SAHARA_HELLO_PACKET_SIZE:
        raise ValueError(
            f"Sahara Hello packet requires {SAHARA_HELLO_PACKET_SIZE} bytes, got {len(raw)}."
        )
    fields = struct.unpack("<12I", raw[:SAHARA_HELLO_PACKET_SIZE])
    pkt = SaharaHelloPacket(
        command=fields[0],
        length=fields[1],
        version=fields[2],
        version_supported=fields[3],
        max_cmd_packet_size=fields[4],
        mode=fields[5],
        reserved=(fields[6], fields[7], fields[8], fields[9], fields[10], fields[11]),
    )
    if not pkt.is_valid:
        raise ValueError(
            f"Invalid Sahara Hello header: cmd=0x{pkt.command:02X}, len={pkt.length}, ver={pkt.version}"
        )
    return pkt


def build_sahara_hello_response(
    version: int = SAHARA_VERSION_SUPPORTED,
    version_supported: int = 1,
    status: int = SAHARA_STATUS_SUCCESS,
    mode: int = 0,
) -> bytes:
    """Construct a 48-byte Qualcomm Sahara Hello Response packet (Command 0x02)."""
    return struct.pack(
        "<12I",
        SAHARA_CMD_HELLO_RESP,
        SAHARA_HELLO_PACKET_SIZE,
        version,
        version_supported,
        status,
        mode,
        0,
        0,
        0,
        0,
        0,
        0,
    )


def perform_mtk_brom_handshake(
    port: str,
    transport_factory: Callable[[str], Win32SerialTransport] | None = None,
) -> HandshakeResult:
    """
    Execute the 4-byte MediaTek BROM handshake sequence:
      TX: 0xA0 -> RX: 0x5F
      TX: 0x0A -> RX: 0xF5
      TX: 0x50 -> RX: 0xAF
      TX: 0x05 -> RX: 0xFA
    """
    factory = transport_factory or (lambda p: Win32SerialTransport(p, baudrate=115200, timeout_ms=500))
    try:
        with factory(port) as transport:
            rx_bytes: list[int] = []
            for tx_byte, expected_rx in zip(MTK_BROM_HANDSHAKE_TX, MTK_BROM_HANDSHAKE_RX):
                transport.write(bytes([tx_byte]))
                resp = transport.read(1)
                if not resp:
                    return HandshakeResult(
                        success=False,
                        protocol="MTK_BROM",
                        port=port,
                        message=f"Timeout waiting for BROM echo after TX 0x{tx_byte:02X}.",
                        details={"tx_Stop": tx_byte, "rx_collected": rx_bytes},
                    )
                actual = resp[0]
                rx_bytes.append(actual)
                if actual != expected_rx:
                    return HandshakeResult(
                        success=False,
                        protocol="MTK_BROM",
                        port=port,
                        message=(
                            f"BROM echo mismatch on {port}: sent 0x{tx_byte:02X}, "
                            f"expected 0x{expected_rx:02X}, got 0x{actual:02X}."
                        ),
                        details={"rx_collected": rx_bytes},
                    )
            return HandshakeResult(
                success=True,
                protocol="MTK_BROM",
                port=port,
                message=f"MediaTek BootROM handshake verified on {port} (5F F5 AF FA).",
                details={"rx_sequence": [f"0x{b:02X}" for b in rx_bytes]},
            )
    except Exception as exc:
        return HandshakeResult(
            success=False,
            protocol="MTK_BROM",
            port=port,
            message=f"MTK BROM transport error on {port}: {exc}",
            details={"error": str(exc)},
        )


def perform_sahara_hello_check(
    port: str,
    send_response: bool = False,
    transport_factory: Callable[[str], Win32SerialTransport] | None = None,
) -> HandshakeResult:
    """Read and inspect the 48-byte Qualcomm Sahara Hello packet from an EDL 9008 port."""
    factory = transport_factory or (lambda p: Win32SerialTransport(p, baudrate=115200, timeout_ms=800))
    try:
        with factory(port) as transport:
            raw = transport.read(SAHARA_HELLO_PACKET_SIZE)
            if not raw:
                return HandshakeResult(
                    success=False,
                    protocol="QUALCOMM_SAHARA",
                    port=port,
                    message=f"No Sahara Hello packet received from {port}.",
                    details={},
                )
            pkt = parse_sahara_hello(raw)
            if send_response:
                resp = build_sahara_hello_response(
                    version=pkt.version,
                    version_supported=pkt.version_supported,
                    status=SAHARA_STATUS_SUCCESS,
                    mode=pkt.mode,
                )
                transport.write(resp)
            return HandshakeResult(
                success=True,
                protocol="QUALCOMM_SAHARA",
                port=port,
                message=(
                    f"Qualcomm Sahara v{pkt.version} Hello verified on {port} "
                    f"(mode=0x{pkt.mode:02X}, max_pkt={pkt.max_cmd_packet_size}B)."
                ),
                details={
                    "version": pkt.version,
                    "version_supported": pkt.version_supported,
                    "mode": pkt.mode,
                    "max_cmd_packet_size": pkt.max_cmd_packet_size,
                },
            )
    except Exception as exc:
        return HandshakeResult(
            success=False,
            protocol="QUALCOMM_SAHARA",
            port=port,
            message=f"Sahara handshake check failed on {port}: {exc}",
            details={"error": str(exc)},
        )


def perform_unisoc_hdlc_ping(
    port: str,
    transport_factory: Callable[[str], Win32SerialTransport] | None = None,
) -> HandshakeResult:
    """
    Send the Unisoc BROM 0x7E check-baud ping and decode the HDLC BSL_REP_VER
    (0x0081) or BSL_REP_ACK (0x0080) response frame.
    """
    factory = transport_factory or (lambda p: Win32SerialTransport(p, baudrate=115200, timeout_ms=800))
    try:
        with factory(port) as transport:
            transport.write(bytes([UNISOC_HDLC_FLAG]))
            raw = transport.read(128)
            if not raw:
                return HandshakeResult(
                    success=False,
                    protocol="UNISOC_HDLC",
                    port=port,
                    message=f"No HDLC response to 0x7E check-baud ping on {port}.",
                    details={},
                )
            cmd_type, payload = decode_unisoc_hdlc_frame(raw)
            ver_str = payload.decode("ascii", errors="replace").strip("\x00 ")
            return HandshakeResult(
                success=True,
                protocol="UNISOC_HDLC",
                port=port,
                message=f"Unisoc HDLC handshake verified on {port} (cmd=0x{cmd_type:04X}, ver='{ver_str}').",
                details={"cmd_type": cmd_type, "version": ver_str},
            )
    except Exception as exc:
        return HandshakeResult(
            success=False,
            protocol="UNISOC_HDLC",
            port=port,
            message=f"Unisoc HDLC ping failed on {port}: {exc}",
            details={"error": str(exc)},
        )

