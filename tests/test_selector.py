"""
Tests for inline Codex / Claude Code style interactive selector.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from agy_multiprofile.cli import interactive_switch
from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.switcher import ProfileSwitcher
from agy_multiprofile.utils.selector import _read_key, inline_select


def test_read_key_sequences(monkeypatch):
    test_cases = [
        (b"\x1b[A", "up"),
        (b"\x1bOA", "up"),
        (b"\x1b[B", "down"),
        (b"\x1bOB", "down"),
        (b"\x1b[C", "right"),
        (b"\x1b[D", "left"),
        (b"\x1b[H", "home"),
        (b"\x1b[F", "end"),
        (b"\x1b[5~", "page_up"),
        (b"\x1b[6~", "page_down"),
        (b"\x1b[Z", "shift_tab"),
        (b"\r", "enter"),
        (b"\n", "enter"),
        (b"\x03", "cancel"),
        (b"\x04", "cancel"),
        (b"k", "k"),
        (b"j", "j"),
        (b"1", "1"),
        (b"q", "q"),
    ]

    for raw_bytes, expected in test_cases:
        monkeypatch.setattr("os.read", lambda fd, n: raw_bytes)
        assert _read_key(0) == expected


def test_read_key_lone_escape(monkeypatch):
    monkeypatch.setattr("os.read", lambda fd, n: b"\x1b")
    monkeypatch.setattr("select.select", lambda r, w, x, timeout: ([], [], []))
    assert _read_key(0) == "escape"


def test_read_key_split_escape_sequence(monkeypatch):
    calls = [b"\x1b", b"[A"]

    def fake_read(fd, n):
        return calls.pop(0)

    monkeypatch.setattr("os.read", fake_read)
    monkeypatch.setattr("select.select", lambda r, w, x, timeout: ([0], [], []))
    assert _read_key(0) == "up"


def test_inline_select_interactive_arrows(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.fileno", lambda: 0)
    monkeypatch.setattr("termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("tty.setcbreak", lambda fd: None, raising=False)
    monkeypatch.setattr("tty.setraw", lambda fd: None, raising=False)

    # Sequence of keypresses: down -> down -> up -> enter
    keys = ["down", "down", "up", "enter"]
    key_iter = iter(keys)
    monkeypatch.setattr("agy_multiprofile.utils.selector._read_key", lambda fd: next(key_iter))

    options = ["Profile A", "Profile B", "Profile C"]
    # Starting at 0: down -> 1, down -> 2, up -> 1, enter -> returns 1
    idx = inline_select("Select Profile", "Choose:", options, default_index=0)
    assert idx == 1


def test_inline_select_interactive_cancel(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.fileno", lambda: 0)
    monkeypatch.setattr("termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("tty.setcbreak", lambda fd: None, raising=False)
    monkeypatch.setattr("tty.setraw", lambda fd: None, raising=False)

    keys = ["down", "escape"]
    key_iter = iter(keys)
    monkeypatch.setattr("agy_multiprofile.utils.selector._read_key", lambda fd: next(key_iter))

    options = ["Profile A", "Profile B"]
    idx = inline_select("Select Profile", "Choose:", options, default_index=0)
    assert idx is None


def test_inline_select_interactive_digits(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.fileno", lambda: 0)
    monkeypatch.setattr("termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("tty.setcbreak", lambda fd: None, raising=False)
    monkeypatch.setattr("tty.setraw", lambda fd: None, raising=False)

    keys = ["3", "enter"]
    key_iter = iter(keys)
    monkeypatch.setattr("agy_multiprofile.utils.selector._read_key", lambda fd: next(key_iter))

    options = ["Profile A", "Profile B", "Profile C"]
    idx = inline_select("Select Profile", "Choose:", options, default_index=0)
    assert idx == 2


def test_inline_select_non_tty_fallback(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")

    options = ["default (active)", "work", "personal"]
    idx = inline_select("Select Profile", "Choose from list:", options, default_index=0)
    assert idx == 1


def test_inline_select_cancel(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda prompt="": "")

    options = ["default", "work"]
    idx = inline_select("Select Profile", "Choose from list:", options, default_index=0)
    assert idx == 0


def test_interactive_switch_existing_profile(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    store.create_profile("work", email="work@company.com")
    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)
    # Select option 2 (which is 'work')
    monkeypatch.setattr("builtins.input", lambda prompt="": "2")

    ret = interactive_switch(store, switcher)
    assert ret == 0
    manifest = store.get_manifest()
    assert manifest.active_profile == "work"
    captured = capsys.readouterr()
    assert "Switched active profile to 'work'" in captured.out


def test_inline_select_delete_action(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.fileno", lambda: 0)
    monkeypatch.setattr("termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("tty.setcbreak", lambda fd: None, raising=False)

    keys = ["down", "delete"]
    key_iter = iter(keys)
    monkeypatch.setattr("agy_multiprofile.utils.selector._read_key", lambda fd: next(key_iter))

    options = ["Profile A", "Profile B"]
    action, idx = inline_select("Select", "Choose:", options, default_index=0, return_action=True)
    assert action == "delete"
    assert idx == 1


def test_inline_select_create_action(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    monkeypatch.setattr("sys.stdin.fileno", lambda: 0)
    monkeypatch.setattr("termios.tcgetattr", lambda fd: [])
    monkeypatch.setattr("termios.tcsetattr", lambda fd, when, attrs: None)
    monkeypatch.setattr("tty.setcbreak", lambda fd: None, raising=False)

    keys = ["create"]
    key_iter = iter(keys)
    monkeypatch.setattr("agy_multiprofile.utils.selector._read_key", lambda fd: next(key_iter))

    options = ["Profile A", "+ Create new profile..."]
    action, idx = inline_select("Select", "Choose:", options, default_index=0, return_action=True)
    assert action == "create"
    assert idx is None


def test_interactive_switch_delete_flow(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    store.create_profile("to_delete", email="del@test.com")
    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    # 1. First input: 'd 2' (delete option 2 'to_delete')
    # 2. Second input: 'y' (confirm delete)
    # 3. Third input: '' (cancel / exit)
    inputs = iter(["d 2", "y", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    ret = interactive_switch(store, switcher)
    assert ret == 0
    assert not store.profile_exists("to_delete")
    assert len(store.list_trash()) == 1
    captured = capsys.readouterr()
    assert "moved to trash" in captured.out


def test_interactive_switch_create_flow_does_not_switch(monkeypatch, temp_vault_home: Path, temp_gemini_home: Path, capsys):
    store = ProfileStore(root_dir=temp_vault_home, gemini_home=temp_gemini_home)
    store.create_profile("default", clone_from_live=True)
    switcher = ProfileSwitcher(store=store, gemini_home=temp_gemini_home)

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stdout.isatty", lambda: False)

    # 1. Option '2' (Create new profile...)
    # 2. Name: 'new_prof'
    # 3. Email: 'new@company.com'
    # 4. Desc: 'New test profile'
    # 5. Clone: 'n'
    # 6. Next menu input: '' (exit/select current default)
    inputs = iter(["2", "new_prof", "new@company.com", "New test profile", "n", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))

    ret = interactive_switch(store, switcher)
    assert ret == 0
    assert store.profile_exists("new_prof")
    
    # Verify active profile was NOT automatically switched
    manifest = store.get_manifest()
    assert manifest.active_profile == "default"

    captured = capsys.readouterr()
    assert "Profile 'new_prof' created successfully." in captured.out


