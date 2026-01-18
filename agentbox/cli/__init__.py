# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Agentbox CLI package."""

import click

from agentbox.container import ContainerManager

from agentbox.cli.helpers import console
from agentbox.cli.helpers import (
    BANNER,
    LOG_DOC_NAME,
    WORKSPACES_CONFIG_NAME,
    WORKSPACES_MOUNT_ROOT,
    _attach_tmux_session,
    _complete_session_name,
    _ensure_container_running,
    _get_tmux_sessions,
    _get_tmux_socket,
    _load_codex_config,
    _load_workspaces_config,
    _resolve_container_and_args,
    _resolve_tmux_prefix,
    _run_agent_command,
    _sanitize_mount_name,
    _sanitize_tmux_name,
    _save_workspaces_config,
)
from agentbox.cli.helpers.completions import (
    _complete_project_name,
    _complete_connect_session,
)


@click.group(invoke_without_command=True)
@click.version_option(version="0.2.0")
def cli():
    """Agentbox - Secure, isolated Docker environment for Claude Code."""
    ctx = click.get_current_context()
    if ctx.invoked_subcommand is None:
        click.echo("Usage: agentbox [OPTIONS] COMMAND [ARGS]...\n")

        def _print_table(title: str, rows: list[tuple[str, str]], width: int) -> None:
            click.echo(f"{title}:")
            for name, desc in rows:
                click.echo(f"  {name.ljust(width)}  {desc}")
            click.echo("")

        groups = [
            ("Agents", [
                ("claude", "Run Claude Code"),
                ("superclaude", "Run Claude Code (auto-approve)"),
                ("codex", "Run Codex"),
                ("supercodex", "Run Codex (auto-approve)"),
                ("gemini", "Run Gemini"),
                ("supergemini", "Run Gemini (auto-approve)"),
            ]),
            ("Quick Commands", [
                ("quick/q", "Mobile-friendly TUI menu"),
                ("start", "Start container for current project"),
                ("stop", "Stop container"),
                ("list/ps", "List containers"),
                ("shell", "Open shell in container"),
                ("connect", "Connect to container/session"),
                ("info", "Show container details"),
                ("rebase", "Rebase project container to current base"),
                ("remove", "Remove container"),
                ("cleanup", "Remove stopped containers"),
                ("setup", "Initialize + configure interactively"),
                ("init", "Initialize .agentbox/ directory"),
                ("reconfigure", "Change agent/project settings"),
                ("rebuild", "Rebuild base Docker image"),
            ]),
            ("Command Groups", [
                ("project", "Lifecycle (init/start/stop/rebase/remove/info/list)"),
                ("session", "Tmux sessions (new/list/attach/remove/rename)"),
                ("worktree/wt", "Git worktrees (ls/add/remove/prune)"),
                ("network", "Connect to containers (list/available/connect/disconnect)"),
                ("base", "Base image (rebuild)"),
            ]),
            ("Libraries & Config", [
                ("mcp/mcps", "MCP servers (manage/list/show/add/remove)"),
                ("skill/skills", "Skills (manage/list/show/add/remove)"),
                ("workspace", "Workspace mounts (list/add/remove)"),
                ("packages", "Package management (list/add/remove)"),
                ("ports", "Port forwarding (list/add/remove/status)"),
                ("devices", "Device passthrough (list/add/remove/choose)"),
                ("docker", "Docker socket access (enable/disable/status)"),
                ("config", "Config utilities (migrate)"),
            ]),
            ("Service", [
                ("service", "Host daemon (install/start/stop/status/logs/serve)"),
            ]),
        ]

        width = max(len(name) for _, rows in groups for name, _ in rows)
        for title, rows in groups:
            _print_table(title, rows, width)
        click.echo("Use --help for full command details.")
        return


def main():
    """Main entry point."""
    cli()


from agentbox.cli.commands import agents  # noqa: E402,F401
from agentbox.cli.commands import base  # noqa: E402,F401
from agentbox.cli.commands import devices  # noqa: E402,F401
from agentbox.cli.commands import docker  # noqa: E402,F401
from agentbox.cli.commands import mcp  # noqa: E402,F401
from agentbox.cli.commands import network  # noqa: E402,F401
from agentbox.cli.commands import packages  # noqa: E402,F401
from agentbox.cli.commands import ports  # noqa: E402,F401
from agentbox.cli.commands import project  # noqa: E402,F401
from agentbox.cli.commands import service  # noqa: E402,F401
from agentbox.cli.commands import sessions  # noqa: E402,F401
from agentbox.cli.commands import skill  # noqa: E402,F401
from agentbox.cli.commands import worktree  # noqa: E402,F401
from agentbox.cli.commands import workspace  # noqa: E402,F401
from agentbox.cli.commands import quick  # noqa: E402,F401


# Shortcut commands that delegate to command groups
# These provide convenient top-level aliases for common operations


@cli.command("start")
def start_shortcut():
    """Start container for current project (shortcut for: project start)."""
    from agentbox.cli.commands.project import start
    ctx = click.get_current_context()
    ctx.invoke(start)


