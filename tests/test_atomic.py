"""
Tests for atomic file operations, fsync, and TransactionContext rollback.
"""

import json
from pathlib import Path
import pytest

from agy_multiprofile.utils.atomic import (
    TransactionContext,
    atomic_copy_file,
    atomic_write_json,
    atomic_write_text,
)


def test_atomic_write_text(tmp_path: Path):
    target = tmp_path / "subdir" / "test.txt"
    atomic_write_text(target, "Hello Antigravity")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == "Hello Antigravity"


def test_atomic_write_json(tmp_path: Path):
    target = tmp_path / "test.json"
    data = {"key": "value", "numbers": [1, 2, 3]}
    atomic_write_json(target, data)
    assert target.exists()
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded == data


def test_atomic_copy_file(tmp_path: Path):
    src = tmp_path / "src.txt"
    dest = tmp_path / "dest.txt"
    src.write_text("Source data", encoding="utf-8")
    atomic_copy_file(src, dest)
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "Source data"


def test_transaction_context_commit(tmp_path: Path):
    file1 = tmp_path / "file1.json"
    file2 = tmp_path / "file2.json"
    file1.write_text('{"v": 1}', encoding="utf-8")

    with TransactionContext() as tx:
        tx.record_and_write_json(file1, {"v": 2})
        tx.record_and_write_json(file2, {"v": 3})
        tx.commit()

    assert json.loads(file1.read_text(encoding="utf-8")) == {"v": 2}
    assert json.loads(file2.read_text(encoding="utf-8")) == {"v": 3}


def test_transaction_context_rollback_on_exception(tmp_path: Path):
    file1 = tmp_path / "file1.json"
    file2 = tmp_path / "file2.json"
    file1.write_text('{"original": true}', encoding="utf-8")

    with pytest.raises(RuntimeError):
        with TransactionContext() as tx:
            tx.record_and_write_json(file1, {"modified": True})
            tx.record_and_write_json(file2, {"created": True})
            # Trigger deliberate failure midway
            raise RuntimeError("Simulated transaction crash")

    # Verify rollback: file1 restored to original, file2 removed
    assert json.loads(file1.read_text(encoding="utf-8")) == {"original": True}
    assert not file2.exists()
