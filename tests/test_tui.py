"""
Tests for Simple Textual TUI Application.
"""

from pathlib import Path
import pytest

from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.tui.app import ProfileManagerApp
from agy_multiprofile.tui.screens import CreateProfileModal
from agy_multiprofile.tui.widgets import ProfileDetailsWidget, ProfileListView


@pytest.mark.asyncio
async def test_tui_app_mount_simple(temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("work", email="work@company.com", clone_from_live=True)
    store.create_profile("personal", email="personal@gmail.com")

    app = ProfileManagerApp(store=store, gemini_home=temp_gemini_home)
    async with app.run_test() as pilot:
        list_view = app.query_one("#profile-list-view", ProfileListView)
        assert len(list_view.children) == 2

        details = app.query_one("#profile-details-widget", ProfileDetailsWidget)
        assert details.current_meta is not None


@pytest.mark.asyncio
async def test_tui_navigate_and_switch(temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    store.create_profile("work", email="work@company.com")

    app = ProfileManagerApp(store=store, gemini_home=temp_gemini_home)
    async with app.run_test() as pilot:
        list_view = app.query_one("#profile-list-view", ProfileListView)
        
        # Navigate down with arrow key
        await pilot.press("down")
        assert list_view.index == 1

        # Press Enter to switch to 'work'
        await pilot.press("enter")
        await pilot.pause()

        manifest = store.get_manifest()
        assert manifest.active_profile == "work"


@pytest.mark.asyncio
async def test_tui_open_create_modal(temp_vault_home: Path, temp_gemini_home: Path):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)

    app = ProfileManagerApp(store=store, gemini_home=temp_gemini_home)
    async with app.run_test() as pilot:
        # Press 'c' to open create modal
        await pilot.press("c")
        assert isinstance(app.screen, CreateProfileModal)
        await pilot.press("escape")
        assert not isinstance(app.screen, CreateProfileModal)
