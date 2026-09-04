from __future__ import annotations

import json
from pathlib import Path
import time

from app.core.logging import (
    bind_trace,
    log_app_event,
    log_parsed_output,
    log_raw_trace,
    start_logging,
    stop_logging,
)
from app.core.config import settings


def test_rotating_logging_streams(tmp_path: Path):
    start_logging(
        log_dir=tmp_path,
        max_bytes=500,
        backup_count=3,
        mask_pii=True,
        force=True,
    )

    with bind_trace(trace_id="test-trace-123", conversation_id="conv-1", username="analyst_bob"):
        log_raw_trace(
            "LLM completion received",
            provider="groq",
            model="llama-3.3-70b-versatile",
            prompt="what is the total loan disbursement?",
            completion="{\"route\": \"data_warehouse\"}",
            duration_ms=250.5,
            usage={"prompt_tokens": 100, "completion_tokens": 20},
            authorization="Bearer secrettoken123",
        )
        log_parsed_output(
            "Tool execution finished",
            tool_name="lookup_table",
            tool_args={"table": "loan_accounts"},
            tool_result={"row_count": 10},
            duration_ms=45.0,
        )
        log_app_event(
            "Turn started",
            stage="nlq_planning",
            outcome="matched_route",
            duration_ms=12.0,
        )

    # Stop logging to flush the QueueListener
    stop_logging()

    raw_file = tmp_path / "llm_raw_traces.jsonl"
    parsed_file = tmp_path / "llm_parsed_outputs.jsonl"
    event_file = tmp_path / "app_events.jsonl"

    assert raw_file.exists()
    assert parsed_file.exists()
    assert event_file.exists()

    # Verify raw trace content
    raw_lines = [json.loads(line) for line in raw_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(raw_lines) == 1
    assert raw_lines[0]["trace_id"] == "test-trace-123"
    assert raw_lines[0]["user"] == "analyst_bob"
    assert raw_lines[0]["provider"] == "groq"
    assert raw_lines[0]["prompt"] == "what is the total loan disbursement?"
    assert raw_lines[0]["usage"]["prompt_tokens"] == 100
    # Verify redaction
    assert raw_lines[0]["authorization"] == "***REDACTED***"

    # Verify parsed output content
    parsed_lines = [json.loads(line) for line in parsed_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(parsed_lines) == 1
    assert parsed_lines[0]["trace_id"] == "test-trace-123"
    assert parsed_lines[0]["tool_name"] == "lookup_table"
    assert parsed_lines[0]["tool_args"] == {"table": "loan_accounts"}
    assert parsed_lines[0]["status"] == "success"

    # Verify event content
    event_lines = [json.loads(line) for line in event_file.read_text(encoding="utf-8").strip().splitlines()]
    assert len(event_lines) == 1
    assert event_lines[0]["trace_id"] == "test-trace-123"
    assert event_lines[0]["stage"] == "nlq_planning"
    assert event_lines[0]["outcome"] == "matched_route"


def test_rotation_creates_backup_files(tmp_path: Path):
    start_logging(
        log_dir=tmp_path,
        max_bytes=200,  # small threshold to force rotation
        backup_count=3,
        force=True,
    )

    for i in range(25):
        log_raw_trace("Synthetic line", pad="X" * 40, idx=i)

    stop_logging()

    # Check for rotated backup file like llm_raw_traces.jsonl.1
    rotated = list(tmp_path.glob("llm_raw_traces.jsonl*"))
    assert len(rotated) > 1


def test_rotation_uses_configured_limits(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "log_rotation_max_bytes", 200)
    monkeypatch.setattr(settings, "log_rotation_backup_count", 2)
    start_logging(log_dir=tmp_path, force=True)

    try:
        for i in range(25):
            log_raw_trace("Configured rotation line", pad="X" * 40, idx=i)
    finally:
        stop_logging()

    rotated = list(tmp_path.glob("llm_raw_traces.jsonl*"))
    assert len(rotated) == 3
