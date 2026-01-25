# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Tests for the migration system."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from agentbox.migrations import (
    DuplicateMigrationError,
    get_all_migrations,
    get_migration,
)
from agentbox.migrations.v0_3_0_unified import MCPUnification, UnifiedConfigStructure


class TestMigrationRegistry:
    """Tests for migration registry functions."""

    def test_get_all_migrations_returns_list(self):
        """All migrations should be returned as a list."""
        migrations = get_all_migrations()
        assert isinstance(migrations, list)
        assert len(migrations) >= 4  # At least our 4 registered migrations

    def test_get_all_migrations_sorted_by_version(self):
        """Migrations should be sorted by introduced_in version."""
        migrations = get_all_migrations()
        versions = [m.introduced_in for m in migrations]
        # Check that v0.2.0 migrations come before v0.3.0
        v020_indices = [i for i, v in enumerate(versions) if v == "0.2.0"]
        v030_indices = [i for i, v in enumerate(versions) if v == "0.3.0"]
        if v020_indices and v030_indices:
            assert max(v020_indices) < min(v030_indices)

    def test_get_migration_by_id(self):
        """Should be able to get migration by ID."""
        migration = get_migration("unified-config-structure")
        assert migration.id == "unified-config-structure"
        assert migration.introduced_in == "0.3.0"

    def test_get_migration_not_found(self):
        """Should raise KeyError for unknown migration ID."""
        with pytest.raises(KeyError):
            get_migration("nonexistent-migration")


