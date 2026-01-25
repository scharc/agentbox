# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Tests for distribute-mcp-config.py script."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


class TestDistributeMcpConfig:
    """Tests for MCP config distribution."""

    @pytest.fixture
    def temp_agentbox(self):
        """Create a temporary .agentbox directory."""
        temp_dir = Path(tempfile.mkdtemp())
        agentbox_dir = temp_dir / ".agentbox"
        agentbox_dir.mkdir()
        yield agentbox_dir
        shutil.rmtree(temp_dir)

    def test_empty_mcp_config(self, temp_agentbox):
        """Script handles missing mcp.json gracefully."""
        result = subprocess.run(
            ["python3", "/workspace/bin/distribute-mcp-config.py", "--agentbox", str(temp_agentbox)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "No MCP servers configured" in result.stderr or "nothing to distribute" in result.stderr

    def test_distributes_stdio_servers(self, temp_agentbox):
        """STDIO servers are distributed to all agents."""
        # Create unified MCP config with STDIO server
        mcp_config = {
            "mcpServers": {
                "test-server": {
                    "command": "python3",
                    "args": ["/path/to/server.py"],
                }
            }
        }
        (temp_agentbox / "mcp.json").write_text(json.dumps(mcp_config))

        result = subprocess.run(
            ["python3", "/workspace/bin/distribute-mcp-config.py", "--agentbox", str(temp_agentbox)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Check Gemini settings
        gemini_path = temp_agentbox / "gemini" / "settings.json"
        assert gemini_path.exists()
        gemini_config = json.loads(gemini_path.read_text())
        assert "test-server" in gemini_config["mcpServers"]

        # Check Qwen settings
        qwen_path = temp_agentbox / "qwen" / "settings.json"
        assert qwen_path.exists()
        qwen_config = json.loads(qwen_path.read_text())
        assert "test-server" in qwen_config["mcpServers"]

        # Check Codex config (TOML)
        codex_path = temp_agentbox / "codex" / "config.toml"
        assert codex_path.exists()
        codex_content = codex_path.read_text()
        assert "test-server" in codex_content

    def test_skips_sse_for_codex(self, temp_agentbox):
        """SSE servers are skipped for Codex but included for Gemini/Qwen."""
        mcp_config = {
            "mcpServers": {
                "sse-server": {
                    "type": "sse",
                    "url": "http://localhost:9000/sse",
                },
                "stdio-server": {
                    "command": "python3",
                    "args": ["/path/to/server.py"],
                },
            }
        }
        (temp_agentbox / "mcp.json").write_text(json.dumps(mcp_config))

        result = subprocess.run(
            ["python3", "/workspace/bin/distribute-mcp-config.py", "--agentbox", str(temp_agentbox)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Gemini should have both
        gemini_config = json.loads((temp_agentbox / "gemini" / "settings.json").read_text())
        assert "sse-server" in gemini_config["mcpServers"]
        assert "stdio-server" in gemini_config["mcpServers"]

        # Codex should only have STDIO
        codex_content = (temp_agentbox / "codex" / "config.toml").read_text()
        assert "stdio-server" in codex_content
        assert "sse-server" not in codex_content

    def test_detects_url_only_as_sse(self, temp_agentbox):
        """Servers with url but no command are treated as SSE."""
        mcp_config = {
            "mcpServers": {
                "url-only-server": {
                    "url": "http://localhost:9000/sse",
                },
            }
        }
        (temp_agentbox / "mcp.json").write_text(json.dumps(mcp_config))

        result = subprocess.run(
            ["python3", "/workspace/bin/distribute-mcp-config.py", "--agentbox", str(temp_agentbox)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Codex should not have the URL-only server
        codex_content = (temp_agentbox / "codex" / "config.toml").read_text()
        assert "url-only-server" not in codex_content

    def test_fallback_to_claude_mcp(self, temp_agentbox):
        """Falls back to claude/mcp.json if unified mcp.json doesn't exist."""
        # Create claude subdirectory with mcp.json
        claude_dir = temp_agentbox / "claude"
        claude_dir.mkdir()
        mcp_config = {
            "mcpServers": {
                "fallback-server": {
                    "command": "test",
                    "args": [],
                }
            }
        }
        (claude_dir / "mcp.json").write_text(json.dumps(mcp_config))

        result = subprocess.run(
            ["python3", "/workspace/bin/distribute-mcp-config.py", "--agentbox", str(temp_agentbox)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0

        # Gemini should have the fallback server
        gemini_config = json.loads((temp_agentbox / "gemini" / "settings.json").read_text())
        assert "fallback-server" in gemini_config["mcpServers"]
