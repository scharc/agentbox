#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Unified container client for SSH-based communication with agentboxd.

This module provides a single client that handles all container-to-host communication:
- Terminal streaming (tmux buffer monitoring)
- Notifications and clipboard
- Port forwarding
- State updates (worktrees, etc.)

All communication goes through the SSH control channel using length-prefixed JSON.
"""

from __future__ import annotations

import asyncio
import json
import os
import socket
import subprocess
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agentbox.ssh_tunnel import (
    SSHTunnelClient,
    PortForwardConfig,
    check_asyncssh_available,
)
from agentbox.utils.logging import get_daemon_logger, configure_logging

# Configure logging for daemon mode
configure_logging(daemon=True)
logger = get_daemon_logger("container-client")

# Local IPC socket for inter-process communication within the container
# This allows scripts like abox-notify to send messages through the SSH tunnel
# Use /tmp which is writable by all users
LOCAL_IPC_SOCKET_PATH = Path("/tmp/agentbox-local.sock")


class SessionState(Enum):
    """State of a session for stall detection."""
    IDLE = "idle"
    ACTIVE = "active"
    STALE = "stale"
    NOTIFIED = "notified"


@dataclass
class SessionStallState:
    """Track stall detection state for a session."""
    state: SessionState = SessionState.IDLE
    last_activity_time: Optional[float] = None
    last_buffer_content: str = ""
    notification_sent_time: Optional[float] = None


@dataclass
class TmuxSession:
    """Represents a monitored tmux session."""
    name: str
    last_buffer: str = ""
    cursor_x: int = 0
    cursor_y: int = 0
    stall_state: SessionStallState = None

    def __post_init__(self):
        if self.stall_state is None:
            self.stall_state = SessionStallState()


class ContainerClient:
    """Unified container client for all agentboxd communication.

    Handles:
    - SSH connection with control channel
    - Terminal streaming (tmux monitoring)
    - Notifications
    - Port forwarding (local and remote)
    - State updates (worktrees)
    """

    def __init__(
        self,
        container_name: Optional[str] = None,
        local_forwards: Optional[List[PortForwardConfig]] = None,
        remote_forwards: Optional[List[PortForwardConfig]] = None,
    ):
        self.container_name = container_name or os.environ.get("AGENTBOX_CONTAINER") or socket.gethostname()
        self.local_forwards = local_forwards or []
        self.remote_forwards = remote_forwards or []

        # SSH client
        self._ssh_client: Optional[SSHTunnelClient] = None
        self._ssh_socket_path: Optional[Path] = None

        # Streaming state
        self._sessions: Dict[str, TmuxSession] = {}
        self._sessions_lock = asyncio.Lock()
        self._tmux_env = {**os.environ, "TMUX_TMPDIR": "/tmp"}

        # State tracking
        self._last_worktrees: List[str] = []
        self._running = False

        # Stall detection config
        self._stall_enabled = True
        self._stall_threshold = 30.0
        self._stall_check_interval = 5.0
        self._last_stall_check = 0.0

        # Timing
        self._last_session_sync = 0.0
        self._last_worktree_push = 0.0
        self._last_change_check = 0.0

        # Event loop reference
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Local IPC socket for abox-notify and other scripts
        self._local_ipc_socket: Optional[socket.socket] = None
        self._local_ipc_thread: Optional[threading.Thread] = None
        self._local_ipc_running = False

    def _get_ssh_socket_path(self) -> Optional[Path]:
        """Find the SSH tunnel socket path."""
        env_socket = os.environ.get("AGENTBOX_SSH_SOCKET")
        if env_socket:
            path = Path(env_socket)
            if path.exists():
                return path

        uid = os.getuid()
        path = Path(f"/run/user/{uid}/agentboxd/ssh.sock")
        if path.exists():
            return path

        # Container mount location
        container_path = Path("/run/agentboxd/ssh.sock")
        if container_path.exists():
            return container_path

        return None

    def _load_stall_config(self) -> None:
        """Load stall detection config from .agentbox.yml."""
        config_path = Path('/workspace/.agentbox.yml')
        if not config_path.exists():
            return

        try:
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f) or {}
            stall_config = config.get('stall_detection', {})
            self._stall_enabled = stall_config.get('enabled', True)
            self._stall_threshold = stall_config.get('threshold_seconds', 30.0)
            self._stall_check_interval = stall_config.get('check_interval_seconds', 5.0)
        except Exception as e:
            logger.warning(f"Failed to load stall config: {e}")

    # ========== tmux Operations ==========

    async def _get_tmux_sessions(self) -> List[str]:
        """Get list of tmux session names."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/tmux", "list-sessions", "-F", "#{session_name}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=self._tmux_env
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            if proc.returncode == 0:
                return [s.strip() for s in stdout.decode().strip().split("\n") if s.strip()]
            return []
        except (asyncio.TimeoutError, OSError):
            return []

    async def _capture_buffer(self, session_name: str) -> Optional[str]:
        """Capture tmux pane buffer with ANSI codes."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/tmux", "capture-pane", "-e", "-p", "-t", session_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=self._tmux_env
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=2.0)
            if proc.returncode == 0:
                return stdout.decode('utf-8', errors='replace')
            return None
        except (asyncio.TimeoutError, OSError):
            return None

    async def _get_cursor_and_size(self, session_name: str) -> tuple:
        """Get cursor position and pane size."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/tmux", "display-message", "-p", "-t", session_name,
                "#{cursor_x} #{cursor_y} #{pane_width} #{pane_height}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=self._tmux_env
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=1.0)
            if proc.returncode == 0:
                parts = stdout.decode().strip().split()
                if len(parts) == 4:
                    return (int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3]))
        except (asyncio.TimeoutError, OSError, ValueError):
            pass
        return (0, 0, 80, 24)

    async def _send_keys(self, session_name: str, keys: str, literal: bool = True) -> bool:
        """Send keystrokes to tmux session."""
        try:
            cmd = ["/usr/bin/tmux", "send-keys", "-t", session_name]
            if literal:
                cmd.extend(["-l", keys])
            else:
                cmd.append(keys)
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
                env=self._tmux_env
            )
            await asyncio.wait_for(proc.wait(), timeout=1.0)
            return proc.returncode == 0
        except (asyncio.TimeoutError, OSError):
            return False

    # ========== Streaming Operations ==========

    async def _register_session(self, session_name: str) -> None:
        """Register a new session."""
        async with self._sessions_lock:
            if session_name in self._sessions:
                return
            self._sessions[session_name] = TmuxSession(name=session_name)

        # Send registration event
        await self._ssh_client.send_event_async("stream_register", {"session": session_name})

        # Send initial buffer
        buffer = await self._capture_buffer(session_name)
        if buffer:
            cursor_x, cursor_y, width, height = await self._get_cursor_and_size(session_name)
            async with self._sessions_lock:
                session = self._sessions.get(session_name)
                if session:
                    session.last_buffer = buffer
                    session.cursor_x = cursor_x
                    session.cursor_y = cursor_y

            await self._ssh_client.send_event_async("stream_data", {
                "session": session_name,
                "data": buffer,
                "cursor_x": cursor_x,
                "cursor_y": cursor_y,
                "pane_width": width,
                "pane_height": height,
            })

    async def _unregister_session(self, session_name: str) -> None:
        """Unregister a session."""
        async with self._sessions_lock:
            if session_name in self._sessions:
                del self._sessions[session_name]

        await self._ssh_client.send_event_async("stream_unregister", {"session": session_name})

    async def _sync_sessions(self) -> None:
        """Sync sessions with tmux."""
        current_sessions = set(await self._get_tmux_sessions())

        async with self._sessions_lock:
            known_sessions = set(self._sessions.keys())

        for session in current_sessions - known_sessions:
            await self._register_session(session)

        for session in known_sessions - current_sessions:
            await self._unregister_session(session)

    async def _check_session_changes(self) -> None:
        """Check all sessions for buffer changes."""
        async with self._sessions_lock:
            sessions_snapshot = list(self._sessions.items())

        for session_name, session in sessions_snapshot:
            buffer = await self._capture_buffer(session_name)
            if buffer is None:
                continue

            cursor_x, cursor_y, width, height = await self._get_cursor_and_size(session_name)

            if buffer != session.last_buffer or cursor_x != session.cursor_x or cursor_y != session.cursor_y:
                session.last_buffer = buffer
                session.cursor_x = cursor_x
                session.cursor_y = cursor_y

                # Update stall state
                if buffer != session.stall_state.last_buffer_content:
                    now = asyncio.get_event_loop().time()
                    session.stall_state.last_buffer_content = buffer
                    session.stall_state.last_activity_time = now

                    if session.stall_state.state in (SessionState.STALE, SessionState.NOTIFIED):
                        session.stall_state.state = SessionState.ACTIVE
                        session.stall_state.notification_sent_time = None
                    elif session.stall_state.state == SessionState.IDLE:
                        session.stall_state.state = SessionState.ACTIVE

                await self._ssh_client.send_event_async("stream_data", {
                    "session": session_name,
                    "data": buffer,
                    "cursor_x": cursor_x,
                    "cursor_y": cursor_y,
                    "pane_width": width,
                    "pane_height": height,
                })

    # ========== Stall Detection ==========

    async def _check_stall_detection(self) -> None:
        """Check all sessions for stalls."""
        if not self._stall_enabled:
            return

        now = asyncio.get_event_loop().time()

        async with self._sessions_lock:
            sessions_snapshot = list(self._sessions.items())

        for session_name, session in sessions_snapshot:
            state = session.stall_state

            if state.state in (SessionState.IDLE, SessionState.NOTIFIED):
                continue

            if state.last_activity_time:
                idle_time = now - state.last_activity_time
                if idle_time >= self._stall_threshold:
                    if state.state == SessionState.ACTIVE:
                        state.state = SessionState.STALE

                    if state.state == SessionState.STALE:
                        await self._send_stall_notification(session_name, idle_time, session.last_buffer)
                        state.state = SessionState.NOTIFIED
                        state.notification_sent_time = now

    async def _send_stall_notification(self, session_name: str, idle_seconds: float, buffer: str) -> None:
        """Send stall notification via control channel."""
        result = await self._ssh_client.request_async("notify", {
            "title": "Session stalled",
            "message": f"No output for {int(idle_seconds)}s",
            "urgency": "normal",
            "metadata": {
                "container": self.container_name,
                "session": session_name,
                "buffer": buffer,
            }
        }, timeout=30.0)

        if not result or not result.get("ok"):
            logger.warning(f"Failed to send stall notification for {session_name}")

    # ========== State Updates ==========

    def _get_worktrees(self) -> List[str]:
        """Get list of git worktree branch names."""
        try:
            result = subprocess.run(
                ["git", "worktree", "list", "--porcelain"],
                capture_output=True,
                text=True,
                cwd="/workspace",
                timeout=5
            )
            if result.returncode != 0:
                return []

            branches = []
            for line in result.stdout.splitlines():
                if line.startswith("branch refs/heads/"):
                    branch = line.replace("branch refs/heads/", "")
                    branches.append(branch)
            return sorted(branches)
        except Exception:
            return []

    async def _push_worktree_state(self, force: bool = False) -> None:
        """Push worktree state if changed."""
        worktrees = self._get_worktrees()

        if not force and worktrees == self._last_worktrees:
            return

        self._last_worktrees = worktrees
        await self._ssh_client.send_event_async("state_update", {"worktrees": worktrees})
        logger.debug(f"Pushed worktree state: {worktrees}")

    # ========== Event Handlers (from server) ==========

    async def _handle_stream_input_event(self, payload: dict) -> None:
        """Handle stream_input event from host (no response needed)."""
        session = payload.get("session")
        keys = payload.get("keys", "")
        literal = payload.get("literal", True)

        if session:
            await self._send_keys(session, keys, literal)

    async def _handle_stream_input_request(self, payload: dict) -> dict:
        """Handle stream_input request from host (response expected)."""
        session = payload.get("session")
        keys = payload.get("keys", "")
        literal = payload.get("literal", True)

        if session:
            success = await self._send_keys(session, keys, literal)
            return {"ok": success}
        return {"ok": False, "error": "No session specified"}

    async def _handle_port_add(self, payload: dict) -> dict:
        """Handle dynamic port add request."""
        direction = payload.get("direction")
        host_port = payload.get("host_port")
        container_port = payload.get("container_port", host_port)
        name = payload.get("name", f"dynamic-{host_port}")

        config = PortForwardConfig(
            name=name,
            host_port=host_port,
            container_port=container_port,
            direction=direction,
        )

        # Use async methods to avoid deadlock (we're on the SSH event loop)
        if direction == "local":
            success = await self._ssh_client.add_local_forward_async(config)
        else:
            success = await self._ssh_client.add_remote_forward_async(config)

        return {"ok": success}

    async def _handle_port_remove(self, payload: dict) -> dict:
        """Handle dynamic port remove request."""
        direction = payload.get("direction")
        host_port = payload.get("host_port")

        if direction == "local":
            success = await self._ssh_client.remove_local_forward_async(host_port)
        else:
            success = await self._ssh_client.remove_remote_forward_async(host_port)

        return {"ok": success}

    # ========== Main Loop ==========

    async def _main_loop(self) -> None:
        """Main async loop."""
        self._load_stall_config()

        # Initial sync
        await self._sync_sessions()
        await self._push_worktree_state(force=True)

        while self._running and self._ssh_client and self._ssh_client.is_connected:
            now = asyncio.get_event_loop().time()

            # Sync sessions every 5 seconds
            if now - self._last_session_sync > 5:
                await self._sync_sessions()
                self._last_session_sync = now

            # Check for worktree changes every 10 seconds
            if now - self._last_worktree_push > 10:
                await self._push_worktree_state()
                self._last_worktree_push = now

            # Check for stalls
            if now - self._last_stall_check >= self._stall_check_interval:
                await self._check_stall_detection()
                self._last_stall_check = now

            # Check for buffer changes (10/sec)
            if now - self._last_change_check >= 0.1:
                await self._check_session_changes()
                self._last_change_check = now

            await asyncio.sleep(0.05)

    def _on_connect(self) -> None:
        """Called when SSH connects."""
        logger.info(f"Connected to agentboxd as {self.container_name}")

        # Get the event loop from SSH client (it creates its own)
        if self._ssh_client and self._ssh_client._loop:
            self._loop = self._ssh_client._loop
            asyncio.run_coroutine_threadsafe(self._main_loop(), self._loop)

    def _on_disconnect(self) -> None:
        """Called when SSH disconnects."""
        logger.info("Disconnected from agentboxd")

    def start(self) -> None:
        """Start the container client."""
        if not check_asyncssh_available():
            logger.error("asyncssh not available")
            return

        self._ssh_socket_path = self._get_ssh_socket_path()
        if not self._ssh_socket_path:
            logger.error("SSH socket not found")
            return

        self._running = True

        # Start local IPC socket for abox-notify and other scripts
        self._start_local_ipc()

        # Create SSH client
        self._ssh_client = SSHTunnelClient(
            socket_path=self._ssh_socket_path,
            container_name=self.container_name,
            local_forwards=self.local_forwards,
            remote_forwards=self.remote_forwards,
        )

        # Register handlers
        # Event handlers (no response expected)
        self._ssh_client.register_event_handler("stream_input", self._handle_stream_input_event)

        # Request handlers (response expected)
        self._ssh_client.register_request_handler("stream_input", self._handle_stream_input_request)
        self._ssh_client.register_request_handler("port_add", self._handle_port_add)
        self._ssh_client.register_request_handler("port_remove", self._handle_port_remove)

        # Set callbacks
        self._ssh_client.on_connect = self._on_connect
        self._ssh_client.on_disconnect = self._on_disconnect

        # Start SSH client (loop is created in start())
        self._ssh_client.start()

        logger.info(f"Container client started for {self.container_name}")

    def stop(self) -> None:
        """Stop the container client."""
        self._running = False

        # Stop local IPC socket
        self._stop_local_ipc()

        if self._ssh_client:
            self._ssh_client.stop()
            self._ssh_client = None

        logger.info("Container client stopped")

    def run(self) -> None:
        """Run the client (blocking)."""
        self.start()

        try:
            # Keep running until stopped
            while self._running:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    # ========== Sync API for external callers ==========

    def send_notification(
        self,
        title: str,
        message: str,
        urgency: str = "normal",
        metadata: Optional[dict] = None,
    ) -> bool:
        """Send a notification to the host."""
        if not self._ssh_client or not self._ssh_client.is_connected:
            return False

        payload = {
            "title": title,
            "message": message,
            "urgency": urgency,
        }
        if metadata:
            payload["metadata"] = metadata

        result = self._ssh_client.request("notify", payload, timeout=30.0)
        return result is not None and result.get("ok", False)

    def set_clipboard(self, data: str, selection: str = "clipboard") -> bool:
        """Set the host clipboard."""
        if not self._ssh_client or not self._ssh_client.is_connected:
            return False

        result = self._ssh_client.request("clipboard_set", {
            "data": data,
            "selection": selection,
        }, timeout=5.0)
        return result is not None and result.get("ok", False)

    # ========== Local IPC for abox-notify ==========

    def _start_local_ipc(self) -> None:
        """Start the local IPC socket listener for scripts like abox-notify."""
        try:
            # Create directory if needed
            LOCAL_IPC_SOCKET_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Remove old socket if exists
            if LOCAL_IPC_SOCKET_PATH.exists():
                LOCAL_IPC_SOCKET_PATH.unlink()

            # Create listener socket
            self._local_ipc_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self._local_ipc_socket.bind(str(LOCAL_IPC_SOCKET_PATH))
            self._local_ipc_socket.listen(5)
            self._local_ipc_socket.settimeout(1.0)

            # Set permissions (readable/writable by owner and group)
            os.chmod(LOCAL_IPC_SOCKET_PATH, 0o660)

            self._local_ipc_running = True
            self._local_ipc_thread = threading.Thread(
                target=self._local_ipc_loop,
                daemon=True,
                name="local-ipc",
            )
            self._local_ipc_thread.start()

            logger.info(f"Local IPC listening on {LOCAL_IPC_SOCKET_PATH}")
        except OSError as e:
            logger.warning(f"Failed to start local IPC socket: {e}")

    def _stop_local_ipc(self) -> None:
        """Stop the local IPC socket listener."""
        self._local_ipc_running = False

        if self._local_ipc_socket:
            try:
                self._local_ipc_socket.close()
            except Exception:
                pass
            self._local_ipc_socket = None

        if self._local_ipc_thread:
            self._local_ipc_thread.join(timeout=2.0)
            self._local_ipc_thread = None

        # Clean up socket file
        if LOCAL_IPC_SOCKET_PATH.exists():
            try:
                LOCAL_IPC_SOCKET_PATH.unlink()
            except Exception:
                pass

    def _local_ipc_loop(self) -> None:
        """Accept and handle local IPC connections."""
        while self._local_ipc_running and self._local_ipc_socket:
            try:
                conn, _ = self._local_ipc_socket.accept()
                conn.settimeout(5.0)

                # Handle in thread to not block accept loop
                threading.Thread(
                    target=self._handle_local_ipc_connection,
                    args=(conn,),
                    daemon=True,
                ).start()
            except socket.timeout:
                continue
            except OSError:
                if self._local_ipc_running:
                    logger.debug("Local IPC socket error")
                break

    def _handle_local_ipc_connection(self, conn: socket.socket) -> None:
        """Handle a single local IPC connection."""
        try:
            # Read request (single line JSON)
            data = b""
            while b"\n" not in data and len(data) < 65536:
                chunk = conn.recv(4096)
                if not chunk:
                    break
                data += chunk

            if not data.strip():
                conn.close()
                return

            # Parse JSON request
            try:
                request = json.loads(data.decode("utf-8").strip())
            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                response = {"ok": False, "error": f"Invalid JSON: {e}"}
                conn.sendall((json.dumps(response) + "\n").encode())
                conn.close()
                return

            # Handle request
            response = self._handle_local_ipc_request(request)

            # Send response
            conn.sendall((json.dumps(response) + "\n").encode())
            conn.close()

        except (BrokenPipeError, ConnectionResetError, OSError) as e:
            logger.debug(f"Local IPC connection error: {e}")
        except Exception as e:
            logger.error(f"Local IPC handler error: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _handle_local_ipc_request(self, request: dict) -> dict:
        """Handle a local IPC request."""
        action = request.get("action")

        if action == "notify":
            title = request.get("title", "Agentbox")
            message = request.get("message", "Notification")
            urgency = request.get("urgency", "normal")
            metadata = request.get("metadata")

            success = self.send_notification(title, message, urgency, metadata)
            return {"ok": success}

        elif action == "clipboard":
            data = request.get("data", "")
            selection = request.get("selection", "clipboard")

            success = self.set_clipboard(data, selection)
            return {"ok": success}

        elif action == "status":
            # Return connection status
            return {
                "ok": True,
                "connected": self._ssh_client is not None and self._ssh_client.is_connected,
                "container": self.container_name,
            }

        else:
            return {"ok": False, "error": f"Unknown action: {action}"}


def load_config_from_yaml() -> tuple:
    """Load port forward config from .agentbox.yml."""
    config_path = Path('/workspace/.agentbox.yml')
    local_forwards = []
    remote_forwards = []

    if not config_path.exists():
        return local_forwards, remote_forwards

    try:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f) or {}

        ports_config = config.get('ports', {})

        # Host ports (remote forwards: host→container)
        for port_spec in ports_config.get('host', []):
            if isinstance(port_spec, str):
                if ':' in port_spec:
                    host_port, container_port = port_spec.split(':')
                    host_port = int(host_port)
                    container_port = int(container_port)
                else:
                    host_port = container_port = int(port_spec)
            else:
                host_port = container_port = int(port_spec)

            remote_forwards.append(PortForwardConfig(
                name=f"host-{host_port}",
                host_port=host_port,
                container_port=container_port,
                direction="remote",
            ))

        # Container ports (local forwards: container→host)
        for port_config in ports_config.get('container', []):
            if isinstance(port_config, dict):
                name = port_config.get('name', f"port-{port_config.get('port')}")
                host_port = port_config.get('port')
                container_port = port_config.get('container_port', host_port)
            else:
                host_port = container_port = int(port_config)
                name = f"port-{host_port}"

            local_forwards.append(PortForwardConfig(
                name=name,
                host_port=host_port,
                container_port=container_port,
                direction="local",
            ))

    except Exception as e:
        logger.warning(f"Failed to load config: {e}")

    return local_forwards, remote_forwards


def main():
    """Main entry point."""
    local_forwards, remote_forwards = load_config_from_yaml()

    client = ContainerClient(
        local_forwards=local_forwards,
        remote_forwards=remote_forwards,
    )

    try:
        client.run()
    except KeyboardInterrupt:
        logger.info("Container client shutting down")


if __name__ == "__main__":
    main()
