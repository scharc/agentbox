# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Tmux session management for web UI.

This module re-exports session functions from agentbox.core.sessions for backward compatibility.
New code should import directly from agentbox.core.sessions.
"""

# Re-export from core for backward compatibility
from agentbox.core.sessions import (
    get_sessions_for_container,
    get_all_sessions,
    capture_session_output,
    send_keys_to_session,
    resize_session,
    create_agent_session as create_session,  # Keep old name for backward compat
)
