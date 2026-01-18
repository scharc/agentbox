# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Dynamic context building from native configs."""

import json
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[assignment]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None


def _parse_skill_frontmatter(skill_path: Path) -> dict:
    """Parse YAML frontmatter from a SKILL.md file.

    Handles common edge cases:
    - BOM markers
    - CRLF line endings
    - Colons in values
    - Quoted strings
    - Multiline values (YAML block scalars with |)
    """
    try:
        content = skill_path.read_text(encoding="utf-8-sig")  # Handle BOM
        content = content.replace("\r\n", "\n")  # Normalize line endings

        # Match YAML frontmatter between --- markers (can start with optional whitespace)
        match = re.match(r"^\s*---\s*\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return {}

        frontmatter = match.group(1)

        # Try PyYAML if available (most robust)
        try:
            import yaml
            parsed = yaml.safe_load(frontmatter)
            # Ensure we return a dict (YAML could be a list or scalar)
            return parsed if isinstance(parsed, dict) else {}
        except ImportError:
            pass

        # Fallback: simple parser for common cases
        result = {}
        lines = frontmatter.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]

            # Skip empty lines and comments
            if not line.strip() or line.strip().startswith("#"):
                i += 1
                continue

            # Must have a colon for key-value
            if ":" not in line:
                i += 1
                continue

            # Split on first colon only (handles colons in values)
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()

            # Handle multiline block scalar (|)
            if value == "|":
                multiline_parts = []
                i += 1
                # Collect indented lines
                while i < len(lines):
                    next_line = lines[i]
                    # Check if line is indented (part of block) or empty
                    if next_line and not next_line[0].isspace() and next_line.strip():
                        break
                    multiline_parts.append(next_line.strip())
                    i += 1
                value = " ".join(p for p in multiline_parts if p)
            else:
                i += 1

            # Handle quoted strings
            if value.startswith('"') and value.endswith('"') and len(value) > 1:
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'") and len(value) > 1:
                value = value[1:-1]

            if key:
                result[key] = value

        return result
    except Exception:
        return {}


def _get_slash_commands(project_dir: Path) -> list[tuple[str, str]]:
    """Get list of available slash commands with descriptions.

    Returns:
        List of tuples: (command_name, description)
    """
    commands_dir = project_dir / ".claude" / "commands"
    if not commands_dir.exists():
        return []

    commands = []
    seen = set()

    for cmd_file in sorted(commands_dir.glob("*.md")):
        # Get the command name (use symlink target name if it's a symlink)
        if cmd_file.is_symlink():
            # This is the user-facing name
            cmd_name = cmd_file.stem
            if cmd_name in seen:
                continue
            seen.add(cmd_name)

            # Read description from the target file
            try:
                content = cmd_file.read_text()
                desc = ""
                if content.startswith("---"):
                    # Parse frontmatter for description
                    end = content.find("---", 3)
                    if end > 0:
                        frontmatter = content[3:end]
                        for line in frontmatter.split("\n"):
                            if line.startswith("description:"):
                                desc = line.split(":", 1)[1].strip().strip('"\'')
                                break
                commands.append((cmd_name, desc))
            except Exception:
                commands.append((cmd_name, ""))

    return commands


