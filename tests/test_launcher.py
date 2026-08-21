"""
Tests for Antigravity CLI (agy) detection and automatic launcher.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch
import os
import pytest

from agy_multiprofile.core.launcher import find_agy_binary, launch_agy
from agy_multiprofile.cli import cmd_switch, cmd_tui, interactive_switch, main
from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.switcher import ProfileSwitcher


def test_find_agy_binary_env_var(monkeypatch, tmp_path: Path):
    mock_bin = tmp_path / "mock_agy"
    mock_bin.write_text("#!/bin/sh\necho agy")
    mock_bin.chmod(0o755)

    monkeypatch.setenv("AGY_BIN", str(mock_bin))
    found = find_agy_binary()
    assert found == mock_bin.resolve()


def test_find_agy_binary_path(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AGY_BIN", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BIN", raising=False)

    mock_bin = tmp_path / "agy"
    mock_bin.write_text("#!/bin/sh\necho agy")
    mock_bin.chmod(0o755)

    monkeypatch.setattr("shutil.which", lambda name: str(mock_bin) if name == "agy" else None)
    found = find_agy_binary()
    assert found == mock_bin.resolve()


def test_find_agy_binary_not_found(monkeypatch):
    monkeypatch.delenv("AGY_BIN", raising=False)
    monkeypatch.delenv("ANTIGRAVITY_BIN", raising=False)
    monkeypatch.setattr("shutil.which", lambda name: None)
    monkeypatch.setattr("pathlib.Path.exists", lambda self: False)

    found = find_agy_binary()
    assert found is None


def test_launch_agy_execvp(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AGY_NO_LAUNCH", raising=False)
    mock_bin = tmp_path / "agy"
    mock_bin.write_text("#!/bin/sh")
    mock_bin.chmod(0o755)

    exec_called = []
    monkeypatch.setattr(os, "execvp", lambda path, args: exec_called.append((path, args)))
    monkeypatch.setattr("agy_multiprofile.core.launcher.find_agy_binary", lambda: mock_bin)

    launch_agy(args=["--verbose"])
    assert len(exec_called) == 1
    assert exec_called[0] == (str(mock_bin), [str(mock_bin), "--verbose"])


def test_launch_agy_subprocess(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("AGY_NO_LAUNCH", raising=False)
    mock_bin = tmp_path / "agy"
    mock_bin.write_text("#!/bin/sh")
    mock_bin.chmod(0o755)

    monkeypatch.setattr("agy_multiprofile.core.launcher.find_agy_binary", lambda: mock_bin)

    with patch("subprocess.call", return_value=0) as mock_call:
        code = launch_agy(args=["status"], exec_process=False)
        assert code == 0
        mock_call.assert_called_once_with([str(mock_bin), "status"])


def test_launch_agy_not_found(monkeypatch, capsys):
    monkeypatch.delenv("AGY_NO_LAUNCH", raising=False)
    monkeypatch.setattr("agy_multiprofile.core.launcher.find_agy_binary", lambda: None)

    ret = launch_agy()
    assert ret == 1
    captured = capsys.readouterr()
    assert "not found" in (captured.out + captured.err)


def test_launch_agy_skipped_when_disabled(monkeypatch):
    monkeypatch.setenv("AGY_NO_LAUNCH", "1")
    with patch("agy_multiprofile.core.launcher.find_agy_binary") as mock_find:
        ret = launch_agy()
        assert ret == 0
        mock_find.assert_not_called()


def test_interactive_switch_triggers_launch(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    store.create_profile("work", email="work@company.com")
    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    # Select option 2 ('work')
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")

    with patch("agy_multiprofile.cli.launch_agy", return_value=0) as mock_launch:
        ret = interactive_switch(store, switcher)
        assert ret == 0
        mock_launch.assert_called_once_with(args=None)


def test_interactive_switch_already_active_triggers_launch(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    # Select option 1 ('default' which is already active)
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")

    with patch("agy_multiprofile.cli.launch_agy", return_value=0) as mock_launch:
        ret = interactive_switch(store, switcher)
        assert ret == 0
        mock_launch.assert_called_once_with(args=None)


def test_interactive_switch_no_launch_flag(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    store.create_profile("work", email="work@company.com")
    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")

    with patch("agy_multiprofile.cli.launch_agy") as mock_launch:
        ret = interactive_switch(store, switcher, launch=False)
        assert ret == 0
        mock_launch.assert_not_called()


def test_cmd_switch_with_launch_flag(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path):
    monkeypatch.setenv("AGY_PROFILE_HOME", str(temp_vault_home))
    monkeypatch.setenv("GEMINI_HOME", str(temp_gemini_home))

    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    store.create_profile("work", email="work@company.com")

    with patch("agy_multiprofile.cli.launch_agy", return_value=0) as mock_launch:
        ret = main(["switch", "work", "--launch"])
        assert ret == 0
        mock_launch.assert_called_once()


def test_cmd_tui_launches_agy_on_select(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    with patch("agy_multiprofile.tui.app.ProfileManagerApp.run", return_value="work"):
        with patch("agy_multiprofile.cli.launch_agy", return_value=0) as mock_launch:
            class DummyArgs:
                no_launch = False
            ret = cmd_tui(DummyArgs(), store, switcher)
            assert ret == 0
            mock_launch.assert_called_once()
