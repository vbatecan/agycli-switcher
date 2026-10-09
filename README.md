# Antigravity CLI Multi-Profile Manager (`agy-multiprofile`)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Code Style](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

A seamless, safety-first CLI and interactive profile switcher for **Google Antigravity** and **Gemini CLI** (`agy`).

Manage distinct profiles for **Work**, **Personal**, **Client Projects**, and **R&D** with complete isolation of configuration files, Model Context Protocol (MCP) servers, lifecycle hooks, plugins, model preferences, and Google accounts.

---

## Table of Contents

- [Why `agy-multiprofile`?](#why-agy-multiprofile)
- [Key Features](#key-features)
- [Interactive Inline Selector](#interactive-inline-selector)
- [Installation](#installation)
  - [User Scope Installation (Recommended)](#user-scope-installation-recommended)
  - [System-Wide Scope Installation](#system-wide-scope-installation)
  - [Verifying Installation & PATH](#verifying-installation--path)
- [Quick Start](#quick-start)
- [Managed State Matrix](#managed-state-matrix)
- [CLI Reference](#cli-reference)
  - [`agy-profile` (Interactive Selector)](#agy-profile-options----agy-args)
  - [`agy-profile list` / `ls`](#agy-profile-list-alias-ls)
  - [`agy-profile current`](#agy-profile-current)
  - [`agy-profile switch` / `use`](#agy-profile-switch-name-options-alias-use)
  - [`agy-profile create`](#agy-profile-create-name-options)
  - [`agy-profile clone`](#agy-profile-clone-source-dest---desc-text)
  - [`agy-profile delete` / `rm`](#agy-profile-delete-name--y--yes-alias-rm)
  - [`agy-profile rename`](#agy-profile-rename-old_name-new_name)
  - [`agy-profile sync`](#agy-profile-sync---dry-run)
  - [`agy-profile diff`](#agy-profile-diff-profile1-profile2)
  - [`agy-profile backups`](#agy-profile-backups)
  - [`agy-profile restore`](#agy-profile-restore-snapshot_id--y--yes)
  - [`agy-profile trash` & `restore-trash`](#agy-profile-trash--restore-trash-trash_id---name-new_name)
  - [`agy-profile export`](#agy-profile-export-name-output_filezip)
  - [`agy-profile import`](#agy-profile-import-input_filezip---name-profile_name)
  - [`agy-profile doctor`](#agy-profile-doctor)
  - [`agy-profile wrap` / `replace-agy`](#agy-profile-wrap-action-options-aliases-replace-agy-shim-alias)
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
- Workspace trust configurations can be overwritten or lost.

`agy-multiprofile` solves this by introducing an isolated profile vault (`~/.config/agy-profile/`). It swaps configuration environments in milliseconds using **atomic filesystem transactions**, synchronizes credentials directly with the **OS Keyring**, preserves workspace permissions, and launches `agy` automatically.

---

## Key Features

- ⚡ **Interactive Inline Selector**: Instant raw terminal selection menu with keyboard navigation, search, direct number jump, in-menu profile creation, and immediate launch.
- 🔒 **Native OS Keyring Synchronization**: Automatically isolates and swaps OAuth credentials in Linux Secret Service, macOS Keychain, and Windows Credential Manager.
- 🛡️ **Zero-Downtime Atomic Transactions**: File swaps use atomic POSIX replacements with automated transaction rollback if any step fails.
- 💼 **Google Account & `gcloud` Alignment**: Automatically updates `google_accounts.json` and syncs active Google Cloud SDK configurations (`gcloud config set account` / `gcloud config configurations activate`).
- 🤝 **Workspace Trust Preservation**: Maintains workspace permissions across profile switches so you are not re-prompted to trust project directories.
- 📦 **Safety Snapshots & Soft-Delete Trash**: Auto-creates rolling recovery backups before every switch. Deletions are moved to trash and can be restored anytime.
- 🩺 **Built-in Doctor Diagnostics**: Runs automated validation on JSON syntax, filesystem permissions, process locks, keyring access, and binary availability (`agy-profile doctor`).
- 🔄 **`agy` Command Interception**: Seamlessly wrap or replace `agy` via executable shims or shell aliases so typing `agy` opens the switcher menu (`agy-profile wrap install`).
- 🚚 **Portable Profile Archives**: Export and import self-contained profiles as ZIP archives for backup or team sharing (`export` / `import`).

---

## Interactive Inline Selector

Running `agy-profile` directly in your terminal launches a fast, responsive inline selection prompt:

```text
✦ Antigravity Profile Switcher
Select a profile to activate & launch agy:

❯ 1. ● default (active)   (vbatecan@gmail.com)   [3 MCPs]  (active) - Default live profile
  2. ○ work               (work@corp.com)        [6 MCPs]           - Work projects & enterprise MCPs
  3. ○ client-acme        (dev@client.io)        [2 MCPs]           - Acme Corp isolated env
  4. + Create new profile...

Press ↑/↓ to navigate, 1-4 to select, Enter to confirm, Esc/q to cancel
```

### Controls & Hotkeys

| Key | Action |
| :--- | :--- |
| **`↑` / `↓`** or **`k` / `j`** | Move selection cursor up / down |
| **`1` – `9`** | Jump directly to profile number and activate |
| **`Enter`** | Activate selected profile and immediately launch `agy` |
| **`s`** | Switch profile only (without launching `agy`) |
| **`c`** | Create a new profile interactively |
| **`d`** | Move highlighted profile to soft-delete trash |
| **`Esc` / `q`** | Cancel and exit without making changes |
| **`-- [args...]`** | Pass trailing arguments directly to `agy` (e.g. `agy-profile -- --model gemini-2.5-pro`) |

---

## Installation

`agy-multiprofile` can be installed in **User Scope** (isolated per user, no root permissions required) or **System-Wide Scope** (accessible to all users on the host).

---

### User Scope Installation (Recommended)

User-scope installations run in isolated environments and do not require `sudo` privileges.

#### Option A: Using `uv tool` (Fastest & Modern)

[`uv`](https://docs.astral.sh/uv/) installs the CLI in an isolated environment and links the binary automatically.

```bash
# Install directly from Git repository
uv tool install git+https://github.com/your-username/agy-multiprofile.git

# Or install from local source clone
git clone https://github.com/your-username/agy-multiprofile.git
cd agy-multiprofile
uv tool install .

# Upgrade to latest version
uv tool upgrade agy-multiprofile
```

#### Option B: Using `pipx` (Standard Isolated Tool Installer)

[`pipx`](https://pipx.pypa.io/) isolates the tool in its own virtualenv while exposing the executable globally for your user.

```bash
# Install directly from Git repository
pipx install git+https://github.com/your-username/agy-multiprofile.git

# Or install from local source clone
pipx install .

# Upgrade to latest version
pipx upgrade agy-multiprofile
```

#### Option C: User-Level `pip` (`--user`)

```bash
# Install for current user only
pip install --user .

# Or for local development with editable mode
pip install --user -e .
```

> [!NOTE]
> When using `pip install --user`, ensure `~/.local/bin` is in your shell's `PATH`:
> ```bash
> export PATH="$HOME/.local/bin:$PATH"
> ```

---

### System-Wide Scope Installation

System-wide installations make `agy-profile` and `agy-multiprofile` commands available to all users across the entire system.

#### Option A: Isolated System Virtualenv in `/opt` (Recommended)

Creates an isolated virtual environment under `/opt/agy-multiprofile` and symlinks the executables into `/usr/local/bin`. This avoids polluting system Python packages.

```bash
# 1. Create system-wide virtual environment
sudo python3 -m venv /opt/agy-multiprofile
sudo /opt/agy-multiprofile/bin/pip install --upgrade pip

# 2. Install agy-multiprofile into the isolated system environment
sudo /opt/agy-multiprofile/bin/pip install git+https://github.com/your-username/agy-multiprofile.git
# (or from local directory):
# sudo /opt/agy-multiprofile/bin/pip install .

# 3. Create global symlinks in /usr/local/bin
sudo ln -sf /opt/agy-multiprofile/bin/agy-profile /usr/local/bin/agy-profile
sudo ln -sf /opt/agy-multiprofile/bin/agy-multiprofile /usr/local/bin/agy-multiprofile
```

#### Option B: System-Wide `pipx` (Global)

Install globally using `pipx` targeting shared directories:

```bash
sudo PIPX_HOME=/opt/pipx PIPX_BIN_DIR=/usr/local/bin pipx install git+https://github.com/your-username/agy-multiprofile.git
```

#### Option C: Global `pip` (Containers / Managed Environments)

For headless Docker containers or build environments:

```bash
# On systems enforcing PEP 668 (e.g. Debian 12+, Ubuntu 23.04+)
sudo pip install --break-system-packages .

# On standard non-managed systems
sudo pip install .
```

---

### Verifying Installation & PATH

Confirm that the CLI is discovered and executable from any directory:

```bash
# Check executable path
which agy-profile
# -> ~/.local/bin/agy-profile (User scope) or /usr/local/bin/agy-profile (System-wide)

# Check installed version
agy-profile --version

# Run diagnostic health check
agy-profile doctor
```

---

## Quick Start

### 1. Interactive Switch and Launch
```bash
# Open interactive selector, choose a profile, and automatically launch agy
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

# Preview switch changes before applying (dry-run)
agy-profile switch work --dry-run

# Pass arguments directly to agy through the switcher
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
| **Global Settings** | `settings.json` | `settings.json` | Gateway authentication and general settings |
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
Invoking `agy-profile` with no subcommands opens the interactive inline selector.

**Options:**
- `--no-launch`: Switch or select without launching `agy`.
- `--version`: Show program version.
- `-- [args...]`: Pass trailing arguments directly to the underlying `agy` binary.

```bash
# Launch interactive selector and start agy with custom flags
agy-profile -- --model gemini-2.5-pro --verbose
```

---

### `agy-profile list` (alias: `ls`)
Lists all profiles in the vault with metadata, active indicators (`● *`), email, gcloud config, MCP counts, hooks counts, and descriptions.

```bash
agy-profile list
agy-profile ls
```

---

### `agy-profile current`
Displays detailed information about the currently active profile, Google account state, and configured MCP servers in a structured panel.

```bash
agy-profile current
```

---

### `agy-profile switch <name> [options]` (alias: `use`)
Switches the active profile to `<name>`. If `<name>` is omitted, opens the interactive selector.

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

# Switch profile only
agy-profile switch personal
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
# Create a fresh clean profile
agy-profile create personal --email "me@gmail.com" --desc "Personal projects"

# Create a profile initialized from live configuration
agy-profile create work --email "dev@corp.com" --gcloud "corp-profile" --clone-current
```

---

### `agy-profile clone <source> <dest> [--desc "<text>"]`
Clones an existing profile to a new destination profile.

```bash
agy-profile clone work work-feature-test --desc "Testing experimental MCPs"
```

---

### `agy-profile delete <name> [-y/--yes]` (alias: `rm`)
Safely soft-deletes a profile by moving it to `trash/`. Cannot delete the currently active profile.

**Options:**
- `-y`, `--yes`: Skip confirmation prompt.

```bash
agy-profile delete old-profile
agy-profile rm old-profile -y
```

---

### `agy-profile rename <old_name> <new_name>`
Renames an existing profile in the vault and updates manifest references.

```bash
agy-profile rename personal personal-primary
```

---

### `agy-profile sync [--dry-run]`
Explicitly captures current live `~/.gemini` modifications and updates the active profile in the vault.

**Options:**
- `--dry-run`: Preview changes that would be synced into the vault without modifying files.

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
Restores the live environment from a previous safety snapshot. If `snapshot_id` is omitted, prompts for selection.

**Options:**
- `-y`, `--yes`: Skip confirmation prompt.

```bash
# Interactive snapshot restore prompt
agy-profile restore

# Direct snapshot restore
agy-profile restore snap_20260821_143000_switch_default_to_work -y
```

---

### `agy-profile trash` & `restore-trash [trash_id] [--name <new_name>]`
Inspect and restore soft-deleted profiles from trash.

```bash
# List items in trash
agy-profile trash

# Restore by trash ID
agy-profile restore-trash 20260821_143000_old-profile

# Restore with a new profile name
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

**Options:**
- `--name <profile_name>`: Override the imported profile name.

```bash
agy-profile import ~/backups/work-profile.zip --name work-restored
```

---

### `agy-profile doctor`
Executes comprehensive diagnostics on:
- Vault integrity, permissions, and `manifest.json` validity
- Profile JSON file integrity and syntax across all profiles
- `~/.gemini` permissions and directory state
- Antigravity CLI binary (`agy`) detection on PATH or override
- OS Keyring integration status (Linux Secret Service / macOS Keychain / Windows Credential Manager)
- Google Cloud SDK CLI (`gcloud`) detection
- Running Antigravity processes & brain locks

```bash
agy-profile doctor
```

---

### `agy-profile wrap [action] [options]` (aliases: `replace-agy`, `shim`, `alias`, `unwrap`, `revert-agy`)
Replaces the `agy` command with the `agy-profile` switcher via an executable binary shim or shell alias. When configured, typing `agy` directly opens the interactive profile selector before transparently launching the real Antigravity binary.

**Actions:**
- `status` (default): Show current replacement status, real binary location, and alias snippet.
- `install`: Install the executable shim or shell alias.
- `revert` / `uninstall` / `remove`: Revert replacement, remove shim (restoring any original binary backup), and remove shell aliases.
- `alias`: Output the shell alias definition for `eval` or scripting.

**Options:**
- `--mode <shim|alias|all>`: Replacement / reversion mode (default: `shim` for wrap, `all` for unwrap).
  - `shim`: Operates on the executable wrapper in `--bin-dir` (default: `~/.local/bin/agy`).
  - `alias`: Operates on shell alias in your shell rc file (`.bashrc`, `.zshrc`, `config.fish`).
  - `all`: Operates on both executable shim and shell alias.
- `--bin-dir <path>`: Custom binary directory for executable shim (default: `~/.local/bin`).
- `--shell <auto|bash|zsh|fish>`: Target shell for alias configuration (default: `auto`).
- `--dry-run`: Preview changes without modifying files on disk.
- `--force`: Overwrite existing files without failing.

```bash
# Check current agy replacement status
agy-profile wrap status

# Install executable shim in ~/.local/bin/agy (Recommended)
agy-profile wrap install --mode shim

# Or install shell alias into your active shell rc (.bashrc / .zshrc)
agy-profile wrap install --mode alias

# Quick one-liner for current session
eval "$(agy-profile alias)"

# Revert and restore original agy binary and shell configuration
agy-profile unwrap
# or:
agy-profile wrap revert
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
8. **Process Collision Detection**: Checks for active running `agy` sessions before switching, prompting or requiring `--force`.

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
# Format code and check linter
black src tests
ruff check src tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).

