# Configuration

Agentbox is customizable but has sensible defaults. You can go deep or just use it out of the box.

This guide covers all configuration options - but you don't need to read it all. Start with the defaults, customize when you need to.

## The Philosophy

**Project-level config** (`.agentbox.yml`) controls what an agent can do in a specific project. Packages, mounts, MCPs, ports. Different projects can have different setups.

**Host-level config** (`~/.config/agentbox/`) sets your personal defaults and daemon settings. These apply across all your projects.

**Agent instructions** (`.agentbox/agents.md`, `.agentbox/superagents.md`) tell agents how to behave. Project conventions, things to avoid, workflow guidelines. Edit freely - they're yours.

---

## Quick Reference

**Add packages:**
```bash
agentbox packages add npm typescript
agentbox packages add pip pytest
# Auto-rebuilds the container
```

**Mount another directory:**
```bash
agentbox workspace add ~/other-repo ro reference
# Auto-rebuilds the container
```

**Enable an MCP:**
```bash
agentbox mcp add agentbox-analyst
# Auto-rebuilds if the MCP needs mounts
```

All these commands automatically rebuild the container to apply changes.

---

## Configuration Hierarchy

```
~/.config/agentbox/           # Host-level config (user preferences)
├── config.yml                # agentboxd settings, timeouts, web server
├── mcp/                      # Custom MCP servers (override library)
└── skills/                   # Custom skills (override library)

/path/to/project/             # Project-level config
├── .agentbox.yml             # Main project config (SSH, packages, ports, etc.)
└── .agentbox/                # Generated runtime files
    ├── agents.md             # Agent instructions template
    ├── superagents.md        # Super agent instructions template
    ├── claude/               # Claude-specific config
    │   └── mcp.json          # Active MCP servers for Claude
    ├── mcp/                   # Installed MCP server code
    ├── mcp-meta.json         # MCP installation tracking
    ├── LOG.md                # Development log
    └── workspaces.json       # Workspace mount tracking

/agentbox/library/            # Built-in library (inside container)
├── config/                   # Config templates
│   └── agentbox.yml.template
├── mcp/                      # Built-in MCP servers
└── skills/                   # Built-in skills
```

---

## 1. Project Config: `.agentbox.yml`

**Location:** Project root (e.g., `/workspace/.agentbox.yml`)
**Purpose:** Configure the container for this specific project
**Applied:** On `agentbox rebase` or container creation
**Model:** `agentbox/models/project_config.py`

### SSH Configuration

```yaml
ssh:
  enabled: true          # Enable SSH access (default: true)
  mode: keys             # How to provide SSH credentials
  forward_agent: false   # Forward SSH agent socket
```

**SSH Modes:**
| Mode | What it does | Use case |
|------|--------------|----------|
| `none` | No SSH setup | Projects that don't need git SSH |
| `keys` | Copy all ~/.ssh files into container | Default, works for most setups |
| `mount` | Bind mount ~/.ssh read-write | Keys change frequently |
| `config` | Copy only config/known_hosts | Use with `forward_agent: true` for hardware keys |

**forward_agent:** Required when `mode: config` since no private keys are copied. Also useful for passphrase-protected keys.

### Automatic Credential Sharing

Agentbox automatically shares your host credentials with the container. No configuration needed.

**How it works:**

| Host Path | Container Access | Purpose |
|-----------|------------------|---------|
| `~/.claude/` | Symlinked to `~/.claude/.credentials.json` | Claude OAuth tokens |
| `~/.codex/` | Symlinked to `~/.codex/auth.json` | Codex authentication |
| `~/.config/openai/` | Symlinked to `~/.config/openai/` | OpenAI CLI config |
| `~/.config/gemini/` | Symlinked to `~/.config/gemini/` | Gemini CLI config |
| `~/.claude.json` | Symlinked to `~/.claude.json` | Claude client state |

**Technical details:**

- Host directories are mounted read-write (not individual files)
- Container-init creates symlinks to expected locations
- Directory mounts avoid stale inode issues when OAuth tokens refresh
- Credentials authenticated on host work immediately in containers

**Why directory mounts?**

When OAuth tokens refresh, the credential file is replaced (new inode). If we mounted the file directly, the container would still see the old content. By mounting the parent directory, the container sees file updates even after replacement.

**Git author:**

Git commits use your host's `GIT_AUTHOR_NAME` and `GIT_AUTHOR_EMAIL` environment variables. If not set, defaults to your username.

