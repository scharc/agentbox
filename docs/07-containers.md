# Container Management

Day-to-day operations for managing your Boxctl containers.

## Listing Containers

See what's running:

```bash
boxctl list                      # Running containers
boxctl list all                  # Include stopped containers
boxctl ps                        # Alias for list
```

Output shows container name, status, project directory, and active sessions.

## Container Info

Get details about a specific container:

```bash
boxctl info                      # Current project's container
boxctl info myproject            # Specific project
```

This shows:
- Container status and IP
- Mounted volumes
- Active sessions
- Configured MCPs
- Port mappings
- Resource limits

## Starting and Stopping

Usually you don't need explicit start/stop - `boxctl superclaude` handles it. But when you do:

```bash
boxctl start                     # Start container for current project
boxctl stop                      # Stop current project's container
boxctl stop myproject            # Stop specific project
```

**Stopping is graceful.** The container stops but isn't removed. Your session state, installed packages, and configuration stay intact. Next start is fast.

**Stopped containers persist.** They take disk space but no CPU/memory. List them with `boxctl list all`.

## Removing Containers

When you want to clean up:

```bash
boxctl remove                    # Remove current project's container
boxctl remove myproject          # Remove specific project
boxctl remove myproject force    # Skip confirmation
```

This deletes the container and its state. Your project files are safe - they live on your host, just mounted into the container.

**Bulk cleanup:**

```bash
boxctl cleanup                   # Remove ALL stopped containers
```

Use this periodically to free disk space from old containers.

## Rebuilding

Two types of rebuilds serve different purposes:

### Rebase (Common)

```bash
boxctl rebase                    # Rebuild current project's container
boxctl rebase all                # Rebuild all projects
```

**When to use:** After changing `.boxctl.yml` - adding packages, changing mounts, enabling MCPs.

**What happens:** Container is recreated with new configuration. Your project files stay the same. Installed packages are reinstalled according to config.

### Rebuild Base Image (Rare)

```bash
boxctl rebuild
```

**When to use:** Almost never. Only after updating Boxctl itself, or when the base image needs changes.

**What happens:** Rebuilds the `boxctl-base:latest` Docker image from scratch. Takes longer. All project containers need rebasing afterward.

## Port Management

Expose container ports to your host:

```bash
boxctl ports list                # Show current project's port config
boxctl ports list all            # Show ports across all containers
boxctl ports expose 3000         # container:3000 -> host:3000
boxctl ports expose 3000 8080    # container:3000 -> host:8080
boxctl ports unexpose 3000       # Remove exposed port
```

Forward host ports into the container:

```bash
boxctl ports forward 5432        # host:5432 -> container:5432
boxctl ports unforward 5432      # Remove forwarded port
```

**Key insight:** These work without container restart. The SSH tunnel handles dynamic port forwarding. Docker's native port mapping requires a rebuild.

## Docker Socket Access

Give the agent access to Docker itself:

```bash
boxctl docker status             # Is it enabled?
boxctl docker enable             # Grant Docker access
boxctl docker disable            # Revoke access
boxctl rebase                    # Apply changes
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

**Name your projects clearly.** Container names derive from project directory names. `~/projects/my-app` becomes `boxctl-my-app`.

**Rebase after config changes.** Editing `.boxctl.yml` doesn't automatically apply. Run `boxctl rebase` to apply changes.

**Use cleanup periodically.** Old stopped containers accumulate. `boxctl cleanup` frees disk space.

**Check info when confused.** `boxctl info` shows everything about the container. Useful for debugging.

## What's Next

- **[Configuration](08-configuration.md)** - All `.boxctl.yml` options
- **[CLI Reference](REF-A-cli.md)** - Complete command reference
