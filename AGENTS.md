# Agent Context

<!-- AGENTBOX:BEGIN -->
## Agentbox Managed Context

### Workflow
- Commit often.
- Keep a log in `.agentbox/LOG.md`.

### MCP
- MCP servers: notify
- Skills: _none_

### Human Interaction
- You are allowed to use `/usr/local/bin/notify`.
- Use it to request human input or confirmation instead of blocking on questions.
- Always send a notification if you have a question for the human.
- Include a concise title and a clear next action for the human.

### Allowed Commands
- `/usr/local/bin/notify`

### Context Files
- `PLAN.md` (if present).

### Context Mounts
Extra context paths are mounted under `/context/<name>`.

_No extra context mounts configured._

<!-- AGENTBOX:END -->
## Notes
### Decision Rationale (Non-Code)
- Project-centric `.agentbox/` keeps config/state versioned alongside projects; avoids global drift.
- Bash default maximizes compatibility across hosts and containers.
- Polling config sync chosen over inotify for portability across filesystems/mounts.
- Default deny Docker socket; enable only when Docker MCP is used to limit host exposure.
- Notify-on-questions workflow reduces blocking and keeps humans in the loop.