### Workspace Mounts

```yaml
workspaces:
  - path: ~/projects/shared-lib    # Host path
    mount: shared-lib              # Name (mounted at /context/shared-lib)
    mode: ro                       # ro (read-only) or rw (read-write)
```

### Container Connections

```yaml
containers:
  - name: postgres-dev      # Docker container name
    auto_reconnect: true    # Reconnect if container restarts
```

Adds the agentbox container to the same Docker network as the specified container.

### Packages

```yaml
system_packages:           # apt packages (legacy, same as packages.apt)
  - ffmpeg
  - imagemagick

packages:
  apt: []                  # apt install <package>
  npm: []                  # npm install -g <package>
  pip: []                  # pip install <package>
  cargo: []                # cargo install <package>
  post: []                 # Custom shell commands after packages
```

### Environment Variables

```yaml
env:
  NODE_ENV: development
  DATABASE_URL: postgres://localhost/mydb
```

### Port Configuration

```yaml
ports:
  mode: tunnel             # tunnel (via agentboxd) or docker (native)
  host:                    # Expose container ports on host
    - "3000"               # container:3000 -> host:3000
    - "8080:3000"          # container:3000 -> host:8080
  container:               # Forward host ports into container
    - "5432"               # host:5432 -> container:5432
```

**Port modes:**
- `tunnel`: Uses SSH tunnel via agentboxd (preferred, survives container restart)
- `docker`: Native Docker port mapping (requires rebuild to change)
- `auto`: Automatically selects tunnel if agentboxd is running, otherwise docker

### Resources

```yaml
resources:
  memory: 4g               # Memory limit
  cpus: 2.0                # CPU limit
```

### Security

```yaml
security:
  seccomp: unconfined      # Required for debugging tools (strace, gdb)
  capabilities:
    - SYS_PTRACE           # For debugging
```

### Devices

Pass through hardware devices to the container:

```bash
agentbox devices              # Interactive chooser
agentbox devices list         # See configured and available
agentbox devices add /dev/snd # Add specific device
```

Or configure directly in `.agentbox.yml`:
```yaml
devices:
  - /dev/snd               # Audio device
  - /dev/dri/renderD128    # GPU
```

**Note:** Devices that are unavailable at container start are skipped automatically - the container won't fail if a USB device is unplugged.

### Docker Socket Access

```yaml
docker:
  enabled: true            # Mount /var/run/docker.sock
```

### Task Agents (Notification Enhancement)

```yaml
task_agents:
  enabled: false           # Enable AI-enhanced notifications
  agent: claude            # Agent to use (claude, codex, gemini)
  model: haiku             # Model for summarization
  timeout: 30              # Seconds to wait for response
  buffer_lines: 50         # Lines of terminal buffer to analyze
  enhance_hooks: true      # Enhance hook notifications
  enhance_stall: true      # Enhance stall detection notifications
  prompt_template: "..."   # Custom prompt for summarization
```

### Stall Detection

```yaml
stall_detection:
  enabled: true            # Detect when agent appears stuck
  threshold_seconds: 30.0  # Seconds of inactivity before notification
```

### MCP Servers and Skills

```yaml
mcp_servers:
  - agentctl               # Names of MCP servers to enable
  - agentbox-analyst

skills:
  - westworld              # Names of skills to enable
```

---

## 2. Host Config: `~/.config/agentbox/config.yml`

**Location:** `~/.config/agentbox/config.yml`
**Purpose:** User preferences for agentboxd daemon and host behavior
**Applied:** On agentboxd startup
**Model:** `agentbox/models/host_config.py`

### Web Server

```yaml
web_server:
  enabled: true            # Enable web UI
  host: 127.0.0.1          # Legacy single host (if hosts is empty)
  hosts:                   # Bind to multiple addresses
    - 127.0.0.1
    - tailscale            # Special: resolves to Tailscale IP
  port: 8080
  log_level: info
```

### Network (Port Tunneling)

```yaml
network:
  bind_addresses:          # Addresses for port tunnels
    - 127.0.0.1
    - tailscale            # Expose on Tailscale network
```

### Tailscale Monitor

```yaml
tailscale_monitor:
  enabled: true
  check_interval_seconds: 30.0   # How often to check for IP changes
```

### Notifications

```yaml
notifications:
  timeout: 2.0             # Timeout for notify-send
  timeout_enhanced: 60.0   # Timeout for AI-enhanced notifications
  deduplication_window: 10.0  # Seconds to deduplicate same notification
  hook_timeout: 5.0        # Timeout for user notify hooks
```

