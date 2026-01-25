# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Centralized path definitions for Agentbox.

This module provides a single source of truth for all paths used throughout
the Agentbox codebase. Paths are organized by context:

- HostPaths: Paths on the host machine (where agentbox CLI runs)
- ContainerPaths: Paths inside the Docker container
- ProjectPaths: Paths relative to a project directory

Usage:
    from agentbox.paths import HostPaths, ContainerPaths, ProjectPaths

    # Host-side paths
    config_file = HostPaths.config_file()
    socket = HostPaths.agentboxd_socket()

    # Container-side paths
    workspace = ContainerPaths.WORKSPACE
    mcp_config = ContainerPaths.mcp_config()

    # Project-relative paths
    agentbox_dir = ProjectPaths.agentbox_dir(project_path)
"""

import os
from pathlib import Path
from typing import Optional


class HostPaths:
    """Paths on the host machine where agentbox CLI runs.

    These paths are used by the agentbox CLI and daemon running outside
    the container.
    """

    # XDG config directory for agentbox
    @staticmethod
    def config_dir() -> Path:
        """~/.config/agentbox/"""
        return Path.home() / ".config" / "agentbox"

    @staticmethod
    def config_file() -> Path:
        """~/.config/agentbox/config.yml"""
        return HostPaths.config_dir() / "config.yml"

    @staticmethod
    def user_mcp_dir() -> Path:
        """~/.config/agentbox/mcp/ - User's custom MCP servers."""
        return HostPaths.config_dir() / "mcp"

    @staticmethod
    def user_skills_dir() -> Path:
        """~/.config/agentbox/skills/ - User's custom skills."""
        return HostPaths.config_dir() / "skills"

    # XDG data directory
    @staticmethod
    def data_dir() -> Path:
        """~/.local/share/agentbox/"""
        return Path.home() / ".local" / "share" / "agentbox"

    @staticmethod
    def usage_state_file() -> Path:
        """~/.local/share/agentbox/usage/state.json"""
        return HostPaths.data_dir() / "usage" / "state.json"

    # XDG runtime directory
    @staticmethod
    def runtime_dir() -> Path:
        """XDG runtime dir or /run/user/{uid}"""
        xdg = os.getenv("XDG_RUNTIME_DIR")
        if xdg:
            return Path(xdg)
        return Path(f"/run/user/{os.getuid()}")

    @staticmethod
    def agentboxd_dir() -> Path:
        """Runtime directory for agentboxd daemon."""
        return HostPaths.runtime_dir() / "agentboxd"

    @staticmethod
    def agentboxd_socket() -> Path:
        """Main agentboxd daemon socket."""
        return HostPaths.agentboxd_dir() / "agentboxd.sock"

    @staticmethod
    def ssh_socket() -> Path:
        """SSH notification socket."""
        return HostPaths.agentboxd_dir() / "ssh.sock"

    @staticmethod
    def dbus_socket() -> str:
        """D-Bus session socket address."""
        return f"unix:path={HostPaths.runtime_dir()}/bus"

    # Docker socket
    DOCKER_SOCKET = "/var/run/docker.sock"

    # Agent home directories on host
    @staticmethod
    def claude_dir() -> Path:
        """~/.claude/"""
        return Path.home() / ".claude"

    @staticmethod
    def codex_dir() -> Path:
        """~/.codex/"""
        return Path.home() / ".codex"

    @staticmethod
    def gemini_dir() -> Path:
        """~/.gemini/"""
        return Path.home() / ".gemini"

    @staticmethod
    def qwen_dir() -> Path:
        """~/.qwen/"""
        return Path.home() / ".qwen"

    @staticmethod
    def openai_config_dir() -> Path:
        """~/.config/openai/"""
        return Path.home() / ".config" / "openai"

    @staticmethod
    def gh_config_dir() -> Path:
        """~/.config/gh/ - GitHub CLI config."""
        return Path.home() / ".config" / "gh"

    @staticmethod
    def glab_config_dir() -> Path:
        """~/.config/glab-cli/ - GitLab CLI config."""
        return Path.home() / ".config" / "glab-cli"

    @staticmethod
    def ssh_dir() -> Path:
        """~/.ssh/"""
        return Path.home() / ".ssh"


