# Remote Q&A Feature Design

## Overview

Enable agents to notify users remotely (Telegram, Slack, etc.) when waiting for input, summarize the question using AI, receive answers, and optionally let AI auto-answer easy decisions.

## Problem Statement

When running agents autonomously (especially with `detach_and_continue`), the agent may stall waiting for user input. Currently:
- Desktop notifications work (if you're at your computer)
- No way to answer from mobile/remote
- No way to know what question the agent is asking without checking the session

## Goals

1. **Detect input-waiting state** - Know when an agent is waiting for user input (not just slow/thinking)
2. **Summarize questions** - Use AI to extract and summarize what's being asked
3. **Remote notifications** - Send questions via Telegram/Slack/webhook
4. **Remote responses** - Receive answers and inject them into the session
5. **AI auto-answer** - Let AI decide easy/obvious questions automatically

## Existing Building Blocks

### Session Streaming (`agentboxd.py`)
```python
# Already have real-time buffer data pushed from containers
self.session_buffers[container][session] = {
    "buffer": data,      # Terminal content
    "cursor_x": ...,
    "cursor_y": ...,
    "pane_width": ...,
    "pane_height": ...,
}
```

### Input Injection (`agentboxd.py`)
```python
# Already can send input to sessions
def send_input_to_daemon(container, session, keys, literal=True)
```

### AI-Enhanced Notifications (`bin/abox-notify`)
```yaml
# Already have task_agents config for AI summarization
task_agents:
  enabled: true
  agent: claude
  model: haiku
  prompt_template: "..."
```

### Stall Detection
- `AGENTBOX_STALL_BUFFER` env var passed to hooks
- Captures last N lines when agent appears stuck

### Notify Hook (`agentboxd.py`)
```python
def _run_notify_hook(self, title, message, urgency):
    # Runs user-defined hook script with notification data
```

## Architecture

### Phase 1: Input Detection

Detect when an agent is waiting for input vs. just processing.

**Approach: Pattern matching on buffer content**

```python
INPUT_PATTERNS = [
    # Claude Code patterns
    r'\? .+\?$',                    # Question ending with ?
    r'Select an option:',
    r'\[Y/n\]',
    r'\[y/N\]',
    r'Enter .+:',
    r'Press Enter to continue',

    # Generic CLI patterns
    r'password:',
    r'passphrase:',
    r'\(yes/no\)',
]

def detect_input_waiting(buffer: str) -> tuple[bool, str | None]:
    """
    Returns (is_waiting, question_text)
    """
    # Check last few lines for input patterns
    last_lines = buffer.split('\n')[-5:]
    for line in last_lines:
        for pattern in INPUT_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                return True, extract_question_context(buffer)
    return False, None
```

**Considerations:**
- False positives: Output that looks like a question
- Solution: Combine with cursor position (at end of buffer) and idle time

### Phase 2: Remote Notification Channels

Extend the notify hook system to support multiple channels.

**Config:**
```yaml
remote_notifications:
  enabled: true
  channels:
    - type: telegram
      bot_token: ${TELEGRAM_BOT_TOKEN}
      chat_id: ${TELEGRAM_CHAT_ID}
    - type: slack
      webhook_url: ${SLACK_WEBHOOK_URL}
    - type: webhook
      url: https://your.server/notify
      method: POST
      headers:
        Authorization: Bearer ${WEBHOOK_TOKEN}
```

**Implementation Options:**

1. **Hook script approach** (simple, extensible)
   ```bash
   # ~/.config/agentbox/hooks/notify-remote.sh
   # Called by agentboxd with: title, message, urgency, context_json
   ```

2. **Built-in channel handlers** (more features)
   ```python
   class TelegramNotifier:
       def send(self, title, message, options=None, reply_callback_url=None):
           # Send with inline keyboard for quick answers
   ```

### Phase 3: Response Handling

Receive answers from remote channels and inject into sessions.

**Architecture:**

```
Telegram Bot                   Agentbox Host               Container
    |                              |                          |
    |  /answer my-project 1       |                          |
    | --------------------------> |                          |
    |                              | lookup pending question  |
    |                              | -----------------------> |
    |                              |   inject: send-keys "1"  |
    |                              | -----------------------> |
    |                              |                          |
```

**Pending Question Store:**
```python
class PendingQuestions:
    """Track questions waiting for remote answers."""

    questions: Dict[str, PendingQuestion] = {}
    # Key: "{container}/{session}" or question_id

    @dataclass
    class PendingQuestion:
        container: str
        session: str
        question_text: str
        options: list[str] | None  # ["Yes", "No"] etc
        timestamp: datetime
        expires_at: datetime
        answered: bool = False
```

**Telegram Bot Commands:**
```
/status - Show running agents and pending questions
/answer <project> <response> - Answer a pending question
/view <project> - View current session output
```

### Phase 4: AI Auto-Answer

Let AI handle obvious decisions automatically.

**Config:**
```yaml
remote_notifications:
  auto_answer:
    enabled: true
    confidence_threshold: 0.9
    allowed_patterns:
      - "Continue anyway?"
      - "Proceed with"
      - "Install .+ dependencies"
    denied_patterns:
      - "delete"
      - "remove"
      - "overwrite"
      - "push to main"
```

**Implementation:**
```python
def should_auto_answer(question: str, options: list[str], buffer: str) -> tuple[bool, str | None]:
    """
    Determine if AI should auto-answer.
    Returns (should_auto, answer) or (False, None) to ask user.
    """
    # Check against denied patterns first
    for pattern in config.denied_patterns:
        if re.search(pattern, question, re.IGNORECASE):
            return False, None

    # Ask AI for assessment
    prompt = f"""
    An agent is asking: "{question}"
    Options: {options}
    Context: {buffer[-2000:]}

    Should this be auto-answered? If yes, which option?
    Respond with JSON: {{"auto_answer": true/false, "option": "...", "confidence": 0.0-1.0, "reason": "..."}}
    Only auto-answer if:
    - The decision is clearly safe and reversible
    - The context makes the answer obvious
    - It's NOT a destructive operation
    """

    response = ask_ai(prompt)
    if response.auto_answer and response.confidence >= threshold:
        return True, response.option
    return False, None
```

## Implementation Plan

### Milestone 1: Input Detection (Foundation)
- [ ] Add `detect_input_waiting()` to agentboxd
- [ ] Track `last_activity_time` per session
- [ ] Emit "input_waiting" event when detected
- [ ] Add tests with sample buffer patterns

### Milestone 2: Remote Notifications
- [ ] Create `RemoteNotifier` base class
- [ ] Implement `TelegramNotifier`
- [ ] Add config schema for channels
- [ ] Include question context and quick-reply options

### Milestone 3: Response Handling
- [ ] Add `PendingQuestions` store to agentboxd
- [ ] Create Telegram bot command handlers
- [ ] Implement answer-to-session injection
- [ ] Add timeout/expiry for pending questions

### Milestone 4: AI Auto-Answer
- [ ] Add auto-answer config schema
- [ ] Implement pattern matching for allowed/denied
- [ ] Add AI assessment integration
- [ ] Log auto-answers for transparency

### Milestone 5: Polish
- [ ] Web UI for viewing/answering questions
- [ ] Slack integration
- [ ] Webhook integration
- [ ] History/audit log

## Security Considerations

1. **Authentication** - Telegram bot should only accept commands from verified users
2. **Rate limiting** - Prevent spam from malicious input patterns
3. **Auto-answer safeguards** - Never auto-answer destructive operations
4. **Secrets** - Bot tokens should use env vars or secret store

## Open Questions

1. Should we use a dedicated Telegram bot or a generic webhook approach?
2. How to handle multiple pending questions from the same session?
3. Should auto-answer be per-project or global config?
4. Do we need a queue for when user is slow to respond?

## Related

- `agentbox/agentboxd.py` - Session streaming, notifications
- `bin/abox-notify` - AI-enhanced notification script
- `agentbox/core/tmux.py` - Buffer capture utilities
