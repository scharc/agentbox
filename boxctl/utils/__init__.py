"""Shared utility functions for boxctl."""

from boxctl.utils.exceptions import (
    boxctlError,
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
from boxctl.utils.logging import (
    get_logger,
    get_daemon_logger,
    configure_logging,
    is_debug_mode,
    log_startup_info,
)
from boxctl.utils.config_io import (
    load_json_config,
    save_json_config,
)

__all__ = [
    # Exceptions
    "boxctlError",
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
