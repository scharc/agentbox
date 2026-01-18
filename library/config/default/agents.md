# Agent Context

You are running in an Agentbox containerized environment.

## Understanding Agentbox: Inside vs Outside

**You are INSIDE the container right now.** Agentbox has two parts:

### INSIDE (Where You Are)
- **Location:** Docker container
- **Working directory:** `/workspace` (your project code)
- **What you CAN do:**
  - Edit files in `/workspace`
  - Run `agentctl wt` - manage git worktrees for parallel branch work
  - Run `notify.sh` - send desktop notifications to the host
  - Use all dev tools: git, node, python, docker CLI, etc.

**What you CANNOT do:**
- Run `abox` or `agentbox` commands (those are host-only)
- Manage containers or add MCP servers (requires host rebuild)
- Access host filesystem outside mounted volumes

### OUTSIDE (Host System)
The user's laptop that controls containers:
- `abox` - Quick launcher for agents
- `agentbox` - Container lifecycle, MCP servers, workspace management
- Web proxy service - Notification bridge

## Working on the Agentbox Repository

**If you're working on the agentbox repo itself** (not a user project), read the detailed documentation:
- `docs/agent-architecture-guide.md` - Complete architecture reference
- `docs/AGENT-QUICK-REF.md` - Quick command reference

These docs explain:
- Host-side vs container-side code split
- Coding style (NO FLAGS - positional args only)
- Testing requirements (pytest, DinD tests)
- Python package management (Poetry)

## Environment
- **Working directory:** `/workspace` (your project root)
- **Container:** Isolated Docker environment with full development tooling
- **Shell:** Bash (default)

## Workflow Best Practices
- Commit changes frequently using git
- Keep a development log in `.agentbox/LOG.md`
- After completing tasks, update the project-specific notes below to help future agents

## Available Resources
Dynamic context about workspace mounts, MCP servers, and skills will be provided at runtime.

---

_This file is a static template. Agentbox does not modify it._
_Add your project-specific instructions and notes below this line._
