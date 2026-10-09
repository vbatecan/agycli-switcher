"""
Command-line interface for Antigravity Multi-Profile Manager.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agy_multiprofile import __version__
from agy_multiprofile.core.auth import get_live_google_accounts
from agy_multiprofile.core.constants import (
    DEFAULT_PROFILE_NAME,
    MANAGED_FILES,
    get_gemini_home,
    get_profile_home,
)
from agy_multiprofile.core.detector import is_gemini_installed
from agy_multiprofile.core.doctor import run_doctor
from agy_multiprofile.core.launcher import launch_agy
from agy_multiprofile.core.storage import ProfileStore
from agy_multiprofile.core.switcher import ProfileSwitcher
from agy_multiprofile.core.sync import capture_live_to_profile, load_live_files, load_profile_files
from agy_multiprofile.utils.console import (
    bold,
    confirm,
    cyan,
    dim,
    green,
    magenta,
    print_error,
    print_info,
    print_success,
    print_table,
    print_warning,
    prompt_selection,
    red,
    yellow,
)
from agy_multiprofile.utils.diff_utils import generate_dict_diff


def ensure_initialized(store: ProfileStore) -> None:
    """If vault is brand new, automatically bootstrap default profile from current ~/.gemini."""
    store.initialize_vault()
    profiles = store.list_profiles()
    if not profiles:
        print_info("Initializing first profile 'default' from current environment...")
        store.create_profile(
            name=DEFAULT_PROFILE_NAME,
            description="Default live profile",
            clone_from_live=True,
        )


def cmd_list(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    manifest = store.get_manifest()
    profiles = store.list_profiles()

    if not profiles:
        print_info("No profiles found. Create one using: agy-profile create <name> --clone-current")
        return 0

    headers = ["Active", "Name", "Google Email", "gcloud Config", "MCPs", "Hooks", "Description"]
    rows: list[list[str]] = []

    for p in profiles:
        is_active = p.name == manifest.active_profile
        active_str = "[bold green]● *[/bold green]" if is_active else ""
        name_str = f"[bold green]{p.name}[/bold green]" if is_active else p.name
        email_str = p.email or "[dim]-[/dim]"
        gcloud_str = p.gcloud_config or "[dim]-[/dim]"

        # Load file counts
        p_files = load_profile_files(store.get_profile_dir(p.name))
        mcp_data = p_files.get("mcp_config", {})
        mcp_servers = mcp_data.get("mcpServers", {}) if isinstance(mcp_data, dict) else {}
        mcp_count = str(len(mcp_servers)) if mcp_servers else "0"

        hooks_data = p_files.get("cli_hooks", {})
        hooks_count = str(len(hooks_data)) if isinstance(hooks_data, dict) else "0"

        desc_str = p.description or "[dim]-[/dim]"

        rows.append([active_str, name_str, email_str, gcloud_str, mcp_count, hooks_count, desc_str])

    print_table(headers, rows, title="✦ Antigravity Profiles")
    return 0


def cmd_current(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    manifest = store.get_manifest()
    active_name = manifest.active_profile
    meta = store.get_profile_metadata(active_name)

    from rich import box
    from rich.panel import Panel
    from rich.tree import Tree
    from agy_multiprofile.utils.console import console

    tree = Tree(f"[bold cyan]✦ Profile:[/] [bold green]{active_name}[/bold green]")
    if meta:
        tree.add(f"[bold]Description:[/] {meta.description or '[dim]None[/dim]'}")
        tree.add(f"[bold]Google Email:[/] {meta.email or '[dim]Not set[/dim]'}")
        tree.add(f"[bold]gcloud Config:[/] {meta.gcloud_config or '[dim]Default / unset[/dim]'}")
        tree.add(f"[bold]Last Switched:[/] {manifest.last_switched or '[dim]Never[/dim]'}")

    # Inspect live components
    live_files = load_live_files(store.gemini_home)
    mcp_data = live_files.get("mcp_config", {})
    mcp_servers = mcp_data.get("mcpServers", {}) if isinstance(mcp_data, dict) else {}
    mcp_branch = tree.add(f"[bold]Configured MCP Servers[/] ([bold cyan]{len(mcp_servers)}[/]):")
    if mcp_servers:
        for m_name in sorted(mcp_servers.keys()):
            srv = mcp_servers[m_name]
            cmd = srv.get("command") or srv.get("httpUrl") or "unknown"
            mcp_branch.add(f"[cyan]{m_name}[/]: [dim]{cmd}[/dim]")
    else:
        mcp_branch.add("[dim]None[/dim]")

    live_accounts = get_live_google_accounts(store.gemini_home)
    acc_branch = tree.add("[bold]Live Google Account State[/]:")
    acc_branch.add(f"Active: [bold green]{live_accounts.get('active')}[/]")
    old_accs = live_accounts.get("old", [])
    if old_accs:
        acc_branch.add(f"Previous accounts: [dim]{', '.join(old_accs)}[/dim]")

    console.print(Panel(tree, title="[bold cyan]Active Antigravity Profile[/]", border_style="cyan", box=box.ROUNDED))
    return 0


def interactive_switch(
    store: ProfileStore,
    switcher: ProfileSwitcher,
    launch: bool = True,
    launch_args: list[str] | None = None,
) -> int:
    from agy_multiprofile.utils.selector import inline_select
    from agy_multiprofile.utils.console import console

    ensure_initialized(store)

    while True:
        profiles = store.list_profiles()
        manifest = store.get_manifest()
        active_name = manifest.active_profile

        options: list[str] = []
        default_idx = 0

        max_name_len = max([len(p.name) for p in profiles] + [12]) if profiles else 12
        max_email_len = max([len(f"({p.email})") for p in profiles if p.email] + [14]) if profiles else 14

        for i, p in enumerate(profiles):
            is_active = p.name == active_name
            p_files = load_profile_files(store.get_profile_dir(p.name))
            mcp_data = p_files.get("mcp_config", {})
            mcp_count = len(mcp_data.get("mcpServers", {})) if isinstance(mcp_data, dict) else 0

            status_badge = "[bold green]●[/bold green]" if is_active else "[dim]○[/dim]"
            email_str = f"[cyan]({p.email})[/cyan]" if p.email else ""
            active_label = " [bold green](active)[/bold green]" if is_active else ""
            desc_str = f"  [dim]- {p.description}[/dim]" if p.description else ""

            name_padded = p.name.ljust(max_name_len)
            raw_email = f"({p.email})" if p.email else ""
            email_padding = " " * (max_email_len - len(raw_email))
            email_col = f"{email_str}{email_padding}" if email_str else (" " * max_email_len)

            opt_str = f"{status_badge}  {name_padded}  {email_col}  [cyan][{mcp_count} MCPs][/cyan]{active_label}{desc_str}"
            options.append(opt_str)

            if is_active:
                default_idx = i

        options.append("[bold cyan]+ Create new profile...[/bold cyan]")

        action, choice = inline_select(
            title="Antigravity Profile Switcher",
            subtitle="Select a profile to activate & launch agy:",
            options=options,
            default_index=default_idx,
            return_action=True,
        )

        if action == "cancel" or choice is None:
            print_info("Profile switch cancelled.")
            return 0

        if action == "create" or choice == len(profiles):
            console.print(f"\n[bold cyan]✦ Create New Profile[/bold cyan]")
            try:
                name = input("  Profile name: ").strip()
                if not name:
                    print_error("Profile name cannot be empty.")
                    continue
                email = input("  Google Account Email (optional): ").strip() or None
                desc = input("  Description (optional): ").strip()
                clone_input = input("  Clone from current active profile? [y/N]: ").strip().lower()
                clone_live = clone_input in ("y", "yes")

                meta = store.create_profile(
                    name=name,
                    description=desc,
                    email=email,
                    clone_from_live=clone_live,
                )
                print_success(f"Profile '{meta.name}' created successfully.")
                continue
            except (KeyboardInterrupt, EOFError):
                console.print()
                return 0
            except Exception as e:
                print_error(f"Failed to create profile: {e}")
                continue

        elif action == "delete":
            if choice == len(profiles):
                continue
            target_profile = profiles[choice]
            target_name = target_profile.name
            if target_name == active_name:
                print_error(f"Cannot delete active profile '{target_name}'. Please switch to another profile first.")
                try:
                    input("Press Enter to continue...")
                except (KeyboardInterrupt, EOFError):
                    pass
                continue

            console.print(f"\n[bold yellow]⚠ Delete Profile[/bold yellow]")
            try:
                confirm_del = input(f"Are you sure you want to move profile '{target_name}' to trash? [y/N]: ").strip().lower()
                if confirm_del in ("y", "yes"):
                    trash_meta = store.soft_delete_profile(target_name)
                    print_success(f"Profile '{target_name}' moved to trash (ID: {trash_meta.trash_id}).")
                else:
                    print_info("Deletion cancelled.")
            except (KeyboardInterrupt, EOFError):
                console.print()
            continue

        elif action == "select":
            target_profile = profiles[choice]
            target_name = target_profile.name
            if target_name == active_name:
                print_info(f"Active profile is already '{target_name}'.")
            else:
                res = switcher.switch_profile(target_name=target_name)
                if res.success:
                    email_info = f" ({target_profile.email})" if target_profile.email else ""
                    print_success(f"Switched active profile to '{target_name}'{email_info}!")
                else:
                    print_error(res.error or "Switch failed.")
                    return 1

            if launch:
                return launch_agy(args=launch_args)
            return 0


def cmd_switch(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    target_name = args.name

    if not target_name:
        launch = not getattr(args, "no_launch", False)
        return interactive_switch(store, switcher, launch=launch)

    if args.dry_run:
        print_info(f"Running DRY-RUN switch preview for profile '{target_name}'...")
        try:
            plan = switcher.create_switch_plan(target_name)
            print(f"\n{bold('Planned Profile Switch:')} {plan.source_profile} -> {green(plan.target_profile)}")
            if plan.account_change[0] != plan.account_change[1]:
                print(f"  Google Account: {plan.account_change[0]} -> {green(str(plan.account_change[1]))}")
            if plan.gcloud_config_change[0] != plan.gcloud_config_change[1]:
                print(f"  gcloud Config:  {plan.gcloud_config_change[0]} -> {green(str(plan.gcloud_config_change[1]))}")

            if plan.diffs_per_file:
                print(f"\n{bold('File Modifications Preview:')}")
                for fname, diffs in plan.diffs_per_file.items():
                    print(f"  {cyan(fname)} ({len(diffs)} diffs):")
                    for d in diffs[:10]:
                        if d.startswith("+"):
                            print(f"    {green(d)}")
                        elif d.startswith("-"):
                            print(f"    {red(d)}")
                        else:
                            print(f"    {yellow(d)}")
                    if len(diffs) > 10:
                        print(dim(f"    ... and {len(diffs) - 10} more changes"))
            else:
                print(dim("\nNo configuration file changes detected."))

            if plan.running_processes:
                print_warning(f"{len(plan.running_processes)} active Antigravity CLI process(es) detected.")
            print_success("Dry-run preview completed. No files were modified.")
            return 0
        except Exception as e:
            print_error(f"Dry-run failed: {e}")
            return 1

    save_current = getattr(args, "save_current", False)
    res = switcher.switch_profile(
        target_name=target_name,
        force=args.force,
        skip_sync_source=not save_current,
        save_current=save_current,
    )

    for warn in res.warnings:
        print_warning(warn)

    if not res.success:
        print_error(res.error or "Switch failed")
        return 1

    for msg in res.messages:
        print_success(msg)

    if res.snapshot:
        print(dim(f"Safety snapshot created: {res.snapshot.id}"))

    if getattr(args, "launch", False):
        return launch_agy()
    return 0


def cmd_create(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    try:
        meta = store.create_profile(
            name=args.name,
            description=args.desc or "",
            email=args.email,
            gcloud_config=args.gcloud,
            clone_from_profile=args.from_profile,
            clone_from_live=args.clone_current,
        )
        print_success(f"Profile '{meta.name}' created successfully.")
        return 0
    except Exception as e:
        print_error(f"Failed to create profile: {e}")
        return 1


def cmd_clone(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    try:
        meta = store.clone_profile(src_name=args.source, dest_name=args.dest, new_desc=args.desc or "")
        print_success(f"Cloned profile '{args.source}' to '{meta.name}'.")
        return 0
    except Exception as e:
        print_error(f"Failed to clone profile: {e}")
        return 1


def cmd_delete(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    manifest = store.get_manifest()
    if manifest.active_profile == args.name:
        print_error(f"Cannot delete active profile '{args.name}'. Please switch to another profile first.")
        return 1

    if not args.yes:
        if not confirm(f"Are you sure you want to soft-delete profile '{args.name}' to trash?"):
            print_info("Deletion cancelled.")
            return 0

    try:
        trash_meta = store.soft_delete_profile(args.name)
        print_success(f"Profile '{args.name}' safely moved to trash (ID: {trash_meta.trash_id}).")
        print_info(f"You can restore it anytime with: agy-profile restore-trash {trash_meta.trash_id}")
        return 0
    except Exception as e:
        print_error(f"Failed to delete profile: {e}")
        return 1


def cmd_rename(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    try:
        store.rename_profile(old_name=args.old_name, new_name=args.new_name)
        print_success(f"Profile '{args.old_name}' renamed to '{args.new_name}'.")
        return 0
    except Exception as e:
        print_error(f"Failed to rename profile: {e}")
        return 1


def cmd_sync(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    manifest = store.get_manifest()
    active_name = manifest.active_profile
    target_dir = store.get_profile_dir(active_name)

    if args.dry_run:
        print_info(f"Checking modifications to sync back to active profile '{active_name}'...")
        live_files = load_live_files(store.gemini_home)
        profile_files = load_profile_files(target_dir)
        has_diffs = False
        for spec in MANAGED_FILES:
            d = generate_dict_diff(profile_files.get(spec.key, {}), live_files.get(spec.key, {}))
            if d:
                has_diffs = True
                print(f"  {cyan(spec.relative_live_path)}:")
                for line in d[:5]:
                    print(f"    {line}")
        if not has_diffs:
            print_info("Active profile is already in sync with live configuration.")
        return 0

    captured = capture_live_to_profile(target_dir, store.gemini_home)
    print_success(f"Synced {len(captured)} configuration files into active profile '{active_name}'.")
    return 0


def cmd_diff(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    manifest = store.get_manifest()

    p1_name = args.profile1 or manifest.active_profile
    p2_name = args.profile2

    if not p2_name:
        # Diff live ~/.gemini vs p1
        print(f"{bold('Diff between LIVE configuration and profile:')} {cyan(p1_name)}")
        live_data = load_live_files(store.gemini_home)
        p1_dir = store.get_profile_dir(p1_name)
        if not p1_dir.exists():
            print_error(f"Profile '{p1_name}' does not exist.")
            return 1
        p1_data = load_profile_files(p1_dir)
        
        has_diff = False
        for spec in MANAGED_FILES:
            diffs = generate_dict_diff(p1_data.get(spec.key, {}), live_data.get(spec.key, {}))
            if diffs:
                has_diff = True
                print(f"\n{bold(cyan(spec.relative_live_path))} (Profile -> Live):")
                for d in diffs:
                    if d.startswith("+"):
                        print(f"  {green(d)}")
                    elif d.startswith("-"):
                        print(f"  {red(d)}")
                    else:
                        print(f"  {yellow(d)}")
        if not has_diff:
            print_info("No differences found.")
        return 0
    else:
        print(f"{bold('Diff between profiles:')} {cyan(p1_name)} <-> {green(p2_name)}")
        p1_dir = store.get_profile_dir(p1_name)
        p2_dir = store.get_profile_dir(p2_name)
        if not p1_dir.exists():
            print_error(f"Profile '{p1_name}' does not exist.")
            return 1
        if not p2_dir.exists():
            print_error(f"Profile '{p2_name}' does not exist.")
            return 1
        p1_data = load_profile_files(p1_dir)
        p2_data = load_profile_files(p2_dir)

        has_diff = False
        for spec in MANAGED_FILES:
            diffs = generate_dict_diff(p1_data.get(spec.key, {}), p2_data.get(spec.key, {}))
            if diffs:
                has_diff = True
                print(f"\n{bold(cyan(spec.relative_live_path))}:")
                for d in diffs:
                    if d.startswith("+"):
                        print(f"  {green(d)}")
                    elif d.startswith("-"):
                        print(f"  {red(d)}")
                    else:
                        print(f"  {yellow(d)}")
        if not has_diff:
            print_info("Both profiles have identical configurations.")
        return 0


def cmd_backups(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    snapshots = store.list_snapshots()
    if not snapshots:
        print_info("No backup snapshots found.")
        return 0

    headers = ["Snapshot ID", "Timestamp", "Trigger", "Files Count"]
    rows = []
    for s in snapshots:
        rows.append([s.id, s.timestamp[:19].replace("T", " "), s.trigger, str(len(s.files))])

    print_table(headers, rows, title="✦ Backup Snapshots")
    return 0


def cmd_restore(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    snap_id = args.snapshot_id
    if not snap_id:
        snapshots = store.list_snapshots()
        if not snapshots:
            print_error("No snapshots available to restore.")
            return 1
        choices = [s.id for s in snapshots]
        snap_id = prompt_selection("Select snapshot to restore:", choices)

    if not args.yes:
        if not confirm(f"Are you sure you want to restore live environment from snapshot '{snap_id}'?"):
            print_info("Restore cancelled.")
            return 0

    ok, msg = switcher.restore_snapshot_to_live(snap_id)
    if ok:
        print_success(msg)
        return 0
    else:
        print_error(msg)
        return 1


def cmd_trash(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    items = store.list_trash()
    if not items:
        print_info("Trash is empty.")
        return 0

    headers = ["Trash ID", "Original Profile Name", "Deleted At"]
    rows = [[it.trash_id, it.profile_name, it.deleted_at[:19].replace("T", " ")] for it in items]
    print_table(headers, rows, title="✦ Soft-Deleted Profiles in Trash")
    return 0


def cmd_restore_trash(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    trash_id = args.trash_id
    if not trash_id:
        items = store.list_trash()
        if not items:
            print_error("Trash is empty.")
            return 1
        choices = [it.trash_id for it in items]
        trash_id = prompt_selection("Select trash item to restore:", choices)

    try:
        meta = store.restore_from_trash(trash_id=trash_id, new_name=args.name)
        print_success(f"Profile '{meta.name}' restored successfully from trash.")
        return 0
    except Exception as e:
        print_error(f"Failed to restore from trash: {e}")
        return 1


def cmd_export(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    export_path = Path(args.output_file)
    try:
        store.export_profile(args.name, export_path)
        print_success(f"Exported profile '{args.name}' to {export_path}")
        return 0
    except Exception as e:
        print_error(f"Failed to export profile: {e}")
        return 1


def cmd_import(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    import_path = Path(args.input_file)
    try:
        meta = store.import_profile(import_path, override_name=args.name)
        print_success(f"Imported profile '{meta.name}' from {import_path}")
        return 0
    except Exception as e:
        print_error(f"Failed to import profile: {e}")
        return 1


def cmd_doctor(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    from agy_multiprofile.utils.console import console
    console.print("[bold cyan]✦ Running Antigravity Profile Doctor...[/bold cyan]\n")
    res = run_doctor(store.root_dir, store.gemini_home)

    for info in res.info:
        print_info(info)
    for warn in res.warnings:
        print_warning(warn)
    for err in res.errors:
        print_error(err)

    if res.is_valid:
        console.print(f"\n[bold green]✔ Doctor check passed.[/bold green] Environment and profile vault are healthy.")
        return 0
    else:
        console.print(f"\n[bold red]✖ Doctor check found issues.[/bold red] Please review errors above.")
        return 1


def cmd_wrap(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    ensure_initialized(store)
    from agy_multiprofile.core.wrapper import (
        generate_shell_alias,
        get_shim_status,
        install_shell_alias,
        install_shim,
        uninstall_shell_alias,
        uninstall_shim,
    )
    from agy_multiprofile.utils.console import console

    action = (args.action or "status").lower()
    mode = getattr(args, "mode", "shim") or "shim"
    bin_dir = Path(args.bin_dir) if getattr(args, "bin_dir", None) else None
    shell = getattr(args, "shell", "auto") or "auto"

    if action in ("status", "info"):
        console.print("[bold cyan]✦ Antigravity CLI 'agy' Replacement Status[/bold cyan]\n")
        status = get_shim_status(bin_dir, store.root_dir)

        if status["is_installed"]:
            if status["is_valid_shim"]:
                print_success(f"Executable shim is installed at: {status['shim_path']}")
            else:
                print_warning(f"File exists at '{status['shim_path']}' but is NOT an agy-profile shim.")
        else:
            print_info(f"No executable shim installed at: {status['shim_path']}")

        if status["has_backup"]:
            print_info(f"Original binary backup preserved at: {status['backup_path']}")

        if status["saved_real_path"]:
            print_info(f"Recorded real Antigravity binary: {status['saved_real_path']}")

        if status["found_real_binary"]:
            print_info(f"Discovered real Antigravity binary: {status['found_real_binary']}")
        else:
            print_warning("No underlying Antigravity CLI binary discovered.")

        which_agy = status.get("which_agy")
        if which_agy:
            if status["is_active_shim"]:
                print_success(f"Active 'agy' command on PATH invokes agy-profile switcher ({which_agy})")
            else:
                print_info(f"Active 'agy' command on PATH: {which_agy}")
        else:
            print_info("No 'agy' command currently on PATH.")

        if not status["in_path"]:
            print_warning(f"Shim directory '{status['shim_path'].parent}' is not in your current PATH.")

        console.print(f"\n[bold]Shell Alias snippet:[/bold] [dim]{generate_shell_alias(shell)}[/dim]")
        return 0

    elif action in ("install", "setup", "enable"):
        if getattr(args, "dry_run", False):
            print_info(f"DRY RUN: Would install agy replacement in mode '{mode}'.")
            return 0

        success = True
        if mode in ("shim", "all"):
            ok, msg = install_shim(bin_dir=bin_dir, profile_home=store.root_dir, force=getattr(args, "force", False))
            if ok:
                print_success(msg)
            else:
                print_error(msg)
                success = False

        if mode in ("alias", "all"):
            ok, msg = install_shell_alias(shell=shell)
            if ok:
                print_success(msg)
            else:
                print_error(msg)
                success = False

        return 0 if success else 1

    elif action in ("uninstall", "remove", "disable", "revert", "restore", "unwrap", "reset"):
        if getattr(args, "dry_run", False):
            print_info(f"DRY RUN: Would revert agy replacement in mode '{mode}'.")
            return 0

        success = True
        if mode in ("shim", "all"):
            ok, msg = uninstall_shim(bin_dir=bin_dir, profile_home=store.root_dir)
            if ok:
                print_success(msg)
            else:
                print_error(msg)
                success = False

        if mode in ("alias", "all"):
            ok, msg = uninstall_shell_alias(shell=shell)
            if ok:
                print_success(msg)
            else:
                print_error(msg)
                success = False

        return 0 if success else 1

    elif action in ("alias", "eval"):
        print(generate_shell_alias(shell))
        return 0

    else:
        print_error(f"Unknown action '{action}'. Use: install, revert, uninstall, status, alias")
        return 1


def cmd_tui(args: argparse.Namespace, store: ProfileStore, switcher: ProfileSwitcher) -> int:
    try:
        from agy_multiprofile.tui.app import ProfileManagerApp
        app = ProfileManagerApp(store=store, gemini_home=store.gemini_home)
        selected_profile = app.run()
        if selected_profile and not getattr(args, "no_launch", False):
            return launch_agy()
        return 0
    except ImportError as e:
        print_error(f"Textual TUI dependency not found: {e}. Please install with: pip install textual rich")
        return 1
    except Exception as e:
        print_error(f"TUI error: {e}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agy-profile",
        description="Seamless, safety-first profile and account switcher for Antigravity & Gemini CLI.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--no-launch", action="store_true", help="Do not automatically launch agy after selecting profile")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # tui
    p_tui = subparsers.add_parser("tui", help="Launch interactive Terminal User Interface (TUI)")
    p_tui.add_argument("--no-launch", action="store_true", help="Do not automatically launch agy when selecting in TUI")
    p_tui.set_defaults(func=cmd_tui)

    # list / ls
    p_list = subparsers.add_parser("list", aliases=["ls"], help="List all available profiles")
    p_list.set_defaults(func=cmd_list)

    # current
    p_curr = subparsers.add_parser("current", help="Show currently active profile details")
    p_curr.set_defaults(func=cmd_current)

    # switch / use
    p_switch = subparsers.add_parser("switch", aliases=["use"], help="Switch to a profile")
    p_switch.add_argument("name", nargs="?", help="Name of profile to switch to")
    p_switch.add_argument("--dry-run", action="store_true", help="Preview file changes without modifying disk")
    p_switch.add_argument("--force", action="store_true", help="Proceed even if active processes are detected")
    p_switch.add_argument("--save-current", action="store_true", help="Sync live modifications into current profile before switching")
    p_switch.add_argument("--skip-sync", action="store_true", help="Do not sync live modifications back to current profile (default)")
    p_switch.add_argument("--no-launch", action="store_true", help="Do not automatically launch agy after selecting/switching")
    p_switch.add_argument("--launch", action="store_true", help="Automatically launch agy after switching")
    p_switch.set_defaults(func=cmd_switch)

    # create
    p_create = subparsers.add_parser("create", help="Create a new profile")
    p_create.add_argument("name", help="Profile name")
    p_create.add_argument("--desc", help="Optional description")
    p_create.add_argument("--email", help="Associated Google account email")
    p_create.add_argument("--gcloud", help="Associated gcloud configuration name")
    p_create.add_argument("--clone-current", action="store_true", help="Initialize from active ~/.gemini files")
    p_create.add_argument("--from", dest="from_profile", help="Clone from an existing profile")
    p_create.set_defaults(func=cmd_create)

    # clone
    p_clone = subparsers.add_parser("clone", help="Clone an existing profile")
    p_clone.add_argument("source", help="Source profile name")
    p_clone.add_argument("dest", help="Destination profile name")
    p_clone.add_argument("--desc", help="Description for cloned profile")
    p_clone.set_defaults(func=cmd_clone)

    # delete / rm
    p_delete = subparsers.add_parser("delete", aliases=["rm"], help="Soft-delete a profile to trash")
    p_delete.add_argument("name", help="Profile name to delete")
    p_delete.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p_delete.set_defaults(func=cmd_delete)

    # rename
    p_rename = subparsers.add_parser("rename", help="Rename a profile")
    p_rename.add_argument("old_name", help="Current profile name")
    p_rename.add_argument("new_name", help="New profile name")
    p_rename.set_defaults(func=cmd_rename)

    # sync
    p_sync = subparsers.add_parser("sync", help="Sync live configuration changes back into active profile vault")
    p_sync.add_argument("--dry-run", action="store_true", help="Check diffs without modifying profile vault")
    p_sync.set_defaults(func=cmd_sync)

    # diff
    p_diff = subparsers.add_parser("diff", help="Show configuration differences between profiles or live state")
    p_diff.add_argument("profile1", nargs="?", help="First profile (defaults to active profile)")
    p_diff.add_argument("profile2", nargs="?", help="Second profile (if omitted, diffs against live ~/.gemini)")
    p_diff.set_defaults(func=cmd_diff)

    # backups
    p_backups = subparsers.add_parser("backups", help="List safety backup snapshots")
    p_backups.set_defaults(func=cmd_backups)

    # restore
    p_restore = subparsers.add_parser("restore", help="Restore live configuration from a backup snapshot")
    p_restore.add_argument("snapshot_id", nargs="?", help="Snapshot ID to restore")
    p_restore.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p_restore.set_defaults(func=cmd_restore)

    # trash
    p_trash = subparsers.add_parser("trash", help="List soft-deleted profiles in trash")
    p_trash.set_defaults(func=cmd_trash)

    # restore-trash
    p_rtrash = subparsers.add_parser("restore-trash", help="Restore a soft-deleted profile from trash")
    p_rtrash.add_argument("trash_id", nargs="?", help="Trash ID to restore")
    p_rtrash.add_argument("--name", help="Optional new name for restored profile")
    p_rtrash.set_defaults(func=cmd_restore_trash)

    # export
    p_export = subparsers.add_parser("export", help="Export a profile to a ZIP archive")
    p_export.add_argument("name", help="Profile name to export")
    p_export.add_argument("output_file", help="Destination ZIP file path")
    p_export.set_defaults(func=cmd_export)

    # import
    p_import = subparsers.add_parser("import", help="Import a profile from a ZIP archive")
    p_import.add_argument("input_file", help="Source ZIP file path")
    p_import.add_argument("--name", help="Optional name for imported profile")
    p_import.set_defaults(func=cmd_import)

    # doctor
    p_doctor = subparsers.add_parser("doctor", help="Run diagnostic health checks")
    p_doctor.set_defaults(func=cmd_doctor)

    # wrap / replace-agy / shim / alias
    p_wrap = subparsers.add_parser(
        "wrap",
        aliases=["replace-agy", "shim", "alias"],
        help="Replace 'agy' command with agy-profile switcher or manage shell alias/shim",
    )
    p_wrap.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["install", "uninstall", "remove", "revert", "restore", "unwrap", "status", "alias", "eval"],
        help="Action to perform (install, revert, uninstall, status, alias)",
    )
    p_wrap.add_argument(
        "--mode",
        choices=["shim", "alias", "all"],
        default="shim",
        help="Replacement mode: 'shim' (executable wrapper in bin dir), 'alias' (shell rc config), or 'all'",
    )
    p_wrap.add_argument("--bin-dir", help="Custom binary directory for executable shim (default: ~/.local/bin)")
    p_wrap.add_argument("--shell", choices=["auto", "bash", "zsh", "fish"], default="auto", help="Target shell for alias")
    p_wrap.add_argument("--dry-run", action="store_true", help="Preview actions without modifying disk")
    p_wrap.add_argument("--force", action="store_true", help="Force overwrite existing binary without failing")
    p_wrap.set_defaults(func=cmd_wrap)

    # unwrap / revert-agy (shortcut)
    p_unwrap = subparsers.add_parser(
        "unwrap",
        aliases=["revert-agy", "revert"],
        help="Revert 'agy' wrapper and restore original binary and shell configuration",
    )
    p_unwrap.add_argument(
        "--mode",
        choices=["shim", "alias", "all"],
        default="all",
        help="Reversion mode: 'shim', 'alias', or 'all' (default: all)",
    )
    p_unwrap.add_argument("--bin-dir", help="Custom binary directory for executable shim (default: ~/.local/bin)")
    p_unwrap.add_argument("--shell", choices=["auto", "bash", "zsh", "fish"], default="auto", help="Target shell for alias")
    p_unwrap.add_argument("--dry-run", action="store_true", help="Preview actions without modifying disk")
    p_unwrap.set_defaults(func=lambda args, store, switcher: (setattr(args, "action", "revert"), cmd_wrap(args, store, switcher))[1])

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()

    pass_args: list[str] = []
    args_list = sys.argv[1:] if argv is None else list(argv)
    if "--" in args_list:
        idx = args_list.index("--")
        pass_args = args_list[idx + 1:]
        args_list = args_list[:idx]

    args = parser.parse_args(args_list)

    store = ProfileStore()
    switcher = ProfileSwitcher(store=store)

    if not args.command:
        # If run interactively with no arguments, launch inline Codex-style selector
        if sys.stdin.isatty() and sys.stdout.isatty() and (argv is None or not args_list):
            launch = not getattr(args, "no_launch", False)
            return interactive_switch(store, switcher, launch=launch, launch_args=pass_args)
        parser.print_help()
        return 0

    func = getattr(args, "func", None)
    if func:
        return func(args, store, switcher)
    parser.print_help()
    return 0




if __name__ == "__main__":
    sys.exit(main())
