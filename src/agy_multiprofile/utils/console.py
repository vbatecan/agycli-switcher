"""
Console formatting, ANSI colors, Rich tables, and interactive prompts.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Sequence

from rich import box
from rich.console import Console
from rich.prompt import Confirm
from rich.table import Table
from rich.text import Text

# Global Rich consoles
console = Console(highlight=False)
err_console = Console(stderr=True, highlight=False)


def supports_color() -> bool:
    """Check whether current terminal supports ANSI color."""
    if os.environ.get("NO_COLOR") or os.environ.get("TERM") == "dumb":
        return False
    return sys.stdout.isatty()


USE_COLOR = supports_color()


def colorize(text: str, color_code: str) -> str:
    """Wrap text in ANSI escape code if color is enabled."""
    if not USE_COLOR:
        return text
    return f"\033[{color_code}m{text}\033[0m"


def bold(text: str) -> str:
    return colorize(text, "1")


def green(text: str) -> str:
    return colorize(text, "32")


def red(text: str) -> str:
    return colorize(text, "31")


def yellow(text: str) -> str:
    return colorize(text, "33")


def cyan(text: str) -> str:
    return colorize(text, "36")


def magenta(text: str) -> str:
    return colorize(text, "35")


def dim(text: str) -> str:
    return colorize(text, "2")


def print_success(message: str) -> None:
    console.print(f"[bold green]✔[/bold green] {message}")


def print_error(message: str) -> None:
    err_console.print(f"[bold red]✖ Error:[/bold red] {message}")


def print_warning(message: str) -> None:
    err_console.print(f"[bold yellow]⚠ Warning:[/bold yellow] {message}")


def print_info(message: str) -> None:
    console.print(f"[bold cyan]ℹ[/bold cyan] {message}")


def print_table(
    headers: Sequence[str],
    rows: Sequence[Sequence[Any]],
    title: str | None = None,
) -> None:
    """Print an aligned, beautiful Rich table with headers."""
    if not rows and not headers:
        return

    table = Table(
        title=title,
        box=box.ROUNDED,
        header_style="bold cyan",
        border_style="dim",
        show_edge=True,
        pad_edge=True,
    )

    for h in headers:
        no_wrap = h in (
            "Active",
            "Name",
            "Google Email",
            "gcloud Config",
            "MCPs",
            "Hooks",
            "Snapshot ID",
            "Timestamp",
            "Trigger",
            "Files Count",
            "Trash ID",
            "Original Profile Name",
            "Deleted At",
        )
        table.add_column(h, no_wrap=no_wrap)

    for row in rows:
        formatted_row = []
        for cell in row:
            if isinstance(cell, str) and "\033[" in cell:
                formatted_row.append(Text.from_ansi(cell))
            elif isinstance(cell, Text):
                formatted_row.append(cell)
            else:
                formatted_row.append(str(cell))
        table.add_row(*formatted_row)

    console.print(table)


def confirm(prompt_text: str, default: bool = False) -> bool:
    """Ask user for yes/no confirmation using Rich Prompt."""
    if not sys.stdin.isatty():
        return default

    try:
        return Confirm.ask(prompt_text, default=default, console=console)
    except (KeyboardInterrupt, EOFError):
        console.print()
        return False


def prompt_selection(prompt_text: str, choices: list[str], default_idx: int = 0) -> str:
    """Prompt user to select from a list of choices using Rich."""
    if not choices:
        raise ValueError("No choices provided")

    console.print(f"[bold]{prompt_text}[/bold]")
    for i, choice in enumerate(choices, 1):
        marker = " [dim](default)[/dim]" if (i - 1) == default_idx else ""
        console.print(f"  [cyan]{i}[/cyan]) {choice}{marker}")

    default_choice = str(default_idx + 1)
    while True:
        try:
            val = input(f"Enter choice [1-{len(choices)}] (default {default_choice}): ").strip()
            if not val:
                return choices[default_idx]
            idx = int(val) - 1
            if 0 <= idx < len(choices):
                return choices[idx]
            print_warning(f"Please enter a number between 1 and {len(choices)}.")
        except ValueError:
            print_warning("Invalid input. Please enter a valid number.")
        except (KeyboardInterrupt, EOFError):
            console.print()
            return choices[default_idx]
