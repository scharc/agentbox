# Agentbox CLI Reference

Complete command reference for `agentbox` (alias: `abox`).

## Command Philosophy

**No Flags Policy:** Agentbox uses positional arguments only. No `--flag` syntax. Commands read like English.

```bash
# Agentbox style - positional args
abox workspace add ~/docs ro reference
abox session new superclaude feature-auth

# NOT like this
abox workspace add --path ~/docs --mode ro --name reference  # Won't work
```

**Why positional args?** Mobile typing. When you're on Termius on your phone, typing `--long-flag-names` is painful. Positional args are faster and autocomplete better. The commands are designed to be memorable: `workspace add PATH MODE NAME` reads naturally.

**Exception:** `abox config migrate` has `--dry-run` and `--auto` flags for safety. Migration is dangerous enough that explicit flags make sense.

---

## Quick Reference

```bash
# Initialize and run
abox init                              # Initialize project
abox superclaude                       # Run autonomous Claude

# Manage
abox list                              # List containers
abox info                              # Show container info
abox shell                             # Open bash in container
abox q                                 # Mobile-friendly TUI menu

# Rebuild after config changes
abox rebase                            # Rebuild project container
abox rebuild                      # Rebuild base image
```

---

## Agents

Agents are the AI assistants that run inside containers. Each has a "super" variant that runs with auto-approve permissions.

### abox claude [project] [args...]

Run Claude Code interactively. The agent asks for permission before executing commands or editing files.

```bash
abox claude                            # Current project
abox claude myproject                  # Specific project
abox claude "fix the login bug"        # With initial prompt
```

**What happens:** Creates a tmux session named `superclaude-1`, launches Claude with the system prompt from `.agentbox/agents.md`, and attaches you to the session.

### abox superclaude [project] [args...]

Run Claude with `--dangerously-skip-permissions`. Full autonomy—the agent executes commands and edits files without asking.

```bash
abox superclaude
abox superclaude "refactor authentication and add tests"
```

**When to use:** When you trust the task and want hands-off execution. Great for well-defined tasks like "add tests for X" or "refactor Y using pattern Z". The agent gets additional instructions from `.agentbox/superagents.md` encouraging autonomous workflow.

**When NOT to use:** Exploratory work, unfamiliar codebases, or anything touching production.

### abox codex / supercodex [project] [args...]

Same pattern for OpenAI Codex.

### abox gemini / supergemini [project] [args...]

Same pattern for Google Gemini. (Untested)

### abox shell [project]

Open bash shell in container (no agent).

```bash
abox shell
abox shell myproject
```

---

## Project Lifecycle

### abox init

Initialize `.agentbox/` directory in current project.

```bash
cd ~/projects/myapp
abox init
```

Creates `.agentbox.yml` and `.agentbox/` directory structure.

### abox setup

Interactive setup wizard with prompts.

```bash
abox setup
```

### abox start

Start project container.

```bash
abox start
```

### abox stop [project]

Stop container.

```bash
abox stop
abox stop myproject
```

### abox list [all]

List agentbox containers.

```bash
abox list                              # Running only
abox list all                          # Include stopped
abox ps                                # Alias
abox ps all
```

### abox info [project]

Show container details (IP, mounts, sessions, MCPs).

```bash
abox info
abox info myproject
```

### abox connect [project] [session]

Connect to container, optionally to specific session.

```bash
abox connect                           # Default session
abox connect myproject                 # Project's default session
abox connect myproject superclaude-1   # Specific session
```

### abox remove [project] [force]

Remove container.

```bash
abox remove
abox remove myproject
abox remove myproject force            # Skip confirmation
```

### abox cleanup

Remove all stopped agentbox containers.

```bash
abox cleanup
```

### abox rebase [scope]

Rebuild project container from base image. Run after config changes.

```bash
abox rebase                            # Current project
abox rebase all                        # All projects
```

### abox reconfigure

Interactive reconfiguration of project settings.

```bash
abox reconfigure
```

---

## Sessions

Manage multiple agent sessions in a container. Sessions are tmux windows that persist even when you disconnect.

**Why sessions?** You might want multiple agents working in the same container—one doing research, another implementing. Or you might want to check on a running agent without interrupting it. Sessions let you multiplex.

### abox session new TYPE [name]

Create new session. TYPE: `claude`, `superclaude`, `codex`, `supercodex`, `gemini`, `supergemini`, `shell`.

```bash
abox session new superclaude           # Creates superclaude-1
abox session new superclaude feature   # Creates superclaude-feature
abox session new shell debug           # Creates shell-debug
```