class ContainerPaths:
    """Paths inside the Docker container.

    These paths are used by scripts and services running inside the
    agentbox container.
    """

    # Container user home
    HOME = "/home/abox"

    # Main workspace mount point
    WORKSPACE = "/workspace"

    # Library mount point (read-only from host)
    LIBRARY = "/agentbox/library"
    LIBRARY_CONFIG = "/agentbox/library/config"
    LIBRARY_MCP = "/agentbox/library/mcp"
    LIBRARY_SKILLS = "/agentbox/library/skills"

    # User config directory inside container
    @staticmethod
    def config_dir() -> str:
        """Container user's config directory."""
        return f"{ContainerPaths.HOME}/.config/agentbox"

    @staticmethod
    def user_mcp_dir() -> str:
        """Container path for user's custom MCP servers."""
        return f"{ContainerPaths.config_dir()}/mcp"

    @staticmethod
    def user_skills_dir() -> str:
        """Container path for user's custom skills."""
        return f"{ContainerPaths.config_dir()}/skills"

    # Agent configuration directories
    @staticmethod
    def claude_dir() -> str:
        return f"{ContainerPaths.HOME}/.claude"

    @staticmethod
    def codex_dir() -> str:
        return f"{ContainerPaths.HOME}/.codex"

    @staticmethod
    def gemini_dir() -> str:
        return f"{ContainerPaths.HOME}/.gemini"

    @staticmethod
    def qwen_dir() -> str:
        return f"{ContainerPaths.HOME}/.qwen"

    # Agent settings files
    @staticmethod
    def claude_settings() -> str:
        return f"{ContainerPaths.claude_dir()}/settings.json"

    @staticmethod
    def claude_super_settings() -> str:
        return f"{ContainerPaths.claude_dir()}/settings-super.json"

    @staticmethod
    def gemini_settings() -> str:
        return f"{ContainerPaths.gemini_dir()}/settings.json"

    @staticmethod
    def qwen_settings() -> str:
        return f"{ContainerPaths.qwen_dir()}/settings.json"

    # MCP configuration
    @staticmethod
    def mcp_config() -> str:
        """Main MCP config file used by agents."""
        return f"{ContainerPaths.HOME}/.mcp.json"

    # SSH directory
    @staticmethod
    def ssh_dir() -> str:
        return f"{ContainerPaths.HOME}/.ssh"

    # Temporary/runtime files
    STATUS_FILE = "/tmp/container-status"
    MCP_PORTS_FILE = "/tmp/mcp-ports.json"
    LITELLM_LOG = "/tmp/litellm.log"
    CONTAINER_CLIENT_LOG = "/tmp/container-client.log"

    @staticmethod
    def mcp_log(name: str) -> str:
        """Log file for an MCP server."""
        return f"/tmp/mcp-{name}.log"

    @staticmethod
    def install_log(log_type: str) -> str:
        """Installation log file (mcp, project, etc.)."""
        return f"/tmp/{log_type}-install.log"

    # Tmux socket
    @staticmethod
    def tmux_socket(uid: Optional[int] = None) -> str:
        """Tmux socket path."""
        if uid is None:
            uid = os.getuid()
        return f"/tmp/tmux-{uid}/default"

    # Host mount points (inside container)
    @staticmethod
    def host_claude_mount(username: str) -> str:
        """Mount point for host ~/.claude inside container."""
        return f"/{username}/host-claude"

    @staticmethod
    def host_codex_mount(username: str) -> str:
        """Mount point for host ~/.codex inside container."""
        return f"/{username}/host-codex"

    @staticmethod
    def host_openai_mount(username: str) -> str:
        """Mount point for host ~/.config/openai inside container."""
        return f"/{username}/openai-config"

    @staticmethod
    def host_gemini_mount(username: str) -> str:
        """Mount point for host ~/.gemini inside container."""
        return f"/{username}/gemini"

    @staticmethod
    def host_qwen_mount(username: str) -> str:
        """Mount point for host ~/.qwen inside container."""
        return f"/{username}/qwen-config"

    @staticmethod
    def host_gh_mount(username: str) -> str:
        """Mount point for host ~/.config/gh inside container."""
        return f"/{username}/gh-config"

    @staticmethod
    def host_glab_mount(username: str) -> str:
        """Mount point for host ~/.config/glab-cli inside container."""
        return f"/{username}/glab-config"

    @staticmethod
    def gh_dir() -> str:
        """GitHub CLI config directory inside container."""
        return f"{ContainerPaths.HOME}/.config/gh"

    @staticmethod
    def glab_dir() -> str:
        """GitLab CLI config directory inside container."""
        return f"{ContainerPaths.HOME}/.config/glab-cli"

    HOST_SSH_MOUNT = "/host-ssh"
    HOST_CONFIG_MOUNT = "/host-config"


