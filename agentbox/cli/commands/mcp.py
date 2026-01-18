# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""MCP server commands."""

import json
from typing import Set

import click
import questionary

from agentbox.cli import cli
from agentbox.cli.helpers import (
    _complete_mcp_names,
    _copy_commands,
    _get_project_context,
    _load_mcp_meta,
    _rebuild_container,
    _remove_commands,
    _require_agentbox_dir,
    _save_mcp_meta,
    _warn_if_agents_running,
    console,
    handle_errors,
)
from agentbox.library import LibraryManager
from agentbox.utils.logging import get_logger
from agentbox.utils.project import resolve_project_dir, get_agentbox_dir

logger = get_logger(__name__)


def _get_installed_mcps(pctx) -> Set[str]:
    """Get set of currently installed MCP server names."""
    installed = set()

    # Check Claude MCP config
    claude_mcp_path = pctx.agentbox_dir / "claude" / "mcp.json"
    if claude_mcp_path.exists():
        try:
            claude_mcp_data = json.loads(claude_mcp_path.read_text())
            installed.update(claude_mcp_data.get("mcpServers", {}).keys())
        except (json.JSONDecodeError, OSError):
            pass

    # Check Codex config
    codex_config_path = pctx.agentbox_dir / "codex" / "config.toml"
    if codex_config_path.exists():
        try:
            import tomllib
            codex_data = tomllib.loads(codex_config_path.read_text())
            installed.update(codex_data.get("mcp_servers", {}).keys())
        except (Exception):
            pass

    return installed


def _add_mcp(name: str, lib_manager: LibraryManager, pctx) -> tuple[bool, bool]:
    """Add an MCP server to the project.

    Returns:
        Tuple of (success, needs_rebuild)
    """
    mcp_path = lib_manager.get_mcp_path(name)
    if mcp_path is None:
        return False, False

    template_path = mcp_path / "config.json"
    if not template_path.exists():
        return False, False

    template = json.loads(template_path.read_text())
    mcp_config = template["config"]

    # Determine which agents to install to from config
    allowed_agents = template.get("allowed_agents", [])
    blocked_agents = template.get("blocked_agents", [])

    if allowed_agents:
        target_agents = allowed_agents
    else:
        target_agents = ["claude", "codex", "gemini"]

    if blocked_agents:
        target_agents = [a for a in target_agents if a not in blocked_agents]

    if not target_agents:
        return False, False

    added_to = []

    # Add to Claude MCP config
    if "claude" in target_agents:
        claude_mcp_path = pctx.agentbox_dir / "claude" / "mcp.json"
        if claude_mcp_path.exists():
            claude_mcp_data = json.loads(claude_mcp_path.read_text())
        else:
            claude_mcp_data = {"mcpServers": {}}

        if name not in claude_mcp_data.get("mcpServers", {}):
            claude_mcp_data["mcpServers"][name] = mcp_config
            claude_mcp_path.write_text(json.dumps(claude_mcp_data, indent=2))
            added_to.append("claude")

    # Add to Codex config
    if "codex" in target_agents:
        codex_config_path = pctx.agentbox_dir / "codex" / "config.toml"
        if codex_config_path.exists():
            import tomllib
            codex_data = tomllib.loads(codex_config_path.read_text())
        else:
            codex_data = {}

        if "mcp_servers" not in codex_data:
            codex_data["mcp_servers"] = {}

        if name not in codex_data["mcp_servers"]:
            codex_mcp = {}
            if mcp_config.get("type") == "stdio":
                codex_mcp["command"] = mcp_config.get("command", "")
                if "args" in mcp_config:
                    codex_mcp["args"] = mcp_config["args"]
                if "env" in mcp_config:
                    codex_mcp["env"] = mcp_config["env"]
            elif mcp_config.get("type") == "http":
                codex_mcp["url"] = mcp_config.get("url", "")
            else:
                codex_mcp["command"] = mcp_config.get("command", "")
                if "args" in mcp_config:
                    codex_mcp["args"] = mcp_config["args"]
                if "env" in mcp_config:
                    codex_mcp["env"] = mcp_config["env"]

            import toml
            codex_data["mcp_servers"][name] = codex_mcp
            with open(codex_config_path, "w") as f:
                toml.dump(codex_data, f)
            added_to.append("codex")

    # Store MCP metadata (including config for generate-mcp-config.py)
    meta = _load_mcp_meta(pctx.agentbox_dir)
    server_meta = {
        "config": mcp_config  # Store full config for config generation
    }
    if "install" in template:
        server_meta["install"] = template["install"]
    if "mounts" in template:
        server_meta["mounts"] = template["mounts"]
    # Always save - every MCP needs an entry for config generation
    meta["servers"][name] = server_meta
    _save_mcp_meta(pctx.agentbox_dir, meta)

    # Copy slash commands if the MCP has any
    copied_commands = _copy_commands(mcp_path, pctx.project_dir, "mcp", name)
    if copied_commands:
        meta["servers"][name]["commands"] = copied_commands
        _save_mcp_meta(pctx.agentbox_dir, meta)

    needs_rebuild = "mounts" in template or "install" in template
    return bool(added_to), needs_rebuild