### Host Task Agents

```yaml
task_agents:
  enabled: false           # Host-level task agent config
  agent: claude
  model: haiku
  timeout: 30
  buffer_lines: 50
```

### Stall Detection (Host-level)

```yaml
stall_detection:
  enabled: true
  threshold_seconds: 30.0
  check_interval_seconds: 5.0
  cooldown_seconds: 60.0
```

### Timeouts

```yaml
timeouts:
  container_wait: 6.0           # Wait for container to start
  container_wait_interval: 0.25 # Polling interval
  web_connection: 2.0           # Web socket connection timeout
  web_resize_wait: 0.1          # Wait after terminal resize
  proxy_connection: 2.0         # Proxy connection timeout
  stream_registration: 5.0      # Stream registration timeout
  tmux_command: 2.0             # Tmux command timeout
```

### Polling

```yaml
polling:
  web_output: 0.1          # Web terminal output polling
  stream_monitor: 0.01     # Stream data monitoring
  session_check: 5.0       # Session health check
```

### Terminal Defaults

```yaml
terminal:
  default_width: 80
  default_height: 24
```

### Paths

```yaml
paths:
  agentbox_dir: null       # Override agentbox installation dir
```

---

## 3. MCP Server Library

**Locations:**
- Built-in: `/agentbox/library/mcp/` (inside container)
- Custom: `~/.config/agentbox/mcp/` (user overrides)

**Structure:**
```
mcp/<server-name>/
├── config.json           # Server configuration
├── server.py             # Server implementation (or package.json for npm)
├── README.md             # Description
└── commands/             # Optional slash commands
    └── <command>.md
```

**config.json format:**
```json
{
  "name": "server-name",
  "description": "What this server does",
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

**Usage:** Add to `.agentbox.yml`:
```yaml
mcp_servers:
  - agentctl
  - my-custom-server
```

Or use CLI: `agentbox mcp add <name>`

---

## 4. Skills Library

**Locations:**
- Built-in: `/agentbox/library/skills/` (inside container)
- Custom: `~/.config/agentbox/skills/` (user overrides)

**Structure:**
```
skills/<skill-name>/
├── SKILL.md              # Main skill definition with YAML frontmatter
└── commands/             # Optional slash commands
    └── <command>.md
```

**SKILL.md format:**
```markdown
---
name: westworld
description: Diagnostic modes for coding agents
triggers:
  - diagnostic mode
  - show goals
---

# Instructions for the agent when skill is activated
...
```

**Usage:** Add to `.agentbox.yml`:
```yaml
skills:
  - westworld
```

Or use CLI: `agentbox skill add <name>`

---

## 5. Agent Instructions

Understanding how agent instructions work is key to customizing agent behavior.

### How Instructions Are Assembled

When you run `agentbox claude` or `agentbox superclaude`, the system assembles a system prompt from multiple sources:

```
┌─────────────────────────────────────────────────────────┐
│ Final System Prompt (what the agent sees)               │
├─────────────────────────────────────────────────────────┤
│ 1. .agentbox/agents.md         (base instructions)      │
│ 2. .agentbox/superagents.md    (if super* agent)        │
│ 3. Dynamic Context             (generated at runtime)   │
│    - Available MCP servers                              │
│    - Workspace mounts                                   │
│    - Installed skills                                   │
│    - Slash commands                                     │
└─────────────────────────────────────────────────────────┘
```

**Regular agents** (`claude`, `codex`, `gemini`) get `agents.md` + dynamic context.

**Super agents** (`superclaude`, `supercodex`, `supergemini`) get `agents.md` + `superagents.md` + dynamic context.

### agents.md - Base Instructions

**Location:** `.agentbox/agents.md`
**Editable:** Yes
**Copied from:** `library/config/default/agents.md` on `agentbox init`

This file tells agents about their environment:
- They're running inside a Docker container
- Working directory is `/workspace`
- What tools are available (`agentctl`, `notify.sh`)
- What they CAN'T do (run `agentbox` commands, access host filesystem)
- Workflow best practices

**Customize this file** to add project-specific instructions that apply to all agents. Add your notes below the `---` separator line.

Example customizations:
```markdown
---

## Project Notes

