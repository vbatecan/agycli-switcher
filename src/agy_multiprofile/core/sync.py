"""
Synchronization engine between active ~/.gemini configuration and profile vault storage.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agy_multiprofile.core.auth import capture_keyring_token_to_profile
from agy_multiprofile.core.constants import AUTH_TOKEN_FILENAME, MANAGED_FILES, ManagedFileSpec, get_gemini_home
from agy_multiprofile.utils.atomic import TransactionContext, atomic_copy_file, atomic_write_json
from agy_multiprofile.utils.json_utils import safe_load_json


def capture_live_to_profile(profile_dir: Path, gemini_home: Path | None = None) -> list[str]:
    """
    Capture live configuration files from gemini_home into the profile directory.
    Also captures active OS Keyring OAuth token into auth_token.json.
    Returns the list of relative filepaths captured.
    """
    home = gemini_home or get_gemini_home()
    profile_dir.mkdir(parents=True, exist_ok=True)
    captured: list[str] = []

    for spec in MANAGED_FILES:
        live_file = home / spec.relative_live_path
        target_file = profile_dir / spec.profile_filename

        if live_file.exists():
            if spec.is_json:
                success, data, err = safe_load_json(live_file)
                if success:
                    atomic_write_json(target_file, data)
                else:
                    atomic_copy_file(live_file, target_file)
            else:
                atomic_copy_file(live_file, target_file)
            captured.append(spec.relative_live_path)
        else:
            # If live file doesn't exist, create an empty JSON object in profile if it's JSON
            if spec.is_json and not target_file.exists():
                atomic_write_json(target_file, {})
                captured.append(spec.relative_live_path)

    # Capture OS Keyring OAuth token
    if capture_keyring_token_to_profile(profile_dir):
        captured.append(AUTH_TOKEN_FILENAME)

    return captured


def apply_profile_to_live(
    profile_dir: Path, transaction: TransactionContext, gemini_home: Path | None = None
) -> list[str]:
    """
    Apply profile configuration files to gemini_home using the transactional context.
    Returns the list of relative live filepaths updated.
    """
    home = gemini_home or get_gemini_home()
    applied: list[str] = []

    for spec in MANAGED_FILES:
        profile_file = profile_dir / spec.profile_filename
        live_file = home / spec.relative_live_path

        if profile_file.exists():
            transaction.record_and_replace(dest_path=live_file, new_content_path=profile_file)
            applied.append(spec.relative_live_path)

    return applied


def load_profile_files(profile_dir: Path) -> dict[str, Any]:
    """
    Load all managed files for a given profile directory into a dictionary mapping keys to parsed content.
    """
    result: dict[str, Any] = {}
    for spec in MANAGED_FILES:
        profile_file = profile_dir / spec.profile_filename
        if profile_file.exists():
            success, data, _ = safe_load_json(profile_file)
            result[spec.key] = data if success else {}
        else:
            result[spec.key] = {}
    return result


def load_live_files(gemini_home: Path | None = None) -> dict[str, Any]:
    """
    Load all active managed files from ~/.gemini into a dictionary mapping keys to parsed content.
    """
    home = gemini_home or get_gemini_home()
    result: dict[str, Any] = {}
    for spec in MANAGED_FILES:
        live_file = home / spec.relative_live_path
        if live_file.exists():
            success, data, _ = safe_load_json(live_file)
            result[spec.key] = data if success else {}
        else:
            result[spec.key] = {}
    return result
