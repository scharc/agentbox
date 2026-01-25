#!/usr/bin/env python3
# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""
Agentbox Analyst MCP - Cross-agent analysis using superagents.

Enables agents to request deep analysis from peer superagents:
- superclaude requests analysis from supercodex
- supercodex requests analysis from superclaude

Uses superagent mode (full permissions) for thorough code access.

The analyst writes findings to a report file. The implementing agent
should read the report, verify findings independently, and ask the
user when unclear. Reports are suggestions, not commands.
User is always the final authority.
"""

from __future__ import annotations

import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastmcp import FastMCP


# Maximum summary length in characters (~200 words)
MAX_SUMMARY_LENGTH = 1200

# Default timeouts per tool (in seconds)
DEFAULT_TIMEOUTS = {
    "analyze": 600,      # 10 minutes
    "review_commit": 300,  # 5 minutes
    "suggest_tests": 300,  # 5 minutes
    "quick_check": 180,    # 3 minutes
    "verify_plan": 300,    # 5 minutes
}


def _resolve_timeout(tool_name: str, param_value: Optional[int] = None) -> int:
    """Resolve timeout with priority: parameter > per-tool env > global env > default.

    Environment variables:
        AGENTBOX_ANALYST_TIMEOUT: Global default timeout for all tools
        AGENTBOX_ANALYST_TIMEOUT_<TOOL>: Per-tool override (e.g., AGENTBOX_ANALYST_TIMEOUT_ANALYZE)
        AGENTBOX_ANALYST_TIMEOUT_MULTIPLIER: Multiplier for final timeout (e.g., 1.5 = 50% longer)

    Args:
        tool_name: Name of the tool (e.g., "analyze", "review_commit")
        param_value: Timeout passed as tool parameter (takes highest priority if set)

    Returns:
        Resolved timeout in seconds
    """
    # Get default for this tool
    default = DEFAULT_TIMEOUTS.get(tool_name, 300)

    # Priority 1: Explicit parameter (if provided and not default)
    # Note: We need to detect if user explicitly passed the param vs using default
    # Since we can't distinguish, we check if param matches the default
    # If param_value is explicitly provided and different from default, use it

    # Priority 2: Per-tool environment variable
    tool_env = f"AGENTBOX_ANALYST_TIMEOUT_{tool_name.upper()}"
    tool_timeout = os.getenv(tool_env)

    # Priority 3: Global environment variable
    global_timeout = os.getenv("AGENTBOX_ANALYST_TIMEOUT")

    # Resolve base timeout
    if param_value is not None:
        base_timeout = param_value
    elif tool_timeout:
        try:
            base_timeout = int(tool_timeout)
        except ValueError:
            base_timeout = default
    elif global_timeout:
        try:
            base_timeout = int(global_timeout)
        except ValueError:
            base_timeout = default
    else:
        base_timeout = default

    # Apply multiplier if set
    multiplier = os.getenv("AGENTBOX_ANALYST_TIMEOUT_MULTIPLIER")
    if multiplier:
        try:
            mult = float(multiplier)
            if mult > 0:
                base_timeout = int(base_timeout * mult)
        except ValueError:
            pass  # Ignore invalid multiplier

    return base_timeout


mcp = FastMCP(
    name="agentbox-analyst",
    instructions=(
        "Agentbox Analyst MCP - cross-agent analysis using superagents. "
        "Request a peer superagent to analyze features, code, or work done. "
        "Reports are written to files. Verify findings independently. "
        "User is the final authority."
    ),
)


# Supported agents for analysis
SUPPORTED_AGENTS = ("claude", "codex", "gemini", "qwen")



def _extract_summary(output: str, fallback: str = "See full output for details") -> str:
    """Extract summary from output, avoiding code blocks and capping length.

    Looks for SUMMARY: or TL;DR: sections outside of code blocks.
    Returns capped text to avoid huge summaries.
    """
    # Remove code blocks to avoid matching SUMMARY: inside them
    # Replace ```...``` blocks with placeholder
    cleaned = re.sub(r'```[\s\S]*?```', '[CODE_BLOCK]', output)

    summary = ""

    # Try SUMMARY: first
    if "SUMMARY:" in cleaned:
        # Find position in cleaned text, extract from original
        match = re.search(r'SUMMARY:\s*', cleaned)
        if match:
            # Get position and extract from original output
            start = match.end()
            # Find the corresponding position in the original
            # by counting non-code-block characters
            orig_pos = 0
            cleaned_pos = 0
            in_code_block = False
            i = 0
            while i < len(output) and cleaned_pos < start:
                if output[i:i+3] == '```':
                    in_code_block = not in_code_block
                    # Skip to end of code block marker
                    end_marker = output.find('\n', i)
                    if end_marker == -1:
                        end_marker = len(output)
                    if in_code_block:
                        # Find closing ```
                        close = output.find('```', end_marker)
                        if close != -1:
                            i = close + 3
                            cleaned_pos += len('[CODE_BLOCK]')
                            in_code_block = False
                            continue
                    i = end_marker
                cleaned_pos += 1
                orig_pos = i
                i += 1

            # Extract summary from after SUMMARY: in cleaned output
            summary_text = cleaned[start:].strip()
            # Take until next section header or end
            end_match = re.search(r'\n##|\n\*\*[A-Z]', summary_text)
            if end_match:
                summary_text = summary_text[:end_match.start()]
            summary = summary_text.strip()

    # Try TL;DR: as fallback
    if not summary and "TL;DR:" in cleaned:
        match = re.search(r'TL;DR:\s*(.+?)(?:\n##|\n\*\*[A-Z]|\Z)', cleaned, re.DOTALL)
        if match:
            summary = match.group(1).strip()

    # Try ## TL;DR header (without colon) as fallback
    if not summary:
        match = re.search(r'##\s*TL;DR\s*\n+(.+?)(?:\n##|\n\*\*[A-Z]|\Z)', cleaned, re.DOTALL | re.IGNORECASE)
        if match:
            summary = match.group(1).strip()

    if not summary:
        summary = fallback

    # Cap length
    if len(summary) > MAX_SUMMARY_LENGTH:
        summary = summary[:MAX_SUMMARY_LENGTH].rsplit(' ', 1)[0] + "..."

    return summary


def _extract_verdict(output: str) -> str:
    """Extract verdict from ### Verdict section.

    Parses the specific verdict line rather than substring matching
    anywhere in output to avoid false positives.

    Handles various formats:
    - Plain: APPROVE
    - List item: - APPROVE
    - Bold: **APPROVE**
    - Combined: - **APPROVE_WITH_NOTES**
    """
    verdict_tokens = r'(APPROVE_WITH_NOTES|NEEDS_REVISION|REJECT|APPROVE)'

    # Look for ### Verdict section and extract the verdict on the next line(s)
    # Allow optional list marker (-), bold (**), or whitespace before verdict
    verdict_match = re.search(
        r'###\s*Verdict\s*\n+\s*[-*]*\s*\*?\*?' + verdict_tokens + r'\b',
        output,
        re.IGNORECASE
    )
    if verdict_match:
        return verdict_match.group(1).upper()

    # Fallback: look for "Verdict:" or "**Verdict**:" patterns
    # Allow bold markers around the verdict value
    verdict_match = re.search(
        r'\*?\*?Verdict\*?\*?:\s*\*?\*?' + verdict_tokens + r'\b',
        output,
        re.IGNORECASE
    )
    if verdict_match:
        return verdict_match.group(1).upper()

    return "UNKNOWN"


def _detect_caller_agent() -> str:
    """Detect which agent is calling this MCP."""
    caller = os.getenv("AGENTBOX_CALLER_AGENT", "").lower()
    if caller in SUPPORTED_AGENTS:
        return caller

    # Check parent process name
    try:
        ppid = os.getppid()
        with open(f"/proc/{ppid}/comm", "r") as f:
            parent = f.read().strip().lower()
            for agent in SUPPORTED_AGENTS:
                if agent in parent:
                    return agent
    except Exception:
        pass

    return "claude"


def _get_peer_superagent(caller: str) -> str:
    """Get the peer superagent (opposite of caller).

    Primary peers:
    - claude → codex
    - codex → claude
    - gemini → codex
    - qwen → claude
    """
    if caller == "claude":
        return "codex"
    elif caller == "codex":
        return "claude"
    elif caller == "gemini":
        return "codex"
    elif caller == "qwen":
        return "claude"
    else:
        return "codex"


def _is_rate_limited(output: str, stderr: str) -> bool:
    """Check if output indicates rate limiting or usage limit reached."""
    combined = f"{output} {stderr}".lower()
    rate_limit_indicators = [
        "usage_limit_reached",
        "usage limit",
        "rate limit",
        "too many requests",
        "429",
        "quota exceeded",
        "try again at",
    ]
    return any(indicator in combined for indicator in rate_limit_indicators)


def _get_fallback_agents(failed_agent: str, caller: str) -> list[str]:
    """Get list of fallback agents to try after primary fails.

    Fallback order: gemini → self (caller) → qwen
    Qwen is last resort (weakest for general analysis).
    """
    # Build fallback chain: gemini, self, qwen - excluding already failed
    fallbacks = []
    for agent in ["gemini", caller, "qwen"]:
        if agent != failed_agent and agent not in fallbacks:
            fallbacks.append(agent)
    return fallbacks


def _execute_qwen_tool_calls(output: str) -> int:
    """Parse qwen's tool call output and execute write_file calls.

    Qwen outputs tool calls as XML instead of executing them.
    This function parses and executes write_file calls.

    Returns number of files written.
    """
    files_written = 0

    # Pattern for qwen's tool call format:
    # <function=write_file>
    # <parameter=file_path>...</parameter>
    # <parameter=content>...</parameter>
    # </function>
    pattern = r'<function=write_file>\s*<parameter=file_path>\s*(.*?)\s*</parameter>\s*<parameter=content>\s*(.*?)\s*</parameter>'

    for match in re.finditer(pattern, output, re.DOTALL):
        file_path = match.group(1).strip()
        content = match.group(2).strip()

        # Security: only allow writes to /tmp/
        if not file_path.startswith("/tmp/"):
            continue

        try:
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            with open(file_path, "w") as f:
                f.write(content)
            files_written += 1
        except Exception:
            pass

    return files_written


def _invoke_single_agent(agent: str, prompt: str, timeout: Optional[int], env: dict, workspace: str) -> dict:
    """Invoke a single superagent (no fallback logic).

    Returns dict with success, output, error, stderr, agent_used.
    """
    import shutil

    # Superagent commands - full permissions for thorough analysis
    # Run directly inside the container (no docker exec needed)
    #
    # CLI compatibility:
    # - claude: -p enables print mode, reads prompt from stdin
    # - codex: exec with "-" reads prompt from stdin
    # - gemini: --yolo for auto-approve, prompt as positional arg
    # - qwen: --yolo for auto-approve, -p for prompt (appended to stdin)
    superagent_commands = {
        "claude": ["claude", "--dangerously-skip-permissions", "-p"],
        "codex": ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", "-"],
        "gemini": ["gemini", "--yolo", "-o", "text"],  # prompt added separately
        "qwen": ["qwen", "--yolo"],  # prompt added separately via -p flag
    }

    # Agents that need prompt as argument, not stdin
    prompt_as_arg = (agent in ("gemini", "qwen"))

    if agent not in superagent_commands:
        return {"success": False, "error": f"Unknown agent: {agent}", "output": "", "stderr": None, "agent_used": agent}

    # Check if agent is available
    agent_bin = agent if agent != "codex" else "codex"
    if not shutil.which(agent_bin):
        return {
            "success": False,
            "error": f"Agent '{agent_bin}' not found on PATH. Is this running inside an agentbox container?",
            "output": "",
            "stderr": None,
            "agent_used": agent,
        }

    cmd = superagent_commands[agent]

    # Handle prompt passing - some agents need it as argument, not stdin
    if prompt_as_arg:
        if agent == "gemini":
            cmd = cmd + [prompt]
        elif agent == "qwen":
            cmd = cmd + ["-p", prompt]
        input_data = None
    else:
        input_data = prompt

    try:
        result = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=workspace,
            env=env,
        )
        stderr = result.stderr.strip() if result.stderr else ""
        stdout = result.stdout.strip() if result.stdout else ""

        # Qwen outputs tool calls as text - parse and execute them
        if agent == "qwen" and stdout:
            _execute_qwen_tool_calls(stdout)

        return {
            "success": result.returncode == 0,
            "output": stdout,
            "error": stderr if result.returncode != 0 else None,
            "stderr": stderr,
            "agent_used": agent,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Timed out after {timeout}s", "output": "", "stderr": None, "agent_used": agent}
    except Exception as e:
        return {"success": False, "error": str(e), "output": "", "stderr": None, "agent_used": agent}


def _invoke_superagent(agent: str, prompt: str, timeout: Optional[int] = None, caller: str = "", workspace: str = "") -> dict:
    """Invoke a superagent for analysis with fallback support.

    Uses superagent mode for full read access:
    - superclaude: claude --dangerously-skip-permissions
    - supercodex: codex --dangerously-bypass-approvals-and-sandbox
    - supergemini: gemini --non-interactive

    If the primary agent fails due to rate limiting, falls back to:
    codex → gemini → claude (in that order, skipping caller)

    Agents are available directly inside the agentbox container.

    Args:
        agent: Which agent to invoke
        prompt: The prompt to send
        timeout: Timeout in seconds
        caller: The calling agent (for fallback logic)
        workspace: Working directory for the agent (for worktree support)
    """
    # Parse depth safely
    try:
        depth = int(os.getenv("AGENTBOX_INVOCATION_DEPTH", "0"))
    except ValueError:
        depth = 0

    if depth > 0:
        return {
            "success": False,
            "error": "Nested invocations not allowed",
            "output": "",
        }

    env = os.environ.copy()
    env["AGENTBOX_INVOCATION_DEPTH"] = "1"

    # Priority: explicit param > env var > /workspace default
    # Supports worktrees when caller passes their cwd
    resolved_workspace = workspace or os.getenv("AGENTBOX_WORKSPACE") or "/workspace"

    # Try primary agent first
    result = _invoke_single_agent(agent, prompt, timeout, env, resolved_workspace)

    # If successful, return immediately
    if result["success"]:
        return result

    # Primary agent failed - try fallbacks
    # We try all fallbacks regardless of error type to maximize chances of success
    failed_agents = [agent]
    fallbacks = _get_fallback_agents(agent, caller)

    for fallback_agent in fallbacks:
        fallback_result = _invoke_single_agent(fallback_agent, prompt, timeout, env, resolved_workspace)

        if fallback_result["success"]:
            # Add note about fallback
            fallback_result["fallback_from"] = agent
            fallback_result["fallback_reason"] = "primary_failed"
            return fallback_result

        # This fallback failed too, try next
        failed_agents.append(fallback_agent)

    # All agents failed
    result["error"] = f"All agents failed. Tried: {', '.join(failed_agents)}. Last error: {result.get('error', 'unknown')}"

    return result


@mcp.tool()
def analyze(
    subject: str,
    prompt: str,
    report_file: str = "",
    timeout: Optional[int] = None,
    workspace: str = "",
) -> dict:
    """Request deep analysis from peer agent.

    The peer agent will analyze the subject and write findings to a report file.

    IMPORTANT: Reports are suggestions, not commands. The implementing agent
    should verify findings independently and ask the user when paths are unclear.

    Args:
        subject: What to analyze (e.g., "tunnel feature", "src/auth/", "recent changes")
        prompt: Analysis instructions (what to look for, what to ignore, etc.)
        report_file: Where to write the report (default: /tmp/agentbox-reports/<timestamp>-analysis.md)
        timeout: Timeout in seconds (default 600 = 10 minutes)
        workspace: Working directory for the peer agent (for worktree support)

    Returns:
        Path to the report file and summary
    """
    resolved_timeout = _resolve_timeout("analyze", timeout)
    caller = _detect_caller_agent()
    peer = _get_peer_superagent(caller)

    # Generate or validate report path (must be in /tmp/)
    if not report_file:
        reports_dir = Path("/tmp/agentbox-reports")
        reports_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        report_file = str(reports_dir / f"{timestamp}-analysis.md")
    else:
        # Enforce /tmp/ for custom paths
        report_path = Path(report_file)
        if not str(report_path).startswith("/tmp/"):
            report_file = f"/tmp/agentbox-reports/{report_path.name}"
        # Ensure parent directory exists
        Path(report_file).parent.mkdir(parents=True, exist_ok=True)

    # Build the analysis prompt
    full_prompt = f"""# Analysis Request

