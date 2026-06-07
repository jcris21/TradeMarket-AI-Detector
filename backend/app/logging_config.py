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
    handler.setFormatter(JsonFormatter("%(levelname)s %(name)s %(message)s"))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
