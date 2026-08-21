"""
Diagnostic Doctor Modal Screen for Textual TUI.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

from agy_multiprofile.core.doctor import run_doctor
from agy_multiprofile.core.storage import ProfileStore


class DoctorModal(ModalScreen[None]):
    """Modal displaying system diagnostics and health status."""

    BINDINGS = [
        Binding("escape,enter", "dismiss_modal", "Close", show=True),
    ]

    def __init__(self, store: ProfileStore, **kwargs):
        super().__init__(**kwargs)
        self.store = store

    def compose(self) -> ComposeResult:
        with Container(classes="modal-dialog"):
            yield Label("Antigravity Profile Doctor", classes="modal-title")
            with ScrollableContainer(id="doctor-scroll"):
                yield Static(id="doctor-report")

            with Horizontal(classes="modal-buttons"):
                yield Button("Close", variant="primary", id="btn-close")

    def on_mount(self) -> None:
        report_static = self.query_one("#doctor-report", Static)
        res = run_doctor(self.store.root_dir, self.store.gemini_home)

        t = Text()
        if res.is_valid:
            t.append("✔ ALL DIAGNOSTICS PASSED\n\n", style="bold green")
        else:
            t.append("✖ ISSUES DETECTED\n\n", style="bold red")

        t.append("System Information:\n", style="bold cyan")
        for info in res.info:
            t.append(f"  • {info}\n", style="dim")

        if res.warnings:
            t.append("\nWarnings:\n", style="bold yellow")
            for warn in res.warnings:
                t.append(f"  ⚠ {warn}\n", style="yellow")

        if res.errors:
            t.append("\nErrors:\n", style="bold red")
            for err in res.errors:
                t.append(f"  ✖ {err}\n", style="bold red")

        report_static.update(t)
        self.query_one("#btn-close", Button).focus()

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss(None)
