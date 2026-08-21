"""
Simple, clean Main Textual Application for agy-profile.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Label, ListView, Static

from agy_multiprofile import __version__
from agy_multiprofile.core.constants import DEFAULT_PROFILE_NAME, get_gemini_home, get_profile_home
from agy_multiprofile.core.detector import find_running_antigravity_processes
from agy_multiprofile.core.models import ProfileMetadata
from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.switcher import ProfileSwitcher
from agy_multiprofile.core.sync import load_profile_files
from agy_multiprofile.tui.screens.modals import (
    ConfirmActionModal,
    CreateProfileModal,
    RenameProfileModal,
)
from agy_multiprofile.tui.widgets import ProfileDetailsWidget, ProfileListItem, ProfileListView


class ProfileManagerApp(App):
    """Simple, clean interactive switcher for Antigravity profiles."""

    CSS_PATH = "style.tcss"
    TITLE = f"Antigravity Profile Switcher v{__version__}"

    BINDINGS = [
        Binding("enter", "switch_and_launch", "Select & Launch agy", show=True),
        Binding("s", "switch_profile", "Switch only", show=True),
        Binding("c", "create_profile", "New", show=True),
        Binding("d,x", "delete_profile", "Delete", show=True),
        Binding("r", "rename_profile", "Rename", show=True),
        Binding("q,escape", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        store: ProfileStore | None = None,
        gemini_home: Path | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.store = store or ProfileStore(gemini_home=gemini_home)
        self.switcher = ProfileSwitcher(store=self.store, gemini_home=gemini_home)
        self.gemini_home = (gemini_home or self.store.gemini_home).resolve()
        self._selected_meta: ProfileMetadata | None = None

    def compose(self) -> ComposeResult:
        with Horizontal(id="header-container"):
            yield Label(f"◆ Antigravity Profiles", id="header-title")
            yield Label("", id="header-status")

        with Vertical(id="main-container"):
            with Vertical(id="list-container"):
                yield Label("PROFILES (Press ↑/↓ to navigate, Enter to select & launch agy, 's' to switch only)", classes="pane-title")
                yield ProfileListView(id="profile-list-view")

            with Vertical(id="details-container"):
                yield Label("PROFILE SUMMARY", classes="pane-title")
                yield ProfileDetailsWidget(id="profile-details-widget")

        yield Footer()

    def on_mount(self) -> None:
        self._ensure_initialized()
        self.refresh_profiles()

    def _ensure_initialized(self) -> None:
        self.store.initialize_vault()
        profiles = self.store.list_profiles()
        if not profiles:
            self.store.create_profile(
                name=DEFAULT_PROFILE_NAME,
                description="Default live profile",
                clone_from_live=True,
            )

    def refresh_profiles(self, select_name: str | None = None) -> None:
        """Reload profiles list and refresh active indicators."""
        manifest = self.store.get_manifest()
        active_name = manifest.active_profile

        # Update Header status badge
        header_status = self.query_one("#header-status", Label)
        header_status.update(f"Active: ● {active_name}")

        list_view = self.query_one("#profile-list-view", ProfileListView)
        list_view.clear()

        profiles = self.store.list_profiles()
        target_idx = 0

        for i, p in enumerate(profiles):
            is_active = p.name == active_name
            p_files = load_profile_files(self.store.get_profile_dir(p.name))
            mcp_data = p_files.get("mcp_config", {})
            mcp_count = len(mcp_data.get("mcpServers", {})) if isinstance(mcp_data, dict) else 0

            item = ProfileListItem(meta=p, is_active=is_active, mcp_count=mcp_count)
            list_view.append(item)

            if select_name and p.name == select_name:
                target_idx = i
            elif not select_name and is_active:
                target_idx = i

        if profiles:
            list_view.index = target_idx
            self._update_details_for_index(target_idx)
            list_view.focus()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and isinstance(event.item, ProfileListItem):
            self._selected_meta = event.item.meta
            manifest = self.store.get_manifest()
            is_active = event.item.meta.name == manifest.active_profile
            details = self.query_one("#profile-details-widget", ProfileDetailsWidget)
            details.update_profile(
                meta=event.item.meta,
                profile_dir=self.store.get_profile_dir(event.item.meta.name),
                is_active=is_active,
            )

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and isinstance(event.item, ProfileListItem):
            self._selected_meta = event.item.meta
            self.action_switch_and_launch()

    def _update_details_for_index(self, index: int) -> None:
        list_view = self.query_one("#profile-list-view", ProfileListView)
        if 0 <= index < len(list_view.children):
            item = list_view.children[index]
            if isinstance(item, ProfileListItem):
                self._selected_meta = item.meta
                manifest = self.store.get_manifest()
                is_active = item.meta.name == manifest.active_profile
                details = self.query_one("#profile-details-widget", ProfileDetailsWidget)
                details.update_profile(
                    meta=item.meta,
                    profile_dir=self.store.get_profile_dir(item.meta.name),
                    is_active=is_active,
                )

    def _get_highlighted_profile(self) -> ProfileMetadata | None:
        try:
            list_view = self.query_one("#profile-list-view", ProfileListView)
            if list_view.index is not None and 0 <= list_view.index < len(list_view.children):
                item = list_view.children[list_view.index]
                if isinstance(item, ProfileListItem):
                    return item.meta
        except Exception:
            pass
        return self._selected_meta

    def action_switch_and_launch(self) -> None:
        """Switch to highlighted profile and exit to launch agy."""
        meta = self._get_highlighted_profile()
        if not meta:
            self.notify("No profile selected.", severity="warning")
            return

        target_name = meta.name
        manifest = self.store.get_manifest()
        if target_name != manifest.active_profile:
            res = self.switcher.switch_profile(target_name=target_name)
            if not res.success:
                self.notify(f"Switch failed: {res.error}", severity="error")
                return

        self.exit(result=target_name)

    def action_switch_profile(self) -> None:
        """Switch to highlighted profile without exiting TUI."""
        meta = self._get_highlighted_profile()
        if not meta:
            self.notify("No profile selected.", severity="warning")
            return

        target_name = meta.name
        manifest = self.store.get_manifest()
        if target_name == manifest.active_profile:
            self.notify(f"Profile '{target_name}' is already active.", severity="information")
            return

        res = self.switcher.switch_profile(target_name=target_name)
        if res.success:
            self.notify(f"✔ Switched to profile '{target_name}'!", severity="information")
            self.refresh_profiles(select_name=target_name)
        else:
            self.notify(f"Switch failed: {res.error}", severity="error")

    def action_create_profile(self) -> None:
        def handle_create(data: dict[str, Any] | None) -> None:
            if not data:
                return
            try:
                meta = self.store.create_profile(
                    name=data["name"],
                    description=data.get("description", ""),
                    email=data.get("email"),
                    clone_from_live=data.get("clone_from_live", False),
                )
                self.notify(f"✔ Profile '{meta.name}' created.", severity="information")
                self.refresh_profiles(select_name=meta.name)
            except Exception as e:
                self.notify(f"Failed to create profile: {e}", severity="error")

        self.push_screen(CreateProfileModal(), handle_create)

    def action_delete_profile(self) -> None:
        meta = self._get_highlighted_profile()
        if not meta:
            self.notify("No profile selected.", severity="warning")
            return

        manifest = self.store.get_manifest()
        target_name = meta.name
        if target_name == manifest.active_profile:
            self.notify(f"Cannot delete active profile '{target_name}'.", severity="error")
            return

        def handle_delete(confirmed: bool) -> None:
            if not confirmed:
                return
            try:
                self.store.soft_delete_profile(target_name)
                self.notify(f"✔ Profile '{target_name}' moved to trash.", severity="information")
                self.refresh_profiles()
            except Exception as e:
                self.notify(f"Failed to delete profile: {e}", severity="error")

        self.push_screen(
            ConfirmActionModal(
                title="Delete Profile",
                message=f"Move profile '{target_name}' to trash?",
                confirm_label="Delete",
                is_danger=True,
            ),
            handle_delete,
        )

    def action_rename_profile(self) -> None:
        meta = self._get_highlighted_profile()
        if not meta:
            self.notify("No profile selected.", severity="warning")
            return

        old_name = meta.name


        def handle_rename(new_name: str | None) -> None:
            if not new_name or new_name == old_name:
                return
            try:
                self.store.rename_profile(old_name=old_name, new_name=new_name)
                self.notify(f"✔ Profile renamed to '{new_name}'!", severity="information")
                self.refresh_profiles(select_name=new_name)
            except Exception as e:
                self.notify(f"Failed to rename profile: {e}", severity="error")

        self.push_screen(RenameProfileModal(old_name=old_name), handle_rename)
