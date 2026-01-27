# Why Boxctl Exists

## The Promise of Autonomous AI Agents

AI coding agents like Claude, Codex, and Gemini are transforming how we write software. At their best, they can work autonomously - reading your codebase, making changes, running tests, iterating until done. You describe a problem, walk away, and come back to a solution.

The most powerful mode is **auto-approve**: let the agent execute commands and edit files without asking permission for each action. This unlocks real productivity - the agent can explore, experiment, fix its mistakes, and make progress while you do other things.

## The Fear

But nobody in their right mind gives an agent those permissions on their actual machine.

We've all heard the stories. An agent runs `rm -rf` in the wrong directory. It corrupts a git repo. It installs packages that break your system. It executes something unexpected and suddenly you're scrambling to undo the damage.

The tension is real:
- **Autonomous agents are powerful** - Let them work while you sleep, handle tedious tasks, run multiple agents in parallel
- **Autonomous agents are dangerous** - Full system access + auto-approve = potential disaster

## The Manual Solution (That Nobody Uses)

You *can* do all this yourself. Git worktrees let you run multiple agents on different branches. Docker gives you containers. But the ergonomics are terrible:

**Too many commands to remember.** Docker commands, git worktree commands, tmux sessions, port forwarding... each with their own flags and parameters. Quick, what's the command to mount a volume read-only? How do you forward a port from a container? What's the tmux keybinding to detach?

**Mobile is painful.** Command history helps you find ONE command. But workflows need many. Typing `docker exec -it container-name bash` on a phone keyboard? Flags like `--mount type=bind,source=...,target=...`? Miserable.

**No unified interface.** You're stitching together docker, git, tmux, ssh, and hoping you remember how they all connect. Context-switching between tools. Forgetting which container you're in. Losing track of what's running where.

## The Origin Story

I saw [Matt Brown](https://www.youtube.com/@mattbrwn) on YouTube do something wild: he set up a race between himself and an AI agent to reverse engineer an IoT binary exploit using Ghidra and Binary Ninja. Human vs machine, both working in parallel on the same problem.

I thought: **"I want this."**

Not just the competition - the workflow itself. An autonomous agent with:
- Full access to specialized tools (Ghidra, debuggers, whatever you need)
- Multiple directories mounted (source code, reference binaries, documentation)
- Complete isolation (can't accidentally wreck your other projects)
- Safe to detach and let it work in the background

The closest thing was Dev Containers, but those are designed for IDE workflows. I didn't want IDE coupling. I wanted something simpler: Docker for isolation, agent CLIs for execution, no editor dependencies.

## The Insight

What if we combined the safety of containers with an interface designed for how developers actually work?

**First, put agents in a jail.** A Docker container gives them a full dev environment - git, node, python, docker CLI, all the tools they need. But it contains the blast radius. If an agent goes rogue, it can only damage what's inside the container. Your system stays safe. And if you consciously choose to give the agent more power (like access to the Docker socket), that's an explicit choice you make, not an accident.

**Second, wrap it all in a simple CLI.** No flags. Positional arguments only. Designed for phone keyboards and tired brains. One command to start, one to attach, one to manage. Let the machine remember the complexity.

**Third, auto-bootstrap credentials.** Git config and API tokens (Claude, Codex, Gemini) are copied into the container on first start. No manual setup. The agent can authenticate with APIs and commit with your name. SSH keys are configurable - copy them, mount them, or use agent forwarding for hardware keys.

## A Different Way of Working

I use Boxctl as my daily driver. Here's what that looks like:

I'm at my desk working on a feature. I run `boxctl superclaude` and give it a task: "refactor the authentication module to use JWT tokens." The agent starts working - reading files, making changes, running tests.

I need to grab lunch. I pull out my phone, SSH into my laptop via Tailscale, and check on the agent through the quick menu. It's still working. I detach and put my phone away.

Later, I get a notification: task complete. I review the changes from my phone. Looks good. I tell it to commit and push.

Meanwhile, I had another idea - a bug that's been nagging me. I use the quick menu to start a second agent on a different branch. Now I have two agents working in parallel, each in their own isolated environment, each on their own branch.

This is the workflow Boxctl enables. Safe. Simple. Mobile-friendly. Let the agents work while you live your life.

## What's Next

- **[Getting Started](03-first-steps.md)** - Two commands to your first agent
- **[Architecture](02-two-worlds.md)** - How the pieces fit together
- **[Agent Types](04-dangerous-settings.md)** - Interactive vs autonomous agents
