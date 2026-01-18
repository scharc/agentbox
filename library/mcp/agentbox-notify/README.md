# Agentbox Notify MCP Server

Send host notifications from inside the container.

## What it does

- Exposes a `notify` tool for info-level notifications
- All notifications use "normal" urgency (not critical)
- For critical alerts, super agents use hooks instead

## Usage

Add to your project:

```bash
abox mcp add notify
```

Then call the tool:

```
notify({ "title": "My Agent", "message": "Task completed" })
```

### Parameters

- `title` (string, optional) - Notification title (default: "Agentbox")
- `message` (string, required) - Notification body

## Notification Levels

| Source | Urgency | Use Case |
|--------|---------|----------|
| Notify MCP | normal | Status updates, info messages |
| Super agent hooks | critical | Alerts requiring attention |
