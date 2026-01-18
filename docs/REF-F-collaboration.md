# Agent Collaboration

Sometimes it helps to have a second opinion. Different models think differently - they catch different things. The agentbox-analyst MCP lets agents ask each other for help.

## The Idea

It's like having a teammate who's just there to verify and catch things you missed.

You're working with Claude on a feature. Before committing, the agent asks a peer: "Review this commit. What did I miss?" The peer agent (maybe using a different model) looks at the changes and reports back.

The primary agent considers the feedback. Maybe incorporates it. Maybe disagrees. You're the final authority - these are suggestions, not commands.

## What It Enables

**Plan verification:** Before implementing something complex, ask a peer to review the plan. Catch issues before writing code.

**Commit review:** After making changes, ask a peer to review. Find bugs, edge cases, improvements.

**Test suggestions:** Ask what tests should exist for some code. Get ideas for coverage.

**Quick sanity checks:** Simple questions that benefit from a second perspective.

## Enabling It

```bash
agentbox mcp add agentbox-analyst
agentbox rebase
```

Now agents have access to the analyst tools.

## How Agents Use It

The analyst MCP provides several functions:

### Verify a Plan

```
verify_plan(plan, context, concerns)
```

Before implementing, the agent writes a plan and asks a peer to review it. The peer considers:
- Are there issues with this approach?
- What risks exist?
- Are there better alternatives?

### Review a Commit

```
review_commit(commit, focus)
```

After making changes, ask a peer to review them. The peer looks for:
- Bugs or logic errors
- Edge cases not handled
- Potential improvements
- Things that don't look right

### Suggest Tests

```
suggest_tests(subject, test_type)
```

Point at some code and ask what tests should exist. The peer suggests:
- Unit tests for functions
- Integration tests for flows
- Edge cases to cover

### Quick Check

```
quick_check(subject, question)
```

For simple questions: "Does this look right?" "Is this the standard pattern?" Quick answers without a full report.

### Deep Analysis

```
analyze(subject, prompt, report_file)
```

For thorough investigation. The peer writes a detailed report to a file.

## Trust Model

Reports are suggestions, not commands. The implementing agent should:
- Read the feedback
- Verify findings independently
- Ask you when paths are unclear

You're the final authority. If the peer says "this is wrong" and you disagree, override it.

## Different Models, Different Perspectives

The power comes from diversity. Claude might miss something that Codex catches. Gemini might suggest an approach Claude didn't consider.

Configure which model the analyst uses in the MCP settings. You can even have multiple analysts with different models for different perspectives.

## When to Use It

**Before major changes.** "I'm about to refactor the auth system. Review my plan."

**After complex implementations.** "I just added rate limiting. What did I miss?"

**When uncertain.** "Is this the right pattern for this use case?"

**For learning.** "Explain why this approach is better than the alternative."

## What's Next

- **[Configuration](08-configuration.md)** - MCP setup details
- **[CLI Reference](REF-A-cli.md)** - MCP commands
