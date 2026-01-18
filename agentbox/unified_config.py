# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Unified config helpers for Agentbox."""

from __future__ import annotations

import json
from copy import deepcopy
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


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def read_toml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    if tomllib is None:
        return {}
    try:
        return tomllib.loads(path.read_text())
    except Exception:
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


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def deep_diff(runtime: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in runtime.items():
        if key not in baseline:
            result[key] = value
            continue
        base_value = baseline[key]
        if isinstance(value, dict) and isinstance(base_value, dict):
            nested = deep_diff(value, base_value)
            if nested:
                result[key] = nested
        elif value != base_value:
            result[key] = value
    return result


def normalize_unified(config: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(config) if isinstance(config, dict) else {}
    result.setdefault("version", 1)
    superset = result.get("superset")
    if not isinstance(superset, dict):
        superset = {}
    superset_mcp = superset.get("mcpServers")
    if not isinstance(superset_mcp, dict):
        superset_mcp = {}
    superset["mcpServers"] = superset_mcp
    result["superset"] = superset

    agents = result.get("agents")
    if not isinstance(agents, dict):
        agents = {}
    claude = agents.get("claude")
    if not isinstance(claude, dict):
        claude = {}
    claude_settings = claude.get("settings")
    if not isinstance(claude_settings, dict):
        claude_settings = {}
    claude_mcp = claude.get("mcpServers")
    if not isinstance(claude_mcp, dict):
        claude_mcp = {}
    claude_skills = claude.get("skills")
    if not isinstance(claude_skills, list):
        claude_skills = []
    claude["settings"] = claude_settings
    claude["mcpServers"] = claude_mcp
    if claude_skills:
        claude["skills"] = claude_skills
    agents["claude"] = claude

    codex = agents.get("codex")
    if not isinstance(codex, dict):
        codex = {}
    codex_projects = codex.get("projects")
    if not isinstance(codex_projects, dict):
        codex_projects = {}
    codex_mcp = codex.get("mcpServers")
    if not isinstance(codex_mcp, dict):
        codex_mcp = {}
    codex["projects"] = codex_projects
    codex["mcpServers"] = codex_mcp
    agents["codex"] = codex

    result["agents"] = agents
    return result


def build_claude_config(unified: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    unified = normalize_unified(unified)
    config = deepcopy(baseline) if isinstance(baseline, dict) else {}
    settings = config.get("settings")
    if not isinstance(settings, dict):
        settings = {}
    settings = deep_merge(settings, unified["agents"]["claude"]["settings"])
    config["settings"] = settings

    mcp_servers: Dict[str, Any] = {}
    if isinstance(config.get("mcpServers"), dict):
        mcp_servers = deepcopy(config["mcpServers"])
    mcp_servers = deep_merge(mcp_servers, unified["superset"]["mcpServers"])
    mcp_servers = deep_merge(mcp_servers, unified["agents"]["claude"]["mcpServers"])
    if mcp_servers:
        config["mcpServers"] = mcp_servers

    skills = unified["agents"]["claude"].get("skills")
    if isinstance(skills, list) and skills:
        config["skills"] = list(skills)

    return config


def build_codex_config(unified: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    unified = normalize_unified(unified)
    config = deepcopy(baseline) if isinstance(baseline, dict) else {}

    projects = config.get("projects")
    if not isinstance(projects, dict):
        projects = {}
    projects = deep_merge(projects, unified["agents"]["codex"]["projects"])
    config["projects"] = projects

    mcp_servers = config.get("mcp_servers")
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
    mcp_servers = deep_merge(mcp_servers, unified["superset"]["mcpServers"])
    mcp_servers = deep_merge(mcp_servers, unified["agents"]["codex"]["mcpServers"])
    if mcp_servers:
        config["mcp_servers"] = mcp_servers

    return config


def refold_unified_config(
    claude_config: Dict[str, Any],
    codex_config: Dict[str, Any],
    claude_baseline: Dict[str, Any],
    codex_baseline: Dict[str, Any],
    version: int = 1,
) -> Dict[str, Any]:
    claude_settings_base = claude_baseline.get("settings")
    if not isinstance(claude_settings_base, dict):
        claude_settings_base = {}
    claude_settings = claude_config.get("settings")
    if not isinstance(claude_settings, dict):
        claude_settings = {}
    settings_diff = deep_diff(claude_settings, claude_settings_base)

    base_projects = codex_baseline.get("projects")
    if not isinstance(base_projects, dict):
        base_projects = {}
    runtime_projects = codex_config.get("projects")
    if not isinstance(runtime_projects, dict):
        runtime_projects = {}
    project_overrides: Dict[str, Any] = {}
    for project_path, runtime_entry in runtime_projects.items():
        base_entry = base_projects.get(project_path)
        if runtime_entry != base_entry:
            project_overrides[project_path] = runtime_entry

    claude_mcp = claude_config.get("mcpServers")
    if not isinstance(claude_mcp, dict):
        claude_mcp = {}
    codex_mcp = codex_config.get("mcp_servers")
    if not isinstance(codex_mcp, dict):
        codex_mcp = {}

    superset_mcp: Dict[str, Any] = {}
    for name, entry in claude_mcp.items():
        if name in codex_mcp and codex_mcp[name] == entry:
            superset_mcp[name] = entry
    claude_only = {
        name: entry for name, entry in claude_mcp.items()
        if superset_mcp.get(name) != entry
    }
    codex_only = {
        name: entry for name, entry in codex_mcp.items()
        if superset_mcp.get(name) != entry
    }

    unified: Dict[str, Any] = {
        "version": version,
        "superset": {"mcpServers": superset_mcp},
        "agents": {
            "claude": {
                "settings": settings_diff,
                "mcpServers": claude_only,
            },
            "codex": {
                "projects": project_overrides,
                "mcpServers": codex_only,
            },
        },
    }

    claude_skills = claude_config.get("skills")
    if isinstance(claude_skills, list) and claude_skills:
        unified["agents"]["claude"]["skills"] = list(claude_skills)

    return normalize_unified(unified)
