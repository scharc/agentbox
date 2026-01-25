# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""State storage for agent rate limit status.

Stores limit state in a JSON file at ~/.local/share/agentbox/usage/state.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# State file location
STATE_DIR = Path.home() / ".local" / "share" / "agentbox" / "usage"
STATE_FILE = STATE_DIR / "state.json"


def _ensure_state_dir() -> None:
    """Ensure the state directory exists."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    """Load the current state from disk.

    Returns:
        Dict mapping agent names to their limit state.
    """
    if not STATE_FILE.exists():
        return {}

    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    """Save state to disk.

    Args:
        state: Dict mapping agent names to their limit state.
    """
    _ensure_state_dir()
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_agent_state(agent: str) -> dict:
    """Get the state for a specific agent.

    Args:
        agent: Agent name (e.g., "superclaude", "supercodex")

    Returns:
        Dict with agent state (limited, resets_at, detected_at) or empty dict.
    """
    state = load_state()
    return state.get(agent, {})


def update_agent_state(
    agent: str,
    limited: bool,
    resets_at: Optional[datetime] = None,
    error_type: Optional[str] = None,
) -> None:
    """Update the state for a specific agent.

    Args:
        agent: Agent name (e.g., "superclaude", "supercodex")
        limited: Whether the agent is currently rate-limited
        resets_at: When the limit resets (if known)
        error_type: Type of error encountered (if any)
    """
    state = load_state()

    agent_state = {
        "limited": limited,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    if resets_at:
        agent_state["resets_at"] = resets_at.isoformat()

    if error_type:
        agent_state["error_type"] = error_type

    state[agent] = agent_state
    save_state(state)


def clear_agent_state(agent: str) -> bool:
    """Clear the limit state for a specific agent.

    Args:
        agent: Agent name to clear

    Returns:
        True if state was cleared, False if agent wasn't in state.
    """
    state = load_state()

    if agent not in state:
        return False

    del state[agent]
    save_state(state)
    return True


def clear_all_state() -> None:
    """Clear all agent state."""
    save_state({})
