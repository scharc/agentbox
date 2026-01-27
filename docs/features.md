# ✨ Boxctl Features

> **Let your AI agents work while you sleep.**
>
> Safe. Autonomous. Unstoppable.

---

## 🤖 Run Any AI Agent

Pick your favorite. They all work the same way.

| Agent | Interactive | Autonomous |
|-------|-------------|------------|
| **Claude Code** | `boxctl claude` | `boxctl superclaude` |
| **OpenAI Codex** | `boxctl codex` | `boxctl supercodex` |
| **Google Gemini** | `boxctl gemini` | `boxctl supergemini` |
| **Alibaba Qwen** | `boxctl qwen` | `boxctl superqwen` |

**Interactive** = asks permission before actions
**Autonomous** = full auto-approve, works while you sleep

```bash
boxctl supercodex "build me a REST API with authentication"
boxctl superclaude "refactor the database layer"
boxctl supergemini "write comprehensive documentation"
boxctl superqwen "add internationalization support"
```

### Mix and Match
Run different agents for different tasks. All in the same project, all isolated, all safe. Use what works best for each job.

---

## 🔒 Complete Isolation

### Your System is Untouchable

Agents run in Docker containers. They see:
- ✅ `/workspace` - your project
- ✅ `/context/*` - directories you explicitly mount
- ❌ Your home directory
- ❌ Your other projects
- ❌ Your system files
- ❌ Your browser history, passwords, keys

An agent could run `rm -rf /` and your laptop wouldn't notice.

### Git is Your Safety Net

Every change is tracked. Every experiment is reversible.

```bash
# Agent went crazy?
git diff                      # See what it did
git reset --hard             # Undo everything
boxctl superclaude             # Try again
```

**Total recovery time: 10 seconds.**

### Credential Isolation

- SSH keys are **copied**, not mounted (in default mode)
- Changes to keys inside container don't affect your host
- API tokens sync for OAuth refresh, nothing else leaks
- Each container is a fresh, isolated environment

---

## 🌳 Parallel Work with Git Worktrees

### Multiple Branches, Multiple Agents, Zero Conflicts

Traditional git: one branch at a time. Switch branches, lose context, stash changes, mess up state.

Boxctl: **every branch gets its own directory**.

```bash
# Create worktrees for parallel work
boxctl worktree add feature-auth
boxctl worktree add feature-payments
boxctl worktree add hotfix-123

# Run agents on each - simultaneously
boxctl worktree superclaude feature-auth
boxctl worktree supercodex feature-payments
boxctl worktree superclaude hotfix-123

# List what's running
boxctl worktree list
```

**Three agents. Three branches. Zero interference.**

### Switch Without Stopping

Inside a conversation, the agent can switch contexts:

```bash
# Agent decides it needs to work on a different branch
agentctl worktree switch feature-payments superclaude
```

Your current agent keeps running. A new one starts on the other branch. Both work in parallel.

---

## 🎛️ agentctl: The Power Tool

### Agents That Manage Themselves

agentctl is an MCP server that's **enabled by default**. Every agent gets these superpowers out of the box - no setup required. They can manage their own environment without your help.

### Switch Branches Mid-Conversation

```
You: "Actually, let's fix that bug on the hotfix branch first"
Agent: "Switching to hotfix branch now..."
[Agent uses agentctl to switch worktrees]
Agent: "I'm now on hotfix-123. What's the bug?"
```

### Spawn Parallel Agents

```
Agent: "This is a big refactor. I'll spawn another agent
       to handle the tests while I work on the implementation."
[Agent creates new worktree and starts another agent]
```

### Detach and Continue

```
Agent: "This will take a while. I'll detach and notify you when done."
[Agent detaches, continues working in background]
[You get a notification 2 hours later]
```

### Session Management

```bash
agentctl list                         # See all sessions
agentctl attach superclaude-1        # Jump to a session
agentctl peek superclaude-1          # View without attaching
agentctl kill superclaude-1          # Stop a session
```

### Full MCP Integration

All agentctl features are available as MCP tools. Agents can:
- `switch_branch` - Move to a different branch/worktree
- `switch_session` - Jump between sessions
- `detach_and_continue` - Keep working after you disconnect
- `list_sessions` - See what's running
- `list_worktrees` - See all branches
- `set_session_task` - Label what they're working on
- `get_current_context` - Understand where they are

---

## 🤝 Multi-Agent Collaboration

