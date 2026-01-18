# Copyright (c) 2025 Marc Schütze <scharc@gmail.com>
# SPDX-License-Identifier: MIT

"""Pydantic models for host configuration (~/.config/agentbox/config.yml)."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PathsConfig(BaseModel):
    """Path configuration overrides."""

    agentbox_dir: Optional[str] = None


class WebServerConfig(BaseModel):
    """Web server configuration."""

    enabled: bool = True
    host: str = "127.0.0.1"  # Legacy single host (used if hosts is empty)
    hosts: List[str] = Field(default_factory=list)  # Empty = use legacy host
    port: int = 8080
    log_level: str = "info"


class NotificationsConfig(BaseModel):
    """Notification system configuration."""

    timeout: float = 2.0
    timeout_enhanced: float = 60.0
    deduplication_window: float = 10.0
    hook_timeout: float = 5.0


class HostTaskAgentsConfig(BaseModel):
    """Task agents configuration for host."""

    enabled: bool = False
    agent: str = "claude"
    model: str = "haiku"
    timeout: int = 30
    buffer_lines: int = 50


class StallDetectionConfig(BaseModel):
    """Stall detection configuration."""

    enabled: bool = True
    threshold_seconds: float = 30.0
    check_interval_seconds: float = 5.0
    cooldown_seconds: float = 60.0


class TimeoutsConfig(BaseModel):
    """Various timeout configurations."""

    container_wait: float = 6.0
    container_wait_interval: float = 0.25
    web_connection: float = 2.0
    web_resize_wait: float = 0.1
    proxy_connection: float = 2.0
    stream_registration: float = 5.0
    tmux_command: float = 2.0


class PollingConfig(BaseModel):
    """Polling interval configurations."""

    web_output: float = 0.1
    stream_monitor: float = 0.01
    session_check: float = 5.0


class TerminalConfig(BaseModel):
    """Terminal default settings."""

    default_width: int = 80
    default_height: int = 24


class TailscaleMonitorConfig(BaseModel):
    """Tailscale monitoring configuration."""

    enabled: bool = True
    check_interval_seconds: float = 30.0


class NetworkConfig(BaseModel):
    """Network binding configuration."""

    bind_addresses: List[str] = Field(default_factory=lambda: ["127.0.0.1", "tailscale"])


class HostConfigModel(BaseModel):
    """Main host configuration model for ~/.config/agentbox/config.yml."""

    version: str = "1.0"
    paths: PathsConfig = Field(default_factory=PathsConfig)
    web_server: WebServerConfig = Field(default_factory=WebServerConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    task_agents: HostTaskAgentsConfig = Field(default_factory=HostTaskAgentsConfig)
    stall_detection: StallDetectionConfig = Field(default_factory=StallDetectionConfig)
    timeouts: TimeoutsConfig = Field(default_factory=TimeoutsConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    terminal: TerminalConfig = Field(default_factory=TerminalConfig)
    tailscale_monitor: TailscaleMonitorConfig = Field(default_factory=TailscaleMonitorConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)

    model_config = ConfigDict(extra="allow")  # Allow extra fields for forward compatibility
