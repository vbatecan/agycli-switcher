"""
Process and environment detection for Antigravity and Gemini CLI.
"""

from __future__ import annotations

import glob
import os
import subprocess
from pathlib import Path
from typing import Any

from agy_multiprofile.core.constants import get_gemini_home


def is_gemini_installed(gemini_home: Path | None = None) -> bool:
    """Check if Gemini/Antigravity configuration directory exists."""
    home = gemini_home or get_gemini_home()
    return home.exists() and home.is_dir()


def check_brain_locks(gemini_home: Path | None = None) -> list[Path]:
    """
    Check for active lock files in the Antigravity CLI brain directory.
    """
    home = gemini_home or get_gemini_home()
    brain_dir = home / "antigravity-cli" / "brain"
    if not brain_dir.exists():
        return []
    
    lock_files: list[Path] = []
    for lock in brain_dir.glob("*.lock"):
        lock_files.append(lock)
    return lock_files


def find_running_antigravity_processes() -> list[dict[str, Any]]:
    """
    Search for currently running agy CLI processes.
    Returns list of dicts with 'pid', 'name', 'cmdline'.
    """
    running: list[dict[str, Any]] = []
    current_pid = os.getpid()
    
    # Try reading Linux /proc first
    proc_path = Path("/proc")
    if proc_path.exists() and proc_path.is_dir():
        for pid_dir in proc_path.iterdir():
            if not pid_dir.is_dir() or not pid_dir.name.isdigit():
                continue
            pid = int(pid_dir.name)
            if pid == current_pid:
                continue
            
            try:
                cmdline_file = pid_dir / "cmdline"
                if not cmdline_file.exists():
                    continue
                cmdline_raw = cmdline_file.read_bytes()
                cmdline = cmdline_raw.replace(b"\x00", b" ").decode("utf-8", errors="ignore").strip()
                
                # Check for agy binary executions (excluding editors or other tools)
                tokens = cmdline.split()
                if not tokens:
                    continue
                
                binary_name = Path(tokens[0]).name
                if binary_name in ("agy", "antigravity-cli"):
                    running.append({
                        "pid": pid,
                        "name": binary_name,
                        "cmdline": cmdline,
                    })
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                continue
        return running

    # Fallback to ps command
    try:
        res = subprocess.run(["ps", "-eo", "pid,comm,args"], capture_output=True, text=True, timeout=2.0)
        if res.returncode == 0:
            for line in res.stdout.splitlines()[1:]:
                parts = line.strip().split(maxsplit=2)
                if len(parts) >= 2:
                    pid_str = parts[0]
                    comm = parts[1]
                    args = parts[2] if len(parts) > 2 else comm
                    if pid_str.isdigit() and int(pid_str) != current_pid:
                        if comm in ("agy", "antigravity-cli"):
                            running.append({
                                "pid": int(pid_str),
                                "name": comm,
                                "cmdline": args,
                            })
    except Exception:
        pass

    return running
