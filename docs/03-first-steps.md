# Getting Started

Two commands. That's all it takes.

## Your First Agent

Navigate to your project directory and initialize Boxctl:

```bash
cd ~/myproject
boxctl init              # One-time setup, creates .boxctl.yml
boxctl superclaude       # Starts container, launches agent
```

That's it. The container starts automatically, installs any configured packages, and the agent begins working. You're now talking to Claude inside an isolated environment.

## Checking On It

Connected to a running agent and want to check something else? Detach without stopping:

Press `Ctrl+A`, then `D` to detach from the tmux session. The agent keeps working.

Come back later:

```bash
boxctl connect           # Reconnect to see what it's doing
```

## When You're Done

```bash
boxctl stop              # Stop the container
```

The container stops but isn't removed. Next time you run `boxctl superclaude`, it starts up quickly because everything's already set up.

## Customizing (Optional)

Want to add packages the agent can use? Mount another directory? Enable an MCP server?

```bash
# Add packages
boxctl packages add npm typescript   # Node packages
boxctl packages add pip pytest       # Python packages
boxctl packages add apt ffmpeg       # System packages

# Mount another directory
boxctl workspace add ~/other-repo ro reference
# Now available at /context/reference/ inside the container

# Enable an MCP server
boxctl mcp add boxctl-analyst

# Pass through hardware devices (audio, GPU, serial)
boxctl devices                       # Interactive chooser
```

These commands automatically rebuild the container to apply changes. No manual `boxctl rebase` needed.

## What Happens Behind the Scenes

When you run `boxctl superclaude`:

1. **Container check** - If no container exists for this project, one is created from the base image
2. **Startup** - Container initializes: creates user, sets up SSH, installs packages
3. **Agent launch** - Claude starts in a tmux session with auto-approve permissions
4. **You're connected** - Terminal attaches to the session

The container mounts your project at `/workspace`. The agent sees your code and can make changes. Those changes appear on your host immediately - it's the same files, just accessed from inside the container.

## Next Steps

- **[Agent Types](04-dangerous-settings.md)** - Learn about interactive vs autonomous agents
- **[Parallel Work](05-parallel.md)** - Run multiple agents on different branches
- **[Mobile Workflow](06-mobile.md)** - Work from your phone
- **[Configuration](08-configuration.md)** - Deep dive into all the options

## Quick Reference

| Task | Command |
|------|---------|
| Initialize project | `boxctl init` |
| Start autonomous Claude | `boxctl superclaude` |
| Start interactive Claude | `boxctl claude` |
| Reconnect to agent | `boxctl connect` |
| Stop container | `boxctl stop` |
| See container info | `boxctl info` |
| Add package | `boxctl packages add TYPE PACKAGE` |
| Mount directory | `boxctl workspace add PATH MODE NAME` |
| Pass through devices | `boxctl devices` |
| Apply config changes | `boxctl rebase` |

See the **[CLI Reference](REF-A-cli.md)** for the complete command list.