def _remove_mcp(name: str, pctx) -> tuple[bool, bool]:
    """Remove an MCP server from the project.

    Returns:
        Tuple of (removed, had_mounts)
    """
    removed = False
    had_mounts = False

    # Check if MCP had mounts before removing
    meta = _load_mcp_meta(pctx.agentbox_dir)
    if name in meta.get("servers", {}):
        had_mounts = "mounts" in meta["servers"][name]

    # Remove slash commands associated with this MCP
    _remove_commands(pctx.project_dir, "mcp", name)

    # Remove from Claude MCP config
    claude_mcp_path = pctx.agentbox_dir / "claude" / "mcp.json"
    if claude_mcp_path.exists():
        claude_mcp_data = json.loads(claude_mcp_path.read_text())
        if name in claude_mcp_data.get("mcpServers", {}):
            del claude_mcp_data["mcpServers"][name]
            claude_mcp_path.write_text(json.dumps(claude_mcp_data, indent=2))
            removed = True

    # Remove from Codex config
    codex_config_path = pctx.agentbox_dir / "codex" / "config.toml"
    if codex_config_path.exists():
        import tomllib
        import toml
        codex_data = tomllib.loads(codex_config_path.read_text())
        if "mcp_servers" in codex_data and name in codex_data["mcp_servers"]:
            del codex_data["mcp_servers"][name]
            with open(codex_config_path, "w") as f:
                toml.dump(codex_data, f)
            removed = True

    # Remove from MCP metadata
    if name in meta.get("servers", {}):
        del meta["servers"][name]
        _save_mcp_meta(pctx.agentbox_dir, meta)

    return removed, had_mounts


@cli.group(invoke_without_command=True)
@click.pass_context
@handle_errors
def mcp(ctx):
    """Manage MCP servers - select which servers to enable."""
    if ctx.invoked_subcommand is None:
        # Run the manage command by default
        ctx.invoke(mcp_manage)


@mcp.command(name="manage")
@handle_errors
def mcp_manage():
    """Interactive MCP server selection with checkboxes."""
    pctx = _get_project_context()
    _require_agentbox_dir(pctx.agentbox_dir, pctx.project_dir)

    lib_manager = LibraryManager()
    available_mcps = lib_manager.list_mcp_servers()

    if not available_mcps:
        console.print("[yellow]No MCP servers available in library[/yellow]")
        console.print(f"[blue]Add MCP servers to: {lib_manager.mcp_dir}[/blue]")
        return

    installed = _get_installed_mcps(pctx)

    # Build choices with pre-selection
    choices = []
    for mcp_info in available_mcps:
        name = mcp_info["name"]
        desc = mcp_info["description"][:50] + "..." if len(mcp_info["description"]) > 50 else mcp_info["description"]
        source = mcp_info.get("source", "library")
        label = f"{name} ({source}) - {desc}"
        choices.append(questionary.Choice(
            title=label,
            value=name,
            checked=name in installed
        ))

    console.print("[bold]Select MCP servers to enable:[/bold]")
    console.print("[dim]Space to toggle, Enter to confirm, Ctrl+C to cancel[/dim]\n")

    try:
        selected = questionary.checkbox(
            "MCP Servers:",
            choices=choices,
        ).ask()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled[/yellow]")
        return

    if selected is None:
        console.print("[yellow]Cancelled[/yellow]")
        return

    selected_set = set(selected)

    # Determine what to add and remove
    to_add = selected_set - installed
    to_remove = installed - selected_set

    if not to_add and not to_remove:
        console.print("[green]No changes needed[/green]")
        return

    # Track if rebuild is needed
    needs_rebuild = False
    added = []
    removed = []
    env_templates = {}
    notes = []

    # Add new MCPs
    for name in to_add:
        success, rebuild_needed = _add_mcp(name, lib_manager, pctx)
        if success:
            added.append(name)
            if rebuild_needed:
                needs_rebuild = True

            # Collect env templates and notes
            mcp_path = lib_manager.get_mcp_path(name)
            if mcp_path:
                template_path = mcp_path / "config.json"
                if template_path.exists():
                    template = json.loads(template_path.read_text())
                    if "env_template" in template:
                        env_templates[name] = template["env_template"]
                    if "notes" in template:
                        notes.append(f"{name}: {template['notes']}")
        else:
            console.print(f"[red]Failed to add MCP server '{name}'[/red]")

    # Remove MCPs
    for name in to_remove:
        success, had_mounts = _remove_mcp(name, pctx)
        if success:
            removed.append(name)
            if had_mounts:
                needs_rebuild = True

    # Print summary
    if added:
        console.print(f"[green]Added MCP servers: {', '.join(sorted(added))}[/green]")
    if removed:
        console.print(f"[yellow]Removed MCP servers: {', '.join(sorted(removed))}[/yellow]")

    # Show env templates
    if env_templates:
        console.print("\n[yellow]Configure environment variables:[/yellow]")
        for name, env in env_templates.items():
            console.print(f"  [cyan]{name}:[/cyan]")
            for key, value in env.items():
                console.print(f"    {key}={value}")
        console.print("\n[blue]Add to .agentbox/.env or set in your shell[/blue]")

    # Show notes
    if notes:
        console.print("\n[blue]Notes:[/blue]")
        for note in notes:
            console.print(f"  {note}")

    # Rebuild container if needed
    if needs_rebuild:
        if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
            console.print("[yellow]Changes applied but container rebuild cancelled[/yellow]")
            console.print("[blue]Run 'agentbox rebase' when ready to apply changes[/blue]")
            return

        console.print("\n[blue]Rebuilding container to apply changes...[/blue]")
        _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
        console.print("[green]Container rebuilt[/green]")


