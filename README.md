# Antigravity CLI Multi-Profile Manager (`agy-multiprofile`)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A seamless, safety-first CLI with an inline interactive selector and Terminal User Interface (TUI) for **Google Antigravity** and **Gemini CLI** (`agy`).

Manage distinct profiles for **Work**, **Personal**, **Client Projects**, and **R&D** with complete isolation of configuration files, Model Context Protocol (MCP) servers, lifecycle hooks, plugins, model preferences, and Google accounts.

---

## Table of Contents

- [Why `agy-multiprofile`?](#why-agy-multiprofile)
- [Key Features](#key-features)
- [Interactive Inline Selector](#interactive-inline-selector)
- [Terminal User Interface (TUI)](#terminal-user-interface-tui)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Managed State Matrix](#managed-state-matrix)
- [CLI Reference](#cli-reference)
- [Safety & Reliability Guarantees](#safety--reliability-guarantees)
- [Configuration & Environment Variables](#configuration--environment-variables)
- [Architecture & Storage Layout](#architecture--storage-layout)
- [Development & Testing](#development--testing)
- [License](#license)

---

## Why `agy-multiprofile`?

Google Antigravity (`agy`) and Gemini CLI store user settings, approved workspace permissions, installed plugins, lifecycle hooks, and global MCP servers in a single global directory (`~/.gemini/`) and OS keyring.

When juggling multiple client projects or switching between work and personal Google accounts:
- Sensitive MCP servers and API tokens can leak across client boundaries.
- Re-authenticating resets authentication tokens and overwrites account states.
- Model selections, approved command execution rules, and custom hooks get mixed up.

`agy-multiprofile` solves this by introducing an isolated profile vault (`~/.config/agy-profile/`). It swaps configuration environments in milliseconds using **atomic filesystem transactions**, synchronizes credentials directly with the **OS Keyring**, preserves workspace permissions, and launches `agy` automatically.

---

## Key Features

- ⚡ **Inline Interactive Selector**: Launch `agy-profile` for an immediate terminal selection prompt. Arrow keys, hotkeys, instant search, and instant launch.
- 🖥️ **Rich Terminal User Interface (TUI)**: Full dashboard powered by Textual with real-time profile details, MCP inspector, and management modals (`agy-profile tui`).
- 🔒 **Native OS Keyring Synchronization**: Automatically isolates and swaps OAuth credentials in Linux Secret Service, macOS Keychain, and Windows Credential Manager.
- 🛡️ **Zero-Downtime Atomic Transactions**: File swaps use atomic POSIX replacements with automated transaction rollback if any step fails.
- 💼 **Google Account & `gcloud` Alignment**: Automatically updates `google_accounts.json` and syncs active Google Cloud SDK configurations (`gcloud config set account` / `gcloud config configurations activate`).
- 🤝 **Workspace Trust Preservation**: Maintains workspace permissions across profile switches so you are not re-prompted to trust project directories.
- 📦 **Safety Snapshots & Soft-Delete Trash**: Auto-creates rolling recovery backups before every switch. Deletions are sent to trash and can be restored anytime.
- 🩺 **Built-in Doctor Diagnostics**: Runs automated validation on JSON syntax, filesystem permissions, process locks, and binary availability (`agy-profile doctor`).
- 🚚 **Portable Profile Archives**: Export and import self-contained profiles as ZIP archives for backup or team sharing (`export` / `import`).

---

## Interactive Inline Selector

Running `agy-profile` directly in your terminal launches a fast, inline terminal prompt:

```text
✦ Antigravity Profile Switcher
Select a profile to activate & launch agy:

❯ 1. ● default (active)   (vbatecan@gmail.com)   [3 MCPs]  (active) - Default live profile
  2. ○ work               (work@corp.com)        [6 MCPs]           - Work projects & enterprise MCPs
  3. ○ client-acme        (dev@client.io)        [2 MCPs]           - Acme Corp isolated env
  4. + Create new profile...

Press ↑/↓ to navigate, 1-4 to select, Enter to confirm, Esc/q to cancel
```

### Fast Controls

| Key | Action |
| :--- | :--- |
| **`↑` / `↓`** or **`k` / `j`** | Move selection cursor up/down |
| **`1` – `9`** | Jump directly to profile number and activate |
| **`Enter`** | Activate selected profile and immediately launch `agy` |
| **`s`** | Switch profile without launching `agy` (or pass `--no-launch`) |
| **`c`** | Create a new profile interactively |
| **`d`** | Move highlighted profile to soft-delete trash |
| **`Esc` / `q`** | Cancel and exit without making changes |
| **`-- [args...]`** | Pass trailing arguments directly to `agy` (e.g. `agy-profile -- --model gemini-2.5-pro`) |

---

## Terminal User Interface (TUI)

For a richer management console, launch the Textual-powered TUI dashboard:

```bash
agy-profile tui
```

```text
┌─ ◆ Antigravity Profiles ────────────────────────────────────────── Active: ● default ─┐
│                                                                                        │
│ PROFILES                                     PROFILE SUMMARY                           │
│ ┌──────────────────────────────────────────┐ ┌───────────────────────────────────────┐ │
│ │ ● default (active)                       │ │ Profile: work                         │ │
│ │ ○ work                                   │ │ Description: Enterprise client stack  │ │
│ │ ○ personal                               │ │ Google Account: work@company.com      │ │
│ │ ○ sandbox-exp                            │ │ gcloud Config:  corp-prod             │ │
│ │                                          │ │                                       │ │
│ │                                          │ │ Configured MCP Servers (4):           │ │
│ │                                          │ │  • postgres: npx -y @mcp/server-pg    │ │
│ │                                          │ │  • github:   npx -y @mcp/server-gh    │ │
│ └──────────────────────────────────────────┘ └───────────────────────────────────────┘ │
│                                                                                        │
└─ Enter Select & Launch │ s Switch only │ c New │ d Delete │ r Rename │ q Quit ─────────┘
```

---

## Installation

### Method 1: Using `uv` (Recommended)

```bash
# Install directly as a global CLI tool
uv tool install agy-multiprofile

# Or install from local repository
git clone https://github.com/your-username/agy-multiprofile.git
cd agy-multiprofile
uv tool install .
```

### Method 2: Using `pipx`

```bash
pipx install agy-multiprofile
# Or from local source:
pipx install .
```

### Method 3: Standard `pip`

```bash
pip install -e .
```

---

## Quick Start

### 1. Interactive Switch and Launch
```bash
agy-profile
```

### 2. Create Profiles
```bash
# Create a work profile cloned from your current live ~/.gemini settings
agy-profile create work --email "developer@work.com" --gcloud "work-config" --clone-current

# Create a clean client profile
agy-profile create client-alpha --email "contractor@client.com" --desc "Client Alpha engagement"

# Clone an existing profile
agy-profile clone work work-secondary --desc "Secondary work profile"
```

### 3. Direct CLI Switching
```bash
# Switch to 'work' and immediately launch Antigravity CLI
agy-profile switch work --launch

# Switch profile only (without launching agy)
agy-profile switch work

# Pass arguments directly to agy
agy-profile -- --continue
```

### 4. Inspect Current Profile & Health
```bash
# Display active profile status, MCP count, and live Google account
agy-profile current

# Run system diagnostic checks
agy-profile doctor
```

---

## Managed State Matrix

When switching profiles, `agy-multiprofile` coordinates and isolates the following components:

| Component | Live Path (`~/.gemini/`) | Profile Storage | Description |
| :--- | :--- | :--- | :--- |
| **CLI Settings** | `antigravity-cli/settings.json` | `cli_settings.json` | Model selection, auto-run permissions, editor settings |
| **Global Settings** | `settings.json` | `settings.json` | Gateway authentication and telemetry options |
| **MCP Servers** | `config/mcp_config.json` | `mcp_config.json` | Configured Model Context Protocol servers & env vars |
| **MCP OAuth** | `antigravity-cli/mcp_oauth_tokens.json` | `mcp_oauth.json` | OAuth tokens for MCP servers |
| **Global Hooks** | `config/hooks.json` | `hooks.json` | Global agent lifecycle hooks |
| **CLI Hooks** | `antigravity-cli/hooks.json` | `cli_hooks.json` | CLI lifecycle event triggers |
| **Plugins Config** | `config/config.json` | `config.json` | Plugin enablement states and settings |
| **Google Account** | `google_accounts.json` | `google_accounts.json` | Active Google account email and account history |
| **Trusted Folders** | `trustedFolders.json` | `trusted_folders.json` | Workspace security permissions & trusted folders |
| **OS Keyring** | System Secret Store | `auth_token.json` (0600) | Active OAuth session token in OS Keyring |
| **gcloud SDK** | `~/.config/gcloud/` | `profile.json` metadata | Active `gcloud` account & configuration |

---

## CLI Reference

### `agy-profile [options] [-- agy-args...]`
Invoking `agy-profile` with no subcommands opens the inline interactive selector.

- `--no-launch`: Switch or select without launching `agy`.
- `--version`: Show version.

```bash
# Launch interactive selector and start agy with custom flags
agy-profile -- --verbose
```

---

### `agy-profile list` (alias: `ls`)
Lists all profiles in the vault with metadata, active indicators, and MCP counts.

```bash
agy-profile list
```

---

### `agy-profile current`
Displays detailed information about the currently active profile, live Google account, and configured MCP servers.

```bash
agy-profile current
```

---

### `agy-profile switch <name> [options]` (alias: `use`)
Switches active profile to `<name>`. If `<name>` is omitted, opens the interactive selector.

**Options:**
- `--dry-run`: Simulate switch and display all configuration diffs without writing to disk.
- `--launch`: Automatically launch `agy` upon successful switch.
- `--no-launch`: Suppress automatic launch.
- `--save-current`: Sync modifications in current session back to source profile before switching.
- `--skip-sync`: Skip syncing live modifications back to source profile (default).
- `--force`: Force switch even if active `agy` processes are detected.

```bash
# Preview changes before switching
agy-profile switch work --dry-run

# Switch and launch agy
agy-profile switch work --launch
```

---

### `agy-profile create <name> [options]`
Creates a new profile in the vault.

**Options:**
- `--desc "<text>"`: Description of the profile.
- `--email "<email>"`: Associated Google account email.
- `--gcloud "<config>"`: Associated `gcloud` configuration name.
- `--clone-current`: Initialize profile by copying live `~/.gemini` configuration.
- `--from <profile>`: Clone from an existing profile in the vault.

```bash
agy-profile create client-corp --email "dev@client.com" --clone-current
```

---

### `agy-profile clone <source> <dest> [--desc "<text>"]`
Clones an existing profile to a new destination profile.

```bash
agy-profile clone work work-feature-branch --desc "Testing experimental MCPs"
```

---

### `agy-profile delete <name> [-y/--yes]` (alias: `rm`)
Safely soft-deletes a profile by moving it to `trash/`.

```bash
agy-profile delete old-profile
```

---

### `agy-profile rename <old_name> <new_name>`
Renames an existing profile in the vault.

```bash
agy-profile rename personal personal-primary
```

---

### `agy-profile sync [--dry-run]`
Explicitly captures the current live `~/.gemini` state and updates the active profile in the vault.

```bash
agy-profile sync
agy-profile sync --dry-run
```

---

### `agy-profile diff [profile1] [profile2]`
Compares configuration differences between profiles or against live state.

- `agy-profile diff`: Diff active profile against live `~/.gemini`.
- `agy-profile diff work`: Diff `work` profile against live `~/.gemini`.
- `agy-profile diff work personal`: Diff `work` profile against `personal` profile.

---

### `agy-profile backups`
Lists all rolling safety snapshots in `~/.config/agy-profile/backups/`.

```bash
agy-profile backups
```

---

### `agy-profile restore [snapshot_id] [-y/--yes]`
Restores the live environment from a previous safety snapshot.

```bash
agy-profile restore
agy-profile restore snap_20260821_143000_switch_default_to_work -y
```

---

### `agy-profile trash` & `restore-trash [trash_id] [--name <new_name>]`
Inspect and restore soft-deleted profiles.

```bash
# List items in trash
agy-profile trash

# Restore by trash ID
agy-profile restore-trash 20260821_143000_old-profile --name restored-profile
```

---

### `agy-profile export <name> <output_file.zip>`
Exports a profile into a portable ZIP archive.

```bash
agy-profile export work ~/backups/work-profile.zip
```

---

### `agy-profile import <input_file.zip> [--name <profile_name>]`
Imports a profile archive into the vault.

```bash
agy-profile import ~/backups/work-profile.zip --name work-restored
```

---

### `agy-profile doctor`
Executes comprehensive diagnostics on:
- Vault integrity and manifest validity
- Profile JSON file integrity and syntax
- `~/.gemini` permissions and directory state
- Antigravity CLI binary (`agy`) detection on PATH
- OS Keyring integration status
- Google Cloud SDK CLI (`gcloud`) detection
- Running Antigravity processes & brain locks

```bash
agy-profile doctor
```

---

## Safety & Reliability Guarantees

1. **POSIX Atomic Replacement**: Files are written to temporary staging files first and swapped using `os.replace`. No partial writes or corrupted files on crash.
2. **Transaction Rollback Engine**: The `TransactionContext` tracks all file replacements. If an error occurs midway through a switch, all original files are restored automatically.
3. **Inter-Process Locking**: An exclusive file lock (`fcntl.flock` / `msvcrt`) prevents multiple processes from modifying profiles concurrently.
4. **Rolling Safety Snapshots**: An immutable snapshot is saved to `backups/` before any switch. Up to 25 rolling snapshots are maintained automatically.
5. **Soft Deletions**: Deleting a profile moves its files to `trash/` with metadata. Profiles are never deleted permanently by accident.
6. **Keyring Credential Isolation**: OAuth tokens stored on disk are restricted to owner-only permissions (`chmod 0600`). Fresh profiles cleanly wipe the active OS keyring entry to prevent credential leakage.
7. **Workspace Trust Preservation**: Workspace approval entries are preserved across fresh profiles so you don't face repeated trust security dialogs.

---

## Configuration & Environment Variables

You can customize `agy-multiprofile` using the following environment variables:

| Variable | Default | Description |
| :--- | :--- | :--- |
| `AGY_PROFILE_HOME` | `~/.config/agy-profile` | Path to the profile vault storage directory |
| `GEMINI_HOME` | `~/.gemini` | Path to the Gemini / Antigravity live configuration root |
| `CLOUDSDK_CONFIG` | `~/.config/gcloud` | Path to Google Cloud SDK configuration directory |
| `AGY_BIN` | Auto-detected | Explicit path to the `agy` / `antigravity` executable |
| `AGY_NO_LAUNCH` | `0` | Set to `1` or `true` to disable automatic launching of `agy` |
| `AGY_KEYRING_DISABLED` | `0` | Set to `1` to bypass OS Keyring operations |

---

## Architecture & Storage Layout

```text
~/.config/agy-profile/                     ~/.gemini/ (Live Configuration)
├── manifest.json                         ├── settings.json
├── .lock                                 ├── google_accounts.json
├── profiles/                             ├── trustedFolders.json
│   ├── default/                          ├── antigravity-cli/
│   │   ├── profile.json                  │   ├── settings.json
│   │   ├── cli_settings.json             │   ├── hooks.json
│   │   ├── settings.json                 │   └── mcp_oauth_tokens.json
│   │   ├── mcp_config.json               └── config/
│   │   ├── mcp_oauth.json                    ├── mcp_config.json
│   │   ├── hooks.json                        ├── hooks.json
│   │   ├── cli_hooks.json                    └── config.json
│   │   ├── config.json
│   │   ├── google_accounts.json          OS Keyring (Secret Service / Keychain)
│   │   ├── trusted_folders.json          └── service: "gemini", username: "antigravity"
│   │   └── auth_token.json (0600)
│   └── work/
│       └── ...
├── backups/
│   ├── snap_20260821_120000_switch_.../
│   └── snap_20260821_143000_switch_.../
└── trash/
    └── 20260821_150000_deprecated-profile/
```

---

## Development & Testing

### Setting Up Development Environment

```bash
git clone https://github.com/your-username/agy-multiprofile.git
cd agy-multiprofile

# Create virtual environment and install dev dependencies
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### Running Test Suite

```bash
# Run pytest with async and coverage
uv run --with pytest --with pytest-asyncio pytest tests/ -v

# Or directly in active venv:
pytest tests/ -v
```

### Code Formatting & Quality

```bash
# Format code
black src tests
ruff check src tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).
