from __future__ import annotations

import logging
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from pathlib import Path
import queue
import sys
from typing import Any

from app.core.logging.formatters import JSONLinesFormatter

RAW_LLM_LOGGER_NAME = "moneypal.llm.raw"
PARSED_LLM_LOGGER_NAME = "moneypal.llm.parsed"
EVENT_LOGGER_NAME = "moneypal.event"

_listener: QueueListener | None = None
_log_queue: queue.Queue | None = None
_file_handlers: list[RotatingFileHandler] = []


class _LoggerPrefixFilter(logging.Filter):
    """Filter records matching logger prefix."""

    def __init__(self, prefix: str) -> None:
        super().__init__()
        self.prefix = prefix

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith(self.prefix)


def get_raw_llm_logger() -> logging.Logger:
    return logging.getLogger(RAW_LLM_LOGGER_NAME)


def get_parsed_llm_logger() -> logging.Logger:
    return logging.getLogger(PARSED_LLM_LOGGER_NAME)


def get_event_logger() -> logging.Logger:
    return logging.getLogger(EVENT_LOGGER_NAME)


def start_logging(
    *,
    log_dir: Path | str | None = None,
    max_bytes: int | None = None,
    backup_count: int | None = None,
    mask_pii: bool = False,
    raw_enabled: bool = True,
    parsed_enabled: bool = True,
    event_enabled: bool = True,
    force: bool = False,
) -> QueueListener | None:
    """Initialize rotating stream handlers with a non-blocking QueueListener."""
    global _listener, _log_queue, _file_handlers

    if _listener is not None:
        if force or log_dir is not None:
            stop_logging()
        else:
            return _listener

    from app.core.config import settings

    target_dir = Path(log_dir or getattr(settings, "log_dir", settings.macro_data_dir.parent / "logs"))
    target_dir.mkdir(parents=True, exist_ok=True)

    max_b = int(
        max_bytes
        if max_bytes is not None
        else getattr(settings, "log_rotation_max_bytes", 50 * 1024 * 1024)
    )
    backups = int(
        backup_count
        if backup_count is not None
        else getattr(settings, "log_rotation_backup_count", 10)
    )
    pii = bool(mask_pii or getattr(settings, "log_mask_pii", False))

    formatter = JSONLinesFormatter(mask_pii=pii)
    handlers: list[logging.Handler] = []
    _file_handlers = []

    # 1. Raw LLM traces stream
    if raw_enabled and getattr(settings, "log_raw_traces_enabled", True):
        raw_handler = RotatingFileHandler(
            target_dir / "llm_raw_traces.jsonl",
            maxBytes=max_b,
            backupCount=backups,
            encoding="utf-8",
        )
        raw_handler.setFormatter(formatter)
        raw_handler.addFilter(_LoggerPrefixFilter(RAW_LLM_LOGGER_NAME))
        handlers.append(raw_handler)
        _file_handlers.append(raw_handler)

    # 2. Parsed LLM outputs & tool calls stream
    if parsed_enabled and getattr(settings, "log_parsed_outputs_enabled", True):
        parsed_handler = RotatingFileHandler(
            target_dir / "llm_parsed_outputs.jsonl",
            maxBytes=max_b,
            backupCount=backups,
            encoding="utf-8",
        )
        parsed_handler.setFormatter(formatter)
        parsed_handler.addFilter(_LoggerPrefixFilter(PARSED_LLM_LOGGER_NAME))
        handlers.append(parsed_handler)
        _file_handlers.append(parsed_handler)

    # 3. Application domain events stream
    if event_enabled and getattr(settings, "log_app_events_enabled", True):
        event_handler = RotatingFileHandler(
            target_dir / "app_events.jsonl",
            maxBytes=max_b,
            backupCount=backups,
            encoding="utf-8",
        )
        event_handler.setFormatter(formatter)
        event_handler.addFilter(_LoggerPrefixFilter(EVENT_LOGGER_NAME))
        handlers.append(event_handler)
        _file_handlers.append(event_handler)

    if not handlers:
        return None

    class ContextInjectingQueueHandler(QueueHandler):
        def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
            from app.core.logging.context import get_trace_context

            ctx = get_trace_context()
            for k, v in ctx.items():
                if not hasattr(record, k):
                    setattr(record, k, v)
            return super().prepare(record)

    _log_queue = queue.Queue(-1)
    queue_handler = ContextInjectingQueueHandler(_log_queue)

    for logger_name in (RAW_LLM_LOGGER_NAME, PARSED_LLM_LOGGER_NAME, EVENT_LOGGER_NAME):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        # Avoid duplicating heavy json payloads to root/console
        logger.propagate = False
        # Remove existing QueueHandlers to avoid double logging on reload
        logger.handlers = [h for h in logger.handlers if not isinstance(h, QueueHandler)]
        logger.addHandler(queue_handler)

    _listener = QueueListener(_log_queue, *handlers, respect_handler_level=True)
    _listener.start()
    return _listener


def stop_logging() -> None:
    """Stop the QueueListener and flush pending log entries to disk."""
    global _listener, _log_queue, _file_handlers

    if _listener is not None:
        _listener.stop()
        _listener = None

    for handler in _file_handlers:
        try:
            handler.flush()
            handler.close()
        except Exception:
            pass
    _file_handlers.clear()
    _log_queue = None
