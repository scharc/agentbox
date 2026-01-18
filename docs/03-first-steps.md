# Getting Started

Two commands. That's all it takes.

## Your First Agent

Navigate to your project directory and initialize Agentbox:

```bash
cd ~/myproject
agentbox init              # One-time setup, creates .agentbox.yml
agentbox superclaude       # Starts container, launches agent
```

That's it. The container starts automatically, installs any configured packages, and the agent begins working. You're now talking to Claude inside an isolated environment.

## Checking On It

Connected to a running agent and want to check something else? Detach without stopping:

Press `Ctrl+A`, then `D` to detach from the tmux session. The agent keeps working.

Come back later:

```bash
agentbox connect           # Reconnect to see what it's doing
```

## When You're Done

```bash
agentbox stop              # Stop the container
```

The container stops but isn't removed. Next time you run `agentbox superclaude`, it starts up quickly because everything's already set up.

## Customizing (Optional)

Want to add packages the agent can use? Mount another directory? Enable an MCP server?

```bash
# Add packages
agentbox packages add npm typescript   # Node packages
agentbox packages add pip pytest       # Python packages
agentbox packages add apt ffmpeg       # System packages

# Mount another directory
agentbox workspace add ~/other-repo ro reference
# Now available at /context/reference/ inside the container

# Enable an MCP server
agentbox mcp add agentbox-analyst

# Pass through hardware devices (audio, GPU, serial)
agentbox devices                       # Interactive chooser
```

These commands automatically rebuild the container to apply changes. No manual `agentbox rebase` needed.

## What Happens Behind the Scenes

When you run `agentbox superclaude`:

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
| Initialize project | `agentbox init` |
| Start autonomous Claude | `agentbox superclaude` |
| Start interactive Claude | `agentbox claude` |
| Reconnect to agent | `agentbox connect` |
| Stop container | `agentbox stop` |
| See container info | `agentbox info` |
| Add package | `agentbox packages add TYPE PACKAGE` |
| Mount directory | `agentbox workspace add PATH MODE NAME` |
| Pass through devices | `agentbox devices` |
| Apply config changes | `agentbox rebase` |

See the **[CLI Reference](REF-A-cli.md)** for the complete command list.