### Agents Reviewing Agents

Enable the analyst MCP (opt-in):

```bash
boxctl mcp add boxctl-analyst
```

Now agents can request peer review from other AI agents:

```
Agent A: "I've implemented the auth system. Let me get a review..."
[Calls boxctl-analyst review_commit]
Agent B: "Looking at the changes... I found 3 issues:
         1. SQL injection vulnerability in login()
         2. Missing rate limiting
         3. Passwords not hashed"
Agent A: "Good catches. Fixing now..."
```

### Second Opinions on Plans

Before implementing, get validation:

```
Agent: "Here's my plan for the refactor. Let me verify with a peer..."
[Calls boxctl-analyst verify_plan]
Peer: "The plan looks solid, but consider:
       - Step 3 might break backward compatibility
       - You're missing database migrations
       - The testing strategy needs more edge cases"
```

### Multi-Agent Discussions

Run conversations between agents:

```
[Calls boxctl-analyst discuss]
Claude: "I think we should use PostgreSQL for this..."
Gemini: "Have you considered the scaling implications? Redis might..."
Claude: "Good point. What about a hybrid approach..."
```

### Test Suggestions

```
Agent: "Let me check what tests are missing..."
[Calls boxctl-analyst suggest_tests]
Peer: "Missing coverage for:
       - Edge case: empty input
       - Error handling: network timeout
       - Integration: database connection failure"
```

---

## 📱 Mobile-First Design

### Work From Anywhere

SSH into your laptop from your phone. Tailscale makes it easy.

### The Quick Menu

One command, zero typing:

```bash
boxctl q
```

```
┌────────────────────────────────────┐
│  🚀 BOXCTL QUICK MENU              │
├────────────────────────────────────┤
│                                    │
│  SESSIONS                          │
│  [1] superclaude-1 (attached)      │
│  [2] supercodex-feature            │
│  [3] shell-debug                   │
│                                    │
│  WORKTREES                         │
│  [a] main                          │
│  [b] feature-auth                  │
│  [c] hotfix-123                    │
│                                    │
│  ACTIONS                           │
│  [s] Start superclaude             │
│  [x] Start supercodex              │
│  [g] Start supergemini             │
│  [h] Start shell                   │
│  [r] Refresh                       │
│  [q] Quit                          │
│                                    │
└────────────────────────────────────┘
```

Press a key. That's it. No arrow keys, no typing, no autocomplete.

### No Flags, Ever

Every command uses positional arguments:

```bash
# Boxctl style
boxctl workspace add ~/docs ro reference
boxctl session new superclaude feature

# NOT like this (won't work)
boxctl workspace add --path ~/docs --mode ro --name reference
```

Why? Try typing `--dangerously-skip-permissions` on a phone keyboard.

---

## 🔌 Port Forwarding

### Expose Container Services

Running a dev server inside the container?

```bash
boxctl ports expose 3000
```

Now `localhost:3000` on your host shows the container's server.

### Forward Host Services

Running PostgreSQL on your laptop?

```bash
boxctl ports forward 5432
```

Now the container can reach your database.

### The Chrome Trick

**Control your browser from inside the container.**

Start Chrome with remote debugging:
```bash
google-chrome --remote-debugging-port=9222
```

Forward the port:
```bash
boxctl ports forward 9222
```

Now your agent can:
- Navigate to any page
- Fill out forms
- Click buttons
- Take screenshots
- Extract data
- Automate workflows

All through Chrome DevTools Protocol. All from inside a safe container.

### Live Port Status

```bash
boxctl ports status
```

See what's forwarded, what's exposed, what's active.

---

## 🔗 Container Networking

### Connect to Other Containers

Running services in Docker? Connect them:

```bash
# Your existing containers
docker ps
# NAMES: postgres-dev, redis-cache, elasticsearch

# Connect boxctl to them
boxctl network connect postgres-dev
boxctl network connect redis-cache
```

Now your agent can reach `postgres-dev:5432` and `redis-cache:6379` directly.

### Service Discovery

Agents can interact with your entire Docker ecosystem:
- Databases
- Message queues
- Search engines
- API mocks
- Microservices

All accessible by container name.

---

## 🔑 Zero-Config Credentials

### Authenticate Once, Work Everywhere

Sign in on your host. Every container inherits access.