@cli.command("stop")
@click.argument("project_name", required=False, shell_complete=_complete_project_name)
def stop_shortcut(project_name):
    """Stop the project container (shortcut for: project stop)."""
    from agentbox.cli.commands.project import stop
    ctx = click.get_current_context()
    ctx.invoke(stop, project_name=project_name)


@cli.command("list")
@click.argument("show_all", required=False)
def list_shortcut(show_all):
    """List all agentbox containers (shortcut for: project list)."""
    from agentbox.cli.commands.project import list as project_list
    ctx = click.get_current_context()
    ctx.invoke(project_list, show_all=show_all)


@cli.command("ps")
@click.argument("show_all", required=False)
def ps_shortcut(show_all):
    """List all agentbox containers (alias for: list)."""
    from agentbox.cli.commands.project import list as project_list
    ctx = click.get_current_context()
    ctx.invoke(project_list, show_all=show_all)


@cli.command("shell")
@click.argument("project_name", required=False, shell_complete=_complete_project_name)
def shell_shortcut(project_name):
    """Open interactive shell in container (shortcut for: project shell)."""
    from agentbox.cli.commands.project import shell
    ctx = click.get_current_context()
    ctx.invoke(shell, project_name=project_name)


@cli.command("connect")
@click.argument("project_name", required=False, shell_complete=_complete_project_name)
@click.argument("session", required=False, shell_complete=_complete_connect_session)
def connect_shortcut(project_name, session):
    """Connect to container (shortcut for: project connect)."""
    from agentbox.cli.commands.project import connect
    ctx = click.get_current_context()
    ctx.invoke(connect, project_name=project_name, session=session)


@cli.command("info")
@click.argument("project_name", required=False, shell_complete=_complete_project_name)
def info_shortcut(project_name):
    """Show container info (shortcut for: project info)."""
    from agentbox.cli.commands.project import info
    ctx = click.get_current_context()
    ctx.invoke(info, project_name=project_name)


@cli.command("remove")
@click.argument("project_name", required=False, shell_complete=_complete_project_name)
@click.argument("force_remove", required=False)
def remove_shortcut(project_name, force_remove):
    """Remove the project container (shortcut for: project remove)."""
    from agentbox.cli.commands.project import remove
    ctx = click.get_current_context()
    ctx.invoke(remove, project_name=project_name, force_remove=force_remove)


@cli.command("cleanup")
def cleanup_shortcut():
    """Remove all stopped containers (shortcut for: project cleanup)."""
    from agentbox.cli.commands.project import cleanup
    ctx = click.get_current_context()
    ctx.invoke(cleanup)


@cli.command("rebase")
@click.argument("scope", required=False)
def rebase_shortcut(scope: str):
    """Rebase project container to current base (shortcut for: project rebase).

    Pass 'all' as argument to rebase all existing containers.
    """
    from agentbox.cli.commands.project import rebase
    ctx = click.get_current_context()
    ctx.invoke(rebase, scope=scope)


@cli.command("init")
def init_shortcut():
    """Initialize .agentbox/ directory (shortcut for: project init)."""
    from agentbox.cli.commands.project import init
    ctx = click.get_current_context()
    ctx.invoke(init)


@cli.command("setup")
def setup_shortcut():
    """Initialize and configure agentbox (shortcut for: project setup)."""
    from agentbox.cli.commands.project import setup
    ctx = click.get_current_context()
    ctx.invoke(setup)


@cli.command("reconfigure")
def reconfigure_shortcut():
    """Reconfigure agent and project settings (shortcut for: project reconfigure)."""
    from agentbox.cli.commands.project import reconfigure
    ctx = click.get_current_context()
    ctx.invoke(reconfigure)


@cli.command("rebuild")
def rebuild_shortcut():
    """Rebuild base Docker image (shortcut for: base rebuild)."""
    from agentbox.cli.commands.base import rebuild
    ctx = click.get_current_context()
    ctx.invoke(rebuild)


@cli.command("fix-terminal")
def fix_terminal():
    """Reset terminal to fix mouse mode and other escape sequence issues.

    Use this command when your terminal is in a broken state after
    a container was destroyed or a tmux session was killed unexpectedly.

    This disables mouse tracking mode and resets terminal settings.
    """
    from agentbox.utils.terminal import reset_terminal
    reset_terminal()
    console.print("[green]Terminal reset complete[/green]")


# Register plural aliases for skill and mcp groups
from agentbox.cli.commands.skill import skill as skill_group
from agentbox.cli.commands.mcp import mcp as mcp_group

cli.add_command(skill_group, name="skills")
cli.add_command(mcp_group, name="mcps")


# Config command group for migration and config utilities
@cli.group()
def config():
    """Configuration utilities (migrate)."""
    pass


@config.command("migrate")
@click.option("--dry-run", is_flag=True, help="Show what would be migrated")
@click.option("--auto", is_flag=True, help="Apply all without prompting")
def config_migrate_shortcut(dry_run: bool, auto: bool):
    """Migrate config to latest format (shortcut for: project migrate)."""
    from agentbox.cli.commands.project import config_migrate
    ctx = click.get_current_context()
    ctx.invoke(config_migrate, dry_run=dry_run, auto=auto)
