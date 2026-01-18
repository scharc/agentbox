# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Configuration management for Agentbox projects."""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from pydantic import ValidationError
from rich.console import Console

from agentbox import __version__ as AGENTBOX_VERSION
from agentbox.models.project_config import (
    ProjectConfigModel,
    PackagesConfig,
    PortsConfig,
    SSHConfig,
    TaskAgentsConfig,
    VALID_PACKAGE_PATTERN,
)

console = Console()


def validate_package_name(name: str) -> bool:
    """Validate a package name is safe for shell execution.

    Args:
        name: Package name to validate

    Returns:
        True if valid, False if potentially dangerous
    """
    if not name or len(name) > 200:
        return False
    return VALID_PACKAGE_PATTERN.match(name) is not None


def validate_host_port(port: int) -> None:
    """Validate a host port number.

    Args:
        port: Port number to validate

    Raises:
        ValueError: If port is invalid or privileged
    """
    if port < 1024:
        raise ValueError(f"Port {port} requires root privileges. Use ports >= 1024.")
    if port > 65535:
        raise ValueError(f"Port {port} is invalid. Must be between 1024 and 65535.")


def parse_port_spec(spec: str) -> Dict[str, Any]:
    """Parse a port specification string.

    Formats:
    - "3000" -> host:3000, container:3000
    - "8080:3000" -> host:8080, container:3000

    Args:
        spec: Port specification string

    Returns:
        Dict with host_port and container_port

    Raises:
        ValueError: If format is invalid
    """
    parts = spec.split(":")
    if len(parts) == 1:
        port = int(parts[0])
        return {"host_port": port, "container_port": port}
    elif len(parts) == 2:
        host_port = int(parts[0])
        container_port = int(parts[1])
        return {"host_port": host_port, "container_port": container_port}
    else:
        raise ValueError(f"Invalid port format: {spec}. Use 'port' or 'host:container'")


