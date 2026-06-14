"""Centralised logging configuration — call configure_logging() at startup."""

import logging
import os

from pythonjsonlogger.json import JsonFormatter


def configure_logging() -> None:
    """Install a JSON formatter on the root logger when LOG_FORMAT=json (default).

    Set LOG_FORMAT=text for human-readable output in local development.
    """
    if os.environ.get("LOG_FORMAT", "json").lower() != "json":
        return

    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))

    app_logger = logging.getLogger("app")
    if not any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, JsonFormatter)
               for h in app_logger.handlers):
        app_logger.addHandler(handler)
    app_logger.setLevel(logging.INFO)
    app_logger.propagate = False
