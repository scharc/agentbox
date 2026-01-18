# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Integration tests for container config features."""

import json

import pytest

from helpers.cli import run_abox
from helpers.config import update_project_config
from helpers.docker import run_docker, wait_for_container_ready


@pytest.mark.integration
class TestContainerConfig:
    """Validate container configuration options from .agentbox.yml."""

    def test_ports_mapping_configured(self, test_project):
        update_project_config(test_project, {"ports": ["18080:8080"]})

        result = run_abox("start", cwd=test_project)
        if result.returncode != 0:
            failure_output = f"{result.stdout}\n{result.stderr}"
            if "cgroupv2" in failure_output or "cgroup" in failure_output:
                pytest.skip("Resource limits not supported in this DinD cgroup mode")
            assert result.returncode == 0, f"Failed to start container: {result.stderr}"

        container_name = f"agentbox-{test_project.name}"
        assert wait_for_container_ready(container_name, timeout=60)

        result = run_docker("inspect", container_name)
        assert result.returncode == 0, f"Failed to inspect container: {result.stderr}"

        data = json.loads(result.stdout)[0]
        ports = data.get("NetworkSettings", {}).get("Ports", {}) or {}
        assert "8080/tcp" in ports, f"Expected port 8080 to be published: {ports}"
        assert ports["8080/tcp"][0]["HostPort"] == "18080"

        run_abox("stop", cwd=test_project)

    def test_resources_configured(self, test_project):
        update_project_config(test_project, {"resources": {"memory": "128m", "cpus": "0.5"}})

        result = run_abox("start", cwd=test_project)
        if result.returncode != 0:
            failure_output = f"{result.stdout}\n{result.stderr}"
            if "cgroupv2" in failure_output or "cgroup" in failure_output:
                pytest.skip("Resource limits not supported in this DinD cgroup mode")
            assert result.returncode == 0, f"Failed to start container: {result.stderr}"

        container_name = f"agentbox-{test_project.name}"
        assert wait_for_container_ready(container_name, timeout=60)

        result = run_docker("inspect", container_name)
        assert result.returncode == 0, f"Failed to inspect container: {result.stderr}"

        data = json.loads(result.stdout)[0]
        host_config = data.get("HostConfig", {})
        assert host_config.get("Memory") == 128 * 1024 * 1024
        assert host_config.get("NanoCpus") == 500_000_000

        run_abox("stop", cwd=test_project)

    def test_security_configured(self, test_project):
        update_project_config(
            test_project,
            {"security": {"seccomp": "unconfined", "capabilities": ["SYS_PTRACE"]}},
        )

        result = run_abox("start", cwd=test_project)
        assert result.returncode == 0, f"Failed to start container: {result.stderr}"

        container_name = f"agentbox-{test_project.name}"
        assert wait_for_container_ready(container_name, timeout=60)

        result = run_docker("inspect", container_name)
        assert result.returncode == 0, f"Failed to inspect container: {result.stderr}"

        data = json.loads(result.stdout)[0]
        host_config = data.get("HostConfig", {})
        security_opt = host_config.get("SecurityOpt") or []
        cap_add = host_config.get("CapAdd") or []

        assert "seccomp=unconfined" in security_opt
        assert "SYS_PTRACE" in cap_add

        run_abox("stop", cwd=test_project)
