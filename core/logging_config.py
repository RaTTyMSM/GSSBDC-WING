"""
Structured logging for GSSBDC WING.

- Console: human-readable key=value lines
- Optional file: JSON lines (one JSON object per line) in logs/app.log
- Use: from core.logging_config import get_logger
       log = get_logger(__name__)
       log.info("user_login", user_id=5, username="masum")
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
LOG_LEVEL = os.environ.get("GSSBDC_LOG_LEVEL", "INFO").upper()
LOG_JSON_FILE = os.environ.get("GSSBDC_LOG_JSON", "1") != "0"  # default: write JSON file


class StructuredFormatter(logging.Formatter):
    """Console: 2026-08-13 22:30:00 INFO [gssbdc.app] event=user_login user_id=5"""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        base = f"{ts} {record.levelname:<7} [{record.name}] {record.getMessage()}"
        extras = getattr(record, "extras", None)
        if extras:
            kv = " ".join(f"{k}={_fmt(v)}" for k, v in extras.items())
            base = f"{base} | {kv}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


class JsonFormatter(logging.Formatter):
    """File: one JSON object per line (JSON Lines)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extras = getattr(record, "extras", None)
        if extras:
            payload.update(extras)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def _fmt(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if any(c.isspace() for c in s) or "=" in s:
        return json.dumps(s, ensure_ascii=False)
    return s


class StructuredLogger(logging.LoggerAdapter):
    """log.info("event_name", key=value, ...) -> structured fields."""

    def process(self, msg, kwargs):
        # Pull structured fields out of kwargs into record.extras
        standard = {"exc_info", "stack_info", "stacklevel", "extra"}
        fields = {k: v for k, v in kwargs.items() if k not in standard}
        for k in fields:
            kwargs.pop(k)
        extra = kwargs.get("extra") or {}
        extra["extras"] = fields
        kwargs["extra"] = extra
        return msg, kwargs


_configured = False


def setup_logging() -> None:
    """Call once at app startup."""
    global _configured
    if _configured:
        return
    _configured = True

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Console (human-readable)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    console.setFormatter(StructuredFormatter())
    root.addHandler(console)

    # File (JSON lines)
    if LOG_JSON_FILE:
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            path = os.path.join(LOG_DIR, "app.log")
            fh = logging.FileHandler(path, encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(JsonFormatter())
            root.addHandler(fh)
        except OSError as e:
            console.emit(logging.LogRecord(
                name="gssbdc.logging", level=logging.WARNING,
                pathname="", lineno=0, msg=f"Could not open log file: {e}",
                args=(), exc_info=None,
            ))

    # Quiet noisy libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("engineio").setLevel(logging.WARNING)
    logging.getLogger("socketio").setLevel(logging.WARNING)


def get_logger(name: str) -> StructuredLogger:
    """Return a structured logger for a module, e.g. get_logger(__name__)."""
    if not _configured:
        setup_logging()
    # Normalize: core.db -> gssbdc.db, app -> gssbdc.app
    if name == "__main__" or name == "app":
        name = "gssbdc.app"
    elif name.startswith("core."):
        name = "gssbdc." + name.split(".", 1)[1]
    elif name.startswith("modules."):
        name = "gssbdc." + name.split(".", 1)[1]
    elif not name.startswith("gssbdc"):
        name = f"gssbdc.{name}"
    return StructuredLogger(logging.getLogger(name), {})