# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Base classes and types for config migrations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class MigrationSeverity(Enum):
    """Severity levels for migrations."""

    INFO = "info"  # Optional improvement
    WARNING = "warning"  # Deprecated, warn user
    BREAKING = "breaking"  # Must fix before continuing


class MigrationAction(Enum):
    """Actions to take for migrations."""

    SUGGEST = "suggest"  # Just show message
    AUTO = "auto"  # Auto-migrate without asking
    PROMPT = "prompt"  # Ask user first


@dataclass
class MigrationResult:
    """Result of a migration check or execution."""

    migration_id: str
    applicable: bool
    description: str
    severity: MigrationSeverity
    action: MigrationAction
    applied: bool = False
    skipped: bool = False
    skip_reason: Optional[str] = None
    changes_made: Optional[List[str]] = None
    error: Optional[str] = None


class Migration(ABC):
    """Base class for config migrations.

    Subclasses must define:
    - id: Unique identifier for the migration
    - description: Human-readable description
    - introduced_in: Version that introduced this migration
    """

    id: str
    description: str
    introduced_in: str
    severity: MigrationSeverity = MigrationSeverity.WARNING
    default_action: MigrationAction = MigrationAction.SUGGEST

    @abstractmethod
    def detect(self, raw_config: Dict[str, Any], project_dir: Path) -> bool:
        """Check if this migration is needed.

        Args:
            raw_config: Raw config dictionary
            project_dir: Project directory path

        Returns:
            True if migration should be applied
        """
        pass

    @abstractmethod
    def migrate(self, raw_config: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
        """Apply the migration.

        Args:
            raw_config: Raw config dictionary
            project_dir: Project directory path

        Returns:
            Modified config dictionary
        """
        pass

    @abstractmethod
    def get_suggestion(self) -> str:
        """Get human-readable fix suggestion.

        Returns:
            Multi-line string describing what to do
        """
        pass

    def check(self, raw_config: Dict[str, Any], project_dir: Path) -> MigrationResult:
        """Check if migration is applicable and return result.

        Args:
            raw_config: Raw config dictionary
            project_dir: Project directory path

        Returns:
            MigrationResult with detection status
        """
        applicable = self.detect(raw_config, project_dir)
        return MigrationResult(
            migration_id=self.id,
            applicable=applicable,
            description=self.description,
            severity=self.severity,
            action=self.default_action,
        )
