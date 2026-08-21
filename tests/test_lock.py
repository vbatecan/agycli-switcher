"""
Tests for inter-process locking.
"""

from pathlib import Path
import pytest

from agy_multiprofile.core.lock import InterProcessLock, ProfileLockError


def test_lock_acquire_and_release(tmp_path: Path):
    lock_dir = tmp_path / "lock_test"
    with InterProcessLock(lock_dir=lock_dir, timeout_seconds=1.0) as lock:
        assert lock._fp is not None
        assert lock.lock_file.exists()

    assert lock._fp is None


def test_lock_timeout(tmp_path: Path):
    lock_dir = tmp_path / "lock_test"
    # Acquire first lock
    lock1 = InterProcessLock(lock_dir=lock_dir, timeout_seconds=1.0)
    lock1.acquire()

    # Attempt to acquire second lock should timeout
    lock2 = InterProcessLock(lock_dir=lock_dir, timeout_seconds=0.3)
    with pytest.raises(ProfileLockError):
        lock2.acquire()

    lock1.release()
