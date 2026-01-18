"""List git worktrees tool"""

import subprocess
import json
from typing import Dict, Any


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """List all git worktrees with metadata

    Returns:
        {
            "success": true,
            "worktrees": [
                {
                    "path": "/workspace",
                    "branch": "main",
                    "commit": "abc123",
                    "sessions": ["claude"],
                    "created": "2026-01-09T10:00:00"
                }
            ]
        }
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
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse worktree data: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
