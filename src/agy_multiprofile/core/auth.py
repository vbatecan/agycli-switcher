"""
Authentication and Google / gcloud account synchronization.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from agy_multiprofile.core.constants import AUTH_TOKEN_FILENAME, get_gcloud_config_home, get_gemini_home
from agy_multiprofile.core.keyring import clear_keyring_token, get_keyring_token, set_keyring_token
from agy_multiprofile.utils.atomic import atomic_write_json
from agy_multiprofile.utils.json_utils import safe_load_json


def capture_keyring_token_to_profile(profile_dir: Path) -> bool:
    """
    Read active OAuth token from OS Keyring and persist it into profile_dir/auth_token.json.
    Sets owner-only (0600) permissions on the saved file.
    """
    token = get_keyring_token()
    if not token:
        return False

    token_file = profile_dir / AUTH_TOKEN_FILENAME
    profile_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_json(token_file, token if isinstance(token, dict) else {"raw": token})
    try:
        os.chmod(token_file, 0o600)
    except Exception:
        pass
    return True


def apply_profile_token_to_keyring(profile_dir: Path) -> tuple[bool, str]:
    """
    Apply profile's saved auth_token.json into the OS Keyring.
    If profile has no saved token, clears the keyring entry so agy prompts for a fresh login.
    """
    token_file = profile_dir / AUTH_TOKEN_FILENAME
    if token_file.exists():
        success, data, _ = safe_load_json(token_file)
        if success and data:
            # If wrapped in dict with "token" or "raw"
            token_payload = data if ("token" in data or "access_token" in data) else data.get("raw", data)
            ok = set_keyring_token(token_payload)
            if ok:
                return True, "Applied OAuth credentials to OS Keyring"
            return False, "Failed to write OAuth credentials to OS Keyring"

    # Profile has no credentials saved yet -> clear OS Keyring for fresh sign-in
    clear_keyring_token()
    return True, "Cleared OS Keyring for fresh profile login"


def get_profile_auth_token(profile_dir: Path) -> dict[str, Any] | None:
    """Read saved auth_token.json from profile directory."""
    token_file = profile_dir / AUTH_TOKEN_FILENAME
    if not token_file.exists():
        return None
    success, data, _ = safe_load_json(token_file)
    return data if success and isinstance(data, dict) else None


def get_live_google_accounts(gemini_home: Path | None = None) -> dict[str, Any]:
    """Read the current google_accounts.json from gemini home."""
    home = gemini_home or get_gemini_home()
    accounts_file = home / "google_accounts.json"
    if not accounts_file.exists():
        return {"active": None, "old": []}
    
    success, data, _ = safe_load_json(accounts_file)
    if success and isinstance(data, dict):
        return data
    return {"active": None, "old": []}


def set_live_google_account(email: str | None, gemini_home: Path | None = None) -> None:
    """
    Update active account in google_accounts.json safely.
    Moves previously active account to 'old' list without duplicates.
    """
    home = gemini_home or get_gemini_home()
    accounts_file = home / "google_accounts.json"
    current_data = get_live_google_accounts(home)
    
    active_now = current_data.get("active")
    old_list: list[str] = list(current_data.get("old") or [])
    
    if active_now and active_now != email and active_now not in old_list:
        old_list.append(active_now)
    
    # If new email was in old_list, remove it from old_list
    if email and email in old_list:
        old_list.remove(email)
    
    new_data = {
        "active": email,
        "old": old_list,
    }
    atomic_write_json(accounts_file, new_data)


def has_gcloud_cli() -> bool:
    """Check if gcloud CLI binary is available on PATH."""
    return shutil.which("gcloud") is not None


def get_gcloud_active_account() -> str | None:
    """Query currently active gcloud account."""
    if not has_gcloud_cli():
        return None
    try:
        res = subprocess.run(
            ["gcloud", "config", "get-value", "account"],
            capture_output=True,
            text=True,
            timeout=3.0,
        )
        if res.returncode == 0:
            val = res.stdout.strip()
            return val if val and val != "(unset)" else None
    except Exception:
        pass
    return None


def get_gcloud_active_configuration() -> str | None:
    """Query currently active gcloud configuration."""
    gcloud_home = get_gcloud_config_home()
    active_config_file = gcloud_home / "active_config"
    if active_config_file.exists():
        try:
            return active_config_file.read_text(encoding="utf-8").strip()
        except Exception:
            pass
    return None


def switch_gcloud_account(email: str) -> tuple[bool, str]:
    """
    Switch active gcloud account using `gcloud config set account <email>`.
    """
    if not has_gcloud_cli():
        return False, "gcloud CLI is not installed"
    try:
        res = subprocess.run(
            ["gcloud", "config", "set", "account", email],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if res.returncode == 0:
            return True, f"Switched gcloud account to {email}"
        return False, res.stderr.strip() or "Failed to set gcloud account"
    except Exception as e:
        return False, str(e)


def switch_gcloud_configuration(config_name: str) -> tuple[bool, str]:
    """
    Switch active gcloud configuration using `gcloud config configurations activate <name>`.
    """
    if not has_gcloud_cli():
        return False, "gcloud CLI is not installed"
    try:
        res = subprocess.run(
            ["gcloud", "config", "configurations", "activate", config_name],
            capture_output=True,
            text=True,
            timeout=5.0,
        )
        if res.returncode == 0:
            return True, f"Activated gcloud configuration '{config_name}'"
        return False, res.stderr.strip() or f"Failed to activate gcloud configuration '{config_name}'"
    except Exception as e:
        return False, str(e)
