# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Git repository helpers for boxctl DinD tests."""

import subprocess
from pathlib import Path
from typing import List, Optional


def init_git_repo(
    path: Path,
    initial_commit: bool = True,
    branches: Optional[List[str]] = None,
) -> Path:
    """Initialize a git repository.

    Args:
        path: Directory path for the repo
        initial_commit: Create initial commit
        branches: List of branches to create

    Returns:
        Path to the repository
    """
    path.mkdir(parents=True, exist_ok=True)

    # Initialize repo
    subprocess.run(
        ["git", "init"],
        cwd=path,
        check=True,
        capture_output=True,
    )

    # Configure git
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=path,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path,
        check=True,
        capture_output=True,
    )

    if initial_commit:
        # Create initial file and commit
        readme = path / "README.md"
        readme.write_text("# Test Repository\n\nThis is a test repository.\n")

        subprocess.run(
            ["git", "add", "."],
            cwd=path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=path,
            check=True,
            capture_output=True,
        )

    # Create additional branches
    if branches:
        for branch in branches:
            subprocess.run(
                ["git", "branch", branch],
                cwd=path,
                check=True,
                capture_output=True,
            )

    return path


def get_current_branch(path: Path) -> str:
    """Get current git branch.

    Args:
        path: Repository path

    Returns:
        Branch name
    """
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def list_branches(path: Path) -> List[str]:
    """List all git branches.

    Args:
        path: Repository path

    Returns:
        List of branch names
    """
    result = subprocess.run(
        ["git", "branch", "--format", "%(refname:short)"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return [b.strip() for b in result.stdout.strip().split("\n") if b.strip()]


def list_worktrees(path: Path) -> List[dict]:
    """List git worktrees.

    Args:
        path: Repository path

    Returns:
        List of worktree info dicts with 'path' and 'branch' keys
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=path,
        capture_output=True,
        text=True,
    )

    worktrees = []
    current = {}

    for line in result.stdout.strip().split("\n"):
        if line.startswith("worktree "):
            if current:
                worktrees.append(current)
            current = {"path": line[9:]}
        elif line.startswith("branch "):
            current["branch"] = line[7:].replace("refs/heads/", "")
        elif line == "":
            if current:
                worktrees.append(current)
                current = {}

    if current:
        worktrees.append(current)

    return worktrees


def add_worktree(path: Path, branch: str, worktree_path: Path) -> bool:
    """Add a git worktree.

    Args:
        path: Repository path
        branch: Branch name
        worktree_path: Path for the worktree

    Returns:
        True if successful
    """
    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), branch],
        cwd=path,
        capture_output=True,
    )
    return result.returncode == 0


def remove_worktree(path: Path, worktree_path: Path, force: bool = False) -> bool:
    """Remove a git worktree.

    Args:
        path: Repository path
        worktree_path: Path to the worktree
        force: Force removal

    Returns:
        True if successful
    """
    args = ["git", "worktree", "remove", str(worktree_path)]
    if force:
        args.append("--force")

    result = subprocess.run(
        args,
        cwd=path,
        capture_output=True,
    )
    return result.returncode == 0
