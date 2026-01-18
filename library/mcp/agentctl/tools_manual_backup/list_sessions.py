"""List tmux sessions tool"""

import subprocess
import json
from typing import Dict, Any


def execute(params: Dict[str, Any]) -> Dict[str, Any]:
    """List all tmux sessions

    Returns:
        {
            "success": true,
            "sessions": [
                {
                    "name": "claude",
                    "windows": 1,
                    "attached": true,
                    "created": "2026-01-09T10:00:00"
                }
            ]
        }
    """
    try:
        # Call agentctl ls --json
        result = subprocess.run(
            ["agentctl", "ls", "--json"],
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
    except json.JSONDecodeError as e:
        return {
            "success": False,
            "error": f"Failed to parse session data: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
