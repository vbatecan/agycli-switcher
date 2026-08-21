"""
Inter-process locking using fcntl.flock to prevent race conditions during profile operations.
"""

from __future__ import annotations

import fcntl
import os
import time
from pathlib import Path
from typing import TextIO

from agy_multiprofile.core.constants import LOCK_FILENAME, get_profile_home


class ProfileLockError(Exception):
    """Raised when unable to acquire the profile lock within timeout."""
    pass


class InterProcessLock:
    """
    Exclusive inter-process lock on ~/.config/agy-profile/.lock.
    Ensures safe concurrent operations.
    """

    def __init__(self, lock_dir: Path | None = None, timeout_seconds: float = 10.0):
        self.lock_dir = (lock_dir or get_profile_home()).resolve()
        self.lock_file = self.lock_dir / LOCK_FILENAME
        self.timeout_seconds = timeout_seconds
        self._fp: TextIO | None = None

    def __enter__(self) -> InterProcessLock:
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()

    def acquire(self) -> None:
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.lock_file, "a+", encoding="utf-8")
        
        start_time = time.monotonic()
        while True:
            try:
                # Try non-blocking exclusive lock
                fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Write current pid into lockfile
                self._fp.seek(0)
                self._fp.truncate()
                self._fp.write(f"pid={os.getpid()}\ntime={time.time()}\n")
                self._fp.flush()
                return
            except (BlockingIOError, OSError):
                elapsed = time.monotonic() - start_time
                if elapsed >= self.timeout_seconds:
                    raise ProfileLockError(
                        f"Could not acquire profile lock on {self.lock_file} after {self.timeout_seconds}s. "
                        "Another agy-profile command may be running."
                    )
                time.sleep(0.1)

    def release(self) -> None:
        if self._fp is not None:
            try:
                fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
                self._fp.close()
            except Exception:
                pass
            finally:
                self._fp = None
