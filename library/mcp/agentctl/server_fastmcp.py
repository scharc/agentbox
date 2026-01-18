#!/usr/bin/env python3
"""AgentCtl MCP Server (FastMCP Implementation)

Expose agentctl functionality to AI agents using the FastMCP framework.
This provides worktree management, session switching, and autonomous agent operations.
"""

import os
import subprocess
import json
from typing import Optional
from fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP(
    name="agentctl",
    instructions="AgentCtl MCP server for git worktree and tmux session management"
)


# ============================================================================
# Helper Functions
# ============================================================================

def get_current_session_info() -> dict:
    """Get current session information"""
    info = {
        "name": None,
        "agent_type": None,
        "working_dir": None
    }

    # Get session name
    if os.environ.get("TMUX"):
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=True
            )
            info["name"] = result.stdout.strip()
        except:
            pass

    # Infer agent type from session name
    # Check for super variants first (longer strings first for proper matching)
    if info["name"]:
        for agent in ["superclaude", "supercodex", "supergemini", "claude", "codex", "gemini", "shell"]:
            if agent in info["name"]:
                info["agent_type"] = agent
                break
        if not info["agent_type"]:
            info["agent_type"] = "claude"  # Default

    # Get current working directory
    info["working_dir"] = os.getcwd()

    return info


def branch_exists(branch: str) -> tuple[bool, bool]:
    """Check if branch exists locally or remotely

    Returns:
        (exists_locally, exists_remotely)
    """
    local = False
    remote = False

    # Check local
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", f"refs/heads/{branch}"],
            capture_output=True,
            check=False
        )
        local = result.returncode == 0
    except:
        pass

    # Check remote
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", "origin", branch],
            capture_output=True,
            text=True,
            check=False
        )
        remote = bool(result.stdout.strip())
    except:
        pass

    return local, remote


def get_worktree_for_branch(branch: str) -> Optional[str]:
    """Check if worktree exists for branch

    Returns:
        Worktree path if exists, None otherwise
    """
    try:
        result = subprocess.run(
            ["agentctl", "worktree", "list", "--json"],
            capture_output=True,
            text=True,
            check=True
        )

        data = json.loads(result.stdout)
        worktrees = data.get("worktrees", [])

        for wt in worktrees:
            if wt.get("branch") == branch:
                return wt.get("path")

    except:
        pass

    return None


def setup_worktree_configs(worktree_path: str) -> tuple[bool, str]:
    """Setup .agentbox for worktree with symlinks to shared configs

    Creates symlinks to shared config files in /workspace/.agentbox and
    creates local state directories for session-specific data.

    Args:
        worktree_path: Path to the worktree

    Returns:
        (success, error_message)
    """
    try:
        # Source and destination paths
        source_agentbox = "/workspace/.agentbox"
        dest_agentbox = f"{worktree_path}/.agentbox"

        # Skip if already configured
        if os.path.exists(f"{dest_agentbox}/claude/mcp.json"):
            return True, ""

        # Create directory structure
        os.makedirs(f"{dest_agentbox}/claude", exist_ok=True)

        # Symlink shared config files to single source of truth
        symlinks = [
            ("claude/mcp.json", f"{dest_agentbox}/claude/mcp.json"),
            ("claude/config.json", f"{dest_agentbox}/claude/config.json"),
            ("claude/config-super.json", f"{dest_agentbox}/claude/config-super.json"),
            ("skills", f"{dest_agentbox}/skills"),
            ("config.json", f"{dest_agentbox}/config.json"),
            ("mcp-meta.json", f"{dest_agentbox}/mcp-meta.json"),
            (".gitignore", f"{dest_agentbox}/.gitignore"),
        ]

        for source_rel, dest in symlinks:
            source = f"{source_agentbox}/{source_rel}"
            if os.path.exists(source) and not os.path.exists(dest):
                os.symlink(source, dest)

        # Create local state directories (isolated per worktree)
        state_dirs = [
            f"{dest_agentbox}/claude/todos",
            f"{dest_agentbox}/claude/telemetry",
            f"{dest_agentbox}/claude/debug",
            f"{dest_agentbox}/claude/file-history",
            f"{dest_agentbox}/claude/plans",
            f"{dest_agentbox}/claude/projects",
            f"{dest_agentbox}/claude/shell-snapshots",
            f"{dest_agentbox}/claude/statsig",
        ]

        for dir_path in state_dirs:
            os.makedirs(dir_path, exist_ok=True)

        return True, ""

    except Exception as e:
        return False, f"Failed to setup worktree configs: {str(e)}"


