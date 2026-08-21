# GEMINI.md — Google Antigravity & Gemini CLI Assistant Context

This document provides operational context and guidelines for **Google Antigravity** and **Gemini CLI** (`agy`) AI assistants working in this repository.

---

## 1. Context & Purpose

`agy-multiprofile` is the profile and account management tool for Google Antigravity (`agy`) and the Gemini CLI ecosystem. It enables zero-downtime switching between isolated developer profiles containing distinct configurations, Model Context Protocol (MCP) servers, lifecycle hooks, plugin settings, and Google authentication identities.

### Antigravity Configuration Topology Managed by this Tool

```text
~/.gemini/                                # GEMINI_HOME
├── settings.json                         # Global Gemini/Antigravity settings
├── google_accounts.json                  # Active Google account email & history
├── trustedFolders.json                   # Workspace security permissions
├── antigravity-cli/                      # Antigravity CLI specific directory
│   ├── settings.json                     # CLI settings (model, permissions, editor)
│   ├── hooks.json                        # CLI-specific event hooks
│   └── mcp_oauth_tokens.json             # MCP OAuth tokens
└── config/                               # Gemini system configuration
    ├── mcp_config.json                   # Global MCP server configurations
    ├── hooks.json                        # Global lifecycle hooks
    └── config.json                       # Plugins configuration & toggles
```

### OS Keyring Storage
- **Linux**: Secret Service (`secret-tool` targeting `service: gemini`, `username: antigravity`)
- **macOS**: Keychain (`security` targeting `-s gemini -a antigravity`)
- **Windows**: Windows Credential Manager (`PasswordVault` targeting `gemini` / `antigravity`)

---

## 2. Critical Guidelines for Antigravity Agents

### ⚠️ In-Session Safety Rule
When developing or testing in an active Antigravity session:
- **DO NOT** execute `agy-profile switch <name>` against the real `~/.gemini/` environment while active in a live agent session, as it will swap configuration files out from underneath the running process.
- **DO** use test fixtures or the `--dry-run` flag (`agy-profile switch <name> --dry-run`) to simulate profile switches safely.
- All unit and integration tests under `tests/` use isolated temporary directories for `gemini_home` and `vault_root`, and mock out keyring and `os.execvp` calls.

### 🛡️ Atomic File Mutation Standards
All writes to any configuration file inside `~/.gemini` or `~/.config/agy-profile` must go through:
1. `atomic_write_json(path, data)`: Staged write to sibling `.tmp_*` file followed by `os.replace`.
2. `TransactionContext()`: Reversible multi-file transaction block that automatically rolls back in case of an error.

### 🔑 Keyring Handling
- Credentials saved to disk in `auth_token.json` must be restricted to file mode `0o600` (`chmod 600`).
- Switching to a clean profile must clear the active keyring entry to prevent token bleed across Google accounts.

---

## 3. Codebase Structure & Key Modules

| Module | Location | Purpose |
| :--- | :--- | :--- |
| **CLI Dispatcher** | [`src/agy_multiprofile/cli.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/cli.py) | Argparse CLI entry point and subcommands |
| **Constants & Specs** | [`src/agy_multiprofile/core/constants.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/core/constants.py) | Path resolvers & `MANAGED_FILES` registry |
| **Vault Storage** | [`src/agy_multiprofile/core/storage.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/core/storage.py) | Vault directories, CRUD, snapshots, and soft-delete trash |
| **Switcher Engine** | [`src/agy_multiprofile/core/switcher.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/core/switcher.py) | Atomic switch execution and rollback coordinator |
| **Sync Manager** | [`src/agy_multiprofile/core/sync.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/core/sync.py) | Bidirectional synchronization between live state and vault |
| **OS Keyring** | [`src/agy_multiprofile/core/keyring.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/core/keyring.py) | Zero-dependency native OS Keyring bridge |
| **Auth & Accounts** | [`src/agy_multiprofile/core/auth.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/core/auth.py) | Google account & `gcloud` SDK synchronizer |
| **Launcher** | [`src/agy_multiprofile/core/launcher.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/core/launcher.py) | Binary discovery and process replacement via `os.execvp` |
| **Inline Selector** | [`src/agy_multiprofile/utils/selector.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/utils/selector.py) | Raw terminal ANSI interactive prompt |
| **TUI Application** | [`src/agy_multiprofile/tui/app.py`](file:///home/vbatecan/Projects/agy-multiprofile/src/agy_multiprofile/tui/app.py) | Textual full terminal dashboard |

---

## 4. Test Suite & Verification

The project includes an end-to-end test suite covering atomic writes, locking, keyring, switching, CLI parsing, doctor diagnostics, and TUI flows.

### Run All Tests
```bash
uv run --with pytest --with pytest-asyncio pytest tests/ -v
```

### Run Specific Test Suites
```bash
# Core switcher tests
uv run --with pytest --with pytest-asyncio pytest tests/test_switcher.py -v

# OS Keyring tests
uv run --with pytest --with pytest-asyncio pytest tests/test_keyring.py -v

# CLI parser tests
uv run --with pytest --with pytest-asyncio pytest tests/test_cli.py -v

# TUI asynchronous tests
uv run --with pytest --with pytest-asyncio pytest tests/test_tui.py -v
```

---

## 5. Environment Variables for Testing & Overrides

- `AGY_PROFILE_HOME`: Custom path for the profile vault root (default: `~/.config/agy-profile`).
- `GEMINI_HOME`: Custom path for live Gemini config directory (default: `~/.gemini`).
- `CLOUDSDK_CONFIG`: Custom path for Google Cloud SDK config (default: `~/.config/gcloud`).
- `AGY_BIN`: Path to `agy` binary override.
- `AGY_NO_LAUNCH`: Set to `1` to suppress automatic launching of `agy` during testing.
- `AGY_KEYRING_DISABLED`: Set to `1` to disable OS Keyring interaction in test runners or headless CI.
