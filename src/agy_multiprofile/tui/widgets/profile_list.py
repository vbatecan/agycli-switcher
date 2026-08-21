"""
Clean, simple Profile List widgets for Textual TUI.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.widgets import Label, ListItem, ListView

from agy_multiprofile.core.models import ProfileMetadata


class ProfileListItem(ListItem):
    """A clean, single-row profile item in the list."""

    def __init__(
        self,
        meta: ProfileMetadata,
        is_active: bool,
        mcp_count: int = 0,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.meta = meta
        self.is_active = is_active
        self.mcp_count = mcp_count

    def compose(self) -> ComposeResult:
        t = Text()
        
        # Status icon
        if self.is_active:
            t.append("● ", style="bold green")
            t.append(f"{self.meta.name:<18}", style="bold")
            t.append(f" {(self.meta.email or '-'):<26}", style="green")
            t.append(f" [{self.mcp_count} MCPs]", style="cyan")
            t.append("  (active)", style="italic bold green")
        else:
            t.append("○ ", style="dim")
            t.append(f"{self.meta.name:<18}", style="")
            t.append(f" {(self.meta.email or '-'):<26}", style="dim")
            t.append(f" [{self.mcp_count} MCPs]", style="dim")

        yield Label(t)


class ProfileListView(ListView):
    """ListView that manages profiles with intuitive arrow key navigation."""
    pass
