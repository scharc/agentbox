#!/usr/bin/env python3
"""Generate Claude MCP Config

Reads mcp-meta.json and port mapping to generate .mcp.json in project root
with SSE URLs for pre-started servers and STDIO for others.

Usage:
    generate-mcp-config.py [--meta PATH] [--ports PATH] [--output PATH]
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# Library configs for STDIO servers (command + args)
# These are used when no SSE port is available
STDIO_CONFIGS = {
    "agentctl": {
        "command": "python3",
        "args": ["/workspace/.agentbox/mcp/agentctl/server_fastmcp.py"]
    },
    "agentbox-notify": {
        "command": "python3",
        "args": ["/workspace/.agentbox/mcp/agentbox-notify/server.py"]
    },
    # npm servers
    "ssh": {
        "command": "npx",
        "args": ["-y", "@aiondadotcom/mcp-ssh"]
    },
    "docker": {
        "command": "bash",
        "args": ["/workspace/.agentbox/mcp/docker-mcp-wrapper.sh"]
    },
    "playwright": {
        "command": "npx",
        "args": ["@playwright/mcp@latest", "--headless"]
    },
    "postgres": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-postgres"]
    },
    "github": {
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"]
    },
    "fetch": {
        "command": "npx",
        "args": ["-y", "@anthropic-ai/mcp-server-fetch"]
    },
    # uvx servers
    "sqlite": {
        "command": "uvx",
        "args": ["mcp-server-sqlite"]
    },
    "redis": {
        "command": "uvx",
        "args": ["redis-mcp-server"]
    },
    "git": {
        "command": "uvx",
        "args": ["mcp-server-git"]
    },
    # pip servers - PYTHONPATH is set globally in Dockerfile
    "mysql": {
        "command": "mysql_mcp_server"
    },
}


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file if it exists."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def generate_mcp_config(
    meta: Dict[str, Any],
    ports: Dict[str, Any],
    existing_config: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate MCP config with SSE for available servers, STDIO for others."""

    mcp_servers = {}

    for name, server_meta in meta.get("servers", {}).items():
        if name in ports:
            # Server has SSE port - use SSE transport (takes precedence)
            port_info = ports[name]
            mcp_servers[name] = {
                "type": "sse",
                "url": port_info["url"]
            }
            logger.info(f"Configured '{name}' with SSE: {port_info['url']}")
        elif "config" in server_meta:
            # Use stored config from mcp-meta.json
            mcp_servers[name] = server_meta["config"]
            logger.info(f"Configured '{name}' from stored config")
        elif name in STDIO_CONFIGS:
            # Fallback to hardcoded STDIO config (legacy support)
            config = STDIO_CONFIGS[name].copy()
            mcp_servers[name] = config
            logger.info(f"Configured '{name}' with STDIO fallback")
        else:
            # Last resort - check existing config
            if name in existing_config.get("mcpServers", {}):
                mcp_servers[name] = existing_config["mcpServers"][name]
                logger.info(f"Preserved existing config for '{name}'")
            else:
                logger.warning(f"No config available for '{name}', skipping")

    return {"mcpServers": mcp_servers}


def main():
    parser = argparse.ArgumentParser(description="Generate Claude MCP Config")
    parser.add_argument(
        "--meta",
        type=Path,
        default=Path("/workspace/.agentbox/mcp-meta.json"),
        help="Path to mcp-meta.json"
    )
    parser.add_argument(
        "--ports",
        type=Path,
        default=Path("/tmp/mcp-ports.json"),
        help="Path to port mapping file"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/workspace/.mcp.json"),
        help="Path to output .mcp.json (project-scoped MCP config)"
    )

    args = parser.parse_args()

    # Load inputs
    meta = load_json(args.meta)
    ports = load_json(args.ports)
    existing_config = load_json(args.output)

    if not meta.get("servers"):
        logger.info("No MCP servers configured in mcp-meta.json")
        # Remove .mcp.json if it exists but no servers configured
        if args.output.exists():
            args.output.unlink()
            logger.info(f"Removed {args.output} (no servers)")
        return

    # Generate new config
    new_config = generate_mcp_config(meta, ports, existing_config)
    mcp_servers = new_config.get("mcpServers", {})

    if not mcp_servers:
        logger.info("No MCP servers to configure")
        if args.output.exists():
            args.output.unlink()
            logger.info(f"Removed {args.output} (no servers)")
        return

    # Write to .mcp.json (project-scoped config that Claude reads directly)
    with open(args.output, "w") as f:
        json.dump(new_config, f, indent=2)
    logger.info(f"Generated MCP config: {args.output}")

    # Also write to .agentbox/claude/mcp.json (used by superclaude sessions)
    agentbox_config = Path("/workspace/.agentbox/claude/mcp.json")
    if agentbox_config.parent.exists():
        with open(agentbox_config, "w") as f:
            json.dump(new_config, f, indent=2)
        logger.info(f"Also wrote to: {agentbox_config}")

    # Summary
    sse_count = sum(1 for cfg in mcp_servers.values() if cfg.get("type") == "sse")
    stdio_count = len(mcp_servers) - sse_count
    logger.info(f"Total servers: {len(mcp_servers)}")
    logger.info(f"  SSE servers: {sse_count}")
    logger.info(f"  STDIO servers: {stdio_count}")


if __name__ == "__main__":
    main()