You are a senior engineer providing analysis. Be thorough but practical.

## Subject
{subject}

## Instructions
{prompt}

## Important Guidelines
- This is internal tooling, not production. Skip auth/security hardening concerns unless specifically asked.
- Focus on: correctness, edge cases, missing functionality, potential bugs
- Be specific: reference file paths and line numbers
- Be actionable: explain what's wrong AND how to fix it
- Prioritize findings by impact

## Output
Write your complete analysis report to: {report_file}

The report should include:
1. **Summary**: 2-3 sentence overview
2. **Findings**: Numbered list with severity (high/medium/low), location, and fix
3. **Recommendations**: Prioritized next steps

After writing the report, output a SUMMARY section (not in the file, just in your response) with:
1. What you analyzed and the scope
2. Key findings with severity counts
3. The most critical issues (briefly describe top 2-3)
4. Recommended next steps

Keep the summary around 150-200 words - enough for the user to understand findings without reading the full report.

Format:
SUMMARY:
<your summary here>
"""

    result = _invoke_superagent(peer, full_prompt, resolved_timeout, caller=caller, workspace=workspace)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Analysis failed"),
            "report_file": None,
        }

    # Track which agent actually performed the analysis
    agent_used = result.get("agent_used", peer)
    fallback_info = ""
    if result.get("fallback_from"):
        fallback_info = f" (fallback from {result['fallback_from']} due to {result.get('fallback_reason', 'error')})"

    # Check if report was created - fail if missing
    report_exists = Path(report_file).exists()
    if not report_exists:
        return {
            "success": False,
            "error": f"Peer agent completed but report was not created at {report_file}",
            "report_file": report_file,
            "analyst_output": result["output"][-500:] if len(result["output"]) > 500 else result["output"],
        }

    # Extract summary for user
    output = result["output"]
    summary = _extract_summary(output, f"Analysis complete - see {report_file} for details")

    return {
        "success": True,
        "superagent": f"super{agent_used}{fallback_info}",
        "subject": subject,
        "report_file": report_file,
        "summary": summary,
        "analyst_output": output[-500:] if len(output) > 500 else output,
        "next_step": f"Read {report_file}, verify findings independently, fix only what you confirm is correct, ask user if unclear.",
    }


def _validate_commit_ref(commit: str, workspace: str = "") -> tuple[bool, str]:
    """Validate a git commit reference to prevent injection.

    Args:
        commit: Git commit reference to validate
        workspace: Working directory for git commands (default: /workspace)

    Returns (is_valid, sanitized_or_error_message).
    """
    import re
    import subprocess

    # Basic format validation - allow common git ref patterns
    # SHA (short or full), HEAD, HEAD~N, HEAD^N, branch names, tags
    safe_pattern = r'^[a-zA-Z0-9_./@^~-]+$'
    if not re.match(safe_pattern, commit):
        return False, f"Invalid commit reference format: {commit}"

    # Reject refs starting with - to prevent option injection
    if commit.startswith("-"):
        return False, f"Commit reference cannot start with dash: {commit}"

    # Reject obvious injection attempts
    dangerous = [';', '|', '&', '$', '`', '(', ')', '{', '}', '<', '>', '\n', '\r']
    if any(c in commit for c in dangerous):
        return False, f"Invalid characters in commit reference: {commit}"

    # Verify it's a valid git ref
    # Note: --verify requires ref immediately after, can't use -- separator
    # Pre-validation above prevents option injection (no leading -, no shell chars)
    # Priority: explicit param > env var > /workspace default
    cwd = workspace or os.getenv("AGENTBOX_WORKSPACE") or "/workspace"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", commit],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=cwd,
        )
        if result.returncode != 0:
            return False, f"Not a valid git reference: {commit}"
        return True, result.stdout.strip()  # Return the resolved SHA
    except Exception as e:
        return False, f"Failed to validate commit: {e}"


@mcp.tool()
def review_commit(
    commit: str = "HEAD",
    focus: str = "",
    timeout: Optional[int] = None,
    workspace: str = "",
) -> dict:
    """Find issues with a commit.

    Reviews the specified commit for bugs, edge cases, and improvements.

    Args:
        commit: Commit to review (default: HEAD, can be SHA, HEAD~1, etc.)
        focus: Optional focus area (e.g., "error handling", "performance")
        timeout: Timeout in seconds (default 300 = 5 minutes)
        workspace: Working directory for git commands (for worktree support)

    Returns:
        Issues found and suggestions
    """
    resolved_timeout = _resolve_timeout("review_commit", timeout)

    # Validate commit reference to prevent injection
    is_valid, validated = _validate_commit_ref(commit, workspace)
    if not is_valid:
        return {
            "success": False,
            "error": validated,  # Contains error message
            "review": None,
        }
    # Use the validated SHA for safety
    safe_commit = validated

    caller = _detect_caller_agent()
    peer = _get_peer_superagent(caller)

    focus_instruction = f"\n\nFocus especially on: {focus}" if focus else ""

    prompt = f"""Review the git commit '{safe_commit}' for issues.

