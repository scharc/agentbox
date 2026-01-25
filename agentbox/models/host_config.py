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
    host: str = "127.0.0.1"  # Single host (used if hosts is empty)
    hosts: List[str] = Field(default_factory=list)  # Empty = use single host
    port: int = 8080
    log_level: str = "info"


class NotificationsConfig(BaseModel):
    """Notification system configuration."""

    timeout: float = 2.0
    timeout_enhanced: float = 60.0
    deduplication_window: float = 10.0
    hook_timeout: float = 5.0
    auto_dismiss: bool = True  # Auto-dismiss notifications on session activity


class HostTaskAgentsConfig(BaseModel):
    """Task agents configuration for host.

    Model aliases (work with any agent):
        - fast: Quick responses (claude: haiku, codex: gpt-4o-mini)
        - balanced: Good quality (claude: sonnet, codex: gpt-4o)
        - powerful: Best quality (claude: opus, codex: o3)
    """

    enabled: bool = False
    agent: str = "claude"
    model: str = "fast"  # Use alias for cross-agent compatibility
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


class LiteLLMProviderConfig(BaseModel):
    """Configuration for a single LLM provider."""

    api_key: Optional[str] = None  # Can use ${ENV_VAR} syntax
    api_base: Optional[str] = None


class LiteLLMModelDeployment(BaseModel):
    """A model deployment in a fallback chain."""

    provider: str
    model: str


class LiteLLMFallbackConfig(BaseModel):
    """Fallback behavior settings."""

    on_rate_limit: bool = True
    on_context_window: bool = True
    on_error: bool = True


class LiteLLMRouterConfig(BaseModel):
    """Router settings for LiteLLM."""

    num_retries: int = 3
    timeout: int = 120
    retry_after_seconds: int = 60


class LiteLLMConfig(BaseModel):
    """LiteLLM proxy configuration for multi-provider LLM access."""

    enabled: bool = False
    port: int = 4000
    providers: Dict[str, LiteLLMProviderConfig] = Field(default_factory=dict)
    models: Dict[str, List[LiteLLMModelDeployment]] = Field(default_factory=dict)
    fallbacks: LiteLLMFallbackConfig = Field(default_factory=LiteLLMFallbackConfig)
    router: LiteLLMRouterConfig = Field(default_factory=LiteLLMRouterConfig)


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
    litellm: LiteLLMConfig = Field(default_factory=LiteLLMConfig)

    model_config = ConfigDict(extra="allow")  # Allow extra fields for forward compatibility