def create_worktree_helper(branch: str, create_new: bool) -> tuple[bool, str, str]:
    """Create worktree for branch

    Args:
        branch: Branch name
        create_new: Whether to create new branch if it doesn't exist

    Returns:
        (success, path, error_message)
    """
    try:
        cmd = ["agentctl", "worktree", "add", branch]
        if create_new:
            cmd.append("--create")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return False, "", result.stderr

        # Get the created worktree path
        worktree_path = get_worktree_for_branch(branch)
        if not worktree_path:
            return False, "", "Failed to find created worktree"

        # Setup configs for the worktree
        success, error = setup_worktree_configs(worktree_path)
        if not success:
            return False, worktree_path, error

        return True, worktree_path, ""

    except Exception as e:
        return False, "", str(e)


def spawn_session_in_worktree(worktree_path: str, agent_type: str, branch: str) -> tuple[bool, str, str]:
    """Spawn a new tmux session in the worktree

    Args:
        worktree_path: Path to worktree
        agent_type: Type of agent (claude, codex, etc.)
        branch: Branch name (for session naming)

    Returns:
        (success, session_name, error_message)
    """
    try:
        # Sanitize branch name for session name
        sanitized_branch = branch.replace("/", "-").replace(".", "-")
        session_name = f"{sanitized_branch}-{agent_type}"

        # Check if session already exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            check=False
        )

        if result.returncode == 0:
            # Session already exists, just return it
            return True, session_name, ""

        # Determine MCP config path - use worktree-specific config if it exists, otherwise use main
        mcp_config = f"{worktree_path}/.agentbox/claude/mcp.json"
        if not os.path.exists(mcp_config):
            mcp_config = "/workspace/.agentbox/claude/mcp.json"

        # Get agent command with proper configuration flags
        agent_commands = {
            "claude": f"/usr/local/bin/claude --settings /home/abox/.claude/config.json --mcp-config {mcp_config}",
            "superclaude": f"/usr/local/bin/claude --settings /home/abox/.claude/config-super.json --mcp-config {mcp_config} --dangerously-skip-permissions",
            "codex": "/usr/local/bin/codex",
            "supercodex": "/usr/local/bin/codex --dangerously-bypass-approvals-and-sandbox",
            "gemini": "/usr/local/bin/gemini",
            "supergemini": "/usr/local/bin/gemini --non-interactive",
            "shell": "/bin/bash"
        }
        command = agent_commands.get(agent_type, "/usr/local/bin/claude")

        # Preserve SSH_AUTH_SOCK for SSH agent forwarding in new sessions
        ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
        if ssh_auth_sock:
            # Set SSH_AUTH_SOCK in tmux global environment
            subprocess.run(
                ["tmux", "set-environment", "-g", "SSH_AUTH_SOCK", ssh_auth_sock],
                capture_output=True,
                check=False
            )

        # Create new session in worktree directory
        # Use /bin/bash -lc to ensure shell configuration and environment are sourced
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-c", worktree_path, "/bin/bash", "-lc", command],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return False, "", f"Failed to create session: {result.stderr}"

        return True, session_name, ""

    except Exception as e:
        return False, "", str(e)


