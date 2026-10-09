"""
Launcher module for Google Antigravity CLI (agy).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Sequence

from agy_multiprofile.core.constants import REAL_AGY_PATH_FILENAME, SHIM_SIGNATURE, get_gemini_home, get_profile_home
from agy_multiprofile.utils.atomic import atomic_write_text
from agy_multiprofile.utils.console import print_error, print_info, print_warning


def is_self_binary(path: Path | str) -> bool:
    """
    Check if the given executable path is this program (agy-profile / agy-multiprofile / shim).
    Used to prevent infinite recursion when agy has been aliased or shimmed.
    """
    try:
        p = Path(path).resolve()
        if not p.exists():
            return False

        # 1. Match against current sys.argv[0] or python executable script
        if sys.argv:
            try:
                argv_path = Path(sys.argv[0]).resolve()
                if p == argv_path:
                    return True
            except Exception:
                pass

        # 2. Check if name is agy-profile or agy-multiprofile
        if p.name in ("agy-profile", "agy-multiprofile", "agy_multiprofile"):
            return True

        # 3. If file is a text script, check for shim signature or agy_multiprofile reference
        if p.is_file() and p.stat().st_size < 10240:
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                if SHIM_SIGNATURE in content or "agy_multiprofile" in content or "exec agy-profile" in content:
                    return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def get_saved_real_agy_path(profile_home: Path | None = None) -> Path | None:
    """Read the saved path to the real Antigravity binary if recorded in vault."""
    vault = profile_home or get_profile_home()
    path_file = vault / REAL_AGY_PATH_FILENAME
    if path_file.exists():
        try:
            saved_str = path_file.read_text(encoding="utf-8").strip()
            if saved_str:
                p = Path(saved_str).expanduser().resolve()
                if p.exists() and os.access(p, os.X_OK) and not is_self_binary(p):
                    return p
        except Exception:
            pass
    return None


def set_saved_real_agy_path(real_bin: Path, profile_home: Path | None = None) -> None:
    """Save the path to the real Antigravity binary in vault."""
    vault = profile_home or get_profile_home()
    vault.mkdir(parents=True, exist_ok=True)
    path_file = vault / REAL_AGY_PATH_FILENAME
    atomic_write_text(path_file, str(real_bin.resolve()))


def find_agy_binary(profile_home: Path | None = None) -> Path | None:
    """
    Search for the real Antigravity CLI ('agy' / 'antigravity-cli') executable.
    Checks AGY_REAL_BIN, AGY_BIN, saved vault path, system PATH, and known install paths,
    filtering out any self-referential shims or agy-profile binaries to prevent loops.
    """
    # 1. Check explicit AGY_REAL_BIN or AGY_BIN environment variable override
    for env_var in ("AGY_REAL_BIN", "AGY_BIN", "ANTIGRAVITY_BIN"):
        env_val = os.environ.get(env_var)
        if env_val:
            p = Path(env_val).expanduser().resolve()
            if p.exists() and os.access(p, os.X_OK) and not is_self_binary(p):
                return p

    # 2. Check saved real binary path in vault
    saved_path = get_saved_real_agy_path(profile_home)
    if saved_path:
        return saved_path

    # 3. Check system PATH
    for name in ("agy", "antigravity-cli", "antigravity"):
        which_path = shutil.which(name)
        if which_path:
            p = Path(which_path).resolve()
            if p.exists() and os.access(p, os.X_OK) and not is_self_binary(p):
                return p

    # 4. Check known default installation paths (excluding shims)
    candidate_paths = [
        Path.home() / ".local" / "bin" / "agy.real",
        get_gemini_home() / "antigravity-cli" / "bin" / "agy",
        Path.home() / ".local" / "bin" / "agy",
        Path.home() / ".local" / "bin" / "antigravity-cli",
        Path.home() / ".cargo" / "bin" / "agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
    ]

    for cand in candidate_paths:
        if cand.exists() and os.access(cand, os.X_OK) and not is_self_binary(cand):
            return cand.resolve()

    return None


def launch_agy(
    args: Sequence[str] | None = None,
    binary_path: str | Path | None = None,
    exec_process: bool = True,
) -> int:
    """
    Launch the Antigravity CLI (agy), replacing the current process image on POSIX.
    
    If exec_process is True and running on POSIX, os.execvp replaces the current process.
    Otherwise (or on Windows), it uses subprocess.call and returns the exit code.
    """
    # Check if disabled via environment (e.g. testing / automated scripts)
    if os.environ.get("AGY_NO_LAUNCH", "").lower() in ("1", "true", "yes"):
        print_info("Automatic agy launch skipped (AGY_NO_LAUNCH set).")
        return 0

    agy_bin = Path(binary_path).resolve() if binary_path else find_agy_binary()

    if not agy_bin:
        print_warning("Antigravity CLI ('agy') executable not found in PATH or standard directories.")
        print_info("Ensure Antigravity CLI is installed or specify its location with AGY_BIN=/path/to/agy")
        return 1

    cmd_args = [str(agy_bin)]
    if args:
        cmd_args.extend(args)

    print_info(f"✦ Launching Antigravity CLI ({agy_bin.name})...\n")
    sys.stdout.flush()
    sys.stderr.flush()

    if exec_process and os.name != "nt":
        # Direct process replacement (seamless terminal handover)
        try:
            os.execvp(str(agy_bin), cmd_args)
        except Exception as e:
            print_error(f"Failed to execute '{agy_bin}': {e}")
            return 1
    else:
        import subprocess
        try:
            return subprocess.call(cmd_args)
        except Exception as e:
            print_error(f"Failed to execute '{agy_bin}': {e}")
            return 1
