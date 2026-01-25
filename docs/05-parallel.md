# Parallel Work

One of the most powerful things about Agentbox is running multiple agents simultaneously. One agent fixing a bug, another building a feature, a third writing tests. Each working independently, not stepping on each other.

## The Problem with Branches

If two agents work on the same checkout, they conflict. Agent A is halfway through editing a file when Agent B checks out a different branch. Chaos.

Git only has one working directory. You can't have two branches checked out at once in the same place.

## Git Worktrees: Separate Checkouts

Git worktrees solve this. A worktree is a separate checkout of your repo - same git history, different working directory. Each branch gets its own folder. Agents don't interfere.

Think of it like having multiple copies of your project, but they share the git database. Changes in one worktree can be merged into another. They're connected, but isolated.

## Creating Worktrees

From the host:

```bash
agentbox worktree add feature-auth     # Create worktree for this branch
agentbox worktree add bugfix-123       # Another one
agentbox worktree list                 # See all worktrees
```

Inside the container, agents can create them too:

```bash
agentctl worktree add feature-auth           # Create worktree
agentctl worktree add new-feature -c         # Create branch AND worktree
agentctl worktree list                       # See worktrees
```

Worktrees appear at `/git-worktrees/worktree-<branch>/` inside the container.

## Running Agents in Worktrees

From the host:

```bash
agentbox worktree new superclaude feature-auth    # Create worktree + start agent
```

From inside the container, agents switch themselves:

```bash
agentctl worktree switch feature-auth superclaude   # Switch to worktree, start agent
```

When an agent switches worktrees, it sends a warning to any existing session ("I'm leaving, stop what you're doing") and then moves to the new location.

## Sessions: Multiple Agents, One Container

Sessions are tmux windows inside the container. Each agent runs in its own session. You can have multiple agents working simultaneously.

```bash
agentbox session new superclaude              # Creates superclaude-1
agentbox session new superclaude feature      # Creates superclaude-feature
agentbox session new shell debug              # Shell session for debugging

agentbox session list                         # See all sessions
agentbox session attach superclaude-1         # Jump to that session
agentbox session remove superclaude-1         # Kill a session
```

## The Picture

```
Container: myproject
├── /workspace (main branch)          → session: main-superclaude
├── /git-worktrees/worktree-feature-auth   → session: feature-auth-superclaude
└── /git-worktrees/worktree-bugfix-123     → session: bugfix-123-codex
```

Three agents, three branches, no conflicts. All in one container, all isolated from each other.

## A Typical Workflow

You're working on main, and an idea strikes - a refactoring that would make everything cleaner. But you're in the middle of something else.

```bash
# Create a worktree and start an agent there
agentbox worktree new superclaude refactor-cleanup
```

Now you have two agents: one continuing your current work on main, one exploring the refactoring on a separate branch. They don't interfere.

When the refactoring is done, you merge it normally through git. The worktree is just a checkout - all the normal git operations work.

## Cleaning Up

When you're done with a branch:

```bash
agentbox worktree remove feature-auth    # Delete the worktree
agentbox worktree prune                  # Clean up stale metadata
```

From inside the container:

```bash
agentctl worktree remove feature-auth
agentctl worktree prune
```

You can't remove the main `/workspace` - that's your primary checkout.

## Quick Menu Access

Don't want to remember commands? Use the quick menu:

```bash
agentbox q
```

This shows all sessions and worktrees visually. Press a letter to jump to one. See [Mobile Workflow](06-mobile.md) for more on the quick menu.

## Agent Autonomy

Agents themselves can manage worktrees. If you give Claude a task like "work on feature X and feature Y in parallel," it might:

1. Create worktrees for each feature
2. Switch between them
3. Work on both
4. Merge when ready

The `agentctl` commands and MCP integration let agents orchestrate their own parallel work. You don't have to manage it all manually.

## What's Next

- **[Mobile Workflow](06-mobile.md)** - Manage sessions from your phone
- **[agentctl Reference](REF-C-agentctl.md)** - Container-side CLI details
- **[CLI Reference](REF-A-cli.md)** - All worktree and session commands
