# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT
# See LICENSE file in the project root for full license information.

"""Migrations introduced in v0.2.0."""

from pathlib import Path
from typing import Any, Dict, Optional

from boxctl.migrations.base import (
    Migration,
    MigrationAction,
    MigrationSeverity,
)


# SSH mode name mappings (old -> new)
SSH_MODE_MIGRATION = {
    "disabled": "none",
    "copy": "keys",
    "shared": "mount",
    "agent": "config",
}


class DockerDevicesToEnabled(Migration):
    """Migrate docker socket from devices list to docker.enabled.

    Previously, docker socket access was configured via:
        devices:
          - /var/run/docker.sock:/var/run/docker.sock

    Now it should be configured via:
        docker:
          enabled: true

    This allows proper volume mounting instead of device mounting,
    which is required for docker socket access to work correctly.
    """

    id = "docker-devices-to-enabled"
    description = "Migrate docker socket from devices to docker.enabled"
    introduced_in = "0.2.0"
    severity = MigrationSeverity.WARNING
    default_action = MigrationAction.AUTO

    DOCKER_SOCKET = "/var/run/docker.sock"

    def detect(self, raw_config: Dict[str, Any], project_dir: Path) -> bool:
        """Check if config uses devices to mount docker socket."""
        devices = raw_config.get("devices", [])
        if not devices or not isinstance(devices, list):
            return False

        for device in devices:
            if isinstance(device, str) and self.DOCKER_SOCKET in device:
                return True

        return False

    def migrate(self, raw_config: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
        """Move docker socket from devices to docker.enabled."""
        devices = raw_config.get("devices", [])

        # Safety: if devices is not a list, don't modify it
        if not isinstance(devices, list):
            # Just enable docker, leave devices as-is
            if "docker" not in raw_config:
                raw_config["docker"] = {}
            raw_config["docker"]["enabled"] = True
            return raw_config

        # Remove docker socket entries, preserving non-string entries
        # Logic: keep entry unless it's a string containing the docker socket
        raw_config["devices"] = [
            d for d in devices if not (isinstance(d, str) and self.DOCKER_SOCKET in d)
        ]

        # Remove empty devices list
        if not raw_config["devices"]:
            del raw_config["devices"]

        # Enable docker
        if "docker" not in raw_config:
            raw_config["docker"] = {}
        raw_config["docker"]["enabled"] = True

        return raw_config

    def get_suggestion(self) -> str:
        """Get human-readable fix suggestion."""
        return (
            "Migrate docker socket from 'devices' to 'docker.enabled'\n"
            "The 'devices' method doesn't work correctly for docker socket.\n"
            "Run: abox docker enable"
        )


class SSHConfigRename(Migration):
    """Migrate SSH config to new mode names and setting names.

    Mode renames:
    - disabled -> none
    - copy -> keys
    - shared -> mount
    - agent -> config

    Setting rename:
    - agent_forwarding -> forward_agent
    """

    id = "ssh-config-rename"
    description = "Rename SSH modes and settings to clearer names"
    introduced_in = "0.2.0"
    severity = MigrationSeverity.INFO
    default_action = MigrationAction.AUTO

    def detect(self, raw_config: Dict[str, Any], project_dir: Path) -> bool:
        """Check if config uses old SSH mode names or agent_forwarding."""
        ssh_config = raw_config.get("ssh", {})
        if not isinstance(ssh_config, dict):
            return False

        # Check for old mode names
        mode = ssh_config.get("mode")
        if mode in SSH_MODE_MIGRATION:
            return True

        # Check for old setting name
        if "agent_forwarding" in ssh_config:
            return True

        return False

    def migrate(self, raw_config: Dict[str, Any], project_dir: Path) -> Dict[str, Any]:
        """Migrate SSH config to new names."""
        ssh_config = raw_config.get("ssh", {})
        if not isinstance(ssh_config, dict):
            return raw_config

        # Migrate mode name
        mode = ssh_config.get("mode")
        if mode in SSH_MODE_MIGRATION:
            ssh_config["mode"] = SSH_MODE_MIGRATION[mode]

        # Migrate agent_forwarding -> forward_agent
        if "agent_forwarding" in ssh_config:
            ssh_config["forward_agent"] = ssh_config.pop("agent_forwarding")

        raw_config["ssh"] = ssh_config
        return raw_config

    def get_suggestion(self) -> str:
        """Get human-readable fix suggestion."""
        return (
            "Update SSH config to use new names:\n"
            "  mode: disabled -> none, copy -> keys, shared -> mount, agent -> config\n"
            "  agent_forwarding -> forward_agent\n"
            "Run: abox config migrate"
        )
