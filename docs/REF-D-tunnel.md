# SSH Tunnel Protocol

## Overview

Boxctl uses **SSH-based tunneling** for all container-host communication. A single SSH connection provides:

- **Control Channel**: Bidirectional JSON messages for notifications, streaming, port management
- **Port Forwarding**: Native SSH -L/-R forwards for data tunnels

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Host                                                            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ boxctld                                                │   │
│  │  └── SSHTunnelServer (AsyncSSH on Unix socket)           │   │
│  │       ├── Control Channel (JSON over SSH session)        │   │
│  │       │    ├── Notifications                             │   │
│  │       │    ├── Clipboard                                 │   │
│  │       │    ├── Streaming (terminal data)                 │   │
│  │       │    ├── Port management (dynamic add/remove)      │   │
│  │       │    ├── State updates (worktrees)                 │   │
│  │       │    └── Health checks (ping/pong)                 │   │
│  │       │                                                  │   │
│  │       └── Port Forwards (native SSH)                     │   │
│  │            ├── Local (-L): Container → Host              │   │
│  │            └── Remote (-R): Host → Container             │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              │ SSH over Unix Socket             │
│                              │ /run/user/UID/boxctld/ssh.sock │
└──────────────────────────────┼──────────────────────────────────┘
                               │
┌──────────────────────────────┼──────────────────────────────────┐
│ Container                    │                                  │
│  ┌───────────────────────────▼─────────────────────────────┐   │
│  │ ContainerClient (or SSHTunnelClient)                     │   │
│  │  ├── Control Channel (JSON messages)                     │   │
│  │  │    ├── Send notifications                             │   │
│  │  │    ├── Stream terminal data                           │   │
│  │  │    ├── Receive keyboard input                         │   │
│  │  │    └── Report state changes                           │   │
│  │  │                                                       │   │
│  │  └── Port Forwards                                       │   │
│  │       ├── Local: localhost:PORT → host:PORT              │   │
│  │       └── Remote: host:PORT → localhost:PORT             │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Control Protocol

### Message Framing

All control messages use **length-prefixed JSON**:

```
┌──────────────────┬─────────────────────────────────┐
│ Length (4 bytes) │ JSON payload (UTF-8)            │
│ big-endian u32   │                                 │
└──────────────────┴─────────────────────────────────┘
```

### Message Envelope

```json
{
  "kind": "request" | "response" | "event",
  "type": "<message_type>",
  "id": "<uuid>",        // Required for request/response
  "ts": 1234567890.123,  // Unix timestamp
  "payload": { ... }
}
```

### Message Types

#### Requests (expect response)

| Type | Direction | Payload | Description |
|------|-----------|---------|-------------|
| `notify` | C→H | `{title, message, urgency?, metadata?}` | Desktop notification |
| `clipboard_set` | C→H | `{data, selection?}` | Set host clipboard |
| `get_completions` | C→H | `{types: [...]}` | Get CLI completions |
| `port_add` | C→H | `{direction, host_port, container_port}` | Add port forward |
| `port_remove` | C→H | `{direction, host_port}` | Remove port forward |
| `ping` | C→H | `{}` | Health check |

#### Events (no response)

| Type | Direction | Payload | Description |
|------|-----------|---------|-------------|
| `stream_register` | C→H | `{session}` | Register terminal session |
| `stream_data` | C→H | `{session, data, cursor_x, cursor_y, ...}` | Terminal buffer update |
| `stream_unregister` | C→H | `{session}` | Unregister session |
| `stream_input` | H→C | `{session, keys, literal?}` | Keyboard input to tmux |
| `state_update` | C→H | `{worktrees: [...]}` | Git worktree state |

#### Responses

```json
{
  "kind": "response",
  "type": "<original_request_type>",
  "id": "<matching_request_id>",
  "ts": 1234567890.123,
  "payload": {
    "ok": true | false,
    "error": "...",      // If ok=false
    "data": { ... }      // Response data if any
  }
}
```

## Port Forwarding

### Local Forwards (Container → Host)

Access host services from inside containers:

```yaml
# .boxctl.yml
ports:
  container:
    - name: playwright
      port: 9100
    - name: custom-mcp
      port: 9200
```

Container can access `localhost:9100` which tunnels to `host:9100`.

### Remote Forwards (Host → Container)

Expose container services to the host:

```yaml
# .boxctl.yml
ports:
  host:
    - "3000"        # Expose container:3000 on host:3000
    - "8080:3000"   # Expose container:3000 on host:8080
```

External clients connect to `host:3000` which tunnels to `container:3000`.

## Security

### Port Restrictions

- Ports below 1024 are **not allowed**
- Host allowlist: Only `127.0.0.1` and `localhost` for local forwards
- Bind addresses: Remote forwards bind on configured addresses (localhost + Tailscale)

### Authentication

- Uses "none" auth - Unix socket permissions provide security
- Socket created with mode 0600 (owner-only access)
- No SSH keys required for local container-to-host communication

## Dynamic Port Management

Ports can be added/removed at runtime via control channel:

```json
// Add remote forward
{"kind": "request", "type": "port_add", "payload": {"direction": "remote", "host_port": 3000, "container_port": 3000}}

// Remove
{"kind": "request", "type": "port_remove", "payload": {"direction": "remote", "host_port": 3000}}
```

## Implementation Files

| File | Description |
|------|-------------|
| `boxctl/ssh_tunnel.py` | SSH server and client implementation |
| `boxctl/container_client.py` | Unified container client (streaming + tunnel) |
| `boxctl/boxctld.py` | Host daemon with SSH handlers |
| `boxctl/notifications.py` | Notification client (SSH + legacy fallback) |

## Benefits of SSH-based Design

1. **Single connection** - One SSH socket handles everything
2. **Native multiplexing** - SSH handles channel management
3. **Efficient binary transfer** - No base64 encoding overhead
4. **Built-in keepalives** - SSH handles connection health
5. **Standard protocol** - Well-tested, secure implementation
6. **Unified reconnect** - One reconnection restores all state
