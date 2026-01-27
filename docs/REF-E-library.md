# Library - MCPs and Skills

Boxctl provides a library of MCP servers and skills. You can also add your own.

## Directory Structure

```
Library (built-in, read-only)
├── /boxctl/library/mcp/          # Inside container
└── /boxctl/library/skills/

Custom (user overrides, read-write)
├── ~/.config/boxctl/mcp/         # On host, mounted into container
└── ~/.config/boxctl/skills/
```

**Priority:** Custom overrides library. If you have `~/.config/boxctl/mcp/my-server/`, it replaces any built-in MCP with the same name.

---

## Managing MCPs

```bash
# List all available
abox mcp list

# Show details
abox mcp show <name>

# Add to project
abox mcp add <name>
abox rebase                    # Apply changes

# Remove
abox mcp remove <name>
abox rebase

# Interactive TUI
abox mcp manage
```

### Core MCPs

| Name | Description |
|------|-------------|
| `agentctl` | Session and worktree management (enabled by default) |
| `boxctl-analyst` | Cross-agent analysis - see [boxctl-analyst](boxctl-analyst.md) |
| `notify` | Desktop notifications via boxctld |

**Agent bridge MCPs** (invoke one agent from another):

| Name | Available to |
|------|--------------|
| `claude-mcp` | codex, gemini |
| `codex-mcp` | claude, gemini |
| `gemini-mcp` | claude, codex |

For additional MCPs (databases, APIs, web search, etc.), create custom MCPs or use npm/PyPI MCP packages directly. Agents can use standard tools like `ssh` directly when keys are available.

### Adding Custom MCPs

Create a directory in `~/.config/boxctl/mcp/`:

```
~/.config/boxctl/mcp/my-server/
├── config.json       # Required
├── .env              # Optional: environment variables
├── server.py         # Or package.json for npm servers
└── README.md         # Optional
```

**config.json:**
```json
{
  "name": "my-server",
  "description": "What it does",
  "config": {
    "command": "python3",
    "args": ["/path/to/server.py"],
    "env": {}
  },
  "install": {
    "pip": ["fastmcp>=2.0.0"],
    "npm": []
  }
}
```

**.env file (optional):**
```bash
# API keys and secrets
MY_API_KEY=your-key-here
MY_SECRET=your-secret
```

When added to a project, `.env` values are merged into the MCP's environment. This allows you to:
- Store API keys once in `~/.config/boxctl/mcp/<name>/.env`
- Have them automatically available in all projects using that MCP
- Keep secrets out of git (the `.env` file stays in your home directory)

Then add to your project: `abox mcp add my-server && abox rebase`

### Updating Custom MCPs

When you modify files in `~/.config/boxctl/mcp/`:

```bash
# After editing config.json, .env, or server code
abox rebase
```

Changes are synced on rebase. Running containers won't pick up changes until you rebase.

---

## Managing Skills

```bash
# List all available
abox skill list

# Show details
abox skill show <name>

# Add to project
abox skill add <name>

# Remove
abox skill remove <name>

# Interactive TUI
abox skill manage
```

### Available Skills

| Name | Description |
|------|-------------|
| `westworld` | Diagnostic modes for debugging agent behavior |

### Adding Custom Skills

Create a directory in `~/.config/boxctl/skills/`:

```
~/.config/boxctl/skills/my-skill/
├── SKILL.md          # Required
└── commands/         # Optional slash commands
    └── my-command.md
```

**SKILL.md format:**
```markdown
---
name: my-skill
description: Brief description
triggers:
  - activate my skill
---

Instructions for the agent...
```

Then add to your project: `abox skill add my-skill`

---

## Environment Variables

MCPs that need credentials read from `.boxctl/.env`:

```bash
# .boxctl/.env (gitignored)
MY_API_KEY=xxx
```

Check individual MCP's `config.json` or README for required variables.

---

## Project Configuration

MCPs and skills are configured in `.boxctl.yml`:

```yaml
mcp_servers:
  - agentctl
  - boxctl-analyst

skills:
  - westworld
```

Changes require `abox rebase` to take effect.

---

## See Also

- [CLI Reference](REF-A-cli.md) - `abox mcp` and `abox skill` commands
- [Configuration](08-configuration.md) - Full config reference
- [boxctl-analyst](boxctl-analyst.md) - Cross-agent analysis MCP
