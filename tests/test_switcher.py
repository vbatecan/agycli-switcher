"""
Tests for ProfileSwitcher, auto-sync, atomic switching, dry-run, and rollback.
"""

import json
from pathlib import Path
import pytest

from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.switcher import ProfileSwitcher
from agy_multiprofile.utils.atomic import atomic_write_json


def test_switch_profile_clean(store: ProfileStore, switcher: ProfileSwitcher, temp_gemini_home: Path):
    # Setup profile 'default' from live
    store.create_profile("default", clone_from_live=True)
    manifest = store.get_manifest()
    manifest.active_profile = "default"
    store.save_manifest(manifest)

    # Setup profile 'work' with distinct settings
    store.create_profile("work", email="work@company.com")
    work_dir = store.get_profile_dir("work")
    atomic_write_json(work_dir / "cli_settings.json", {"model": "Gemini 3.7 Pro", "editor": "nano"})
    atomic_write_json(work_dir / "mcp_config.json", {"mcpServers": {"work_mcp": {"command": "work_tool"}}})

    # Switch to 'work'
    res = switcher.switch_profile("work")
    assert res.success is True
    assert res.target_profile == "work"

    # Verify live gemini files were updated
    cli_settings_live = json.loads((temp_gemini_home / "antigravity-cli" / "settings.json").read_text(encoding="utf-8"))
    assert cli_settings_live["model"] == "Gemini 3.7 Pro"

    mcp_live = json.loads((temp_gemini_home / "config" / "mcp_config.json").read_text(encoding="utf-8"))
    assert "work_mcp" in mcp_live.get("mcpServers", {})

    acc_live = json.loads((temp_gemini_home / "google_accounts.json").read_text(encoding="utf-8"))
    assert acc_live["active"] == "work@company.com"


def test_switch_profile_isolated_by_default(store: ProfileStore, switcher: ProfileSwitcher, temp_gemini_home: Path):
    # Setup default profile
    store.create_profile("default", clone_from_live=True)
    manifest = store.get_manifest()
    manifest.active_profile = "default"
    store.save_manifest(manifest)

    store.create_profile("target_prof")

    # Simulate user modifying a live setting during their session in 'default'
    live_cli_settings = temp_gemini_home / "antigravity-cli" / "settings.json"
    data = json.loads(live_cli_settings.read_text(encoding="utf-8"))
    data["custom_new_permission"] = "allowed"
    atomic_write_json(live_cli_settings, data)

    # Switch to 'target_prof' without save_current (default isolation)
    res = switcher.switch_profile("target_prof")
    assert res.success is True

    # Verify that default profile in vault was NOT mutated
    default_dir = store.get_profile_dir("default")
    saved_default_cli = json.loads((default_dir / "cli_settings.json").read_text(encoding="utf-8"))
    assert "custom_new_permission" not in saved_default_cli


def test_switch_profile_explicit_save_current(store: ProfileStore, switcher: ProfileSwitcher, temp_gemini_home: Path):
    # Setup default profile
    store.create_profile("default", clone_from_live=True)
    manifest = store.get_manifest()
    manifest.active_profile = "default"
    store.save_manifest(manifest)

    store.create_profile("target_prof")

    # Simulate user modifying a live setting during their session in 'default'
    live_cli_settings = temp_gemini_home / "antigravity-cli" / "settings.json"
    data = json.loads(live_cli_settings.read_text(encoding="utf-8"))
    data["custom_new_permission"] = "allowed"
    atomic_write_json(live_cli_settings, data)

    # Switch to 'target_prof' with save_current=True
    res = switcher.switch_profile("target_prof", save_current=True)
    assert res.success is True

    # Verify that default profile in vault was explicitly saved
    default_dir = store.get_profile_dir("default")
    saved_default_cli = json.loads((default_dir / "cli_settings.json").read_text(encoding="utf-8"))
    assert saved_default_cli.get("custom_new_permission") == "allowed"


def test_switch_profile_dry_run(store: ProfileStore, switcher: ProfileSwitcher, temp_gemini_home: Path):
    store.create_profile("default", clone_from_live=True)
    store.create_profile("target_prof", email="target@domain.com")

    live_cli_settings_before = (temp_gemini_home / "antigravity-cli" / "settings.json").read_text(encoding="utf-8")

    res = switcher.switch_profile("target_prof", dry_run=True)
    assert res.success is True
    assert "[DRY-RUN]" in res.messages[0]

    # Verify live file was untouched
    live_cli_settings_after = (temp_gemini_home / "antigravity-cli" / "settings.json").read_text(encoding="utf-8")
    assert live_cli_settings_before == live_cli_settings_after
