"""
Wrapper and shim manager for replacing 'agy' with agy-profile switcher.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Any

from agy_multiprofile.core.constants import (
    REAL_AGY_PATH_FILENAME,
    SHIM_SIGNATURE,
    get_profile_home,
)
from agy_multiprofile.core.launcher import (
    find_agy_binary,
    get_saved_real_agy_path,
    is_self_binary,
    set_saved_real_agy_path,
)
from agy_multiprofile.utils.atomic import atomic_write_text


def get_default_shim_dir() -> Path:
    """Return default directory where the agy shim executable should be installed."""
    if os.name == "nt":
        # Windows: prefer %USERPROFILE%\bin or %APPDATA%\Python\Scripts
        user_bin = Path.home() / "bin"
        if user_bin.exists():
            return user_bin
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            scripts = Path(local_app_data) / "Programs" / "Python" / "Scripts"
            if scripts.exists():
                return scripts
        return Path.home() / ".local" / "bin"
    
    # On POSIX: prefer ~/.local/bin
    return Path.home() / ".local" / "bin"


def get_shim_path(bin_dir: Path | None = None) -> Path:
    """Return the full destination path for the agy shim."""
    target_dir = (bin_dir or get_default_shim_dir()).expanduser().resolve()
    if os.name == "nt":
        return target_dir / "agy.cmd"
    return target_dir / "agy"


def generate_shim_content() -> str:
    """Generate executable shim script content."""
    if os.name == "nt":
        return (
            "@echo off\r\n"
            f"{SHIM_SIGNATURE}\r\n"
            "agy-profile %*\r\n"
        )
    return (
        "#!/usr/bin/env sh\n"
        f"{SHIM_SIGNATURE}\n"
        'exec agy-profile "$@"\n'
    )


def install_shim(
    bin_dir: Path | None = None,
    profile_home: Path | None = None,
    force: bool = False,
) -> tuple[bool, str]:
    """
    Install an executable 'agy' shim in bin_dir that delegates to agy-profile.
    Preserves and records the path to the real Antigravity binary.
    """
    vault = profile_home or get_profile_home()
    shim_file = get_shim_path(bin_dir)
    target_dir = shim_file.parent

    # 1. Ensure target directory exists
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return False, f"Failed to create bin directory '{target_dir}': {e}"

    # 2. Discover and record real binary before putting shim in place
    real_bin = find_agy_binary(vault)
    if real_bin and not is_self_binary(real_bin):
        set_saved_real_agy_path(real_bin, vault)

    # 3. Handle existing file at shim path
    backup_file = shim_file.with_name(shim_file.name + ".real")
    if shim_file.exists():
        if is_self_binary(shim_file):
            # Already our shim, can overwrite safely
            pass
        else:
            # It's an existing non-shim binary or script, back it up!
            try:
                shutil.copy2(shim_file, backup_file)
                # If we hadn't found a real binary yet, use this backup
                if not get_saved_real_agy_path(vault):
                    set_saved_real_agy_path(backup_file, vault)
            except Exception as e:
                if not force:
                    return False, f"Failed to backup existing '{shim_file}' to '{backup_file}': {e}"

    # 4. Write shim file
    content = generate_shim_content()
    try:
        atomic_write_text(shim_file, content)
        if os.name != "nt":
            # Set executable permissions (0o755)
            curr_mode = os.stat(shim_file).st_mode
            os.chmod(shim_file, curr_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH | stat.S_IRUSR | stat.S_IWUSR)
    except Exception as e:
        return False, f"Failed to write shim executable at '{shim_file}': {e}"

    # 5. Check PATH presence
    path_dirs = [Path(p).expanduser().resolve() for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    in_path = target_dir in path_dirs

    msg = f"Successfully installed 'agy' shim at '{shim_file}'."
    if not in_path:
        msg += f"\n[warning] Note: '{target_dir}' is not in your current PATH. Add it to your shell rc (e.g. export PATH=\"{target_dir}:$PATH\")."

    saved_real = get_saved_real_agy_path(vault)
    if saved_real:
        msg += f"\n[info] Real Antigravity binary mapped to: {saved_real}"
    else:
        msg += "\n[info] Real Antigravity binary will be auto-detected when launched."

    return True, msg


def uninstall_shim(
    bin_dir: Path | None = None,
    profile_home: Path | None = None,
) -> tuple[bool, str]:
    """
    Remove the 'agy' shim executable and restore any backup binary if available.
    """
    vault = profile_home or get_profile_home()
    shim_file = get_shim_path(bin_dir)
    backup_file = shim_file.with_name(shim_file.name + ".real")

    if not shim_file.exists():
        return False, f"No shim found at '{shim_file}'."

    if not is_self_binary(shim_file):
        return False, f"The file at '{shim_file}' is not an agy-multiprofile shim. Refusing to remove."

    # 1. Restore backup if exists
    try:
        if backup_file.exists():
            shutil.move(str(backup_file), str(shim_file))
            msg = f"Removed shim and restored original binary at '{shim_file}'."
        else:
            shim_file.unlink()
            msg = f"Removed shim at '{shim_file}'."
    except Exception as e:
        return False, f"Failed to remove shim at '{shim_file}': {e}"

    # 2. Clean up real_agy_path file if it pointed to backup
    real_path_file = vault / REAL_AGY_PATH_FILENAME
    if real_path_file.exists():
        try:
            saved_str = real_path_file.read_text(encoding="utf-8").strip()
            if saved_str == str(backup_file.resolve()):
                real_path_file.unlink()
        except Exception:
            pass

    return True, msg


def get_shim_status(
    bin_dir: Path | None = None,
    profile_home: Path | None = None,
) -> dict[str, Any]:
    """Return diagnostic status of the agy shim and PATH resolution."""
    vault = profile_home or get_profile_home()
    shim_file = get_shim_path(bin_dir)
    backup_file = shim_file.with_name(shim_file.name + ".real")

    target_dir = shim_file.parent
    path_dirs = [Path(p).expanduser().resolve() for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    in_path = target_dir in path_dirs

    which_agy = shutil.which("agy")
    which_path = Path(which_agy).resolve() if which_agy else None

    is_installed = shim_file.exists()
    is_valid = is_self_binary(shim_file) if is_installed else False
    has_backup = backup_file.exists()
    saved_real = get_saved_real_agy_path(vault)
    found_real = find_agy_binary(vault)

    # Check if active `agy` on PATH points to the shim
    is_active_shim = bool(which_path and is_self_binary(which_path))

    return {
        "shim_path": shim_file,
        "is_installed": is_installed,
        "is_valid_shim": is_valid,
        "has_backup": has_backup,
        "backup_path": backup_file if has_backup else None,
        "in_path": in_path,
        "which_agy": which_path,
        "is_active_shim": is_active_shim,
        "saved_real_path": saved_real,
        "found_real_binary": found_real,
    }


def detect_user_shell() -> str:
    """Detect current user's default shell name."""
    shell_env = os.environ.get("SHELL", "")
    if "zsh" in shell_env:
        return "zsh"
    if "fish" in shell_env:
        return "fish"
    if "csh" in shell_env or "tcsh" in shell_env:
        return "csh"
    return "bash"


