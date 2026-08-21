"""
Backups and Snapshots Modal Screen for Textual TUI with arrow key navigation.
"""

from __future__ import annotations

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label, Static

from agy_multiprofile.core.storage import ProfileStore


class BackupsModal(ModalScreen[str | None]):
    """Modal displaying available backup snapshots with option to restore."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", show=True),
    ]

    def __init__(self, store: ProfileStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Safety Backup Snapshots", classes="modal-title")
            yield DataTable(id="table-snapshots", cursor_type="row")

            with Horizontal(classes="modal-buttons"):
                yield Button("Close", variant="default", id="btn-close")
                yield Button("Restore Selected Snapshot", variant="warning", id="btn-restore")

    def on_mount(self) -> None:
        table = self.query_one("#table-snapshots", DataTable)
        table.add_columns("Snapshot ID", "Timestamp", "Trigger", "Files")
        
        snapshots = self.store.list_snapshots()
        if not snapshots:
            table.add_row("No snapshots found", "-", "-", "-")
        else:
            for s in snapshots:
                ts_str = s.timestamp[:19].replace("T", " ")
                table.add_row(s.id, ts_str, s.trigger, str(len(s.files)), key=s.id)
        table.focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        if event.key in ("left", "right", "h", "l"):
            # Toggle between Close and Restore buttons
            if isinstance(self.focused, Button):
                if event.key in ("left", "h"):
                    self.focus_previous()
                else:
                    self.focus_next()
                event.prevent_default()
                event.stop()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss(None)
        elif event.button.id == "btn-restore":
            table = self.query_one("#table-snapshots", DataTable)
            if table.cursor_row is not None and table.row_count > 0:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                snap_id = str(row_key.value)
                if snap_id.startswith("snap_"):
                    self.dismiss(snap_id)
                    return
            self.notify("Please select a valid snapshot to restore.", severity="warning")
