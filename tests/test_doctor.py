"""
Tests for health check doctor.
"""

from pathlib import Path

from agy_multiprofile.core.doctor import run_doctor, validate_profile
from agy_multiprofile.core.storage import ProfileStore


def test_doctor_healthy(store: ProfileStore, temp_gemini_home: Path):
    store.create_profile("default", clone_from_live=True)
    res = run_doctor(store.root_dir, temp_gemini_home)
    assert res.is_valid is True
    assert len(res.errors) == 0


def test_validate_profile_corrupted_json(store: ProfileStore):
    store.create_profile("corrupt_prof")
    p_dir = store.get_profile_dir("corrupt_prof")
    (p_dir / "cli_settings.json").write_text("{invalid json: broken", encoding="utf-8")

    res = validate_profile(p_dir)
    assert res.is_valid is False
    assert any("Corrupt JSON" in err for err in res.errors)
