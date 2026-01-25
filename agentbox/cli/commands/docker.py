# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Docker socket management commands."""

from pathlib import Path

import click

from agentbox.cli import cli
from agentbox.cli.helpers import console, handle_errors
from agentbox.config import ProjectConfig
from agentbox.utils.project import resolve_project_dir

DOCKER_SOCKET = "/var/run/docker.sock"


@cli.group()
def docker():
    """Manage Docker socket access for containers."""
    pass


@docker.command(name="enable")
@handle_errors
def docker_enable():
    """Enable Docker socket access for the container.

    Mounts /var/run/docker.sock into the container, allowing
    agents to run docker commands. Requires container restart.
    """
    project_dir = resolve_project_dir()
    config = ProjectConfig(project_dir)

    if not config.exists():
        raise click.ClickException(
            f"No .agentbox/config.yml found in {project_dir}. Run: agentbox init"
        )

    # Check if docker socket exists on host
    if not Path(DOCKER_SOCKET).exists():
        console.print(f"[yellow]Warning: {DOCKER_SOCKET} not found on host[/yellow]")
        console.print("[dim]Docker daemon may not be running[/dim]")

    if config.docker_enabled:
        console.print("[blue]Docker socket already enabled[/blue]")
    else:
        config.docker_enabled = True
        config.save()
        console.print("[green]✓ Docker socket enabled[/green]")
        console.print(f"[dim]Socket will be mounted as volume: {DOCKER_SOCKET}[/dim]")
        console.print("\n[yellow]Restart container for changes to take effect:[/yellow]")
        console.print("  agentbox rebase")


@docker.command(name="disable")
@handle_errors
def docker_disable():
    """Disable Docker socket access for the container.

    Removes the docker socket mount. Requires container restart.
    """
    project_dir = resolve_project_dir()
    config = ProjectConfig(project_dir)

    if not config.exists():
        raise click.ClickException(
            f"No .agentbox/config.yml found in {project_dir}. Run: agentbox init"
        )

    if not config.docker_enabled:
        console.print("[blue]Docker socket already disabled[/blue]")
    else:
        config.docker_enabled = False
        config.save()
        console.print("[green]✓ Docker socket disabled[/green]")
        console.print("\n[yellow]Restart container for changes to take effect:[/yellow]")
        console.print("  agentbox rebase")


@docker.command(name="status")
@handle_errors
def docker_status():
    """Show Docker socket access status."""
    project_dir = resolve_project_dir()
    config = ProjectConfig(project_dir)

    if not config.exists():
        raise click.ClickException(
            f"No .agentbox/config.yml found in {project_dir}. Run: agentbox init"
        )

    enabled = config.docker_enabled
    socket_exists = Path(DOCKER_SOCKET).exists()

    console.print("[bold]Docker Socket Status[/bold]")
    console.print("")

    if enabled:
        console.print("[green]Config:[/green] Enabled (socket mounted as volume)")
    else:
        console.print("[yellow]Config:[/yellow] Disabled")

    if socket_exists:
        console.print(f"[green]Host:[/green] {DOCKER_SOCKET} exists")
    else:
        console.print(f"[red]Host:[/red] {DOCKER_SOCKET} not found")

    if enabled and not socket_exists:
        console.print("\n[yellow]Warning: Docker enabled but socket not found on host[/yellow]")
        console.print("[dim]Is Docker daemon running?[/dim]")
