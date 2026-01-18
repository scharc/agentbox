# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Integration tests for workspace mounts from .agentbox.yml."""

import pytest

from helpers.cli import run_abox
from helpers.config import update_project_config
from helpers.docker import exec_in_container, wait_for_container_ready


@pytest.mark.integration
class TestWorkspaceConfigMounts:
    """Validate workspace mounts configured in project config."""

    def test_configured_workspace_mount(self, test_project):
        host_dir = test_project / "external-data"
        host_dir.mkdir(parents=True, exist_ok=True)
        (host_dir / "data.txt").write_text("hello-config")

        update_project_config(
            test_project,
            {"workspaces": [{"path": str(host_dir), "mode": "ro", "mount": "external"}]},
        )

        result = run_abox("start", cwd=test_project)
        assert result.returncode == 0, f"Failed to start container: {result.stderr}"

        container_name = f"agentbox-{test_project.name}"
        assert wait_for_container_ready(container_name, timeout=60)

        result = exec_in_container(
            container_name,
            "cat /context/external/data.txt",
        )
        assert result.returncode == 0
        assert result.stdout.strip() == "hello-config"

        run_abox("stop", cwd=test_project)
