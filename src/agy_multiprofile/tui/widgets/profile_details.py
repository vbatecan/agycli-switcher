"""
Simple, elegant Profile Summary Card for Textual TUI.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import Static

from agy_multiprofile.core.models import ProfileMetadata
from agy_multiprofile.core.sync import load_profile_files


class ProfileDetailsWidget(Vertical):
    """Clean summary card for the currently highlighted profile."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current_meta: ProfileMetadata | None = None
        self.current_profile_dir: Path | None = None
        self.is_active: bool = False

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(Static(id="details-card-text"), id="details-card")

    def update_profile(
        self,
        meta: ProfileMetadata | None,
        profile_dir: Path | None,
        is_active: bool,
    ) -> None:
        """Update the rendered card when selected profile changes."""
        self.current_meta = meta
        self.current_profile_dir = profile_dir
        self.is_active = is_active

        static = self.query_one("#details-card-text", Static)
        if not meta or not profile_dir or not profile_dir.exists():
            static.update(Text("No profile selected.", style="dim"))
            return

        files_data = load_profile_files(profile_dir)
        cli_settings = files_data.get("cli_settings", {})
        mcp_data = files_data.get("mcp_config", {})
        mcp_servers = mcp_data.get("mcpServers", {}) if isinstance(mcp_data, dict) else {}

        t = Text()

        # Status Line
        status_badge = "● Active Profile" if is_active else "○ Inactive Profile"
        badge_style = "bold green" if is_active else "dim"
        t.append(f"{status_badge}\n", style=badge_style)

        # Basic Info
        t.append("  • Name:        ", style="bold")
        t.append(f"{meta.name}\n")

        t.append("  • Account:     ", style="bold")
        t.append(f"{meta.email or '(not set)'}\n", style="cyan" if meta.email else "dim")

        if meta.gcloud_config:
            t.append("  • gcloud:      ", style="bold")
            t.append(f"{meta.gcloud_config}\n")

        t.append("  • Model:       ", style="bold")
        t.append(f"{cli_settings.get('model', 'Default (Gemini 3.7 Flash)')}\n")

        # MCP Servers Line
        t.append("  • MCP Servers: ", style="bold")
        if mcp_servers:
            srv_names = ", ".join(sorted(mcp_servers.keys()))
            t.append(f"{len(mcp_servers)} ({srv_names})\n", style="green")
        else:
            t.append("None configured\n", style="dim")

        if meta.description:
            t.append("  • Description: ", style="bold")
            t.append(f"{meta.description}\n", style="italic")

        static.update(t)
