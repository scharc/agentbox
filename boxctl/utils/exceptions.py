"""Custom exception hierarchy for boxctl."""


class boxctlError(Exception):
    """Base exception for all boxctl errors."""

    pass


class ContainerError(boxctlError):
    """Container-related errors."""

    pass


class ContainerNotFoundError(ContainerError):
    """Container does not exist."""

    pass


class ContainerNotRunningError(ContainerError):
    """Container exists but is not running."""

    pass


class TmuxError(boxctlError):
    """TMux-related errors."""

    pass


class TmuxSessionNotFoundError(TmuxError):
    """TMux session does not exist."""

    pass


class TmuxServerNotRunningError(TmuxError):
    """TMux server is not running."""

    pass


class ConfigError(boxctlError):
    """Configuration-related errors."""

    pass


class ConfigLoadError(ConfigError):
    """Failed to load configuration."""

    pass


class ConfigSaveError(ConfigError):
    """Failed to save configuration."""

    pass


class LibraryError(boxctlError):
    """Library/MCP/Skills errors."""

    pass


class MCPNotFoundError(LibraryError):
    """MCP server not found in library."""

    pass
