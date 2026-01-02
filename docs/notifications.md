# Notifications

How autonomous agents send desktop notifications to ask for help.

## The Problem

You start an autonomous agent with `abox superclaude`, give it a task, and detach. It works in the background.

Eventually it hits a decision point: "Should I delete these old migration files?" It needs your input, but you're not watching the terminal.

Desktop notifications solve this. The agent sends a notification to your desktop, you see it, you reattach and answer.

## How It Works

```
Agent in container → notify MCP → Unix socket → Proxy on host → notify-send → Your desktop
```

The agent uses the notify MCP server to send messages. Those go through a Unix socket to a proxy running on your host. The proxy calls `notify-send` and you see a desktop notification.

## Setup

Install the notification proxy as a systemd user service:

```bash
agentbox proxy install --enable
```

This creates `~/.config/systemd/user/agentbox-proxy.service` and starts it.

Check if it's running:

```bash
systemctl --user status agentbox-proxy
```

That's it. Notifications are available, but only enabled when a session opts in.

## Using It

Notifications are enabled automatically for `super*` sessions. For normal sessions,
opt in with `--notify`:

```bash
agentbox superclaude
agentbox claude --notify
```

If an agent sends a notification, it should also include the same message in the
chat context so it isn't lost when the notification expires.

Urgency levels: `low`, `normal`, `high`, `critical`

Critical notifications play an audio alert.

## The Flow

The notify MCP server ships with Agentbox but only exposes tools when the session
sets `AGENTBOX_NOTIFY=1` (super* does this automatically).

The notify MCP server lives at `library/mcp/notify/server.py`. It connects to a Unix socket at `/home/abox/.agentbox/notify.sock` inside the container.

That socket is a symlink pointing to `/run/user/<your-uid>/agentbox-notify.sock` on the host, which is mounted read-only into the container.

The proxy daemon listens on that socket. When it receives a message, it calls `notify-send` on the host with the title, message, and urgency level.

Your desktop notification daemon (dunst, mako, or whatever you use) shows the notification.

## Why This Design?

**Unix socket instead of HTTP**: Faster, simpler, more secure. File permissions control access, no network exposure.

**Systemd user service**: Runs as your user (not root), starts on login, auto-restarts on failure, integrates with journalctl for logs.

**Read-only mount**: The container mounts `/run/user/<uid>` read-only. It can connect to the socket but can't modify or delete it.

**Hard-coded paths**: We control the container build, so paths are known and stable. No environment variables, no configuration files, just works.

**Symlink for stability**: The socket is created by the proxy on the host. Inside the container, a symlink points to it. If the proxy restarts, the symlink still works.

## Troubleshooting

**No notifications appear**

Check if the proxy is running:
```bash
systemctl --user status agentbox-proxy
```

If not, start it:
```bash
systemctl --user start agentbox-proxy
```

Check if the socket exists:
```bash
ls -la /run/user/$(id -u)/agentbox-notify.sock
```

Test with a notify-enabled session:
```bash
agentbox claude --notify "send a test notification"
```

**Proxy won't start**

Check logs:
```bash
journalctl --user -u agentbox-proxy -n 50
```

Common issues:
- `DISPLAY` not set (needed for notify-send)
- D-Bus session not available
- notify-send not installed

**Notifications delayed**

The proxy processes messages sequentially. If you send many at once, they queue up. This is normal.

**No audio alert on critical**

Critical notifications try to play `/usr/share/sounds/freedesktop/stereo/bell.oga` via `paplay`.

If that doesn't work, falls back to TTY bell (`\a`).

Install `pulseaudio-utils` if you want audio alerts:
```bash
sudo apt install pulseaudio-utils
```

## Managing the Service

View logs in real-time:
```bash
journalctl --user -u agentbox-proxy -f
```

Restart:
```bash
systemctl --user restart agentbox-proxy
```

Stop:
```bash
systemctl --user stop agentbox-proxy
```

Disable and uninstall:
```bash
agentbox proxy uninstall
```

## Security

The socket has `0o600` permissions (user-only read/write). Only you can connect.

The container mounts `/run/user/<uid>` read-only, so it can't modify the socket or interfere with other processes.

There's no rate limiting. A container can spam notifications. If that happens, stop the container or the proxy service.

No authentication. Any process inside the container can send notifications. But the container is isolated - you control what runs inside.

## Disabling Notifications

Stop the proxy service:
```bash
systemctl --user stop agentbox-proxy
systemctl --user disable agentbox-proxy
```

Notifications are off by default for normal sessions. If you started a `super*`
session, pass `--no-notify` to keep notifications disabled.
