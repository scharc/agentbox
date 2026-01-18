#!/usr/bin/env python3
"""MCP STDIO-to-SSE Bridge

Bridges a STDIO-based MCP server to SSE transport, allowing pre-started servers
that Claude can connect to instantly without subprocess spawn delay.

This bridge:
1. Starts the STDIO MCP server as a subprocess
2. Exposes an SSE endpoint for Claude to connect to
3. Proxies JSON-RPC messages between Claude and the subprocess

Usage:
    mcp-bridge.py --port 9100 --name playwright -- npx @playwright/mcp --headless
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Any
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import Response, JSONResponse
from starlette.routing import Route
from starlette.requests import Request
from sse_starlette.sse import EventSourceResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("mcp-bridge")


class StdioProcess:
    """Manages a STDIO MCP subprocess with proper message framing."""

    def __init__(self, command: list[str], env: Optional[dict] = None):
        self.command = command
        self.env = env or {}
        self.process: Optional[asyncio.subprocess.Process] = None
        self._read_buffer = b""
        self._lock = asyncio.Lock()

    async def start(self):
        """Start the subprocess."""
        logger.info(f"Starting subprocess: {' '.join(self.command)}")

        # Merge environment
        full_env = os.environ.copy()
        full_env.update(self.env)

        self.process = await asyncio.create_subprocess_exec(
            *self.command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=full_env,
        )

        # Start stderr reader task
        asyncio.create_task(self._read_stderr())

        logger.info(f"Subprocess started with PID {self.process.pid}")

    async def stop(self):
        """Stop the subprocess."""
        if self.process:
            logger.info(f"Stopping subprocess PID {self.process.pid}")
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            self.process = None

    async def _read_stderr(self):
        """Read and log stderr from subprocess."""
        if not self.process or not self.process.stderr:
            return

        try:
            while True:
                line = await self.process.stderr.readline()
                if not line:
                    break
                logger.warning(f"[subprocess] {line.decode().strip()}")
        except Exception as e:
            logger.error(f"Error reading stderr: {e}")

    async def send_message(self, message: dict) -> Optional[dict]:
        """Send a JSON-RPC message and wait for response."""
        if not self.process or not self.process.stdin or not self.process.stdout:
            raise RuntimeError("Subprocess not running")

        async with self._lock:
            # Use JSON lines format (newline-delimited JSON)
            # MCP STDIO transport uses newline-delimited JSON, not Content-Length headers
            msg_json = json.dumps(message)
            logger.debug(f"Sending: {msg_json[:100]}...")
            self.process.stdin.write((msg_json + '\n').encode('utf-8'))
            await self.process.stdin.drain()

            # Read response (single JSON line)
            response = await self._read_message()
            return response

    async def _read_message(self) -> Optional[dict]:
        """Read a JSON-RPC message (JSON lines format)."""
        if not self.process or not self.process.stdout:
            return None

        # Check if process is still running
        if self.process.returncode is not None:
            logger.error(f"Subprocess exited with code {self.process.returncode}")
            return None

        # Read a single JSON line
        line = await self.process.stdout.readline()
        if not line:
            logger.warning("Empty read from stdout - subprocess may have closed")
            return None

        line_str = line.decode('utf-8').strip()
        if not line_str:
            return None

        try:
            return json.loads(line_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {line_str[:200]}")
            return None

    def is_running(self) -> bool:
        """Check if subprocess is still running."""
        return self.process is not None and self.process.returncode is None


class McpBridge:
    """SSE server that bridges to a STDIO MCP subprocess."""

    def __init__(self, process: StdioProcess, name: str = "mcp-bridge"):
        self.process = process
        self.name = name
        self._initialized = False
        self._response_queues: dict[str, asyncio.Queue] = {}  # session_id -> queue

    async def health(self, request: Request) -> Response:
        """Health check endpoint."""
        if self.process.is_running():
            return Response("OK", status_code=200)
        return Response("Subprocess not running", status_code=503)

    async def sse_endpoint(self, request: Request) -> Response:
        """SSE endpoint for MCP communication."""
        session_id = uuid.uuid4().hex
        logger.info(f"SSE client {session_id} connected")

        # Create response queue for this session
        queue: asyncio.Queue = asyncio.Queue()
        self._response_queues[session_id] = queue

        async def event_generator():
            try:
                # Send endpoint info (matching FastMCP format)
                yield {
                    "event": "endpoint",
                    "data": f"/messages/?session_id={session_id}"
                }

                # Wait for messages from the queue
                while True:
                    try:
                        message = await asyncio.wait_for(queue.get(), timeout=30.0)
                        yield {
                            "event": "message",
                            "data": json.dumps(message)
                        }
                    except asyncio.TimeoutError:
                        # Send keepalive ping
                        yield {"event": "ping", "data": ""}

            except asyncio.CancelledError:
                logger.info(f"SSE client {session_id} disconnected")
            finally:
                self._response_queues.pop(session_id, None)

        return EventSourceResponse(event_generator())

    async def message_endpoint(self, request: Request) -> Response:
        """POST endpoint for sending messages to MCP server."""
        try:
            # Get session ID from query params (matching FastMCP format)
            session_id = request.query_params.get("session_id")

            body = await request.json()
            logger.debug(f"Received message from session {session_id}: {body.get('method', 'response')}")

            # Forward to subprocess
            response = await self.process.send_message(body)

            if response:
                # If we have a session queue, also push there for SSE
                if session_id is not None and session_id in self._response_queues:
                    await self._response_queues[session_id].put(response)

                return JSONResponse(response)

            return JSONResponse(
                {"error": "No response from server"},
                status_code=500
            )

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return JSONResponse(
                {"jsonrpc": "2.0", "error": {"code": -32603, "message": str(e)}},
                status_code=500
            )


def create_app(bridge: McpBridge, process: StdioProcess) -> Starlette:
    """Create the Starlette application."""

    routes = [
        Route("/health", bridge.health, methods=["GET"]),
        Route("/sse", bridge.sse_endpoint, methods=["GET"]),
        Route("/messages/", bridge.message_endpoint, methods=["POST"]),
    ]

    @asynccontextmanager
    async def lifespan(app):
        # Startup
        await process.start()
        yield
        # Shutdown
        await process.stop()

    return Starlette(routes=routes, lifespan=lifespan)


async def main():
    parser = argparse.ArgumentParser(
        description="Bridge STDIO MCP server to SSE transport",
        usage="%(prog)s [options] -- command [args...]"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("MCP_PORT", "9100")),
        help="Port to listen on (default: 9100)"
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("MCP_HOST", "127.0.0.1"),
        help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--name",
        default="mcp-bridge",
        help="Name for this MCP server"
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Command and arguments to run (after --)"
    )

    args = parser.parse_args()

    # Handle -- separator
    command = args.command
    if command and command[0] == "--":
        command = command[1:]

    if not command:
        parser.error("No command specified. Use: mcp-bridge.py --port 9100 -- npx @playwright/mcp")

    # Create process and bridge
    process = StdioProcess(command)
    bridge = McpBridge(process, args.name)

    # Create app
    app = create_app(bridge, process)

    # Handle signals
    loop = asyncio.get_event_loop()

    def signal_handler():
        logger.info("Received shutdown signal")
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

    # Run server
    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    logger.info(f"Starting MCP bridge '{args.name}' on http://{args.host}:{args.port}")
    logger.info(f"Bridging command: {' '.join(command)}")

    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())
