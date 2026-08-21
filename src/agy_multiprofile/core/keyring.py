"""
Native, zero-dependency OS Keyring manager for Antigravity & Gemini OAuth tokens.
Supports Linux (Secret Service / secret-tool), macOS (Keychain), and Windows.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from typing import Any


def has_keyring_support() -> bool:
    """Check if the current platform has a supported keyring utility available."""
    if os.environ.get("AGY_KEYRING_DISABLED", "").lower() in ("1", "true", "yes"):
        return False

    if sys.platform.startswith("linux"):
        return shutil.which("secret-tool") is not None
    elif sys.platform == "darwin":
        return shutil.which("security") is not None
    elif sys.platform.startswith("win"):
        return shutil.which("cmdkey") is not None
    return False


def get_keyring_token(service: str = "gemini", username: str = "antigravity") -> dict[str, Any] | str | None:
    """
    Retrieve stored OAuth token / credentials from OS Keyring.
    Returns parsed JSON dict if possible, or raw string, or None if not found/error.
    """
    if os.environ.get("AGY_KEYRING_DISABLED", "").lower() in ("1", "true", "yes"):
        return None

    try:
        if sys.platform.startswith("linux"):
            if not shutil.which("secret-tool"):
                return None
            res = subprocess.run(
                ["secret-tool", "lookup", "service", service, "username", username],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                raw = res.stdout.strip()
                try:
                    return json.loads(raw)
                except Exception:
                    return raw
            return None

        elif sys.platform == "darwin":
            if not shutil.which("security"):
                return None
            res = subprocess.run(
                ["security", "find-generic-password", "-s", service, "-a", username, "-w"],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                raw = res.stdout.strip()
                try:
                    return json.loads(raw)
                except Exception:
                    return raw
            return None

        elif sys.platform.startswith("win"):
            # Windows Credential Manager lookup via PowerShell
            ps_cmd = (
                f"[void][Windows.Security.Credentials.PasswordVault,Windows.Security.Credentials,ContentType=WindowsRuntime];"
                f"$v = New-Object Windows.Security.Credentials.PasswordVault;"
                f"try {{ $c = $v.Retrieve('{service}', '{username}'); $c.RetrievePassword(); $c.Password }} catch {{ }}"
            )
            res = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            if res.returncode == 0 and res.stdout.strip():
                raw = res.stdout.strip()
                try:
                    return json.loads(raw)
                except Exception:
                    return raw
            return None

    except Exception:
        return None

    return None


def set_keyring_token(
    token_data: dict[str, Any] | str,
    service: str = "gemini",
    username: str = "antigravity",
    label: str | None = None,
) -> bool:
    """
    Store OAuth token / credentials in the OS Keyring.
    """
    if os.environ.get("AGY_KEYRING_DISABLED", "").lower() in ("1", "true", "yes"):
        return False

    raw_val = json.dumps(token_data) if isinstance(token_data, (dict, list)) else str(token_data)
    entry_label = label or f"Password for '{username}' on '{service}'"

    try:
        if sys.platform.startswith("linux"):
            if not shutil.which("secret-tool"):
                return False
            # secret-tool store --label="Label" service gemini username antigravity
            # Value is passed via standard input
            proc = subprocess.run(
                ["secret-tool", "store", f"--label={entry_label}", "service", service, "username", username],
                input=raw_val,
                text=True,
                capture_output=True,
                timeout=4.0,
            )
            return proc.returncode == 0

        elif sys.platform == "darwin":
            if not shutil.which("security"):
                return False
            # security add-generic-password -U -s service -a username -w password -l label
            proc = subprocess.run(
                [
                    "security",
                    "add-generic-password",
                    "-U",
                    "-s",
                    service,
                    "-a",
                    username,
                    "-l",
                    entry_label,
                    "-w",
                    raw_val,
                ],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            return proc.returncode == 0

        elif sys.platform.startswith("win"):
            # Windows Credential Manager storage via PowerShell
            escaped_val = raw_val.replace("'", "''")
            ps_cmd = (
                f"[void][Windows.Security.Credentials.PasswordVault,Windows.Security.Credentials,ContentType=WindowsRuntime];"
                f"$v = New-Object Windows.Security.Credentials.PasswordVault;"
                f"$c = New-Object Windows.Security.Credentials.PasswordCredential('{service}', '{username}', '{escaped_val}');"
                f"$v.Add($c);"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            return proc.returncode == 0

    except Exception:
        return False

    return False


def clear_keyring_token(service: str = "gemini", username: str = "antigravity") -> bool:
    """
    Remove OAuth token / credentials for the given service & username from the OS Keyring.
    """
    if os.environ.get("AGY_KEYRING_DISABLED", "").lower() in ("1", "true", "yes"):
        return False

    try:
        if sys.platform.startswith("linux"):
            if not shutil.which("secret-tool"):
                return False
            proc = subprocess.run(
                ["secret-tool", "clear", "service", service, "username", username],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            return proc.returncode == 0

        elif sys.platform == "darwin":
            if not shutil.which("security"):
                return False
            proc = subprocess.run(
                ["security", "delete-generic-password", "-s", service, "-a", username],
                capture_output=True,
                text=True,
                timeout=3.0,
            )
            return proc.returncode == 0

        elif sys.platform.startswith("win"):
            ps_cmd = (
                f"[void][Windows.Security.Credentials.PasswordVault,Windows.Security.Credentials,ContentType=WindowsRuntime];"
                f"$v = New-Object Windows.Security.Credentials.PasswordVault;"
                f"try {{ $c = $v.Retrieve('{service}', '{username}'); $v.Remove($c) }} catch {{ }}"
            )
            proc = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                capture_output=True,
                text=True,
                timeout=4.0,
            )
            return proc.returncode == 0

    except Exception:
        return False

    return False
