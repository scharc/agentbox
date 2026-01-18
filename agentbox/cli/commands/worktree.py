# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Git worktree management commands for host-side agentbox CLI."""

import sys
from typing import Optional

import click
from rich.table import Table

from agentbox.cli import cli
from agentbox.container import get_abox_environment
from agentbox.cli.helpers import (
    _ensure_container_running,
    _get_project_context,
    _run_agent_command,
    _complete_worktree_branch,
    console,
    handle_errors,
)
from agentbox.cli.commands.agents import (
    _has_vscode,
    _read_agent_instructions,
    _read_super_prompt,
)


def _exec_worktree_command(manager, container_name: str, args: list[str]) -> tuple[int, str]:
    """Execute agentctl worktree command in container."""
    cmd = ["agentctl", "worktree"] + args
    exit_code, output = manager.exec_command(
        container_name,
        cmd,
        environment=get_abox_environment(include_tmux=True, container_name=container_name),
        user="abox",
        workdir="/workspace",
    )
    return exit_code, output


@cli.group(name="worktree")
def worktree_group():
    """Git worktree management.

    Manage git worktrees for multi-branch parallel development.
    Create, list, and remove worktrees with automatic metadata tracking.

    Examples:
        abox worktree add feature-auth          # Create worktree
        abox worktree claude feature-auth       # Run Claude in worktree
        abox worktree superclaude feature-auth  # Run superclaude in worktree
        abox worktree list                      # List all worktrees
        abox worktree remove feature-auth       # Remove worktree
    """
    pass


# Add shortcut alias - register the same group under a different name
cli.add_command(worktree_group, name="wt")


@worktree_group.command(name="list")
@click.argument("format", required=False, type=click.Choice(["json"]))
@handle_errors
def worktree_list(format: Optional[str]):
    """List all git worktrees.

    FORMAT: Use "json" for machine-readable output

    Shows all git worktrees with their paths, branches, and associated sessions.

    Examples:
        abox worktree list
        abox worktree list json
    """
    pctx = _get_project_context()
    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Container {pctx.container_name} is not running")

    args = ["list"]
    if format == "json":
        args.append("--json")

    exit_code, output = _exec_worktree_command(pctx.manager, pctx.container_name, args)
    if output:
        click.echo(output.rstrip())
    sys.exit(exit_code)