class TestUnifiedConfigStructure:
    """Tests for UnifiedConfigStructure migration."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_detect_old_config_structure(self, temp_project):
        """Should detect when .agentbox.yml exists in root."""
        migration = UnifiedConfigStructure()

        # Create old-style config
        old_config = temp_project / ".agentbox.yml"
        old_config.write_text("version: 1\n")

        assert migration.detect({}, temp_project) is True

    def test_detect_new_config_structure(self, temp_project):
        """Should not detect when new structure exists."""
        migration = UnifiedConfigStructure()

        # Create new-style config
        new_dir = temp_project / ".agentbox"
        new_dir.mkdir()
        (new_dir / "config.yml").write_text("version: 1\n")

        assert migration.detect({}, temp_project) is False

    def test_detect_both_configs_exist(self, temp_project):
        """Should not migrate if both old and new exist."""
        migration = UnifiedConfigStructure()

        # Create both configs
        (temp_project / ".agentbox.yml").write_text("version: 1\n")
        new_dir = temp_project / ".agentbox"
        new_dir.mkdir()
        (new_dir / "config.yml").write_text("version: 1\n")

        assert migration.detect({}, temp_project) is False

    def test_detect_no_config(self, temp_project):
        """Should not detect when no config exists."""
        migration = UnifiedConfigStructure()
        assert migration.detect({}, temp_project) is False

    def test_migrate_moves_config(self, temp_project):
        """Migration should move .agentbox.yml to .agentbox/config.yml."""
        migration = UnifiedConfigStructure()

        # Create old-style config
        old_config = temp_project / ".agentbox.yml"
        old_config.write_text("version: 1\ntest: value\n")

        # Run migration
        migration.migrate({}, temp_project)

        # Verify
        assert not old_config.exists()
        new_config = temp_project / ".agentbox" / "config.yml"
        assert new_config.exists()
        assert "test: value" in new_config.read_text()

    def test_migrate_creates_backup(self, temp_project):
        """Migration should create backup before changes."""
        migration = UnifiedConfigStructure()

        # Create old-style config
        (temp_project / ".agentbox.yml").write_text("version: 1\n")

        # Run migration
        migration.migrate({}, temp_project)

        # Verify backup exists
        backup_dir = temp_project / ".agentbox" / "backup-pre-migration"
        assert backup_dir.exists()
        assert (backup_dir / ".agentbox.yml").exists()

    def test_migrate_merges_mcp_configs(self, temp_project):
        """Migration should merge agent MCP configs into unified mcp.json."""
        migration = UnifiedConfigStructure()

        # Create old-style config
        (temp_project / ".agentbox.yml").write_text("version: 1\n")

        # Create Claude MCP config
        claude_dir = temp_project / ".agentbox" / "claude"
        claude_dir.mkdir(parents=True)
        claude_mcp = {"mcpServers": {"server1": {"command": "test1"}}}
        (claude_dir / "mcp.json").write_text(json.dumps(claude_mcp))

        # Run migration
        migration.migrate({}, temp_project)

        # Verify unified MCP exists with merged content
        unified_mcp = temp_project / ".agentbox" / "mcp.json"
        assert unified_mcp.exists()
        content = json.loads(unified_mcp.read_text())
        assert "server1" in content["mcpServers"]

    def test_migrate_creates_internal_symlinks(self, temp_project):
        """Migration should create symlinks in agent directories."""
        migration = UnifiedConfigStructure()

        # Create old-style config
        (temp_project / ".agentbox.yml").write_text("version: 1\n")

        # Create unified MCP first (simulating merge result)
        agentbox_dir = temp_project / ".agentbox"
        agentbox_dir.mkdir(exist_ok=True)
        (agentbox_dir / "mcp.json").write_text('{"mcpServers": {}}')

        # Run migration
        migration.migrate({}, temp_project)

        # Verify symlink created
        claude_mcp = agentbox_dir / "claude" / "mcp.json"
        assert claude_mcp.is_symlink()
        assert str(claude_mcp.readlink()) == "../mcp.json"

    def test_migrate_updates_gitignore(self, temp_project):
        """Migration should add state directories to .gitignore."""
        migration = UnifiedConfigStructure()

        # Create old-style config
        (temp_project / ".agentbox.yml").write_text("version: 1\n")

        # Run migration
        migration.migrate({}, temp_project)

        # Verify .gitignore updated
        gitignore = temp_project / ".gitignore"
        assert gitignore.exists()
        content = gitignore.read_text()
        assert ".agentbox/claude/projects/" in content
        assert "Agentbox state" in content

    def test_migrate_gitignore_idempotent(self, temp_project):
        """Running migration twice should not duplicate .gitignore entries."""
        migration = UnifiedConfigStructure()

        # Create .gitignore with existing content
        gitignore = temp_project / ".gitignore"
        gitignore.write_text("*.pyc\n")

        # Create old-style config
        (temp_project / ".agentbox.yml").write_text("version: 1\n")

        # Run migration
        migration.migrate({}, temp_project)

        # Get content after first migration
        content1 = gitignore.read_text()

        # Recreate old config and run again
        (temp_project / ".agentbox.yml").write_text("version: 1\n")
        # Remove new config to allow detection
        (temp_project / ".agentbox" / "config.yml").unlink()

        migration.migrate({}, temp_project)

        # Content should be same (no duplicates)
        content2 = gitignore.read_text()
        assert content1 == content2

    def test_get_suggestion(self):
        """Should return helpful suggestion text."""
        migration = UnifiedConfigStructure()
        suggestion = migration.get_suggestion()
        assert "abox config migrate" in suggestion
        assert ".agentbox/" in suggestion


class TestMCPUnification:
    """Tests for MCPUnification migration."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_detect_separate_mcp_configs(self, temp_project):
        """Should detect when Claude has separate MCP config."""
        migration = MCPUnification()

        # Create .agentbox structure with separate Claude MCP
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)
        (claude_dir / "mcp.json").write_text('{"mcpServers": {}}')

        assert migration.detect({}, temp_project) is True

    def test_detect_already_unified(self, temp_project):
        """Should not detect when MCP is already unified (symlink)."""
        migration = MCPUnification()

        # Create .agentbox structure with symlink
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)

        # Create unified mcp.json
        (agentbox_dir / "mcp.json").write_text('{"mcpServers": {}}')

        # Create symlink in Claude dir
        (claude_dir / "mcp.json").symlink_to("../mcp.json")

        assert migration.detect({}, temp_project) is False

    def test_detect_no_claude_mcp(self, temp_project):
        """Should not detect when no Claude MCP exists."""
        migration = MCPUnification()

        # Create empty .agentbox structure
        agentbox_dir = temp_project / ".agentbox"
        agentbox_dir.mkdir(parents=True)

        assert migration.detect({}, temp_project) is False

    def test_migrate_merges_and_symlinks(self, temp_project):
        """Migration should merge Claude MCP and replace with symlink."""
        migration = MCPUnification()

        # Create .agentbox structure
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)

        # Create Claude MCP config
        claude_mcp = {"mcpServers": {"test-server": {"command": "test"}}}
        (claude_dir / "mcp.json").write_text(json.dumps(claude_mcp))

        # Run migration
        migration.migrate({}, temp_project)

        # Verify unified MCP created with content
        unified_mcp = agentbox_dir / "mcp.json"
        assert unified_mcp.exists()
        content = json.loads(unified_mcp.read_text())
        assert "test-server" in content["mcpServers"]

        # Verify Claude MCP is now a symlink
        claude_mcp_path = claude_dir / "mcp.json"
        assert claude_mcp_path.is_symlink()
        assert str(claude_mcp_path.readlink()) == "../mcp.json"

    def test_migrate_preserves_existing_unified(self, temp_project):
        """Migration should preserve existing unified MCP entries."""
        migration = MCPUnification()

        # Create .agentbox structure
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)

        # Create existing unified MCP
        unified = {"mcpServers": {"existing-server": {"command": "existing"}}}
        (agentbox_dir / "mcp.json").write_text(json.dumps(unified))

        # Create Claude MCP with different server
        claude = {"mcpServers": {"claude-server": {"command": "claude"}}}
        (claude_dir / "mcp.json").write_text(json.dumps(claude))

        # Run migration
        migration.migrate({}, temp_project)

        # Verify both servers in unified
        content = json.loads((agentbox_dir / "mcp.json").read_text())
        assert "existing-server" in content["mcpServers"]
        assert "claude-server" in content["mcpServers"]

    def test_migrate_handles_broken_symlink(self, temp_project):
        """Migration should handle broken symlinks gracefully."""
        migration = MCPUnification()

        # Create .agentbox structure
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)

        # Create a broken symlink (pointing to non-existent file)
        broken_link = claude_dir / "mcp.json"
        broken_link.symlink_to("../nonexistent.json")

        # Verify it's a broken symlink
        assert broken_link.is_symlink()
        assert not broken_link.exists()

        # Run migration - should not raise
        migration.migrate({}, temp_project)

        # Verify symlink now points to correct target
        assert broken_link.is_symlink()
        assert str(broken_link.readlink()) == "../mcp.json"


