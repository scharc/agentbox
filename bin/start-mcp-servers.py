#!/usr/bin/env python3
"""MCP Server Manager

Pre-starts native SSE MCP servers (FastMCP) during container initialization.
This allows Claude to connect instantly without subprocess spawn delay.

Only FastMCP servers (like agentctl) are pre-started with SSE transport.
All other MCPs (npm, uvx) use STDIO and are spawned by Claude on-demand.

Usage:
    start-mcp-servers.py [--meta PATH] [--ports-file PATH] [--base-port PORT]
"""

import argparse
import json
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class McpServerConfig:
    """Configuration for an MCP server (native SSE only)."""
    name: str
    command: List[str]
    port: int
    transport: str = "sse"
    env: Dict[str, str] = field(default_factory=dict)


@dataclass
class McpServerProcess:
    """A running MCP server process."""
    config: McpServerConfig
    process: Optional[subprocess.Popen] = None
    restart_count: int = 0
    last_restart: float = 0


class McpServerManager:
    """Manages MCP server lifecycle."""

    # Known FastMCP servers that support native SSE
    # Only these servers are pre-started with SSE transport
    # All other MCPs use STDIO (spawned by Claude on-demand)
    NATIVE_SSE_SERVERS = {
        "agentctl": {
            "script": "/workspace/.boxctl/mcp/agentctl/server_fastmcp.py",
            "args": ["--transport", "sse"]
        },
        # Add more FastMCP servers here as they're created
    }

    def __init__(
        self,
        meta_path: Path,
        ports_file: Path,
        base_port: int = 9100,
        max_restarts: int = 3,
        restart_backoff: float = 2.0
    ):
        self.meta_path = meta_path
        self.ports_file = ports_file
        self.base_port = base_port
        self.max_restarts = max_restarts
        self.restart_backoff = restart_backoff

        self.servers: Dict[str, McpServerProcess] = {}
        self._running = False

    def load_config(self) -> List[McpServerConfig]:
        """Load MCP server configurations from mcp-meta.json."""
        if not self.meta_path.exists():
            logger.warning(f"MCP meta file not found: {self.meta_path}")
            return []

        with open(self.meta_path) as f:
            meta = json.load(f)

        configs = []
        port = self.base_port

        for name, server_meta in meta.get("servers", {}).items():
            # Only pre-start native SSE servers (FastMCP)
            # All other MCPs use STDIO, spawned by Claude on-demand
            if name in self.NATIVE_SSE_SERVERS:
                native_config = self.NATIVE_SSE_SERVERS[name]
                script = native_config["script"]

                if Path(script).exists():
                    config = McpServerConfig(
                        name=name,
                        command=["python3", script] + native_config.get("args", []),
                        port=port,
                        transport="sse"
                    )
                    configs.append(config)
                    logger.info(f"Found native SSE server: {name} on port {port}")
                    port += 1
                else:
                    logger.warning(f"Native SSE server script not found: {script}")
            else:
                # Not a native SSE server - will use STDIO via generate-mcp-config.py
                logger.info(f"Server '{name}' will use STDIO (spawned by Claude)")

        return configs

    def start_server(self, config: McpServerConfig) -> McpServerProcess:
        """Start a single MCP server."""
        logger.info(f"Starting MCP server '{config.name}' on port {config.port}")

        # Native SSE server (FastMCP) - add port/host args directly
        cmd = config.command + ["--port", str(config.port), "--host", "127.0.0.1"]

        # Prepare environment
        env = os.environ.copy()
        env.update(config.env)
        env["MCP_PORT"] = str(config.port)
        env["MCP_TRANSPORT"] = config.transport

        # Start process
        log_file = Path(f"/tmp/mcp-{config.name}.log")

        with open(log_file, "a") as log:
            process = subprocess.Popen(
                cmd,
                stdout=log,
                stderr=subprocess.STDOUT,
                env=env,
                start_new_session=True,  # Detach from parent
            )

        server = McpServerProcess(config=config, process=process)
        self.servers[config.name] = server

        logger.info(f"Started '{config.name}' with PID {process.pid}, log: {log_file}")
        return server

    def check_server_health(self, server: McpServerProcess, timeout: float = 5.0) -> bool:
        """Check if server is healthy by testing the port."""
        import socket

        start = time.time()
        while time.time() - start < timeout:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex(("127.0.0.1", server.config.port))
                sock.close()

                if result == 0:
                    logger.info(f"Server '{server.config.name}' is healthy on port {server.config.port}")
                    return True
            except Exception:
                pass

            time.sleep(0.5)

        logger.warning(f"Server '{server.config.name}' health check failed")
        return False

    def restart_server(self, server: McpServerProcess) -> bool:
        """Restart a failed server with backoff."""
        if server.restart_count >= self.max_restarts:
            logger.error(f"Server '{server.config.name}' exceeded max restarts ({self.max_restarts})")
            return False

        # Calculate backoff
        backoff = self.restart_backoff ** server.restart_count
        time_since_last = time.time() - server.last_restart

        if time_since_last < backoff:
            sleep_time = backoff - time_since_last
            logger.info(f"Waiting {sleep_time:.1f}s before restarting '{server.config.name}'")
            time.sleep(sleep_time)

        # Kill existing process if still running
        if server.process and server.process.poll() is None:
            server.process.terminate()
            try:
                server.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.process.kill()

        # Restart
        server.restart_count += 1
        server.last_restart = time.time()

        logger.info(f"Restarting '{server.config.name}' (attempt {server.restart_count})")
        new_server = self.start_server(server.config)
        new_server.restart_count = server.restart_count
        new_server.last_restart = server.last_restart

        return self.check_server_health(new_server)

    def start_all(self) -> bool:
        """Start all configured MCP servers."""
        configs = self.load_config()

        if not configs:
            logger.info("No MCP servers to start")
            return True

        # Start each server
        all_healthy = True
        for config in configs:
            server = self.start_server(config)

            if not self.check_server_health(server):
                logger.warning(f"Server '{config.name}' failed initial health check")
                all_healthy = False

        # Write port mapping
        self.write_ports_file()

        return all_healthy

    def write_ports_file(self):
        """Write port mapping to file for config generation."""
        ports = {}
        for name, server in self.servers.items():
            if server.process and server.process.poll() is None:
                ports[name] = {
                    "port": server.config.port,
                    "url": f"http://127.0.0.1:{server.config.port}/sse",
                    "transport": server.config.transport,
                    "pid": server.process.pid
                }

        self.ports_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.ports_file, "w") as f:
            json.dump(ports, f, indent=2)

        logger.info(f"Wrote port mapping to {self.ports_file}")

    def monitor(self):
        """Monitor servers and restart failed ones."""
        self._running = True

        while self._running:
            for name, server in list(self.servers.items()):
                if server.process and server.process.poll() is not None:
                    # Process died
                    exit_code = server.process.returncode
                    logger.warning(f"Server '{name}' exited with code {exit_code}")

                    if not self.restart_server(server):
                        logger.error(f"Failed to restart '{name}', giving up")

            # Update ports file periodically
            self.write_ports_file()

            time.sleep(5)

    def stop_all(self):
        """Stop all servers."""
        self._running = False

        for name, server in self.servers.items():
            if server.process and server.process.poll() is None:
                logger.info(f"Stopping '{name}' (PID {server.process.pid})")
                server.process.terminate()
                try:
                    server.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.process.kill()

        logger.info("All MCP servers stopped")


