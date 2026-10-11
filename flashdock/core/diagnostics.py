"""
FlashDock — Advanced Diagnostics, Debloater & System Tweaks Engine (Phase 10).

Handles:
* Package Manager Debloater: safe disabling, user uninstallation, restoration,
  and classification (Carrier, OEM Bloat, Telemetry, User, Protected Core).
* Battery & Hardware Health: battery capacity, temperature, voltage, health state,
  charge cycles, thermal zones, and display specifications.
* System Tweaks: display density (DPI), animation speeds (0x, 0.5x, 1x),
  ADB-over-Wi-Fi enabler with IP extraction, and stay-awake toggle.

Spec references: Phase 10, Section 29.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Optional

from flashdock.logger import get_logger
from flashdock.tools.adb import ADB
from flashdock.tools.runner import CommandResult

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Package Classification Data
# ---------------------------------------------------------------------------

CRITICAL_PROTECTED_PACKAGES = {
    "android",
    "com.android.systemui",
    "com.android.settings",
    "com.android.phone",
    "com.android.providers.telephony",
    "com.android.providers.settings",
    "com.android.packageinstaller",
    "com.google.android.packageinstaller",
    "com.android.launcher3",
}

KNOWN_BLOATWARE: dict[str, str] = {
    # Meta / Facebook
    "com.facebook.katana": "Facebook App",
    "com.facebook.system": "Facebook App Installer",
    "com.facebook.appmanager": "Facebook App Manager",
    "com.facebook.services": "Facebook Services",
    # Xiaomi / MIUI Bloat
    "com.miui.analytics": "MIUI Analytics & Tracking",
    "com.miui.msa.global": "MIUI System Ads Daemon",
    "com.xiaomi.mipicks": "Xiaomi GetApps Store",
    "com.miui.yellowpage": "MIUI YellowPages Spammer",
    "com.mi.globalbrowser": "Mi Browser",
    "com.miui.bugreport": "MIUI Bug Report Telemetry",
    "com.miui.hybrid": "MIUI Quick Apps Service",
    # Samsung Bloat
    "com.samsung.android.bixby.agent": "Samsung Bixby Voice Agent",
    "com.samsung.android.bixby.service": "Samsung Bixby Background Service",
    "com.samsung.android.game.gamehome": "Samsung Gaming Hub",
    "com.sec.android.app.sbrowser": "Samsung Internet Browser",
    "com.samsung.android.spay": "Samsung Pay Agent",
    "com.samsung.android.kidsinstaller": "Samsung Kids Mode Installer",
    # Google Non-Core Apps
    "com.google.android.apps.tachyon": "Google Meet / Duo",
    "com.google.android.youtube": "YouTube (Pre-installed)",
    "com.google.android.apps.photos": "Google Photos",
    "com.google.android.videos": "Google TV / Play Movies",
    "com.google.android.music": "Google Play Music",
    # Carrier Bloat
    "com.vzw.apnlib": "Verizon Provisioning & Telemetry",
    "com.att.dh": "AT&T Device Help",
    "com.tmobile.pr.adapt": "T-Mobile Analytics Service",
    "com.sprint.ms.smf": "Sprint Zone / Carrier Services",
}


@dataclass
class InstalledPackage:
    """Metadata for an installed Android application."""
    package_name: str
    label: str = ""
    is_system: bool = False
    is_enabled: bool = True
    category: str = "general"  # "bloat", "carrier", "system", "user", "protected"
    can_debloat: bool = True


@dataclass
class BatteryHealthInfo:
    """Device battery health and power telemetry."""
    level: int = -1
    temperature_c: float = 0.0
    voltage_mv: int = 0
    health_status: str = "Unknown"
    power_source: str = "Battery"
    technology: str = "Li-ion"
    cycle_count: Optional[int] = None
    charge_counter_uah: Optional[int] = None


@dataclass
class HardwareSpecs:
    """Display and hardware platform metrics."""
    resolution: str = "Unknown"
    density_dpi: str = "Unknown"
    cpu_cores: int = 0
    cpu_governor: str = "Unknown"
    thermal_zones: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Debloater Manager
# ---------------------------------------------------------------------------

class DebloaterManager:
    """Manages package enumeration, disabling, uninstallation, and restore."""

    def __init__(self, adb: Optional[ADB] = None) -> None:
        self.adb = adb or ADB()

    def list_packages(self, serial: str = "") -> list[InstalledPackage]:
        """Fetch all installed packages and categorize them."""
        # 1. Fetch all packages with status
        res_all = self.adb.shell("pm list packages -u -f", serial=serial)
        res_disabled = self.adb.shell("pm list packages -d", serial=serial)
        res_third = self.adb.shell("pm list packages -3", serial=serial)

        disabled_set = set(
            p.replace("package:", "").strip()
            for p in res_disabled.stdout.splitlines() if p.strip()
        )
        third_party_set = set(
            p.replace("package:", "").strip()
            for p in res_third.stdout.splitlines() if p.strip()
        )

        packages: list[InstalledPackage] = []
        for line in res_all.stdout.splitlines():
            line = line.strip()
            if not line.startswith("package:"):
                continue
            # Format: package:/data/app/.../base.apk=com.example.app
            raw = line[len("package:"):]
            pkg = raw.split("=")[-1].strip() if "=" in raw else raw.strip()
            if not pkg:
                continue

            is_system = pkg not in third_party_set
            is_enabled = pkg not in disabled_set

            if pkg in CRITICAL_PROTECTED_PACKAGES:
                category = "protected"
                can_debloat = False
                label = "Core Android System"
            elif "carrier" in pkg or "vzw" in pkg or "att" in pkg or "tmobile" in pkg or "sprint" in pkg:
                category = "carrier"
                can_debloat = True
                label = KNOWN_BLOATWARE.get(pkg, "Carrier Services")
            elif pkg in KNOWN_BLOATWARE:
                category = "bloat"
                can_debloat = True
                label = KNOWN_BLOATWARE[pkg]
            elif not is_system:
                category = "user"
                can_debloat = True
                label = "Third-Party App"
            else:
                category = "system"
                can_debloat = True
                label = "OEM System Package"

            packages.append(InstalledPackage(
                package_name=pkg,
                label=label,
                is_system=is_system,
                is_enabled=is_enabled,
                category=category,
                can_debloat=can_debloat,
            ))

        packages.sort(key=lambda p: (not p.category == "bloat", p.package_name))
        return packages

    def disable_package(self, package_name: str, serial: str = "") -> tuple[bool, str]:
        """Safely disable a package for user 0."""
        if package_name in CRITICAL_PROTECTED_PACKAGES:
            return False, f"Package '{package_name}' is essential for Android system operations and cannot be disabled."
        res = self.adb.shell(f"pm disable-user --user 0 {package_name}", serial=serial)
        if "disabled" in res.stdout.lower() or res.return_code == 0:
            return True, f"Disabled {package_name}"
        return False, res.stderr or res.stdout

    def uninstall_package(self, package_name: str, serial: str = "") -> tuple[bool, str]:
        """Uninstall package for user 0 while retaining base apk for reinstallation."""
        if package_name in CRITICAL_PROTECTED_PACKAGES:
            return False, f"Package '{package_name}' is protected and cannot be uninstalled."
        res = self.adb.shell(f"pm uninstall -k --user 0 {package_name}", serial=serial)
        if "success" in res.stdout.lower() or res.return_code == 0:
            return True, f"Uninstalled {package_name} for current user"
        return False, res.stderr or res.stdout

    def restore_package(self, package_name: str, serial: str = "") -> tuple[bool, str]:
        """Re-enable or reinstall previously disabled/uninstalled package."""
        self.adb.shell(f"pm enable {package_name}", serial=serial)
        res = self.adb.shell(f"cmd package install-existing {package_name}", serial=serial)
        if "installed" in res.stdout.lower() or res.return_code == 0:
            return True, f"Restored {package_name}"
        return False, res.stderr or res.stdout


# ---------------------------------------------------------------------------
# Hardware & Battery Health Inspector
# ---------------------------------------------------------------------------

class HardwareHealthInspector:
    """Queries hardware health, battery cycle counts, thermals, and display."""

    def __init__(self, adb: Optional[ADB] = None) -> None:
        self.adb = adb or ADB()

    def get_battery_health(self, serial: str = "") -> BatteryHealthInfo:
        """Inspect battery metrics via dumpsys battery."""
        res = self.adb.shell("dumpsys battery", serial=serial)
        info = BatteryHealthInfo()

        health_map = {
            "1": "Unknown",
            "2": "Good",
            "3": "Overheat",
            "4": "Dead",
            "5": "Over Voltage",
            "6": "Unspecified Failure",
            "7": "Cold",
        }

        for line in res.stdout.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            k, v = [x.strip() for x in line.split(":", 1)]
            k_lower = k.lower()
            if k_lower == "level":
                try:
                    info.level = int(v)
                except ValueError:
                    pass
            elif k_lower == "voltage":
                try:
                    info.voltage_mv = int(v)
                except ValueError:
                    pass
            elif k_lower == "temperature":
                try:
                    info.temperature_c = round(float(v) / 10.0, 1)
                except ValueError:
                    pass
            elif k_lower == "health":
                info.health_status = health_map.get(v, v)
            elif k_lower == "technology":
                info.technology = v
            elif k_lower == "charge counter":
                try:
                    info.charge_counter_uah = int(v)
                except ValueError:
                    pass
            elif k_lower in ("cycle count", "cycle_count"):
                try:
                    info.cycle_count = int(v)
                except ValueError:
                    pass
            elif k_lower == "ac powered" and v == "true":
                info.power_source = "AC Charger"
            elif k_lower == "usb powered" and v == "true":
                info.power_source = "USB Port"
            elif k_lower == "wireless powered" and v == "true":
                info.power_source = "Wireless Charger"

        return info

    def get_hardware_specs(self, serial: str = "") -> HardwareSpecs:
        """Retrieve display resolution, density, and CPU governor."""
        specs = HardwareSpecs()

        # Display size
        res_size = self.adb.shell("wm size", serial=serial)
        m_size = re.search(r"(\d+x\d+)", res_size.stdout)
        if m_size:
            specs.resolution = m_size.group(1)

        # Density
        res_density = self.adb.shell("wm density", serial=serial)
        m_den = re.search(r"(\d+)", res_density.stdout)
        if m_den:
            specs.density_dpi = f"{m_den.group(1)} DPI"

        # Governor
        res_gov = self.adb.shell("cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor", serial=serial)
        if res_gov.stdout and not res_gov.stdout.startswith("cat:"):
            specs.cpu_governor = res_gov.stdout.strip()
        else:
            specs.cpu_governor = "schedutil"

        # Cores count
        res_cores = self.adb.shell("ls -d /sys/devices/system/cpu/cpu[0-9]* | wc -l", serial=serial)
        try:
            specs.cpu_cores = int(res_cores.stdout.strip())
        except ValueError:
            specs.cpu_cores = 8

        # Thermals
        res_therm = self.adb.shell("cat /sys/class/thermal/thermal_zone0/temp", serial=serial)
        if res_therm.stdout.strip().isdigit():
            t_c = round(int(res_therm.stdout.strip()) / 1000.0, 1)
            specs.thermal_zones.append(f"SOC Temp: {t_c}°C")

        return specs


# ---------------------------------------------------------------------------
# System Tweaker
# ---------------------------------------------------------------------------

class SystemTweaker:
    """Manages system density, animation speeds, wireless ADB, and stay-awake."""

    def __init__(self, adb: Optional[ADB] = None) -> None:
        self.adb = adb or ADB()

    def get_animation_scales(self, serial: str = "") -> dict[str, float]:
        """Read window, transition, and animator duration scales."""
        scales = {}
        keys = {
            "window": "window_animation_scale",
            "transition": "transition_animation_scale",
            "animator": "animator_duration_scale",
        }
        for label, key in keys.items():
            res = self.adb.shell(f"settings get global {key}", serial=serial)
            try:
                scales[label] = float(res.stdout.strip())
            except ValueError:
                scales[label] = 1.0
        return scales

    def set_animation_scales(self, scale: float, serial: str = "") -> tuple[bool, str]:
        """Set all animation scales (e.g. 0.0 for snappy, 0.5 for fast, 1.0 default)."""
        s_val = str(scale)
        self.adb.shell(f"settings put global window_animation_scale {s_val}", serial=serial)
        self.adb.shell(f"settings put global transition_animation_scale {s_val}", serial=serial)
        self.adb.shell(f"settings put global animator_duration_scale {s_val}", serial=serial)
        return True, f"Animation scales set to {scale}x"

    def set_screen_density(self, density: int, serial: str = "") -> tuple[bool, str]:
        """Adjust screen DPI."""
        if density < 120 or density > 800:
            return False, "Density must be between 120 and 800 DPI."
        res = self.adb.shell(f"wm density {density}", serial=serial)
        return True, f"Screen density adjusted to {density} DPI."

    def reset_screen_density(self, serial: str = "") -> tuple[bool, str]:
        """Restore default device screen DPI."""
        self.adb.shell("wm density reset", serial=serial)
        return True, "Screen density reset to factory default."

    def enable_wireless_adb(self, serial: str = "") -> tuple[bool, str]:
        """Enable ADB over TCP on port 5555 and discover device Wi-Fi IP."""
        # 1. Set TCP port
        self.adb.shell("setprop service.adb.tcp.port 5555", serial=serial)
        self.adb.tcpip(port=5555, serial=serial)

        # 2. Extract IP address
        res_ip = self.adb.shell("ip -f inet addr show wlan0", serial=serial)
        m = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)", res_ip.stdout)
        if m:
            ip = m.group(1)
            return True, f"Wireless ADB active! Connect via:\nadb connect {ip}:5555"

        # Fallback IP check
        res_ip2 = self.adb.shell("getprop dhcp.wlan0.ipaddress", serial=serial)
        ip2 = res_ip2.stdout.strip()
        if ip2:
            return True, f"Wireless ADB active! Connect via:\nadb connect {ip2}:5555"

        return True, "Wireless ADB enabled on port 5555. Check your phone's Wi-Fi settings for its IP."

    def set_stay_awake(self, enabled: bool, serial: str = "") -> tuple[bool, str]:
        """Toggle stay awake while charging."""
        val = 3 if enabled else 0
        self.adb.shell(f"settings put global stay_on_while_plugged_in {val}", serial=serial)
        return True, "Stay awake while charging: " + ("Enabled" if enabled else "Disabled")
