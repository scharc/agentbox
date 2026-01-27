# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Base Docker image commands."""

import os
import subprocess
import sys
from pathlib import Path

import click

from boxctl import __version__ as BOXCTL_VERSION
from boxctl.container import ContainerManager
from boxctl.cli import cli
from boxctl.cli.helpers import console, handle_errors


@cli.group()
def base():
    """Manage the boxctl base Docker image."""
    pass


@base.command()
@handle_errors
def rebuild():
    """Rebuild the boxctl-base:latest Docker image."""
    # Find Dockerfile.base
    package_root = Path(__file__).resolve().parents[3]
    if not (package_root / "Dockerfile.base").is_file():
        raise click.ClickException(
            "Dockerfile.base not found. Run from the boxctl repo or build manually:\n"
            "  docker build -f Dockerfile.base -t boxctl-base:latest ."
        )

    console.print(f"[blue]Rebuilding base image from {package_root}...[/blue]")
    try:
        result = subprocess.run(
            [
                "docker",
                "build",
                "-f",
                str(package_root / "Dockerfile.base"),
                "-t",
                ContainerManager.BASE_IMAGE,
                "--build-arg",
                f"BOXCTL_VERSION={BOXCTL_VERSION}",
                str(package_root),
            ],
            check=False,
        )
    finally:
        # Reset terminal after docker build (progress indicators can corrupt terminal)
        os.system("stty sane 2>/dev/null")
        sys.stdout.write("\033[?25h")  # Show cursor
        sys.stdout.write("\033[0m")  # Reset colors/attributes
        sys.stdout.write("\033[?7h")  # Re-enable line wrapping
        sys.stdout.write("\033[?1049l")  # Exit alternate screen buffer (if entered)
        sys.stdout.write("\n")  # Ensure we're on a new line
        sys.stdout.flush()
    if result.returncode != 0:
        console.print("[red]Docker build failed.[/red]")
        sys.exit(result.returncode)
    console.print("[green]✓ Base image rebuilt[/green]")