### abox session list [all]

List sessions.

```bash
abox session list                      # Current project
abox session list all                  # All containers
```

### abox session attach SESSION

Attach to session.

```bash
abox session attach superclaude-1
```

### abox session remove SESSION

Kill session.

```bash
abox session remove superclaude-1
```

### abox session rename OLD NEW

Rename session identifier.

```bash
abox session rename superclaude-1 superclaude-feature
```

---

## Worktrees

Work on multiple git branches in parallel. Commands run inside container via `docker exec`.

### abox worktree list [json]

List worktrees.

```bash
abox worktree list
abox wt list                           # Alias
abox wt list json                      # JSON output
```

### abox worktree add BRANCH

Create worktree. Creates branch if it doesn't exist.

```bash
abox worktree add feature-auth
abox wt add bugfix-123
```

### abox worktree remove BRANCH [force]

Remove worktree.

```bash
abox wt remove feature-auth
abox wt remove feature-auth force      # Discard uncommitted changes
```

### abox worktree prune

Clean stale worktree metadata.

```bash
abox wt prune
```

### abox worktree shell BRANCH

Shell in worktree directory.

```bash
abox wt shell feature-auth
```

### abox worktree claude BRANCH [args...]

Run Claude in worktree.

```bash
abox wt claude feature-auth
abox wt claude feature-auth "implement OAuth"
```

### abox worktree superclaude BRANCH [args...]

Run superclaude in worktree.

```bash
abox wt superclaude feature-auth
```

---

## MCP Servers

### abox mcp list

List available MCPs (library + custom).

```bash
abox mcp list
```

### abox mcp show NAME

Show MCP details.

```bash
abox mcp show docker
abox mcp show agentctl
```

### abox mcp add NAME

Add MCP to project. Requires `abox rebase` to activate.

```bash
abox mcp add docker
abox mcp add agentbox-analyst
abox rebase
```

### abox mcp remove NAME

Remove MCP from project.

```bash
abox mcp remove docker
abox rebase
```

### abox mcp manage

Interactive checkbox selection.

```bash
abox mcp manage
```

---

## Skills

### abox skill list

List available skills.

```bash
abox skill list
```

### abox skill show NAME

Show skill details.

```bash
abox skill show westworld
```

### abox skill add NAME

Add skill to project.

```bash
abox skill add westworld
```

### abox skill remove NAME

Remove skill.

```bash
abox skill remove westworld
```

### abox skill manage

Interactive selection.

```bash
abox skill manage
```

---

## Workspaces

Mount additional directories into container.

### abox workspace list

List mounts.

```bash
abox workspace list
```

### abox workspace add PATH [mode] [name]

Add mount. Mode: `ro` (read-only, default) or `rw` (read-write).

```bash
abox workspace add ~/shared                    # ro, auto-named "shared"
abox workspace add ~/docs ro reference         # ro, named "reference"
abox workspace add ~/data rw data              # rw, named "data"
abox rebase                                    # Apply changes
```

Mounts appear at `/context/<name>/` in container.

### abox workspace remove NAME

Remove mount.

```bash
abox workspace remove reference
abox rebase
```

---

## Network

Connect to other Docker containers.

### abox network available [all]

List containers available for connection.

```bash
abox network available
abox network available all             # Include stopped
```

### abox network list

Show current connections.

```bash
abox network list
```

### abox network connect CONTAINER

Connect to container's network.

```bash
abox network connect postgres-dev
abox network connect redis-cache
```

After connecting, agents can reach `postgres-dev:5432` by hostname.

### abox network disconnect CONTAINER

Disconnect.

```bash
abox network disconnect postgres-dev
```

---

## Ports

Forward ports via SSH tunnel (no Docker port bindings needed).

### abox ports list

List configured ports.

```bash
abox ports list
```

### abox ports status

Show active tunnel connections.

```bash
abox ports status
```

### abox ports expose PORT_SPEC

Expose container port to host. Use when service runs IN container.

```bash
abox ports expose 3000                 # container:3000 → host:3000
abox ports expose 3000:8080            # container:3000 → host:8080
```

### abox ports unexpose PORT

Remove exposed port.

```bash
abox ports unexpose 3000
```

### abox ports forward PORT_SPEC

Forward host port into container. Use when service runs ON host.

```bash
abox ports forward 9222                # host:9222 → container:9222
```

### abox ports unforward PORT

Remove forwarded port.

```bash
abox ports unforward 9222
```

---

## Packages

Install packages in container.

### abox packages list

List configured packages.

```bash
abox packages list
```

