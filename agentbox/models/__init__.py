# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Pydantic models for Agentbox configuration."""

from agentbox.models.project_config import (
    ProjectConfigModel,
    SSHConfig,
    PortsConfig,
    PackagesConfig,
    ResourcesConfig,
    SecurityConfig,
    TaskAgentsConfig,
    WorkspaceMount,
    ContainerConnection,
)
from agentbox.models.host_config import (
    HostConfigModel,
    WebServerConfig,
    NotificationsConfig,
    StallDetectionConfig,
    TimeoutsConfig,
    PollingConfig,
    TerminalConfig,
    TailscaleMonitorConfig,
    NetworkConfig,
)

__all__ = [
    # Project config
    "ProjectConfigModel",
    "SSHConfig",
    "PortsConfig",
    "PackagesConfig",
    "ResourcesConfig",
    "SecurityConfig",
    "TaskAgentsConfig",
    "WorkspaceMount",
    "ContainerConnection",
    # Host config
    "HostConfigModel",
    "WebServerConfig",
    "NotificationsConfig",
    "StallDetectionConfig",
    "TimeoutsConfig",
    "PollingConfig",
    "TerminalConfig",
    "TailscaleMonitorConfig",
    "NetworkConfig",
]
