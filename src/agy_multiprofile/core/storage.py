"""
Profile vault storage manager, snapshots, backups, and soft-delete trash.
"""

from __future__ import annotations

import json
import os
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agy_multiprofile.core.constants import (
    BACKUPS_DIRNAME,
    DEFAULT_PROFILE_NAME,
    MANAGED_FILES,
    MANIFEST_FILENAME,
    MAX_BACKUPS_RETENTION,
    PROFILE_META_FILENAME,
    PROFILES_DIRNAME,
    TRASH_DIRNAME,
    get_gemini_home,
    get_profile_home,
)
from agy_multiprofile.core.models import (
    Manifest,
    ProfileMetadata,
    SnapshotMetadata,
    TrashMetadata,
    utc_now_iso,
)
from agy_multiprofile.core.sync import capture_live_to_profile
from agy_multiprofile.utils.atomic import (
    atomic_copy_file,
    atomic_write_json,
)
from agy_multiprofile.utils.json_utils import safe_load_json


class ProfileStore:
    """
    Manages the ~/.config/agy-profile/ vault filesystem.
    """

    def __init__(self, root_dir: Path | None = None, gemini_home: Path | None = None):
        self.root_dir = (root_dir or get_profile_home()).resolve()
        self.gemini_home = (gemini_home or get_gemini_home()).resolve()
        self.profiles_dir = self.root_dir / PROFILES_DIRNAME
        self.backups_dir = self.root_dir / BACKUPS_DIRNAME
        self.trash_dir = self.root_dir / TRASH_DIRNAME
        self.manifest_file = self.root_dir / MANIFEST_FILENAME

    def initialize_vault(self) -> None:
        """Create vault structure if it doesn't exist."""
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        self.trash_dir.mkdir(parents=True, exist_ok=True)

        if not self.manifest_file.exists():
            manifest = Manifest(active_profile=DEFAULT_PROFILE_NAME)
            atomic_write_json(self.manifest_file, manifest.to_dict())

    def get_manifest(self) -> Manifest:
        """Read vault manifest."""
        self.initialize_vault()
        success, data, _ = safe_load_json(self.manifest_file)
        if success and isinstance(data, dict):
            return Manifest.from_dict(data)
        manifest = Manifest()
        atomic_write_json(self.manifest_file, manifest.to_dict())
        return manifest

    def save_manifest(self, manifest: Manifest) -> None:
        """Save vault manifest."""
        self.initialize_vault()
        manifest.updated_at = utc_now_iso()
        atomic_write_json(self.manifest_file, manifest.to_dict())

    def get_profile_dir(self, name: str) -> Path:
        """Return the directory path for a profile."""
        return self.profiles_dir / name

    def profile_exists(self, name: str) -> bool:
        """Check if a profile exists."""
        return self.get_profile_dir(name).exists()

    def list_profiles(self) -> list[ProfileMetadata]:
        """List all profiles in the vault."""
        self.initialize_vault()
        profiles: list[ProfileMetadata] = []
        if not self.profiles_dir.exists():
            return profiles

        for p_dir in sorted(self.profiles_dir.iterdir()):
            if p_dir.is_dir() and not p_dir.name.startswith("."):
                meta = self.get_profile_metadata(p_dir.name)
                if meta:
                    profiles.append(meta)
        return profiles

    def get_profile_metadata(self, name: str) -> ProfileMetadata | None:
        """Read profile.json metadata for a profile."""
        p_dir = self.get_profile_dir(name)
        meta_file = p_dir / PROFILE_META_FILENAME
        if not meta_file.exists():
            return None
        success, data, _ = safe_load_json(meta_file)
        if success and isinstance(data, dict):
            return ProfileMetadata.from_dict(data)
        return None

    def save_profile_metadata(self, meta: ProfileMetadata) -> None:
        """Save profile metadata."""
        p_dir = self.get_profile_dir(meta.name)
        p_dir.mkdir(parents=True, exist_ok=True)
        meta.updated_at = utc_now_iso()
        atomic_write_json(p_dir / PROFILE_META_FILENAME, meta.to_dict())

    def create_profile(
        self,
        name: str,
        description: str = "",
        email: str | None = None,
        gcloud_config: str | None = None,
        clone_from_profile: str | None = None,
        clone_from_live: bool = False,
    ) -> ProfileMetadata:
        """
        Create a new profile.
        Can initialize from existing profile or capture from live ~/.gemini.
        """
        self.initialize_vault()
        name = name.strip()
        if not name or "/" in name or "\\" in name:
            raise ValueError(f"Invalid profile name: '{name}'")
        if self.profile_exists(name):
            raise FileExistsError(f"Profile '{name}' already exists.")

        p_dir = self.get_profile_dir(name)
        p_dir.mkdir(parents=True, exist_ok=True)

        if clone_from_profile:
            src_dir = self.get_profile_dir(clone_from_profile)
            if not src_dir.exists():
                raise FileNotFoundError(f"Source profile '{clone_from_profile}' does not exist.")
            for item in src_dir.iterdir():
                if item.is_file() and item.name != PROFILE_META_FILENAME:
                    dest_file = p_dir / item.name
                    atomic_copy_file(item, dest_file)
                    if item.name == "auth_token.json":
                        try:
                            os.chmod(dest_file, 0o600)
                        except Exception:
                            pass
        elif clone_from_live:
            capture_live_to_profile(p_dir, self.gemini_home)
        else:
            # Initialize clean defaults while preserving workspace trust so user isn't re-prompted
            live_cli_settings = self.gemini_home / "antigravity-cli" / "settings.json"
            trusted_workspaces = []
            if live_cli_settings.exists():
                s_ok, s_data, _ = safe_load_json(live_cli_settings)
                if s_ok and isinstance(s_data, dict):
                    trusted_workspaces = s_data.get("trustedWorkspaces", [])

            live_trusted_folders = self.gemini_home / "trustedFolders.json"
            trusted_folders_data: dict[str, Any] = {}
            if live_trusted_folders.exists():
                f_ok, f_data, _ = safe_load_json(live_trusted_folders)
                if f_ok and isinstance(f_data, dict):
                    trusted_folders_data = f_data

            for spec in MANAGED_FILES:
                if spec.is_json:
                    if spec.key == "mcp_config":
                        atomic_write_json(p_dir / spec.profile_filename, {"mcpServers": {}})
                    elif spec.key == "google_accounts":
                        atomic_write_json(p_dir / spec.profile_filename, {"active": email, "old": []})
                    elif spec.key == "cli_settings":
                        settings_payload = {"trustedWorkspaces": trusted_workspaces} if trusted_workspaces else {}
                        atomic_write_json(p_dir / spec.profile_filename, settings_payload)
                    elif spec.key == "trusted_folders":
                        atomic_write_json(p_dir / spec.profile_filename, trusted_folders_data)
                    else:
                        atomic_write_json(p_dir / spec.profile_filename, {})

        meta = ProfileMetadata(
            name=name,
            description=description,
            email=email,
            gcloud_config=gcloud_config,
        )
        self.save_profile_metadata(meta)
        return meta

    def clone_profile(self, src_name: str, dest_name: str, new_desc: str = "") -> ProfileMetadata:
        """Clone an existing profile."""
        src_meta = self.get_profile_metadata(src_name)
        if not src_meta:
            raise FileNotFoundError(f"Source profile '{src_name}' does not exist.")
        
        desc = new_desc or f"Cloned from {src_name}"
        return self.create_profile(
            name=dest_name,
            description=desc,
            email=src_meta.email,
            gcloud_config=src_meta.gcloud_config,
            clone_from_profile=src_name,
        )

    def rename_profile(self, old_name: str, new_name: str) -> None:
        """Rename a profile safely."""
        self.initialize_vault()
        old_dir = self.get_profile_dir(old_name)
        new_dir = self.get_profile_dir(new_name)

        if not old_dir.exists():
            raise FileNotFoundError(f"Profile '{old_name}' does not exist.")
        if new_dir.exists():
            raise FileExistsError(f"Profile '{new_name}' already exists.")

        meta = self.get_profile_metadata(old_name)
        if not meta:
            meta = ProfileMetadata(name=new_name)
        else:
            meta.name = new_name

        shutil.move(str(old_dir), str(new_dir))
        self.save_profile_metadata(meta)

        # Update manifest active profile if needed
        manifest = self.get_manifest()
        if manifest.active_profile == old_name:
            manifest.active_profile = new_name
            self.save_manifest(manifest)

    def soft_delete_profile(self, name: str) -> TrashMetadata:
        """
        Soft-delete a profile by moving it to the trash folder.
        NEVER permanently deletes files.
        """
        self.initialize_vault()
        manifest = self.get_manifest()
        if manifest.active_profile == name:
            raise RuntimeError(f"Cannot delete currently active profile '{name}'. Switch to another profile first.")

        p_dir = self.get_profile_dir(name)
        if not p_dir.exists():
            raise FileNotFoundError(f"Profile '{name}' does not exist.")

        meta = self.get_profile_metadata(name)
        meta_dict = meta.to_dict() if meta else {"name": name}

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        trash_id = f"{timestamp_str}_{name}"
        target_trash_dir = self.trash_dir / trash_id

        shutil.move(str(p_dir), str(target_trash_dir))

        trash_meta = TrashMetadata(
            trash_id=trash_id,
            profile_name=name,
            profile_meta=meta_dict,
        )
        atomic_write_json(target_trash_dir / ".trash_meta.json", trash_meta.to_dict())
        return trash_meta

    def list_trash(self) -> list[TrashMetadata]:
        """List all soft-deleted items in trash."""
        self.initialize_vault()
        items: list[TrashMetadata] = []
        if not self.trash_dir.exists():
            return items

        for item_dir in sorted(self.trash_dir.iterdir(), reverse=True):
            if item_dir.is_dir():
                meta_file = item_dir / ".trash_meta.json"
                if meta_file.exists():
                    success, data, _ = safe_load_json(meta_file)
                    if success and isinstance(data, dict):
                        items.append(TrashMetadata.from_dict(data))
                else:
                    items.append(TrashMetadata(trash_id=item_dir.name, profile_name=item_dir.name))
        return items

    def restore_from_trash(self, trash_id: str, new_name: str | None = None) -> ProfileMetadata:
        """Restore a profile from trash."""
        self.initialize_vault()
        target_trash_dir = self.trash_dir / trash_id
        if not target_trash_dir.exists():
            raise FileNotFoundError(f"Trash item '{trash_id}' not found.")

        meta_file = target_trash_dir / ".trash_meta.json"
        profile_name = new_name
        meta_dict = {}
        if meta_file.exists():
            success, data, _ = safe_load_json(meta_file)
            if success and isinstance(data, dict):
                meta_dict = data.get("profile_meta", {})
                if not profile_name:
                    profile_name = data.get("profile_name", "restored_profile")
            meta_file.unlink()

        if not profile_name:
            profile_name = trash_id

        dest_dir = self.get_profile_dir(profile_name)
        if dest_dir.exists():
            raise FileExistsError(f"Cannot restore: Profile '{profile_name}' already exists.")

        shutil.move(str(target_trash_dir), str(dest_dir))
        
        meta = ProfileMetadata.from_dict(meta_dict) if meta_dict else ProfileMetadata(name=profile_name)
        meta.name = profile_name
        self.save_profile_metadata(meta)
        return meta

    def create_snapshot(self, trigger: str, source_profile: str | None = None) -> SnapshotMetadata:
        """
        Create a full snapshot backup of the live ~/.gemini configuration.
        """
        self.initialize_vault()
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"snap_{timestamp_str}_{trigger}"
        snap_dir = self.backups_dir / snapshot_id
        snap_dir.mkdir(parents=True, exist_ok=True)

        files_backed_up: list[str] = []
        for spec in MANAGED_FILES:
            live_path = self.gemini_home / spec.relative_live_path
            if live_path.exists():
                snap_dest = snap_dir / spec.profile_filename
                atomic_copy_file(live_path, snap_dest)
                files_backed_up.append(spec.relative_live_path)

        meta = SnapshotMetadata(
            id=snapshot_id,
            timestamp=utc_now_iso(),
            trigger=trigger,
            source_profile=source_profile,
            files=files_backed_up,
        )
        atomic_write_json(snap_dir / "snapshot.json", meta.to_dict())
        self.prune_snapshots()
        return meta

    def list_snapshots(self) -> list[SnapshotMetadata]:
        """List all available backup snapshots."""
        self.initialize_vault()
        snapshots: list[SnapshotMetadata] = []
        if not self.backups_dir.exists():
            return snapshots

        for s_dir in sorted(self.backups_dir.iterdir(), reverse=True):
            if s_dir.is_dir() and s_dir.name.startswith("snap_"):
                meta_file = s_dir / "snapshot.json"
                if meta_file.exists():
                    success, data, _ = safe_load_json(meta_file)
                    if success and isinstance(data, dict):
                        snapshots.append(SnapshotMetadata.from_dict(data))
        return snapshots

    def prune_snapshots(self, keep_count: int = MAX_BACKUPS_RETENTION) -> int:
        """Prune old snapshots beyond retention count."""
        snapshots = self.list_snapshots()
        if len(snapshots) <= keep_count:
            return 0

        to_remove = snapshots[keep_count:]
        for snap in to_remove:
            snap_dir = self.backups_dir / snap.id
            if snap_dir.exists():
                shutil.rmtree(str(snap_dir), ignore_errors=True)
        return len(to_remove)

    def export_profile(self, name: str, export_zip_path: Path) -> None:
        """Export a profile directory as a portable ZIP archive."""
        p_dir = self.get_profile_dir(name)
        if not p_dir.exists():
            raise FileNotFoundError(f"Profile '{name}' does not exist.")

        export_zip_path = export_zip_path.resolve()
        export_zip_path.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(export_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in p_dir.rglob("*"):
                if item.is_file() and not item.name.startswith(".tmp"):
                    arcname = item.relative_to(p_dir)
                    zf.write(item, arcname)

    def import_profile(self, import_zip_path: Path, override_name: str | None = None) -> ProfileMetadata:
        """Import a profile from a ZIP archive."""
        if not import_zip_path.exists():
            raise FileNotFoundError(f"Import file does not exist: {import_zip_path}")

        temp_dir = self.root_dir / f".import_tmp_{datetime.now().timestamp()}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(import_zip_path, "r") as zf:
                zf.extractall(temp_dir)

            meta_file = temp_dir / PROFILE_META_FILENAME
            if meta_file.exists():
                success, data, _ = safe_load_json(meta_file)
                profile_name = override_name or (data.get("name") if success else None)
            else:
                profile_name = override_name or import_zip_path.stem

            if not profile_name:
                profile_name = "imported_profile"

            if self.profile_exists(profile_name):
                raise FileExistsError(f"Profile '{profile_name}' already exists. Use --name to specify a different name.")

            target_dir = self.get_profile_dir(profile_name)
            shutil.move(str(temp_dir), str(target_dir))

            meta = self.get_profile_metadata(profile_name)
            if not meta:
                meta = ProfileMetadata(name=profile_name)
            else:
                meta.name = profile_name
            self.save_profile_metadata(meta)
            return meta
        finally:
            if temp_dir.exists():
                shutil.rmtree(str(temp_dir), ignore_errors=True)
