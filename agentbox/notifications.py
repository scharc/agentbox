# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Notification client for sending alerts via agentboxd.

Supports two modes:
1. SSH control channel (preferred) - uses the container client's SSH connection
2. Legacy Unix socket (fallback) - direct connection to agentboxd socket

The SSH mode is preferred as it uses the unified SSH connection for all communication.
"""

import json
import os
import socket
import struct
import time
from pathlib import Path
from typing import Optional

from agentbox.host_config import get_config


def _get_ssh_socket_path() -> Optional[Path]:
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


def _get_legacy_socket_path() -> Optional[Path]:
    """Find the legacy agentboxd socket path."""
    config = get_config()
    socket_path = Path(str(config.socket_path))
    if socket_path.exists():
        return socket_path
    return None


def _send_via_ssh(
    title: str,
    message: str,
    urgency: str,
    metadata: Optional[dict],
    timeout: float,
) -> bool:
    """Send notification via SSH control channel."""
    try:
        import asyncssh
    except ImportError:
        return False

    ssh_socket = _get_ssh_socket_path()
    if not ssh_socket:
        return False

    container_name = os.environ.get("AGENTBOX_CONTAINER") or socket.gethostname()

    try:
        import asyncio

        async def send_notify():
            try:
                conn = await asyncssh.connect(
                    path=str(ssh_socket),
                    username=container_name,
                    known_hosts=None,
                )

                process = await conn.create_process(
                    term_type=None,
                    encoding=None,
                )

                # Build request message
                request = {
                    "kind": "request",
                    "type": "notify",
                    "id": f"notify-{time.time()}",
                    "ts": time.time(),
                    "payload": {
                        "title": title,
                        "message": message,
                        "urgency": urgency,
                    }
                }

                if metadata:
                    request["payload"]["metadata"] = metadata

                # Send with length prefix
                data = json.dumps(request).encode("utf-8")
                header = struct.pack(">I", len(data))
                process.stdin.write(header + data)
                await process.stdin.drain()

                # Read response with length prefix
                response_header = await asyncio.wait_for(
                    process.stdout.readexactly(4),
                    timeout=timeout
                )
                response_length = struct.unpack(">I", response_header)[0]
                response_data = await asyncio.wait_for(
                    process.stdout.readexactly(response_length),
                    timeout=timeout
                )
                response = json.loads(response_data.decode("utf-8"))

                conn.close()
                await conn.wait_closed()

                return response.get("payload", {}).get("ok", False)

            except Exception:
                return False

        # Handle both sync and async contexts
        try:
            loop = asyncio.get_running_loop()
            # Already in async context - run in a daemon thread to avoid blocking
            # Using daemon thread with join(timeout) instead of ThreadPoolExecutor
            # because TPE.shutdown(wait=True) blocks even after timeout
            import threading
            result_container = [False]

            def run_in_thread():
                try:
                    result_container[0] = asyncio.run(send_notify())
                except Exception:
                    result_container[0] = False

            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()
            thread.join(timeout=timeout + 5)

            # If thread is still alive, timeout occurred - return False
            # The daemon thread will be cleaned up when the process exits
            if thread.is_alive():
                return False
            return result_container[0]
        except RuntimeError:
            # No running loop - use asyncio.run
            return asyncio.run(send_notify())

    except Exception:
        return False


def _send_via_legacy_socket(
    title: str,
    message: str,
    urgency: str,
    metadata: Optional[dict],
    timeout: float,
) -> bool:
    """Send notification via legacy Unix socket."""
    socket_path = _get_legacy_socket_path()
    if not socket_path:
        return False

    payload_dict = {
        "action": "notify",
        "title": title,
        "message": message,
        "urgency": urgency,
    }

    if metadata:
        payload_dict["enhance"] = True
        payload_dict["metadata"] = metadata

    payload = json.dumps(payload_dict).encode("utf-8")

    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect(str(socket_path))
            sock.sendall(payload + b"\n")
            sock.shutdown(socket.SHUT_WR)
            response = sock.recv(4096).decode("utf-8")

        response_data = json.loads(response.strip().splitlines()[-1])
        return response_data.get("ok") is True

    except Exception:
        return False


def send_notification(
    title: str,
    message: str,
    urgency: str = "normal",
    socket_path: Optional[str] = None,
    container: Optional[str] = None,
    session: Optional[str] = None,
    buffer: Optional[str] = None,
    enhance: bool = False
) -> bool:
    """Send a notification via the agentboxd daemon.

    Args:
        title: Notification title
        message: Notification message
        urgency: Urgency level (normal, low, critical)
        socket_path: Path to Unix socket (for legacy mode, ignored in SSH mode)
        container: Container name (for task agent enhancement)
        session: Session name (for task agent enhancement)
        buffer: Session buffer content (for task agent enhancement)
        enhance: Enable task agent analysis

    Returns:
        True if notification sent successfully, False otherwise
    """
    # Build metadata if enhancement requested
    metadata = None
    if enhance:
        metadata = {
            "container": container,
            "session": session,
            "buffer": buffer,
        }

    # Determine timeout
    config = get_config()
    timeout = config.get("notifications", "timeout_enhanced" if enhance else "timeout")

    # Try SSH first (preferred)
    if _send_via_ssh(title, message, urgency, metadata, timeout):
        return True

    # Fall back to legacy socket
    return _send_via_legacy_socket(title, message, urgency, metadata, timeout)
