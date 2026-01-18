# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Tmux session management commands."""

from typing import Optional

import click
from rich.table import Table

from agentbox.cli import cli
from agentbox.container import get_abox_environment
from agentbox.utils.terminal import reset_terminal
from agentbox.utils.project import resolve_project_dir
from agentbox.cli.helpers import (
    _attach_tmux_session,
    _complete_connect_session,
    _complete_session_name,
    _ensure_container_running,
    _generate_session_name,
    _get_agent_sessions,
    _get_project_context,
    _get_tmux_sessions,
    _get_tmux_socket,
    _require_container_running,
    _sanitize_tmux_name,
    _session_exists,
    console,
    handle_errors,
)


@cli.group()
def session():
    """Manage tmux sessions in containers."""
    pass


@session.command(name="new")
@click.argument("agent_type", type=click.Choice([
    "claude", "superclaude", "codex", "supercodex", "gemini", "supergemini", "shell"
]))
@click.argument("name", required=False)
@handle_errors
def session_new(agent_type: str, name: Optional[str]):
    """Create a new agent session with custom name or auto-numbered.

    Creates a new tmux session for the specified agent type.

    Examples:
        abox session new superclaude              # Creates superclaude-1
        abox session new superclaude "feature 1"  # Creates superclaude-feature-1
        abox session new codex mcp-receiver       # Creates codex-mcp-receiver
    """
    # Check if current directory is initialized
    from agentbox.config import ProjectConfig

    project_dir = resolve_project_dir()
    config = ProjectConfig(project_dir)

    if not config.exists():
        raise click.ClickException(
            f"Current directory is not initialized: {project_dir}. Run: agentbox init"
        )

    # Import agent-specific functions
    from agentbox.cli.commands.agents import (
        _read_agent_instructions,
        _read_super_prompt,
        _has_vscode,
    )
    from agentbox.cli.helpers import _run_agent_command

    pctx = _get_project_context()

    # Ensure container is running (will create if needed)
    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Failed to start container {pctx.container_name}")

    # Generate session name
    session_name = _generate_session_name(pctx.manager, pctx.container_name, agent_type, name)

    # Check if session already exists
    if _session_exists(pctx.manager, pctx.container_name, session_name):
        raise click.ClickException(
            f"Session '{session_name}' already exists. Attach with: abox session attach {session_name}"
        )

    # Prepare agent-specific settings
    command = None
    extra_args = []
    label = None
    persist_session = False

    if agent_type == "claude":
        command = "claude"
        label = f"Claude Code ({session_name})"
        instructions = _read_agent_instructions()
        extra_args = [
            "--settings", "/home/abox/.claude/config.json",
            "--mcp-config", "/workspace/.agentbox/claude/mcp.json",
            "--append-system-prompt", instructions,
        ]
        if _has_vscode():
            extra_args.append("--ide")

    elif agent_type == "superclaude":
        command = "claude"
        label = f"Claude Code (auto-approve, {session_name})"
        prompt = _read_super_prompt()
        extra_args = [
            "--settings", "/home/abox/.claude/config-super.json",
            "--mcp-config", "/workspace/.agentbox/claude/mcp.json",
            "--dangerously-skip-permissions",
            "--append-system-prompt", prompt,
        ]
        if _has_vscode():
            extra_args.append("--ide")
        persist_session = False

    elif agent_type == "codex":
        command = "codex"
        label = f"Codex ({session_name})"

    elif agent_type == "supercodex":
        command = "codex"
        label = f"Codex (auto-approve, {session_name})"
        extra_args = ["--dangerously-bypass-approvals-and-sandbox"]
        persist_session = False

    elif agent_type == "gemini":
        command = "gemini"
        label = f"Gemini ({session_name})"

    elif agent_type == "supergemini":
        command = "gemini"
        label = f"Gemini (auto-approve, {session_name})"
        extra_args = ["--non-interactive"]
        persist_session = False

    elif agent_type == "shell":
        command = "/bin/bash"
        label = f"Shell ({session_name})"

    # Create and attach to new session
    console.print(f"[green]Creating session: {session_name}[/green]")
    _run_agent_command(
        pctx.manager,
        None,  # Uses current project (auto-detected)
        tuple(),  # No additional args
        command,
        extra_args=extra_args,
        label=label,
        reuse_tmux_session=False,  # Force new session
        persist_session=persist_session,
        custom_session_name=session_name,
    )


def _complete_list_scope(ctx, param, incomplete):
    """Shell completion for list scope."""
    return [c for c in ["all"] if c.startswith(incomplete)]


