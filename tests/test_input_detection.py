# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Tests for input detection module."""

import pytest

from agentbox.core.input_detection import (
    DetectedInput,
    InputType,
    detect_input_waiting,
    summarize_question,
)


class TestDetectInputWaiting:
    """Tests for detect_input_waiting function."""

    def test_empty_buffer_not_waiting(self):
        """Empty buffer should not be detected as waiting."""
        result = detect_input_waiting("")
        assert not result.waiting
        assert result.input_type == InputType.UNKNOWN

    def test_yes_no_prompt_yn(self):
        """Detect [Y/n] prompts."""
        buffer = """
Some output here
Continue with installation? [Y/n]
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.CONFIRMATION
        assert "Y/n" in result.pattern_matched  # Pattern is regex escaped

    def test_yes_no_prompt_yesno(self):
        """Detect (yes/no) prompts."""
        buffer = """
Are you sure you want to proceed? (yes/no)
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.CONFIRMATION

    def test_question_mark_prompt(self):
        """Detect questions ending with ?"""
        buffer = """
Claude is asking:
? Which framework would you like to use?
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.QUESTION

    def test_password_prompt(self):
        """Detect password prompts."""
        buffer = """
Connecting to server...
Password:
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.PASSWORD

    def test_enter_prompt(self):
        """Detect Enter prompts."""
        buffer = """
Press Enter to continue
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.CONFIRMATION

    def test_text_input_prompt(self):
        """Detect text input prompts."""
        buffer = """
Setting up your project...
Enter your project name:
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.TEXT
        assert "project name" in result.question.lower()

    def test_busy_spinner_not_waiting(self):
        """Spinner indicates busy, not waiting."""
        buffer = """
Processing...
⠋ Building components
"""
        result = detect_input_waiting(buffer)
        assert not result.waiting

    def test_busy_progress_not_waiting(self):
        """Progress percentage indicates busy."""
        buffer = """
Downloading dependencies... 45%
"""
        result = detect_input_waiting(buffer)
        assert not result.waiting

    def test_busy_compiling_not_waiting(self):
        """Compiling message indicates busy."""
        buffer = """
Compiling TypeScript files...
"""
        result = detect_input_waiting(buffer)
        assert not result.waiting

    def test_npm_ok_prompt(self):
        """Detect npm 'Is this OK?' prompts."""
        buffer = """
package.json:
{
  "name": "my-project"
}

Is this OK? (yes)
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.CONFIRMATION

    def test_select_option_prompt(self):
        """Detect selection prompts."""
        buffer = """
Select an option:
1. Create new project
2. Open existing project
3. Exit
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.QUESTION

    def test_claude_code_question(self):
        """Detect Claude Code style questions."""
        buffer = """
I found multiple files matching your query.
? Which file would you like to edit?
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.input_type == InputType.QUESTION

    def test_git_overwrite_prompt(self):
        """Detect git overwrite prompts."""
        buffer = """
error: The following untracked working tree files would be overwritten by checkout:
	config.json
Overwrite these files? (y/n)
"""
        result = detect_input_waiting(buffer)
        assert result.waiting

    def test_context_included(self):
        """Context should include recent lines."""
        buffer = """
Line 1
Line 2
Line 3
Continue? [Y/n]
"""
        result = detect_input_waiting(buffer)
        assert result.waiting
        assert result.context is not None
        assert "Line" in result.context

    def test_real_claude_permission_prompt(self):
        """Test with realistic Claude Code permission prompt."""
        buffer = """
╭──────────────────────────────────────╮
│ Claude wants to run a bash command   │
│                                      │
│ npm install typescript               │
│                                      │
│ Allow this command?                  │
╰──────────────────────────────────────╯
? Proceed with command? (Y/n)
"""
        result = detect_input_waiting(buffer)
        assert result.waiting


class TestSummarizeQuestion:
    """Tests for summarize_question function."""

    def test_basic_summary(self):
        """Basic question summary."""
        detected = DetectedInput(
            waiting=True,
            input_type=InputType.CONFIRMATION,
            question="Continue with installation? [Y/n]",
            options=None,
            context=None,
            pattern_matched=None,
        )
        summary = summarize_question(detected)
        assert "Continue" in summary
        assert "[Y/n]" in summary

    def test_summary_with_options(self):
        """Summary includes options."""
        detected = DetectedInput(
            waiting=True,
            input_type=InputType.QUESTION,
            question="Which framework?",
            options=["React", "Vue", "Angular"],
            context=None,
            pattern_matched=None,
        )
        summary = summarize_question(detected)
        assert "Which framework?" in summary
        assert "React" in summary
        assert "Vue" in summary

    def test_summary_truncation(self):
        """Long questions are truncated."""
        long_question = "A" * 200
        detected = DetectedInput(
            waiting=True,
            input_type=InputType.TEXT,
            question=long_question,
            options=None,
            context=None,
            pattern_matched=None,
        )
        summary = summarize_question(detected, max_length=50)
        assert len(summary) <= 50
        assert summary.endswith("...")

    def test_not_waiting_default_message(self):
        """Not waiting returns default message."""
        detected = DetectedInput(
            waiting=False,
            input_type=InputType.UNKNOWN,
            question=None,
            options=None,
            context=None,
            pattern_matched=None,
        )
        summary = summarize_question(detected)
        assert summary == "Agent needs input"

    def test_ansi_codes_removed(self):
        """ANSI escape codes are stripped."""
        detected = DetectedInput(
            waiting=True,
            input_type=InputType.QUESTION,
            question="\x1b[32mContinue?\x1b[0m [Y/n]",
            options=None,
            context=None,
            pattern_matched=None,
        )
        summary = summarize_question(detected)
        assert "\x1b" not in summary
        assert "Continue?" in summary