- This is a Python/FastAPI project
- Run tests with `pytest tests/`
- Database migrations: `alembic upgrade head`
- Never commit directly to main branch
```

### superagents.md - Autonomous Mode Instructions

**Location:** `.agentbox/superagents.md`
**Editable:** Yes
**Copied from:** `library/config/default/superagents.md` on `agentbox init`

This file adds instructions for autonomous agents running with `--dangerously-skip-permissions`:
- Auto-approve mode reminder
- Autonomous workflow guidelines
- Commit frequently, notify on completion
- Safety guidelines even with full permissions

**Customize this file** for project-specific autonomous behavior. Add notes below the `---` separator.

Example customizations:
```markdown
---

## Autonomous Guidelines

- Always run `make test` before committing
- Push to feature branches, never directly to main
- Send notification after completing major tasks
- If tests fail, fix before moving on
```

### Dynamic Context

Dynamic context is generated at runtime and appended to agent instructions. You don't edit this directly—it's assembled from your configuration:

**MCP Servers:** Lists all MCP servers configured in `.agentbox/claude/mcp.json`. Agents use this to know what tools they have.

**Workspace Mounts:** Shows additional directories mounted at `/context/`. Helps agents know what external files they can access.

**Skills:** Lists available skills from `.agentbox/claude/skills/`. Tells agents to use the Skill tool to invoke them.

**Slash Commands:** Lists available `/commands` from `.claude/commands/`. Tells agents when to use them.

### Why Two Files?

The separation exists because:

1. **Different trust levels.** Regular agents ask for permission. Super agents execute autonomously. Different instructions are appropriate.

2. **Gradual escalation.** Start with `agentbox claude`, switch to `agentbox superclaude` when you trust the agent's judgment.

3. **Customization flexibility.** You might want all agents to know about your test framework, but only super agents to auto-push to remote.

### Updating Instructions

After editing instruction files:
- **New sessions** pick up changes immediately
- **Existing sessions** keep their original instructions
- Kill the session and start fresh to apply changes

---

## 6. Runtime Files (`.agentbox/`)

These files are generated/managed automatically:

| File | Purpose | Editable |
|------|---------|----------|
| `agents.md` | Base agent instructions | Yes (template) |
| `superagents.md` | Super agent instructions | Yes (template) |
| `claude/mcp.json` | Active MCP config for Claude | No (generated) |
| `mcp/` | Installed MCP server code | No (managed) |
| `mcp-meta.json` | Tracks MCP installations | No (managed) |
| `LOG.md` | Development log | Yes (append) |
| `workspaces.json` | Workspace mount tracking | No (managed) |

---

## 7. Configuration Priority

1. **Environment variables** (highest priority)
   - `AGENTBOX_DIR` - Override agentbox installation path
   - `AGENTBOX_PROJECT_DIR` - Override project directory

2. **Project config** (`.agentbox.yml`)
   - Per-project settings

3. **Host config** (`~/.config/agentbox/config.yml`)
   - User preferences

4. **Library defaults** (`library/config/`)
   - Built-in defaults

5. **Pydantic model defaults** (lowest priority)
   - Hardcoded fallbacks

---

## 8. Common Workflows

### Adding packages
```yaml
# Edit .agentbox.yml
packages:
  pip:
    - requests
    - pandas
```
Then run: `agentbox rebase`

### Exposing a port (no rebuild needed)
```bash
agentbox ports expose 3000        # Container:3000 -> Host:3000
agentbox ports expose 3000 8080   # Container:3000 -> Host:8080
```

### Forwarding host port (no rebuild needed)
```bash
agentbox ports forward 5432       # Host:5432 -> Container:5432
```

### Adding an MCP server
```bash
agentbox mcp add agentbox-analyst             # Add from library
agentbox rebase                  # Apply changes
```

### Adding a workspace mount
```yaml
# Edit .agentbox.yml
workspaces:
  - path: ~/other-project
    mount: other
    mode: ro
```
Then run: `agentbox rebase`

### Customizing agent instructions
Edit `.agentbox/agents.md` or `.agentbox/superagents.md` directly. Changes apply to new sessions.

---

## 9. Validation

Configurations are validated using Pydantic models:
- Invalid values show warnings but fall back to defaults
- Version mismatches are warned about
- Package names are validated for shell safety

Run `agentbox config migrate` to update old configs to the latest format.

---

## See Also

- [CLI Reference](REF-A-cli.md) - All `agentbox` commands
- [agentboxd](REF-B-daemon.md) - Host daemon configuration details
- [agentctl](REF-C-agentctl.md) - Container-side CLI
- [Library](REF-E-library.md) - MCPs and skills
