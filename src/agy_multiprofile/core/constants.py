"""
Constants and path mappings for agy-multiprofile.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def get_profile_home() -> Path:
    """Return the profile store root directory (~/.config/agy-profile or $AGY_PROFILE_HOME)."""
    env_path = os.environ.get("AGY_PROFILE_HOME")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (Path.home() / ".config" / "agy-profile").resolve()


def get_gemini_home() -> Path:
    """Return the gemini configuration root directory (~/.gemini or $GEMINI_HOME)."""
    env_path = os.environ.get("GEMINI_HOME")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (Path.home() / ".gemini").resolve()


def get_gcloud_config_home() -> Path:
    """Return the gcloud configuration root directory (~/.config/gcloud or $CLOUDSDK_CONFIG)."""
    env_path = os.environ.get("CLOUDSDK_CONFIG")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return (Path.home() / ".config" / "gcloud").resolve()


@dataclass(frozen=True)
class ManagedFileSpec:
    """Specification of a managed configuration file."""
    key: str
    relative_live_path: str
    profile_filename: str
    description: str
    is_json: bool = True
    default_factory_func: str = "dict"  # 'dict' or 'list' or 'text'


# The registry of all configuration files managed by a profile
MANAGED_FILES: list[ManagedFileSpec] = [
    ManagedFileSpec(
        key="cli_settings",
        relative_live_path="antigravity-cli/settings.json",
        profile_filename="cli_settings.json",
        description="Antigravity CLI settings (model, permissions, editor, sandbox)",
    ),
    ManagedFileSpec(
        key="global_settings",
        relative_live_path="settings.json",
        profile_filename="settings.json",
        description="Global Gemini/Antigravity settings (gateway auth, general)",
    ),
    ManagedFileSpec(
        key="mcp_config",
        relative_live_path="config/mcp_config.json",
        profile_filename="mcp_config.json",
        description="Global Model Context Protocol (MCP) server definitions",
    ),
    ManagedFileSpec(
        key="mcp_oauth",
        relative_live_path="antigravity-cli/mcp_oauth_tokens.json",
        profile_filename="mcp_oauth.json",
        description="MCP server OAuth tokens",
    ),
    ManagedFileSpec(
        key="global_hooks",
        relative_live_path="config/hooks.json",
        profile_filename="hooks.json",
        description="Global lifecycle hooks",
    ),
    ManagedFileSpec(
        key="cli_hooks",
        relative_live_path="antigravity-cli/hooks.json",
        profile_filename="cli_hooks.json",
        description="Antigravity CLI lifecycle hooks",
    ),
    ManagedFileSpec(
        key="plugins_config",
        relative_live_path="config/config.json",
        profile_filename="config.json",
        description="Installed plugins toggle state and user settings",
    ),
    ManagedFileSpec(
        key="google_accounts",
        relative_live_path="google_accounts.json",
        profile_filename="google_accounts.json",
        description="Google account active state",
    ),
    ManagedFileSpec(
        key="trusted_folders",
        relative_live_path="trustedFolders.json",
        profile_filename="trusted_folders.json",
        description="Trusted workspaces and project folders",
    ),
]

MANIFEST_FILENAME = "manifest.json"
PROFILE_META_FILENAME = "profile.json"
AUTH_TOKEN_FILENAME = "auth_token.json"
LOCK_FILENAME = ".lock"
BACKUPS_DIRNAME = "backups"
TRASH_DIRNAME = "trash"
PROFILES_DIRNAME = "profiles"
MAX_BACKUPS_RETENTION = 25
DEFAULT_PROFILE_NAME = "default"
