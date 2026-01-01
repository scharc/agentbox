# Agentbox Implementation Plan (Current)

## Project Overview

**Agentbox** (`agentbox`, alias `abox`) is a secure, isolated Docker environment for Claude Code with:
- Complete development tooling (Node.js, Python, Git, Docker CLI)
- Safe isolation from the host system
- Dynamic workspace mounting
- Library system for reusable configs/MCP/skills
- Optional hostname aliases for local access

## Status Update (2025-12-30)

- Base image includes Claude, Codex, and Gemini CLIs
- Bash is the default shell
- Project config lives in `.agentbox/` with `config.json` (Claude) and `codex.toml` (Codex)
- Config sync uses polling (two-way) instead of inotify
- Host auth/config is bootstrapped into containers on startup
- Extra mounts are configured via `.agentbox/volumes.json` and mounted under `/context/<name>`
- Containers are named `agentbox-{project-name}` and use `agentbox-base:latest`
- Default notify MCP is always enabled for new projects
- Notify socket is stable via symlink to `/run/user/<uid>/agentbox-notify.sock`
- Docker socket is only mounted when the Docker MCP is enabled

## Architecture Summary

**Multi-Project Design**: One base image, multiple per-project containers

```
Host (/x/coding/agentbox/)          Base Image (agentbox-base)
├─ Dockerfile.base                  ├─ Ubuntu 24.04 minimal
├─ agentbox/ (Python package)      ├─ Bash (default shell)
├─ bin/                             ├─ Node.js LTS + npm
│  ├─ agentbox                      ├─ Python 3.12 + pip
│  ├─ abox                          ├─ Git + Docker CLI
│  ├─ container-init.sh             ├─ Claude/Codex/Gemini CLIs
│  └─ config-watcher.sh             └─ Essential build tools
├─ library/                         Per-Project Containers
│  ├─ config/                       (agentbox-{project-name})
│  ├─ mcp/                           ├─ /workspace (project dir, RW)
│  ├─ skills/                        ├─ /${USER}/* (auth/config, RO)
│  └─ skills/                        ├─ /root/.claude (runtime)
└─ completions/                      └─ /agentbox/library/* (RO)

Project Directory
├─ .agentbox/
│  ├─ config.json                    # Claude config
│  ├─ codex.toml                     # Codex config
│  ├─ state/                         # Runtime state (gitignored)
│  ├─ skills/                        # Project skills
│  └─ volumes.json                   # Extra mounts for /context/<name>
├─ src/
└─ package.json
```

## Command Surface

- `agentbox start|stop|ps|shell|claude|ip`
- `agentbox hosts add|remove|list`
- `agentbox mcp list|show|add|remove`
- `agentbox skill list|show`
- `agentbox volume list|add|remove`
- `agentbox remove|cleanup|rebuild|init|update`
- `abox` is a short alias for `agentbox`

## Key Files

- `agentbox/cli.py` - Click CLI with all commands
- `agentbox/container.py` - Docker container lifecycle
- `agentbox/config.py` - `.agentbox.yml` parsing and rebuild support
- `agentbox/network.py` - IP/hosts management
- `agentbox/library.py` - Library listing/show helpers
- `bin/agentbox` - Wrapper script (sets `AGENTBOX_PROJECT_DIR`)
- `bin/abox` - Alias wrapper for `agentbox`
- `bin/container-init.sh` - Container bootstrap + config poller
- `bin/config-watcher.sh` - Polling sync for Claude/Codex configs
- `bin/merge-*.py` / `bin/split-*.py` - Config merge/split utilities
- `completions/agentbox-completion.zsh` - Zsh completion for `agentbox`/`abox`

## Next Steps

- Rebuild base image and validate notify socket linkage
- End-to-end test: init → start → claude → config changes sync
- Verify hosts add/remove flows with new container prefix
