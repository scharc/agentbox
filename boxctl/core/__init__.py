# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Core business logic for boxctl.

This package contains the canonical implementations of core functionality.
CLI commands and other tools should import from here.

Modules:
    tmux: Low-level tmux operations (host-side, via docker exec)
    sessions: High-level session management
"""

from boxctl.core.tmux import (
    capture_pane,
    create_session,
    get_tmux_socket_path,
    list_tmux_sessions,
    resize_window,
    sanitize_tmux_name,
    send_keys,
    session_exists,
)
from boxctl.core.sessions import (
    AGENT_COMMANDS,
    AGENT_TYPES,
    capture_session_output,
    create_agent_session,
    generate_session_name,
    get_agent_sessions,
    get_all_sessions,
    get_sessions_for_container,
    resize_session,
    send_keys_to_session,
)

__all__ = [
    # tmux (low-level)
    "sanitize_tmux_name",
    "get_tmux_socket_path",
    "list_tmux_sessions",
    "session_exists",
    "capture_pane",
    "send_keys",
    "resize_window",
    "create_session",
    # sessions (high-level)
    "AGENT_TYPES",
    "AGENT_COMMANDS",
    "get_sessions_for_container",
    "get_all_sessions",
    "capture_session_output",
    "send_keys_to_session",
    "resize_session",
    "get_agent_sessions",
    "generate_session_name",
    "create_agent_session",
]
