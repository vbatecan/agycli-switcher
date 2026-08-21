"""
Atomic and transactional file operations.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable


def atomic_write_text(filepath: Path, content: str, encoding: str = "utf-8") -> None:
    """
    Atomically write text to a file using temporary file and atomic replace.
    Ensures parent directory exists and flushes data to physical disk before replacing.
    """
    filepath = filepath.resolve()
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    unique_suffix = f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    temp_path = filepath.parent / f".{filepath.name}{unique_suffix}"
    
    try:
        with open(temp_path, "w", encoding=encoding) as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        
        # Atomic replace on POSIX filesystems
        os.replace(temp_path, filepath)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


def atomic_write_json(filepath: Path, data: Any, indent: int = 2) -> None:
    """Atomically write JSON serializable data to a file."""
    content = json.dumps(data, indent=indent, ensure_ascii=False) + "\n"
    atomic_write_text(filepath, content, encoding="utf-8")


def atomic_copy_file(src: Path, dest: Path) -> None:
    """Atomically copy a file from src to dest."""
    src = src.resolve()
    dest = dest.resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source file does not exist: {src}")
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    unique_suffix = f".tmp.{os.getpid()}.{uuid.uuid4().hex[:8]}"
    temp_path = dest.parent / f".{dest.name}{unique_suffix}"
    
    try:
        shutil.copy2(src, temp_path)
        with open(temp_path, "r+b") as f:
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, dest)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise


class FileRollbackAction:
    """Record of a file modification that can be rolled back."""

    def __init__(self, dest_path: Path, backup_copy_path: Path | None, was_created: bool):
        self.dest_path = dest_path
        self.backup_copy_path = backup_copy_path
        self.was_created = was_created

    def rollback(self) -> None:
        """Undo this modification."""
        try:
            if self.was_created:
                if self.dest_path.exists():
                    self.dest_path.unlink()
            elif self.backup_copy_path and self.backup_copy_path.exists():
                atomic_copy_file(self.backup_copy_path, self.dest_path)
        except Exception as e:
            # Best effort rollback logging
            pass


class TransactionContext:
    """
    Context manager that coordinates multi-file atomic transactions.
    If an error occurs or rollback() is called, all changes made during the
    transaction are reverted to their exact pre-transaction state.
    """

    def __init__(self, temp_staging_dir: Path | None = None):
        self.temp_staging_dir = temp_staging_dir
        self._temp_dir_obj: tempfile.TemporaryDirectory | None = None
        self._actions: list[FileRollbackAction] = []
        self._committed = False

    def __enter__(self) -> TransactionContext:
        if self.temp_staging_dir is None:
            self._temp_dir_obj = tempfile.TemporaryDirectory(prefix="agy_tx_")
            self.temp_staging_dir = Path(self._temp_dir_obj.name)
        else:
            self.temp_staging_dir.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None and not self._committed:
            self.rollback()
        self.cleanup()
        return False  # Propagate exception

    def record_and_replace(self, dest_path: Path, new_content_path: Path) -> None:
        """
        Record the current state of dest_path, stage a backup, and atomically replace it with new_content_path.
        """
        dest_path = dest_path.resolve()
        assert self.temp_staging_dir is not None

        if dest_path.exists():
            backup_copy = self.temp_staging_dir / f"bak_{len(self._actions)}_{dest_path.name}"
            shutil.copy2(dest_path, backup_copy)
            action = FileRollbackAction(dest_path=dest_path, backup_copy_path=backup_copy, was_created=False)
        else:
            action = FileRollbackAction(dest_path=dest_path, backup_copy_path=None, was_created=True)

        self._actions.append(action)
        atomic_copy_file(new_content_path, dest_path)

    def record_and_write_json(self, dest_path: Path, data: Any) -> None:
        """
        Record the current state of dest_path, stage a backup, and write JSON data atomically.
        """
        dest_path = dest_path.resolve()
        assert self.temp_staging_dir is not None

        if dest_path.exists():
            backup_copy = self.temp_staging_dir / f"bak_{len(self._actions)}_{dest_path.name}"
            shutil.copy2(dest_path, backup_copy)
            action = FileRollbackAction(dest_path=dest_path, backup_copy_path=backup_copy, was_created=False)
        else:
            action = FileRollbackAction(dest_path=dest_path, backup_copy_path=None, was_created=True)

        self._actions.append(action)
        atomic_write_json(dest_path, data)

    def commit(self) -> None:
        """Mark the transaction as successfully committed."""
        self._committed = True

    def rollback(self) -> None:
        """Roll back all recorded actions in reverse order."""
        for action in reversed(self._actions):
            action.rollback()
        self._actions.clear()

    def cleanup(self) -> None:
        """Clean up temporary staging files."""
        if self._temp_dir_obj:
            try:
                self._temp_dir_obj.cleanup()
            except Exception:
                pass