@worktree_group.command(name="add")
@click.argument("branch")
@handle_errors
def worktree_add(branch: str):
    """Create a new git worktree.

    BRANCH: Name of the branch to check out in the worktree

    Creates a new worktree for the specified branch.
    If the branch doesn't exist, it will be created automatically.

    Examples:
        abox worktree add feature-auth
        abox worktree add bugfix-123
    """
    pctx = _get_project_context()
    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Container {pctx.container_name} is not running")

    # Check if branch exists
    exit_code, _ = pctx.manager.exec_command(
        pctx.container_name,
        ["git", "-C", "/workspace", "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        user="abox",
    )
    branch_exists = exit_code == 0

    args = ["add", branch]
    if not branch_exists:
        args.append("--create")

    exit_code, output = _exec_worktree_command(pctx.manager, pctx.container_name, args)
    if output:
        click.echo(output.rstrip())
    sys.exit(exit_code)


@worktree_group.command(name="remove")
@click.argument("branch_or_path", shell_complete=_complete_worktree_branch)
@click.argument("mode", required=False, type=click.Choice(["force"]))
@handle_errors
def worktree_remove(branch_or_path: str, mode: Optional[str]):
    """Remove a git worktree.

    BRANCH_OR_PATH: Branch name or worktree path to remove
    MODE: Use "force" to remove even with uncommitted changes

    Removes the specified worktree and cleans up metadata.

    Examples:
        abox worktree remove feature-auth
        abox worktree remove feature-auth force
    """
    pctx = _get_project_context()
    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Container {pctx.container_name} is not running")

    args = ["remove", branch_or_path]
    if mode == "force":
        args.append("--force")

    exit_code, output = _exec_worktree_command(pctx.manager, pctx.container_name, args)
    if output:
        click.echo(output.rstrip())
    sys.exit(exit_code)


@worktree_group.command(name="prune")
@handle_errors
def worktree_prune():
    """Remove stale worktree metadata.

    Cleans up metadata for worktrees that no longer exist in git.
    Useful after manually removing worktree directories.
    """
    pctx = _get_project_context()
    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Container {pctx.container_name} is not running")

    exit_code, output = _exec_worktree_command(pctx.manager, pctx.container_name, ["prune"])
    if output:
        click.echo(output.rstrip())
    sys.exit(exit_code)


@worktree_group.command(name="shell")
@click.argument("branch", shell_complete=_complete_worktree_branch)
@handle_errors
def worktree_shell(branch: str):
    """Open a shell in a worktree directory.

    BRANCH: Branch name of the worktree to enter

    Opens an interactive shell in the specified worktree directory.
    From there you can start agents with agentctl.

    Examples:
        abox worktree shell feature-auth
    """
    import subprocess

    pctx = _get_project_context()
    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Container {pctx.container_name} is not running")

    # Construct worktree path
    worktree_path = f"/git-worktrees/worktree-{branch}"

    # Verify worktree exists
    exit_code, output = pctx.manager.exec_command(
        pctx.container_name,
        ["test", "-d", worktree_path],
        user="abox",
    )
    if exit_code != 0:
        raise click.ClickException(
            f"Worktree not found: {worktree_path}. Use 'abox worktree ls' to see available worktrees"
        )

    # Start interactive shell in worktree
    console.print(f"[green]Entering worktree: {branch}[/green]")
    console.print(f"[dim]Working directory: {worktree_path}[/dim]")
    console.print("[dim]Start an agent with: agentctl a claude[/dim]\n")

    subprocess.run(
        [
            "docker", "exec", "-it",
            "-u", "abox",
            "-w", worktree_path,
            pctx.container_name,
            "/bin/bash"
        ],
        check=False
    )


def _get_worktree_path(branch: str) -> str:
    """Get the worktree path for a branch."""
    return f"/git-worktrees/worktree-{branch}"


def _verify_worktree_exists(manager, container_name: str, worktree_path: str) -> bool:
    """Verify a worktree directory exists."""
    exit_code, _ = manager.exec_command(
        container_name,
        ["test", "-d", worktree_path],
        user="abox",
    )
    return exit_code == 0


@worktree_group.command(name="claude")
@click.argument("branch", shell_complete=_complete_worktree_branch)
@click.argument("args", nargs=-1)
@handle_errors
def worktree_claude(branch: str, args: tuple):
    """Run Claude Code in a worktree.

    BRANCH: Branch name of the worktree to work in

    Starts Claude Code with the working directory set to the worktree.
    Uses the same configuration as the normal claude command.

    Examples:
        abox worktree claude feature-auth
        abox worktree claude feature-auth "implement login"
    """
    pctx = _get_project_context()
    worktree_path = _get_worktree_path(branch)

    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Container {pctx.container_name} is not running")

    if not _verify_worktree_exists(pctx.manager, pctx.container_name, worktree_path):
        raise click.ClickException(
            f"Worktree not found: {worktree_path}. Create it with 'abox worktree add {branch}'"
        )

    instructions = _read_agent_instructions()
    extra_args = [
        "--settings", "/home/abox/.claude/config.json",
        "--mcp-config", "/workspace/.agentbox/claude/mcp.json",
        "--append-system-prompt", instructions,
    ]

    if _has_vscode():
        extra_args.append("--ide")

    _run_agent_command(
        pctx.manager,
        None,  # Uses current project
        args,
        "claude",
        extra_args=extra_args,
        label=f"Claude Code ({branch})",
        reuse_tmux_session=True,
        session_key=f"claude-{branch}",
        workdir=worktree_path,
    )


@worktree_group.command(name="superclaude")
@click.argument("branch", shell_complete=_complete_worktree_branch)
@click.argument("args", nargs=-1)
@handle_errors
def worktree_superclaude(branch: str, args: tuple):
    """Run Claude Code with auto-approve in a worktree.

    BRANCH: Branch name of the worktree to work in

    Starts Claude Code with auto-approve permissions in the worktree.

    Examples:
        abox worktree superclaude feature-auth
        abox worktree superclaude feature-auth "implement login"
    """
    pctx = _get_project_context()
    worktree_path = _get_worktree_path(branch)

    if not _ensure_container_running(pctx.manager, pctx.container_name):
        raise click.ClickException(f"Container {pctx.container_name} is not running")

    if not _verify_worktree_exists(pctx.manager, pctx.container_name, worktree_path):
        raise click.ClickException(
            f"Worktree not found: {worktree_path}. Create it with 'abox worktree add {branch}'"
        )

    prompt = _read_super_prompt()
    extra_args = [
        "--settings", "/home/abox/.claude/config-super.json",
        "--mcp-config", "/workspace/.agentbox/claude/mcp.json",
        "--dangerously-skip-permissions",
        "--append-system-prompt", prompt,
    ]

    if _has_vscode():
        extra_args.append("--ide")

    _run_agent_command(
        pctx.manager,
        None,  # Uses current project
        args,
        "claude",
        extra_args=extra_args,
        label=f"Claude Code auto-approve ({branch})",
        reuse_tmux_session=True,
        session_key=f"superclaude-{branch}",
        persist_session=False,
        workdir=worktree_path,
    )
