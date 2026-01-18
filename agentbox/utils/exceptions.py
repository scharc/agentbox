"""Custom exception hierarchy for Agentbox."""


class AgentboxError(Exception):
    """Base exception for all Agentbox errors."""

    pass


class ContainerError(AgentboxError):
    """Container-related errors."""

    pass


class ContainerNotFoundError(ContainerError):
    """Container does not exist."""

    pass


class ContainerNotRunningError(ContainerError):
    """Container exists but is not running."""

    pass


class TmuxError(AgentboxError):
    """TMux-related errors."""

    pass


class TmuxSessionNotFoundError(TmuxError):
    """TMux session does not exist."""

    pass


class TmuxServerNotRunningError(TmuxError):
    """TMux server is not running."""

    pass


class ConfigError(AgentboxError):
    """Configuration-related errors."""

    pass


class ConfigLoadError(ConfigError):
    """Failed to load configuration."""

    pass


class ConfigSaveError(ConfigError):
    """Failed to save configuration."""

    pass


class LibraryError(AgentboxError):
    """Library/MCP/Skills errors."""

    pass


class MCPNotFoundError(LibraryError):
    """MCP server not found in library."""

    pass
