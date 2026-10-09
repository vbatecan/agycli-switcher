"""
Tests for 'agy' command wrapper, shim installer, and shell alias generator.
"""

import os
from pathlib import Path
from unittest.mock import patch
import pytest

from agy_multiprofile.cli import main
from agy_multiprofile.core.launcher import find_agy_binary, is_self_binary
from agy_multiprofile.core.wrapper import (
    generate_shell_alias,
    get_shell_rc_path,
    get_shim_path,
    get_shim_status,
    install_shell_alias,
    install_shim,
    uninstall_shell_alias,
    uninstall_shim,
)


def test_shim_installation_and_uninstallation(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    vault_dir = tmp_path / "vault"
    real_agy = tmp_path / "opt" / "agy"
    real_agy.parent.mkdir(parents=True, exist_ok=True)
    real_agy.write_text("#!/bin/sh\necho real agy")
    real_agy.chmod(0o755)

    # 1. Install shim with real_agy discoverable
    with patch("agy_multiprofile.core.wrapper.find_agy_binary", return_value=real_agy):
        ok, msg = install_shim(bin_dir=bin_dir, profile_home=vault_dir)
        assert ok is True
        assert "Successfully installed" in msg

    shim_file = get_shim_path(bin_dir)
    assert shim_file.exists()
    assert is_self_binary(shim_file) is True

    if os.name != "nt":
        assert os.access(shim_file, os.X_OK)

    # Check status
    status = get_shim_status(bin_dir=bin_dir, profile_home=vault_dir)
    assert status["is_installed"] is True
    assert status["is_valid_shim"] is True
    assert status["saved_real_path"] == real_agy.resolve()

    # 2. find_agy_binary should not return the shim
    with patch("shutil.which", lambda name: str(shim_file) if name == "agy" else None):
        found = find_agy_binary(profile_home=vault_dir)
        assert found == real_agy.resolve()
        assert found != shim_file.resolve()

    # 3. Uninstall shim
    ok, msg = uninstall_shim(bin_dir=bin_dir, profile_home=vault_dir)
    assert ok is True
    assert not shim_file.exists()


def test_shim_backup_existing_binary(tmp_path: Path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    vault_dir = tmp_path / "vault"

    existing_agy = bin_dir / ("agy.cmd" if os.name == "nt" else "agy")
    existing_agy.write_text("#!/bin/sh\necho original binary")
    existing_agy.chmod(0o755)

    # Install shim over existing binary
    ok, msg = install_shim(bin_dir=bin_dir, profile_home=vault_dir)
    assert ok is True

    backup_file = existing_agy.with_name(existing_agy.name + ".real")
    assert backup_file.exists()
    assert backup_file.read_text() == "#!/bin/sh\necho original binary"

    # Uninstall should restore original binary
    ok, msg = uninstall_shim(bin_dir=bin_dir, profile_home=vault_dir)
    assert ok is True
    assert existing_agy.exists()
    assert existing_agy.read_text() == "#!/bin/sh\necho original binary"
    assert not backup_file.exists()


def test_shell_alias_generation_and_rc(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))

    # Test generation
    assert "alias agy=" in generate_shell_alias("bash")
    assert "alias agy=" in generate_shell_alias("zsh")
    assert "alias agy 'agy-profile'" in generate_shell_alias("fish")

    # Test install and uninstall into bashrc
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("# Existing bashrc\n")

    with patch("agy_multiprofile.core.wrapper.get_shell_rc_path", return_value=bashrc):
        ok, msg = install_shell_alias("bash")
        assert ok is True
        assert "alias agy=" in bashrc.read_text()

        # Idempotent install
        ok, msg = install_shell_alias("bash")
        assert ok is True
        assert "already present" in msg.lower()

        # Uninstall
        ok, msg = uninstall_shell_alias("bash")
        assert ok is True
        assert "alias agy=" not in bashrc.read_text()
        assert "# Existing bashrc" in bashrc.read_text()


def test_cli_wrap_commands(tmp_path: Path, monkeypatch, capsys):
    vault_dir = tmp_path / "vault"
    gemini_dir = tmp_path / "gemini"
    bin_dir = tmp_path / "bin"
    monkeypatch.setenv("AGY_PROFILE_HOME", str(vault_dir))
    monkeypatch.setenv("GEMINI_HOME", str(gemini_dir))

    # Status check
    ret = main(["wrap", "status", "--bin-dir", str(bin_dir)])
    assert ret == 0

    # Install shim via CLI
    ret = main(["wrap", "install", "--bin-dir", str(bin_dir), "--mode", "shim"])
    assert ret == 0
    shim_file = get_shim_path(bin_dir)
    assert shim_file.exists()

    # Alias subcommand
    ret = main(["wrap", "alias"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "alias agy=" in captured.out

    # Uninstall via alias replace-agy
    ret = main(["replace-agy", "uninstall", "--bin-dir", str(bin_dir), "--mode", "shim"])
    assert ret == 0
    assert not shim_file.exists()


def test_revert_commands(tmp_path: Path, monkeypatch):
    vault_dir = tmp_path / "vault"
    gemini_dir = tmp_path / "gemini"
    bin_dir = tmp_path / "bin"
    monkeypatch.setenv("AGY_PROFILE_HOME", str(vault_dir))
    monkeypatch.setenv("GEMINI_HOME", str(gemini_dir))

    # 1. Install shim and alias
    bashrc = tmp_path / ".bashrc"
    bashrc.write_text("# bashrc\n")

    with patch("agy_multiprofile.core.wrapper.get_shell_rc_path", return_value=bashrc):
        ret = main(["wrap", "install", "--bin-dir", str(bin_dir), "--mode", "all", "--shell", "bash"])
        assert ret == 0
        shim_file = get_shim_path(bin_dir)
        assert shim_file.exists()
        assert "alias agy=" in bashrc.read_text()

        # 2. Revert using 'unwrap' command
        ret = main(["unwrap", "--bin-dir", str(bin_dir), "--mode", "all", "--shell", "bash"])
        assert ret == 0
        assert not shim_file.exists()
        assert "alias agy=" not in bashrc.read_text()

        # 3. Test 'wrap revert' syntax
        ret = main(["wrap", "install", "--bin-dir", str(bin_dir), "--mode", "shim"])
        assert ret == 0
        assert shim_file.exists()

        ret = main(["wrap", "revert", "--bin-dir", str(bin_dir), "--mode", "shim"])
        assert ret == 0
        assert not shim_file.exists()

