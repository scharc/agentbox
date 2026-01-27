# Boxctl Roadmap

## Current Focus

### Documentation Cleanup
- Update docs to reflect current state (SSH consolidation, migrations, positional CLI args)
- Remove outdated plan files and references

### Test Suite Expansion
- Test all default MCPs with real test suite (docker + dummy data)
- Verify each MCP actually works before shipping

---

## Web UI Direction

**Current Status:** WIP - direction under review

**Background:** The web UI was built for mobile access to agent sessions. However:
- PWA features require valid HTTPS certificate (not practical for local dev)
- Termius on Android provides excellent tmux access already
- Full terminal emulation in browser adds complexity

**Proposed Direction:** Simplify web UI to be an "boxctl quick" gateway:
- Remove full tmux terminal emulation
- Keep status page (tunnel monitoring, container status)
- Add web-based `abox q` menu for quick actions
- Focus on information display, not terminal interaction

**Deferred:**
- PWA offline support
- Push notifications
- Session peek pane

---

## Ideas Backlog

### agentctl Auto-Completion (Container)
- Add shell auto-completion for `agentctl` commands inside container
- Priority: session name completion for faster mobile typing
- Could use bash-completion or zsh-completion scripts

### Session Monitoring Improvements
- Enhanced stall detection signals
- Better notification content
- Task completion summaries

---

## Completed (Reference)

### January 2026
- SSH tunnel consolidation (all container-host communication via SSH)
- Config migration system (`abox config migrate`)
- Quick menu TUI (`abox q`) - full implementation
- Mobile-friendly status page
- Session task labeling (`set_session_task`/`clear_session_task`)
- Custom MCP/skills directory support (`~/.config/boxctl/mcp/`, `~/.config/boxctl/skills/`)
- Device passthrough for containers
- Positional CLI arguments (no more flags)
- Pydantic config validation

---

## Research Archive

Detailed research on the following topics was completed and is available in git history (NOTES.md prior to cleanup):

- PWA best practices for terminal apps
- Service Worker & WebSocket handling
- IndexedDB vs LocalStorage
- Push notification APIs
- Mobile UI touch targets and thumb zones
- Cache versioning strategies
- Workbox library patterns

This research remains valid if PWA work is revisited in the future.
