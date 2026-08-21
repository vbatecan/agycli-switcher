"""
Atomic profile switcher with auto-sync, transaction rollback, and safety validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agy_multiprofile.core.auth import (
    apply_profile_token_to_keyring,
    capture_keyring_token_to_profile,
    set_live_google_account,
    switch_gcloud_account,
    switch_gcloud_configuration,
)
from agy_multiprofile.core.constants import (
    MANAGED_FILES,
    get_gemini_home,
    get_profile_home,
)
from agy_multiprofile.core.detector import check_brain_locks, find_running_antigravity_processes
from agy_multiprofile.core.doctor import validate_profile
from agy_multiprofile.core.lock import InterProcessLock
from agy_multiprofile.core.models import ProfileMetadata, SnapshotMetadata, utc_now_iso
from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.sync import apply_profile_to_live, capture_live_to_profile, load_live_files, load_profile_files
from agy_multiprofile.utils.atomic import TransactionContext
from agy_multiprofile.utils.diff_utils import generate_dict_diff


@dataclass
class SwitchPlan:
    """Preview plan for a switch operation."""
    source_profile: str
    target_profile: str
    files_to_sync_back: list[str]
    files_to_replace: list[str]
    diffs_per_file: dict[str, list[str]] = field(default_factory=dict)
    account_change: tuple[str | None, str | None] = (None, None)
    gcloud_config_change: tuple[str | None, str | None] = (None, None)
    running_processes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class SwitchResult:
    """Result of a completed profile switch operation."""
    success: bool
    source_profile: str
    target_profile: str
    snapshot: SnapshotMetadata | None = None
    files_updated: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


class ProfileSwitcher:
    """
    Coordinates seamless, atomic profile switching.
    """

    def __init__(self, store: ProfileStore | None = None, gemini_home: Path | None = None):
        self.store = store or ProfileStore(gemini_home=gemini_home)
        self.gemini_home = (gemini_home or self.store.gemini_home).resolve()

    def create_switch_plan(self, target_name: str) -> SwitchPlan:
        """
        Generate a dry-run preview of what switching to target_name will do.
        """
        manifest = self.store.get_manifest()
        source_name = manifest.active_profile

        if not self.store.profile_exists(target_name):
            raise FileNotFoundError(f"Target profile '{target_name}' does not exist.")

        target_meta = self.store.get_profile_metadata(target_name)
        source_meta = self.store.get_profile_metadata(source_name)

        target_dir = self.store.get_profile_dir(target_name)
        live_files_data = load_live_files(self.gemini_home)
        target_files_data = load_profile_files(target_dir)

        diffs: dict[str, list[str]] = {}
        files_to_replace: list[str] = []

        for spec in MANAGED_FILES:
            key = spec.key
            old_data = live_files_data.get(key, {})
            new_data = target_files_data.get(key, {})

            if isinstance(old_data, dict) and isinstance(new_data, dict):
                d = generate_dict_diff(old_data, new_data)
                if d:
                    diffs[spec.relative_live_path] = d
                    files_to_replace.append(spec.relative_live_path)

        running_procs = find_running_antigravity_processes()

        plan = SwitchPlan(
            source_profile=source_name,
            target_profile=target_name,
            files_to_sync_back=[s.relative_live_path for s in MANAGED_FILES],
            files_to_replace=files_to_replace,
            diffs_per_file=diffs,
            account_change=(source_meta.email if source_meta else None, target_meta.email if target_meta else None),
            gcloud_config_change=(
                source_meta.gcloud_config if source_meta else None,
                target_meta.gcloud_config if target_meta else None,
            ),
            running_processes=running_procs,
        )
        return plan

    def switch_profile(
        self,
        target_name: str,
        dry_run: bool = False,
        force: bool = False,
        skip_sync_source: bool = True,
        save_current: bool = False,
    ) -> SwitchResult:
        """
        Execute an atomic profile switch.
        """
        with InterProcessLock(self.store.root_dir):
            manifest = self.store.get_manifest()
            source_name = manifest.active_profile

            if not self.store.profile_exists(target_name):
                return SwitchResult(
                    success=False,
                    source_profile=source_name,
                    target_profile=target_name,
                    error=f"Target profile '{target_name}' does not exist.",
                )

            # 1. Process and lock check
            running = find_running_antigravity_processes()
            warnings: list[str] = []
            if running and not force:
                pids_desc = ", ".join(f"{p['name']}(pid={p['pid']})" for p in running)
                warnings.append(f"Running Antigravity process(es) detected: {pids_desc}")

            # 2. Pre-validate target profile
            target_dir = self.store.get_profile_dir(target_name)
            val = validate_profile(target_dir)
            if not val.is_valid:
                return SwitchResult(
                    success=False,
                    source_profile=source_name,
                    target_profile=target_name,
                    warnings=warnings,
                    error=f"Target profile validation failed: {'; '.join(val.errors)}",
                )

            if dry_run:
                plan = self.create_switch_plan(target_name)
                return SwitchResult(
                    success=True,
                    source_profile=source_name,
                    target_profile=target_name,
                    files_updated=plan.files_to_replace,
                    messages=["[DRY-RUN] Profile switch simulation succeeded."],
                    warnings=warnings,
                )

            # 3. Preserve active profile's credentials and config
            if self.store.profile_exists(source_name):
                source_dir = self.store.get_profile_dir(source_name)
                capture_keyring_token_to_profile(source_dir)
                if save_current or not skip_sync_source:
                    capture_live_to_profile(source_dir, self.gemini_home)

            # 4. Create safety snapshot backup
            snap_trigger = f"switch_{source_name}_to_{target_name}"
            snapshot = self.store.create_snapshot(trigger=snap_trigger, source_profile=source_name)

            # 5. Atomic transaction swap
            messages: list[str] = []
            applied_files: list[str] = []
            target_meta = self.store.get_profile_metadata(target_name)

            try:
                with TransactionContext() as tx:
                    # Apply configuration files
                    applied_files = apply_profile_to_live(target_dir, tx, self.gemini_home)

                    # Update Google account
                    if target_meta and target_meta.email:
                        set_live_google_account(target_meta.email, self.gemini_home)
                        messages.append(f"Set active Google Account: {target_meta.email}")

                    # Apply profile OAuth token to OS Keyring
                    ok_keyring, msg_keyring = apply_profile_token_to_keyring(target_dir)
                    messages.append(msg_keyring)

                    # Switch gcloud configuration or account if configured
                    if target_meta and target_meta.options.get("sync_gcloud", True):
                        if target_meta.gcloud_config:
                            ok, msg = switch_gcloud_configuration(target_meta.gcloud_config)
                            if ok:
                                messages.append(msg)
                            else:
                                warnings.append(f"gcloud: {msg}")
                        elif target_meta.email:
                            ok, msg = switch_gcloud_account(target_meta.email)
                            if ok:
                                messages.append(msg)
                            else:
                                warnings.append(f"gcloud: {msg}")

                    # Update manifest
                    manifest.active_profile = target_name
                    manifest.last_switched = utc_now_iso()
                    self.store.save_manifest(manifest)

                    tx.commit()
            except Exception as e:
                # Transaction context automatically executed rollback handlers
                return SwitchResult(
                    success=False,
                    source_profile=source_name,
                    target_profile=target_name,
                    snapshot=snapshot,
                    error=f"Transaction failed and was safely rolled back: {e}",
                )

            messages.append(f"Successfully switched active profile to '{target_name}'")
            return SwitchResult(
                success=True,
                source_profile=source_name,
                target_profile=target_name,
                snapshot=snapshot,
                files_updated=applied_files,
                messages=messages,
                warnings=warnings,
            )

    def restore_snapshot_to_live(self, snapshot_id: str) -> tuple[bool, str]:
        """
        Restore live ~/.gemini configuration from a safety snapshot.
        """
        with InterProcessLock(self.store.root_dir):
            snap_dir = self.store.backups_dir / snapshot_id
            if not snap_dir.exists():
                return False, f"Snapshot '{snapshot_id}' does not exist."

            # Pre-restore safety snapshot of whatever is live right now
            self.store.create_snapshot(trigger=f"pre_restore_{snapshot_id}")

            with TransactionContext() as tx:
                try:
                    for spec in MANAGED_FILES:
                        snap_file = snap_dir / spec.profile_filename
                        live_file = self.gemini_home / spec.relative_live_path
                        if snap_file.exists():
                            tx.record_and_replace(live_file, snap_file)
                    tx.commit()
                    return True, f"Successfully restored environment from snapshot '{snapshot_id}'"
                except Exception as e:
                    return False, f"Restore failed and was rolled back: {e}"
