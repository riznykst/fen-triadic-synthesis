"""Structured JSON logging for all FEN services.

Every entry point replaces ``logging.basicConfig`` with a call to
``setup_logging("<service-name>", level=log_level_from_env())`` so that each
log line is a single JSON object on stdout — machine-parseable by Loki/ELK
in production (docs/architecture.md "Observability"):

    {"timestamp": "...", "level": "INFO", "service": "fen-bridge-webhook",
     "logger": "services.fen_bridge.webhook", "message": "...", ...extras}

``extra=`` fields passed to the logging call are merged into the JSON object
(the standard logging record attributes are excluded).
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone

_JSON_HANDLER_MARKER = "_fen_json_handler"

# Standard attributes that logging attaches to every LogRecord; everything
# else found on the record is treated as a user-supplied extra field.
_RESERVED_ATTRIBUTES = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "taskName", "message", "asctime",
    }
)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line: timestamp, level, service, logger,
    message, exception (when one is attached), plus any extra fields.
    """

    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRIBUTES or key.startswith("_"):
                continue
            payload[key] = value
        return json.dumps(payload, ensure_ascii=False, default=str)


def log_level_from_env() -> int:
    """LOG_LEVEL (DEBUG/INFO/WARNING/ERROR) as a logging level int, default
    INFO. Unknown values fall back to INFO instead of raising.
    """
    return getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)


def setup_logging(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """Configure the root logger to emit JSON lines to stdout.

    Idempotent: any previously installed FEN JSON handler is replaced, so the
    most recent ``service_name`` wins (each process runs exactly one service).
    Returns the service's logger.
    """
    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        if getattr(handler, _JSON_HANDLER_MARKER, False):
            root.removeHandler(handler)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service_name))
    setattr(handler, _JSON_HANDLER_MARKER, True)
    root.addHandler(handler)
    return logging.getLogger(service_name)
