"""
FlashDock — Play Integrity Fixer, Diagnostic Engine & Fingerprint Spoofer (Phase 14).

Provides comprehensive tooling for bypassing Google Play Integrity (SafetyNet successor):
1. Device diagnostic engine querying bootloader lock state, SELinux, root solutions, and Zygisk.
2. Built-in vault of verified, certified stock fingerprints known to pass MEETS_DEVICE_INTEGRITY.
3. Automated 1-click pif.json generator, injector, and Google Play Services cache cleaner.
4. Zygisk DenyList / Shamiko banking app protector.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import re
from typing import Any, Optional

from flashdock.constants import DATA_DIR
from flashdock.core.device import DeviceInfo
from flashdock.tools.adb import ADB

log = logging.getLogger("flashdock.integrity")


@dataclass
class FingerprintProfile:
    """Definition of a certified Android build fingerprint profile used for spoofing."""

    id: str
    name: str
    manufacturer: str
    brand: str
    device: str
    model: str
    product: str
    fingerprint: str
    security_patch: str
    first_api_level: int
    release: str
    id_build: str = ""
    incremental: str = ""
    type: str = "user"
    tags: str = "release-keys"

    def to_pif_dict(self) -> dict[str, Any]:
        """Convert to standard pif.json dictionary compatible with PlayIntegrityFix module."""
        data = {
            "MANUFACTURER": self.manufacturer,
            "BRAND": self.brand,
            "DEVICE": self.device,
            "MODEL": self.model,
            "PRODUCT": self.product,
            "FINGERPRINT": self.fingerprint,
            "SECURITY_PATCH": self.security_patch,
            "FIRST_API_LEVEL": str(self.first_api_level),
        }
        if self.id_build:
            data["ID"] = self.id_build
        if self.incremental:
            data["INCREMENTAL"] = self.incremental
        if self.type:
            data["TYPE"] = self.type
        if self.tags:
            data["TAGS"] = self.tags
        return data

    def to_pif_json(self, indent: int = 2) -> str:
        """Serialize profile to JSON formatted string."""
        return json.dumps(self.to_pif_dict(), indent=indent)


# ---------------------------------------------------------------------------
# Built-in Verified Certified Fingerprint Vault
# Profiles with first_api_level <= 32 (Android 12 or older) trigger
# software-backed key attestation fallback on Google Play Services,
# allowing unlocked bootloaders to pass MEETS_DEVICE_INTEGRITY.
# ---------------------------------------------------------------------------
BUILTIN_PROFILES: list[FingerprintProfile] = [
    FingerprintProfile(
        id="pixel_5",
        name="Google Pixel 5 (Android 11 Stock)",
        manufacturer="Google",
        brand="google",
        device="redfin",
        model="Pixel 5",
        product="redfin",
        fingerprint="google/redfin/redfin:11/RQ3A.211001.001/7641976:user/release-keys",
        security_patch="2021-10-05",
        first_api_level=30,
        release="11",
        id_build="RQ3A.211001.001",
    ),
    FingerprintProfile(
        id="pixel_4a",
        name="Google Pixel 4a (Android 11 Stock)",
        manufacturer="Google",
        brand="google",
        device="sunfish",
        model="Pixel 4a",
        product="sunfish",
        fingerprint="google/sunfish/sunfish:11/RQ3A.210905.001/7511028:user/release-keys",
        security_patch="2021-09-05",
        first_api_level=29,
        release="11",
        id_build="RQ3A.210905.001",
    ),
    FingerprintProfile(
        id="pixel_3a_xl",
        name="Google Pixel 3a XL (Android 9 Stock)",
        manufacturer="Google",
        brand="google",
        device="bonito",
        model="Pixel 3a XL",
        product="bonito",
        fingerprint="google/bonito/bonito:9/PQ3B.190801.002/5670851:user/release-keys",
        security_patch="2019-08-01",
        first_api_level=28,
        release="9",
        id_build="PQ3B.190801.002",
    ),
    FingerprintProfile(
        id="xiaomi_poco_f1",
        name="Xiaomi POCO F1 (MIUI 11 / Android 9)",
        manufacturer="Xiaomi",
        brand="POCO",
        device="beryllium",
        model="POCO F1",
        product="beryllium",
        fingerprint="Xiaomi/beryllium/beryllium:9/PKQ1.180729.001/V11.0.5.0.PEJMIXM:user/release-keys",
        security_patch="2019-10-01",
        first_api_level=27,
        release="9",
        id_build="PKQ1.180729.001",
    ),
    FingerprintProfile(
        id="oneplus_7_pro",
        name="OnePlus 7 Pro (OxygenOS 10 / Android 10)",
        manufacturer="OnePlus",
        brand="OnePlus",
        device="OnePlus7Pro",
        model="GM1913",
        product="OnePlus7Pro",
        fingerprint="OnePlus/OnePlus7Pro_EEA/OnePlus7Pro:10/QKQ1.190716.003/2011052225:user/release-keys",
        security_patch="2020-10-01",
        first_api_level=28,
        release="10",
        id_build="QKQ1.190716.003",
    ),
    FingerprintProfile(
        id="samsung_galaxy_s9",
        name="Samsung Galaxy S9 (One UI / Android 10)",
        manufacturer="samsung",
        brand="samsung",
        device="starlte",
        model="SM-G960F",
        product="starltexx",
        fingerprint="samsung/starltexx/starlte:10/QP1A.190711.020/G960FXXU7DTAA:user/release-keys",
        security_patch="2020-02-01",
        first_api_level=26,
        release="10",
        id_build="QP1A.190711.020",
    ),
    FingerprintProfile(
        id="moto_edge_20",
        name="Motorola Edge 20 (Android 11 Stock)",
        manufacturer="motorola",
        brand="motorola",
        device="berlin",
        model="motorola edge 20",
        product="berlin_retail",
        fingerprint="motorola/berlin_retail/berlin:11/RRG31.Q3-23-50/5f6b9:user/release-keys",
        security_patch="2021-11-01",
        first_api_level=30,
        release="11",
        id_build="RRG31.Q3-23-50",
    ),
]


@dataclass
class IntegrityDiagnostic:
    """Live diagnosis of Play Integrity readiness and security verdicts."""

    bootloader_status: str  # "Locked", "Unlocked", "Unknown"
    selinux_status: str     # "Enforcing", "Permissive", "Unknown"
    root_type: str          # "Magisk", "KernelSU", "APatch", "None", "Unknown"
    zygisk_active: bool
    pif_module_installed: bool
    custom_pif_active: bool
    current_spoofed_model: str = ""
    verdict_basic: str = "Unknown"   # "Pass", "Fail", "Warning"
    verdict_device: str = "Unknown"  # "Pass", "Fail", "Warning"
    verdict_strong: str = "Notice"   # "Hardware Locked Only"
    recommendations: list[str] = field(default_factory=list)


# Popular banking, fintech, and security-sensitive apps to protect
RECOMMENDED_PROTECTED_PACKAGES: list[tuple[str, str]] = [
    ("com.google.android.gms", "Google Play Services"),
    ("com.android.vending", "Google Play Store"),
    ("com.google.android.apps.walletnfcrel", "Google Wallet"),
    ("com.paypal.android.p2pmobile", "PayPal"),
    ("com.revolut.revolut", "Revolut"),
    ("com.chase.sig.android", "Chase Mobile"),
    ("com.wf.wellsfargomobile", "Wells Fargo Mobile"),
    ("com.bofa.mobilebanking", "Bank of America"),
    ("com.citibank.mobile.us", "Citi Mobile"),
    ("com.mcdonalds.app", "McDonald's App"),
    ("com.netflix.mediaclient", "Netflix"),
    ("com.nianticlabs.pokemongo", "Pokémon GO"),
]


class PlayIntegrityFixer:
    """Manages Google Play Integrity diagnostics, fingerprint spoofing, and cache cleaning."""

    def __init__(self, adb: Optional[ADB] = None) -> None:
        self.adb = adb or ADB()

    def _run_shell(self, cmd: str, serial: str = "") -> str:
        """Execute shell command and safely extract stdout text."""
        res = self.adb.shell(cmd, serial=serial)
        if hasattr(res, "stdout"):
            return res.stdout
        if isinstance(res, tuple):
            return str(res[0])
        return str(res)

    def _push_file(self, local: Path, remote: str, serial: str = "") -> bool:
        """Push file to device and safely check success."""
        res = self.adb.push(str(local), remote, serial=serial)
        if hasattr(res, "success"):
            return res.success
        if isinstance(res, bool):
            return res
        return True

    def diagnose_device(self, device: Optional[DeviceInfo]) -> IntegrityDiagnostic:
        """Run deep checks over ADB to evaluate Play Integrity readiness."""
        if not device or device.mode != "system":
            return IntegrityDiagnostic(
                bootloader_status="Unknown",
                selinux_status="Unknown",
                root_type="None",
                zygisk_active=False,
                pif_module_installed=False,
                custom_pif_active=False,
                verdict_basic="Unknown",
                verdict_device="Unknown",
                verdict_strong="Notice: Hardware Attestation Required",
                recommendations=["Connect an Android device booted into System OS with USB debugging enabled."],
            )

        serial = device.serial

        # 1. Check Bootloader State
        if hasattr(self.adb, "get_all_props"):
            props = self.adb.get_all_props(serial=serial)
        elif hasattr(self.adb, "getprops"):
            props = self.adb.getprops(serial)
        else:
            props = {}

        bl_locked_prop = props.get("ro.boot.flash.locked", "")
        vb_state = props.get("ro.boot.verifiedbootstate", "")
        is_unlocked = (bl_locked_prop == "0") or (vb_state in ("orange", "yellow"))
        bootloader_status = "Unlocked" if is_unlocked else "Locked"

        # 2. Check SELinux Enforcing
        selinux_out = self._run_shell("getenforce", serial=serial)
        selinux_status = selinux_out.strip() if selinux_out else "Unknown"

        # 3. Check Root Type & Zygisk
        root_type = "None"
        if device.is_rooted:
            root_type = device.root_method or "Rooted"
        else:
            # Check su binary
            su_check = self._run_shell("which su", serial=serial)
            if "/su" in su_check:
                root_type = "Generic SU"

        # Check Zygisk
        zygisk_out = self._run_shell("magisk -v; su -c 'magisk resetprop -v' 2>/dev/null", serial=serial)
        zygisk_active = ("zygisk" in zygisk_out.lower()) or ("magisk" in zygisk_out.lower())

        # 4. Check PIF module & custom pif.json
        pif_check = self._run_shell(
            "test -d /data/adb/modules/playintegrityfix && echo 'MODULE_EXISTS'; "
            "test -f /data/adb/pif.json && echo 'PIF_JSON_EXISTS'",
            serial=serial,
        )
        pif_module_installed = "MODULE_EXISTS" in pif_check
        custom_pif_active = "PIF_JSON_EXISTS" in pif_check

        current_spoofed_model = ""
        if custom_pif_active:
            cat_out = self._run_shell("cat /data/adb/pif.json 2>/dev/null", serial=serial)
            try:
                p_data = json.loads(cat_out)
                current_spoofed_model = f"{p_data.get('BRAND', '')} {p_data.get('MODEL', '')}".strip()
            except Exception:
                current_spoofed_model = "Custom pif.json detected"

        # 5. Evaluate Expected Verdicts
        recs: list[str] = []

        if is_unlocked:
            if pif_module_installed or custom_pif_active:
                verdict_basic = "Pass"
                verdict_device = "Pass"
                recs.append("✅ Certified fingerprint active. MEETS_DEVICE_INTEGRITY should pass.")
            else:
                verdict_basic = "Fail"
                verdict_device = "Fail"
                recs.append("⚠️ Bootloader is unlocked and no Play Integrity Fix module or pif.json was found.")
                recs.append("👉 Inject a certified fingerprint below to bypass Google Play Integrity.")
        else:
            verdict_basic = "Pass"
            verdict_device = "Pass"
            recs.append("Device bootloader is locked. Stock integrity passes naturally.")

        if selinux_status.lower() == "permissive":
            verdict_basic = "Fail"
            recs.append("⚠️ SELinux is Permissive. Most banking apps block permissive SELinux.")

        return IntegrityDiagnostic(
            bootloader_status=bootloader_status,
            selinux_status=selinux_status,
            root_type=root_type,
            zygisk_active=zygisk_active,
            pif_module_installed=pif_module_installed,
            custom_pif_active=custom_pif_active,
            current_spoofed_model=current_spoofed_model,
            verdict_basic=verdict_basic,
            verdict_device=verdict_device,
            verdict_strong="Notice: Hardware Keystore Required (Locked BL Only)",
            recommendations=recs,
        )

    def inject_profile(
        self,
        serial: str,
        profile: FingerprintProfile,
        clear_gms: bool = True,
    ) -> tuple[bool, str]:
        """Inject a FingerprintProfile into the device's /data/adb/pif.json."""
        pif_content = profile.to_pif_json()
        return self.inject_pif_json(serial, pif_content, clear_gms=clear_gms)

    def inject_pif_json(
        self,
        serial: str,
        pif_json_str: str,
        clear_gms: bool = True,
    ) -> tuple[bool, str]:
        """Write pif.json content to /data/adb/pif.json and set proper permissions."""
        if not serial:
            return False, "No device connected."

        # Validate JSON format
        try:
            parsed = json.loads(pif_json_str)
            if not isinstance(parsed, dict) or "FINGERPRINT" not in parsed:
                return False, "Invalid pif.json structure: must contain 'FINGERPRINT' key."
        except Exception as exc:
            return False, f"JSON parse error: {exc}"

        log.info("Injecting pif.json to device %s...", serial)

        # Temporary local file
        tmp_local = DATA_DIR / "cache" / f"pif_{serial}.json"
        tmp_local.parent.mkdir(parents=True, exist_ok=True)
        tmp_local.write_text(pif_json_str, encoding="utf-8")

        # Push to /data/local/tmp first, then copy with root/su to /data/adb/pif.json
        push_ok = self._push_file(tmp_local, "/data/local/tmp/pif.json", serial=serial)
        if not push_ok:
            return False, "Failed to transfer pif.json to device /data/local/tmp."

        # Copy to /data/adb/pif.json and /data/adb/modules/playintegrityfix/pif.json
        cmd = (
            "su -c '"
            "cp /data/local/tmp/pif.json /data/adb/pif.json && "
            "chmod 644 /data/adb/pif.json && "
            "mkdir -p /data/adb/modules/playintegrityfix && "
            "cp /data/local/tmp/pif.json /data/adb/modules/playintegrityfix/pif.json && "
            "chmod 644 /data/adb/modules/playintegrityfix/pif.json && "
            "rm -f /data/local/tmp/pif.json && echo SUCCESS"
            "' 2>&1"
        )
        out = self._run_shell(cmd, serial=serial)

        if "SUCCESS" not in out:
            # Fallback attempt without su if already root shell
            fallback_cmd = (
                "cp /data/local/tmp/pif.json /data/adb/pif.json 2>/dev/null && "
                "chmod 644 /data/adb/pif.json 2>/dev/null && echo SUCCESS"
            )
            fb_out = self._run_shell(fallback_cmd, serial=serial)
            if "SUCCESS" not in fb_out:
                return False, (
                    f"Could not copy pif.json to /data/adb/:\n{out}\n"
                    "Ensure your phone is rooted (Magisk, KernelSU, or APatch) and granted root permissions."
                )

        msg = "Successfully injected certified pif.json fingerprint into /data/adb/pif.json."

        # Clear Google Play Services cache if requested
        if clear_gms:
            gms_ok, gms_msg = self.clear_gms_cache(serial)
            msg += f"\n\nGoogle Play Services Cache: {gms_msg}"

        return True, msg

    def clear_gms_cache(self, serial: str) -> tuple[bool, str]:
        """Kill Google Play Services unstable process and clear caches to force verdict re-evaluation."""
        if not serial:
            return False, "No device connected."

        log.info("Clearing GMS and Play Store cache on %s...", serial)
        # Commands: Kill unstable background process & clear vending cache
        cmds = [
            "su -c 'killall -9 com.google.android.gms.unstable 2>/dev/null'",
            "su -c 'rm -rf /data/data/com.google.android.gms/cache/* 2>/dev/null'",
            "su -c 'rm -rf /data/data/com.android.vending/cache/* 2>/dev/null'",
            "su -c 'am force-stop com.google.android.gms 2>/dev/null'",
            "su -c 'am force-stop com.android.vending 2>/dev/null'",
        ]
        combined = "; ".join(cmds) + "; echo DONE"
        out = self._run_shell(combined, serial=serial)

        if "DONE" in out:
            return True, "Killed unstable GMS processes and cleared caches. Play Integrity cache refreshed."
        return False, "Could not completely clear GMS cache via su."

    def add_package_to_denylist(self, serial: str, package_name: str) -> tuple[bool, str]:
        """Add package to Magisk DenyList via `magisk --denylist add <pkg>`."""
        if not serial:
            return False, "No device connected."

        pkg = package_name.strip()
        if not pkg:
            return False, "Package name cannot be empty."

        cmd = f"su -c 'magisk --denylist add {pkg} 2>&1'"
        out = self._run_shell(cmd, serial=serial)
        if "error" in out.lower() or "not found" in out.lower():
            return False, f"Magisk DenyList command error:\n{out}"
        return True, f"Added '{pkg}' to Magisk DenyList."

    def read_device_pif(self, serial: str) -> Optional[dict[str, Any]]:
        """Read active /data/adb/pif.json from device if present."""
        if not serial:
            return None
        out = self._run_shell("su -c 'cat /data/adb/pif.json 2>/dev/null'", serial=serial)
        if not out or not out.strip().startswith("{"):
            return None
        try:
            return json.loads(out)
        except Exception:
            return None
