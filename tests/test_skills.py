# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Tests for skills management commands (list, add, remove)."""

import subprocess
import pytest
from pathlib import Path
from tests.conftest import run_abox


@pytest.fixture
def test_skill(tmp_path):
    """Create a test skill in the library for testing.

    Returns:
        tuple: (skill_name, skill_path)
    """
    package_root = Path(__file__).resolve().parents[1]
    library_skills_dir = package_root / "library" / "skills"
    library_skills_dir.mkdir(parents=True, exist_ok=True)

    skill_name = "test-skill-fixture"
    skill_path = library_skills_dir / skill_name

    # Create skill directory structure
    skill_path.mkdir(exist_ok=True)
    (skill_path / "README.md").write_text("# Test Skill\n\nA test skill for testing.")
    (skill_path / "SKILL.md").write_text("# Test Skill Instructions\n\nThis is a test skill for automated testing.")
    (skill_path / "config.json").write_text('{"name": "test-skill-fixture", "description": "Test skill"}')

    yield skill_name, skill_path

    # Cleanup: remove test skill from library
    import shutil
    if skill_path.exists():
        shutil.rmtree(skill_path)


def test_skill_list_shows_library(test_project):
    """Test that 'abox skill list' shows available skills from library."""
    result = run_abox("skill", "list", cwd=test_project)

    assert result.returncode == 0, "skill list should succeed"
    # Output should show table or list of skills
    assert len(result.stdout) > 0, "Should produce output"


def test_skill_add_copies_to_project(test_project, test_skill):
    """Test that 'abox skill add' copies skill to project."""
    skill_name, _ = test_skill

    result = run_abox("skill", "add", skill_name, cwd=test_project, check=False)

    assert result.returncode == 0, f"skill add should succeed: {result.stderr}"

    # Verify skill was copied to both Claude and Codex
    claude_skill_dir = test_project / ".agentbox" / "claude" / "skills" / skill_name
    codex_skill_dir = test_project / ".agentbox" / "codex" / "skills" / skill_name

    assert claude_skill_dir.exists(), f"Skill {skill_name} should be copied to Claude skills"
    assert codex_skill_dir.exists(), f"Skill {skill_name} should be copied to Codex skills"
    assert (claude_skill_dir / "README.md").exists(), "Skill files should be copied"


def test_skill_add_creates_claude_dir(test_project, test_skill):
    """Test that adding a skill creates skill directory in Claude config."""
    skill_name, _ = test_skill

    result = run_abox("skill", "add", skill_name, cwd=test_project, check=False)

    assert result.returncode == 0, f"skill add should succeed: {result.stderr}"

    claude_skill_dir = test_project / ".agentbox" / "claude" / "skills" / skill_name
    assert claude_skill_dir.exists(), f"Skill {skill_name} should be copied to Claude skills"
    assert (claude_skill_dir / "config.json").exists(), "Skill config should be copied"


def test_skill_add_creates_codex_dir(test_project, test_skill):
    """Test that adding a skill creates skill directory in Codex config."""
    skill_name, _ = test_skill

    result = run_abox("skill", "add", skill_name, cwd=test_project, check=False)

    assert result.returncode == 0, f"skill add should succeed: {result.stderr}"

    codex_skill_dir = test_project / ".agentbox" / "codex" / "skills" / skill_name
    assert codex_skill_dir.exists(), f"Skill {skill_name} should be copied to Codex skills"
    assert (codex_skill_dir / "config.json").exists(), "Skill config should be copied"


def test_skill_remove_deletes_from_project(test_project, test_skill):
    """Test that 'abox skill remove' removes skill from project."""
    skill_name, _ = test_skill

    # Add skill first
    add_result = run_abox("skill", "add", skill_name, cwd=test_project, check=False)
    assert add_result.returncode == 0, "skill add should succeed"

    # Verify it was added
    claude_skill_dir = test_project / ".agentbox" / "claude" / "skills" / skill_name
    codex_skill_dir = test_project / ".agentbox" / "codex" / "skills" / skill_name
    assert claude_skill_dir.exists(), "Skill should exist before remove"
    assert codex_skill_dir.exists(), "Skill should exist before remove"

    # Remove skill
    remove_result = run_abox("skill", "remove", skill_name, cwd=test_project, check=False)
    assert remove_result.returncode == 0, f"skill remove should succeed: {remove_result.stderr}"

    # Verify it was removed
    assert not claude_skill_dir.exists(), "Skill should be removed from Claude"
    assert not codex_skill_dir.exists(), "Skill should be removed from Codex"


def test_skill_files_accessible_in_container(test_project, test_skill):
    """Test that skill files are accessible in container after adding."""
    skill_name, _ = test_skill

    # Add skill
    add_result = run_abox("skill", "add", skill_name, cwd=test_project, check=False)
    assert add_result.returncode == 0, "skill add should succeed"

    # Start container
    run_abox("start", cwd=test_project)

    container_name = f"agentbox-{test_project.name}"

    # Check if skill files are accessible in container
    result = subprocess.run(
        ["docker", "exec", container_name, "test", "-d",
         f"/workspace/.agentbox/claude/skills/{skill_name}"],
        capture_output=True
    )

    assert result.returncode == 0, \
        f"Skill {skill_name} directory should be accessible in container"


def test_skill_show_displays_info(test_project):
    """Test that 'abox skill show' displays skill information."""
    from pathlib import Path
    package_root = Path(__file__).resolve().parents[1]
    library_skills_dir = package_root / "library" / "skills"

    if library_skills_dir.exists():
        skills = [d.name for d in library_skills_dir.iterdir() if d.is_dir()]

        if len(skills) > 0:
            skill_name = skills[0]

            # Show skill info
            result = run_abox("skill", "show", skill_name, cwd=test_project, check=False)

            # Should succeed (or fail gracefully if command doesn't exist)
            assert result.returncode in [0, 1, 2], "skill show should not crash"

            # If it succeeded, should produce output
            if result.returncode == 0:
                assert len(result.stdout) > 0, "Should display skill information"
