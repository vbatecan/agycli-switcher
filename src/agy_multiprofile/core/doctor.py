"""
Health check and diagnostic verification engine.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from agy_multiprofile.core.constants import (
    MANAGED_FILES,
    MANIFEST_FILENAME,
    PROFILE_META_FILENAME,
    PROFILES_DIRNAME,
    get_gemini_home,
    get_profile_home,
)
from agy_multiprofile.core.detector import check_brain_locks, find_running_antigravity_processes
from agy_multiprofile.core.keyring import get_keyring_token, has_keyring_support
from agy_multiprofile.core.models import ValidationResult
from agy_multiprofile.utils.json_utils import safe_load_json


def validate_profile(profile_dir: Path) -> ValidationResult:
    """Validate that a profile directory has valid metadata and uncorrupted JSON files."""
    result = ValidationResult(is_valid=True)
    if not profile_dir.exists() or not profile_dir.is_dir():
        result.add_error(f"Profile directory does not exist: {profile_dir}")
        return result

    # Check profile metadata
    meta_path = profile_dir / PROFILE_META_FILENAME
    if not meta_path.exists():
        result.add_error(f"Missing {PROFILE_META_FILENAME} in {profile_dir.name}")
    else:
        success, data, err = safe_load_json(meta_path)
        if not success:
            result.add_error(f"Corrupt {PROFILE_META_FILENAME} in {profile_dir.name}: {err}")
        elif not isinstance(data, dict) or not data.get("name"):
            result.add_error(f"Invalid {PROFILE_META_FILENAME} schema in {profile_dir.name}")

    # Check all managed files in the profile
    for spec in MANAGED_FILES:
        target_path = profile_dir / spec.profile_filename
        if target_path.exists() and spec.is_json:
            success, _, err = safe_load_json(target_path)
            if not success:
                result.add_error(f"Corrupt JSON in {profile_dir.name}/{spec.profile_filename}: {err}")

    return result


def run_doctor(profile_home: Path | None = None, gemini_home: Path | None = None) -> ValidationResult:
    """
    Perform full system diagnostics and health checks on vault, profiles, and gemini environment.
    """
    vault = profile_home or get_profile_home()
    gemini = gemini_home or get_gemini_home()
    result = ValidationResult(is_valid=True)

    # 1. Check Gemini environment
    if not gemini.exists():
        result.add_warning(f"Gemini home directory does not exist yet: {gemini}")
    else:
        if not os.access(gemini, os.R_OK | os.W_OK):
            result.add_error(f"Insufficient read/write permissions for Gemini home: {gemini}")
        else:
            result.add_info(f"Gemini home: {gemini} (Accessible)")

    # 2. Check CLI binary and shim status
    from agy_multiprofile.core.launcher import find_agy_binary, is_self_binary
    agy_bin = shutil.which("agy")
    real_bin = find_agy_binary(vault)
    if agy_bin:
        p_agy = Path(agy_bin).resolve()
        if is_self_binary(p_agy):
            if real_bin:
                result.add_info(f"Antigravity CLI 'agy' is intercepted by agy-profile shim (Real binary: {real_bin})")
            else:
                result.add_warning("Antigravity CLI 'agy' is a switcher shim, but underlying real 'agy' binary could not be found.")
        else:
            result.add_info(f"Antigravity CLI binary found at: {agy_bin}")
    else:
        if real_bin:
            result.add_info(f"Antigravity CLI binary found at: {real_bin}")
        else:
            result.add_warning("Antigravity CLI binary 'agy' was not found on PATH")

    # 3. Check gcloud CLI
    gcloud_bin = shutil.which("gcloud")
    if gcloud_bin:
        result.add_info(f"Google Cloud SDK binary found at: {gcloud_bin}")
    else:
        result.add_info("Google Cloud SDK 'gcloud' is not installed (optional)")

    # 4. Check OS Keyring Integration
    if has_keyring_support():
        token = get_keyring_token()
        if token:
            result.add_info("OS Keyring: Accessible (Active OAuth credentials found)")
        else:
            result.add_info("OS Keyring: Accessible (No OAuth credentials stored)")
    else:
        result.add_warning("OS Keyring: No supported keyring utility found (install secret-tool on Linux)")

    # 5. Check Vault and Manifest
    if not vault.exists():
        result.add_info(f"Vault has not been initialized yet at: {vault}")
        return result

    manifest_path = vault / MANIFEST_FILENAME
    if not manifest_path.exists():
        result.add_warning(f"Vault manifest not found at: {manifest_path}")
    else:
        success, m_data, err = safe_load_json(manifest_path)
        if not success:
            result.add_error(f"Corrupt manifest.json: {err}")
        else:
            active_name = m_data.get("active_profile", "")
            result.add_info(f"Active profile recorded in manifest: '{active_name}'")

    # 5. Check Profiles
    profiles_dir = vault / PROFILES_DIRNAME
    if profiles_dir.exists():
        for p_dir in profiles_dir.iterdir():
            if p_dir.is_dir() and not p_dir.name.startswith("."):
                p_res = validate_profile(p_dir)
                for err in p_res.errors:
                    result.add_error(err)
                for warn in p_res.warnings:
                    result.add_warning(warn)

    # 6. Check Active Processes & Locks
    running = find_running_antigravity_processes()
    if running:
        pids = ", ".join(f"{p['name']}(pid={p['pid']})" for p in running)
        result.add_warning(f"Active Antigravity processes detected: {pids}")

    brain_locks = check_brain_locks(gemini)
    if brain_locks:
        result.add_info(f"Found {len(brain_locks)} session lock file(s) in brain directory")

    return result
