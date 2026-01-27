---
name: agentpipe
description: Multi-agent orchestration tool for running conversations between AI agents (Claude, Gemini, Codex, Qwen, etc.). Use when tasks benefit from multiple perspectives, code review by different models, or collaborative problem-solving.
metadata:
  short-description: Orchestrate multi-agent AI conversations
---

# AgentPipe

Orchestrate conversations between multiple AI agents. Useful for:
- Getting multiple perspectives on a problem
- Code review from different AI models
- Collaborative brainstorming
- Comparative analysis

---

## Quick Start

### Two-Agent Conversation
```bash
agentpipe run -a claude:Alice -a gemini:Bob -p "Review this approach to caching"
```

### With TUI and Metrics
```bash
agentpipe run -a claude:Reviewer -a codex:Implementer --tui --metrics -p "Design a rate limiter"
```

### From Config File
```bash
agentpipe run -c /path/to/config.yaml --tui
```

---

## Agent Specification

Three formats for `-a/--agents`:

| Format | Example | Description |
|--------|---------|-------------|
| `type` | `-a claude` | Just the agent type |
| `type:name` | `-a claude:Alice` | Type with display name |
| `type:model:name` | `-a claude:claude-sonnet-4-5:Alice` | Type, model, and name |

### Available Agents in boxctl

These are installed in the container:
- `claude` - Anthropic Claude
- `codex` - OpenAI Codex
- `gemini` - Google Gemini
- `qwen` - Alibaba Qwen

---

## Configuration File

For complex setups, use a YAML config:

```yaml
version: "1.0"

agents:
  - id: reviewer
    type: claude
    name: "Code Reviewer"
    prompt: "You are a senior engineer focused on code quality and bugs."

  - id: architect
    type: gemini
    name: "Architect"
    prompt: "You focus on system design and scalability."

orchestrator:
  mode: round-robin      # round-robin | reactive | free-form
  max_turns: 6
  initial_prompt: "Review this pull request for issues"

logging:
  enabled: true
  show_metrics: true
```

---

## Conversation Modes

| Mode | Behavior |
|------|----------|
| `round-robin` | Fixed rotation: A → B → A → B |
| `reactive` | Response based on previous speaker's content |
| `free-form` | Agents decide when to participate |

---

## Key Flags

```bash
agentpipe run [flags]

  -a, --agents        Agent specs (can repeat)
  -p, --prompt        Initial prompt
  -c, --config        YAML config file
  --mode              Conversation mode
  --max-turns         Max rounds
  --timeout           Per-agent timeout
  --tui               Terminal UI mode
  --no-tui            Disable TUI (for scripting)
  --metrics           Show response metrics
  --json              JSON output
```

---

## Common Patterns

### Code Review Panel
```bash
agentpipe run \
  -a claude:Bugs -a gemini:Architecture -a codex:Performance \
  -p "Review this code for issues: $(cat src/api.py)" \
  --mode round-robin --max-turns 3
```

### Architecture Discussion
```bash
agentpipe run \
  -a claude:Pragmatist -a gemini:Idealist \
  -p "Should we use microservices or monolith for this startup?" \
  --tui --metrics
```

### Scripted (No TUI)
```bash
# For automation - capture output
agentpipe run \
  -a claude -a gemini \
  -p "Summarize the pros/cons of Rust vs Go" \
  --no-tui --max-turns 4 > discussion.txt
```

---

## Utility Commands

```bash
# Check what agents are available
agentpipe doctor

# List agents with details
agentpipe agents list
agentpipe agents list --json
```

---

## Tips

1. **Name your agents** - Makes conversations easier to follow: `-a claude:Skeptic -a gemini:Optimist`

2. **Use prompts to set roles** - In config files, give each agent a specific perspective

3. **Limit turns** - Start with `--max-turns 4-6` to keep conversations focused

4. **TUI for interactive** - Use `--tui` when watching live, `--no-tui` for scripts

5. **Combine with boxctl-analyst** - Use agentpipe for brainstorming, analyst MCP for deep dives

---

## When to Use AgentPipe vs Analyst MCP

| Use Case | Tool |
|----------|------|
| Multi-perspective discussion | AgentPipe |
| Deep code analysis | boxctl-analyst |
| Brainstorming approaches | AgentPipe |
| Code review with report | boxctl-analyst |
| Comparing viewpoints | AgentPipe |
| Plan verification | boxctl-analyst |

---

## Troubleshooting

### "Agent not found"
Run `agentpipe doctor` to see which agents are installed.

### Conversation stalls
Add `--timeout 60` to increase per-response timeout.

### Too verbose
Use `--max-turns 2-3` for quick comparisons.