def get_shell_rc_path(shell: str = "auto") -> Path | None:
    """Return path to user's shell configuration file."""
    sh = detect_user_shell() if shell == "auto" else shell.lower()
    home = Path.home()
    if sh == "zsh":
        return home / ".zshrc"
    elif sh == "bash":
        bashrc = home / ".bashrc"
        if bashrc.exists():
            return bashrc
        return home / ".bash_profile"
    elif sh == "fish":
        return home / ".config" / "fish" / "config.fish"
    return home / ".bashrc"


def generate_shell_alias(shell: str = "auto") -> str:
    """Generate shell alias or function string."""
    sh = detect_user_shell() if shell == "auto" else shell.lower()
    if sh == "fish":
        return "alias agy 'agy-profile'"
    elif sh in ("csh", "tcsh"):
        return "alias agy 'agy-profile'"
    # bash, zsh, sh
    return 'alias agy="agy-profile"'


def install_shell_alias(shell: str = "auto") -> tuple[bool, str]:
    """Append shell alias definition to shell config file."""
    rc_path = get_shell_rc_path(shell)
    if not rc_path:
        return False, f"Could not determine configuration file for shell '{shell}'."

    alias_line = generate_shell_alias(shell)
    marker = "# Added by agy-multiprofile"
    block = f"\n{marker}\n{alias_line}\n"

    try:
        rc_path.parent.mkdir(parents=True, exist_ok=True)
        if rc_path.exists():
            content = rc_path.read_text(encoding="utf-8")
            if alias_line in content:
                return True, f"Alias already present in '{rc_path}'."
        else:
            content = ""

        with open(rc_path, "a", encoding="utf-8") as f:
            f.write(block)
        return True, f"Appended alias to '{rc_path}'. Run 'source {rc_path}' or start a new shell session."
    except Exception as e:
        return False, f"Failed to write to '{rc_path}': {e}"


def uninstall_shell_alias(shell: str = "auto") -> tuple[bool, str]:
    """Remove shell alias definition from shell config file."""
    rc_path = get_shell_rc_path(shell)
    if not rc_path or not rc_path.exists():
        return False, f"Shell config file '{rc_path}' not found."

    try:
        content = rc_path.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        new_lines: list[str] = []
        skip_next = False

        for line in lines:
            if "# Added by agy-multiprofile" in line:
                skip_next = True
                continue
            if skip_next and ("alias agy=" in line or "alias agy " in line):
                skip_next = False
                continue
            skip_next = False
            if "alias agy=" not in line and "alias agy " not in line:
                new_lines.append(line)

        new_content = "".join(new_lines)
        if new_content != content:
            atomic_write_text(rc_path, new_content)
            return True, f"Removed alias from '{rc_path}'."
        return True, f"No agy alias found in '{rc_path}'."
    except Exception as e:
        return False, f"Failed to update '{rc_path}': {e}"


# Revert function aliases for convenience
revert_shim = uninstall_shim
revert_shell_alias = uninstall_shell_alias
