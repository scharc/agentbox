# Agentbox Development Log

## 2025-12-30 - Notifications MCP + Socket Fix ✅

- [x] Added `notify` MCP server library entry and Python server
- [x] Made `notify` MCP always on in default project config + codex.toml
- [x] Added `high` urgency level (maps to `critical` for notify-send)
- [x] Updated AGENTS default context to require notifications on questions
- [x] Fixed notify socket staleness by symlinking to `/run/user/<uid>/agentbox-notify.sock`

## 2025-12-30 - Remove Tools System ✅

- [x] Removed tools library support and CLI commands
- [x] Removed tools mount/config handling
- [x] Updated docs to focus on MCP servers and skills

## 2025-12-30 - Optional Docker MCP ✅

- [x] Added Docker MCP template
- [x] Mount Docker socket only when Docker MCP is enabled

## 2025-12-30 - Rename to Agentbox ✅

- [x] Renamed package/command to `agentbox`
- [x] Added `abox` alias (Poetry script + wrapper)
- [x] Updated paths and prefixes (`/agentbox`, `.agentbox`, `agentbox-*`)
- [x] Refreshed docs and completions to match the new name

### Commits
- `8dd30d4` - Rename core package to agentbox
- `ccc6155` - Update docs for agentbox

## 2025-12-28 - Phase 0: Session Documentation ✅

- [x] Created `/x/coding/agentbox/` directory
- [x] Copied implementation plan to `PLAN.md`
- [x] Created `DEVLOG.md` (this file)
- [x] Created `NOTES.md`
- [x] Initialized git repository
- [x] Initial commit with documentation

## 2025-12-28 - Phase 1: Base Infrastructure ✅

- [x] Created directory structure
- [x] Wrote `Dockerfile.base` with comprehensive tooling
  - Ubuntu 24.04
  - Node.js 24.x, Python 3.12, Git, Docker CLI
  - Claude Code via npm
  - System tools: jq, curl, wget, ripgrep, bat, fzf, httpie, inotify-tools
  - Database clients: postgresql-client, mysql-client, redis-tools
  - Build essentials: gcc, make, cmake
- [x] Wrote `container-init.sh` for startup configuration
- [x] Made scripts executable
- [x] Built and tested base image

## 2025-12-28 - Phase 2: Python Management Tool ✅

- [x] Created `pyproject.toml` with Poetry configuration
  - Dependencies: click, docker, pyyaml, rich
  - Entry point: `agentbox` command
- [x] Created modular Python package structure:
  - `cli.py` - Click-based CLI with all commands
  - `container.py` - Docker container lifecycle management
  - `config.py` - Project configuration management
  - `network.py` - IP address and /etc/hosts management
  - `library.py` - Library system for browsing templates
- [x] Implemented core CLI commands:
  - `start`, `stop`, `ps`, `remove`, `cleanup`, `rebuild`
  - `shell`, `claude`, `ip`
  - `init` - Initialize project-specific .agentbox/ directory
  - `hosts add/remove/list` - Manage /etc/hosts entries
  - `mcp list/show/add/remove` - Manage MCP servers
  - `skill list/show` - Browse skills library

## 2025-12-28 - Installation & Wrapper Script ✅

- [x] Created wrapper script `bin/agentbox`
  - Preserves current working directory via AGENTBOX_PROJECT_DIR
  - Resolves symlinks correctly with `readlink -f`
  - Passes through to Poetry command
- [x] Added alias wrapper `bin/abox`
- [x] Made symlink in ~/.local/bin for global access
- [x] Generated and configured zsh completion

## 2025-12-28 - Major Architecture Refactor ✅

### Removed Dotfiles Dependency
- [x] Removed dotfiles mounting entirely
- [x] Switched from zsh to bash (universal compatibility)
- [x] Container now uses clean bash environment

### Project-Centric Design
- [x] Each project has `.agentbox/` directory with:
  - `config.json` - Claude Code settings and MCP servers
  - `state/` - Claude runtime state and history (per-project)
  - `skills/` - Custom Claude Code skills
  - `.gitignore` - Ignores state/ and .env files
  - `README.md` - Documentation for project config

### Bidirectional Config Sync
- [x] Created `bin/merge-config.py` - Merges global + project configs
- [x] Created `bin/split-config.py` - Extracts project-specific changes
- [x] Created `bin/config-watcher.sh` - polling-based live sync
  - Watches project config → syncs to container runtime
  - Watches container runtime → syncs back to project
  - Debouncing and lock mechanism prevents loops