| Service | Host Path | What Happens |
|---------|-----------|--------------|
| **Claude** | `~/.claude/` | OAuth tokens sync, auto-refresh works |
| **Codex** | `~/.codex/` | Auth tokens available immediately |
| **OpenAI** | `~/.config/openai/` | API keys ready to use |
| **Gemini** | `~/.config/gemini/` | Google auth inherited |
| **Qwen** | `~/.qwen/` | Alibaba auth ready |
| **Git** | Environment | Author name/email preserved |
| **SSH** | Configurable | Keys copied or agent forwarded |

### CLI Tools (Opt-In)

Enable GitHub CLI:
```yaml
credentials:
  gh: true
```

Now `gh pr create` works inside the container with your GitHub auth.

Enable GitLab CLI:
```yaml
credentials:
  glab: true
```

Now `glab mr create` works with your GitLab auth.

### SSH Flexibility

Choose your security level:

```yaml
ssh:
  mode: keys          # Copy keys into container (default, isolated)
  mode: mount         # Mount ~/.ssh directly (convenient)
  mode: config        # Config only, use agent forwarding
  mode: none          # No SSH access
  forward_agent: true # Forward SSH agent socket
```

---

## 📦 Package Management

### Add Anything

```bash
# Node packages
boxctl packages add npm typescript eslint prettier webpack

# Python packages
boxctl packages add pip pytest black mypy flask django

# System packages
boxctl packages add apt ffmpeg imagemagick pandoc graphviz

# Rust tools
boxctl packages add cargo ripgrep fd-find bat
```

### Auto-Rebuild

Packages are tracked in config. Change them and run:

```bash
boxctl rebase
```

Container rebuilds with new packages. State preserved.

### Pre-Installed Tools

Every container comes with:
- Git, GitHub CLI, GitLab CLI
- Node.js, npm, yarn
- Python, pip, Poetry
- Rust, cargo
- Docker CLI (if enabled)
- tmux, vim, curl, jq
- And more...

---

## 📁 Workspace Mounts

### Mount Anything, Anywhere

```bash
# Mount a reference project (read-only)
boxctl workspace add ~/other-project ro reference

# Mount a data directory (read-write)
boxctl workspace add ~/datasets rw data

# Mount documentation
boxctl workspace add ~/company-docs ro docs
```

### Inside the Container

```
/workspace           → Your project (read-write)
/context/reference   → other-project (read-only)
/context/data        → datasets (read-write)
/context/docs        → company-docs (read-only)
```

### Why Read-Only?

Reference code shouldn't be modified. Mount it read-only and your agent can read but not break anything.

---

## 🎮 Device Passthrough

### Hardware Access

Give agents access to real devices:

```bash
# Audio devices
boxctl devices add /dev/snd

# GPU (for ML, rendering)
boxctl devices add /dev/dri/renderD128

# Serial ports (for embedded development)
boxctl devices add /dev/ttyUSB0

# Cameras
boxctl devices add /dev/video0
```

### Interactive Selection

Not sure what's available?

```bash
boxctl devices
```

Interactive chooser shows detected devices:
- 🔊 Audio devices
- 🎮 GPU/Graphics
- 🔌 Serial ports
- 📷 Cameras

Select what you need. Config updates automatically.

### Graceful Handling

Device went offline? Container starts anyway - missing devices are skipped.

---

## 🔔 Desktop Notifications

### Never Miss a Beat

```bash
boxctl service install
```

Get notified when:
- ✅ Agent completes a task
- ⏸️ Agent appears stalled
- ❓ Agent asks a question
- ⚠️ Something needs attention

### Smart Summaries

Notifications include AI-generated summaries:
- Short version for desktop popups
- Long version for Telegram/webhook

### Multi-Channel

- Desktop notifications (notify-send)
- Telegram bot integration
- Webhook support (Slack, Discord, etc.)

---

## 💬 Sessions

### Multiple Agents, One Container

```bash
# Start different agents for different tasks
boxctl session new superclaude research
boxctl session new supercodex implementation
boxctl session new supergemini documentation
boxctl session new shell debugging
```

### Quick Navigation

```bash
boxctl session list                    # See all sessions
boxctl session attach research         # Jump to one
boxctl session attach implementation   # Switch to another
```

### Persistent State

Sessions survive disconnection. SSH drops? Resume where you left off:

```bash
boxctl connect
```

---

## 📜 Conversation Logs

### Full History

Every conversation is logged:

```bash
boxctl logs list
```

