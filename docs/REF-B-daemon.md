# boxctld - Host Daemon

The host-side daemon that bridges containers to the desktop environment.

## What It Does

boxctld runs on your host machine and provides:

- **Desktop Notifications** - Agents send alerts that appear as native notifications
- **Port Forwarding** - SSH tunnels between host and containers
- **Shell Completions** - Fast tab-completion for CLI
- **Clipboard Access** *(WIP)* - Containers can copy to your system clipboard

Without boxctld, containers are isolated. With it, agents can notify you when tasks complete and expose services.

## Installation

```bash
# Install as systemd user service
abox service install

# Check status
abox service status

# View logs
abox service logs
abox service follow              # Real-time
```

The service auto-starts on login.

## Communication Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Host                                                        │
│                                                             │
│   boxctld                                                 │
│   ├── SSH Server (AsyncSSH)                                 │
│   │     └── /run/user/{uid}/boxctld/ssh.sock             │
│   ├── Unix Socket (local IPC)                              │
│   │     └── /run/user/{uid}/boxctld/boxctld.sock       │
│   └── Web Server (Uvicorn)                                  │
│         └── http://localhost:8080                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         │ SSH Tunnel
         │
┌────────▼────────────────────────────────────────────────────┐
│ Container                                                   │
│                                                             │
│   ContainerClient                                           │
│   ├── Connects to SSH socket (mounted from host)           │
│   ├── Sends notifications, state updates                   │
│   └── Receives port forward configs                        │
│                                                             │
│   Tools:                                                    │
│   └── /usr/local/bin/abox-notify                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

All container ↔ host communication flows through a single SSH connection per container.

## Configuration

Host config at `~/.config/boxctl/config.yml`:

```yaml
# Web server settings
web_server:
  enabled: true
  host: 127.0.0.1              # Bind address
  port: 8080
  log_level: info

# Optional: bind to Tailscale IP for remote access
# hosts: ["127.0.0.1", "tailscale"]

# Tailscale IP monitoring
tailscale_monitor:
  enabled: true
  check_interval_seconds: 60   # How often to check for IP changes

# Stall detection (notify when agent idle)
stall_detection:
  enabled: true
  threshold_seconds: 30

# Custom notification hook
# notify_hook: ~/.config/boxctl/notify-hook.sh
```

## Capabilities

### Desktop Notifications

Containers send notifications via `abox-notify`:

```bash
# Inside container
abox-notify "Build Complete" "All tests passed" normal
abox-notify "Error" "Build failed" critical
```

On host:
- Uses `notify-send` (Linux)
- Critical notifications play sound via `paplay`
- Custom hook script runs if configured

**Custom Hook:**

```bash
# ~/.config/boxctl/notify-hook.sh
#!/bin/bash
TITLE="$1"
MESSAGE="$2"
URGENCY="$3"

# Example: send to phone via ntfy
curl -d "$MESSAGE" "ntfy.sh/my-boxctl-alerts"
```

### Clipboard Access *(WIP)*

> **Note:** This feature is work-in-progress and may not be fully functional.

Containers copy to host clipboard:

```bash
# Inside container
echo "some text" | abox-clipboard
abox-clipboard < file.txt
```

Auto-detects clipboard tool:
- `wl-copy` (Wayland)
- `xclip` (X11)
- `xsel` (X11 fallback)

### Port Forwarding

Two directions:

**Expose (container → host):** Service runs in container, access from host.

```bash
# From host CLI
abox ports expose 3000              # container:3000 → host:3000

# What happens:
# 1. boxctld creates SSH remote forward
# 2. Listening on host:3000
# 3. Traffic tunneled to container:3000
```

**Forward (host → container):** Service runs on host, access from container.

```bash
# From host CLI
abox ports forward 9222             # host:9222 → container:9222

# What happens:
# 1. boxctld creates SSH local forward
# 2. Container can connect to localhost:9222
# 3. Traffic tunneled to host:9222
```

### Terminal Streaming

Real-time session content for web UI:

1. Container registers session via `stream_register`
2. Pushes buffer updates via `stream_data`
3. Web server subscribes to streams
4. Updates pushed to browser via WebSocket

Used by the web terminal at `http://localhost:8080`.

### Shell Completions

Fast tab-completion for CLI. boxctld caches:

- Connected container names
- Active tmux sessions
- Git worktrees
- MCP server names
- Skill names
- Docker container names

When you type `abox session attach <TAB>`, the CLI queries boxctld instead of running slow Docker commands.

## Tailscale Support

boxctld monitors Tailscale IP changes:

1. Background thread checks `tailscale ip -4` periodically
2. If IP changes, web server rebinds
3. Enables remote access via Tailscale

Configure in `~/.config/boxctl/config.yml`:

```yaml
web_server:
  hosts: ["127.0.0.1", "tailscale"]  # Bind to both
  port: 8080

tailscale_monitor:
  enabled: true
  check_interval_seconds: 60
```

Access from phone: `http://<tailscale-ip>:8080`

## Debugging

Run in foreground:

```bash
abox service serve
```

Shows all requests, connections, errors in terminal.

Check what's connected:

```bash
abox ports status                   # Active tunnels
abox service status                 # Service health
```

View logs:

```bash
abox service logs 100               # Last 100 lines
journalctl --user -u boxctld -f   # Full systemd logs
```

## Protocol Reference

For details on the SSH tunnel protocol and message formats, see [tunnel-protocol.md](REF-D-tunnel.md).

## Container Tools

### abox-notify

```bash
abox-notify TITLE MESSAGE [URGENCY]
```

- `TITLE` - Notification title
- `MESSAGE` - Notification body
- `URGENCY` - `normal` (default) or `critical`

### abox-clipboard

```bash
echo "text" | abox-clipboard
abox-clipboard < file.txt
```

Copies stdin to host clipboard.

## API Functions

For developers integrating with boxctld:

| Function | Purpose |
|----------|---------|
| `get_connected_containers()` | List containers with active SSH connections |
| `get_host_ports()` | List active port forwards |
| `is_host_port_active(port)` | Check if port has active tunnel |
| `get_tunnel_stats()` | Connection statistics |
| `send_input(container, session, keys)` | Send keystrokes to session |
| `subscribe_to_stream(container, session, cb)` | Subscribe to terminal updates |
| `get_cached_buffer(container, session)` | Get last known terminal content |

## See Also

- [CLI Reference](REF-A-cli.md) - `abox service` commands
- [Tunnel Protocol](REF-D-tunnel.md) - SSH protocol details
- [Configuration](08-configuration.md) - Full config reference
