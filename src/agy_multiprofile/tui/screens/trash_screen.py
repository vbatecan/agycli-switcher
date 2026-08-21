"""
Soft-delete Trash Modal Screen for Textual TUI with arrow key navigation.
"""

from __future__ import annotations

from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Label

from agy_multiprofile.core.storage import ProfileStore


class TrashModal(ModalScreen[str | None]):
    """Modal displaying soft-deleted profiles in trash with restore option."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Close", show=True),
    ]

    def __init__(self, store: ProfileStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Soft-Deleted Profiles (Trash)", classes="modal-title")
            yield DataTable(id="table-trash", cursor_type="row")

            with Horizontal(classes="modal-buttons"):
                yield Button("Close", variant="default", id="btn-close")
                yield Button("Restore Profile", variant="success", id="btn-restore")

    def on_mount(self) -> None:
        table = self.query_one("#table-trash", DataTable)
        table.add_columns("Trash ID", "Original Name", "Deleted At")

        items = self.store.list_trash()
        if not items:
            table.add_row("Trash is empty", "-", "-")
        else:
            for it in items:
                ts_str = it.deleted_at[:19].replace("T", " ")
                table.add_row(it.trash_id, it.profile_name, ts_str, key=it.trash_id)
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
            table = self.query_one("#table-trash", DataTable)
            if table.cursor_row is not None and table.row_count > 0:
                row_key, _ = table.coordinate_to_cell_key(table.cursor_coordinate)
                trash_id = str(row_key.value)
                if trash_id and trash_id != "Trash is empty":
                    self.dismiss(trash_id)
                    return
            self.notify("Please select an item from trash to restore.", severity="warning")
