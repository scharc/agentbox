# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Package management commands."""

from pathlib import Path

import click
from rich.table import Table

import agentbox.cli as cli_module
from agentbox.config import ProjectConfig
from agentbox.cli import cli
from agentbox.cli.helpers import (
    _get_project_context,
    _load_packages_config,
    _rebuild_container,
    _require_agentbox_dir,
    _save_packages_config,
    _warn_if_agents_running,
    console,
    handle_errors,
)
from agentbox.utils.project import resolve_project_dir, get_agentbox_dir


@cli.group(name="packages")
def packages_group():
    """Manage project package installations."""
    pass


@packages_group.command(name="list")
@handle_errors
def packages_list():
    """List configured packages for this project."""
    project_dir = resolve_project_dir()
    agentbox_dir = get_agentbox_dir(project_dir)
    _require_agentbox_dir(agentbox_dir, project_dir)

    packages = _load_packages_config(agentbox_dir)

    has_packages = any(packages[key] for key in ["npm", "pip", "apt", "cargo", "post"])

    if not has_packages:
        console.print("[yellow]No packages configured[/yellow]")
        console.print("\n[blue]Add packages with:[/blue]")
        console.print("  agentbox packages add npm <package>")
        console.print("  agentbox packages add pip <package>")
        console.print("  agentbox packages add apt <package>")
        console.print("  agentbox packages add cargo <package>")
        return

    table = Table(title="Project Packages")
    table.add_column("Type", style="cyan")
    table.add_column("Packages", style="white")

    if packages["npm"]:
        table.add_row("npm", ", ".join(packages["npm"]))
    if packages["pip"]:
        table.add_row("pip", ", ".join(packages["pip"]))
    if packages["apt"]:
        table.add_row("apt", ", ".join(packages["apt"]))
    if packages["cargo"]:
        table.add_row("cargo", ", ".join(packages["cargo"]))
    if packages["post"]:
        for i, cmd in enumerate(packages["post"], 1):
            table.add_row(f"post-{i}", cmd)

    console.print(table)
    console.print("\n[dim]Packages are installed when you add them or run 'agentbox rebase'[/dim]")


@packages_group.command(name="add")
@click.argument("package_type", type=click.Choice(["npm", "pip", "apt", "cargo", "post"]))
@click.argument("package")
@handle_errors
def packages_add(package_type: str, package: str):
    """Add a package to the project.

    Examples:
      agentbox packages add npm typescript
      agentbox packages add pip black
      agentbox packages add apt neovim
      agentbox packages add cargo ripgrep
      agentbox packages add post "curl -sSL https://example.com/install.sh | bash"
    """
    project_dir = resolve_project_dir()
    agentbox_dir = get_agentbox_dir(project_dir)
    _require_agentbox_dir(agentbox_dir, project_dir)

    packages = _load_packages_config(agentbox_dir)

    # Check if already exists
    if package in packages[package_type]:
        console.print(f"[yellow]Package '{package}' already in {package_type} list[/yellow]")
        return

    # Add package
    packages[package_type].append(package)
    _save_packages_config(agentbox_dir, packages)

    console.print(f"[green]✓ Added '{package}' to {package_type} packages[/green]")

    # Rebuild container if it exists
    pctx = _get_project_context()
    if pctx.manager.container_exists(pctx.container_name):
        if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
            console.print("[yellow]Package added but container rebuild cancelled[/yellow]")
            console.print("[blue]Run 'agentbox rebase' when ready to install[/blue]")
            return

        console.print("\n[blue]Rebuilding container to install package...[/blue]")
        _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
        console.print("[green]✓ Container rebuilt[/green]")
    else:
        console.print("[dim]Package will be installed when container is created[/dim]")


@packages_group.command(name="remove")
@click.argument("package_type", type=click.Choice(["npm", "pip", "apt", "cargo", "post"]))
@click.argument("package")
@handle_errors
def packages_remove(package_type: str, package: str):
    """Remove a package from the project."""
    project_dir = resolve_project_dir()
    agentbox_dir = get_agentbox_dir(project_dir)
    _require_agentbox_dir(agentbox_dir, project_dir)

    packages = _load_packages_config(agentbox_dir)

    # Check if exists
    if package not in packages[package_type]:
        console.print(f"[yellow]Package '{package}' not in {package_type} list[/yellow]")
        return

    # Remove package
    packages[package_type] = [p for p in packages[package_type] if p != package]
    _save_packages_config(agentbox_dir, packages)

    console.print(f"[green]✓ Removed '{package}' from {package_type} packages[/green]")

    # Rebuild container if it exists (to get clean state without the package)
    pctx = _get_project_context()
    if pctx.manager.container_exists(pctx.container_name):
        if not _warn_if_agents_running(pctx.manager, pctx.container_name, "container rebuild"):
            console.print("[yellow]Package removed but container rebuild cancelled[/yellow]")
            console.print("[blue]Run 'agentbox rebase' when ready to apply[/blue]")
            return

        console.print("\n[blue]Rebuilding container to apply changes...[/blue]")
        _rebuild_container(pctx.manager, pctx.project_name, pctx.project_dir, pctx.container_name)
        console.print("[green]✓ Container rebuilt[/green]")


@packages_group.command(name="init")
@handle_errors
def packages_init():
    """Initialize packages section in .agentbox/config.yml with empty configuration."""
    project_dir = resolve_project_dir()
    agentbox_dir = get_agentbox_dir(project_dir)
    _require_agentbox_dir(agentbox_dir, project_dir)

    config_path = project_dir / ".agentbox/config.yml"
    config = ProjectConfig(project_dir)
    if "packages" in config.config:
        console.print("[yellow]packages already configured in .agentbox/config.yml[/yellow]")
        return

    # Create empty packages config
    packages = {"npm": [], "pip": [], "apt": [], "cargo": [], "post": []}
    _save_packages_config(agentbox_dir, packages)

    console.print("[green]✓ Initialized packages in .agentbox/config.yml[/green]")
    console.print(f"\n[blue]Location:[/blue] {config_path}")
    console.print("\n[blue]Add packages with:[/blue]")
    console.print("  agentbox packages add npm <package>")
    console.print("  agentbox packages add pip <package>")
    console.print("  agentbox packages add apt <package>")