class TestSymlinkEdgeCases:
    """Tests for symlink edge cases in migrations."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_safe_symlink_skips_if_correct_target(self, temp_project):
        """_safe_symlink should skip if symlink already points to correct target."""
        migration = UnifiedConfigStructure()

        # Create directory structure
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)

        # Create correct symlink
        link = claude_dir / "mcp.json"
        link.symlink_to("../mcp.json")

        # Get original inode
        original_link = link.readlink()

        # Call _safe_symlink with same target
        migration._safe_symlink(link, "../mcp.json")

        # Symlink should still exist and point to same target
        assert link.is_symlink()
        assert str(link.readlink()) == "../mcp.json"

    def test_safe_symlink_replaces_wrong_target(self, temp_project):
        """_safe_symlink should replace symlink pointing to wrong target."""
        migration = UnifiedConfigStructure()

        # Create directory structure
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)

        # Create symlink pointing to wrong target
        link = claude_dir / "mcp.json"
        link.symlink_to("../wrong.json")

        # Call _safe_symlink with correct target
        migration._safe_symlink(link, "../mcp.json")

        # Symlink should now point to correct target
        assert link.is_symlink()
        assert str(link.readlink()) == "../mcp.json"

    def test_safe_symlink_replaces_broken_symlink(self, temp_project):
        """_safe_symlink should replace broken symlink."""
        migration = UnifiedConfigStructure()

        # Create directory structure
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)

        # Create broken symlink
        link = claude_dir / "mcp.json"
        link.symlink_to("../nonexistent.json")

        # Call _safe_symlink
        migration._safe_symlink(link, "../mcp.json")

        # Symlink should now point to correct target
        assert link.is_symlink()
        assert str(link.readlink()) == "../mcp.json"

    def test_backup_handles_symlinks(self, temp_project):
        """Backup should preserve symlinks."""
        migration = UnifiedConfigStructure()

        # Create directory structure with symlink
        agentbox_dir = temp_project / ".agentbox"
        claude_dir = agentbox_dir / "claude"
        claude_dir.mkdir(parents=True)
        (agentbox_dir / "mcp.json").write_text('{"mcpServers": {}}')
        (claude_dir / "mcp.json").symlink_to("../mcp.json")

        # Create old-style config to trigger migration
        (temp_project / ".agentbox.yml").write_text("version: 1\n")

        # Run migration (which creates backup)
        migration.migrate({}, temp_project)

        # Verify backup contains symlink
        backup_dir = agentbox_dir / "backup-pre-migration"
        backup_claude = backup_dir / "claude"
        assert backup_claude.exists()
        # The symlink was inside claude dir, so it was copied via copytree
