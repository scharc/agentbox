#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Sync project Claude config into runtime config.

Reads:
  - /workspace/.agentbox/config.json (project config, generated)

Writes:
  - /home/abox/.claude/config.json (runtime config)
"""

import json
import os
import sys
from pathlib import Path


def _env_path(var_name: str, default: Path) -> Path:
    value = os.getenv(var_name)
    return Path(value) if value else default


def merge_configs() -> bool:
    """Sync project config into runtime config."""
    project_config_path = _env_path(
        "AGENTBOX_CLAUDE_PROJECT_CONFIG",
        Path("/workspace/.agentbox/config.json"),
    )
    runtime_config_path = _env_path(
        "AGENTBOX_CLAUDE_RUNTIME_CONFIG",
        Path("/home/abox/.claude/config.json"),
    )

    if not project_config_path.exists():
        print("Warning: Project config doesn't exist yet", file=sys.stderr)
        return False

    project_config = {}
    if project_config_path.exists():
        try:
            with open(project_config_path, 'r') as f:
                project_config = json.load(f)
        except Exception as e:
            print(f"Warning: Failed to read project config: {e}", file=sys.stderr)

    # Ensure .claude directory exists
    runtime_config_path.parent.mkdir(parents=True, exist_ok=True)

    # Write runtime config
    try:
        with open(runtime_config_path, 'w') as f:
            json.dump(project_config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error: Failed to write runtime config: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = merge_configs()
    sys.exit(0 if success else 1)
