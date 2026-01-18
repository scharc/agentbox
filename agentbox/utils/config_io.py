"""Configuration file I/O utilities."""

import json
from pathlib import Path
from typing import Any

from agentbox.utils.exceptions import ConfigLoadError, ConfigSaveError
from agentbox.utils.logging import get_logger

logger = get_logger(__name__)


def load_json_config(config_path: Path, default: Any = None) -> Any:
    """Load JSON configuration file.

    Args:
        config_path: Path to JSON file
        default: Default value if file doesn't exist

    Returns:
        Loaded configuration

    Raises:
        ConfigLoadError: If file exists but cannot be parsed
    """
    if not config_path.exists():
        logger.debug(f"Config file not found: {config_path}, using default")
        return default if default is not None else {}

    try:
        with open(config_path, "r") as f:
            data = json.load(f)
        logger.debug(f"Loaded config from {config_path}")
        return data
    except json.JSONDecodeError as e:
        raise ConfigLoadError(f"Invalid JSON in {config_path}: {e}") from e
    except Exception as e:
        raise ConfigLoadError(f"Failed to load {config_path}: {e}") from e


def save_json_config(config_path: Path, data: Any, indent: int = 2) -> None:
    """Save configuration to JSON file.

    Args:
        config_path: Path to JSON file
        data: Data to save
        indent: JSON indentation level

    Raises:
        ConfigSaveError: If save fails
    """
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(data, f, indent=indent)
        logger.debug(f"Saved config to {config_path}")
    except Exception as e:
        raise ConfigSaveError(f"Failed to save {config_path}: {e}") from e
