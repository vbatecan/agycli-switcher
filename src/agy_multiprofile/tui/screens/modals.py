"""
Clean, simple modal dialogs for the Textual TUI.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Checkbox, Input, Label, Static

ScreenResultType = TypeVar("ScreenResultType")


class BaseArrowModal(ModalScreen[ScreenResultType], Generic[ScreenResultType]):
    """Base modal screen supporting arrow-key focus traversal and escape dismissal."""

    BINDINGS = [
        Binding("escape", "dismiss_modal", "Cancel", show=True),
    ]

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_key(self, event: events.Key) -> None:
        """Handle Up/Down/Left/Right arrow navigation across modal controls."""
        if event.key in ("down", "j"):
            self.focus_next()
            event.prevent_default()
            event.stop()
        elif event.key in ("up", "k"):
            self.focus_previous()
            event.prevent_default()
            event.stop()
        elif event.key in ("left", "right", "h", "l"):
            focused = self.focused
            if isinstance(focused, Button):
                if event.key in ("left", "h"):
                    self.focus_previous()
                else:
                    self.focus_next()
                event.prevent_default()
                event.stop()


class CreateProfileModal(BaseArrowModal[dict[str, Any] | None]):
    """Clean, simple modal dialog for creating a new profile."""

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Create New Profile", classes="modal-title")
            
            yield Label("Profile Name:", classes="field-label")
            yield Input(placeholder="e.g. work, personal, staging", id="input-name")

            yield Label("Google Account Email (optional):", classes="field-label")
            yield Input(placeholder="e.g. user@gmail.com", id="input-email")

            yield Label("Description (optional):", classes="field-label")
            yield Input(placeholder="Brief description", id="input-desc")

            yield Checkbox("Clone current active configuration", value=False, id="check-clone-live")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Create", variant="primary", id="btn-create")

    def on_mount(self) -> None:
        self.query_one("#input-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-create":
            name = self.query_one("#input-name", Input).value.strip()
            if not name:
                self.notify("Profile name cannot be empty.", severity="error")
                return
            
            email = self.query_one("#input-email", Input).value.strip() or None
            desc = self.query_one("#input-desc", Input).value.strip()
            clone_live = self.query_one("#check-clone-live", Checkbox).value

            self.dismiss({
                "name": name,
                "description": desc,
                "email": email,
                "clone_from_live": clone_live,
            })


class SwitchConfirmModal(BaseArrowModal[dict[str, bool] | None]):
    """Simple confirmation modal before switching profiles."""

    def __init__(self, target_name: str, has_running_procs: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.target_name = target_name
        self.has_running_procs = has_running_procs

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Confirm Profile Switch", classes="modal-title")
            
            msg = Text()
            msg.append(f"Switch active profile to '", style="bold")
            msg.append(self.target_name, style="bold green")
            msg.append("'?\n")

            if self.has_running_procs:
                msg.append("\n⚠ Note: Active Antigravity process(es) detected.\n", style="yellow")

            yield Static(msg)
            yield Checkbox("Dry Run (preview only)", value=False, id="check-dry-run")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Switch", variant="success", id="btn-confirm")

    def on_mount(self) -> None:
        self.query_one("#btn-confirm", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-confirm":
            dry_run = self.query_one("#check-dry-run", Checkbox).value
            self.dismiss({"dry_run": dry_run, "force": False})


class RenameProfileModal(BaseArrowModal[str | None]):
    """Modal dialog for renaming a profile."""

    def __init__(self, old_name: str, **kwargs):
        super().__init__(**kwargs)
        self.old_name = old_name

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label(f"Rename Profile '{self.old_name}'", classes="modal-title")
            yield Label("New Profile Name:", classes="field-label")
            yield Input(value=self.old_name, id="input-new-name")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Rename", variant="primary", id="btn-rename")

    def on_mount(self) -> None:
        self.query_one("#input-new-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-rename":
            new_name = self.query_one("#input-new-name", Input).value.strip()
            if not new_name:
                self.notify("New profile name cannot be empty.", severity="error")
                return
            self.dismiss(new_name)


class CloneProfileModal(BaseArrowModal[tuple[str, str] | None]):
    """Modal dialog for cloning a profile."""

    def __init__(self, source_name: str, **kwargs):
        super().__init__(**kwargs)
        self.source_name = source_name

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label(f"Clone Profile '{self.source_name}'", classes="modal-title")
            yield Label("New Cloned Profile Name:", classes="field-label")
            yield Input(placeholder="e.g. work-clone", id="input-dest-name")
            yield Label("Description (optional):", classes="field-label")
            yield Input(placeholder=f"Clone of {self.source_name}", id="input-desc")

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                yield Button("Clone Profile", variant="primary", id="btn-clone")

    def on_mount(self) -> None:
        self.query_one("#input-dest-name", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-clone":
            dest_name = self.query_one("#input-dest-name", Input).value.strip()
            if not dest_name:
                self.notify("Destination name cannot be empty.", severity="error")
                return
            desc = self.query_one("#input-desc", Input).value.strip()
            self.dismiss((dest_name, desc))


class ConfirmActionModal(BaseArrowModal[bool]):
    """Generic simple confirmation dialog."""

    def __init__(self, title: str, message: str, confirm_label: str = "Confirm", is_danger: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.dialog_title = title
        self.dialog_message = message
        self.confirm_label = confirm_label
        self.is_danger = is_danger

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label(self.dialog_title, classes="modal-title")
            yield Static(self.dialog_message)

            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", variant="default", id="btn-cancel")
                variant = "error" if self.is_danger else "primary"
                yield Button(self.confirm_label, variant=variant, id="btn-confirm")

    def on_mount(self) -> None:
        self.query_one("#btn-cancel", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "btn-confirm")
