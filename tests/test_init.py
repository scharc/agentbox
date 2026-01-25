# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Tests for 'abox init' command."""

import json
from pathlib import Path
from tests.conftest import run_abox


def test_init_creates_agentbox_dir(test_project):
    """Test that 'abox init' creates .agentbox/ with correct structure."""
    agentbox_dir = test_project / ".agentbox"

    assert agentbox_dir.exists(), ".agentbox directory should exist"
    assert agentbox_dir.is_dir(), ".agentbox should be a directory"

    # Check for expected subdirectories
    assert (agentbox_dir / "claude").exists(), ".agentbox/claude should exist"
    assert (agentbox_dir / "skills").exists(), ".agentbox/skills should exist"

    # Note: codex/, gemini/, qwen/ are created at runtime by container-init.sh
    # mcp.json is at root level (unified for all agents)
    assert (agentbox_dir / "mcp.json").exists(), ".agentbox/mcp.json should exist"


def test_init_creates_claude_config(test_project):
    """Test that 'abox init' creates Claude config files."""
    claude_dir = test_project / ".agentbox" / "claude"

    # Check config.json
    config_file = claude_dir / "config.json"
    assert config_file.exists(), "claude/config.json should exist"

    with open(config_file) as f:
        config = json.load(f)
    assert isinstance(config, dict), "config.json should be valid JSON"

    # Check config-super.json
    config_super_file = claude_dir / "config-super.json"
    assert config_super_file.exists(), "claude/config-super.json should exist"

    with open(config_super_file) as f:
        config_super = json.load(f)
    assert isinstance(config_super, dict), "config-super.json should be valid JSON"


def test_init_creates_unified_mcp(test_project):
    """Test that 'abox init' creates unified mcp.json at root level."""
    agentbox_dir = test_project / ".agentbox"
    mcp_file = agentbox_dir / "mcp.json"

    assert mcp_file.exists(), "mcp.json should exist at root"

    with open(mcp_file) as f:
        mcp_config = json.load(f)
    assert isinstance(mcp_config, dict), "mcp.json should be valid JSON"
    assert "mcpServers" in mcp_config, "mcp.json should have mcpServers key"

    # claude/mcp.json should NOT exist after init (symlink created at runtime)
    claude_mcp = agentbox_dir / "claude" / "mcp.json"
    assert not claude_mcp.exists(), "claude/mcp.json should not exist (symlink created at runtime)"


def test_init_idempotent(tmp_path, docker_available):
    """Test that running 'abox init' twice doesn't break things."""
    # Run init first time
    result1 = run_abox("init", cwd=tmp_path)
    assert result1.returncode == 0, "First init should succeed"

    agentbox_dir = tmp_path / ".agentbox"
    assert agentbox_dir.exists(), ".agentbox should exist after first init"

    # Run init second time
    result2 = run_abox("init", cwd=tmp_path, check=False)

    # Should succeed idempotently (may show warning but still returns 0)
    assert result2.returncode == 0, \
        f"Second init should succeed idempotently. stderr: {result2.stderr}"

    # Should show warning about already existing
    assert "already" in result2.stdout.lower(), \
        "Second init should warn that directory already exists"

    # Directory should still exist
    assert agentbox_dir.exists(), ".agentbox should still exist after second init"
