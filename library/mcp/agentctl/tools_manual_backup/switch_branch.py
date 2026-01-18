"""Switch branch tool - Main orchestration for branch switching"""

import os
import subprocess
import json
from typing import Dict, Any, Optional


def get_current_session_info() -> Dict[str, str]:
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
    # Session names like "claude", "codex", "feature-auth-claude"
    if info["name"]:
        for agent in ["claude", "codex", "gemini", "shell"]:
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


def create_worktree(branch: str, create_new: bool) -> tuple[bool, str, str]:
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

        # Parse output to get path (worktree path is /worktree-{sanitized-branch})
        # We can also get it from the worktree list
        worktree_path = get_worktree_for_branch(branch)
        if not worktree_path:
            return False, "", "Failed to find created worktree"

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

        # Get agent command
        agent_commands = {
            "claude": "/usr/local/bin/claude",
            "superclaude": "/usr/local/bin/claude",
            "codex": "/usr/local/bin/codex",
            "supercodex": "/usr/local/bin/codex",
            "gemini": "/usr/local/bin/gemini",
            "supergemini": "/usr/local/bin/gemini",
            "shell": "/bin/bash"
        }
        cmd = agent_commands.get(agent_type, "/usr/local/bin/claude")

        # Create new session in worktree directory
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name, "-c", worktree_path, cmd],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode != 0:
            return False, "", f"Failed to create session: {result.stderr}"

        return True, session_name, ""

    except Exception as e:
        return False, "", str(e)


def get_git_status(worktree_path: str) -> Dict[str, Any]:
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


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Switch to a different git branch

    Creates worktree and spawns session if needed. This is the main
    orchestration tool that agents use to switch branches.

    Args:
        params: {
            "branch": str,                  # Branch name to switch to
            "create_if_missing": bool       # Create branch if not found (default: true)
        }

    Returns:
        {
            "success": true,
            "worktree_path": "/worktree-feature-auth",
            "branch": "feature/auth",
            "old_session": "claude",
            "new_session": "feature-auth-claude",
            "commit": "abc1234",
            "uncommitted_changes": false,
            "ahead_remote": 0,
            "behind_remote": 0,
            "message": "✓ Switched to branch 'feature/auth' in new session..."
        }
    """
    branch = params.get("branch")
    create_if_missing = params.get("create_if_missing", True)

    if not branch:
        return {
            "success": False,
            "error": "branch parameter is required"
        }

    try:
        # Step 1: Get current session info
        current = get_current_session_info()

        # Step 2: Check if branch exists
        local_exists, remote_exists = branch_exists(branch)

        if not local_exists and not remote_exists and not create_if_missing:
            return {
                "success": False,
                "error": f"Branch '{branch}' not found. Set create_if_missing=true to create it."
            }

        # Step 3: Check if worktree exists for branch
        worktree_path = get_worktree_for_branch(branch)

        # Step 4: Create worktree if needed
        if not worktree_path:
            should_create_branch = not local_exists and not remote_exists
            success, worktree_path, error = create_worktree(branch, should_create_branch)

            if not success:
                return {
                    "success": False,
                    "error": f"Failed to create worktree: {error}"
                }

        # Step 5: Spawn new session in worktree
        success, new_session, error = spawn_session_in_worktree(
            worktree_path,
            current["agent_type"] or "claude",
            branch
        )

        if not success:
            return {
                "success": False,
                "error": f"Failed to spawn session: {error}"
            }

        # Step 6: Get git status
        git_status = get_git_status(worktree_path)

        # Step 7: Return rich context
        return {
            "success": True,
            "worktree_path": worktree_path,
            "branch": branch,
            "old_session": current["name"],
            "new_session": new_session,
            **git_status,
            "message": f"✓ Switched to branch '{branch}' in new session '{new_session}'. "
                      f"You are now working in {worktree_path}. "
                      f"Use switch_session('{new_session}') to automatically switch to this session, "
                      f"or continue working in the current session. "
                      f"IMPORTANT: Please re-check the current state of files as the working directory has changed."
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
