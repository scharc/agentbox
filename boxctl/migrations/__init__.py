# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Config migration system for boxctl.

This module provides version-aware config migrations that detect legacy
configuration patterns and help users update their configs.

Usage:
    from boxctl.migrations import MigrationRunner

    runner = MigrationRunner(raw_config, project_dir)
    results = runner.check_all()
    if any(r.applicable for r in results):
        runner.show_warnings()
"""

from typing import Dict, List, Type

from boxctl.migrations.base import (
    Migration,
    MigrationAction,
    MigrationResult,
    MigrationSeverity,
)
from boxctl.migrations.runner import MigrationRunner

# Migration registry
_MIGRATIONS: Dict[str, Type[Migration]] = {}


class DuplicateMigrationError(Exception):
    """Raised when attempting to register a migration with a duplicate ID."""

    pass


def register_migration(cls: Type[Migration]) -> Type[Migration]:
    """Register a migration class.

    Args:
        cls: Migration class to register

    Returns:
        The registered class (for use as decorator)

    Raises:
        DuplicateMigrationError: If a migration with the same ID is already registered
    """
    if cls.id in _MIGRATIONS:
        raise DuplicateMigrationError(
            f"Migration '{cls.id}' is already registered by {_MIGRATIONS[cls.id].__name__}"
        )
    _MIGRATIONS[cls.id] = cls
    return cls


def _parse_version(version: str) -> tuple:
    """Parse a version string into a comparable tuple.

    Args:
        version: Version string like "0.2.0"

    Returns:
        Tuple of integers for comparison
    """
    try:
        return tuple(int(x) for x in version.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def get_all_migrations() -> List[Migration]:
    """Get instances of all registered migrations, sorted by version.

    Returns:
        List of Migration instances sorted by introduced_in version,
        with migration ID as secondary sort key for deterministic ordering
    """
    migrations = [cls() for cls in _MIGRATIONS.values()]
    migrations.sort(key=lambda m: (_parse_version(m.introduced_in), m.id))
    return migrations


def get_migration(migration_id: str) -> Migration:
    """Get a migration instance by ID.

    Args:
        migration_id: Migration identifier

    Returns:
        Migration instance

    Raises:
        KeyError: If migration not found
    """
    return _MIGRATIONS[migration_id]()


# Register migrations
from boxctl.migrations.v0_2_0 import DockerDevicesToEnabled, SSHConfigRename
from boxctl.migrations.v0_3_0_unified import MCPUnification, UnifiedConfigStructure

register_migration(DockerDevicesToEnabled)
register_migration(SSHConfigRename)
register_migration(UnifiedConfigStructure)
register_migration(MCPUnification)


__all__ = [
    "DuplicateMigrationError",
    "Migration",
    "MigrationAction",
    "MigrationResult",
    "MigrationRunner",
    "MigrationSeverity",
    "get_all_migrations",
    "get_migration",
    "register_migration",
]
