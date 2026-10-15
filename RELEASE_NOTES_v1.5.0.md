## Summary

Upgrades **FlashDock** from `v1.4.0` to `v1.5.0` with a comprehensive concurrency & I/O hardening pass, zero-copy `mmap` binary extraction, native Win32 `WM_DEVICECHANGE` hardware event signaling, pure-Python `ctypes` Win32 USB/Serial BootROM handshakes (Qualcomm Sahara, MediaTek BROM, Unisoc HDLC), and a property-based binary parser fuzzing suite.

```text
MainWindow / Screen Workers
 ├── flashdock.tools.runner.flash_lock_scope()        [Reentrant RLock + deterministic release]
 │    └── kill_process_tree(pid)                      [Win32 taskkill /F /T /PID subtree cleanup]
 ├── flashdock.workers.device_monitor
 │    └── Win32DeviceEventMonitor                     [WM_DEVICECHANGE <50ms instant wake-up]
 ├── flashdock.tools.mmap_stream
 │    ├── open_mmap_view()                            [Zero-copy mmap + memoryview streaming]
 │    └── safe_extract_zip() / safe_extract_tar()     [Zip-Slip guard + PEP 706 filter="data"]
 └── flashdock.tools.usb_transport
      ├── perform_sahara_hello_check()                [Qualcomm EDL 9008 Sahara 0x01/0x02]
      ├── perform_mtk_brom_handshake()                [MediaTek BROM 0xA0 0x0A 0x50 0x05 -> 5F F5 AF FA]
      └── perform_unisoc_hdlc_ping()                  [Unisoc BROM HDLC 0x7E + CRC-16/XMODEM]

DeviceMonitorWorker relied strictly on a 1.5s polling interval, risking missed detection windows on short-lived MediaTek BROM (0E8D:0003) connections.

Subprocess timeouts in runner.py terminated only the immediate process handle without killing child trees (taskkill /F /T), and flash lock acquisition lacked a reentrant context manager.

payload_dumper.py and lz4_util.py performed standard buffered file reads, and tarfile.extractall() in return_stock.py lacked Python 3.12–3.14 PEP 706 filter="data" enforcement.

Zero-Copy & Archive Hardening: open_mmap_view() provides zero-copy memoryview slices over mmap.mmap handles; safe_extract_zip() and safe_extract_tar() block ../ path traversal and enforce PEP 706 filter="data".

Low-Level Protocol Handshakes: Pure-Python ctypes Win32SerialTransport verifies Qualcomm Sahara Hello (0x01), MediaTek BROM 4-byte echo (5F F5 AF FA), and Unisoc HDLC 0x7E frames with CRC-16/XMODEM validation without external C-extensions.

Test & Fuzzing Verification: All legacy unit tests plus 75+ new fuzzing, transport, and hardening tests in tests/test_fuzz_parsers.py, tests/test_usb_transport.py, and tests/test_v150_hardening.py pass (0 warnings, 0 failures).

All v1.5.0 transport, mmap, and WM_DEVICECHANGE modules are additive, pure-Python standard-library components with graceful fallbacks (open_mmap_view handles 0-byte files; Win32DeviceEventMonitor falls back to timed waits if no event arrives). All existing v1.4.0 public APIs and signatures remain 100% backward-compatible.

Binary Parsers & Archive Extractors: flashdock/tools/mmap_stream.py, flashdock/tools/lz4_util.py, flashdock/tools/payload_dumper.py, flashdock/core/return_stock.py

Packaging & Verification: flashdock.spec, version_info.txt, tests/test_fuzz_parsers.py, tests/test_usb_transport.py, tests/test_v150_hardening.py

