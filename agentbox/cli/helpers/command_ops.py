# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Slash command management for MCPs and skills.

Commands are stored in .claude/commands/ at the project root.
Each command file is prefixed with its source (mcp or skill name)
to allow clean removal and avoid conflicts.

Symlinks are created with 'ab-' prefix for easy identification:
  ab-consult.md -> mcp-agentbox-analyst-consult.md

Note: Command names (the .md filename without extension) should NOT contain
hyphens, as the parsing logic uses the last hyphen to separate source name
from command name. MCP/skill names CAN contain hyphens (e.g., "agentbox-analyst").
"""

import shutil
from pathlib import Path
from typing import List, Tuple


def _get_commands_dir(project_dir: Path) -> Path:
    """Get the .claude/commands/ directory path."""
    return project_dir / ".claude" / "commands"


def _get_command_prefix(source_type: str, name: str) -> str:
    """Get the prefix for command files from a source.

    Args:
        source_type: Either 'mcp' or 'skill'
        name: Name of the MCP or skill

    Returns:
        Prefix string like 'mcp-agentctl-' or 'skill-westworld-'
    """
    return f"{source_type}-{name}-"


def _copy_commands(
    source_dir: Path,
    project_dir: Path,
    source_type: str,
    name: str,
    override_symlinks: bool = False,
) -> List[str]:
    """Copy command files from source to .claude/commands/.

    Args:
        source_dir: Directory containing command .md files
        project_dir: Project root directory
        source_type: Either 'mcp' or 'skill'
        name: Name of the MCP or skill
        override_symlinks: If True, update ab- symlinks even if they exist
                          (used for custom MCPs/skills to override library ones)

    Returns:
        List of command names that were copied
    """
    import sys

    commands_src = source_dir / "commands"
    if not commands_src.exists() or not commands_src.is_dir():
        return []

    commands_dest = _get_commands_dir(project_dir)
    commands_dest.mkdir(parents=True, exist_ok=True)

    prefix = _get_command_prefix(source_type, name)
    copied = []

    for cmd_file in sorted(commands_src.glob("*.md")):  # Sort for deterministic order
        cmd_name = cmd_file.stem  # filename without .md

        # Validate: command names should not contain hyphens (breaks parsing)
        if "-" in cmd_name:
            print(
                f"Warning: Skipping command '{cmd_name}' from {source_type}/{name} - "
                f"command names cannot contain hyphens",
                file=sys.stderr,
            )
            continue

        # Create prefixed filename to track source
        dest_name = f"{prefix}{cmd_file.name}"
        dest_path = commands_dest / dest_name

        # Copy the command file
        shutil.copy2(cmd_file, dest_path)

        # Create a symlink with ab- prefix for easy identification
        # e.g., ab-consult.md -> mcp-agentbox-analyst-consult.md
        ab_symlink_name = f"ab-{cmd_file.name}"
        ab_symlink_path = commands_dest / ab_symlink_name

        if ab_symlink_path.is_symlink():
            # Check if symlink is broken (target doesn't exist)
            try:
                target_exists = ab_symlink_path.resolve().exists()
            except (OSError, ValueError):
                target_exists = False

            if not target_exists or override_symlinks:
                # Repair broken symlink or override for custom source
                ab_symlink_path.unlink()
                ab_symlink_path.symlink_to(dest_name)
            # else: keep existing valid symlink (first-come wins for same priority)
        elif ab_symlink_path.exists():
            # Non-symlink file exists - warn and skip
            print(
                f"Warning: {ab_symlink_name} exists as regular file, "
                f"cannot create symlink for {source_type}/{name}",
                file=sys.stderr,
            )
        else:
            ab_symlink_path.symlink_to(dest_name)

        copied.append(cmd_file.stem)  # Without .md extension

    return copied


def _remove_commands(
    project_dir: Path,
    source_type: str,
    name: str,
) -> List[str]:
    """Remove command files for a source from .claude/commands/.

    Args:
        project_dir: Project root directory
        source_type: Either 'mcp' or 'skill'
        name: Name of the MCP or skill

    Returns:
        List of command names that were removed
    """
    commands_dir = _get_commands_dir(project_dir)
    if not commands_dir.exists():
        return []

    prefix = _get_command_prefix(source_type, name)
    removed = []

    # Find and remove all files with this prefix
    for cmd_file in commands_dir.glob(f"{prefix}*.md"):
        # Get the original command name (without prefix and extension)
        original_name = cmd_file.name[len(prefix):]  # e.g., "context.md"
        cmd_name = original_name[:-3] if original_name.endswith(".md") else original_name

        # Check if there's an ab- prefixed symlink pointing to this file
        ab_symlink_path = commands_dir / f"ab-{original_name}"
        if ab_symlink_path.is_symlink():
            # Only remove symlink if it points to our file
            try:
                if ab_symlink_path.resolve().name == cmd_file.name:
                    ab_symlink_path.unlink()
            except (OSError, ValueError):
                pass

        # Remove the prefixed file
        cmd_file.unlink()
        removed.append(cmd_name)

    return removed


def _list_installed_commands(project_dir: Path) -> List[Tuple[str, str, str]]:
    """List all installed commands with their sources.

    Returns:
        List of tuples: (command_name, source_type, source_name)
    """
    commands_dir = _get_commands_dir(project_dir)
    if not commands_dir.exists():
        return []

    commands = []
    for cmd_file in sorted(commands_dir.glob("*.md")):  # Sort for deterministic order
        # Skip symlinks, only process actual files
        if cmd_file.is_symlink():
            continue

        name = cmd_file.stem
        # Parse prefix to get source
        # Use rsplit to handle MCP/skill names with hyphens (e.g., "agentbox-analyst")
        # mcp-agentbox-analyst-consult -> source_name=agentbox-analyst, cmd_name=consult
        if name.startswith("mcp-"):
            rest = name[4:]  # Remove "mcp-"
            if "-" in rest:
                source_name, cmd_name = rest.rsplit("-", 1)
                commands.append((cmd_name, "mcp", source_name))
        elif name.startswith("skill-"):
            rest = name[6:]  # Remove "skill-"
            if "-" in rest:
                source_name, cmd_name = rest.rsplit("-", 1)
                commands.append((cmd_name, "skill", source_name))
        else:
            # Standalone command (not from MCP or skill)
            commands.append((name, "project", ""))

    return commands


def _get_installed_command_names(
    project_dir: Path,
    source_type: str,
    name: str,
) -> set:
    """Get the set of command names currently installed for a source.

    Args:
        project_dir: Project root directory
        source_type: Either 'mcp' or 'skill'
        name: Name of the MCP or skill

    Returns:
        Set of command names (without .md extension)
    """
    commands_dir = _get_commands_dir(project_dir)
    if not commands_dir.exists():
        return set()

    prefix = _get_command_prefix(source_type, name)
    installed = set()

    for cmd_file in commands_dir.glob(f"{prefix}*.md"):
        if cmd_file.is_symlink():
            continue
        # Extract command name: "mcp-agentctl-context.md" -> "context"
        cmd_name = cmd_file.name[len(prefix):-3]  # Remove prefix and .md
        installed.add(cmd_name)

    return installed


def _remove_stale_commands(
    source_dir: Path,
    project_dir: Path,
    source_type: str,
    name: str,
) -> List[str]:
    """Remove commands that no longer exist in the source directory.

    Args:
        source_dir: Source directory of the MCP/skill (containing commands/ subdir)
        project_dir: Project root directory
        source_type: Either 'mcp' or 'skill'
        name: Name of the MCP or skill

    Returns:
        List of command names that were removed
    """
    commands_src = source_dir / "commands"

    # Get commands from source (what should exist)
    source_commands = set()
    if commands_src.exists() and commands_src.is_dir():
        for cmd_file in commands_src.glob("*.md"):
            source_commands.add(cmd_file.stem)

    # Get currently installed commands
    installed_commands = _get_installed_command_names(project_dir, source_type, name)

    # Find stale commands (installed but not in source)
    stale_commands = installed_commands - source_commands

    if not stale_commands:
        return []

    # Remove stale commands
    commands_dir = _get_commands_dir(project_dir)
    prefix = _get_command_prefix(source_type, name)
    removed = []

    for cmd_name in stale_commands:
        cmd_file = commands_dir / f"{prefix}{cmd_name}.md"
        if cmd_file.exists() and not cmd_file.is_symlink():
            # Remove ab- symlink if it points to this file
            ab_symlink = commands_dir / f"ab-{cmd_name}.md"
            if ab_symlink.is_symlink():
                try:
                    if ab_symlink.resolve().name == cmd_file.name:
                        ab_symlink.unlink()
                except (OSError, ValueError):
                    pass

            # Remove the command file
            cmd_file.unlink()
            removed.append(cmd_name)

    return removed


def _sync_mcp_commands(
    mcp_source_dir: Path,
    project_dir: Path,
    mcp_name: str,
    is_custom: bool = False,
) -> List[str]:
    """Sync slash commands for an MCP from its source directory.

    This removes stale commands, updates existing ones, and adds new ones.
    Used during MCP sync to keep slash commands in sync with MCP server files.

    Args:
        mcp_source_dir: Source directory of the MCP (containing commands/ subdir)
        project_dir: Project root directory
        mcp_name: Name of the MCP
        is_custom: If True, this is a custom MCP that should override library commands

    Returns:
        List of command names that were synced
    """
    # First remove any stale commands that no longer exist in source
    _remove_stale_commands(mcp_source_dir, project_dir, "mcp", mcp_name)

    commands_src = mcp_source_dir / "commands"
    if not commands_src.exists() or not commands_src.is_dir():
        return []

    # Copy/update commands from source
    # Custom MCPs override library MCPs for ab- symlinks
    return _copy_commands(mcp_source_dir, project_dir, "mcp", mcp_name, override_symlinks=is_custom)


def _sync_skill_commands(
    skill_source_dir: Path,
    project_dir: Path,
    skill_name: str,
    is_custom: bool = False,
) -> List[str]:
    """Sync slash commands for a skill from its source directory.

    This removes stale commands, updates existing ones, and adds new ones.
    Used during skill sync to keep slash commands in sync with skill files.

    Args:
        skill_source_dir: Source directory of the skill (containing commands/ subdir)
        project_dir: Project root directory
        skill_name: Name of the skill
        is_custom: If True, this is a custom skill that should override library commands

    Returns:
        List of command names that were synced
    """
    # First remove any stale commands that no longer exist in source
    _remove_stale_commands(skill_source_dir, project_dir, "skill", skill_name)

    commands_src = skill_source_dir / "commands"
    if not commands_src.exists() or not commands_src.is_dir():
        return []

    # Copy/update commands from source
    # Custom skills override library skills for ab- symlinks
    return _copy_commands(skill_source_dir, project_dir, "skill", skill_name, override_symlinks=is_custom)
