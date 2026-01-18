# Agent Types

Not all agents are the same. You choose based on how much autonomy you want to give them.

## Interactive Agents (Ask Permission)

```bash
agentbox claude                    # Claude Code
agentbox codex                     # OpenAI Codex
agentbox gemini                    # Google Gemini
```

Interactive agents ask permission before running commands or editing files. They show you what they want to do and wait for your approval.

**Use these when:**
- Exploring an unfamiliar codebase
- Working on sensitive code
- Learning what the agent does
- You want to review each change before it happens

The tradeoff: more control, but you need to be present. The agent can't make progress while you're away.

## Autonomous Agents (Auto-Approve)

```bash
agentbox superclaude               # Claude with --dangerously-skip-permissions
agentbox supercodex                # Codex autonomous
agentbox supergemini               # Gemini autonomous
```

Autonomous agents execute without asking. They make changes, run commands, fix their mistakes, and keep going.

**Use these when:**
- You have a well-defined task ("add tests for the auth module")
- You trust the agent with the codebase
- You want hands-off execution
- You're stepping away and want work to continue

The tradeoff: less control, but the agent can work independently. You come back to completed work instead of a list of pending approvals.

### Why the "Super" Prefix?

The "super" in `superclaude` signals elevated permissions. It's a visual reminder that this agent operates differently. Just like `sudo` makes you think twice, `superclaude` should make you consider whether this task is appropriate for autonomous execution.

## Shell (No Agent)

```bash
agentbox shell                     # Just bash
```

Opens a shell inside the container with no AI. Useful for:
- Manual debugging
- Running commands yourself
- Checking the container environment
- Installing things manually

## How They Differ Internally

Interactive and autonomous agents use different configurations:

| Aspect | Interactive | Autonomous |
|--------|-------------|------------|
| Config file | `config.json` | `config-super.json` |
| Instructions | `agents.md` | `agents.md` + `superagents.md` |
| Permissions | Asks for each action | Auto-approves everything |

The `superagents.md` file contains additional instructions for autonomous behavior - things like "commit frequently," "notify on completion," and "don't ask, just do."

## Choosing the Right Agent

**Start interactive, graduate to autonomous.**

When working on something new, start with `agentbox claude`. Watch what the agent does. Get comfortable with its patterns. See how it handles your codebase.

Once you trust it with a type of task - say, writing tests or refactoring - switch to `agentbox superclaude` for that work. The agent works faster, and you can do other things.

**Match autonomy to task clarity.**

Vague tasks ("improve this code") are better for interactive agents. You'll want to guide the direction.

Clear tasks ("add input validation to the user registration form") are great for autonomous agents. There's less ambiguity about what success looks like.

**Consider your availability.**

Going to be away? Use autonomous. You'll come back to progress instead of a paused agent waiting for permission.

Sitting at your desk? Either works. Interactive gives you more control; autonomous lets you multitask.

## Multiple Agents

You can run multiple agents simultaneously - that's covered in [Parallel Work](05-parallel.md). But here's a preview:

```bash
agentbox superclaude                      # Main branch
agentbox session new superclaude feature  # Feature branch
agentbox session new codex tests          # Different agent for tests
```

Three agents, working in parallel, each in their own session. Mix and match agent types based on what each task needs.

## What's Next

- **[Parallel Work](05-parallel.md)** - Run multiple agents simultaneously
- **[Configuration](08-configuration.md)** - Customize agent instructions
- **[CLI Reference](REF-A-cli.md)** - All agent commands
