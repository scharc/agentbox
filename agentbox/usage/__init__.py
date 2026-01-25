# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Agent usage tracking and fallback system.

This package provides:
- Unified client API that works with service or falls back to local storage
- Rate limit detection and reporting
- Fallback logic to use available agents when preferred is rate-limited

Primary API (use these):
- report_rate_limit() - Report when an agent hits a rate limit
- is_agent_available() - Check if an agent is available
- get_fallback_agent() - Get available agent from fallback chain
- get_usage_status() - Get status of all agents
- parse_rate_limit_error() - Parse agent output for rate limits
"""

# Primary API - unified client that tries service, falls back to local
from agentbox.usage.client import (
    report_rate_limit,
    clear_rate_limit,
    is_agent_available,
    get_fallback_agent,
    get_usage_status,
    parse_rate_limit_error,
    FALLBACK_CHAINS,
)

# Local state management (fallback when service unavailable)
from agentbox.usage.state import (
    load_state,
    save_state,
    update_agent_state,
    clear_agent_state,
    get_agent_state,
)

# Fallback chain logic
from agentbox.usage.fallback import (
    get_status_summary,
)

# Parser for probing (used by container client)
from agentbox.usage.parser import (
    parse_agent_output,
    probe_agent,
)

__all__ = [
    # Primary API (unified client)
    "report_rate_limit",
    "clear_rate_limit",
    "is_agent_available",
    "get_fallback_agent",
    "get_usage_status",
    "parse_rate_limit_error",
    "FALLBACK_CHAINS",
    # Local state management (fallback)
    "load_state",
    "save_state",
    "update_agent_state",
    "clear_agent_state",
    "get_agent_state",
    # Fallback chain
    "get_status_summary",
    # Parser
    "parse_agent_output",
    "probe_agent",
]
