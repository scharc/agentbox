"""Shared utility functions for Agentbox."""

from agentbox.utils.exceptions import (
    AgentboxError,
    ContainerError,
    TmuxError,
    ConfigError,
    ContainerNotFoundError,
    ContainerNotRunningError,
    TmuxSessionNotFoundError,
    TmuxServerNotRunningError,
    ConfigLoadError,
    ConfigSaveError,
    LibraryError,
    MCPNotFoundError,
)
from agentbox.utils.logging import (
    get_logger,
    get_daemon_logger,
    configure_logging,
    is_debug_mode,
    log_startup_info,
)
from agentbox.utils.config_io import (
    load_json_config,
    save_json_config,
)

# Note: tmux functions moved to agentbox.core.tmux
# Import from agentbox.utils.tmux for backward compatibility

__all__ = [
    # Exceptions
    "AgentboxError",
    "ContainerError",
    "TmuxError",
    "ConfigError",
    "ContainerNotFoundError",
    "ContainerNotRunningError",
    "TmuxSessionNotFoundError",
    "TmuxServerNotRunningError",
    "ConfigLoadError",
    "ConfigSaveError",
    "LibraryError",
    "MCPNotFoundError",
    # Logging
    "get_logger",
    "get_daemon_logger",
    "configure_logging",
    "is_debug_mode",
    "log_startup_info",
    # Config I/O
    "load_json_config",
    "save_json_config",
]
