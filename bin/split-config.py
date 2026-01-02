#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Sync runtime Claude config back to project config.

Reads:
  - /home/abox/.claude/config.json (runtime config, edited by Claude)

Writes:
  - /workspace/.agentbox/config.json (project config)
"""

import json
import os
import sys
from pathlib import Path


def _env_path(var_name: str, default: Path) -> Path:
    value = os.getenv(var_name)
    return Path(value) if value else default


def split_config() -> bool:
    """Split runtime config changes back to project config."""
    runtime_config_path = _env_path(
        "AGENTBOX_CLAUDE_RUNTIME_CONFIG",
        Path("/home/abox/.claude/config.json"),
    )
    project_config_path = _env_path(
        "AGENTBOX_CLAUDE_PROJECT_CONFIG",
        Path("/workspace/.agentbox/config.json"),
    )

    # Read runtime config (edited)
    if not runtime_config_path.exists():
        print("Warning: Runtime config doesn't exist yet", file=sys.stderr)
        return False

    try:
        with open(runtime_config_path, 'r') as f:
            runtime_config = json.load(f)
    except Exception as e:
        print(f"Error: Failed to read runtime config: {e}", file=sys.stderr)
        return False

    # Ensure .agentbox directory exists
    project_config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write project config
    try:
        with open(project_config_path, 'w') as f:
            json.dump(runtime_config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error: Failed to write project config: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = split_config()
    sys.exit(0 if success else 1)
