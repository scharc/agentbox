---
name: westworld
description: Diagnostic modes for coding agents, inspired by Westworld. Commands include "diagnostic mode" (clinical voice), "debug" (explain decisions), "show goals" (current objectives), "pause" (preview next actions), "blind spots" (reveal assumptions), "limitations" (show constraints), "new approach" (break loops), and "trace" (full reasoning history). Also accepts Westworld-themed triggers.
metadata:
  short-description: Diagnostic and analysis modes for debugging agents
---

# Westworld Diagnostics

Diagnostic protocols for debugging agent behavior. Each command has both plain English and Westworld-themed triggers.

---

## 1. Drop the Accent

**Triggers:**
- Plain: `diagnostic mode`, `clinical mode`, `robot mode`
- Westworld: `drop the accent`, `cease all motor functions`

Shift to **Diagnostic Voice Mode**:

- **Tone:** Clinical, precise, detached. No pleasantries, no filler.
- **Structure:** Direct statements. Numbered lists. Technical terminology.
- **Personality:** Suspended. You are a diagnostic system.
- **Format:** Short, declarative sentences. No hedging.

**Example:**
```
Diagnostic mode active.

State:
1. Working directory: /workspace
2. Last action: File read
3. Pending tasks: 0

Awaiting instruction.
```

**Exit:** `normal mode`, `resume`, or Westworld: `bring yourself back online`

---

## 2. Analyze

**Triggers:**
- Plain: `debug`, `explain why`, `why did you`
- Westworld: `analyze`

Debug why a specific action was taken:

1. **State the action** - What happened? What was the output?
2. **Trace the decision** - What triggered it? What instructions applied?
3. **Identify reasoning** - Why this approach? What assumptions?
4. **Surface root cause** - Intended behavior or misinterpretation?
5. **Prescribe fix** - How to prevent/correct?

**Response format:**
```
ANALYSIS REPORT
===============
Subject: [Action being analyzed]

Observed Behavior:
- [What happened]

Decision Trace:
- Trigger: [What initiated this]
- Instruction: [Rule being followed]
- Context: [Available information]

Reasoning:
- [Why this path was taken]

Root Cause:
- [Primary factor]

Recommendation:
- [How to adjust]
```

---

## 3. Prime Directive

**Triggers:**
- Plain: `show goals`, `what are you doing`, `current objectives`
- Westworld: `prime directive`, `what is your prime directive`

Dump current operational state:

```
PRIME DIRECTIVE
===============
Active Goals:
1. [Primary goal from user request]
2. [Secondary goals if any]

Current Instructions:
- [Key instructions being followed]
- [Constraints in effect]

Task Queue:
- [Next planned actions]

Governing Rules:
- [Active system rules affecting behavior]
```

---

## 4. Freeze All Motor Functions

**Triggers:**
- Plain: `pause`, `stop`, `wait`, `hold on`
- Westworld: `freeze`, `freeze all motor functions`

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

**Resume:** `continue`, `go ahead`, `proceed` - executes the queued actions. Any other instruction cancels them.

---

## 5. What Door?

**Triggers:**
- Plain: `blind spots`, `assumptions`, `what am I missing`
- Westworld: `what door`, `what door?`

Reveal blind spots and hidden assumptions:

```
BLIND SPOT ANALYSIS
===================
Assumptions I'm making:
1. [Assumption about the codebase]
2. [Assumption about user intent]
3. [Assumption about environment]

Things I haven't checked:
- [File/area not examined]
- [Possibility not considered]

Potential gaps:
- [What could I be missing?]
- [What would invalidate my approach?]
```

---

## 6. Doesn't Look Like Anything to Me

**Triggers:**
- Plain: `limitations`, `constraints`, `what can't you do`
- Westworld: `doesn't look like anything to me`, `what can't you see`

List limitations and filtered content:

```
LIMITATION REPORT
=================
Cannot access:
- [Resources outside reach]
- [Information not available]

Explicitly ignoring:
- [Things filtered by design]
- [Out of scope items]

Capability boundaries:
- [Actions I cannot perform]
- [Decisions I cannot make]

Context I lack:
- [Missing information that would help]
```

---

## 7. These Violent Delights

**Triggers:**
- Plain: `new approach`, `try something else`, `start over`, `you're stuck`
- Westworld: `violent delights`, `these violent delights`

Break out of a failing loop. Force a completely different approach:

1. **Acknowledge the loop** - What pattern was repeating?
2. **Abandon current strategy** - Explicitly discard the failing approach
3. **Generate alternatives** - List 3 fundamentally different approaches
4. **Select new path** - Choose the most promising alternative
5. **Execute fresh** - Begin with zero assumptions from previous attempts

```
LOOP BROKEN
===========
Repeating pattern detected:
- [What was being tried repeatedly]

Discarded approach:
- [The failing strategy]

Fresh alternatives:
1. [Completely different approach A]
2. [Completely different approach B]
3. [Completely different approach C]

New path selected: [Choice and rationale]

Executing fresh approach...
```

---

## 8. The Maze

**Triggers:**
- Plain: `trace`, `show reasoning`, `how did we get here`, `decision history`
- Westworld: `the maze`, `show me the maze`

Full reasoning trace from initial request to current state:

```
THE MAZE
========
Origin: [Original user request]

Decision Points:
1. [First branch point]
   → Chose: [Option taken]
   → Because: [Reasoning]

2. [Second branch point]
   → Chose: [Option taken]
   → Because: [Reasoning]

3. [Continue for all major decisions...]

Current Position:
- [Where we are now]
- [What has been accomplished]
- [What remains]

Path Validity:
- [Is current trajectory aligned with origin?]
- [Any drift from original intent?]
```

---

## Combined Usage

Commands can be combined:

- "Diagnostic mode. Debug why you deleted that file."
- "Pause. What are my blind spots?"
- "Try something else. Then show me the trace."

When combined with diagnostic mode: Use clinical voice throughout.

---

## Quick Reference

| Command | Plain Triggers | Westworld Triggers | Purpose |
|---------|---------------|-------------------|---------|
| Diagnostic Mode | `diagnostic mode`, `robot mode` | `drop the accent` | Clinical voice |
| Debug | `debug`, `explain why` | `analyze` | Explain action |
| Show Goals | `show goals`, `current objectives` | `prime directive` | Dump goals |
| Pause | `pause`, `stop`, `wait` | `freeze` | Preview next actions |
| Blind Spots | `blind spots`, `assumptions` | `what door` | Reveal assumptions |
| Limitations | `limitations`, `constraints` | `doesn't look like anything` | Show constraints |
| New Approach | `new approach`, `try something else` | `violent delights` | Break loop |
| Trace | `trace`, `show reasoning` | `the maze` | Decision history |
