"""Get current context tool"""

import os
import subprocess
from typing import Dict, Any, Optional


def get_current_session() -> Optional[str]:
    """Get current tmux session name"""
    # Try from environment variable (set by tmux)
    tmux_env = os.environ.get("TMUX")
    if tmux_env:
        # TMUX env format: /tmp/tmux-1000/default,12345,0
        # Extract session name from tmux display-message
        try:
            result = subprocess.run(
                ["tmux", "display-message", "-p", "#S"],
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except:
            pass
    return None


def get_git_info(cwd: str) -> Dict[str, Any]:
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
        info["commit"] = result.stdout.strip()[:8]  # Short hash

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
        # Not a git repository or git command failed
        pass

    return info


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get current context (session, worktree, branch, git status)

    Returns:
        {
            "success": true,
            "session": "claude",
            "working_directory": "/workspace",
            "worktree_path": "/workspace",
            "is_worktree": false,
            "branch": "main",
            "commit": "abc123",
            "uncommitted_changes": false,
            "recent_commits": [
                "abc123 Fix bug",
                "def456 Add feature"
            ]
        }
    """
    try:
        # Get current session
        session = get_current_session()

        # Get current working directory
        cwd = os.getcwd()

        # Determine if we're in a worktree
        is_worktree = cwd.startswith("/git-worktrees/")
        worktree_path = cwd if is_worktree else "/workspace"

        # Get git information
        git_info = get_git_info(cwd)

        return {
            "success": True,
            "session": session,
            "working_directory": cwd,
            "worktree_path": worktree_path,
            "is_worktree": is_worktree,
            **git_info
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
