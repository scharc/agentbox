# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Integration tests for network auto-reconnect."""

import json

import pytest

from helpers.cli import run_abox
from helpers.docker import run_docker, wait_for_container_ready


@pytest.mark.integration
class TestNetworkAutoReconnect:
    """Ensure configured network connections reconnect on container recreate."""

    def test_network_reconnect_on_recreate(self, test_project, nginx_container, test_network):
        result = run_abox("start", cwd=test_project)
        assert result.returncode == 0, f"Failed to start container: {result.stderr}"

        container_name = f"boxctl-{test_project.name}"
        assert wait_for_container_ready(container_name, timeout=60)

        result = run_abox("network", "connect", nginx_container, cwd=test_project)
        assert result.returncode == 0, f"network connect failed: {result.stderr}"

        # Stop and remove to force create_container path on next start
        run_abox("stop", cwd=test_project)
        run_docker("rm", "-f", container_name)

        result = run_abox("start", cwd=test_project)
        assert result.returncode == 0, f"Failed to restart container: {result.stderr}"
        assert wait_for_container_ready(container_name, timeout=60)

        inspect = run_docker("inspect", container_name)
        assert inspect.returncode == 0, f"Failed to inspect container: {inspect.stderr}"

        data = json.loads(inspect.stdout)[0]
        networks = data.get("NetworkSettings", {}).get("Networks", {}).keys()
        assert test_network in networks

        run_abox("stop", cwd=test_project)
