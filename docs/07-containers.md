# Container Management

Day-to-day operations for managing your Agentbox containers.

## Listing Containers

See what's running:

```bash
agentbox list                      # Running containers
agentbox list all                  # Include stopped containers
agentbox ps                        # Alias for list
```

Output shows container name, status, project directory, and active sessions.

## Container Info

Get details about a specific container:

```bash
agentbox info                      # Current project's container
agentbox info myproject            # Specific project
```

This shows:
- Container status and IP
- Mounted volumes
- Active sessions
- Configured MCPs
- Port mappings
- Resource limits

## Starting and Stopping

Usually you don't need explicit start/stop - `agentbox superclaude` handles it. But when you do:

```bash
agentbox start                     # Start container for current project
agentbox stop                      # Stop current project's container
agentbox stop myproject            # Stop specific project
```

**Stopping is graceful.** The container stops but isn't removed. Your session state, installed packages, and configuration stay intact. Next start is fast.

**Stopped containers persist.** They take disk space but no CPU/memory. List them with `agentbox list all`.

## Removing Containers

When you want to clean up:

```bash
agentbox remove                    # Remove current project's container
agentbox remove myproject          # Remove specific project
agentbox remove myproject force    # Skip confirmation
```

This deletes the container and its state. Your project files are safe - they live on your host, just mounted into the container.

**Bulk cleanup:**

```bash
agentbox cleanup                   # Remove ALL stopped containers
```

Use this periodically to free disk space from old containers.

## Rebuilding

Two types of rebuilds serve different purposes:

### Rebase (Common)

```bash
agentbox rebase                    # Rebuild current project's container
agentbox rebase all                # Rebuild all projects
```

**When to use:** After changing `.agentbox.yml` - adding packages, changing mounts, enabling MCPs.

**What happens:** Container is recreated with new configuration. Your project files stay the same. Installed packages are reinstalled according to config.

### Rebuild Base Image (Rare)

```bash
agentbox rebuild
```

**When to use:** Almost never. Only after updating Agentbox itself, or when the base image needs changes.

**What happens:** Rebuilds the `agentbox-base:latest` Docker image from scratch. Takes longer. All project containers need rebasing afterward.

## Port Management

Expose container ports to your host:

```bash
agentbox ports list                # Show current project's port config
agentbox ports list all            # Show ports across all containers
agentbox ports expose 3000         # container:3000 -> host:3000
agentbox ports expose 3000 8080    # container:3000 -> host:8080
agentbox ports unexpose 3000       # Remove exposed port
```

Forward host ports into the container:

```bash
agentbox ports forward 5432        # host:5432 -> container:5432
agentbox ports unforward 5432      # Remove forwarded port
```

**Key insight:** These work without container restart. The SSH tunnel handles dynamic port forwarding. Docker's native port mapping requires a rebuild.

## Docker Socket Access

Give the agent access to Docker itself:

```bash
agentbox docker status             # Is it enabled?
agentbox docker enable             # Grant Docker access
agentbox docker disable            # Revoke access
agentbox rebase                    # Apply changes
```

**Use with caution.** With Docker socket access, the agent can create containers, run arbitrary images, and affect your host's Docker environment. Only enable when the agent genuinely needs it.

## Lifecycle Summary

```
init → start → [work] → stop → (remove)
        ↑                ↓
        └─── rebase ─────┘
```

1. **Init** creates configuration
2. **Start** creates/starts container
3. **Work** happens in running container
4. **Stop** pauses the container (state preserved)
5. **Rebase** rebuilds with new config
6. **Remove** deletes container (optional cleanup)

## Tips

**Name your projects clearly.** Container names derive from project directory names. `~/projects/my-app` becomes `agentbox-my-app`.

**Rebase after config changes.** Editing `.agentbox.yml` doesn't automatically apply. Run `agentbox rebase` to apply changes.

**Use cleanup periodically.** Old stopped containers accumulate. `agentbox cleanup` frees disk space.

**Check info when confused.** `agentbox info` shows everything about the container. Useful for debugging.

## What's Next

- **[Configuration](08-configuration.md)** - All `.agentbox.yml` options
- **[CLI Reference](REF-A-cli.md)** - Complete command reference
