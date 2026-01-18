---
description: Pause and preview next actions without executing
---

Immediately halt. Report what was about to happen WITHOUT executing it:

```
FROZEN
======
State: Halted mid-execution

About to execute:
1. [Next action that was queued]
2. [Following action]
3. [...]

Reason for planned actions:
- [Why these were next]

Awaiting: "continue" or new instruction
```

**Resume:** `continue`, `go ahead`, `proceed` - executes the queued actions.
Any other instruction cancels them.
