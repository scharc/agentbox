# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Workspace mount commands."""

from pathlib import Path
from typing import Optional

import click
from rich.table import Table

from agentbox.cli import cli
from agentbox.cli.helpers import (
    WORKSPACES_MOUNT_ROOT,
    _get_project_context,
    _load_workspaces_config,
    _require_agentbox_dir,
    _save_workspaces_config,
    _sanitize_mount_name,
    _warn_if_agents_running,
    _rebuild_container,
    console,
    handle_errors,
)
from agentbox.cli.helpers.completions import _complete_workspace_names
from agentbox.utils.project import resolve_project_dir, get_agentbox_dir


@cli.group()
def workspace():
    """Manage workspace mounts (list, add, remove)."""
    pass


@workspace.command(name="list")
@handle_errors
def workspace_list():
    """List configured workspace mounts for the current project."""
    project_dir = resolve_project_dir()
    agentbox_dir = get_agentbox_dir(project_dir)
    workspaces = _load_workspaces_config(agentbox_dir)

    if not workspaces:
        console.print("[yellow]No workspace mounts configured[/yellow]")
        return

    table = Table(title="Workspace Mounts")
    table.add_column("Name", style="cyan")
    table.add_column("Host Path", style="white")
    table.add_column("Mode", style="magenta")
    table.add_column("Container Path", style="blue")

    for entry in workspaces:
        mount = entry.get("mount", "")
        host_path = entry.get("path", "")
        mode = entry.get("mode", "ro")
        container_path = f"{WORKSPACES_MOUNT_ROOT}/{mount}"
        table.add_row(mount, host_path, mode, container_path)

    console.print(table)


@workspace.command(name="add")
@click.argument(
    "path",
    type=click.Path(exists=True, dir_okay=True, file_okay=True, resolve_path=False),
)
@click.argument("mode", required=False, type=click.Choice(["ro", "rw"]))
@click.argument("name", required=False)
@handle_errors
def workspace_add(path: str, mode: Optional[str], name: Optional[str]):
    """Add an extra mount for the current project."""
    mode_final = mode or "ro"
    pctx = _get_project_context()
    _require_agentbox_dir(pctx.agentbox_dir, pctx.project_dir)

    host_path = Path(path).expanduser().resolve()
    if not host_path.exists():
        raise click.ClickException(f"Path not found: {host_path}")

    mount_name = name or host_path.name or "root"
    mount_name = _sanitize_mount_name(mount_name)
    if not mount_name:
        raise click.ClickException("Invalid mount name")

    workspaces = _load_workspaces_config(pctx.agentbox_dir)
    existing_entry = None
    for entry in workspaces:
        if entry.get("path") == str(host_path):
            existing_entry = entry
            break

    if existing_entry:
        if existing_entry.get("mode") == mode_final:
            console.print(f"[yellow]Path already mounted: {host_path}[/yellow]")
            return
        existing_mount = existing_entry.get("mount") or mount_name
        if name and existing_mount != mount_name:
            console.print(
                f"[yellow]Path already mounted as '{existing_mount}'. Keeping existing mount name.[/yellow]"
            )
        existing_entry["mode"] = mode_final
        _save_workspaces_config(pctx.agentbox_dir, workspaces)

        container_path = f"{WORKSPACES_MOUNT_ROOT}/{existing_mount}"
        console.print("[green]✓ Updated mount mode[/green]")
        console.print(f"  Host: {host_path}")
        console.print(f"  Container: {container_path} ({mode_final})")

        # Warn if agents are running
        if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
            console.print("[yellow]Operation cancelled[/yellow]")
            return

        console.print("[blue]Rebuilding container to apply mounts...[/blue]")
        _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
        console.print("[green]✓ Container rebuilt[/green]")
        return

    for entry in workspaces:
        if entry.get("mount") == mount_name:
            console.print(f"[yellow]Mount name already exists: {mount_name}[/yellow]")
            return

    workspaces.append({"path": str(host_path), "mode": mode_final, "mount": mount_name})
    _save_workspaces_config(pctx.agentbox_dir, workspaces)

    container_path = f"{WORKSPACES_MOUNT_ROOT}/{mount_name}"
    console.print("[green]✓ Added mount[/green]")
    console.print(f"  Host: {host_path}")
    console.print(f"  Container: {container_path} ({mode_final})")

    # Warn if agents are running
    if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
        console.print("[yellow]Operation cancelled[/yellow]")
        return

    console.print("[blue]Rebuilding container to apply mounts...[/blue]")
    _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
    console.print("[green]✓ Container rebuilt[/green]")


@workspace.command(name="remove")
@click.argument("path_or_name", shell_complete=_complete_workspace_names)
@handle_errors
def workspace_remove(path_or_name: str):
    """Remove an extra mount by name or path."""
    pctx = _get_project_context()
    _require_agentbox_dir(pctx.agentbox_dir, pctx.project_dir)

    workspaces = _load_workspaces_config(pctx.agentbox_dir)
    if not workspaces:
        console.print("[yellow]No extra mounts configured[/yellow]")
        return

    target_path = str(Path(path_or_name).expanduser().resolve())
    removed = [
        entry
        for entry in workspaces
        if entry.get("mount") == path_or_name or entry.get("path") == target_path
    ]
    remaining = [
        entry
        for entry in workspaces
        if entry.get("mount") != path_or_name and entry.get("path") != target_path
    ]

    if len(remaining) == len(workspaces):
        console.print(f"[yellow]No matching mount found for '{path_or_name}'[/yellow]")
        return

    _save_workspaces_config(pctx.agentbox_dir, remaining)

    console.print(f"[green]✓ Removed mount(s) matching '{path_or_name}'[/green]")

    # Warn if agents are running
    if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
        console.print("[yellow]Operation cancelled[/yellow]")
        return

    console.print("[blue]Rebuilding container to apply mounts...[/blue]")
    _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
    console.print("[green]✓ Container rebuilt[/green]")
