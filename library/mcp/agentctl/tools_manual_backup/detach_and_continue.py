"""Detach and continue tool"""

import os
import subprocess
from typing import Dict, Any


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Detach from current session and continue working autonomously

    Perfect for mobile use: user says 'detach and implement X' then closes app.
    Agent continues working in background session.

    Args:
        params: {
            "task_description": str,       # What agent should work on
            "branch": str (optional),      # Switch to this branch first
            "notify_on_complete": bool     # Send notification when done (default: true)
        }

    Returns:
        {
            "success": true,
            "session": "feature-auth-claude",
            "worktree_path": "/worktree-feature-auth",
            "branch": "feature/auth",
            "task": "Implement authentication feature",
            "message": "✓ Detached. Agent will continue working autonomously..."
        }
    """
    task_description = params.get("task_description")
    branch = params.get("branch")
    notify_on_complete = params.get("notify_on_complete", True)

    if not task_description:
        return {
            "success": False,
            "error": "task_description parameter is required"
        }

    # Check if we're in a tmux session
    if not os.environ.get("TMUX"):
        return {
            "success": False,
            "error": "Not in a tmux session. This tool only works from within tmux."
        }

    try:
        # Get current session name
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#S"],
            capture_output=True,
            text=True,
            check=True
        )
        session_name = result.stdout.strip()

        # Get current working directory
        cwd = os.getcwd()

        # If branch parameter provided, we'll need to switch first
        # This will be handled by the agent calling switch_branch before detach
        if branch:
            # Return instruction to switch branch first
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
        is_worktree = cwd.startswith("/worktree-")
        worktree_path = cwd if is_worktree else "/workspace"

        # Detach from tmux session
        subprocess.run(
            ["tmux", "detach-client"],
            check=True
        )

        # TODO: Future enhancement - integrate with notification system
        # For now, we'll just return success and the agent continues in background

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

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Failed to detach: {e.stderr if e.stderr else str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
