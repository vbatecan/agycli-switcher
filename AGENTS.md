# AGENTS.md — Agent & Contributor Development Guide

This guide is for AI agents (Antigravity, Gemini CLI, Claude Code, Cursor, Copilot, Codex) and human developers working on the `agy-multiprofile` codebase.

---

## 1. Project Overview & Mission

`agy-multiprofile` is a high-reliability, zero-dataloss profile and credential switcher for Google Antigravity & Gemini CLI (`agy`). It enables instantaneous switching between different work, personal, and client profiles while maintaining complete isolation across:
- Antigravity CLI and Gemini global configuration files (`~/.gemini/`)
- Global Model Context Protocol (MCP) server definitions and OAuth tokens
- Lifecycle hooks and installed plugins
- Google account identity (`google_accounts.json`)
- System OS Keyring OAuth credentials (Linux Secret Service, macOS Keychain, Windows Credential Manager)
- Active Google Cloud SDK configurations (`gcloud`)

**Primary Directive**: Safety First. Configuration corruption or credential loss is catastrophic. All file operations must be atomic, reversible, and non-destructive.

---

## 2. Architecture & File Structure

```text
agy-multiprofile/
├── pyproject.toml                     # Build setup, dependencies (textual, rich), pytest config
├── README.md                          # Public user documentation and CLI manual
├── AGENTS.md                          # Agent development guidelines and architectural rules
├── GEMINI.md                          # Antigravity / Gemini CLI operational guide
├── CLAUDE.md                          # Claude Code reference guide
├── src/
│   └── agy_multiprofile/
│       ├── __init__.py                # Package root and version export (__version__ = "0.1.0")
│       ├── __main__.py                # CLI invocation entry point (python -m agy_multiprofile)
│       ├── cli.py                     # Argparse CLI interface and command dispatchers
│       ├── core/                      # Core business logic (Storage, Switcher, Keyring, Auth)
│       │   ├── __init__.py
│       │   ├── constants.py           # Path resolvers, MANAGED_FILES specs, default names
│       │   ├── models.py              # Data models (ProfileMetadata, Manifest, SnapshotMetadata, TrashMetadata)
│       │   ├── storage.py             # Profile vault manager, backups, trash, zip import/export
│       │   ├── switcher.py            # Atomic profile switcher engine, plan generator, transaction runner
│       │   ├── sync.py                # Bidirectional file syncer between ~/.gemini and profile vault
│       │   ├── keyring.py             # OS Keyring manager (Linux secret-tool, macOS security, Windows)
│       │   ├── auth.py                # Keyring capture/apply, google_accounts.json, gcloud integration
│       │   ├── doctor.py              # Health check diagnostic engine
│       │   ├── detector.py            # Process detector (psutil/pgrep fallback) & brain lock checks
│       │   ├── launcher.py            # agy binary discovery & process replacement (os.execvp)
│       │   └── lock.py                # Inter-process file locking (fcntl.flock / msvcrt)
│       ├── tui/                       # Terminal User Interface (Textual & Rich)
│       │   ├── __init__.py
│       │   ├── app.py                 # Main Textual App (ProfileManagerApp)
│       │   ├── style.tcss             # Textual CSS styling
│       │   ├── screens/               # Modals and dedicated screens
│       │   │   ├── __init__.py
│       │   │   ├── modals.py          # Create, Rename, Confirm Action modals
│       │   │   ├── doctor_screen.py   # Diagnostics report viewer
│       │   │   ├── backups_screen.py  # Backup snapshots browser & restore
│       │   │   ├── trash_screen.py    # Soft-deleted trash browser & restore
│       │   │   └── help_screen.py     # Hotkey help dialog
│       │   └── widgets/               # Custom Textual widgets
│       │       ├── __init__.py
│       │       ├── profile_list.py    # ProfileListView and ProfileListItem
│       │       └── profile_details.py # ProfileDetailsWidget (live MCP list & metadata)
│       └── utils/                     # Utility helpers
│           ├── __init__.py
│           ├── atomic.py              # atomic_write_json, atomic_copy_file, TransactionContext
│           ├── console.py             # Rich console formatting and prompt helpers
│           ├── diff_utils.py          # Dictionary deep diff & unified diff generators
│           ├── json_utils.py          # Safe JSON loader and serializer
│           └── selector.py            # Lightweight raw-mode terminal inline selector
└── tests/                             # Comprehensive pytest test suite (67+ tests)
    ├── conftest.py                    # Mock fixtures for gemini_home, vault_dir, keyring
    ├── test_atomic.py                 # Tests for atomic writes and rollback transactions
    ├── test_cli.py                    # Tests for CLI subcommands
    ├── test_diff.py                   # Tests for dict and unified diffing
    ├── test_doctor.py                 # Tests for health validation
    ├── test_keyring.py                # Tests for OS keyring token capture and switching
    ├── test_launcher.py               # Tests for agy binary discovery and execvp
    ├── test_lock.py                   # Tests for inter-process locking
    ├── test_selector.py               # Tests for interactive inline keypress reader
    ├── test_storage.py                # Tests for vault CRUD, trash, snapshots, zip import/export
    ├── test_switcher.py               # Tests for profile switching, dry runs, rollbacks
    └── test_tui.py                    # Tests for Textual async TUI navigation and modals
```