### abox packages add TYPE PACKAGE

Add package. TYPE: `apt`, `npm`, `pip`, `cargo`, `post`.

```bash
abox packages add apt ffmpeg
abox packages add npm typescript
abox packages add pip pytest
abox packages add cargo ripgrep
abox rebase                            # Install packages
```

### abox packages remove TYPE PACKAGE

Remove package.

```bash
abox packages remove apt ffmpeg
```

### abox packages init

Initialize packages section in config.

```bash
abox packages init
```

---

## Docker Socket

Control Docker socket access in container.

### abox docker status

Show current status.

```bash
abox docker status
```

### abox docker enable

Enable Docker socket. Requires rebase.

```bash
abox docker enable
abox rebase
```

### abox docker disable

Disable Docker socket.

```bash
abox docker disable
abox rebase
```

---

## Devices

Pass through host devices (audio, GPU, serial) to the container.

Devices that are unavailable at container start are automatically skipped - the container won't fail to start if a device goes offline.

### abox devices

Interactive device selection. Shows available devices grouped by category with checkboxes.

```bash
abox devices                   # Interactive chooser
```

Pre-selects currently configured devices. Space to toggle, Enter to confirm.

### abox devices list

Show configured and available devices.

```bash
abox devices list
```

### abox devices add DEVICE

Add a device to passthrough.

```bash
abox devices add /dev/snd           # Audio
abox devices add /dev/dri/card0     # GPU
abox devices add /dev/ttyUSB0       # Serial
```

The device doesn't need to exist - unavailable devices are skipped at container start.

### abox devices remove DEVICE

Remove a device from passthrough.

```bash
abox devices remove /dev/snd
```

### abox devices clear

Remove all configured devices.

```bash
abox devices clear
```

### Device Categories

The interactive chooser detects these device types:

| Category | Device Patterns |
|----------|-----------------|
| Audio | `/dev/snd` |
| GPU (Intel/AMD) | `/dev/dri/card*`, `/dev/dri/renderD*` |
| GPU (NVIDIA) | `/dev/nvidia*` |
| Serial/USB | `/dev/ttyUSB*`, `/dev/ttyACM*` |
| Video/Camera | `/dev/video*` |
| Input | `/dev/input/event*` |

---

## Config

### abox config migrate

Migrate project config to latest format.

```bash
abox config migrate                    # Interactive
abox config migrate --dry-run          # Preview only
abox config migrate --auto             # Auto-apply all
```

---

## Base Image

### abox base rebuild

Rebuild the `agentbox-base` Docker image.

```bash
abox base rebuild
abox rebuild                           # Alias
```

Run after updating agentbox or Dockerfile.

---

## Service (agentboxd)

Host daemon for notifications, web UI, and SSH tunnels.

### abox service install

Install systemd user service.

```bash
abox service install
```

### abox service uninstall

Remove service.

```bash
abox service uninstall
```

### abox service start

Start service.

```bash
abox service start
```

### abox service stop

Stop service.

```bash
abox service stop
```

### abox service restart

Restart service.

```bash
abox service restart
```

### abox service status

Show service status.

```bash
abox service status
```

### abox service logs [lines]

Show logs.

```bash
abox service logs                      # Last 50 lines
abox service logs 100                  # Last 100 lines
```

### abox service follow

Follow logs in real-time.

```bash
abox service follow                    # Ctrl+C to stop
```

### abox service serve

Run in foreground (debugging).

```bash
abox service serve
```

### abox service config

Show/edit config file.

```bash
abox service config
```

---

## Quick Menu

### abox quick

Mobile-friendly TUI. Single-keypress navigation.

```bash
abox quick
abox q                                 # Alias
```

See [Quick Menu Guide](quick-menu.md) for full documentation.

---

## Utility

### abox fix-terminal

Reset terminal after escape sequence issues.

```bash
abox fix-terminal
```

---

## Aliases

| Full | Alias |
|------|-------|
| `agentbox` | `abox` |
| `abox list` | `abox ps` |
| `abox quick` | `abox q` |
| `abox worktree` | `abox wt` |
| `abox base rebuild` | `abox rebuild` |
| `abox mcp` | `abox mcps` |
| `abox skill` | `abox skills` |

---

## See Also

- [Quick Menu](quick-menu.md) - TUI guide
- [Configuration](08-configuration.md) - Config file reference
- [agentctl](REF-C-agentctl.md) - Container-side CLI
- [agentboxd](REF-B-daemon.md) - Host daemon details
- [Library](REF-E-library.md) - MCPs and skills
