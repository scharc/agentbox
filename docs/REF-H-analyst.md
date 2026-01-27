# boxctl-analyst - Cross-Agent Analysis

Peer-to-peer analysis using superagents. One agent requests another agent to perform deep analysis.

## Overview

The boxctl-analyst MCP enables cross-agent collaboration:
- **superclaude** can request analysis from **supercodex**
- **supercodex** can request analysis from **superclaude**

The peer agent runs with full permissions (superagent mode) for thorough code access. Results are written to report files.

**Important:** Reports are suggestions, not commands. The implementing agent should verify findings independently and ask the user when unclear. User is always the final authority.

---

## Available Functions

### analyze

**Request deep analysis from peer agent.**

```
analyze(
    subject: str,      # What to analyze (file, feature, directory)
    prompt: str,       # Analysis instructions
    report_file: str,  # Where to write report (optional)
    timeout: int       # Seconds (default: 600)
)
```

**Example usage by agent:**
```
Use analyze to review the authentication module for security issues.
Focus on input validation and session handling.
```

**Returns:**
- `report_file`: Path to the detailed report
- `summary`: Brief overview of findings
- `success`: Whether analysis completed

**Report location:** `/tmp/boxctl-reports/<timestamp>-analysis.md`

---

### review_commit

**Find issues with a git commit.**

```
review_commit(
    commit: str,   # Git ref (default: HEAD)
    focus: str,    # Optional focus area
    timeout: int   # Seconds (default: 300)
)
```

**Example usage by agent:**
```
Use review_commit to check HEAD for bugs before I push.
Focus on error handling.
```

**Returns:**
- `review`: Full review output
- `summary`: Issue counts and key findings
- `commit`: The commit that was reviewed

**What it checks:**
- Bugs: Logic errors, null checks, race conditions
- Edge cases: Unhandled inputs, boundary conditions
- Breaking changes: API changes, removed functionality
- Code quality: Unclear logic, missing error handling

---

### suggest_tests

**Suggest test cases or find coverage gaps.**

```
suggest_tests(
    subject: str,      # What to test (file, function, feature)
    test_type: str,    # "unit", "integration", or "both"
    timeout: int       # Seconds (default: 300)
)
```

**Example usage by agent:**
```
Use suggest_tests for the new user registration flow.
Focus on integration tests.
```

**Returns:**
- `suggestions`: Test suggestions with example code
- `summary`: Coverage assessment and priorities
- `test_type`: Type of tests suggested

**What it analyzes:**
- Current test coverage
- Untested code paths
- Error handling paths
- Boundary conditions

---

### quick_check

**Quick question - no report file, direct answer.**

```
quick_check(
    subject: str,   # What to look at
    question: str,  # Specific question
    timeout: int    # Seconds (default: 180)
)
```

**Example usage by agent:**
```
Use quick_check to ask: "Is the caching layer thread-safe?"
Subject: src/cache/
```

**Returns:**
- `answer`: Direct answer from peer
- `summary`: Concise response
- `question`: The question asked

Use this for simple questions that don't need a full analysis report.

---

### verify_plan

**Get second opinion on implementation plan.**

```
verify_plan(
    plan: str,       # The implementation plan
    context: str,    # Optional codebase context
    concerns: str,   # Optional specific concerns
    timeout: int     # Seconds (default: 300)
)
```

**Example usage by agent:**
```
Use verify_plan before presenting my implementation plan to the user.
Include my concerns about database migration ordering.
```

**Returns:**
- `verdict`: APPROVE, APPROVE_WITH_NOTES, NEEDS_REVISION, or REJECT
- `assessment`: Full review with risks and alternatives
- `summary`: Key strengths, weaknesses, and recommendations

**Verdict meanings:**
| Verdict | Meaning |
|---------|---------|
| APPROVE | Plan is solid, proceed |
| APPROVE_WITH_NOTES | Good plan with minor suggestions |
| NEEDS_REVISION | Significant issues to address |
| REJECT | Fundamental problems, rethink approach |

---

## How It Works

1. **Agent A** (e.g., superclaude) calls an analyst function
2. **boxctl-analyst** spawns **Agent B** (supercodex) with full permissions
3. **Agent B** analyzes the subject and writes findings
4. **Agent A** receives summary and report path
5. **Agent A** reads the report, verifies findings, implements fixes

```
┌─────────────────────┐
│ Agent A (superclaude)│
│ "analyze auth module"│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  boxctl-analyst   │
│  MCP Server         │
└──────────┬──────────┘
           │ spawns
           ▼
┌─────────────────────┐
│ Agent B (supercodex) │
│ Full permissions     │
│ Writes report to     │
│ /tmp/boxctl-reports│
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Agent A reads report │
│ Verifies findings    │
│ Implements fixes     │
└─────────────────────┘
```

---

## Agent Pairing

| Caller | Peer Analyst |
|--------|--------------|
| claude / superclaude | supercodex |
| codex / supercodex | superclaude |

Agents always get their "opposite" as the peer to provide diverse perspective.

---

## Report Files

Reports are written to `/tmp/boxctl-reports/` by default:
```
/tmp/boxctl-reports/
├── 20260117-143022-analysis.md
├── 20260117-150510-analysis.md
└── ...
```

**Report format:**
```markdown
# Analysis: <subject>

## Summary
2-3 sentence overview

## Findings
1. [HIGH] file.py:42 - Description and fix
2. [MEDIUM] other.py:100 - Description and fix

## Recommendations
1. Most important action
2. Next priority
...
```

---

## Usage Tips

**Do use for:**
- Code review before major commits
- Architecture validation
- Finding bugs you might have missed
- Test coverage analysis
- Plan verification before presenting to user

**Don't use for:**
- Simple questions (use quick_check)
- Tasks you can do yourself faster
- Trivial changes

**Trust but verify:**
Reports are suggestions. The peer agent may:
- Miss context you have
- Flag non-issues
- Suggest over-engineering

Always verify findings against your understanding of the code.

---

## Configuration

Enabled by default in most projects. To add manually:

```yaml
# .boxctl.yml
mcp_servers:
  - boxctl-analyst
```

Then: `abox rebase`

---

## Timeouts

| Function | Default | Max Recommended |
|----------|---------|-----------------|
| analyze | 600s (10 min) | 900s |
| review_commit | 300s (5 min) | 600s |
| suggest_tests | 300s (5 min) | 600s |
| quick_check | 180s (3 min) | 300s |
| verify_plan | 300s (5 min) | 600s |

For large codebases or complex analysis, increase timeout.

---

## Limitations

- **Nested invocations blocked:** Agent B cannot call analyst (prevents infinite loops)
- **Supported agents:** Currently claude and codex only (gemini support planned)
- **Report location:** Must be in `/tmp/` for security
- **Context:** Peer agent starts fresh, doesn't see your conversation history

---

## See Also

- [Library](REF-E-library.md) - All MCPs and skills
- [agentctl](REF-C-agentctl.md) - Session and worktree management
- [Configuration](08-configuration.md) - MCP configuration