class ProjectPaths:
    """Paths relative to a project directory.

    These represent the structure inside a project's workspace.
    """

    # Directory names (relative)
    AGENTBOX_DIR_NAME = ".agentbox"
    CONFIG_NAME = "config.yml"

    @staticmethod
    def agentbox_dir(project_dir: Path) -> Path:
        """Project's .agentbox/ directory."""
        return project_dir / ProjectPaths.AGENTBOX_DIR_NAME

    @staticmethod
    def config_file(project_dir: Path) -> Path:
        """Project config at .agentbox/config.yml"""
        return ProjectPaths.agentbox_dir(project_dir) / ProjectPaths.CONFIG_NAME

    @staticmethod
    def mcp_meta_file(project_dir: Path) -> Path:
        """MCP metadata at .agentbox/mcp-meta.json"""
        return ProjectPaths.agentbox_dir(project_dir) / "mcp-meta.json"

    @staticmethod
    def install_manifest(project_dir: Path) -> Path:
        """Package install manifest at .agentbox/install-manifest.json"""
        return ProjectPaths.agentbox_dir(project_dir) / "install-manifest.json"

    @staticmethod
    def workspaces_file(project_dir: Path) -> Path:
        """Extra workspaces config at .agentbox/workspaces.json"""
        return ProjectPaths.agentbox_dir(project_dir) / "workspaces.json"

    @staticmethod
    def env_file(project_dir: Path) -> Path:
        """Environment file at .agentbox/.env"""
        return ProjectPaths.agentbox_dir(project_dir) / ".env"

    @staticmethod
    def env_local_file(project_dir: Path) -> Path:
        """Local environment file at .agentbox/.env.local"""
        return ProjectPaths.agentbox_dir(project_dir) / ".env.local"

    @staticmethod
    def host_config_file(project_dir: Path) -> Path:
        """Cached host config at .agentbox/host-config.yml"""
        return ProjectPaths.agentbox_dir(project_dir) / "host-config.yml"

    @staticmethod
    def agents_md(project_dir: Path) -> Path:
        """Agents instructions at .agentbox/agents.md"""
        return ProjectPaths.agentbox_dir(project_dir) / "agents.md"

    @staticmethod
    def superagents_md(project_dir: Path) -> Path:
        """Superagent instructions at .agentbox/superagents.md"""
        return ProjectPaths.agentbox_dir(project_dir) / "superagents.md"

    @staticmethod
    def claude_dir(project_dir: Path) -> Path:
        """Project-local Claude state at .agentbox/claude/"""
        return ProjectPaths.agentbox_dir(project_dir) / "claude"

    @staticmethod
    def codex_dir(project_dir: Path) -> Path:
        """Project-local Codex state at .agentbox/codex/"""
        return ProjectPaths.agentbox_dir(project_dir) / "codex"

    @staticmethod
    def mcp_dir(project_dir: Path) -> Path:
        """Project MCP servers at .agentbox/mcp/"""
        return ProjectPaths.agentbox_dir(project_dir) / "mcp"

    @staticmethod
    def log_file(project_dir: Path) -> Path:
        """Development log at .agentbox/LOG.md"""
        return ProjectPaths.agentbox_dir(project_dir) / "LOG.md"

    @staticmethod
    def mobile_debug_log(project_dir: Path) -> Path:
        """Mobile debug log at .agentbox/mobile-debug.log"""
        return ProjectPaths.agentbox_dir(project_dir) / "mobile-debug.log"

    # Agent config subdirectories
    @staticmethod
    def claude_mcp_config(project_dir: Path) -> Path:
        """Claude MCP config at .agentbox/claude/mcp.json"""
        return ProjectPaths.claude_dir(project_dir) / "mcp.json"


class TempPaths:
    """Temporary paths used for IPC and runtime state."""

    # Local IPC socket (for container-to-daemon communication)
    LOCAL_IPC_SOCKET = "/tmp/agentbox-local.sock"

    # Combined super instructions file
    SUPER_INSTRUCTIONS = "/tmp/agentbox-super-instructions.md"

    # LiteLLM temporary config
    LITELLM_CONFIG = "/tmp/litellm-config.yaml"

    # Installation progress tracking
    INSTALL_PROGRESS = "/tmp/install-progress.json"


class BinPaths:
    """Paths to executable scripts and binaries."""

    # Container-side executables
    CLAUDE = "/usr/local/bin/claude"
    CONTAINER_INIT = "/usr/local/bin/container-init.sh"
    INSTALL_PACKAGES = "/usr/local/bin/install-packages.py"
    GENERATE_MCP_CONFIG = "/usr/local/bin/generate-mcp-config.py"

    # Workspace bin scripts (when running from source)
    @staticmethod
    def workspace_script(name: str) -> str:
        """Script in /workspace/bin/ directory."""
        return f"{ContainerPaths.WORKSPACE}/bin/{name}"

    @staticmethod
    def agentbox_script(name: str) -> str:
        """Script in /workspace/agentbox/ directory."""
        return f"{ContainerPaths.WORKSPACE}/agentbox/{name}"
