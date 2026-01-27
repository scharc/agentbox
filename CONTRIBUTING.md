# Contributing to Boxctl

Thank you for considering contributing to Boxctl! This guide will help you get started.

## Table of Contents

- [We Need Help!](#we-need-help)
- [Development Setup](#development-setup)
- [Coding Guidelines](#coding-guidelines)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Documentation](#documentation)
- [Community](#community)

---

## We Need Help!

Boxctl is a daily-driver work-in-progress. Some areas work great, others need love. Here's where you can make the biggest impact:

### 🔴 Critical (High Priority)

**1. Mobile Web Terminal**
- **Status:** "Driving me nuts" - scrolling is broken
- **Problem:** Tmux session handling in mobile browsers
- **Impact:** Web UI unusable on phones/tablets
- **Skills needed:** Web development, xterm.js, tmux, mobile browsers
- **Entry point:** `boxctl/web/static/terminal.html`, `boxctl/web/static/js/terminal.js`

**2. PWA/HTTPS Setup**
- **Status:** PWA code exists but untested
- **Problem:** Service worker requires HTTPS, Tailscale HTTPS setup unclear
- **Impact:** Offline mode, install prompts don't work
- **Skills needed:** PWA, HTTPS/TLS, Tailscale configuration
- **Entry point:** `boxctl/web/static/sw.js`, `boxctl/web/static/manifest.json`

**3. Skills System**
- **Status:** Completely untested, not used in production
- **Problem:** Unknown stability, no test coverage
- **Impact:** Feature exists but may be broken
- **Skills needed:** Python, CLI development, testing
- **Entry point:** `boxctl/skills/`, needs full test suite

### 🟡 Important (Medium Priority)

**4. MCP Dependency Installation Edge Cases**
- **Status:** Mostly working, some edge cases fail
- **Problem:** Some packages don't install correctly in certain scenarios
- **Impact:** MCPs may not activate after rebuild
- **Skills needed:** Python, package managers (npm, pip, cargo)
- **Entry point:** `boxctl/mcp.py`, `library/mcp/*/install_manifest.json`

**5. Experimental MCP Testing**
- **Status:** 16 MCPs configured but not battle-tested
- **Problem:** Unknown reliability, minimal real-world usage
- **Impact:** Users may encounter bugs in experimental MCPs
- **Skills needed:** Testing, Python, various APIs
- **Entry point:** `library/mcp/`

**6. Test Coverage**
- **Status:** 75% overall, some modules < 50%
- **Problem:** AgentCtl (45%), Web UI (60%), Skills (0%)
- **Impact:** Bugs may slip through
- **Skills needed:** pytest, Docker, integration testing
- **Entry point:** `tests/`, see [docs/testing.md](docs/testing.md)

### 🟢 Nice to Have (Low Priority)

**7. Documentation**
- **Status:** Good but can always improve
- **Problem:** New features need examples, edge cases need docs
- **Skills needed:** Writing, markdown
- **Entry point:** `docs/`

**8. Performance Optimization**
- **Status:** Works fine, could be faster
- **Problem:** Container startup, rebuild time
- **Skills needed:** Docker, profiling, Python optimization

---

## Development Setup

### Prerequisites

- **Python 3.10+** - Language runtime
- **Docker 24+** - Container platform
- **Poetry** - Python dependency management (recommended)
- **Git** - Version control
- **Linux or macOS** - Primary development platforms

### Getting Started

**1. Clone repository:**
```bash
git clone https://github.com/yourusername/boxctl.git
cd boxctl
```

**2. Install dependencies:**

**With Poetry (recommended):**
```bash
# Install Poetry if needed
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

**With pip:**
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"
```

**3. Install pre-commit hooks (optional but recommended):**
```bash
poetry run pre-commit install
```

This runs linters and formatters automatically on commit.

**4. Verify installation:**
```bash
# Check version
boxctl --version

# Run tests
poetry run pytest

# Should see tests passing
```

### Development Workflow

**1. Create feature branch:**
```bash
git checkout -b feature/your-feature-name
```

**2. Make changes:**
```bash
# Edit code
vim boxctl/container.py

# Run tests
poetry run pytest

# Format code
poetry run black boxctl/
poetry run ruff check boxctl/
```

**3. Test locally:**
```bash
# Rebuild base image with changes
boxctl rebuild base

# Test in a project
cd /tmp/test-project
boxctl init
boxctl start
abox superclaude
```

**4. Commit changes:**
```bash
git add .
git commit -m "feat: Add awesome feature"
```

**5. Push and create PR:**
```bash
git push origin feature/your-feature-name
# Open PR on GitHub
```

---

## Coding Guidelines

### Philosophy

**Simplicity over cleverness.** Code should be:
- **Readable** - Clear > clever
- **Tested** - Every feature needs tests
- **Documented** - Docstrings and comments where needed
- **Consistent** - Follow existing patterns

### The NO FLAGS Policy

**Critical:** Boxctl uses positional arguments only. NEVER add flags.

**Bad:**
```python
@click.command()
@click.option('--project', help='Project name')
@click.option('--force', is_flag=True)
def start(project, force):
    pass
```

**Good:**
```python
@click.command()
@click.argument('project', required=False)
@click.argument('force', required=False)
def start(project, force):
    # force is "force" string if provided, None otherwise
    pass
```

**Why?** Natural English syntax: `boxctl start myproject` not `boxctl start --project myproject`

### Python Style

**Use Black formatter:**
```bash
poetry run black boxctl/
```

**Use Ruff linter:**
```bash
poetry run ruff check boxctl/
```

**Follow PEP 8:**
- 88 character line length (Black default)
- Use type hints where helpful
- Docstrings for public functions/classes
- Descriptive variable names

**Example:**
```python
def create_container(
    project_name: str,
    config: ProjectConfig,
    network: Optional[str] = None
) -> Container:
    """Create a new boxctl container.

    Args:
        project_name: Name of the project
        config: Project configuration
        network: Optional Docker network to join

    Returns:
        Container instance

    Raises:
        ValueError: If project_name is invalid
        DockerException: If container creation fails
    """
    if not is_valid_project_name(project_name):
        raise ValueError(f"Invalid project name: {project_name}")

    # ... implementation ...
    return Container(project_name, config)
```

### Code Organization

**File structure:**
```
boxctl/
├── __init__.py           # Package initialization, version
├── cli/                  # CLI commands
│   ├── __init__.py       # Main CLI entry point
│   ├── project.py        # Project commands
│   ├── session.py        # Session commands
│   └── ...
├── container.py          # Container management
├── config.py             # Configuration parsing
├── mcp.py                # MCP server management
├── web/                  # Web UI
│   ├── host_server.py    # FastAPI server
│   └── static/           # HTML/JS/CSS
└── agentctl/             # Container-side tools
    └── cli.py            # agentctl CLI
```

**Separation of concerns:**
- CLI commands in `cli/` - thin wrappers
- Business logic in core modules - `container.py`, `config.py`, etc.
- Web UI separate from core logic
- Container-side tools in `agentctl/`

### Error Handling

**Be explicit about errors:**
```python
# Bad - silent failure
def start_container(name):
    try:
        container = docker.containers.get(name)
        container.start()
    except:
        pass  # ❌ What went wrong?

# Good - explicit error handling
def start_container(name):
    try:
        container = docker.containers.get(name)
        container.start()
    except docker.errors.NotFound:
        raise ContainerNotFoundError(f"Container {name} not found")
    except docker.errors.APIError as e:
        raise ContainerStartError(f"Failed to start {name}: {e}")
```

**User-facing errors should be helpful:**
```python
# Bad
raise Exception("Error")

# Good
raise ValueError(
    f"Invalid project name '{name}'. "
    "Project names must be lowercase alphanumeric with hyphens only. "
    "Examples: 'my-project', 'app-123'"
)
```

### Logging

**Use appropriate log levels:**
```python
import logging

logger = logging.getLogger(__name__)

# DEBUG - Detailed information for diagnosing problems
logger.debug(f"Connecting to Docker daemon at {docker_host}")

# INFO - Confirmation that things are working as expected
logger.info(f"Container {name} started successfully")

# WARNING - Something unexpected but not an error
logger.warning(f"Container {name} already exists, using existing")

# ERROR - A significant problem occurred
logger.error(f"Failed to start container {name}: {error}")
```

**Don't log sensitive information:**
```python
# Bad
logger.info(f"Connecting with password: {password}")

# Good
logger.info("Connecting with credentials from environment")
```

---

## Testing

### Test Requirements

**All contributions must include tests:**
- ✅ New features → integration tests + unit tests
- ✅ Bug fixes → regression test that would catch the bug
- ✅ Refactoring → existing tests must pass

**Minimum coverage:** 80% for new code

### Running Tests

**All tests:**
```bash
poetry run pytest
```

**With coverage:**
```bash
poetry run pytest --cov=boxctl --cov-report=html
# Open htmlcov/index.html
```

**Fast tests only (skip slow):**
```bash
poetry run pytest -m "not slow"
```

**Integration tests (DinD):**
```bash
./scripts/test-dind.sh
```

### Writing Tests

**Follow the testing guide:** [docs/testing.md](docs/testing.md)

**Quick example:**
```python
import pytest
from boxctl.container import Container

@pytest.mark.integration
def test_container_lifecycle(tmp_path):
    """Test container can be created, started, stopped, removed."""
    # Arrange
    project_dir = tmp_path / "test"
    project_dir.mkdir()

    container = Container(project_dir)

    try:
        # Act
        container.create()
        container.start()

        # Assert
        assert container.is_running()

        # Act
        container.stop()

        # Assert
        assert not container.is_running()

    finally:
        # Cleanup
        container.remove(force=True)
```

**Key principles:**
- **Arrange-Act-Assert** pattern
- **Cleanup** in finally block or fixture
- **Isolation** - tests don't depend on each other
- **Clear names** - describe what is tested

---

## Submitting Changes

### Before You Submit

**Checklist:**
- [ ] Code follows style guidelines (Black, Ruff)
- [ ] All tests pass: `poetry run pytest`
- [ ] New tests added for new functionality
- [ ] Coverage hasn't decreased: `poetry run pytest --cov`
- [ ] Documentation updated (if needed)
- [ ] Commit messages follow conventions
- [ ] No merge conflicts with main branch

### Commit Messages

**Follow Conventional Commits:**

Format: `<type>(<scope>): <description>`

**Types:**
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation only
- `style` - Code style (formatting, no logic change)
- `refactor` - Code change that neither fixes bug nor adds feature
- `test` - Adding or updating tests
- `chore` - Maintenance (dependencies, build, etc.)

**Examples:**
```bash
feat(web): Add mobile scrolling support for terminal
fix(mcp): Handle npm install failures gracefully
docs(worktrees): Add example for parallel branch development
test(container): Add integration tests for network connections
refactor(cli): Simplify session command structure
chore(deps): Update FastAPI to 0.109.0
```

**Good commit messages:**
```bash
feat(web): Add floating controls panel for mobile terminal

- Add scroll controls (page up/down, line up/down)
- Add quick keys (ESC, TAB, CTRL, arrows)
- Auto-enter tmux copy mode on control use
- Position panel in bottom-right corner

Closes #123
```

**Bad commit messages:**
```bash
update files
fix bug
wip
changes
```

### Pull Request Process

**1. Create PR from feature branch:**
- Title: Same format as commit message
- Description: Explain what and why
- Link related issues: `Closes #123`, `Fixes #456`

**2. PR template (use this):**
```markdown
## Description
Brief description of changes and motivation.

## Type of Change
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature causing existing functionality to change)
- [ ] Documentation update

## How Has This Been Tested?
Describe tests you ran and how to reproduce.

## Checklist
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code where needed
- [ ] I have updated documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix/feature works
- [ ] New and existing tests pass locally
- [ ] Coverage hasn't decreased

## Screenshots (if applicable)
Add screenshots for UI changes.

## Additional Notes
Any other context about the PR.
```

**3. Code review:**
- Respond to feedback constructively
- Make requested changes
- Push updates to same branch (PR auto-updates)

**4. Merge:**
- Maintainer will merge once approved
- Squash merge for features
- Regular merge for multi-commit PRs

---

## Documentation

### When to Update Docs

**Always update docs for:**
- ✅ New features (add guide + CLI reference entry)
- ✅ Breaking changes (update migration guide)
- ✅ New configuration options (update configuration.md)
- ✅ New CLI commands (update cli-reference.md)
- ✅ Bug fixes that affect behavior (update relevant guide)

### Documentation Style

**Be user-focused:**
- Write for users trying to accomplish tasks
- Start with simple examples
- Add complexity progressively
- Include troubleshooting

**Good example:**
```markdown
## Creating a Worktree

To work on multiple branches simultaneously:

1. Create a worktree:
   ```bash
   agentctl worktree add feature-auth
   ```

2. Switch to the worktree:
   ```bash
   agentctl worktree switch feature-auth
   ```

3. Start working:
   ```bash
   agentctl worktree superclaude feature-auth "Implement OAuth"
   ```

**What this does:**
- Creates `/git-worktrees/worktree-feature-auth/`
- Checks out the `feature-auth` branch
- Launches superclaude in that worktree

**Use case:** Fix bugs on main while developing feature.
```

**Bad example:**
```markdown
## Worktree Function

The `add` function creates worktrees. Use `switch` to switch.

```bash
agentctl worktree add <branch>
```
```

### Documentation Structure

```
docs/
├── web-terminal.md        # Feature guide
├── worktrees.md           # Feature guide
├── multi-instance.md      # Feature guide
├── mcp-servers.md         # Reference
├── cli-reference.md       # Reference
├── configuration.md       # Reference
├── testing.md             # Contributor guide
├── migration-guide.md     # Version-specific
└── architecture.md        # Technical deep-dive
```

---

## Community

### Communication Channels

**GitHub Issues:**
- Bug reports
- Feature requests
- Questions (use "question" label)

**GitHub Discussions:**
- General discussion
- Ideas and proposals
- Show and tell

**Pull Requests:**
- Code contributions
- Documentation improvements

### Code of Conduct

**Be respectful:**
- Welcome newcomers
- Assume good intent
- Provide constructive feedback
- No harassment, discrimination, or abuse

**Be helpful:**
- Answer questions when you can
- Share knowledge
- Improve documentation
- Help review PRs

**Be patient:**
- This is a WIP daily-driver project
- Maintainer is also a user
- Response times may vary
- Quality over speed

### Getting Help

**Stuck?** Try this order:
1. Search existing issues and discussions
2. Check documentation
3. Ask in Discussions (Q&A category)
4. Open an issue (if it's a bug)

**When asking for help:**
- Describe what you're trying to do
- Show what you've tried
- Include error messages (full text)
- Provide versions: `boxctl --version`, `docker --version`
- Include config (`.boxctl.yml`) if relevant

---

## Release Process

For maintainers:

**1. Version bump:**
```bash
# Update version in:
# - pyproject.toml
# - boxctl/__init__.py
# - boxctl/cli/__init__.py
# - boxctl/web/__init__.py
# - boxctl/agentctl/cli.py
# - boxctl/web/host_server.py
```

**2. Update CHANGELOG.md:**
```markdown
## [0.2.0] - 2026-01-13

### Added
- Web terminal UI for browser-based access
- Git worktree support for parallel branch development
- Multi-instance session management
- 20 pre-configured MCP servers

### Changed
- CLI now uses positional arguments instead of flags
- Package configuration moved to .boxctl.yml

### Deprecated
- packages.json (use .boxctl.yml instead)

### Fixed
- Session name conflicts
- MCP installation edge cases
```

**3. Tag release:**
```bash
git tag -a v0.2.0 -m "Release version 0.2.0"
git push origin v0.2.0
```

**4. Build and publish:**
```bash
poetry build
poetry publish
```

**5. GitHub release:**
- Create release from tag
- Copy CHANGELOG entry
- Add release notes

---

## Thank You!

Every contribution helps make Boxctl better. Whether you:
- Fix a typo in docs
- Report a bug
- Add a test
- Build a feature
- Help other users

**You're making a difference.** Thank you! 🙏

---

## Quick Links

- [README](README.md) - Project overview
- [Architecture](docs/architecture.md) - System design
- [Testing Guide](docs/testing.md) - How to test
- [CLI Reference](docs/cli-reference.md) - All commands
- [Issues](https://github.com/yourusername/boxctl/issues) - Report bugs
- [Discussions](https://github.com/yourusername/boxctl/discussions) - Ask questions
