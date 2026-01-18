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


def _is_docker_enabled(config: ProjectConfig) -> bool:
    """Check if docker socket is enabled in config."""
    # Check the docker.enabled field
    if config._model and hasattr(config._model, 'docker'):
        return config._model.docker.enabled if config._model.docker else False
    return config.config.get("docker", {}).get("enabled", False)


def _enable_docker(config: ProjectConfig) -> bool:
    """Enable docker socket in config. Returns True if changed."""
    if _is_docker_enabled(config):
        return False

    # Update the model if it exists
    if config._model:
        if not config._model.docker:
            from agentbox.models.project_config import DockerConfigModel
            config._model.docker = DockerConfigModel(enabled=True)
        else:
            config._model.docker.enabled = True

        # Remove legacy device entries
        config._model.devices = [d for d in config._model.devices if DOCKER_SOCKET not in d]
    else:
        if "docker" not in config.config:
            config.config["docker"] = {}
        config.config["docker"]["enabled"] = True

        # Remove legacy device entries
        if "devices" in config.config:
            config.config["devices"] = [d for d in config.config["devices"] if DOCKER_SOCKET not in d]

    config.save()
    return True


def _disable_docker(config: ProjectConfig) -> bool:
    """Disable docker socket in config. Returns True if changed."""
    if not _is_docker_enabled(config):
        return False

    # Update the model if it exists
    if config._model and config._model.docker:
        config._model.docker.enabled = False
    else:
        if "docker" in config.config:
            config.config["docker"]["enabled"] = False

    config.save()
    return True


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
            f"No .agentbox.yml found in {project_dir}. Run: agentbox init"
        )

    # Check if docker socket exists on host
    if not Path(DOCKER_SOCKET).exists():
        console.print(f"[yellow]Warning: {DOCKER_SOCKET} not found on host[/yellow]")
        console.print("[dim]Docker daemon may not be running[/dim]")

    if _enable_docker(config):
        console.print("[green]✓ Docker socket enabled[/green]")
        console.print(f"[dim]Socket will be mounted as volume: {DOCKER_SOCKET}[/dim]")
        console.print("\n[yellow]Restart container for changes to take effect:[/yellow]")
        console.print("  agentbox rebase")
    else:
        console.print("[blue]Docker socket already enabled[/blue]")


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
            f"No .agentbox.yml found in {project_dir}. Run: agentbox init"
        )

    if _disable_docker(config):
        console.print("[green]✓ Docker socket disabled[/green]")
        console.print("\n[yellow]Restart container for changes to take effect:[/yellow]")
        console.print("  agentbox rebase")
    else:
        console.print("[blue]Docker socket already disabled[/blue]")


@docker.command(name="status")
@handle_errors
def docker_status():
    """Show Docker socket access status."""
    project_dir = resolve_project_dir()
    config = ProjectConfig(project_dir)

    if not config.exists():
        raise click.ClickException(
            f"No .agentbox.yml found in {project_dir}. Run: agentbox init"
        )

    enabled = _is_docker_enabled(config)
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

    # Check for legacy device entry
    devices = config.devices
    legacy_entries = [d for d in devices if DOCKER_SOCKET in d]
    if legacy_entries:
        console.print(f"\n[yellow]Note: Found legacy device entry: {legacy_entries}[/yellow]")
        console.print("[dim]Run 'abox docker enable' to migrate to volume mount[/dim]")