```
SESSION              AGENT       STARTED              FILE
superclaude-1        claude      2024-01-25 10:30     claude/sessions/abc123.jsonl
supercodex-feature   codex       2024-01-25 09:15     codex/sessions/def456.jsonl
```

### Quick View

```bash
boxctl logs show superclaude-1
```

See recent messages, timestamped, role-labeled.

### Export to Markdown

```bash
boxctl logs export superclaude-1
```

Creates a clean markdown document:
- Session metadata
- Full conversation
- Timestamps
- Tool calls

Perfect for documentation, review, or sharing.

---

## 🤖 Non-Interactive Mode

### Script Everything

```bash
boxctl run superclaude "add unit tests for the API"
```

- No tmux
- No TTY required
- Output to stdout
- Exit codes for scripting

### CI/CD Integration

```bash
#!/bin/bash
boxctl run superclaude "fix linting errors"
if [ $? -eq 0 ]; then
    git add -A && git commit -m "Auto-fix linting"
fi
```

### Capture Output

```bash
output=$(boxctl run claude "explain this function" 2>&1)
echo "$output" > explanation.md
```

---

## 🐳 Docker-in-Docker

### Full Docker Access

Enable Docker socket:

```bash
boxctl docker enable
```

Now your agent can:
- Build images
- Run containers
- Manage Docker Compose stacks
- Deploy applications

### Use With Caution

Docker access means container escape is possible. Only enable for trusted tasks.

---

## 🛡️ Security Controls

### Seccomp Profiles

```yaml
security:
  seccomp: unconfined    # Default, needed for some tools
  seccomp: default       # Stricter, may break some features
```

### Capability Control

```yaml
security:
  capabilities:
    - SYS_PTRACE         # For debugging
    - NET_ADMIN          # For network tools
```

### Read-Only Mounts

Sensitive directories are mounted read-only by default:
- Credential directories
- Reference workspaces (when specified)
- System configs

---

## ⚙️ Configuration

### Everything in One File

`.boxctl/config.yml`:

```yaml
# Packages to install
packages:
  npm: [typescript, eslint]
  pip: [pytest, black]
  apt: [ffmpeg]

# Extra directories to mount
workspaces:
  - path: ~/other-project
    mode: ro
    name: reference

# Port configuration
ports:
  expose: [3000, 8080]
  forward: [5432, 6379]

# SSH settings
ssh:
  mode: keys
  forward_agent: false

# Credentials
credentials:
  gh: true
  glab: false

# Docker access
docker: false

# Devices
devices:
  - /dev/snd
```

### Interactive Setup

Don't like editing YAML?

```bash
boxctl reconfigure
```

Walk through every option interactively.

---

## 🚀 Quick Commands

| Command | What it does |
|---------|--------------|
| `boxctl superclaude` | Start autonomous Claude |
| `boxctl q` | Quick menu (mobile-friendly) |
| `boxctl list` | List containers |
| `boxctl info` | Container details |
| `boxctl stop` | Stop container |
| `boxctl connect` | Reconnect to session |
| `boxctl shell` | Open bash |
| `boxctl rebase` | Rebuild with config changes |
| `boxctl logs show` | View conversation |
| `boxctl worktree list` | List branches |

---

## 💡 The Philosophy

### Built for Real Work

Boxctl isn't a demo or proof-of-concept. It's what I use every single day.

Every feature exists because I hit a wall:
- Needed Chrome automation → port forwarding
- Needed parallel branches → worktree integration
- Needed GitHub releases → gh credential mounting
- Needed mobile access → quick menu with single-key navigation

### No Flags

Positional arguments only. Because phone keyboards are terrible for typing `--dangerously-skip-permissions`.

### Fail Safe

The worst case is always recoverable:
- Container broke? `boxctl remove && boxctl superclaude`
- Agent went crazy? `git reset --hard`
- Config messed up? Delete `.boxctl/`, start fresh

### Your Feature Next

Using Boxctl and need something? [Open an issue](https://github.com/scharc/boxctl/issues) with your story. If it makes sense, it gets built.

---

## 🏁 Get Started

```bash
# Clone and install
git clone git@github.com:scharc/boxctl.git
cd boxctl
bash bin/setup.sh --shell zsh

# Initialize your project
cd ~/your-project
boxctl init

# Start working
boxctl superclaude "let's build something amazing"
```

**Your agent is ready. What will you build?**
