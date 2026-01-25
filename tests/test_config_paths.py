# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Tests for config path resolution."""

import shutil
import tempfile
from pathlib import Path

import pytest
import yaml


class TestConfigPathResolution:
    """Tests for config file path resolution."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_no_config_exists(self, temp_project):
        """exists() returns False when no config file exists."""
        from agentbox.config import ProjectConfig

        config = ProjectConfig(temp_project)
        assert not config.exists()

    def test_new_config_found(self, temp_project):
        """Config loads from new .agentbox/config.yml location."""
        from agentbox.config import ProjectConfig

        # Create new config
        new_dir = temp_project / ".agentbox"
        new_dir.mkdir()
        new_path = new_dir / "config.yml"
        new_path.write_text("version: '1.0'\n")

        config = ProjectConfig(temp_project)

        assert config.exists()
        assert config.config_path == new_path

    def test_save_writes_to_config_path(self, temp_project):
        """Save writes to .agentbox/config.yml location."""
        from agentbox.config import ProjectConfig

        # Create config directory
        new_dir = temp_project / ".agentbox"
        new_dir.mkdir()
        new_path = new_dir / "config.yml"
        new_path.write_text("version: '1.0'\n")

        config = ProjectConfig(temp_project)
        config.docker_enabled = True
        config.save(quiet=True)

        # Should save to new path
        assert new_path.exists()
        with open(new_path) as f:
            data = yaml.safe_load(f)
        assert data["docker"]["enabled"] is True

    def test_create_template_uses_new_location(self, temp_project):
        """create_template() creates config in new .agentbox/ location."""
        from agentbox.config import ProjectConfig

        config = ProjectConfig(temp_project)
        config.create_template()

        # Should create in new location
        new_path = temp_project / ".agentbox" / "config.yml"
        legacy_path = temp_project / ".agentbox.yml"

        assert new_path.exists()
        assert not legacy_path.exists()

    def test_config_path_constant(self):
        """Verify config path constant is set correctly."""
        from agentbox.config import ProjectConfig

        assert ProjectConfig.CONFIG_PATH == ".agentbox/config.yml"
