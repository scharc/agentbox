# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Project directory resolution utilities.

This module provides centralized project directory resolution logic.
All CLI commands should use these functions instead of duplicating
the AGENTBOX_PROJECT_DIR environment variable check.
"""

import os
from pathlib import Path
from typing import Optional


def resolve_project_dir(project_dir: Optional[Path] = None) -> Path:
    """Resolve the project directory.

    Resolution order:
    1. Explicit project_dir argument (if provided)
    2. AGENTBOX_PROJECT_DIR environment variable
    3. Current working directory

    Args:
        project_dir: Optional explicit project directory

    Returns:
        Resolved project directory as Path
    """
    if project_dir is not None:
        return project_dir

    env_project_dir = os.getenv("AGENTBOX_PROJECT_DIR")
    if env_project_dir:
        return Path(env_project_dir)

    return Path.cwd()


def get_container_name(project_dir: Optional[Path] = None) -> str:
    """Get the container name for a project.

    Args:
        project_dir: Optional project directory (resolved if not provided)

    Returns:
        Container name in format: agentbox-<project_name>
    """
    resolved = resolve_project_dir(project_dir)
    # Sanitize project name: lowercase, replace special chars
    project_name = resolved.name.lower()
    project_name = "".join(c if c.isalnum() or c == "-" else "-" for c in project_name)
    project_name = project_name.strip("-")
    return f"agentbox-{project_name}"


def find_project_by_container(container_name: str) -> Optional[Path]:
    """Find the project directory for a given container name.

    Args:
        container_name: Container name (e.g., agentbox-steuerung)

    Returns:
        Path to project directory, or None if not found
    """
    import subprocess

    # Try to get workspace mount from running container
    try:
        result = subprocess.run(
            ["docker", "inspect", container_name, "--format",
             "{{range .Mounts}}{{if eq .Destination \"/workspace\"}}{{.Source}}{{end}}{{end}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            project_dir = Path(result.stdout.strip())
            if project_dir.exists():
                return project_dir
    except Exception:
        pass

    # Fallback: extract project name from container name and search common locations
    if container_name.startswith("agentbox-"):
        project_name = container_name[9:]  # Remove "agentbox-" prefix

        # Search in common project locations
        search_paths = [
            Path.home() / "projects",
            Path.home() / "code",
            Path.home() / "src",
            Path("/x/coding"),
            Path.cwd(),
        ]

        for base in search_paths:
            if not base.exists():
                continue
            # Try exact match
            candidate = base / project_name
            if candidate.exists() and (candidate / ".agentbox.yml").exists():
                return candidate
            # Try case-insensitive search
            try:
                for d in base.iterdir():
                    if d.is_dir() and d.name.lower() == project_name.lower():
                        if (d / ".agentbox.yml").exists():
                            return d
            except PermissionError:
                continue

    return None


def get_agentbox_dir(project_dir: Optional[Path] = None) -> Path:
    """Get the .agentbox directory for a project.

    Args:
        project_dir: Optional project directory (resolved if not provided)

    Returns:
        Path to .agentbox directory
    """
    return resolve_project_dir(project_dir) / ".agentbox"


def get_agentbox_yml(project_dir: Optional[Path] = None) -> Path:
    """Get the .agentbox.yml config file path for a project.

    Args:
        project_dir: Optional project directory (resolved if not provided)

    Returns:
        Path to .agentbox.yml file
    """
    return resolve_project_dir(project_dir) / ".agentbox.yml"


def is_initialized(project_dir: Optional[Path] = None) -> bool:
    """Check if a project directory is initialized for agentbox.

    A project is considered initialized if it has a .agentbox directory.

    Args:
        project_dir: Optional project directory (resolved if not provided)

    Returns:
        True if project is initialized, False otherwise
    """
    return get_agentbox_dir(project_dir).exists()