def get_git_status(worktree_path: str) -> dict:
    """Get git status for worktree

    Returns:
        Dict with commit, uncommitted_changes, ahead, behind
    """
    status = {
        "commit": None,
        "uncommitted_changes": False,
        "ahead_remote": 0,
        "behind_remote": 0
    }

    try:
        # Get current commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=True
        )
        status["commit"] = result.stdout.strip()[:8]

        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=True
        )
        status["uncommitted_changes"] = bool(result.stdout.strip())

        # Check ahead/behind (this might fail if no upstream)
        try:
            result = subprocess.run(
                ["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
                cwd=worktree_path,
                capture_output=True,
                text=True,
                check=True
            )
            parts = result.stdout.strip().split()
            if len(parts) == 2:
                status["ahead_remote"] = int(parts[0])
                status["behind_remote"] = int(parts[1])
        except:
            pass

    except:
        pass

    return status


def get_git_info(cwd: str) -> dict:
    """Get git repository information

    Args:
        cwd: Working directory to check

    Returns:
        Dict with branch, commit, uncommitted_changes, recent_commits
    """
    info = {
        "branch": None,
        "commit": None,
        "uncommitted_changes": False,
        "recent_commits": []
    }

    try:
        # Get current branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        info["branch"] = result.stdout.strip()

        # Get current commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        info["commit"] = result.stdout.strip()[:8]

        # Check for uncommitted changes
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        info["uncommitted_changes"] = bool(result.stdout.strip())

        # Get recent commits (last 5)
        result = subprocess.run(
            ["git", "log", "-5", "--oneline"],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        info["recent_commits"] = result.stdout.strip().splitlines()

    except subprocess.CalledProcessError:
        pass

    return info


# ============================================================================
# MCP Tools
# ============================================================================

@mcp.tool()
def switch_branch(
    branch: str,
    create_if_missing: bool = True,
    agent: Optional[str] = None
) -> dict:
    """Switch to work on a different git branch in an isolated environment.

    This tool creates a new git worktree for the branch (if needed) and spawns a new
    tmux session there. This allows working on multiple branches in parallel without
    conflicts. The new session will have the same agent type as the current session
    unless explicitly overridden.

    IMPORTANT: This tool CREATES the session but does NOT switch to it. You MUST call
    switch_session() afterwards to actually move into the new environment.

    Natural language triggers - use this tool when the user says:
    - "send me to <branch/feature>" or "go to <branch>"
    - "switch to <branch>" or "work on <feature>"
    - "create a session for <branch/agent>"
    - "open <agent> on <branch>" or "start <agent> session"
    - "I want to work on <feature>" or "let's work on <branch>"

    When to use: When you need to work on a different branch or feature in parallel.

    Args:
        branch: Name of the git branch to switch to (e.g., "feature/new-api")
        create_if_missing: If true, creates a new branch if it doesn't exist locally
                          or remotely (default: true)
        agent: Override the agent type for the new session. Options:
               - "claude": Standard Claude agent (requires approvals)
               - "superclaude": Auto-approve Claude agent (autonomous)
               - "codex", "supercodex": Alternative agents
               - "gemini", "supergemini": Alternative agents
               - "shell": Plain bash shell
               If not specified, uses the same agent type as current session.

    Returns:
        Dict with worktree_path, new_session name, branch, agent_type, and git status.
        Contains detailed message about next steps (calling switch_session).
    """
    try:
        # Step 1: Get current session info
        current = get_current_session_info()

        # Step 2: Determine which agent to use
        # Priority: explicit agent parameter > current agent type > default to claude
        if agent:
            agent_type = agent
        elif current["agent_type"]:
            agent_type = current["agent_type"]
        else:
            agent_type = "claude"

        # Validate agent type
        valid_agents = ["claude", "superclaude", "codex", "supercodex",
                       "gemini", "supergemini", "shell"]
        if agent_type not in valid_agents:
            return {
                "success": False,
                "error": f"Invalid agent type '{agent_type}'. Valid options: {', '.join(valid_agents)}"
            }

        # Step 3: Check if branch exists
        local_exists, remote_exists = branch_exists(branch)

        if not local_exists and not remote_exists and not create_if_missing:
            return {
                "success": False,
                "error": f"Branch '{branch}' not found. Set create_if_missing=true to create it."
            }

        # Step 4: Check if worktree exists for branch
        worktree_path = get_worktree_for_branch(branch)

        # Step 5: Create worktree if needed
        if not worktree_path:
            should_create_branch = not local_exists and not remote_exists
            success, worktree_path, error = create_worktree_helper(branch, should_create_branch)

            if not success:
                return {
                    "success": False,
                    "error": f"Failed to create worktree: {error}"
                }
        else:
            # Worktree exists, ensure it has proper configs
            success, error = setup_worktree_configs(worktree_path)
            if not success:
                # Non-fatal, log but continue
                pass

        # Step 6: Spawn new session in worktree
        success, new_session, error = spawn_session_in_worktree(
            worktree_path,
            agent_type,
            branch
        )

        if not success:
            return {
                "success": False,
                "error": f"Failed to spawn session: {error}"
            }

        # Step 7: Get git status
        git_status = get_git_status(worktree_path)

        # Step 8: Return rich context
        return {
            "success": True,
            "worktree_path": worktree_path,
            "branch": branch,
            "agent_type": agent_type,
            "old_session": current["name"],
            "new_session": new_session,
            **git_status,
            "message": f"✓ Created new '{agent_type}' session '{new_session}' for branch '{branch}' at {worktree_path}. "
                      f"\n\n"
                      f"⚠️  IMPORTANT: You are STILL in the OLD session '{current['name']}' at {current['working_dir']}. "
                      f"The new session has been CREATED but you have NOT switched to it yet. "
                      f"\n\n"
                      f"DO NOT work on files yet! You must call switch_session('{new_session}') first to move to the new environment. "
                      f"After switching, you will be in the new worktree with the correct branch checked out."
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def switch_session(session_name: str) -> dict:
    """Actually switch the agent into a different tmux session and working directory.

    This is the second step after switch_branch(). Calling this tool moves the agent's
    execution context into the new session, changing the working directory and environment.
    After calling this, all file operations will happen in the new worktree.

    Natural language triggers - use this tool when the user says:
    - "send me to <session>" or "go to <session>"
    - "switch to <session>" or "move to <session>"
    - "take me to <session>" or "jump to <session>"
    - "attach to <session>" or "connect to <session>"

    When to use: Immediately after switch_branch() to complete the branch switch, or
    anytime you need to move between existing sessions.

    Args:
        session_name: Name of the tmux session to switch to (get this from switch_branch
                      response or list_sessions)

    Returns:
        Dict with old_session, new_session, working_directory, and success status.
    """
    try:
        old_session = None

        # Try TMUX env var first (if running inside tmux)
        if os.environ.get("TMUX"):
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=True
            )
            old_session = result.stdout.strip()
        else:
            # MCP server runs as daemon, query tmux directly for attached session
            old_session, _ = _get_active_tmux_session()

        if not old_session:
            return {
                "success": False,
                "error": "Not in a tmux session. This tool only works from within tmux."
            }

        # Check if target session exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            check=False
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Session '{session_name}' does not exist. Use list_sessions to see available sessions."
            }

        # Get working directory of target session
        result = subprocess.run(
            ["tmux", "display-message", "-p", "-t", session_name, "#{pane_current_path}"],
            capture_output=True,
            text=True,
            check=True
        )
        working_directory = result.stdout.strip()

        # Switch to target session
        subprocess.run(
            ["tmux", "switch-client", "-t", session_name],
            check=True
        )

        return {
            "success": True,
            "old_session": old_session,
            "new_session": session_name,
            "working_directory": working_directory,
            "message": f"✓ Switched to session '{session_name}'. You are now in {working_directory}."
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def detach_and_continue(task_description: str, branch: Optional[str] = None, notify_on_complete: bool = True) -> dict:
    """Detach from the current session so the agent continues working in the background.

    This disconnects the user's terminal from the tmux session while the agent keeps
    running autonomously. Perfect for long-running tasks or mobile use - the user can
    close their app and the agent will continue working and notify when complete.

    When to use: When starting a long task that should continue even if the user
    disconnects, or when working on mobile and need to close the app.

    IMPORTANT: If you want to switch branches first, call switch_branch and switch_session
    BEFORE calling this tool. Do not use the branch parameter.

    Args:
        task_description: Brief description of what you'll work on (used for logging/notifications)
        branch: DEPRECATED - do not use. Call switch_branch separately instead.
        notify_on_complete: If true, sends desktop notification when task completes (default: true)

    Returns:
        Dict with session name, worktree_path, branch, task description, and reconnect command.
    """
    try:
        session_name = None
        cwd = None

        # Try TMUX env var first (if running inside tmux)
        if os.environ.get("TMUX"):
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=True
            )
            session_name = result.stdout.strip()

            # Get working directory from tmux pane
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#{pane_current_path}"],
                capture_output=True,
                text=True,
                check=True
            )
            cwd = result.stdout.strip()
        else:
            # MCP server runs as daemon, query tmux directly for attached session
            session_name, cwd = _get_active_tmux_session()

        if not session_name:
            return {
                "success": False,
                "error": "Not in a tmux session. This tool only works from within tmux."
            }

        # Fallback for working directory
        if not cwd:
            cwd = os.getcwd()

        # If branch parameter provided, suggest switching first
        if branch:
            return {
                "success": False,
                "error": f"Please call switch_branch('{branch}') first, then call detach_and_continue again without the branch parameter.",
                "suggestion": f"Use switch_branch tool with branch='{branch}', then call detach_and_continue"
            }

        # Get current git info
        git_branch = None
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            git_branch = result.stdout.strip()
        except:
            pass

        # Determine worktree path
        is_worktree = cwd.startswith("/git-worktrees/")
        worktree_path = cwd if is_worktree else "/workspace"

        # Detach from tmux session
        subprocess.run(
            ["tmux", "detach-client"],
            check=True
        )

        reconnect_command = f"abox shell {session_name}" if session_name != "claude" else "abox shell"

        return {
            "success": True,
            "session": session_name,
            "worktree_path": worktree_path,
            "branch": git_branch,
            "task": task_description,
            "notify_on_complete": notify_on_complete,
            "message": f"✓ Detached. Agent will continue working autonomously on '{task_description}'. "
                      f"You'll receive a notification when complete. "
                      f"Reconnect anytime with: {reconnect_command}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def list_worktrees() -> dict:
    """List all git worktrees (separate checkouts of different branches).

    Each worktree is an independent checkout of a specific branch, allowing you to
    work on multiple branches simultaneously without switching. This shows all existing
    worktrees with their paths, branches, commits, and creation times.

    When to use: To see what branches already have worktrees before calling switch_branch,
    or to find the path of an existing worktree.

    Returns:
        Dict with "worktrees" list, where each worktree has path, branch, commit,
        sessions (list of tmux sessions in that worktree), and created timestamp.
    """
    try:
        # Call agentctl worktree list --json
        result = subprocess.run(
            ["agentctl", "worktree", "list", "--json"],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse JSON output
        data = json.loads(result.stdout)

        return {
            "success": True,
            **data  # Includes "worktrees" key
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Failed to list worktrees: {e.stderr}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def create_worktree(branch: str, create_branch: bool = False) -> dict:
    """Create a git worktree for a branch without switching to it.

    Creates an isolated checkout of the specified branch in a separate directory.
    This is useful for preparing a worktree in advance or for background operations.
    Unlike switch_branch, this does NOT create a tmux session or switch context.

    When to use: When you want to prepare a worktree for later use, or when another
    agent/process will work in that worktree.

    Args:
        branch: Name of the git branch to create a worktree for
        create_branch: If true, creates a new branch if it doesn't exist (default: false)

    Returns:
        Dict with worktree_path, branch, commit, and success status.
    """
    try:
        # Check if worktree already exists for this branch
        existing_path = get_worktree_for_branch(branch)
        if existing_path:
            # Ensure configs are set up (may have been created without them)
            setup_worktree_configs(existing_path)
            # Get git status for existing worktree
            git_status = get_git_status(existing_path)
            return {
                "success": True,
                "worktree_path": existing_path,
                "branch": branch,
                "already_existed": True,
                **git_status,
                "message": f"Worktree for branch '{branch}' already exists at {existing_path}"
            }

        # Check if branch exists
        local_exists, remote_exists = branch_exists(branch)

        if not local_exists and not remote_exists and not create_branch:
            return {
                "success": False,
                "error": f"Branch '{branch}' not found locally or remotely. Set create_branch=true to create it."
            }

        # Create the worktree
        should_create_branch = not local_exists and not remote_exists
        success, worktree_path, error = create_worktree_helper(branch, should_create_branch)

        if not success:
            return {
                "success": False,
                "error": f"Failed to create worktree: {error}"
            }

        # Get git status
        git_status = get_git_status(worktree_path)

        return {
            "success": True,
            "worktree_path": worktree_path,
            "branch": branch,
            "already_existed": False,
            **git_status,
            "message": f"Created worktree for branch '{branch}' at {worktree_path}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def list_sessions() -> dict:
    """List all tmux sessions (running agent instances).

    Each tmux session represents a running agent instance. This shows all active
    sessions with their names, window counts, and attachment status. Session names
    typically follow the pattern: {branch}-{agent-type} (e.g., "main-superclaude").

    When to use: To see what sessions exist before calling switch_session, or to
    find which sessions are currently running.

    Returns:
        Dict with "sessions" list, where each session has name, windows (count),
        attached (boolean), and created timestamp.
    """
    try:
        # Call agentctl list --json
        result = subprocess.run(
            ["agentctl", "list", "--json"],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse JSON output
        data = json.loads(result.stdout)

        return {
            "success": True,
            **data  # Includes "sessions" key
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Failed to list sessions: {e.stderr}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def _get_active_tmux_session() -> tuple:
    """Get the active tmux session and its working directory.

    Since the MCP server runs as a daemon, it doesn't have TMUX env var.
    Instead, we find the attached session by querying tmux directly.

    Returns:
        Tuple of (session_name, working_directory) or (None, None) if not found.
    """
    try:
        # List all sessions and find one that's attached
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}:#{session_attached}"],
            capture_output=True,
            text=True,
            check=True
        )

        session = None
        for line in result.stdout.strip().split("\n"):
            if line:
                parts = line.split(":")
                if len(parts) >= 2 and parts[1] == "1":
                    session = parts[0]
                    break

        if not session:
            return None, None

        # Get the working directory from the active pane
        result = subprocess.run(
            ["tmux", "display-message", "-t", session, "-p", "#{pane_current_path}"],
            capture_output=True,
            text=True,
            check=True
        )
        working_directory = result.stdout.strip()

        return session, working_directory

    except Exception:
        return None, None


@mcp.tool()
def set_session_task(task: str) -> dict:
    """Set a task label on the current tmux session name.

    Appends a task description to the session name to help identify what the agent
    is working on. The base session name (branch-agent) is preserved, with the task
    appended after @_ delimiter.

    Example: "main-superclaude" -> "main-superclaude@_auth-feature"

    Natural language triggers - use this tool when the user says:
    - "work on <task>" or "I'm working on <task>"
    - "start <task>" or "begin <task>"
    - "focus on <task>" or "let's do <task>"
    - "label this <task>" or "tag this session"

    When to use: When starting work on a specific task, to help users identify
    what each session is doing at a glance.

    Args:
        task: Short task description (will be sanitized - spaces become dashes,
              max 30 chars). Use descriptive names like "auth-feature", "fix-bug-123",
              "refactor-api".

    Returns:
        Dict with old_name, new_name, and success status.
    """
    try:
        # Get current session info
        session = None

        if os.environ.get("TMUX"):
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=True
            )
            session = result.stdout.strip()
        else:
            # MCP server runs as daemon, find attached session
            session, _ = _get_active_tmux_session()

        if not session:
            return {
                "success": False,
                "error": "Could not determine current tmux session"
            }

        # Extract base name (remove any existing task suffix)
        base_name = session.split("@_")[0]

        # Sanitize task label
        sanitized_task = task.strip()
        sanitized_task = sanitized_task.replace(" ", "-")
        sanitized_task = sanitized_task.replace("/", "-")
        sanitized_task = sanitized_task.replace(".", "-")
        sanitized_task = sanitized_task.replace(":", "-")
        sanitized_task = sanitized_task.replace("@", "-")
        sanitized_task = sanitized_task[:30]  # Max 30 chars

        # Build new session name
        new_name = f"{base_name}@_{sanitized_task}" if sanitized_task else base_name

        # Rename the session
        result = subprocess.run(
            ["tmux", "rename-session", "-t", session, new_name],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to rename session: {result.stderr}"
            }

        return {
            "success": True,
            "old_name": session,
            "new_name": new_name,
            "base_name": base_name,
            "task": sanitized_task,
            "message": f"Session renamed: {session} -> {new_name}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def clear_session_task() -> dict:
    """Remove the task label from the current session name.

    Reverts the session name back to its base form (branch-agent).

    Example: "main-superclaude@_auth-feature" -> "main-superclaude"

    Natural language triggers - use this tool when the user says:
    - "done with this task" or "finished with <task>"
    - "clear the task" or "clear session label"
    - "move on" or "next task"
    - "reset session name" or "remove task label"

    When to use: When finishing a task and moving to something else, or to
    clean up the session name.

    Returns:
        Dict with old_name, new_name, and success status.
    """
    try:
        # Get current session info
        session = None

        if os.environ.get("TMUX"):
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=True
            )
            session = result.stdout.strip()
        else:
            # MCP server runs as daemon, find attached session
            session, _ = _get_active_tmux_session()

        if not session:
            return {
                "success": False,
                "error": "Could not determine current tmux session"
            }

        # Extract base name (remove any existing task suffix)
        base_name = session.split("@_")[0]

        # If no task suffix, nothing to do
        if "@_" not in session:
            return {
                "success": True,
                "old_name": session,
                "new_name": session,
                "message": "Session has no task label to clear"
            }

        # Rename the session back to base
        result = subprocess.run(
            ["tmux", "rename-session", "-t", session, base_name],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Failed to rename session: {result.stderr}"
            }

        return {
            "success": True,
            "old_name": session,
            "new_name": base_name,
            "message": f"Task label cleared: {session} -> {base_name}"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@mcp.tool()
def get_current_context() -> dict:
    """Get complete information about where the agent is currently working.

    Returns the current tmux session name, working directory, git branch, commit hash,
    whether you're in a worktree, and if there are uncommitted changes. Use this to
    understand your current environment before making changes.

    When to use: At the start of a task, after switching sessions, or when you need
    to verify which branch/worktree you're in.

    Returns:
        Dict with session, working_directory, worktree_path, is_worktree, branch,
        commit, uncommitted_changes, and recent_commits.
    """
    try:
        session = None
        working_directory = None

        # Get current session and working directory from tmux
        # Try TMUX env var first (if running inside tmux), then query tmux directly
        if os.environ.get("TMUX"):
            try:
                # Get session name
                result = subprocess.run(
                    ["tmux", "display-message", "-p", "#S"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                session = result.stdout.strip()

                # Get actual working directory from tmux pane
                # This returns the real cwd of the agent's shell, not the MCP server's cwd
                result = subprocess.run(
                    ["tmux", "display-message", "-p", "#{pane_current_path}"],
                    capture_output=True,
                    text=True,
                    check=True
                )
                working_directory = result.stdout.strip()
            except:
                pass
        else:
            # MCP server runs as daemon, query tmux directly for attached session
            session, working_directory = _get_active_tmux_session()

        # Fallback to /workspace if not in tmux or tmux query failed
        if not working_directory:
            # Try /workspace first (standard agentbox location), then fall back to process cwd
            if os.path.isdir("/workspace") and os.path.isdir("/workspace/.git"):
                working_directory = "/workspace"
            else:
                working_directory = os.getcwd()

        # Determine if we're in a worktree
        is_worktree = working_directory.startswith("/git-worktrees/")
        worktree_path = working_directory if is_worktree else "/workspace"

        # Get git information from the actual working directory
        git_info = get_git_info(working_directory)

        return {
            "success": True,
            "session": session,
            "working_directory": working_directory,
            "worktree_path": worktree_path,
            "is_worktree": is_worktree,
            **git_info
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AgentCtl MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="Transport mode: stdio (default) or sse"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "9100")),
        help="Port for SSE transport (default: 9100)"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="Host for SSE transport (default: 127.0.0.1)"
    )

    args = parser.parse_args()

    if args.transport == "sse":
        # Run with SSE transport for pre-started server mode
        mcp.run(transport="sse", host=args.host, port=args.port, show_banner=False)
    else:
        # Default stdio transport (spawned by client)
        mcp.run()
