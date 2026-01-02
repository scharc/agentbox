#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Sync runtime Codex config into project config.

Reads:
  - /home/abox/.codex/config.toml (runtime config)

Writes:
  - /workspace/.agentbox/codex.toml (project config)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None
    try:
        import tomli as tomllib  # type: ignore[assignment]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None


def read_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if tomllib is None:
        print("Error: tomllib not available", file=sys.stderr)
        return {}
    try:
        return tomllib.loads(path.read_text())
    except Exception as e:
        print(f"Warning: Failed to read {path}: {e}", file=sys.stderr)
        return {}


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return f'"{_toml_escape(value)}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        items = ", ".join(_toml_value(v) for v in value)
        return f"[{items}]"
    return str(value)


def dump_toml(data: Dict[str, Any]) -> str:
    lines: list[str] = []

    projects = data.get("projects", {})
    if isinstance(projects, dict):
        for project_path in sorted(projects.keys()):
            entry = projects[project_path]
            if not isinstance(entry, dict):
                continue
            lines.append(f'[projects."{project_path}"]')
            for key in sorted(entry.keys()):
                lines.append(f"{key} = {_toml_value(entry[key])}")
            lines.append("")

    mcp_servers = data.get("mcp_servers", {})
    if isinstance(mcp_servers, dict):
        for server_name in sorted(mcp_servers.keys()):
            entry = mcp_servers[server_name]
            if not isinstance(entry, dict):
                continue
            lines.append(f'[mcp_servers."{server_name}"]')

            for key in sorted(entry.keys()):
                if key in ("env", "http_headers", "env_http_headers"):
                    continue
                lines.append(f"{key} = {_toml_value(entry[key])}")

            for nested_key in ("env", "http_headers", "env_http_headers"):
                nested = entry.get(nested_key)
                if isinstance(nested, dict) and nested:
                    lines.append(f'[mcp_servers."{server_name}".{nested_key}]')
                    for nk in sorted(nested.keys()):
                        lines.append(f"{nk} = {_toml_value(nested[nk])}")

            lines.append("")

    if not lines:
        return "# empty\n"
    return "\n".join(lines).rstrip() + "\n"


def _env_path(var_name: str, default: Path) -> Path:
    value = os.getenv(var_name)
    return Path(value) if value else default


def split_config() -> bool:
    runtime_config_path = _env_path(
        "AGENTBOX_CODEX_RUNTIME_CONFIG",
        Path("/home/abox/.codex/config.toml"),
    )
    project_config_path = _env_path(
        "AGENTBOX_CODEX_PROJECT_CONFIG",
        Path("/workspace/.agentbox/codex.toml"),
    )

    runtime_config = read_toml(runtime_config_path)

    project_config_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        project_config_path.write_text(dump_toml(runtime_config))
        return True
    except Exception as e:
        print(f"Error: Failed to write project config: {e}", file=sys.stderr)
        return False


if __name__ == "__main__":
    success = split_config()
    sys.exit(0 if success else 1)
