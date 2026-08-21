# CLAUDE.md — Claude Code Quick Reference

Multi-profile manager and credential switcher for Google Antigravity & Gemini CLI (`agy`).

## Fast Commands

```bash
# Setup virtual environment
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"

# Run full test suite
uv run --with pytest --with pytest-asyncio pytest tests/ -v

# Run single test
uv run --with pytest --with pytest-asyncio pytest tests/test_switcher.py -k test_switch_profile_clean -v

# Run with test coverage
uv run --with pytest --with pytest-asyncio --with pytest-cov pytest --cov=agy_multiprofile tests/

# Lint & type check
ruff check src/ tests/
black --check src/ tests/
```

---

## Core Architecture

- **CLI Dispatcher** (`src/agy_multiprofile/cli.py`): Argparse parser, command handlers, inline selector runner.
- **Vault Storage** (`src/agy_multiprofile/core/storage.py`): Manages `~/.config/agy-profile/` (`profiles/`, `backups/`, `trash/`, `manifest.json`).
- **Switcher Engine** (`src/agy_multiprofile/core/switcher.py`): Dry-run planner, transaction runner, and rollback coordinator.
- **File Sync** (`src/agy_multiprofile/core/sync.py`): Bidirectional sync between `~/.gemini/` and vault.
- **Keyring Manager** (`src/agy_multiprofile/core/keyring.py`): Native OS Keyring integration (Linux `secret-tool`, macOS `security`, Windows `PasswordVault`).
- **Auth Sync** (`src/agy_multiprofile/core/auth.py`): Keyring tokens, `google_accounts.json`, and `gcloud` CLI alignment.
- **Process Launcher** (`src/agy_multiprofile/core/launcher.py`): Discovers `agy` binary and performs POSIX `os.execvp` process replacement.
- **TUI Dashboard** (`src/agy_multiprofile/tui/app.py`): Full Textual application with screens and widgets.
- **Diagnostics** (`src/agy_multiprofile/core/doctor.py`): Health checks and validation engine.
- **Atomic Utilities** (`src/agy_multiprofile/utils/atomic.py`): `atomic_write_json`, `atomic_copy_file`, `TransactionContext`.

---

## Critical Safety Invariants

1. **Zero Direct Overwrites**: Always use `atomic_write_json` or `atomic_copy_file` with staging `.tmp_*` files and `os.replace`.
2. **Transaction Rollbacks**: Multi-file switch operations must run inside `with TransactionContext() as tx:`. Unhandled exceptions automatically trigger rollbacks.
3. **Inter-Process Lock**: Mutating operations must acquire `InterProcessLock(store.root_dir)`.
4. **Soft Delete**: Profiles are moved to `trash/` with `.trash_meta.json`. Never delete permanently in standard workflows.
5. **Safety Backups**: Always create a snapshot in `backups/` before modifying live configuration.
6. **Keyring Permissions**: `auth_token.json` files must be saved with mode `0o600`.
7. **Workspace Trust**: Preserve `trustedWorkspaces` and `trustedFolders.json` across new profile initializations.

---

## Code Style Rules

- Python `>=3.10` standard annotations (`list[str]`, `dict[str, Any]`, `Path | None`).
- Every module starts with `from __future__ import annotations`.
- Use dataclasses for schema models with `.to_dict()` and `.from_dict()`.
- Standard library first: keep `core/` and `utils/` zero-dependency where practical (Textual & Rich for UI only).
