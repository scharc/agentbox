# Agentbox Architecture Guide for AI Agents

This guide helps AI agents understand the Agentbox architecture when working on the Agentbox repository itself.

## The Big Picture

Agentbox is a system that runs AI agents in isolated Docker containers. It has two distinct parts:

### 1. Inside the Container (Agent Runtime)
This is where AI agents execute. When a user runs `abox claude` or `abox superclaude`, they're launching an agent inside a Docker container.

**Location:** Inside Docker container
**What runs here:**
- AI agent CLIs (Claude Code, Codex, Gemini)
- Agent MCP servers
- User's project code at `/workspace`
- Development tools (git, node, python, docker CLI, etc.)

**Special tools inside:**
- **`agentctl`** (`/workspace/bin/agentctl`) - Python CLI for managing git worktrees and tmux sessions
  - Allows agents to work on multiple branches in parallel
  - Uses git worktree to create isolated branch environments
  - Integrates with tmux for session management
  - Source: `/workspace/agentbox/agentctl/`

- **`notify.sh`** / **`abox-notify`** (`/workspace/bin/notify.sh`, `/usr/local/bin/abox-notify`)
  - Send desktop notifications from container to host
  - Communicates via Unix socket to the web proxy on host
  - Socket path: `/home/abox/.agentbox/notify.sock`
  - Appends notifications to `.agentbox/LOG.md`

**Container initialization:**
- Entry point: `/workspace/bin/container-init.sh`
- Bootstraps credentials from host (SSH keys, git config, API tokens - read-only)
- Installs MCP server packages based on `/workspace/.agentbox/mcp-meta.json`
- Sets up tmux environment
- Runs `/workspace/bin/start-mcp-servers.py` to launch MCP servers

### 2. Outside the Container (Host System)
This is the user's host machine that creates and manages containers.