---

## 3. Critical Invariants & Safety Principles

When writing or modifying code in this repository, you MUST strictly uphold these invariants:

### 1. Atomic Filesystem Operations
- **NEVER** write directly to live configuration files or profile files with standard `open(..., "w")`.
- **ALWAYS** use `atomic_write_json()`, `atomic_write_text()`, or `atomic_copy_file()` from `agy_multiprofile.utils.atomic`.
- Atomic writes must write to a temporary sibling file (`.tmp_<random>`) in the same filesystem directory and commit via `os.replace`.

### 2. Transaction Rollback on Switch Failures
- The `ProfileSwitcher` executes all file replacements inside a `TransactionContext()`.
- If an exception occurs at any point (e.g. disk write failure, keyring error), `TransactionContext.__exit__` automatically rolls back all modified files to their original state before raising the exception.

### 3. Inter-Process Concurrency Safety
- Vault operations that modify profiles, manifest, backups, or trash MUST acquire `InterProcessLock(vault_root)` (`src/agy_multiprofile/core/lock.py`).
- This guarantees mutual exclusion across concurrent CLI invocations and background processes.

### 4. Non-Destructive Operations
- Profiles must **never** be permanently deleted via `rm -rf` in normal operations.
- `cmd_delete` and `store.soft_delete_profile()` must move the profile folder to `~/.config/agy-profile/trash/<timestamp>_<name>` and create `.trash_meta.json`.
- Before every profile switch, `store.create_snapshot()` must take a safety snapshot of the live configuration in `~/.config/agy-profile/backups/`.

### 5. Sensitive Credential Security
- OAuth tokens extracted from OS Keyring and saved into `auth_token.json` MUST be chmodded to `0o600` (owner read/write only).
- When switching to a newly created profile without an auth token, the OS Keyring entry (`service=gemini, username=antigravity`) must be cleared so `agy` prompts for a fresh authentication flow rather than bleeding previous credentials.

### 6. Workspace Trust Preservation
- When initializing a clean profile, existing `trustedWorkspaces` in `cli_settings.json` and `trustedFolders.json` should be preserved from live configuration so the user is not spammed with security trust prompts upon switching.

---

## 4. How to Extend the Codebase

### Adding a New Managed Configuration File
1. Open `src/agy_multiprofile/core/constants.py`.
2. Add a new `ManagedFileSpec` entry to `MANAGED_FILES`:
   ```python
   ManagedFileSpec(
       key="my_new_config",
       relative_live_path="config/my_new_config.json",
       profile_filename="my_new_config.json",
       description="Description of what this config controls",
       is_json=True,
   )
   ```
3. Update `capture_live_to_profile` / `create_profile` in `storage.py` if special default fallback initialization is required.
4. Add corresponding tests in `tests/test_storage.py` and `tests/test_switcher.py`.

### Adding a New CLI Subcommand
1. In `src/agy_multiprofile/cli.py`:
   - Implement the command handler `def cmd_<name>(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:`.
   - In `build_parser()`, add the subparser and configure arguments.
   - Set default func: `p_<name>.set_defaults(func=cmd_<name>)`.
2. Add test coverage in `tests/test_cli.py`.

### Adding a New TUI Modal or Screen
1. Create or update screen in `src/agy_multiprofile/tui/screens/`.
2. Inherit from `textual.screen.ModalScreen` or `textual.screen.Screen`.
3. Add keyboard shortcuts / bindings in `src/agy_multiprofile/tui/app.py`.
4. Add test coverage using Textual's async testing harness in `tests/test_tui.py`.

---

## 5. Development & Testing Commands

### Virtual Environment Setup
```bash
# Using uv (fastest)
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Running Tests
```bash
# Run all tests with pytest
uv run --with pytest --with pytest-asyncio pytest tests/ -v

# Run specific test module
uv run --with pytest --with pytest-asyncio pytest tests/test_switcher.py -v

# Run with test coverage report
uv run --with pytest --with pytest-asyncio --with pytest-cov pytest --cov=agy_multiprofile tests/
```

### Linting & Formatting
```bash
ruff check src/ tests/
black --check src/ tests/
```

---

## 6. Code Conventions

- **Typing**: Use standard Python 3.10+ annotations (`list[str]`, `dict[str, Any]`, `Path | None`). Always include `from __future__ import annotations` at the top of every file.
- **Dataclasses**: Use `@dataclass` for schema objects with explicit `to_dict()` and `from_dict()` serialization methods.
- **Error Handling**: Raise explicit exception types (`FileNotFoundError`, `FileExistsError`, `ValueError`, `RuntimeError`). Catch expected failures cleanly with user-friendly console messages.
- **No Heavy Third-Party Dependencies in Core**: Keep `src/agy_multiprofile/core/` and `src/agy_multiprofile/utils/` reliant on the standard library whenever possible. Rich and Textual are only used for CLI display and TUI presentation.
