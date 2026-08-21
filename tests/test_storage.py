"""
Tests for ProfileStore, snapshots, soft-delete trash, and export/import.
"""

from pathlib import Path
import pytest

from agy_multiprofile.core.storage import ProfileStore


def test_profile_create_and_list(store: ProfileStore):
    p1 = store.create_profile(name="work", description="Work account", email="work@company.com")
    assert p1.name == "work"
    assert p1.email == "work@company.com"

    # Check clean defaults
    p_dir = store.get_profile_dir("work")
    mcp_data = (p_dir / "mcp_config.json").read_text(encoding="utf-8")
    assert "mcpServers" in mcp_data

    profiles = store.list_profiles()
    assert len(profiles) == 1
    assert profiles[0].name == "work"


def test_profile_create_clone_from_live(store: ProfileStore, temp_gemini_home: Path):
    p = store.create_profile(name="live_clone", clone_from_live=True)
    assert p.name == "live_clone"

    p_dir = store.get_profile_dir("live_clone")
    assert (p_dir / "cli_settings.json").exists()
    assert (p_dir / "mcp_config.json").exists()


def test_profile_clone(store: ProfileStore):
    store.create_profile(name="source", description="Source", email="source@domain.com")
    cloned = store.clone_profile("source", "cloned")
    assert cloned.name == "cloned"
    assert cloned.email == "source@domain.com"


def test_profile_rename(store: ProfileStore):
    store.create_profile(name="old_name", description="To be renamed")
    store.rename_profile("old_name", "new_name")
    assert not store.profile_exists("old_name")
    assert store.profile_exists("new_name")


def test_soft_delete_to_trash_and_restore(store: ProfileStore):
    store.create_profile(name="temp_profile", description="Temporary")
    trash_meta = store.soft_delete_profile("temp_profile")
    assert not store.profile_exists("temp_profile")
    assert len(store.list_trash()) == 1

    # Restore from trash
    restored = store.restore_from_trash(trash_meta.trash_id)
    assert restored.name == "temp_profile"
    assert store.profile_exists("temp_profile")
    assert len(store.list_trash()) == 0


def test_create_and_list_snapshots(store: ProfileStore):
    snap = store.create_snapshot(trigger="test_snap", source_profile="default")
    assert snap.trigger == "test_snap"
    snaps = store.list_snapshots()
    assert len(snaps) == 1
    assert snaps[0].id == snap.id


def test_export_and_import_profile(store: ProfileStore, tmp_path: Path):
    store.create_profile(name="export_me", description="Ready for export", email="exp@test.com")
    zip_path = tmp_path / "exported.zip"
    store.export_profile("export_me", zip_path)
    assert zip_path.exists()

    imported = store.import_profile(zip_path, override_name="imported_profile")
    assert imported.name == "imported_profile"
    assert store.profile_exists("imported_profile")