@session.command(name="list")
@click.argument("scope", required=False, type=click.Choice(["all"]), shell_complete=_complete_list_scope)
@handle_errors
def session_list(scope: Optional[str]):
    """List tmux sessions with agent types and identifiers.

    SCOPE: Use "all" to list sessions across all containers.

    Examples:
        abox session list       # List sessions in current project
        abox session list all   # List sessions in all containers
    """
    pctx = _get_project_context()

    if scope == "all":
        # List sessions across all containers
        all_containers = pctx.manager.client.containers.list(
            filters={"name": "agentbox-"}
        )

        if not all_containers:
            console.print("[yellow]No agentbox containers found[/yellow]")
            return

        all_sessions = []
        for container in all_containers:
            cname = container.name
            if not cname.startswith("agentbox-"):
                continue

            # Extract project name (strip "agentbox-" prefix)
            project_name = cname[9:] if cname.startswith("agentbox-") else cname

            sessions = _get_tmux_sessions(pctx.manager, cname)
            for sess in sessions:
                all_sessions.append({
                    "project": project_name,
                    "session": sess["name"],
                    "status": "attached" if sess["attached"] else "detached",
                    "windows": sess["windows"]
                })

        if not all_sessions:
            console.print("[yellow]No tmux sessions found in any container[/yellow]")
            return

        table = Table(title="All Agentbox Sessions")
        table.add_column("Project", style="cyan")
        table.add_column("Session", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Windows", style="blue")

        for sess in all_sessions:
            table.add_row(
                sess["project"],
                sess["session"],
                sess["status"],
                str(sess["windows"])
            )

        console.print(table)
        console.print("\n[blue]Connect:[/blue] abox connect <project> <session>")
    else:
        # List sessions in current project only
        if not pctx.manager.is_running(pctx.container_name):
            console.print(f"[red]Container {pctx.container_name} is not running[/red]")
            console.print("[blue]Start it with: agentbox start[/blue]")
            return

        table = Table(title="Agentbox Tmux Sessions")
        table.add_column("Session", style="magenta")
        table.add_column("Agent Type", style="cyan")
        table.add_column("Identifier", style="yellow")
        table.add_column("Attached", style="green")
        table.add_column("Windows", style="blue")

        sessions = _get_agent_sessions(pctx.manager, pctx.container_name)
        if not sessions:
            console.print("[yellow]No tmux sessions found[/yellow]")
            return

        for session_entry in sessions:
            table.add_row(
                session_entry["name"],
                session_entry["agent_type"],
                session_entry["identifier"],
                "yes" if session_entry["attached"] else "no",
                str(session_entry["windows"]),
            )

        console.print(table)
        console.print("\n[blue]Attach to session:[/blue] abox session attach <session-name>")
        console.print("[blue]Create new session:[/blue] abox session new <agent-type> [name]")


@session.command(name="remove")
@click.argument("session_name", shell_complete=_complete_session_name)
@handle_errors
def session_remove(session_name: str):
    """Kill a tmux session inside a container."""
    pctx = _get_project_context()
    _require_container_running(pctx.manager, pctx.container_name)

    socket_path = _get_tmux_socket(pctx.manager, pctx.container_name)
    tmux_cmd = ["/usr/bin/tmux", "kill-session", "-t", session_name]
    if socket_path:
        tmux_cmd = ["/usr/bin/tmux", "-S", socket_path, "kill-session", "-t", session_name]
    exit_code, output = pctx.manager.exec_command(
        pctx.container_name,
        tmux_cmd,
        environment=get_abox_environment(include_tmux=True, container_name=pctx.container_name),
        user="abox",
    )
    if exit_code != 0:
        msg = f"Failed to remove tmux session {session_name}"
        if output.strip():
            msg += f": {output.strip()}"
        raise click.ClickException(msg)

    # Reset terminal in case user was attached to this session
    reset_terminal()
    console.print(f"[green]Removed tmux session {session_name} from {pctx.container_name}[/green]")


@session.command(name="rename")
@click.argument("old_name", shell_complete=_complete_session_name)
@click.argument("new_identifier")
@handle_errors
def session_rename(old_name: str, new_identifier: str):
    """Rename a session's identifier while preserving agent type.

    Examples:
        abox session rename superclaude-1 feature-auth
        # Renames to: superclaude-feature-auth
    """
    pctx = _get_project_context()
    _require_container_running(pctx.manager, pctx.container_name)

    # Check if old session exists
    sessions = _get_agent_sessions(pctx.manager, pctx.container_name)
    old_session = next((s for s in sessions if s["name"] == old_name), None)

    if not old_session:
        raise click.ClickException(f"Session '{old_name}' not found")

    # Generate new name with same agent type
    agent_type = old_session["agent_type"]
    new_name = f"{agent_type}-{_sanitize_tmux_name(new_identifier)}"

    # Check if new name already exists
    if _session_exists(pctx.manager, pctx.container_name, new_name):
        raise click.ClickException(f"Session '{new_name}' already exists")

    # Rename session using tmux
    socket_path = _get_tmux_socket(pctx.manager, pctx.container_name)
    tmux_cmd = ["/usr/bin/tmux", "rename-session", "-t", old_name, new_name]
    if socket_path:
        tmux_cmd = ["/usr/bin/tmux", "-S", socket_path, "rename-session", "-t", old_name, new_name]

    exit_code, output = pctx.manager.exec_command(
        pctx.container_name,
        tmux_cmd,
        environment=get_abox_environment(include_tmux=True, container_name=pctx.container_name),
        user="abox",
    )

    if exit_code != 0:
        msg = "Failed to rename session"
        if output.strip():
            msg += f": {output.strip()}"
        raise click.ClickException(msg)

    console.print(f"[green]Renamed '{old_name}' to '{new_name}'[/green]")


@session.command(name="attach")
@click.argument("session_name", shell_complete=_complete_session_name)
@handle_errors
def session_attach(session_name: str):
    """Attach to a tmux session inside the project container."""
    pctx = _get_project_context()
    _require_container_running(pctx.manager, pctx.container_name)

    _attach_tmux_session(pctx.manager, pctx.container_name, session_name)