def main():
    parser = argparse.ArgumentParser(description="MCP Server Manager")
    parser.add_argument(
        "--meta",
        type=Path,
        default=Path("/workspace/.boxctl/mcp-meta.json"),
        help="Path to mcp-meta.json"
    )
    parser.add_argument(
        "--ports-file",
        type=Path,
        default=Path("/tmp/mcp-ports.json"),
        help="Path to write port mapping"
    )
    parser.add_argument(
        "--base-port",
        type=int,
        default=9100,
        help="Base port for MCP servers (default: 9100)"
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="Start servers and exit (don't monitor)"
    )

    args = parser.parse_args()

    manager = McpServerManager(
        meta_path=args.meta,
        ports_file=args.ports_file,
        base_port=args.base_port
    )

    # Handle signals
    def signal_handler(signum, frame):
        logger.info(f"Received signal {signum}")
        manager.stop_all()
        sys.exit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Start all servers
    if not manager.start_all():
        logger.warning("Some servers failed to start")
        # Continue anyway - partial success is still useful

    if args.no_monitor:
        logger.info("Servers started, exiting (no-monitor mode)")
        return

    # Monitor loop
    logger.info("Entering monitoring loop")
    try:
        manager.monitor()
    except KeyboardInterrupt:
        pass
    finally:
        manager.stop_all()


if __name__ == "__main__":
    main()
