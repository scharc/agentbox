#!/usr/bin/env python3
"""Generate Claude MCP Config

Reads mcp-meta.json and port mapping to generate .mcp.json in project root
with SSE URLs for pre-started servers and STDIO for others.

Smart config resolution:
- Detects pyproject.toml → wraps command with `uv --directory <path> run`
- Detects package.json → wraps command with `npx --prefix <path>`
- Resolves relative .py paths in args to absolute paths

Usage:
    generate-mcp-config.py [--meta PATH] [--ports PATH] [--output PATH]
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


# Path resolution for different source types
MCP_SOURCE_PATHS = {
    "library": "/boxctl/library/mcp",
    "custom": "/home/abox/.config/boxctl/mcp",
    "project": "/workspace/.boxctl/mcp",
}


def get_mcp_dir(source_type: str, source_name: str) -> Optional[Path]:
    """Get the container path to an MCP directory based on source metadata.

    Args:
        source_type: "library", "custom", or "project"
        source_name: Directory name of the MCP

    Returns:
        Path to MCP directory, or None if source_type is unknown
    """
    base_path = MCP_SOURCE_PATHS.get(source_type)
    if not base_path:
        return None
    return Path(base_path) / source_name


def _is_writable(path: Path) -> bool:
    """Check if a directory is writable."""
    import os
    return os.access(path, os.W_OK)


def resolve_mcp_config(config: Dict[str, Any], mcp_dir: Path) -> Dict[str, Any]:
    """Resolve MCP config with smart detection of project type.

    Detects:
    - pyproject.toml (writable) → wrap with `uv --directory <path> run`
    - pyproject.toml (read-only) → use command directly (pip-installed)
    - package.json (writable) → wrap with `npx --prefix <path>`
    - package.json (read-only) → use command directly (npm-installed)
    - Neither → resolve relative .py paths in args

    Args:
        config: Original config from mcp-meta.json
        mcp_dir: Path to the MCP directory

    Returns:
        Resolved config with proper command/args
    """
    resolved = config.copy()
    command = config.get("command", "")
    args = config.get("args", [])

    has_pyproject = (mcp_dir / "pyproject.toml").exists()
    has_package_json = (mcp_dir / "package.json").exists()
    is_writable = _is_writable(mcp_dir)

    if has_pyproject:
        if is_writable:
            # Writable Python package - wrap with uv --directory
            resolved["command"] = "uv"
            resolved["args"] = ["--directory", str(mcp_dir), "run", command] + list(args)
            logger.debug(f"Wrapped Python package with uv: {mcp_dir}")
        else:
            # Read-only Python package - assume pip-installed, use command directly
            # Keep original command and args
            logger.debug(f"Read-only Python package, using pip-installed command: {command}")

    elif has_package_json:
        if is_writable:
            # Writable Node.js package - wrap with npx --prefix
            resolved["command"] = "npx"
            resolved["args"] = ["--prefix", str(mcp_dir), command] + list(args)
            logger.debug(f"Wrapped Node.js package with npx: {mcp_dir}")
        else:
            # Read-only Node.js package - assume npm-installed, use command directly
            logger.debug(f"Read-only Node.js package, using npm-installed command: {command}")

    else:
        # Raw script - resolve relative paths in args
        resolved_args = []
        for arg in args:
            if isinstance(arg, str) and not arg.startswith("/") and (
                arg.endswith(".py") or arg.endswith(".js") or arg.endswith(".sh")
            ):
                # Relative script path - resolve to absolute
                resolved_args.append(str(mcp_dir / arg))
            else:
                resolved_args.append(arg)
        resolved["args"] = resolved_args
        logger.debug(f"Resolved relative paths for raw script: {mcp_dir}")

    return resolved


# Library configs for STDIO servers (command + args)
# These are used when no SSE port is available
STDIO_CONFIGS = {
    "agentctl": {
        "command": "python3",
        "args": ["/workspace/.boxctl/mcp/agentctl/server_fastmcp.py"]
    },
    "boxctl-notify": {
        "command": "python3",
        "args": ["/workspace/.boxctl/mcp/boxctl-notify/server.py"]
    },
    # npm servers
    "ssh": {
        "command": "npx",
        "args": ["-y", "@aiondadotcom/mcp-ssh"]
    },
    "docker": {
        "command": "bash",
        "args": ["/workspace/.boxctl/mcp/docker-mcp-wrapper.sh"]
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


def load_env_files() -> Dict[str, str]:
    """Load environment variables from MCP .env files.

    Loads from:
    - /workspace/.boxctl/.env
    - /workspace/.boxctl/.env.local
    - /home/abox/.config/boxctl/mcp/*/.env (custom MCP credentials)
    """
    import os
    from pathlib import Path

    env_vars = {}

    def load_env_file(path: Path):
        if not path.exists():
            return
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, _, value = line.partition('=')
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key:
                            env_vars[key] = value
        except Exception as e:
            logger.debug(f"Could not load {path}: {e}")

    # Project env files
    load_env_file(Path("/workspace/.boxctl/.env"))
    load_env_file(Path("/workspace/.boxctl/.env.local"))

    # Custom MCP env files
    mcp_dir = Path("/home/abox/.config/boxctl/mcp")
    if mcp_dir.exists():
        for mcp_path in mcp_dir.iterdir():
            if mcp_path.is_dir():
                load_env_file(mcp_path / ".env")

    return env_vars


def resolve_env_vars(env_dict: Dict[str, str], loaded_env: Dict[str, str]) -> Dict[str, str]:
    """Resolve ${VAR} references in env values.

    Uses loaded_env first, then falls back to os.environ.
    If a value is "${VAR}" and VAR is found, replace it.
    Otherwise, keep the original value (allows runtime resolution by Claude).
    """
    import os
    import re

    resolved = {}
    for key, value in env_dict.items():
        if isinstance(value, str):
            # Match ${VAR} pattern
            match = re.fullmatch(r'\$\{(\w+)\}', value)
            if match:
                var_name = match.group(1)
                # Check loaded env files first, then os.environ
                env_value = loaded_env.get(var_name) or os.environ.get(var_name)
                if env_value:
                    resolved[key] = env_value
                    logger.debug(f"Resolved {key} from environment")
                else:
                    # Keep original - maybe user wants runtime resolution
                    resolved[key] = value
            else:
                resolved[key] = value
        else:
            resolved[key] = value
    return resolved


def generate_mcp_config(
    meta: Dict[str, Any],
    ports: Dict[str, Any],
    existing_config: Dict[str, Any],
    loaded_env: Dict[str, str]
) -> Dict[str, Any]:
    """Generate MCP config with SSE for available servers, STDIO for others.

    Uses smart config resolution:
    - Detects pyproject.toml → wraps with uv --directory
    - Detects package.json → wraps with npx --prefix
    - Resolves relative script paths to absolute
    """

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
            # Use stored config from mcp-meta.json with smart resolution
            config = server_meta["config"].copy()

            # Get MCP directory for smart resolution
            source_type = server_meta.get("source_type")
            source_name = server_meta.get("source_name")

            if source_type and source_name:
                mcp_dir = get_mcp_dir(source_type, source_name)
                if mcp_dir and mcp_dir.exists():
                    # Smart resolution based on project type
                    config = resolve_mcp_config(config, mcp_dir)
                    logger.info(f"Configured '{name}' with smart resolution ({source_type})")
                else:
                    logger.warning(f"MCP dir not found for '{name}': {mcp_dir}")
            else:
                logger.info(f"Configured '{name}' from stored config (no source metadata)")

            # Resolve ${VAR} references in env using loaded env files
            if "env" in config and isinstance(config["env"], dict):
                config["env"] = resolve_env_vars(config["env"], loaded_env)

            mcp_servers[name] = config
        elif name in STDIO_CONFIGS:
            # Fallback to hardcoded STDIO config (legacy support)
            config = STDIO_CONFIGS[name].copy()
            mcp_servers[name] = config
            logger.info(f"Configured '{name}' with STDIO fallback (legacy)")
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
        default=Path("/workspace/.boxctl/mcp-meta.json"),
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
        default=Path("/home/abox/.mcp.json"),
        help="Path to output .mcp.json (Claude reads from home dir)"
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

    # Load environment variables from .env files
    loaded_env = load_env_files()

    # Generate new config
    new_config = generate_mcp_config(meta, ports, existing_config, loaded_env)
    mcp_servers = new_config.get("mcpServers", {})

    if not mcp_servers:
        logger.info("No MCP servers to configure")
        if args.output.exists():
            args.output.unlink()
            logger.info(f"Removed {args.output} (no servers)")
        return

    # Write to ~/.mcp.json (Claude reads MCP config from home dir)
    with open(args.output, "w") as f:
        json.dump(new_config, f, indent=2)
    logger.info(f"Generated MCP config: {args.output}")

    # Summary
    sse_count = sum(1 for cfg in mcp_servers.values() if cfg.get("type") == "sse")
    stdio_count = len(mcp_servers) - sse_count
    logger.info(f"Total servers: {len(mcp_servers)}")
    logger.info(f"  SSE servers: {sse_count}")
    logger.info(f"  STDIO servers: {stdio_count}")


if __name__ == "__main__":
    main()