def _build_dynamic_context(agentbox_dir: Path) -> str:
    """Build dynamic context string from native configs (MCPs, workspaces, skills)."""
    lines = ["## Dynamic Context", ""]

    # MCP Servers from native configs
    all_mcps = set()

    # Claude MCPs from .agentbox/claude/mcp.json
    claude_mcp_path = agentbox_dir / "claude" / "mcp.json"
    if claude_mcp_path.exists():
        try:
            claude_mcp_data = json.loads(claude_mcp_path.read_text())
            claude_mcps = claude_mcp_data.get("mcpServers", {})
            all_mcps.update(claude_mcps.keys())
        except Exception:
            pass

    # Codex MCPs from .agentbox/codex/config.toml
    codex_config_path = agentbox_dir / "codex" / "config.toml"
    if codex_config_path.exists():
        try:
            import tomllib
            codex_data = tomllib.loads(codex_config_path.read_text())
            codex_mcps = codex_data.get("mcp_servers", {})
            all_mcps.update(codex_mcps.keys())
        except Exception:
            pass

    if all_mcps:
        lines.append("### MCP Servers Available")
        for mcp_name in sorted(all_mcps):
            lines.append(f"- `{mcp_name}`")
        lines.append("")

    # Workspace Mounts from .agentbox/workspaces.json
    workspaces_path = agentbox_dir / "workspaces.json"
    if workspaces_path.exists():
        try:
            workspaces_data = json.loads(workspaces_path.read_text())
            workspaces = workspaces_data.get("workspaces", [])
            if workspaces:
                lines.append("### Workspace Mounts")
                lines.append("Extra directories mounted in the container:")
                for entry in workspaces:
                    mount = entry.get("mount", "")
                    path = entry.get("path", "")
                    mode = entry.get("mode", "ro")
                    lines.append(f"- `/context/{mount}` → `{path}` ({mode})")
                lines.append("")
        except Exception:
            pass

    # Skills from directory listings with descriptions
    claude_skills_dir = agentbox_dir / "claude" / "skills"
    codex_skills_dir = agentbox_dir / "codex" / "skills"
    all_skills: dict[str, dict] = {}  # name -> {description, path}

    for skills_dir in [claude_skills_dir, codex_skills_dir]:
        if not skills_dir.exists():
            continue
        for skill_dir in skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            # Skip system skills (hidden directories)
            if skill_dir.name.startswith("."):
                continue
            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                frontmatter = _parse_skill_frontmatter(skill_file)
                skill_name = frontmatter.get("name", skill_dir.name)
                description = frontmatter.get("description", "")
                # Don't overwrite if we already have this skill with a description
                if skill_name not in all_skills or not all_skills[skill_name].get("description"):
                    all_skills[skill_name] = {"description": description}

    if all_skills:
        lines.append("### Skills")
        lines.append("Available skills. Use the Skill tool to invoke them when relevant:")
        lines.append("")
        for skill_name in sorted(all_skills.keys()):
            info = all_skills[skill_name]
            desc = info.get("description", "")
            if desc:
                lines.append(f"- **{skill_name}**: {desc}")
            else:
                lines.append(f"- **{skill_name}**")
        lines.append("")

    # Slash commands from .claude/commands/
    project_dir = agentbox_dir.parent
    slash_commands = _get_slash_commands(project_dir)
    if slash_commands:
        lines.append("### Slash Commands")
        lines.append("Use these commands when relevant to the task:")
        lines.append("")
        for cmd_name, desc in slash_commands:
            if desc:
                lines.append(f"- `/{cmd_name}`: {desc}")
            else:
                lines.append(f"- `/{cmd_name}`")
        lines.append("")

    # Add skill/command usage instruction if any are available
    if all_skills or slash_commands:
        lines.append("### Using Skills and Commands")
        lines.append("")
        lines.append("**IMPORTANT:** Proactively use available skills and slash commands when they match the task at hand.")
        lines.append("- Skills provide specialized capabilities - invoke them with the Skill tool")
        lines.append("- Slash commands are quick actions - they appear in autocomplete with `/`")
        lines.append("- Don't wait to be asked - if a skill/command fits the situation, use it")
        lines.append("- Example: Use `/improve` periodically to optimize agent configuration")
        lines.append("- Example: Use `/analyze` when debugging unexpected behavior")
        lines.append("")

    return "\n".join(lines)


def _load_codex_config(path: Path) -> dict:
    if not path.exists():
        return {}
    if tomllib is None:
        return {}
    try:
        return tomllib.loads(path.read_text())
    except Exception:
        return {}
