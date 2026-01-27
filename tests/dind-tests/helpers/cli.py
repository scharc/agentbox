# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""CLI execution helpers for boxctl DinD tests."""

import subprocess
from pathlib import Path
from typing import Optional


def run_abox(
    *args,
    cwd: Optional[Path] = None,
    check: bool = False,
    capture_output: bool = True,
    text: bool = True,
    timeout: int = 120,
    env: Optional[dict] = None,
) -> subprocess.CompletedProcess:
    """Run boxctl CLI command.

    Uses the poetry-installed 'boxctl' command.

    Args:
        *args: Command arguments (e.g., "start", "mcp", "add", "fetch")
        cwd: Working directory
        check: Raise on non-zero exit
        capture_output: Capture stdout/stderr
        text: Decode output as text
        timeout: Command timeout in seconds
        env: Additional environment variables

    Returns:
        CompletedProcess result
    """
    import os

    cmd = ["boxctl", *[str(a) for a in args]]

    # Merge environment
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        env=run_env,
    )


def run_agentctl(
    *args,
    cwd: Optional[Path] = None,
    check: bool = False,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Run agentctl CLI command.

    Args:
        *args: Command arguments
        cwd: Working directory
        check: Raise on non-zero exit
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess result
    """
    cmd = ["agentctl", *[str(a) for a in args]]
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
