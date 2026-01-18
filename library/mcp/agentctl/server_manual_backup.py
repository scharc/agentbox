#!/usr/bin/env python3
"""AgentCtl MCP Server - Expose agentctl functionality to AI agents"""

import sys
import json
import os
import logging
from datetime import datetime

# Set up file logging
log_file = "/tmp/agentctl-mcp.log"
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

logger.info("="*60)
logger.info("AgentCtl MCP Server Starting")
logger.info(f"Log file: {log_file}")
logger.info(f"Python: {sys.version}")
logger.info(f"Working dir: {os.getcwd()}")
logger.info("="*60)

# Add agentbox to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
logger.debug(f"Added to path: {sys.path[0]}")

from tools import (
    switch_branch,
    switch_session,
    detach_and_continue,
    list_worktrees,
    list_sessions,
    get_context
)


def handle_request(request: dict) -> dict:
    """Handle MCP protocol requests"""
    method = request.get("method")
    logger.debug(f"Handling request: method={method}, id={request.get('id')}")

    if method == "initialize":
        logger.info("Processing initialize request")
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "agentctl",
                "version": "0.1.0"
            },
            "capabilities": {
                "tools": {}
            }
        }

    elif method == "tools/list":
        logger.info("Processing tools/list request")
        return {
            "tools": [
                {
                    "name": "switch_branch",
                    "description": "Switch to a different git branch. Creates a new worktree and spawns a session there if the branch doesn't have one yet.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "branch": {
                                "type": "string",
                                "description": "Name of the branch to switch to"
                            },
                            "create_if_missing": {
                                "type": "boolean",
                                "description": "Create the branch if it doesn't exist (default: true)"
                            }
                        },
                        "required": ["branch"]
                    }
                },
                {
                    "name": "switch_session",
                    "description": "Automatically switch to a different tmux session. Agent can seamlessly move to another session.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "session_name": {
                                "type": "string",
                                "description": "Name of the tmux session to switch to"
                            }
                        },
                        "required": ["session_name"]
                    }
                },
                {
                    "name": "detach_and_continue",
                    "description": "Detach from current session and continue working autonomously. Perfect for mobile use: user says 'detach and implement X' then closes app.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "task_description": {
                                "type": "string",
                                "description": "What the agent should work on after detaching"
                            },
                            "branch": {
                                "type": "string",
                                "description": "Optional: switch to this branch first"
                            },
                            "notify_on_complete": {
                                "type": "boolean",
                                "description": "Send notification when task complete (default: true)"
                            }
                        },
                        "required": ["task_description"]
                    }
                },
                {
                    "name": "list_worktrees",
                    "description": "List all git worktrees (checked-out branches)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "list_sessions",
                    "description": "List all tmux sessions",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                },
                {
                    "name": "get_current_context",
                    "description": "Get information about current worktree, branch, and session",
                    "inputSchema": {
                        "type": "object",
                        "properties": {}
                    }
                }
            ]
        }

    elif method == "tools/call":
        tool_name = request.get("params", {}).get("name")
        arguments = request.get("params", {}).get("arguments", {})
        logger.info(f"Processing tools/call: tool={tool_name}, args={arguments}")

        try:
            if tool_name == "switch_branch":
                result = switch_branch.execute(arguments)
            elif tool_name == "switch_session":
                result = switch_session.execute(arguments)
            elif tool_name == "detach_and_continue":
                result = detach_and_continue.execute(arguments)
            elif tool_name == "list_worktrees":
                result = list_worktrees.execute(arguments)
            elif tool_name == "list_sessions":
                result = list_sessions.execute(arguments)
            elif tool_name == "get_current_context":
                result = get_context.execute(arguments)
            else:
                return {"error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}

            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ]
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": False,
                            "error": str(e)
                        }, indent=2)
                    }
                ]
            }

    # Handle notifications (no response needed)
    if method and method.startswith("notifications/"):
        logger.debug(f"Ignoring notification: {method}")
        return None  # Notifications don't require a response

    logger.warning(f"Unknown method: {method}")
    return {"error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    """MCP server main loop"""
    logger.info("Entering main loop, waiting for stdin...")

    try:
        line_count = 0
        for line in sys.stdin:
            line_count += 1
            logger.debug(f"Received line {line_count}: {line[:100]}...")

            try:
                request = json.loads(line)
                response = handle_request(request)

                # Notifications don't get responses
                if response is None:
                    logger.debug("No response needed (notification)")
                    continue

                response["jsonrpc"] = "2.0"
                response["id"] = request.get("id")
                response_json = json.dumps(response)
                logger.debug(f"Sending response: {response_json[:100]}...")
                print(response_json, flush=True)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error on line {line_count}: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": f"Parse error: {str(e)}"}
                }
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                logger.error(f"Error handling request: {e}", exc_info=True)
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {"code": -32603, "message": str(e)}
                }
                print(json.dumps(error_response), flush=True)

        logger.info("stdin closed, exiting main loop")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
