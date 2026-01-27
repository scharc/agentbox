# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Integration tests for workspace mount management."""

from pathlib import Path

import pytest

from helpers.cli import run_abox
from helpers.docker import exec_in_container, wait_for_container_ready


@pytest.mark.integration
class TestWorkspaceMounts:
    """Validate workspace list/add/remove behavior."""

    def test_workspace_add_list_access(self, test_project):
        host_dir = test_project / "extra"
        host_dir.mkdir(parents=True, exist_ok=True)
        host_file = host_dir / "hello.txt"
        host_file.write_text("hello", encoding="utf-8")

        result = run_abox("workspace", "add", str(host_dir), "rw", cwd=test_project)
        assert result.returncode == 0, f"workspace add failed: {result.stderr}"

        result = run_abox("workspace", "list", cwd=test_project)
        assert result.returncode == 0, f"workspace list failed: {result.stderr}"
        assert "extra" in result.stdout, f"workspace list missing mount. stdout: {result.stdout}"

        result = run_abox("start", cwd=test_project)
        assert result.returncode == 0, f"start failed: {result.stderr}"
        container_name = f"boxctl-{test_project.name}"
        assert wait_for_container_ready(container_name, timeout=60), "container not ready"

        result = exec_in_container(container_name, "cat /context/extra/hello.txt")
        assert result.returncode == 0, f"mount not readable: {result.stderr}"
        assert "hello" in result.stdout

        result = exec_in_container(container_name, "echo written > /context/extra/inside.txt")
        assert result.returncode == 0, f"mount not writable: {result.stderr}"
        assert (host_dir / "inside.txt").exists(), "write did not propagate to host"

        run_abox("stop", cwd=test_project)

    def test_workspace_remove_unmounts(self, test_project):
        host_dir = test_project / "extra-remove"
        host_dir.mkdir(parents=True, exist_ok=True)

        result = run_abox("workspace", "add", str(host_dir), "ro", "extras", cwd=test_project)
        assert result.returncode == 0, f"workspace add failed: {result.stderr}"

        result = run_abox("start", cwd=test_project)
        assert result.returncode == 0, f"start failed: {result.stderr}"
        container_name = f"boxctl-{test_project.name}"
        assert wait_for_container_ready(container_name, timeout=60), "container not ready"

        result = exec_in_container(container_name, "test -d /context/extras")
        assert result.returncode == 0, "mount not present after add"

        result = run_abox("workspace", "remove", "extras", cwd=test_project)
        assert result.returncode == 0, f"workspace remove failed: {result.stderr}"

        result = run_abox("start", cwd=test_project)
        assert result.returncode == 0, f"start failed: {result.stderr}"
        assert wait_for_container_ready(container_name, timeout=60), "container not ready"

        result = exec_in_container(container_name, "test -d /context/extras")
        assert result.returncode != 0, "mount still present after removal"

        run_abox("stop", cwd=test_project)
