"""
Launcher module for Google Antigravity CLI (agy).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Sequence

from agy_multiprofile.core.constants import get_gemini_home
from agy_multiprofile.utils.console import print_error, print_info, print_warning


def find_agy_binary() -> Path | None:
    """
    Search for the Antigravity CLI ('agy' / 'antigravity-cli') executable.
    Checks AGY_BIN environment variable, PATH, and standard installation locations.
    """
    # 1. Check environment variable override
    env_bin = os.environ.get("AGY_BIN") or os.environ.get("ANTIGRAVITY_BIN")
    if env_bin:
        p = Path(env_bin).expanduser().resolve()
        if p.exists() and os.access(p, os.X_OK):
            return p

    # 2. Check system PATH
    for name in ("agy", "antigravity-cli", "antigravity"):
        which_path = shutil.which(name)
        if which_path:
            p = Path(which_path).resolve()
            if p.exists() and os.access(p, os.X_OK):
                return p

    # 3. Check known default installation paths
    candidate_paths = [
        Path.home() / ".local" / "bin" / "agy",
        Path.home() / ".local" / "bin" / "antigravity-cli",
        get_gemini_home() / "antigravity-cli" / "bin" / "agy",
        Path.home() / ".cargo" / "bin" / "agy",
        Path("/usr/local/bin/agy"),
        Path("/usr/bin/agy"),
    ]

    for cand in candidate_paths:
        if cand.exists() and os.access(cand, os.X_OK):
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
