"""Switch tmux session tool"""

import os
import subprocess
from typing import Dict, Any


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """Automatically switch to a different tmux session

    Args:
        params: {
            "session_name": str  # Name of session to switch to
        }

    Returns:
        {
            "success": true,
            "old_session": "claude",
            "new_session": "feature-auth-claude",
            "working_directory": "/worktree-feature-auth",
            "message": "✓ Switched to session 'feature-auth-claude'"
        }
    """
    session_name = params.get("session_name")

    if not session_name:
        return {
            "success": False,
            "error": "session_name parameter is required"
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
        old_session = result.stdout.strip()

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

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Failed to switch session: {e.stderr if e.stderr else str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
