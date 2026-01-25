# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Daemon client helper for CLI tools.

Provides functions to query the agentboxd daemon for cached data,
with fallback support for when the daemon is unavailable.
"""

import json
import urllib.request
import urllib.error
from typing import Optional

from agentbox.host_config import HostConfig


def get_daemon_port() -> int:
    """Get the web server port from host config."""
    try:
        host_config = HostConfig()
        web_config = host_config._config.get("web_server", {})
        return web_config.get("port", 8080)
    except Exception:
        return 8080


def query_daemon(endpoint: str, timeout: float = 1.0) -> Optional[dict]:
    """Query daemon API with timeout and error handling.

    Args:
        endpoint: API endpoint path (e.g., "/api/sessions/metadata")
        timeout: Request timeout in seconds (default: 1.0s for fast fail)

    Returns:
        JSON response as dict, or None if daemon unavailable/error
    """
    port = get_daemon_port()
    url = f"http://localhost:{port}{endpoint}"

    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode())
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, Exception):
        return None


def get_sessions_from_daemon(timeout: float = 1.0) -> Optional[list]:
    """Get all sessions from daemon cache.

    Args:
        timeout: Request timeout in seconds

    Returns:
        List of session dicts, or None if daemon unavailable.
        Each session has: container_name, project, project_path, session_name,
        windows, attached, agent_type, identifier
    """
    result = query_daemon("/api/sessions/metadata", timeout=timeout)
    if result is None:
        return None

    # Check for stale data
    if result.get("stale"):
        return None

    return result.get("sessions", [])


def get_session_counts_from_daemon(timeout: float = 1.0) -> Optional[dict]:
    """Get session counts per container from daemon cache.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Dict mapping container_name to session count, or None if unavailable
    """
    sessions = get_sessions_from_daemon(timeout=timeout)
    if sessions is None:
        return None

    counts = {}
    for sess in sessions:
        container_name = sess.get("container_name", "")
        if container_name:
            counts[container_name] = counts.get(container_name, 0) + 1

    return counts


def get_usage_status_from_daemon(timeout: float = 1.0) -> Optional[dict]:
    """Get agent rate limit status from daemon cache.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Dict with agent statuses, or None if daemon unavailable.
        Each agent has: available, limited, resets_at, resets_in_seconds, error_type
    """
    result = query_daemon("/api/usage", timeout=timeout)
    if result is None:
        return None

    return result.get("agents", {})