class ProjectConfig:
    """Manages .agentbox.yml configuration for projects."""

    CONFIG_FILENAME = ".agentbox.yml"
    SUPPORTED_VERSION = "1.0"

    def __init__(self, project_dir: Optional[Path] = None):
        """Initialize config manager.

        Args:
            project_dir: Project directory (defaults to current dir)
        """
        if project_dir is None:
            # Check for environment variable set by wrapper script
            env_project_dir = os.getenv("AGENTBOX_PROJECT_DIR")
            if env_project_dir:
                project_dir = Path(env_project_dir)
            else:
                project_dir = Path.cwd()
        self.project_dir = project_dir
        self.config_path = project_dir / self.CONFIG_FILENAME
        self._model: Optional[ProjectConfigModel] = None
        self.config: Dict[str, Any] = {}
        self._load()

    def exists(self) -> bool:
        """Check if config file exists.

        Returns:
            True if .agentbox.yml exists
        """
        return self.config_path.exists()

    def _load(self) -> None:
        """Load configuration from file."""
        if not self.exists():
            return

        try:
            with open(self.config_path, "r") as f:
                raw_config = yaml.safe_load(f) or {}

            # Store raw config for backward compatibility
            self.config = raw_config

            # Parse with Pydantic for validation
            try:
                self._model = ProjectConfigModel.model_validate(raw_config)
            except ValidationError as e:
                console.print(f"[yellow]Warning: Config validation errors:[/yellow]")
                for error in e.errors():
                    loc = ".".join(str(x) for x in error["loc"])
                    console.print(f"  [dim]{loc}:[/dim] {error['msg']}")
                # Fall back to raw config
                self._model = None

            # Validate version
            version = raw_config.get("version")
            if version != self.SUPPORTED_VERSION:
                console.print(
                    f"[yellow]Warning: Unsupported config version {version}, "
                    f"expected {self.SUPPORTED_VERSION}[/yellow]"
                )

        except yaml.YAMLError as e:
            console.print(f"[red]Error parsing {self.CONFIG_FILENAME}: {e}[/red]")
            self.config = {}
            self._model = None
        except Exception as e:
            console.print(f"[red]Error loading config: {e}[/red]")
            self.config = {}
            self._model = None

    def save(self, quiet: bool = False) -> None:
        """Save configuration to file.

        Args:
            quiet: If True, suppress success message
        """
        try:
            # If we have a model, serialize from it
            if self._model:
                # Convert model to dict, excluding unset values
                data = self._model.model_dump(exclude_unset=False, exclude_none=True)
                self.config = data

            with open(self.config_path, "w") as f:
                yaml.safe_dump(self.config, f, default_flow_style=False, sort_keys=False)
            if not quiet:
                console.print(f"[green]Config saved to {self.config_path}[/green]")
        except Exception as e:
            console.print(f"[red]Error saving config: {e}[/red]")

    @property
    def agentbox_version(self) -> Optional[str]:
        """Get the agentbox version that created/last updated this config."""
        if self._model:
            return self._model.agentbox_version
        return self.config.get("agentbox_version")

    @agentbox_version.setter
    def agentbox_version(self, value: str) -> None:
        """Set the agentbox version."""
        self.config["agentbox_version"] = value
        if self._model:
            self._model.agentbox_version = value

    def is_version_outdated(self) -> bool:
        """Check if the config was created with an older agentbox version."""
        stored_version = self.agentbox_version
        if stored_version is None:
            return False
        return stored_version != AGENTBOX_VERSION

    @property
    def system_packages(self) -> List[str]:
        """Get list of system packages to install."""
        if self._model:
            return self._model.system_packages
        return self.config.get("system_packages", [])

    @property
    def mcp_servers(self) -> List[str]:
        """Get list of MCP servers to enable."""
        if self._model:
            return self._model.mcp_servers
        return self.config.get("mcp_servers", [])

    @property
    def skills(self) -> List[str]:
        """Get list of skills to enable."""
        if self._model:
            return self._model.skills
        return self.config.get("skills", [])

    @property
    def hostname(self) -> Optional[str]:
        """Get hostname alias for /etc/hosts."""
        if self._model:
            return self._model.hostname
        return self.config.get("hostname")

    @property
    def environment(self) -> Dict[str, str]:
        """Get environment variables."""
        if self._model:
            return self._model.env
        return self.config.get("env", {})

    @property
    def ports(self) -> Dict[str, Any]:
        """Get unified port configuration."""
        if self._model:
            ports = self._model.ports
            if isinstance(ports, PortsConfig):
                return {
                    "host": ports.host,
                    "container": ports.container,
                    "mode": ports.mode,
                }
            # Old format already converted by model validator
            return {"host": ports, "container": []}

        raw = self.config.get("ports", {})
        if isinstance(raw, list):
            return {"host": raw, "container": []}
        return {
            "host": raw.get("host", []),
            "container": raw.get("container", []),
        }

    @property
    def ports_host(self) -> List[str]:
        """Get host-exposed ports (container -> host)."""
        return self.ports.get("host", [])

    @property
    def ports_container(self) -> List[Dict[str, Any]]:
        """Get container-forwarded ports (host -> container)."""
        return self.ports.get("container", [])

    @property
    def ports_mode(self) -> str:
        """Get port forwarding mode."""
        if self._model:
            ports = self._model.ports
            if isinstance(ports, PortsConfig):
                return ports.mode
            return "tunnel"

        raw = self.config.get("ports", {})
        if isinstance(raw, dict):
            return raw.get("mode", "tunnel")
        return "tunnel"

    @property
    def ssh_enabled(self) -> bool:
        """Get SSH enabled setting."""
        if self._model:
            return self._model.ssh.enabled
        ssh_config = self.config.get("ssh", {})
        return ssh_config.get("enabled", True)

    @property
    def ssh_mode(self) -> str:
        """Get SSH mode: none, keys, mount, config."""
        if self._model:
            return self._model.ssh.mode

        ssh_config = self.config.get("ssh", {})
        mode = ssh_config.get("mode", "keys")

        # Map old mode names to new names for backwards compatibility
        mode_migration = {
            "disabled": "none",
            "copy": "keys",
            "shared": "mount",
            "agent": "config",
        }
        if mode in mode_migration:
            mode = mode_migration[mode]

        valid_modes = ["none", "keys", "mount", "config"]
        if mode not in valid_modes:
            console.print(f"[yellow]Warning: Invalid ssh.mode '{mode}', defaulting to 'keys'[/yellow]")
            return "keys"

        return mode

    @property
    def ssh_forward_agent(self) -> bool:
        """Get SSH agent forwarding setting."""
        if self._model:
            return self._model.ssh.forward_agent
        ssh_config = self.config.get("ssh", {})
        # Support both new and old config key names
        return ssh_config.get("forward_agent", ssh_config.get("agent_forwarding", False))

    @property
    def workspaces(self) -> List[Dict[str, str]]:
        """Get workspace mounts."""
        if self._model:
            return [w.model_dump() for w in self._model.workspaces]
        return self.config.get("workspaces", [])

    @property
    def containers(self) -> List[Dict[str, Any]]:
        """Get container connections."""
        if self._model:
            return [c.model_dump() for c in self._model.containers]
        return self.config.get("containers", [])

    @property
    def resources(self) -> Dict[str, str]:
        """Get container resource limits."""
        if self._model:
            return self._model.resources.model_dump(exclude_none=True)
        return self.config.get("resources", {})

    @property
    def security(self) -> Dict[str, Any]:
        """Get container security settings."""
        if self._model:
            return self._model.security.model_dump()
        return self.config.get("security", {})

    @property
    def devices(self) -> List[str]:
        """Get device mappings for container."""
        if self._model:
            return self._model.devices
        return self.config.get("devices", [])

    @property
    def task_agents(self) -> Dict[str, Any]:
        """Get task agent configuration for notification enhancement."""
        if self._model:
            return self._model.task_agents.model_dump()

        default = {
            "enabled": False,
            "agent": "claude",
            "model": "haiku",
            "timeout": 30,
            "buffer_lines": 50,
            "enhance_hooks": True,
            "enhance_stall": True,
            "prompt_template": (
                "Analyze this terminal session output and provide a brief 1-2 sentence summary "
                "of what task was being worked on.\n\n"
                "Session: {session}\n"
                "Project: {project}\n\n"
                "Last {buffer_lines} lines of output:\n"
                "```\n{buffer}\n```\n\n"
                "Provide ONLY the summary, no preamble or explanation."
            )
        }
        return self.config.get("task_agents", default)

    @property
    def packages(self) -> dict:
        """Get package installation configuration."""
        if self._model:
            return self._model.packages.model_dump()

        default = {"npm": [], "pip": [], "apt": [], "cargo": [], "post": []}
        return self.config.get("packages", default)

    def rebuild(self, container_manager, container_name: str) -> None:
        """Rebuild container environment from config.

        Args:
            container_manager: ContainerManager instance
            container_name: Name of container to configure
        """
        if not self.exists():
            console.print(
                f"[yellow]No {self.CONFIG_FILENAME} found in {self.project_dir}[/yellow]"
            )
            return

        console.print(f"[blue]Rebuilding from {self.CONFIG_FILENAME}...[/blue]")

        # Install system packages
        if self.system_packages:
            # Validate all package names before execution
            invalid_packages = [p for p in self.system_packages if not validate_package_name(p)]
            if invalid_packages:
                console.print(f"[red]Invalid package names (skipping): {', '.join(invalid_packages)}[/red]")
                console.print("[yellow]Package names must be alphanumeric with ._+- allowed[/yellow]")

            valid_packages = [p for p in self.system_packages if validate_package_name(p)]
            if valid_packages:
                console.print(f"[blue]Installing system packages: {', '.join(valid_packages)}[/blue]")
                packages = " ".join(valid_packages)
                exit_code, output = container_manager.exec_command(
                    container_name,
                    ["sh", "-c", f"apt-get update && apt-get install -y {packages}"],
                )
                if exit_code != 0:
                    console.print(f"[red]Error installing packages: {output}[/red]")
                else:
                    console.print("[green]System packages installed[/green]")

        # Enable MCP servers
        if self.mcp_servers:
            console.print(f"[blue]Enabling MCP servers: {', '.join(self.mcp_servers)}[/blue]")
            console.print("[yellow]MCP server installation not yet implemented[/yellow]")

        # Enable skills
        if self.skills:
            console.print(f"[blue]Enabling skills: {', '.join(self.skills)}[/blue]")
            console.print("[yellow]Skill installation not yet implemented[/yellow]")

        # Set environment variables
        if self.environment:
            console.print(f"[blue]Setting environment variables[/blue]")
            console.print("[yellow]Environment variable persistence not yet implemented[/yellow]")

        # Set up hostname
        if self.hostname:
            console.print(f"[blue]Setting up hostname: {self.hostname}[/blue]")
            console.print("[yellow]Hostname configuration not yet implemented[/yellow]")

        console.print("[green]Rebuild complete[/green]")

    def create_template(self) -> None:
        """Create a template .agentbox.yml file with helpful comments."""
        if self.exists():
            console.print(f"[yellow]{self.CONFIG_FILENAME} already exists[/yellow]")
            return

        # Copy template from library
        from agentbox.library import LibraryManager
        lib = LibraryManager()
        template_path = lib.config_dir / "agentbox.yml.template"

        if template_path.exists():
            import shutil
            shutil.copy(template_path, self.config_path)
        else:
            # Fallback if template not found - use Pydantic model defaults
            model = ProjectConfigModel()
            self.config = model.model_dump(exclude_none=True)
            self.save(quiet=True)

        # Reload to parse
        self._load()
        console.print(f"[green]Created template {self.CONFIG_FILENAME}[/green]")
        console.print("[blue]Edit the file and run 'abox rebuild' to apply changes[/blue]")