### Username-Based Mount Paths
- [x] Changed from confusing `/host-*` to `/${USER}/*` paths:
  - `/${USER}/ssh` - User's SSH keys (read-only)
  - `/${USER}/claude` - User's credentials from ~/.claude (read-only)
  - `/agentbox/library/*` - Global templates (read-only)
  - `/root/.claude` - Project state directory (read/write)

### Credential Sharing
- [x] Host `~/.claude/.credentials.json` mounted to container
- [x] Symlinked into `/root/.claude/.credentials.json`
- [x] Authenticate once on host, works in all containers

## 2025-12-28 - Repository Cleanup ✅

- [x] Consolidated all scripts into `bin/` directory
- [x] Organized library items into `library/` structure:
  - `library/config/` - Config presets
  - `library/mcp/` - MCP server templates
  - `library/skills/` - Skill definitions
- [x] Added `.gitignore` for Python artifacts and runtime data
- [x] Removed old runtime/ directory (now per-project)

## 2025-12-28 - MCP Template System ✅

- [x] Created MCP server templates with full documentation:
  - `postgres` - PostgreSQL database access
    - config.json with server definition
    - README.md with connection methods
    - Examples for host.docker.internal, containers, remote DBs
  - `github` - GitHub API access
    - Token-based authentication
    - Environment variable substitution (${GITHUB_TOKEN})
    - Setup instructions
  - `homeassistant` - Smart home control
    - Multiple connection methods
    - Token creation guide
    - Network access examples

## 2025-12-28 - CLI Simplification ✅

- [x] Removed confusing `library` command group
- [x] Consolidated all commands under top-level groups:
  - `agentbox mcp list/show/add/remove` - All MCP operations
  - `agentbox skill list/show` - All skill operations
- [x] Implemented `mcp add` command:
  - Reads template from library
  - Merges into project config.json
  - Shows environment variables and setup notes
  - Auto-syncs to container
- [x] Implemented `mcp remove` command
- [x] Fixed `init` command to create config.json even if directory exists

## 2025-12-28 - Naming Improvements ✅

- [x] Renamed `.agentbox/.claude/` → `.agentbox/state/`
  - Clearer: "state" indicates runtime/generated data
  - Avoids confusion with host `~/.claude/` directory
  - Updated all code, documentation, and .gitignore

## 2025-12-28 - Current Status: Testing & Fixes 🔄

### Issues Discovered
- [x] Credentials file is `.credentials.json` not `credentials.json` - Fixed
- [x] Base image contains old container-init.sh - Rebuilding
- [x] Native Claude binary URL 404 - Switched to npm package

### Testing Progress
- [✅] `agentbox init` creates correct directory structure
- [✅] `agentbox mcp add/remove` works with multiple MCPs
- [✅] Container creation and volume mounts work
- [✅] Host mounts verified (/${USER}/ssh, /${USER}/claude)
- [⏳] Base image rebuild in progress
- [⏸️] Credentials symlink (waiting for rebuild)
- [⏸️] Config merge/split scripts (waiting for rebuild)
- [⏸️] Config poller (waiting for rebuild)

### Commits
- `cfa22f2` - Phase 1 complete: Base infrastructure
- `e2fdc68` - Initial commit: Session documentation
- `e310811` - Add MCP server templates to library
- `fcc26d1` - Simplify CLI: Consolidate commands under mcp/skill
- `59aae05` - Fix mcp add/remove commands and init behavior
- `040c628` - Rename .claude to state for clarity

## Next Steps

- [ ] Complete base image rebuild
- [ ] Test credentials symlink creation
- [ ] Test config merge/split with default config
- [ ] Test config poller bidirectional sync
- [ ] End-to-end test: init → start → claude → config changes
- [ ] Verify security boundaries
- [ ] Add more MCP templates to library
- [ ] Document container networking (host.docker.internal)

## 2025-12-28 - Multi-AI Config & Bootstrap ✅

- [x] Added Codex and Gemini CLIs to base image
- [x] Added Codex config base (`library/config/default/codex.toml`)
- [x] Added Codex merge/split scripts
- [x] Switched config sync from inotify to polling (two-way)
- [x] Bootstrapped host auth/config for Claude, Codex, OpenAI, Gemini
- [x] Added extra mount support via `.agentbox/volumes.json`
