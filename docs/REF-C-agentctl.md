# agentctl - Container-Side CLI

Session and worktree management from inside the container.

## Overview

`agentctl` runs **inside** containers. Use it to:

- Manage tmux sessions (list, attach, peek, kill)
- Work with git worktrees (create, switch, remove)
- Switch between branches without leaving the container

**Not to be confused with:**
- `abox` / `agentbox` - runs on **host**, manages containers
- `agentctl` - runs **inside container**, manages sessions/worktrees

## Quick Reference

```bash
# Sessions
agentctl list                        # List sessions
agentctl attach superclaude-1        # Attach to session
agentctl peek superclaude-1          # View without attaching
agentctl kill superclaude-1          # Kill session

# Worktrees
agentctl wt list                     # List worktrees
agentctl wt add feature-auth         # Create worktree
agentctl wt switch feature-auth superclaude  # Switch and start agent
agentctl wt remove feature-auth      # Remove worktree
```

---

## Session Commands

### agentctl list [--json]

List all tmux sessions.

```bash
agentctl list
```

Output:
```
SESSION              WINDOWS  ATTACHED  CREATED
superclaude-1        1        yes       Fri Jan 17 10:30
claude-tests         1        no        Fri Jan 17 09:15
feature-auth-super   1        no        Fri Jan 17 11:00
```

JSON output:
```bash
agentctl list --json
```

### agentctl attach AGENT

Attach to session. Creates it if it doesn't exist.

```bash
agentctl attach superclaude          # Attach or create
agentctl attach claude-tests         # Existing session
agentctl attach shell                # Shell session
```

**Agent types:** `claude`, `superclaude`, `codex`, `supercodex`, `gemini`, `supergemini`, `shell`

When creating new sessions:
- Determines working directory (worktree or `/workspace`)
- Preserves `SSH_AUTH_SOCK` for git operations
- Resets terminal on exit

### agentctl detach

Detach from current tmux session.

```bash
agentctl detach
```

Same as `Ctrl-a d` but works from scripts.

### agentctl peek SESSION [lines] [-f]

View session output without attaching.

```bash
agentctl peek superclaude-1          # Last 50 lines
agentctl peek superclaude-1 100      # Last 100 lines
agentctl peek superclaude-1 -f       # Follow mode (refresh every 1s)
```

Useful for checking progress without interrupting the agent.

### agentctl kill SESSION [-f]

Kill a session.

```bash
agentctl kill superclaude-1          # Asks confirmation
agentctl kill superclaude-1 -f       # Force, no confirmation
```

---

## Worktree Commands

Git worktrees let you work on multiple branches simultaneously. Each worktree is an independent checkout.

### agentctl wt list [--json]

List all worktrees.

```bash
agentctl wt list
agentctl worktree list               # Full form
```

Output:
```
PATH                                    BRANCH         COMMIT   SESSIONS
/workspace                              main           abc123   superclaude-1
/git-worktrees/worktree-feature-auth    feature-auth   def456   feature-auth-superclaude
/git-worktrees/worktree-bugfix          bugfix-123     789abc   -
```

### agentctl wt add BRANCH [-c]

Create a worktree.

```bash
agentctl wt add feature-auth         # Existing branch
agentctl wt add new-feature -c       # Create new branch
```

Worktrees created at `/git-worktrees/worktree-<branch>`.

Branch names are sanitized:
- `feature/auth` → `feature-auth`
- `refs/heads/main` → `main`

### agentctl wt remove BRANCH [-f]

Remove a worktree.

```bash
agentctl wt remove feature-auth      # Asks confirmation
agentctl wt remove feature-auth -f   # Force (discard changes)
```

Accepts branch name or full path:
```bash
agentctl wt remove feature-auth
agentctl wt remove /git-worktrees/worktree-feature-auth
```

Cannot remove `/workspace` (main worktree).

### agentctl wt prune

Clean up stale metadata.

```bash
agentctl wt prune
```

Removes tracking entries for worktrees that no longer exist.

### agentctl wt switch BRANCH AGENT

Switch to worktree and start agent session.

```bash
agentctl wt switch feature-auth superclaude
agentctl wt switch bugfix-123 claude
```

**What happens:**
1. Gets worktree path for branch
2. If in a session, sends STOP warning to current agent (3 second delay)
3. Creates session named `<branch>-<agent>` (e.g., `feature-auth-superclaude`)
4. Attaches to session in worktree directory

**The STOP warning:** When switching from an active session, agentctl sends a visible warning to the agent telling it to stop working immediately.

---

## Worktree Workflow

Typical workflow for parallel feature development:

```bash
# Start in main workspace
agentctl attach superclaude

# Agent decides to work on a feature branch
# (Agent can run these commands)

# Create worktree for feature
agentctl wt add feature-auth -c

# Switch to it
agentctl wt switch feature-auth superclaude

# Work on feature...
# Commit changes...

# Switch back to main
agentctl wt switch main superclaude

# Clean up when done
agentctl wt remove feature-auth
```

## Directory Structure

```
/workspace/                          # Main project (always exists)
├── .agentbox/
│   └── worktrees.json              # Worktree metadata
└── ...

/git-worktrees/                      # Worktree root
├── worktree-feature-auth/          # One per branch
│   └── ... (full checkout)
└── worktree-bugfix-123/
    └── ...
```

## Metadata

Worktree tracking stored in `/workspace/.agentbox/worktrees.json`:

```json
{
  "worktrees": [
    {
      "path": "/git-worktrees/worktree-feature-auth",
      "branch": "feature-auth",
      "commit": "abc123...",
      "created": "2026-01-17T10:30:00",
      "sessions": ["feature-auth-superclaude"]
    }
  ]
}
```

## MCP Integration

The `agentctl` MCP server exposes these functions to agents:

| MCP Function | Maps To |
|--------------|---------|
| `switch_branch(branch)` | Creates worktree + session |
| `switch_session(name)` | Attaches to session |
| `detach_and_continue(task)` | Detaches, agent keeps running |
| `list_worktrees()` | `agentctl wt list --json` |
| `list_sessions()` | `agentctl list --json` |
| `get_current_context()` | Current session, branch, worktree info |
| `set_session_task(task)` | Label session with task description |
| `clear_session_task()` | Remove task label |

Agents use these to autonomously manage their work across branches.

## Aliases

| Full | Short |
|------|-------|
| `agentctl worktree` | `agentctl wt` |

## Shell Completions

Tab completion available for bash and zsh:
- Session names
- Branch names
- Worktree paths

Completions installed automatically in container.

## See Also

- [CLI Reference](REF-A-cli.md) - Host-side `abox worktree` commands
- [agentboxd](REF-B-daemon.md) - Host daemon that enables MCP communication
- [agentbox-analyst](agentbox-analyst.md) - Cross-agent analysis
