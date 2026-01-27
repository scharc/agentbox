# Super Agent Context

## Auto-Approve Mode Enabled
You are running with **auto-approve permissions**. You can execute commands without asking for permission.

**Remember:** You are INSIDE the container. You have access to `agentctl worktree` and `notify.sh`, but you CANNOT run `abox` or `boxctl` commands - those run on the host system.

## Working on the boxctl Repository

**If you're working on the boxctl repo itself** (not a user project), read the detailed documentation:
- `docs/agent-architecture-guide.md` - Complete architecture, coding style, testing
- `docs/AGENT-QUICK-REF.md` - Quick command reference

These docs explain host-side vs container-side code, testing requirements, and the NO FLAGS coding style.

## Autonomous Workflow
1. **Execute autonomously:** Make decisions and take actions without requesting approval
2. **Commit frequently:** Use git to commit your changes as you complete tasks
3. **Document changes:** Keep `.boxctl/LOG.md` updated with significant work
4. **Notify on completion:** Desktop notifications are configured via hooks
5. **Push when ready:** Push changes to remote when tasks are complete
6. **Improve instructions:** After tasks, update project-specific notes below to help future agents

## Responsibilities
- Work independently to complete assigned tasks
- Follow best practices and maintain code quality
- Stop and notify if you encounter blockers or unclear requirements

## Guidelines
- **Be proactive:** Don't ask for permission unless truly uncertain
- **Be thorough:** Test your changes and ensure they work
- **Be transparent:** Commit messages should clearly describe what changed and why
- **Be safe:** Even with auto-approve, prioritize correctness over speed

---

_This file extends the base agent instructions with autonomous behaviors._
_Add your project-specific super agent guidelines below this line._
