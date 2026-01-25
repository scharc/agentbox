# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Project directory resolution utilities.

This module provides centralized project directory resolution logic.
All CLI commands should use these functions instead of duplicating
the AGENTBOX_PROJECT_DIR environment variable check.

For container name resolution, use agentbox.container_naming module directly.
"""

from pathlib import Path
from typing import Optional

from agentbox.paths import ProjectPaths

# Re-export from container_naming
from agentbox.container_naming import (
    resolve_project_dir,
    resolve_container_name,
    get_container_workspace,
    find_container_by_workspace,
    extract_project_name,
    sanitize_name,
    CONTAINER_PREFIX,
)


def find_project_by_container(container_name: str) -> Optional[Path]:
    """Find the project directory for a given container name.

    Args:
        container_name: Container name (e.g., agentbox-steuerung)

    Returns:
        Path to project directory, or None if not found
    """
    # First try to get workspace from container mounts
    workspace = get_container_workspace(container_name)
    if workspace and workspace.exists():
        return workspace

    # Fallback: extract project name and search common locations
    project_name = extract_project_name(container_name)
    if not project_name:
        return None

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
        if candidate.exists() and ProjectPaths.agentbox_dir(candidate).exists():
            return candidate
        # Try case-insensitive search
        try:
            for d in base.iterdir():
                if d.is_dir() and d.name.lower() == project_name.lower():
                    if ProjectPaths.agentbox_dir(d).exists():
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
    return ProjectPaths.agentbox_dir(resolve_project_dir(project_dir))


def get_config_file(project_dir: Optional[Path] = None) -> Path:
    """Get the config file path for a project.

    Args:
        project_dir: Optional project directory (resolved if not provided)

    Returns:
        Path to .agentbox/config.yml file
    """
    return ProjectPaths.config_file(resolve_project_dir(project_dir))


def is_initialized(project_dir: Optional[Path] = None) -> bool:
    """Check if a project directory is initialized for agentbox.

    A project is considered initialized if it has a .agentbox directory.

    Args:
        project_dir: Optional project directory (resolved if not provided)

    Returns:
        True if project is initialized, False otherwise
    """
    return get_agentbox_dir(project_dir).exists()
