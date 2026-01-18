# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Agentbox host daemon (agentboxd).

The central daemon that runs on the host and provides:
- Desktop notifications from containers
- Clipboard integration
- Port tunneling (container <-> host)
- Session streaming
- Completion data for CLI
"""

from __future__ import annotations

import json
import os
import re
import signal
import socket
import subprocess
import shutil
import sys
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentbox.host_config import get_config
from agentbox.ssh_tunnel import SSHTunnelServer, check_asyncssh_available
from agentbox.utils.logging import get_daemon_logger, configure_logging

# Configure logging for daemon mode
configure_logging(daemon=True)
logger = get_daemon_logger("agentboxd")

# Buffer limits to prevent memory exhaustion (Finding #6)
MAX_RECV_BUFFER_SIZE = 10 * 1024 * 1024  # 10MB max receive buffer
MAX_MESSAGE_SIZE = 5 * 1024 * 1024  # 5MB max single message


def _handle_sigpipe(signum, frame):
    """Handle SIGPIPE gracefully instead of crashing."""
    logger.debug("Received SIGPIPE, ignoring")


# Ignore SIGPIPE to prevent crashes on broken pipes
signal.signal(signal.SIGPIPE, _handle_sigpipe)


def _default_socket_path() -> Path:
    return Path(f"/run/user/{os.getuid()}/agentboxd/agentboxd.sock")


def _ssh_socket_path() -> Path:
    return Path(f"/run/user/{os.getuid()}/agentboxd/ssh.sock")


class Agentboxd:
    def __init__(self, socket_path: Path) -> None:
        self.socket_path = socket_path
        self.config = get_config()
        self.recent_notifications = {}  # Deduplication: (container, session) -> timestamp
        self.notifications_lock = threading.Lock()  # Protects recent_notifications
        self.handlers = {
            "notify": self._handle_notify,
            "clipboard": self._handle_clipboard,
            "add_host_port": self._handle_add_host_port,
            "add_container_port": self._handle_add_container_port,
            "remove_host_port": self._handle_remove_host_port,
            "remove_container_port": self._handle_remove_container_port,
            "get_completions": self._handle_get_completions,
        }
        # Streaming support: container -> {session -> {buffer, cursor_x, cursor_y}}
        self.session_buffers: Dict[str, Dict[str, Dict]] = {}
        self.stream_lock = threading.Lock()
        # Stream subscribers: (container, session) -> list of callbacks
        self.stream_subscribers: Dict[Tuple[str, str], list] = {}
        self.subscribers_lock = threading.Lock()
        # Container state (pushed from containers): container -> {worktrees: [...], ...}
        self.container_state: Dict[str, Dict] = {}
        self.container_state_lock = threading.Lock()
        # Tailscale IP monitoring
        self.tailscale_monitor_thread: Optional[threading.Thread] = None
        self.tailscale_monitor_running = False
        self._current_tailscale_ip: Optional[str] = None
        self._web_server_restart_event: Optional[threading.Event] = None
        # SSH tunnel server (AsyncSSH-based implementation)
        # Handles all container communication via SSH control channel and port forwarding
        if not check_asyncssh_available():
            raise RuntimeError(
                "asyncssh is required but not available. "
                "Install it with: pip install asyncssh"
            )
        self.ssh_tunnel_server = SSHTunnelServer(
            socket_path=_ssh_socket_path(),
            allowed_hosts={"127.0.0.1", "localhost"},
            get_bind_addresses=self._get_bind_addresses,
        )
        # Register control channel handlers
        self._register_ssh_handlers()
        logger.info("SSH tunnel server initialized")
        # Cleanup timestamp tracking
        self._last_cleanup_time = time.time()
        self.session_activity: Dict[Tuple[str, str], float] = {}

    def _handle_notify(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        title = str(payload.get("title", "Agentbox"))
        message = str(payload.get("message", "Notification"))
        urgency = str(payload.get("urgency", "normal"))
        if urgency == "high":
            urgency = "critical"

        args = ["notify-send", "-u", urgency, title, message]
        logger.debug(f"Notify: title={title!r} message={message!r}")
        try:
            result = subprocess.run(args, check=False, capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("notify-send timed out")
            return {"ok": False, "error": "notify_timeout"}

        if urgency == "critical":
            self._beep()

        # Run user hook if configured
        self._run_notify_hook(title, message, urgency)

        if result.returncode != 0:
            logger.warning(result.stderr.strip() or "notify-send failed")
            return {"ok": False, "error": result.stderr.strip() or "notify_failed"}
        return {"ok": True}

    def _handle_clipboard(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle clipboard set requests from containers.

        Uses wl-copy for Wayland or xclip for X11 to set the host clipboard.
        """
        data = payload.get("data", "")
        selection = payload.get("selection", "primary")  # primary or clipboard

        if not data:
            return {"ok": False, "error": "empty_data"}

        # Try wl-copy first (Wayland), fall back to xclip (X11)
        if shutil.which("wl-copy"):
            if selection == "primary":
                cmd = ["wl-copy", "--primary"]
            else:
                cmd = ["wl-copy"]
        elif shutil.which("xclip"):
            cmd = ["xclip", "-selection", selection]
        elif shutil.which("xsel"):
            if selection == "primary":
                cmd = ["xsel", "--primary", "--input"]
            else:
                cmd = ["xsel", "--clipboard", "--input"]
        else:
            logger.warning("No clipboard tool found (wl-copy, xclip, xsel)")
            return {"ok": False, "error": "no_clipboard_tool"}

        try:
            # Use Popen to avoid blocking on wl-copy which daemonizes to serve clipboard
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
            # Write data and close stdin - wl-copy reads this then forks to background
            proc.stdin.write(data)
            proc.stdin.close()

            # Give wl-copy a moment to process and fork (typically <100ms)
            try:
                proc.wait(timeout=0.5)
            except subprocess.TimeoutExpired:
                # wl-copy daemonized successfully (still running = good)
                pass

            return {"ok": True}
        except OSError as e:
            logger.error(f"Clipboard exception: {e}")
            return {"ok": False, "error": str(e)}

    def _handle_add_host_port(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request to add a host port listener (expose container to host)."""
        container = payload.get("container")
        host_port = payload.get("host_port")
        container_port = payload.get("container_port", host_port)

        if not container or not host_port:
            return {"ok": False, "error": "missing required fields: container, host_port"}

        # Send request to container to set up remote forward via SSH
        with self.ssh_tunnel_server.connections_lock:
            if container not in self.ssh_tunnel_server.connections:
                return {"ok": False, "error": f"container {container} not connected"}

        response = self.ssh_tunnel_server.request_to_container_sync(
            container,
            "port_add",
            {
                "direction": "remote",
                "host_port": host_port,
                "container_port": container_port,
                "name": f"dynamic-{host_port}",
            },
            timeout=10.0,
        )
        if response is None:
            return {"ok": False, "error": "failed to communicate with container"}
        if response.get("ok"):
            return {"ok": True, "message": f"Port {host_port} exposed via SSH tunnel"}
        else:
            error = response.get("error", "unknown error")
            return {"ok": False, "error": error}

    def _handle_add_container_port(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request to forward a host port into the container.

        This sets up a local forward: container listens on container_port
        and forwards connections to host_port on the host.
        """
        container = payload.get("container")
        host_port = payload.get("host_port")
        container_port = payload.get("container_port", host_port)

        if not container or not host_port:
            return {"ok": False, "error": "missing required fields: container, host_port"}

        # Check if container is connected
        with self.ssh_tunnel_server.connections_lock:
            if container not in self.ssh_tunnel_server.connections:
                return {"ok": False, "error": f"container {container} not connected"}

        # Send request to container to set up local forward via SSH
        response = self.ssh_tunnel_server.request_to_container_sync(
            container,
            "port_add",
            {
                "direction": "local",
                "host_port": host_port,
                "container_port": container_port,
                "name": f"dynamic-{host_port}",
            },
            timeout=10.0,
        )
        if response is None:
            return {"ok": False, "error": "failed to communicate with container"}
        if response.get("ok"):
            return {"ok": True, "message": f"Host port {host_port} forwarded into container"}
        else:
            error = response.get("error", "unknown error")
            return {"ok": False, "error": error}

    def _handle_remove_host_port(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request to remove a host port listener (unexpose).

        This removes a remote forward: host stops listening, container stops forwarding.
        """
        container = payload.get("container")
        host_port = payload.get("host_port")

        if not container or not host_port:
            return {"ok": False, "error": "missing required fields: container, host_port"}

        # Check if container is connected
        with self.ssh_tunnel_server.connections_lock:
            if container not in self.ssh_tunnel_server.connections:
                return {"ok": False, "error": f"container {container} not connected"}

        # Send request to container to remove remote forward
        response = self.ssh_tunnel_server.request_to_container_sync(
            container,
            "port_remove",
            {
                "direction": "remote",
                "host_port": host_port,
            },
            timeout=10.0,
        )
        if response is None:
            return {"ok": False, "error": "failed to communicate with container"}
        if response.get("ok"):
            return {"ok": True, "message": f"Port {host_port} unexposed"}
        else:
            error = response.get("error", "unknown error")
            return {"ok": False, "error": error}

    def _handle_remove_container_port(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle request to remove a forwarded host port from container.

        This removes a local forward: container stops listening on the port.
        """
        container = payload.get("container")
        host_port = payload.get("host_port")

        if not container or not host_port:
            return {"ok": False, "error": "missing required fields: container, host_port"}

        # Check if container is connected
        with self.ssh_tunnel_server.connections_lock:
            if container not in self.ssh_tunnel_server.connections:
                return {"ok": False, "error": f"container {container} not connected"}

        # Send request to container to remove local forward
        response = self.ssh_tunnel_server.request_to_container_sync(
            container,
            "port_remove",
            {
                "direction": "local",
                "host_port": host_port,
            },
            timeout=10.0,
        )
        if response is None:
            return {"ok": False, "error": "failed to communicate with container"}
        if response.get("ok"):
            return {"ok": True, "message": f"Port {host_port} unforwarded"}
        else:
            error = response.get("error", "unknown error")
            return {"ok": False, "error": error}

    def _handle_get_completions(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle completion data requests for CLI tab-completion.

        This provides fast completion data by using cached state instead of
        making Docker API calls. Supports:
        - projects: Connected container project names
        - sessions: Active tmux sessions
        - worktrees: Git worktrees (pushed from containers)
        - mcp: MCP server names from library
        - skills: Skill names from library
        - docker_containers: Non-agentbox docker containers
        """
        comp_type = payload.get("type")

        if comp_type == "projects":
            # Return project names from connected containers (via SSH tunnel)
            with self.ssh_tunnel_server.connections_lock:
                projects = []
                for container_name in self.ssh_tunnel_server.connections.keys():
                    # Only include agentbox containers, strip prefix to get project name
                    if container_name.startswith("agentbox-"):
                        projects.append(container_name[9:])
            return {"ok": True, "projects": projects}

        elif comp_type == "sessions":
            # Return sessions from session_buffers
            project = payload.get("project")
            with self.stream_lock:
                if project:
                    # Sanitize project name to match Docker container naming
                    sanitized = re.sub(r'[^a-z0-9_-]', '-', project.lower())
                    container = f"agentbox-{sanitized}"
                    sessions = list(self.session_buffers.get(container, {}).keys())
                else:
                    # Return all sessions as "project/session" (only agentbox containers)
                    sessions = []
                    for container, sess_dict in self.session_buffers.items():
                        if not container.startswith("agentbox-"):
                            continue  # Skip non-agentbox containers
                        proj = container[9:]
                        for sess in sess_dict.keys():
                            sessions.append(f"{proj}/{sess}")
            return {"ok": True, "sessions": sessions}

        elif comp_type == "worktrees":
            # Return cached worktrees from container state
            project = payload.get("project")
            with self.container_state_lock:
                if project:
                    # Sanitize project name to match Docker container naming
                    sanitized = re.sub(r'[^a-z0-9_-]', '-', project.lower())
                    container = f"agentbox-{sanitized}"
                    state = self.container_state.get(container, {})
                    worktrees = state.get("worktrees", [])
                else:
                    # Return all worktrees (only from agentbox containers)
                    worktrees = []
                    for container, state in self.container_state.items():
                        if not container.startswith("agentbox-"):
                            continue  # Skip non-agentbox containers
                        worktrees.extend(state.get("worktrees", []))
            return {"ok": True, "worktrees": worktrees}

        elif comp_type == "mcp":
            # Query MCP servers on demand (fast: ~1ms)
            try:
                from agentbox.library import LibraryManager
                lib = LibraryManager()
                servers = lib.list_mcp_servers()
                names = [s["name"] for s in servers]
                return {"ok": True, "mcp_servers": names}
            except Exception as e:
                logger.debug(f"Error listing MCP servers: {e}")
                return {"ok": True, "mcp_servers": []}

        elif comp_type == "skills":
            # Query skills on demand (fast: ~23ms)
            try:
                from agentbox.library import LibraryManager
                lib = LibraryManager()
                skills = lib.list_skills()
                names = [s["name"] for s in skills]
                return {"ok": True, "skills": names}
            except Exception as e:
                logger.debug(f"Error listing skills: {e}")
                return {"ok": True, "skills": []}

        elif comp_type == "docker_containers":
            # Query non-agentbox docker containers
            include_agentbox = payload.get("include_agentbox", False)
            try:
                from agentbox.container import ContainerManager
                manager = ContainerManager()
                containers = manager.get_all_containers(include_agentbox=include_agentbox)
                names = [c["name"] for c in containers]
                return {"ok": True, "docker_containers": names}
            except Exception as e:
                logger.debug(f"Error listing docker containers: {e}")
                return {"ok": True, "docker_containers": []}

        return {"ok": False, "error": f"unknown completion type: {comp_type}"}

    def _run_notify_hook(self, title: str, message: str, urgency: str) -> None:
        """Run user notify hook script if configured."""
        hook_path = self.config.get("notify_hook")
        if not hook_path:
            return

        hook = Path(hook_path).expanduser()
        if not hook.exists() or not hook.is_file():
            return

        try:
            subprocess.run(
                [str(hook), title, message, urgency],
                check=False,
                capture_output=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as e:
            logger.warning(f"Notify hook failed: {e}")

    def _beep(self) -> None:
        sound = Path("/usr/share/sounds/freedesktop/stereo/bell.oga")
        if sound.exists() and shutil.which("paplay"):
            try:
                subprocess.run(["paplay", str(sound)], check=False, timeout=5)
            except subprocess.TimeoutExpired:
                pass
            return
        try:
            with open("/dev/tty", "w", encoding="utf-8") as tty:
                tty.write("\a")
                tty.flush()
        except Exception:
            pass

    def _get_bind_addresses(self) -> list:
        """Get list of addresses to bind port listeners to.

        Reads from config network.bind_addresses, resolving "tailscale"
        to the current Tailscale IP from the monitor.
        """
        cfg = self.config.get("network", default={})
        configured = cfg.get("bind_addresses", ["127.0.0.1", "tailscale"])

        resolved = []
        for addr in configured:
            if addr.lower() == "tailscale":
                if self._current_tailscale_ip:
                    resolved.append(self._current_tailscale_ip)
            else:
                resolved.append(addr)

        return resolved if resolved else ["127.0.0.1"]

    def _register_ssh_handlers(self) -> None:
        """Register all handlers for the SSH control channel."""
        if not self.ssh_tunnel_server:
            return

        # Request handlers (expect response)
        self.ssh_tunnel_server.register_request_handler("notify", self._ssh_handle_notify)
        self.ssh_tunnel_server.register_request_handler("clipboard_set", self._ssh_handle_clipboard)
        self.ssh_tunnel_server.register_request_handler("get_completions", self._ssh_handle_get_completions)
        self.ssh_tunnel_server.register_request_handler("port_add", self._ssh_handle_port_add)
        self.ssh_tunnel_server.register_request_handler("port_remove", self._ssh_handle_port_remove)
        self.ssh_tunnel_server.register_request_handler("ping", self._ssh_handle_ping)

        # Event handlers (no response)
        self.ssh_tunnel_server.register_event_handler("stream_register", self._ssh_handle_stream_register)
        self.ssh_tunnel_server.register_event_handler("stream_data", self._ssh_handle_stream_data)
        self.ssh_tunnel_server.register_event_handler("stream_unregister", self._ssh_handle_stream_unregister)
        self.ssh_tunnel_server.register_event_handler("state_update", self._ssh_handle_state_update)
        self.ssh_tunnel_server.register_event_handler("forward_removed", self._ssh_handle_forward_removed)

        # Internal events for connection lifecycle
        self.ssh_tunnel_server.register_event_handler("_container_connect", self._ssh_on_container_connect)
        self.ssh_tunnel_server.register_event_handler("_container_disconnect", self._ssh_on_container_disconnect)

        logger.debug("Registered SSH control channel handlers")

    # ========== SSH Control Channel Handlers ==========

    def _ssh_handle_notify(self, container: str, payload: dict) -> dict:
        """Handle notify request from SSH control channel."""
        # Reuse existing notify handler
        result = self._handle_notify(payload)
        return result

    def _ssh_handle_clipboard(self, container: str, payload: dict) -> dict:
        """Handle clipboard_set request from SSH control channel."""
        # Convert to action format and reuse handler
        clipboard_payload = {
            "data": payload.get("data", ""),
            "selection": payload.get("selection", "clipboard"),
        }
        result = self._handle_clipboard(clipboard_payload)
        return result

    def _ssh_handle_get_completions(self, container: str, payload: dict) -> dict:
        """Handle get_completions request from SSH control channel."""
        result = self._handle_get_completions(payload)
        return {"ok": True, "data": result}

    def _ssh_handle_port_add(self, container: str, payload: dict) -> dict:
        """Handle dynamic port add request from container.

        In SSH mode, the container must request the port forward via SSH protocol.
        This handler just updates allowlists and policies.
        """
        direction = payload.get("direction")
        host_port = payload.get("host_port")
        container_port = payload.get("container_port", host_port)

        if direction == "remote":
            # Host→Container: container is requesting a remote forward
            # The SSH protocol handles the actual binding; we just need to allow it
            # The container will call forward_remote_port() after this returns
            logger.info(f"Container {container} requesting remote forward: host:{host_port} -> container:{container_port}")
            return {"ok": True, "data": {"host_port": host_port, "container_port": container_port}}
        else:
            # Container→Host: add to allowed ports so SSH accepts the forward
            if self.ssh_tunnel_server:
                self.ssh_tunnel_server.add_allowed_port(host_port)
            logger.info(f"Container {container} requesting local forward: container:{container_port} -> host:{host_port}")
            return {"ok": True}

    def _ssh_handle_port_remove(self, container: str, payload: dict) -> dict:
        """Handle dynamic port remove request."""
        direction = payload.get("direction")
        host_port = payload.get("host_port")

        if direction == "remote":
            return self._handle_remove_host_port({
                "container": container,
                "host_port": host_port,
            })
        else:
            if self.ssh_tunnel_server:
                self.ssh_tunnel_server.remove_allowed_port(host_port)
            return {"ok": True}

    def _ssh_handle_ping(self, container: str, payload: dict) -> dict:
        """Handle ping request."""
        return {"ok": True}

    def _ssh_handle_stream_register(self, container: str, payload: dict) -> None:
        """Handle stream_register event from SSH control channel."""
        session = payload.get("session", "unknown")
        logger.debug(f"SSH stream register: {container}/{session}")
        with self.stream_lock:
            if container not in self.session_buffers:
                self.session_buffers[container] = {}

    def _ssh_handle_stream_data(self, container: str, payload: dict) -> None:
        """Handle stream_data event from SSH control channel."""
        session = payload.get("session", "unknown")
        data = payload.get("data", "")
        cursor_x = payload.get("cursor_x", 0)
        cursor_y = payload.get("cursor_y", 0)
        pane_width = payload.get("pane_width", 80)
        pane_height = payload.get("pane_height", 24)

        stream_data = {
            "buffer": data,
            "cursor_x": cursor_x,
            "cursor_y": cursor_y,
            "pane_width": pane_width,
            "pane_height": pane_height,
        }

        with self.stream_lock:
            if container not in self.session_buffers:
                self.session_buffers[container] = {}
            self.session_buffers[container][session] = stream_data

        # Notify subscribers
        self._notify_stream_subscribers(container, session, stream_data)

    def _ssh_handle_stream_unregister(self, container: str, payload: dict) -> None:
        """Handle stream_unregister event from SSH control channel."""
        session = payload.get("session", "unknown")
        logger.debug(f"SSH stream unregister: {container}/{session}")
        with self.stream_lock:
            if container in self.session_buffers:
                self.session_buffers[container].pop(session, None)
            key = (container, session)
            self.session_activity.pop(key, None)

    def _ssh_handle_state_update(self, container: str, payload: dict) -> None:
        """Handle state_update event from SSH control channel."""
        with self.container_state_lock:
            if container not in self.container_state:
                self.container_state[container] = {}
            if "worktrees" in payload:
                self.container_state[container]["worktrees"] = payload["worktrees"]
                logger.debug(f"SSH state update: {container} worktrees={payload['worktrees']}")

    def _ssh_handle_forward_removed(self, container: str, payload: dict) -> None:
        """Handle forward_removed event - update server-side tracking."""
        direction = payload.get("direction")
        host_port = payload.get("host_port")

        if not direction or not host_port:
            return

        with self.ssh_tunnel_server.connections_lock:
            conn = self.ssh_tunnel_server.connections.get(container)
            if not conn:
                return

            if direction == "local":
                conn.local_forwards = [
                    f for f in conn.local_forwards if f.get("host_port") != host_port
                ]
                logger.debug(f"Removed local forward tracking: {container}:{host_port}")
            elif direction == "remote":
                conn.remote_forwards = [
                    f for f in conn.remote_forwards if f.get("host_port") != host_port
                ]
                logger.debug(f"Removed remote forward tracking: {container}:{host_port}")

    def _ssh_on_container_connect(self, container: str) -> None:
        """Handle container connect event."""
        logger.info(f"SSH tunnel: container {container} connected")

    def _ssh_on_container_disconnect(self, container: str) -> None:
        """Handle container disconnect event."""
        logger.info(f"SSH tunnel: container {container} disconnected")

        # Clean up session buffers for this container
        sessions_to_cleanup = []
        with self.stream_lock:
            if container in self.session_buffers:
                sessions_to_cleanup = list(self.session_buffers[container].keys())
            self.session_buffers.pop(container, None)

        # Clean up session activity tracking
        for session in sessions_to_cleanup:
            key = (container, session)
            self.session_activity.pop(key, None)

        # Clean up stream subscribers
        with self.subscribers_lock:
            keys_to_remove = [k for k in self.stream_subscribers if k[0] == container]
            for key in keys_to_remove:
                self.stream_subscribers.pop(key, None)

        # Clean up container state
        with self.container_state_lock:
            self.container_state.pop(container, None)

    def _check_tailscale_ip(self) -> bool:
        """Check if Tailscale IP has changed.

        Returns True if IP changed and rebind is needed.
        """
        from agentbox.host_config import get_tailscale_ip

        # Only check if tailscale is configured (hosts or bind_addresses)
        if not self.config.uses_tailscale():
            return False

        expected_ip = get_tailscale_ip()

        if expected_ip != self._current_tailscale_ip:
            old_ip = self._current_tailscale_ip
            self._current_tailscale_ip = expected_ip

            if old_ip is None and expected_ip is not None:
                logger.info(f"Tailscale IP now available: {expected_ip}")
                return True
            elif old_ip is not None and expected_ip is None:
                logger.info(f"Tailscale IP no longer available (was {old_ip})")
                return True
            elif old_ip != expected_ip:
                logger.info(f"Tailscale IP changed: {old_ip} -> {expected_ip}")
                return True

        return False

    def _tailscale_monitor_loop(self) -> None:
        """Background thread loop that checks for Tailscale IP changes."""
        config = self.config.get("tailscale_monitor", default={})
        check_interval = float(config.get("check_interval_seconds", 30.0))

        while self.tailscale_monitor_running:
            try:
                if self._check_tailscale_ip():
                    # Signal web server to restart
                    if self._web_server_restart_event:
                        self._web_server_restart_event.set()
            except OSError as e:
                logger.error(f"Tailscale monitor error: {e}")
            time.sleep(check_interval)

    def _start_tailscale_monitor(self) -> None:
        """Start the Tailscale IP monitor thread."""
        from agentbox.host_config import get_tailscale_ip

        # Only start if "tailscale" is configured (hosts or bind_addresses)
        if not self.config.uses_tailscale():
            return

        config = self.config.get("tailscale_monitor", default={})
        if not config.get("enabled", True):
            return

        # Initialize current IP
        self._current_tailscale_ip = get_tailscale_ip()

        self.tailscale_monitor_running = True
        self.tailscale_monitor_thread = threading.Thread(
            target=self._tailscale_monitor_loop,
            daemon=True,
            name="tailscale-monitor"
        )
        self.tailscale_monitor_thread.start()
        logger.info(f"Tailscale monitor started (current IP: {self._current_tailscale_ip})")

    def _stop_tailscale_monitor(self) -> None:
        """Stop the Tailscale IP monitor thread."""
        if self.tailscale_monitor_thread and self.tailscale_monitor_running:
            self.tailscale_monitor_running = False
            self.tailscale_monitor_thread.join(timeout=2.0)
            logger.info("Tailscale monitor stopped")

    def get_session_buffer(self, container: str, session: str) -> Optional[str]:
        """Get cached buffer for a session (thread-safe)."""
        with self.stream_lock:
            data = self.session_buffers.get(container, {}).get(session)
            if data:
                return data.get("buffer")
            return None

    def get_session_cursor(self, container: str, session: str) -> tuple:
        """Get cached cursor position and pane size for a session (thread-safe).

        Returns: (cursor_x, cursor_y, pane_width, pane_height)
        """
        with self.stream_lock:
            data = self.session_buffers.get(container, {}).get(session)
            if data:
                return (
                    data.get("cursor_x", 0),
                    data.get("cursor_y", 0),
                    data.get("pane_width", 0),
                    data.get("pane_height", 0)
                )
            return (0, 0, 0, 0)

    def subscribe_to_stream(self, container: str, session: str, callback) -> None:
        """Subscribe to stream updates for a session.

        The callback will be called with stream data dict whenever new data arrives.
        Callbacks should be fast and non-blocking (e.g., put to asyncio queue).
        """
        key = (container, session)
        with self.subscribers_lock:
            if key not in self.stream_subscribers:
                self.stream_subscribers[key] = []
            self.stream_subscribers[key].append(callback)

    def unsubscribe_from_stream(self, container: str, session: str, callback) -> None:
        """Unsubscribe from stream updates."""
        key = (container, session)
        with self.subscribers_lock:
            if key in self.stream_subscribers:
                try:
                    self.stream_subscribers[key].remove(callback)
                    if not self.stream_subscribers[key]:
                        del self.stream_subscribers[key]
                except ValueError:
                    pass  # Callback not found

    def _notify_stream_subscribers(self, container: str, session: str, data: dict) -> None:
        """Notify all subscribers of new stream data."""
        key = (container, session)
        with self.subscribers_lock:
            callbacks = self.stream_subscribers.get(key, []).copy()

        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"Stream subscriber callback error: {e}")

    def send_input_to_daemon(self, container: str, session: str, keys: str, literal: bool = True) -> bool:
        """Send input to a container's streaming daemon via SSH control channel."""
        payload = {
            "session": session,
            "keys": keys,
            "literal": literal,
        }
        return self.ssh_tunnel_server.send_to_container_sync(container, "stream_input", payload)

    def _handle_request(self, raw: bytes) -> Dict[str, Any]:
        """Handle action-based requests from the Unix socket."""
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning(f"JSON parse error: {e}")
            return {"ok": False, "error": "invalid_json"}

        if not isinstance(payload, dict):
            return {"ok": False, "error": "invalid_payload"}

        # Handle action-based messages
        action = payload.get("action")
        if not action:
            logger.warning(f"Message without action: {list(payload.keys())}")
            return {"ok": False, "error": "missing_action"}
        logger.debug(f"Action={action}")
        handler = self.handlers.get(action)
        if handler is None:
            return {"ok": False, "error": "unknown_action"}
        return handler(payload)

    def serve_forever(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(self.socket_path))
            os.chmod(self.socket_path, 0o600)
            server.listen(5)
            logger.info("Listening on socket")

            # Start Tailscale IP monitor
            self._start_tailscale_monitor()

            # Start SSH tunnel server
            self.ssh_tunnel_server.start()
            logger.info(f"SSH tunnel server listening on {_ssh_socket_path()}")

            try:
                while True:
                    try:
                        conn, _ = server.accept()
                        conn.settimeout(2.0)  # Timeout per recv call

                        # Read request data
                        data = b""
                        read_start = time.time()
                        max_read_time = 5.0  # Max 5 seconds to receive initial data
                        try:
                            while time.time() - read_start < max_read_time:
                                chunk = conn.recv(4096)
                                if not chunk:
                                    break
                                data += chunk
                                if b"\n" in data:
                                    break
                        except socket.timeout:
                            pass

                        # Check if we timed out without getting complete data
                        if data and b"\n" not in data:
                            logger.warning(f"Connection timed out waiting for newline, got {len(data)} bytes")
                            conn.close()
                            continue

                        if not data.strip():
                            conn.close()
                            continue

                        # Handle request/response - run in thread to avoid blocking
                        def handle_request(c, d):
                            try:
                                responses = []
                                for line in d.splitlines():
                                    if not line.strip():
                                        continue
                                    responses.append(self._handle_request(line))
                                if not responses:
                                    responses = [{"ok": False, "error": "empty_request"}]
                                try:
                                    c.settimeout(5.0)  # Timeout for send
                                    c.sendall((json.dumps(responses[-1]) + "\n").encode("utf-8"))
                                except (BrokenPipeError, ConnectionResetError, OSError, socket.timeout) as e:
                                    logger.warning(f"Send failed: {e}")
                            except Exception as e:
                                logger.error(f"Request handler error: {e}")
                            finally:
                                try:
                                    c.close()
                                except Exception:
                                    pass

                        t = threading.Thread(
                            target=handle_request,
                            args=(conn, data),
                            daemon=True
                        )
                        t.start()

                    except Exception as e:
                        logger.error(f"Connection error: {e}")
                        traceback.print_exc()
            except KeyboardInterrupt:
                logger.info("Shutting down...")
            finally:
                self._stop_tailscale_monitor()
                self.ssh_tunnel_server.stop()


# Global proxy instance for web server access
_instance: Optional[Agentboxd] = None


def get_cached_buffer(container: str, session: str) -> Optional[str]:
    """Get cached buffer from streaming daemon (for web server use)."""
    if _instance:
        return _instance.get_session_buffer(container, session)
    return None


def get_cached_cursor(container: str, session: str) -> tuple:
    """Get cached cursor position and pane size from streaming daemon.

    Returns: (cursor_x, cursor_y, pane_width, pane_height)
    """
    if _instance:
        return _instance.get_session_cursor(container, session)
    return (0, 0, 0, 0)


def send_input(container: str, session: str, keys: str, literal: bool = True) -> bool:
    """Send input to a container's streaming daemon (for web server use)."""
    if _instance:
        return _instance.send_input_to_daemon(container, session, keys, literal)
    return False


def subscribe_to_stream(container: str, session: str, callback) -> bool:
    """Subscribe to stream updates for a session (for web server use).

    The callback will be called with stream data dict whenever new data arrives.
    Callbacks should be fast and non-blocking (e.g., put to asyncio queue).

    Returns True if subscription was successful.
    """
    if _instance:
        _instance.subscribe_to_stream(container, session, callback)
        return True
    return False


def unsubscribe_from_stream(container: str, session: str, callback) -> bool:
    """Unsubscribe from stream updates (for web server use)."""
    if _instance:
        _instance.unsubscribe_from_stream(container, session, callback)
        return True
    return False


def add_host_port(container: str, host_port: int, container_port: int = 0) -> Tuple[bool, str]:
    """Add a port listener to expose container port on host via SSH tunnel.

    Args:
        container: Target container name
        host_port: Port to listen on (host side, must be >= 1024)
        container_port: Port to connect to in container (defaults to host_port)

    Returns:
        Tuple of (success, message)
    """
    if not _instance:
        return False, "agentboxd not running"
    result = _instance._handle_add_host_port({
        "container": container,
        "host_port": host_port,
        "container_port": container_port or host_port,
    })
    return result.get("ok", False), result.get("message", result.get("error", "unknown error"))


def remove_host_port(host_port: int) -> Tuple[bool, str]:
    """Remove a port listener (unexpose container port from host).

    Args:
        host_port: Port to stop listening on

    Returns:
        Tuple of (success, message)
    """
    if not _instance or not _instance.ssh_tunnel_server:
        return False, "agentboxd not running"

    # Find which container has this port forwarded
    container = None
    with _instance.ssh_tunnel_server.connections_lock:
        for cont_name, conn in _instance.ssh_tunnel_server.connections.items():
            for fwd in conn.remote_forwards:
                if fwd.get("host_port") == host_port:
                    container = cont_name
                    break
            if container:
                break

    if not container:
        return False, f"no forward found for host port {host_port}"

    result = _instance._handle_remove_host_port({
        "container": container,
        "host_port": host_port,
    })
    return result.get("ok", False), result.get("message", result.get("error", "unknown error"))


def get_host_ports() -> list:
    """Get list of active host port listeners from SSH tunnel connections.

    Returns:
        List of dicts with host_port, container_port, container keys
    """
    if not _instance or not _instance.ssh_tunnel_server:
        return []

    result = []
    with _instance.ssh_tunnel_server.connections_lock:
        for container, conn in _instance.ssh_tunnel_server.connections.items():
            for fwd in conn.remote_forwards:
                result.append({
                    "host_port": fwd.get("host_port", 0),
                    "container_port": fwd.get("container_port", fwd.get("host_port", 0)),
                    "container": container,
                    "active": True,
                })
    return result


def is_host_port_active(host_port: int) -> bool:
    """Check if a host port has an active SSH tunnel forward.

    Args:
        host_port: The host port to check

    Returns:
        True if there's an active forward for this port
    """
    if not _instance or not _instance.ssh_tunnel_server:
        return False

    with _instance.ssh_tunnel_server.connections_lock:
        for conn in _instance.ssh_tunnel_server.connections.values():
            for fwd in conn.remote_forwards:
                if fwd.get("host_port") == host_port:
                    return True
    return False


def get_tunnel_stats() -> dict:
    """Get tunnel statistics.

    Returns:
        Dict with ssh_tunnel stats
    """
    if not _instance or not _instance.ssh_tunnel_server:
        return {"ssh_tunnel": {"connected_containers": 0, "total_forwards": 0}}

    connected = 0
    forwards = 0
    with _instance.ssh_tunnel_server.connections_lock:
        connected = len(_instance.ssh_tunnel_server.connections)
        for conn in _instance.ssh_tunnel_server.connections.values():
            forwards += len(conn.remote_forwards) + len(conn.local_forwards)

    return {
        "ssh_tunnel": {
            "connected_containers": connected,
            "total_forwards": forwards,
        }
    }


def get_connected_containers() -> list:
    """Get list of containers connected via SSH tunnel.

    Returns:
        List of container names
    """
    if not _instance or not _instance.ssh_tunnel_server:
        return []

    with _instance.ssh_tunnel_server.connections_lock:
        return list(_instance.ssh_tunnel_server.connections.keys())


def run_agentboxd(socket_path: Optional[str] = None) -> None:
    """Run the agentbox daemon, optionally with web server."""
    global _instance
    import asyncio

    path = Path(socket_path) if socket_path else _default_socket_path()
    daemon = Agentboxd(path)
    _instance = daemon  # Make accessible to web server
    host_config = get_config()

    web_config = host_config._config.get("web_server", {})

    # Create restart event for Tailscale monitor to signal web server restart
    web_restart_event = threading.Event()
    daemon._web_server_restart_event = web_restart_event

    # Track running web server state
    web_server_state = {
        "servers": [],  # List of uvicorn.Server instances
        "thread": None,
        "loop": None,
        "shutdown_event": None,
    }

    def start_web_server():
        """Start web server with current host bindings."""
        if not web_config.get("enabled", True):
            return False

        try:
            import uvicorn
            from agentbox.web.host_server import app

            # Reload config to get fresh hosts
            host_config._config = host_config._load()
            hosts = host_config.get_web_server_hosts()
            port = web_config.get("port", 8080)
            log_level = web_config.get("log_level", "info")

            # Create shutdown event for this server instance
            shutdown_event = threading.Event()
            web_server_state["shutdown_event"] = shutdown_event

            def run_web_server():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                web_server_state["loop"] = loop

                async def serve_all():
                    servers = []
                    for host in hosts:
                        logger.info(f"Starting web server on {host}:{port}")
                        uvi_config = uvicorn.Config(app, host=host, port=port, log_level=log_level)
                        server = uvicorn.Server(uvi_config)
                        servers.append(server)
                        web_server_state["servers"].append(server)

                    # Run all servers
                    await asyncio.gather(*[s.serve() for s in servers])

                try:
                    loop.run_until_complete(serve_all())
                except Exception as e:
                    if not shutdown_event.is_set():
                        logger.error(f"Web server error: {e}")
                finally:
                    loop.close()

            thread = threading.Thread(target=run_web_server, daemon=True, name="web-server")
            thread.start()
            web_server_state["thread"] = thread
            return True

        except ImportError as e:
            logger.warning(f"Cannot start web server (missing dependencies): {e}")
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")
        return False

    def stop_web_server():
        """Stop running web server gracefully."""
        if web_server_state["shutdown_event"]:
            web_server_state["shutdown_event"].set()

        # Signal all servers to exit
        for server in web_server_state["servers"]:
            server.should_exit = True

        # Wait briefly for thread to finish
        if web_server_state["thread"]:
            web_server_state["thread"].join(timeout=3.0)

        # Reset state
        web_server_state["servers"] = []
        web_server_state["thread"] = None
        web_server_state["loop"] = None
        web_server_state["shutdown_event"] = None

    def restart_monitor():
        """Monitor thread that handles web server restart requests."""
        while True:
            web_restart_event.wait()
            web_restart_event.clear()

            logger.info("Restarting web server due to binding changes...")

            # Stop old server
            stop_web_server()

            # Brief delay to allow port release
            time.sleep(1)

            # Start new server with fresh bindings
            start_web_server()

    # Start initial web server
    if web_config.get("enabled", True):
        start_web_server()

        # Start restart monitor thread
        restart_thread = threading.Thread(target=restart_monitor, daemon=True, name="web-restart-monitor")
        restart_thread.start()

    try:
        daemon.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)