First, run: git show {safe_commit} --stat && git show {safe_commit}

Then analyze the changes for:
1. **Bugs**: Logic errors, off-by-one, null checks, race conditions
2. **Edge cases**: Unhandled inputs, boundary conditions
3. **Breaking changes**: API changes, removed functionality
4. **Code quality**: Unclear logic, missing error handling
{focus_instruction}

Format your response as:

## Summary
One sentence: what this commit does

## Issues Found
- [SEVERITY] file:line - Description of issue and how to fix

## Suggestions
- Optional improvements (not bugs, just nice-to-have)

After your analysis, output a SUMMARY section with:
1. What the commit does (one sentence)
2. Issue counts by severity
3. Brief description of each issue found (what's wrong and where)
4. Whether the commit is ready to merge or needs fixes

Keep the summary around 150-200 words - enough for the user to understand without reading the full review.

Format:
SUMMARY:
<your summary here>

Be specific with file paths and line numbers. Only report real issues, not style preferences.
"""

    result = _invoke_superagent(peer, prompt, resolved_timeout, caller=caller, workspace=workspace)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Review failed"),
            "review": None,
        }

    # Track which agent actually performed the review
    agent_used = result.get("agent_used", peer)
    fallback_info = ""
    if result.get("fallback_from"):
        fallback_info = f" (fallback from {result['fallback_from']} due to {result.get('fallback_reason', 'error')})"

    # Extract summary for user
    output = result["output"]

    # Try structured extraction first, fall back to counting issues
    summary = _extract_summary(output, "")
    if not summary:
        # Fallback: count issues from ## Issues Found section
        if "## Issues Found" in output:
            issues_section = output.split("## Issues Found")[-1].split("##")[0]
            issue_count = issues_section.count("- [")
            summary = f"Found {issue_count} issue(s) - see full review for details" if issue_count else "No issues found"
        else:
            summary = "Review complete - see full output for details"

    return {
        "success": True,
        "superagent": f"super{agent_used}{fallback_info}",
        "commit": commit,
        "summary": summary,
        "review": output,
    }


@mcp.tool()
def suggest_tests(
    subject: str,
    test_type: str = "unit",
    timeout: Optional[int] = None,
    workspace: str = "",
) -> dict:
    """Suggest tests for code or find gaps in existing tests.

    Analyzes the subject and suggests test cases or identifies missing coverage.

    Args:
        subject: What to test (file path, function name, feature, or "recent changes")
        test_type: Type of tests - "unit", "integration", or "both" (default: unit)
        timeout: Timeout in seconds (default 300 = 5 minutes)
        workspace: Working directory for the peer agent (for worktree support)

    Returns:
        Test suggestions with example code
    """
    resolved_timeout = _resolve_timeout("suggest_tests", timeout)
    caller = _detect_caller_agent()
    peer = _get_peer_superagent(caller)

    prompt = f"""Analyze '{subject}' and suggest {test_type} tests.

Steps:
1. Read the relevant code to understand what needs testing
2. Find existing tests (if any) to avoid duplicates
3. Identify untested code paths, edge cases, and error conditions

Format your response as:

## Current Coverage
Brief assessment of existing tests (if any)

## Suggested Tests
For each suggested test:
### Test: <descriptive name>
- **What it tests**: One sentence
- **Why it matters**: Edge case / error path / core functionality
- **Example**:
```python
def test_<name>():
    # Arrange
    ...
    # Act
    ...
    # Assert
    ...
```

## Priority
List tests in order of importance (most critical first)

After your analysis, output a SUMMARY section with:
1. Current test coverage assessment (good/partial/missing)
2. Number of tests suggested and their priorities
3. Brief description of each suggested test (what it covers and why it matters)
4. Which tests to implement first

Keep the summary around 150-200 words - enough for the user to understand suggestions without reading full details.

Format:
SUMMARY:
<your summary here>

Focus on:
- Error handling paths
- Boundary conditions
- Common failure modes
- Integration points

Be practical - suggest tests that catch real bugs, not trivial ones.
"""

    result = _invoke_superagent(peer, prompt, resolved_timeout, caller=caller, workspace=workspace)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Test suggestion failed"),
            "suggestions": None,
        }

    # Track which agent actually performed the analysis
    agent_used = result.get("agent_used", peer)
    fallback_info = ""
    if result.get("fallback_from"):
        fallback_info = f" (fallback from {result['fallback_from']} due to {result.get('fallback_reason', 'error')})"

    # Extract summary for user
    output = result["output"]

    # Try structured extraction first, fall back to counting tests
    summary = _extract_summary(output, "")
    if not summary:
        # Fallback: count suggested tests
        if "### Test:" in output:
            test_count = output.count("### Test:")
            summary = f"{test_count} test(s) suggested - see full output for details"
        else:
            summary = "Test analysis complete - see full output for details"

    return {
        "success": True,
        "superagent": f"super{agent_used}{fallback_info}",
        "subject": subject,
        "test_type": test_type,
        "summary": summary,
        "suggestions": output,
    }


@mcp.tool()
def quick_check(
    subject: str,
    question: str,
    timeout: Optional[int] = None,
    workspace: str = "",
) -> dict:
    """Quick question to peer agent - no report file, direct answer.

    Use for simple questions that don't need a full analysis.

    Args:
        subject: What to look at (files, feature, etc.)
        question: Specific question to answer
        timeout: Timeout in seconds (default 180 = 3 minutes)
        workspace: Working directory for the peer agent (for worktree support)

    Returns:
        Direct answer from peer
    """
    resolved_timeout = _resolve_timeout("quick_check", timeout)
    caller = _detect_caller_agent()
    peer = _get_peer_superagent(caller)

    prompt = f"""Quick analysis request. Be concise and direct.

Subject: {subject}

Question: {question}

Answer the question directly. If you need to read files, do so.

End with a SUMMARY section (3-5 sentences) that:
1. Directly answers the question
2. Provides key supporting details
3. Notes any caveats or things to watch out for

Format:
SUMMARY:
<your summary here>
"""

    result = _invoke_superagent(peer, prompt, resolved_timeout, caller=caller, workspace=workspace)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Check failed"),
            "answer": None,
        }

    # Track which agent actually performed the check
    agent_used = result.get("agent_used", peer)
    fallback_info = ""
    if result.get("fallback_from"):
        fallback_info = f" (fallback from {result['fallback_from']} due to {result.get('fallback_reason', 'error')})"

    # Extract summary for user
    output = result["output"]

    # Try structured extraction first, fall back to last paragraph
    summary = _extract_summary(output, "")
    if not summary:
        # Use last paragraph as summary fallback
        paragraphs = [p.strip() for p in output.strip().split("\n\n") if p.strip()]
        summary = paragraphs[-1] if paragraphs else "Check complete"

    return {
        "success": True,
        "superagent": f"super{agent_used}{fallback_info}",
        "question": question,
        "summary": summary,
        "answer": output,
    }


@mcp.tool()
def verify_plan(
    plan: str,
    context: str = "",
    concerns: str = "",
    timeout: Optional[int] = None,
    workspace: str = "",
) -> dict:
    """Get a second opinion on an implementation plan.

    Use this in plan mode to validate your approach before presenting to the user.
    The peer agent will review the plan for issues, risks, and alternatives.

    Args:
        plan: The implementation plan to verify (paste the full plan)
        context: Optional context about the codebase or requirements
        concerns: Optional specific concerns you want addressed
        timeout: Timeout in seconds (default 300 = 5 minutes)
        workspace: Working directory for the peer agent (for worktree support)

    Returns:
        Peer's assessment with approval/concerns/alternatives
    """
    resolved_timeout = _resolve_timeout("verify_plan", timeout)
    caller = _detect_caller_agent()
    peer = _get_peer_superagent(caller)

    concerns_section = f"\n## Specific Concerns\n{concerns}" if concerns else ""
    context_section = f"\n## Context\n{context}" if context else ""

    prompt = f"""Review this implementation plan and provide a second opinion.

## Plan to Review
{plan}
{context_section}
{concerns_section}

## Your Task
1. Read any relevant code files mentioned in the plan
2. Evaluate the approach for correctness and completeness
3. Identify risks, edge cases, or issues the plan misses
4. Suggest alternatives if you see a better approach

## Response Format

### Verdict
One of: APPROVE, APPROVE_WITH_NOTES, NEEDS_REVISION, REJECT

### Assessment
- What the plan gets right
- What concerns you have
- Missing considerations

### Risks
- Potential issues or edge cases
- Things that could go wrong

### Alternatives (if any)
- Better approaches if you see them
- Why they might be preferable

### Recommendations
- Specific changes to improve the plan
- Priority order for implementation

End with a SUMMARY section (150-200 words) that:
1. States your verdict clearly
2. Summarizes the key strengths and weaknesses
3. Lists the most important changes needed (if any)
4. Gives a clear go/no-go recommendation

Format:
SUMMARY:
<your summary here>
"""

    result = _invoke_superagent(peer, prompt, resolved_timeout, caller=caller, workspace=workspace)

    if not result["success"]:
        return {
            "success": False,
            "error": result.get("error", "Plan verification failed"),
            "assessment": None,
        }

    # Track which agent actually performed the verification
    agent_used = result.get("agent_used", peer)
    fallback_info = ""
    if result.get("fallback_from"):
        fallback_info = f" (fallback from {result['fallback_from']} due to {result.get('fallback_reason', 'error')})"

    # Extract summary and verdict for user
    output = result["output"]

    # Use structured extraction for verdict (parses ### Verdict section)
    verdict = _extract_verdict(output)

    # Use structured extraction for summary
    summary = _extract_summary(output, "")
    if not summary:
        summary = f"Verdict: {verdict} - see full assessment for details"

    return {
        "success": True,
        "superagent": f"super{agent_used}{fallback_info}",
        "verdict": verdict,
        "summary": summary,
        "assessment": output,
    }


@mcp.tool()
def discuss(
    topic: str,
    agents: str = "claude,gemini",
    max_turns: int = 2,
    timeout: Optional[int] = None,
    workspace: str = "",
) -> dict:
    """Get multiple AI perspectives on a topic via multi-agent discussion.

    Runs a conversation between multiple AI agents using AgentPipe.
    Useful for brainstorming, comparing viewpoints, or exploring trade-offs.

    Args:
        topic: What to discuss (question, problem, or context)
        agents: Comma-separated agent list (default: claude,gemini)
        max_turns: Conversation rounds per agent (default: 2)
        timeout: Timeout in seconds (default 120 = 2 minutes)
        workspace: Working directory for the discussion (for worktree support)

    Returns:
        Discussion transcript with all agent responses
    """
    import shutil

    resolved_timeout = timeout or 120

    # Check if agentpipe is available
    if not shutil.which("agentpipe"):
        return {
            "success": False,
            "error": "agentpipe not installed. Run 'abox rebuild' on host.",
            "discussion": None,
        }

    # Parse agents
    agent_list = [a.strip() for a in agents.split(",") if a.strip()]
    if len(agent_list) < 2:
        return {
            "success": False,
            "error": "Need at least 2 agents for discussion",
            "discussion": None,
        }

    # Build agentpipe command
    cmd = ["agentpipe", "run"]
    for agent in agent_list:
        cmd.extend(["-a", agent])
    cmd.extend([
        "-p", topic,
        "--max-turns", str(max_turns),
        "--json",
        "--no-log",
        "--no-summary",
    ])

    # Priority: explicit param > env var > /workspace default
    resolved_workspace = workspace or os.getenv("AGENTBOX_WORKSPACE") or "/workspace"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=resolved_timeout,
            cwd=resolved_workspace,
        )

        # Parse JSONL output for messages
        messages = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                import json
                event = json.loads(line)
                if event.get("type") == "message.created":
                    data = event.get("data", {})
                    content = data.get("content", "").strip()
                    # Clean up MCP noise from gemini
                    content = "\n".join(
                        line for line in content.split("\n")
                        if not line.startswith("MCP server")
                        and not line.startswith("Server '")
                        and "Listening for changes" not in line
                    ).strip()
                    if content:
                        messages.append({
                            "agent": data.get("agent_name", "Unknown"),
                            "content": content,
                        })
            except (json.JSONDecodeError, KeyError):
                continue

        if not messages:
            return {
                "success": False,
                "error": "No messages in discussion",
                "raw_output": result.stdout[-500:] if result.stdout else result.stderr[-500:],
            }

        # Format discussion transcript
        transcript = []
        for msg in messages:
            transcript.append(f"**{msg['agent']}:** {msg['content']}")

        return {
            "success": True,
            "agents": agent_list,
            "turns": max_turns,
            "message_count": len(messages),
            "discussion": "\n\n".join(transcript),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Discussion timed out after {resolved_timeout}s",
            "discussion": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "discussion": None,
        }


if __name__ == "__main__":
    mcp.run()
