"""
Help and Keyboard Shortcuts Modal Screen for Textual TUI with arrow key guide.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static


class HelpModal(ModalScreen[None]):
    """Modal displaying keyboard shortcuts and help guide."""

    BINDINGS = [
        Binding("escape,enter", "dismiss_modal", "Close", show=True),
    ]

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Keyboard Shortcuts & Navigation", classes="modal-title")
            with ScrollableContainer():
                yield Static(self._build_help_text())

            with Horizontal(classes="modal-buttons"):
                yield Button("Close", variant="primary", id="btn-close")

    def on_mount(self) -> None:
        self.query_one("#btn-close", Button).focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def _build_help_text(self) -> Text:
        t = Text()
        shortcuts = [
            ("Arrow Key Navigation", [
                ("↑ / ↓", "Navigate up/down profiles (sidebar) or scroll content (right pane)"),
                ("→ (Right)", "Jump from sidebar into Details & Tabs, or cycle to next tab"),
                ("← (Left)", "Cycle to previous tab, or jump from first tab back to sidebar"),
                ("Enter", "Confirm action / Submit form / Switch to selected profile"),
                ("Escape", "Close active modal / Cancel action"),
            ]),
            ("Profile Actions", [
                ("s", "Switch to highlighted profile"),
                ("c", "Create a new profile"),
                ("d", "Jump to Live Diff tab"),
                ("y", "Sync live modifications from ~/.gemini into active profile"),
                ("r", "Rename selected profile"),
                ("x", "Soft-delete selected profile to trash"),
            ]),
            ("Management Modals", [
                ("b", "Open Backups & Snapshots Manager (with 1-click restore)"),
                ("t", "Open Soft-Deleted Profiles Trash (with 1-click restore)"),
                ("g", "Run Doctor diagnostics health check"),
                ("? / h", "Show this help screen"),
                ("q", "Quit application"),
            ]),
        ]

        for section, items in shortcuts:
            t.append(f"\n{section}\n", style="bold cyan")
            t.append("──────────────────────────────────────────\n", style="dim")
            for key, desc in items:
                t.append(f"  {key:<16}", style="bold green")
                t.append(f"{desc}\n", style="dim")

        return t

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss(None)
