"""
Logging configuration with structlog.
"""
import logging
import sys

import structlog
from app.core.config import get_settings

settings = get_settings()


def setup_logging() -> None:
    """Configure structured logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper())

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__):
    """Get a logger instance."""
    return structlog.get_logger(name)
