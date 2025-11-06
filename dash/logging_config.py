"""
Centralized logging configuration for Dash application.

Log levels can be controlled via environment variables:
- DASH_LOG_LEVEL: Global default log level (defaults to WARNING)
- DASH_LOG_DATA_VIZ: Log level for data_visualization.py
- DASH_LOG_CALLBACKS: Log level for callbacks.py
- DASH_LOG_SELECTION: Log level for selection_callbacks.py
- DASH_LOG_LAYOUT: Log level for all layout files (sidebar.py, indicators.py, etc.)
"""

import logging
import os


def _get_log_level(env_var: str, default: str = "WARNING") -> int:
    """Get log level from environment variable or return default."""
    level_str = os.getenv(env_var, default).upper()
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    return level_map.get(level_str, logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger for the given module name.

    Args:
        name: Logger name (typically __name__ or module name)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured (avoid duplicate handlers)
    if logger.handlers:
        return logger

    # Get log level from environment variable or use default
    global_level = _get_log_level("DASH_LOG_LEVEL", "WARNING")

    # Determine specific log level for this logger
    # Check for specific env var first, then fall back to global level
    if "layout" in name.lower():
        level = (
            _get_log_level("DASH_LOG_LAYOUT", "WARNING")
            if os.getenv("DASH_LOG_LAYOUT")
            else global_level
        )
    elif "data_visualization" in name:
        level = (
            _get_log_level("DASH_LOG_DATA_VIZ", "WARNING")
            if os.getenv("DASH_LOG_DATA_VIZ")
            else global_level
        )
    elif "callbacks" in name and "selection" not in name:
        level = (
            _get_log_level("DASH_LOG_CALLBACKS", "WARNING")
            if os.getenv("DASH_LOG_CALLBACKS")
            else global_level
        )
    elif "selection_callbacks" in name:
        level = (
            _get_log_level("DASH_LOG_SELECTION", "WARNING")
            if os.getenv("DASH_LOG_SELECTION")
            else global_level
        )
    else:
        level = global_level

    logger.setLevel(level)

    # Create console handler with formatter
    handler = logging.StreamHandler()
    handler.setLevel(level)

    # Format: timestamp | level | logger_name | message
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    return logger
