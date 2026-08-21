"""
Unit and integration tests for OS Keyring token isolation and profile authentication.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from agy_multiprofile.core.auth import (
    apply_profile_token_to_keyring,
    capture_keyring_token_to_profile,
    get_profile_auth_token,
)
from agy_multiprofile.core.constants import AUTH_TOKEN_FILENAME
from agy_multiprofile.core.keyring import (
    clear_keyring_token,
    get_keyring_token,
    has_keyring_support,
    set_keyring_token,
)
from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.switcher import ProfileSwitcher


def test_has_keyring_support(monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/secret-tool" if name == "secret-tool" else None)
    assert has_keyring_support() is True

    monkeypatch.setenv("AGY_KEYRING_DISABLED", "1")
    assert has_keyring_support() is False


def test_get_keyring_token_linux(monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/secret-tool")

    sample_token = {"token": {"access_token": "token_123", "refresh_token": "ref_456"}, "auth_method": "consumer"}

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        assert cmd[:4] == ["secret-tool", "lookup", "service", "gemini"]
        return MagicMock(returncode=0, stdout=json.dumps(sample_token))

    monkeypatch.setattr("subprocess.run", fake_run)
    token = get_keyring_token()
    assert token == sample_token


def test_get_keyring_token_macos(monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/security")

    sample_token = {"token": {"access_token": "mac_token"}, "auth_method": "consumer"}

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        assert cmd[:2] == ["security", "find-generic-password"]
        return MagicMock(returncode=0, stdout=json.dumps(sample_token))

    monkeypatch.setattr("subprocess.run", fake_run)
    token = get_keyring_token()
    assert token == sample_token


def test_set_keyring_token_linux(monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/secret-tool")

    stored_input = []

    def fake_run(cmd, input=None, text=True, capture_output=True, timeout=None):
        assert cmd[0] == "secret-tool"
        assert cmd[1] == "store"
        stored_input.append(input)
        return MagicMock(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)
    payload = {"token": {"access_token": "new_tok"}}
    ok = set_keyring_token(payload)
    assert ok is True
    assert len(stored_input) == 1
    assert json.loads(stored_input[0]) == payload


def test_clear_keyring_token_linux(monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/secret-tool")

    called_cmds = []

    def fake_run(cmd, capture_output=True, text=True, timeout=None):
        called_cmds.append(cmd)
        return MagicMock(returncode=0)

    monkeypatch.setattr("subprocess.run", fake_run)
    ok = clear_keyring_token()
    assert ok is True
    assert called_cmds[0] == ["secret-tool", "clear", "service", "gemini", "username", "antigravity"]


def test_capture_and_apply_profile_token(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)
    profile_dir = tmp_path / "work_profile"

    # 1. Mock get_keyring_token returning token
    sample_token = {"token": {"access_token": "work_token_abc"}, "auth_method": "consumer"}
    monkeypatch.setattr("agy_multiprofile.core.auth.get_keyring_token", lambda: sample_token)

    captured = capture_keyring_token_to_profile(profile_dir)
    assert captured is True
    assert (profile_dir / AUTH_TOKEN_FILENAME).exists()
    assert get_profile_auth_token(profile_dir) == sample_token

    # 2. Mock set_keyring_token when applying
    set_called = []
    monkeypatch.setattr("agy_multiprofile.core.auth.set_keyring_token", lambda data: set_called.append(data) or True)

    ok, msg = apply_profile_token_to_keyring(profile_dir)
    assert ok is True
    assert len(set_called) == 1
    assert set_called[0] == sample_token


def test_apply_profile_token_clears_for_fresh_profile(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)
    empty_profile_dir = tmp_path / "new_empty_profile"
    empty_profile_dir.mkdir(parents=True)

    clear_called = []
    monkeypatch.setattr("agy_multiprofile.core.auth.clear_keyring_token", lambda: clear_called.append(True) or True)

    ok, msg = apply_profile_token_to_keyring(empty_profile_dir)
    assert ok is True
    assert len(clear_called) == 1
    assert "Cleared OS Keyring" in msg


def test_switch_profile_swaps_keyring_tokens(temp_vault_home: Path, temp_gemini_home: Path, monkeypatch):
    monkeypatch.delenv("AGY_KEYRING_DISABLED", raising=False)

    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    store.create_profile("work", email="work@corp.com")

    # Give 'work' profile a pre-existing saved token
    work_token = {"token": {"access_token": "work_oauth_token"}, "auth_method": "consumer"}
    work_dir = store.get_profile_dir("work")
    (work_dir / AUTH_TOKEN_FILENAME).write_text(json.dumps(work_token), encoding="utf-8")

    # Live keyring currently has 'default' token
    live_keyring_token = {"token": {"access_token": "default_oauth_token"}, "auth_method": "consumer"}
    keyring_state = {"current": live_keyring_token}

    monkeypatch.setattr("agy_multiprofile.core.auth.get_keyring_token", lambda: keyring_state["current"])
    def mock_set(t):
        keyring_state["current"] = t
        return True
    def mock_clear():
        keyring_state["current"] = None
        return True

    monkeypatch.setattr("agy_multiprofile.core.auth.set_keyring_token", mock_set)
    monkeypatch.setattr("agy_multiprofile.core.auth.clear_keyring_token", mock_clear)

    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    # Switch to 'work'
    res = switcher.switch_profile("work")
    assert res.success is True

    # 1. Default profile should now have captured the default token
    default_saved_token = get_profile_auth_token(store.get_profile_dir("default"))
    assert default_saved_token == live_keyring_token

    # 2. Keyring should now hold the work token
    assert keyring_state["current"] == work_token

    # Switch back to 'default'
    res = switcher.switch_profile("default")
    assert res.success is True

    # 3. Keyring should now hold the default token again
    assert keyring_state["current"] == live_keyring_token


def test_create_profile_preserves_trusted_workspaces(temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    meta = store.create_profile("personal", email="personal@gmail.com")

    p_dir = store.get_profile_dir("personal")
    cli_settings_file = p_dir / "cli_settings.json"
    assert cli_settings_file.exists()

    with open(cli_settings_file, "r") as f:
        data = json.load(f)
    assert "trustedWorkspaces" in data
    assert "/mock/project" in data["trustedWorkspaces"]

    trusted_folders_file = p_dir / "trusted_folders.json"
    assert trusted_folders_file.exists()
    with open(trusted_folders_file, "r") as f:
        f_data = json.load(f)
    assert "/mock/project" in f_data
