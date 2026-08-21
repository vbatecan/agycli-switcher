"""
Pytest fixtures for agy-multiprofile testing.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from agy_multiprofile.core.constants import MANAGED_FILES
from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.switcher import ProfileSwitcher


@pytest.fixture(autouse=True)
def disable_real_launch(monkeypatch):
    """Ensure tests do not inadvertently launch a real interactive agy session or mutate system keyring."""
    monkeypatch.setenv("AGY_NO_LAUNCH", "1")
    monkeypatch.setenv("AGY_KEYRING_DISABLED", "1")


@pytest.fixture
def temp_gemini_home(tmp_path: Path) -> Path:
    """Create a mock ~/.gemini directory with sample configuration files."""
    gemini_dir = tmp_path / "mock_gemini"
    gemini_dir.mkdir(parents=True, exist_ok=True)

    # 1. Global settings
    (gemini_dir / "settings.json").write_text(
        json.dumps({
            "security": {"auth": {"selectedType": "gateway"}},
            "ide": {"enabled": True},
        }, indent=2),
        encoding="utf-8"
    )

    # 2. CLI settings
    cli_dir = gemini_dir / "antigravity-cli"
    cli_dir.mkdir(parents=True, exist_ok=True)
    (cli_dir / "settings.json").write_text(
        json.dumps({
            "model": "Gemini 3.7 Flash (High)",
            "permissions": {"allow": ["command(git status)"]},
            "editor": "vim",
            "trustedWorkspaces": ["/mock/project"]
        }, indent=2),
        encoding="utf-8"
    )

    # 3. MCP config
    config_dir = gemini_dir / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "mcp_config.json").write_text(
        json.dumps({
            "mcpServers": {
                "server_a": {"command": "echo", "args": ["a"]}
            }
        }, indent=2),
        encoding="utf-8"
    )

    # 4. MCP OAuth tokens
    (cli_dir / "mcp_oauth_tokens.json").write_text(json.dumps({}, indent=2), encoding="utf-8")

    # 5. Global hooks
    (config_dir / "hooks.json").write_text(json.dumps({"hooks": {}}, indent=2), encoding="utf-8")

    # 6. CLI hooks
    (cli_dir / "hooks.json").write_text(json.dumps({"SessionStart": []}, indent=2), encoding="utf-8")

    # 7. Plugins config
    (config_dir / "config.json").write_text(
        json.dumps({"plugins": {"code-review": {"enabled": True}}}, indent=2),
        encoding="utf-8"
    )

    # 8. Google accounts
    (gemini_dir / "google_accounts.json").write_text(
        json.dumps({"active": "testuser@gmail.com", "old": []}, indent=2),
        encoding="utf-8"
    )

    # 9. Trusted Folders
    (gemini_dir / "trustedFolders.json").write_text(
        json.dumps({"/mock/project": "TRUST_PARENT"}, indent=2),
        encoding="utf-8"
    )

    return gemini_dir


@pytest.fixture
def temp_vault_home(tmp_path: Path) -> Path:
    """Create an isolated ~/.config/agy-profile directory."""
    vault_dir = tmp_path / "mock_vault"
    vault_dir.mkdir(parents=True, exist_ok=True)
    return vault_dir


@pytest.fixture
def store(temp_vault_home: Path, temp_gemini_home: Path) -> ProfileStore:
    """Create a ProfileStore bound to temp directories."""
    return ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)


@pytest.fixture
def switcher(store: ProfileStore, temp_gemini_home: Path) -> ProfileSwitcher:
    """Create a ProfileSwitcher bound to temp store."""
    return ProfileSwitcher(store=store, gemini_home=temp_gemini_home)
