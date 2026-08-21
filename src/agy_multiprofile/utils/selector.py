"""
Lightweight, elegant terminal interactive selector powered by Rich.
"""

from __future__ import annotations

import os
import select
import sys
from typing import Sequence

from rich import box
from rich.console import Group, RenderableType
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agy_multiprofile.utils.console import console


def _read_key(fd: int) -> str:
    """Read a single keypress or escape sequence from standard input."""
    try:
        data = os.read(fd, 32)
    except (OSError, EOFError):
        return "cancel"

    if not data:
        return "cancel"

    # If data is lone ESC (0x1b), check if more bytes are immediately pending (escape sequence)
    if data == b"\x1b":
        r, _, _ = select.select([fd], [], [], 0.05)
        if r:
            try:
                more = os.read(fd, 31)
                data += more
            except OSError:
                pass
        else:
            return "escape"

    # Match escape sequences
    if data in (b"\x1b[A", b"\x1bOA", b"\x1b[1;2A", b"\x1b[1;5A"):
        return "up"
    elif data in (b"\x1b[B", b"\x1bOB", b"\x1b[1;2B", b"\x1b[1;5B"):
        return "down"
    elif data in (b"\x1b[C", b"\x1bOC", b"\x1b[1;2C", b"\x1b[1;5C"):
        return "right"
    elif data in (b"\x1b[D", b"\x1bOD", b"\x1b[1;2D", b"\x1b[1;5D"):
        return "left"
    elif data in (b"\x1b[H", b"\x1b[1~", b"\x1bOH", b"\x1b[7~"):
        return "home"
    elif data in (b"\x1b[F", b"\x1b[4~", b"\x1bOF", b"\x1b[8~"):
        return "end"
    elif data in (b"\x1b[3~",):
        return "delete"
    elif data in (b"\x1b[5~",):
        return "page_up"
    elif data in (b"\x1b[6~",):
        return "page_down"
    elif data in (b"\x1b[Z",):
        return "shift_tab"
    elif data == b"\x1b":
        return "escape"
    elif data in (b"\r", b"\n"):
        return "enter"
    elif data in (b"\x03", b"\x04"):  # Ctrl+C or Ctrl+D
        return "cancel"
    elif data == b"\t":
        return "tab"
    elif data in (b"\x7f", b"\x08"):
        return "backspace"
    elif data in (b"d", b"D", b"x", b"X"):
        return "delete"
    elif data in (b"c", b"C", b"n", b"N"):
        return "create"

    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def inline_select(
    title: str,
    subtitle: str,
    options: Sequence[str],
    default_index: int = 0,
    return_action: bool = False,
) -> Any:
    """
    Renders an inline, elegant interactive selection prompt styled with Rich.
    If return_action is False, returns selected index (int) or None.
    If return_action is True, returns tuple of (action_name, index | None).
    """
    if not options:
        return ("cancel", None) if return_action else None

    # Fallback for non-interactive / non-TTY environments
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        console.print(f"[bold cyan]✦ {title}[/bold cyan]")
        if subtitle:
            console.print(f"[dim]{subtitle}[/dim]")
        for i, opt in enumerate(options, 1):
            if isinstance(opt, str) and "[" in opt and "]" in opt:
                try:
                    console.print(f"  {i}. ", Text.from_markup(opt))
                except Exception:
                    console.print(f"  {i}. {opt}")
            else:
                console.print(f"  {i}. {opt}")
        try:
            val = input(f"Select option [1-{len(options)}]: ").strip()
            if not val:
                return ("select", default_index) if return_action else default_index
            if val.startswith("d ") or val.startswith("delete "):
                parts = val.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    del_idx = int(parts[1]) - 1
                    if 0 <= del_idx < len(options):
                        return ("delete", del_idx) if return_action else None
            idx = int(val) - 1
            if 0 <= idx < len(options):
                return ("select", idx) if return_action else idx
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
        return ("cancel", None) if return_action else None

    current_idx = max(0, min(default_index, len(options) - 1))
    num_options = len(options)

    def render_menu(idx: int) -> RenderableType:
        grid = Table.grid(padding=(0, 1))
        grid.add_column("pointer", justify="right", width=2)
        grid.add_column("number", justify="right")
        grid.add_column("content")

        for i, opt in enumerate(options):
            num_str = f"{i + 1}."
            is_selected = i == idx

            if isinstance(opt, Text):
                opt_text = opt.copy()
            elif "\033[" in opt:
                opt_text = Text.from_ansi(opt)
            elif "[" in opt and "]" in opt:
                try:
                    opt_text = Text.from_markup(opt)
                except Exception:
                    opt_text = Text(opt)
            else:
                opt_text = Text(opt)

            if is_selected:
                pointer = Text("❯", style="bold cyan")
                num_text = Text(num_str, style="bold cyan")
                opt_text.stylize("bold")
            else:
                pointer = Text(" ")
                num_text = Text(num_str, style="dim")

            grid.add_row(pointer, num_text, opt_text)

        footer_text = Text()
        footer_text.append("↑/↓ / j/k", style="bold")
        footer_text.append(": navigate  •  ", style="dim")
        footer_text.append("Enter", style="bold")
        footer_text.append(": select & launch  •  ", style="dim")
        footer_text.append("d", style="bold red")
        footer_text.append(": delete  •  ", style="dim")
        footer_text.append("c", style="bold cyan")
        footer_text.append(": new  •  ", style="dim")
        footer_text.append("Esc/q", style="bold")
        footer_text.append(": cancel", style="dim")

        elements = []
        if subtitle:
            elements.append(Text(subtitle, style="dim"))
            elements.append(Text(""))
        elements.append(grid)
        elements.append(Text(""))
        elements.append(footer_text)

        panel_content = Group(*elements)

        return Panel(
            panel_content,
            title=f"[bold cyan]✦ {title}[/bold cyan]",
            title_align="left",
            border_style="cyan",
            box=box.ROUNDED,
            padding=(0, 1),
        )

    # Prepare terminal in cbreak mode
    old_settings = None
    fd = None
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setcbreak(fd)
    except Exception:
        pass

    try:
        with Live(render_menu(current_idx), console=console, auto_refresh=False, transient=True) as live:
            while True:
                key = _read_key(fd if fd is not None else 0)
                if key in ("up", "k", "shift_tab", "page_up"):
                    current_idx = (current_idx - 1) % num_options
                    live.update(render_menu(current_idx), refresh=True)
                elif key in ("down", "j", "tab", "page_down"):
                    current_idx = (current_idx + 1) % num_options
                    live.update(render_menu(current_idx), refresh=True)
                elif key in ("home",):
                    current_idx = 0
                    live.update(render_menu(current_idx), refresh=True)
                elif key in ("end", "G"):
                    current_idx = num_options - 1
                    live.update(render_menu(current_idx), refresh=True)
                elif key == "delete":
                    return ("delete", current_idx) if return_action else current_idx
                elif key == "create":
                    return ("create", None) if return_action else (num_options - 1)
                elif key.isdigit():
                    digit = int(key)
                    if 1 <= digit <= num_options:
                        current_idx = digit - 1
                        live.update(render_menu(current_idx), refresh=True)
                elif key == "enter":
                    return ("select", current_idx) if return_action else current_idx
                elif key in ("escape", "q", "Q", "cancel"):
                    return ("cancel", None) if return_action else None
    except (Exception, KeyboardInterrupt):
        return ("cancel", None) if return_action else None
    finally:
        if old_settings is not None and fd is not None:
            try:
                import termios

                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            except Exception:
                pass
