# Default Config Preset

This preset defines the unified Agentbox defaults in `agentbox.config.json`.

## Philosophy

**Auto-accept everything, but break when Claude is uncertain.**

This config enables Claude to work autonomously inside the isolated container while preserving your control over critical decisions.

## Auto-Approve Settings

### Always Auto-Approved (No prompts)

These tools are auto-approved because they operate within the isolated container workspace:

- **Bash**: Execute commands (safe because container is isolated)
- **Read**: Read files (read-only operations are safe)
- **Write**: Write files (limited to workspace directory)
- **Edit**: Edit files (limited to workspace directory)
- **Glob**: Find files by pattern (read-only)
- **Grep**: Search file contents (read-only)
- **NotebookEdit**: Edit Jupyter notebooks
- **Task**: Launch specialized agents
- **WebFetch**: Fetch web content
- **WebSearch**: Search the web
- **LSP**: Language server protocol operations
- **TodoWrite**: Task list management
- **ExitPlanMode**: Exit planning mode

### Never Auto-Approved (Always asks)

These require human input:

- **AskUserQuestion**: Claude needs clarification or input
  - This ensures Claude breaks and asks when uncertain
  - You maintain control over architectural decisions
  - Critical for the "break when unclear" behavior

- **EnterPlanMode**: Entering planning mode
  - You decide when to enter planning phase
  - Prevents unnecessary planning for simple tasks

## Usage

The default unified config lives at `library/config/default/agentbox.config.json`.
`agentbox init` uses it to seed `.agentbox/agentbox.config.json`, and the runtime
configs are generated from that unified file.

## Security

All auto-approved operations are safe because:

1. Container is isolated from host system
2. File operations limited to workspace directory
3. Dotfiles and SSH keys mounted read-only
4. No access to host files outside workspace

The worst case is Claude makes mistakes in your project code, which can be reverted via git.

## Customization

To create a custom config:

1. Copy this directory to `config/your-preset/`
2. Modify `agentbox.config.json` as needed
3. Update README.md to document your changes
4. Copy into your project `.agentbox/agentbox.config.json`