**Location:** Host system (user's laptop/workstation)
**What runs here:**
- **`agentbox`** CLI - Main command-line tool for managing containers
  - Source: `/workspace/agentbox/` Python package
  - Entry point: `/workspace/bin/agentbox`
  - Commands: `init`, `start`, `stop`, `remove`, `rebuild`, `mcp add`, `workspace add`, etc.
  - Main logic: `/workspace/agentbox/container.py`

- **`abox`** CLI - Quick launcher for agents
  - Entry point: `/workspace/bin/abox`
  - Shortcuts: `abox claude`, `abox superclaude`, `abox shell`, etc.
  - Just a convenience wrapper around `agentbox session` commands

- **Web proxy service** - Notification and web UI bridge
  - Source: `/workspace/agentbox/proxy.py`
  - Installed as systemd service: `agentbox proxy install --enable`
  - Functions:
    1. **Notification bridge**: Receives notifications from container via Unix socket, sends to host D-Bus
    2. **Web UI**: Serves tmux session viewer on `http://localhost:8765`
  - Socket path (mounted into container): `~/.agentbox/notify.sock`

## Communication Flow

```
┌─────────────────────────────────────────────────────┐
│ Host System                                         │
│                                                     │
│  User runs: abox superclaude                       │
│      ↓                                              │
│  agentbox CLI (Python)                             │
│      ↓                                              │
│  Starts/attaches Docker container                  │
│      ↓                                              │
│  Web Proxy Service (systemd)                       │
│    - Listens on Unix socket                        │
│    - Serves web UI on :8765                        │
│    - Sends D-Bus notifications                     │
└─────────────────────────────────────────────────────┘
           ↕ (Unix socket, Docker exec)
┌─────────────────────────────────────────────────────┐
│ Container (agentbox-agentbox)                       │
│                                                     │
│  container-init.sh (startup)                       │
│      ↓                                              │
│  Claude Code / Agent CLI                           │
│      ↓                                              │
│  Agent works on /workspace                         │
│      ↓                                              │
│  Calls notify.sh to send notification              │
│      ↓                                              │
│  Unix socket → Web Proxy → Host Desktop            │
│                                                     │
│  Agent can use agentctl for worktrees/sessions     │
└─────────────────────────────────────────────────────┘
```

## Key Files by Location

### Host-side (runs on user's machine)
- `/workspace/agentbox/container.py` - Container lifecycle management
- `/workspace/agentbox/proxy.py` - Notification and web proxy service
- `/workspace/agentbox/cli.py` - Main CLI entry point
- `/workspace/agentbox/config.py` - Configuration management
- `/workspace/agentbox/library.py` - MCP server library management
- `/workspace/agentbox/notifications.py` - Notification helpers
- `/workspace/agentbox/sessions.py` - Tmux session management
- `/workspace/agentbox/host_config.py` - Host configuration
- `/workspace/agentbox/web/host_server.py` - Web UI server
- `/workspace/agentbox/web/tmux_manager.py` - Tmux web interface
- `/workspace/Dockerfile.base` - Base image definition

### Container-side (runs inside Docker)
- `/workspace/bin/container-init.sh` - Container initialization script
- `/workspace/bin/agentctl` - Worktree/session management CLI
- `/workspace/bin/notify.sh` - Notification bridge script
- `/usr/local/bin/abox-notify` - Enhanced notification script
- `/workspace/bin/install-packages.py` - Package installation
- `/workspace/bin/start-mcp-servers.py` - MCP server launcher
- `/workspace/bin/generate-mcp-config.py` - MCP config generator
- `/workspace/agentbox/agentctl/` - Agentctl Python package

### Template files (copied to user projects)
- `/workspace/.agentbox/agents.md` - Base agent instructions (template)
- `/workspace/.agentbox/superagents.md` - Super agent instructions (template)
- `/workspace/.agentbox/config.json` - Agentbox project config
- `/workspace/.agentbox/mcp-meta.json` - MCP installation tracking
- `/workspace/.agentbox/workspaces.json` - Additional directory mounts

## Important Constraints

### What agents inside the container CAN do:
- Run `agentctl` to manage worktrees and sessions
- Run `notify.sh` to send notifications to host
- Access `/workspace` (read-write)
- Access `/context/*` mounts (typically read-only)
- Use MCP servers configured for the project
- Execute all standard dev tools

### What agents inside the container CANNOT do:
- Run `agentbox` or `abox` commands (those are host-side only)
- Directly access the host filesystem outside mounts
- Modify container configuration (requires host-side rebuild)
- Install MCP servers (requires host-side `agentbox mcp add`)

### What you need the host to do:
If you need to change container configuration (add MCP servers, mount new directories, etc.), the user must run commands on the host:
- `agentbox mcp add <name>` - Add MCP server
- `agentbox workspace add <path> <mode> <name>` - Mount directory
- `agentbox rebuild` - Apply changes

## Testing

Agentbox has a comprehensive test suite to ensure reliability.

### Unit Tests
**Location:** `/workspace/tests/`
**Run:** `pytest tests/`
**Coverage:** Configuration, library management, MCP servers, workspace handling

Fast tests that don't require Docker. Run these frequently during development:
```bash
pytest tests/                    # All unit tests
pytest tests/test_config.py      # Specific test file
pytest -k "test_mcp"            # Tests matching pattern
pytest -v                        # Verbose output
```

### Integration Tests (Docker-in-Docker)
**Location:** `/workspace/tests/dind/`
**Run:** `./tests/dind/run_dind_tests.sh`
**Coverage:** Full container lifecycle, session management, networking, real MCP integration

Comprehensive tests that run inside agentbox containers with Docker access:
```bash
./tests/dind/run_dind_tests.sh              # All integration tests
./tests/dind/run_dind_tests.sh -k networking # Specific tests
./tests/dind/run_dind_tests.sh -v           # Verbose output
```

**Requirements:** These tests must run inside an agentbox container with Docker socket access (already configured).

### Test Requirements for New Features
**All new features must have passing tests.** Before committing:
1. Write tests in `tests/test_yourfeature.py`
2. Run your tests: `pytest tests/test_yourfeature.py -v`
3. Run full suite: `pytest tests/`
4. For Docker/container changes: `./tests/dind/run_dind_tests.sh`

## Coding Style and Conventions

**CLI Command Design Philosophy:**

Agentbox follows a strict CLI design pattern:
- **NO FLAGS OR OPTIONS** - Do not add `--flag` or `-f` style arguments
- **POSITIONAL ARGUMENTS ONLY** - Arguments must be in the correct order
- **FOLLOW EXISTING PATTERNS** - Study current commands before adding new ones

**Examples:**
```bash
# ✅ CORRECT - Positional arguments
agentbox workspace add /home/user/code ro backend
agentbox mcp add agentbox-analyst
agentbox container connect postgres-dev
agentctl wt add feature-auth

# ❌ WRONG - Do not use flags
agentbox workspace add /home/user/code --mode ro --name backend
agentbox mcp add agentbox-analyst force
agentbox container connect postgres-dev auto-reconnect
agentctl wt add feature-auth create force
```

**Rationale:** Positional arguments keep commands clean, predictable, and consistent. The order matters and users learn the pattern quickly.

**When adding new commands:**
1. Study existing commands in `agentbox/cli/commands/` and `agentbox/agentctl/cli.py`
2. Use the same argument order pattern (e.g., resource name, mode, optional name)
3. Never add optional flags - use positional args or separate subcommands
4. Document the argument order clearly in help text

## Development Workflow

When working on the Agentbox repository:

1. **Changes to container-side scripts** (`bin/*`, `agentbox/agentctl/*`):
   - Edit the files in `/workspace/`
   - Test by running them inside the container
   - Rebuild base image to include changes: `agentbox rebuild-base`

2. **Changes to host-side Python code** (`agentbox/*.py`):
   - Edit the files in `/workspace/agentbox/`
   - Test by running `agentbox` commands from host
   - No container rebuild needed (Python package is mounted)

3. **Adding Python dependencies**:
   - Agentbox is a **Poetry project** - uses `pyproject.toml`
   - Add to `[project.dependencies]` or `[tool.poetry.group.dev.dependencies]`
   - User must run `poetry install` on host to install
   - Don't use `pip install` for project dependencies

4. **Changes to base image** (`Dockerfile.base`):
   - Edit `/workspace/Dockerfile.base`
   - Rebuild: `agentbox rebuild-base` (from host)
   - Recreate containers: `agentbox rebuild` (per project)

5. **Changes to template files** (`.agentbox/*`):
   - Edit templates in `/workspace/.agentbox/`
   - New projects will get updated templates
   - Existing projects keep their versions unless manually updated

## Common Confusion Points

**Q: Why can't I run `agentbox mcp add` from inside the container?**
A: `agentbox` is a host-side command that modifies the container configuration and rebuilds it. You're inside the container, so you can only use what's already installed.

**Q: How do notifications work?**
A: The web proxy service runs on the host and creates a Unix socket. This socket is mounted into the container at `/home/abox/.agentbox/notify.sock`. When you run `notify.sh` inside the container, it sends a JSON message through the socket, and the proxy displays it on the host desktop.

**Q: What's the difference between `abox` and `agentbox`?**
A: `abox` is a quick launcher (e.g., `abox claude`). `agentbox` is the full CLI with all management commands (e.g., `agentbox mcp add agentbox-analyst`). Both run on the host, not inside the container.

**Q: Where does `agentctl` run?**
A: Inside the container only. It's a tool for agents to manage git worktrees and tmux sessions without leaving the container environment.

## Summary

- **Inside container**: Agent runtime, `agentctl`, `notify.sh`, user code
- **Outside container**: `agentbox` CLI, `abox` launcher, web proxy service
- **Communication**: Unix socket for notifications, Docker exec for commands
- **One-way boundary**: Container can notify host, but can't manage itself

This architecture keeps agents isolated and safe while giving them the tools they need to work autonomously.
