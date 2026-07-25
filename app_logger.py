"""Centralized logging for FastCommandCenter. Route all logging through AppLogger, never print()."""

import logging
import os


class AppLogger:
    """Single entry point for application logging.

    Level set via FASTCOMMANDCENTER_LOG_LEVEL env var.
    """

    _logger = logging.getLogger("fastcommandcenter")
    _logger.setLevel(os.environ.get("FASTCOMMANDCENTER_LOG_LEVEL", "INFO").upper())
    if not _logger.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        _logger.addHandler(_handler)

    @classmethod
    def debug(cls, message):
        cls._logger.debug(message)

    @classmethod
    def info(cls, message):
        cls._logger.info(message)

    @classmethod
    def warning(cls, message):
        cls._logger.warning(message)

    @classmethod
    def error(cls, message, exc_info=False):
        cls._logger.error(message, exc_info=exc_info)
