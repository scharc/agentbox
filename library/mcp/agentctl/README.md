# AgentCtl MCP Server

**Control boxctl sessions and git worktrees from AI agents**

This MCP server exposes boxctl's worktree and session management capabilities to AI agents, enabling them to autonomously switch between git branches, manage tmux sessions, and work on multiple features in parallel.

## Overview

The AgentCtl MCP allows agents to:
- **Switch branches seamlessly** - Just say "switch to feature-branch" and the system handles everything
- **Work on multiple features in parallel** - Each branch gets its own worktree and session
- **Detach and continue autonomously** - Perfect for mobile: "detach and implement X", then close the app
- **Auto-switch between sessions** - Move between different work contexts automatically

## Implementation

**Framework:** Built with [FastMCP](https://github.com/jlowin/fastmcp) (v2.0+)

This server uses the FastMCP framework, which provides:
- ✅ Automatic JSON-RPC protocol handling
- ✅ Built-in error handling and response formatting
- ✅ Type-safe tool definitions with Python decorators
- ✅ Production-ready with 15k+ GitHub stars
- ✅ Comprehensive testing support

**Migration Note:** Migrated from manual MCP implementation to FastMCP on 2026-01-09. The manual implementation is preserved in `server_manual_backup.py` and `tools_manual_backup/` for reference.

**Server File:** `server_fastmcp.py` (662 lines, all-in-one)

## Installation

The AgentCtl MCP is included in boxctl. It's automatically available when you start an agent session.

Configuration file: `library/mcp/agentctl/config.json`

```json
{
  "name": "agentctl",
  "description": "Control boxctl sessions and git worktrees",
  "config": {
    "command": "python3",
    "args": ["server_fastmcp.py"],
    "env": {}
  }
}
```

## Available Tools

### 1. `switch_branch`

**Switch to a different git branch with automatic worktree and session creation.**

When an agent calls this tool, the system:
1. Checks if the branch exists (local or remote)
2. Creates the branch if missing (when `create_if_missing=true`)
3. Creates a worktree at `/worktree-{branch}` if needed
4. Spawns a new tmux session in the worktree
5. Returns rich context about the new environment

**Parameters:**
```typescript
{
  branch: string,              // Required: branch name to switch to
  create_if_missing: boolean,  // Default: true - create branch if not found
  agent: string                // Default: same as current session
                               // Options: "claude", "superclaude", "codex",
                               //          "supercodex", "gemini", "supergemini", "shell"
}
```

**Example Usage:**
```
# Example 1: Default agent (inherits from current session)
Agent: I'll switch to a feature branch to work on authentication.
[Calls switch_branch("feature/authentication")]

Response: {
  success: true,
  worktree_path: "/git-worktrees/worktree-feature-authentication",
  branch: "feature/authentication",
  agent_type: "claude",
  old_session: "claude",
  new_session: "feature-authentication-claude",
  commit: "abc1234",
  uncommitted_changes: false,
  message: "✓ Switched to branch 'feature/authentication' in new 'claude' session..."
}

# Example 2: Explicit agent type
Agent: I'll switch to a shell session for debugging.
[Calls switch_branch("debug-branch", agent="shell")]

Response: {
  success: true,
  worktree_path: "/git-worktrees/worktree-debug-branch",
  branch: "debug-branch",
  agent_type: "shell",
  new_session: "debug-branch-shell",
  message: "✓ Switched to branch 'debug-branch' in new 'shell' session..."
}

Agent: I've created a new worktree for the authentication feature.
Use switch_session("feature-authentication-claude") to move to the new session,
or I can continue working here and switch later.
```

**Return Value:**
```typescript
{
  success: boolean,
  worktree_path: string,        // Path to worktree
  branch: string,               // Branch name
  agent_type: string,           // Agent type used for new session
  old_session: string,          // Previous session name
  new_session: string,          // New session name
  commit: string,               // Current commit (short hash)
  uncommitted_changes: boolean, // Are there uncommitted changes?
  ahead_remote: number,         // Commits ahead of remote
  behind_remote: number,        // Commits behind remote
  message: string              // Human-readable status
}
```

### 2. `switch_session`

**Automatically switch the tmux client to a different session.**

This allows agents to seamlessly move between different work contexts. After calling `switch_branch`, the agent can use this to automatically switch to the new session.

**Parameters:**
```typescript
{
  session_name: string  // Required: name of session to switch to
}
```

**Example Usage:**
```
Agent: I'll switch to the feature-authentication session.
[Calls switch_session("feature-authentication-claude")]

Response: {
  success: true,
  old_session: "claude",
  new_session: "feature-authentication-claude",
  working_directory: "/worktree-feature-authentication",
  message: "✓ Switched to session 'feature-authentication-claude'"
}

Agent: I've switched to the feature-authentication session.
I'm now working in /worktree-feature-authentication.
```

**Return Value:**
```typescript
{
  success: boolean,
  old_session: string,      // Previous session
  new_session: string,      // New session
  working_directory: string, // New working directory
  message: string
}
```

### 3. `detach_and_continue`

**Detach from current session and continue working autonomously.**

Perfect for mobile use cases:
1. User on phone: "Detach and start implementing the authentication feature"
2. Agent detaches, user closes app
3. Agent continues working in background
4. User receives notification when task complete

**Parameters:**
```typescript
{
  task_description: string,     // Required: what agent should work on
  branch?: string,              // Optional: switch to this branch first
  notify_on_complete: boolean   // Default: true - send notification when done
}
```

**Example Usage:**
```
User (on phone): "Detach and start implementing the authentication feature"

Agent: I'll detach and continue working autonomously on the authentication implementation.
[Calls detach_and_continue({
  task_description: "Implement authentication feature",
  notify_on_complete: true
})]

Response: {
  success: true,
  session: "claude",
  task: "Implement authentication feature",
  message: "✓ Detached. Agent will continue working autonomously..."
}

[User closes phone app, agent continues working in background]
[Later: User receives notification when task complete]
```

**Return Value:**
```typescript
{
  success: boolean,
  session: string,          // Current session name
  worktree_path: string,    // Current worktree path
  branch: string,           // Current branch
  task: string,             // Task description
  notify_on_complete: boolean,
  message: string
}
```

### 4. `list_worktrees`

**List all git worktrees with metadata.**

Shows all available branches that have worktrees, along with their paths, commits, and associated tmux sessions.

**Parameters:** None

**Return Value:**
```typescript
{
  success: boolean,
  worktrees: [
    {
      path: string,           // Worktree path
      branch: string,         // Branch name
      commit: string,         // Current commit (short hash)
      sessions: string[],     // Associated tmux sessions
      created?: string        // Creation timestamp (if available)
    }
  ]
}
```

### 5. `list_sessions`

**List all tmux sessions.**

Shows all active agent and shell sessions.

**Parameters:** None

**Return Value:**
```typescript
{
  success: boolean,
  sessions: [
    {
      name: string,         // Session name
      windows: number,      // Number of windows
      attached: boolean,    // Is session attached?
      created: string       // Creation time
    }
  ]
}
```

### 6. `get_current_context`

**Get information about current worktree, branch, and session.**

Provides the agent with full awareness of their current environment.

**Parameters:** None

**Return Value:**
```typescript
{
  success: boolean,
  session: string,              // Current session name (null if not in tmux)
  working_directory: string,    // Current working directory
  worktree_path: string,        // Worktree path
  is_worktree: boolean,         // Are we in a worktree?
  branch: string,               // Current git branch
  commit: string,               // Current commit (short hash)
  uncommitted_changes: boolean, // Are there uncommitted changes?
  recent_commits: string[]      // Last 5 commits
}
```

## Typical Workflows

### Workflow 1: Agent switches to feature branch

```
User: "Let's work on the authentication feature in a separate branch"

Agent: I'll switch to a feature branch for the authentication work.

[Agent calls: switch_branch("feature/authentication", create_if_missing=true)]

System creates:
- New branch "feature/authentication" (if doesn't exist)
- Worktree at /worktree-feature-authentication
- New tmux session "feature-authentication-claude"

Agent: I've switched to the feature/authentication branch in a new worktree.
Use switch_session to move to the new session, or continue here.

[Agent may call: switch_session("feature-authentication-claude")]

Agent now works in isolated environment at /worktree-feature-authentication
Old session continues in /workspace on main branch (parallel work!)
```

### Workflow 2: Mobile detach and continue

```
User (on phone): "Detach and start implementing user registration"

Agent: I'll detach and continue working autonomously.

[Agent calls: detach_and_continue({
  task_description: "Implement user registration feature"
})]

User closes phone app
Agent continues working in background session
Agent implements feature, runs tests, commits changes
User receives notification: "Task complete: Implemented user registration"

User later: abox shell  (reconnects to session)
Agent: I've completed the user registration feature. Here's what I did...
```

### Workflow 3: Parallel work on multiple features

```
Agent 1: [Calls switch_branch("feature/auth")]
→ Works in /worktree-feature-auth

Agent 2: [Calls switch_branch("feature/ui")]
→ Works in /worktree-feature-ui

Agent 3: [Stays in main]
→ Works in /workspace (main branch)

All three agents work simultaneously on different branches!
```

## Architecture

### File Structure

```
library/mcp/agentctl/
├── config.json              # MCP server configuration
├── server.py                # MCP protocol implementation
├── tools/                   # Tool implementations
│   ├── __init__.py
│   ├── switch_branch.py     # Branch switching orchestration
│   ├── switch_session.py    # Session switching
│   ├── detach_and_continue.py  # Detach and autonomous work
│   ├── list_worktrees.py    # Worktree listing
│   ├── list_sessions.py     # Session listing
│   └── get_context.py       # Current context
└── README.md                # This file
```

### Integration with boxctl

The MCP integrates with existing boxctl infrastructure:

1. **Worktree Management**: Uses `boxctl.agentctl.worktree` commands
   - `agentctl worktree add` - Create worktrees
   - `agentctl worktree list` - List worktrees
   - Metadata tracking in `.boxctl/worktrees.json`

2. **Session Management**: Uses `agentctl` CLI commands
   - `agentctl a <agent>` - Spawn sessions (now with dynamic working directories)
   - `agentctl ls` - List sessions
   - `agentctl d` - Detach client

3. **Dynamic Working Directories**:
   - Modified `boxctl/agentctl/cli.py` to detect worktree directories
   - Sessions spawned in worktrees use worktree path
   - Sessions in /workspace use /workspace

### Worktree Persistence

**Important**: Worktrees are filesystem directories, not stored in git.

**What persists:**
- ✅ Git branches (if pushed to remote)
- ✅ Commits in those branches
- ✅ File contents

**What doesn't persist:**
- ❌ Worktree directory itself
- ❌ Worktree location on disk
- ❌ Which worktrees you have checked out

**Container worktrees** (created at `/worktree-*`):
- Lost on container rebuild/restart
- Branches are safe in git (if pushed)
- Recreate worktree in 1 second: `agentctl worktree add <branch>`

**Recovery after rebuild:**
```bash
Container rebuilt → Worktrees gone, but branches still in git
Agent: "Switch to feature-auth"
System: Creates /worktree-feature-auth (1 second)
Agent continues working → All commits still there!
```

## Development

### Running Tests

```bash
# Run all MCP tests
pytest tests/test_mcp_agentctl/ -v

# Run specific test file
pytest tests/test_mcp_agentctl/test_mcp_server.py -v
```

### Test Coverage

- ✅ MCP protocol compliance (initialize, tools/list, tools/call)
- ✅ Tool schema validation
- ✅ Error handling (unknown methods, unknown tools)
- ✅ Tool execution through MCP
- ✅ List worktrees functionality
- ✅ List sessions functionality
- ✅ Get context functionality

### Adding New Tools

1. Create tool implementation in `tools/<tool_name>.py`
2. Implement `execute(params: Dict[str, Any]) -> Dict[str, Any]` function
3. Add tool to `tools/__init__.py`
4. Add tool definition in `server.py` (tools/list method)
5. Add tool routing in `server.py` (tools/call method)
6. Write tests in `tests/test_mcp_agentctl/`

## Troubleshooting

### Tool returns "Not in a tmux session"

Some tools (`switch_session`, `detach_and_continue`) require being in a tmux session.
- Make sure you're running the agent inside boxctl: `abox claude`

### "Branch not found" error

The branch doesn't exist locally or remotely.
- Set `create_if_missing: true` to auto-create the branch
- Or create the branch manually: `git checkout -b <branch>`

### Worktree creation fails

Possible causes:
- Directory already exists at `/worktree-<branch>`
- Branch is already checked out in another worktree
- Not in a git repository

Solutions:
- Remove existing worktree: `agentctl worktree remove <branch>`
- Use different branch name
- Check git status

### Session spawn fails

Possible causes:
- Session name already exists
- Working directory doesn't exist
- Agent command not found

Solutions:
- Use different session name
- Verify worktree exists: `agentctl worktree list`
- Check agent installation: `which claude`

## Future Enhancements

Potential additions (not in current MVP):

- **Notification System Integration**: Send desktop/mobile notifications when tasks complete
- **Task State Persistence**: Save agent task state across container rebuilds
- **Background Workers**: Spawn autonomous agents for specific tasks
- **Session Output Streaming**: Monitor other sessions in real-time
- **Checkpoint System**: Save/restore session state
- **Host-Persistent Worktrees**: Option to create worktrees on host filesystem

## See Also

- [Git Worktrees Quick Start](/workspace/WORKTREE_QUICKSTART.md)
- [Worktree Implementation Roadmap](/workspace/WORKTREE_IMPLEMENTATION_ROADMAP.md)
- [AgentCtl CLI Documentation](/workspace/boxctl/agentctl/)
- [MCP Specification](https://modelcontextprotocol.io/)

## License

Part of the boxctl project.