@mcp.command(name="show")
@click.argument("name", shell_complete=_complete_mcp_names)
@handle_errors
def mcp_show(name: str):
    """Show details of an MCP server."""
    lib_manager = LibraryManager()
    lib_manager.show_mcp(name)


@mcp.command(name="list")
@handle_errors
def mcp_list():
    """List available MCP servers from library."""
    lib_manager = LibraryManager()
    lib_manager.print_mcp_table()


@mcp.command(name="add")
@click.argument("name", shell_complete=_complete_mcp_names)
@handle_errors
def mcp_add(name: str):
    """Add an MCP server from library to current project."""
    pctx = _get_project_context()
    _require_agentbox_dir(pctx.agentbox_dir, pctx.project_dir)

    lib_manager = LibraryManager()
    success, needs_rebuild = _add_mcp(name, lib_manager, pctx)

    if not success:
        raise click.ClickException(f"MCP server '{name}' not found or already added")

    console.print(f"[green]✓ Added '{name}' MCP server[/green]")

    # Show env template if present
    mcp_path = lib_manager.get_mcp_path(name)
    if mcp_path:
        template_path = mcp_path / "config.json"
        if template_path.exists():
            template = json.loads(template_path.read_text())
            if "env_template" in template:
                console.print("\n[yellow]Configure environment variables:[/yellow]")
                for key, value in template["env_template"].items():
                    console.print(f"  {key}={value}")
                console.print("\n[blue]Add to .agentbox/.env or set in your shell[/blue]")
            if "notes" in template:
                console.print(f"\n[blue]Note: {template['notes']}[/blue]")

    # Rebuild container if needed
    if needs_rebuild:
        if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
            console.print("[yellow]MCP added but container rebuild cancelled[/yellow]")
            console.print("[blue]Run 'agentbox rebase' when ready[/blue]")
            return

        console.print("\n[blue]Rebuilding container to apply changes...[/blue]")
        _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
        console.print("[green]✓ Container rebuilt[/green]")


@mcp.command(name="remove")
@click.argument("name", shell_complete=_complete_mcp_names)
@handle_errors
def mcp_remove(name: str):
    """Remove an MCP server from current project."""
    pctx = _get_project_context()

    removed, had_mounts = _remove_mcp(name, pctx)

    if not removed:
        console.print(f"[yellow]MCP server '{name}' not found in project[/yellow]")
        return

    console.print(f"[green]✓ Removed '{name}' MCP server[/green]")

    if had_mounts:
        if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
            console.print("[yellow]MCP removed but container rebuild cancelled[/yellow]")
            console.print("[blue]Run 'agentbox rebase' when ready[/blue]")
            return

        console.print("\n[blue]Rebuilding container to remove mounts...[/blue]")
        _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
        console.print("[green]✓ Container rebuilt[/green]")
