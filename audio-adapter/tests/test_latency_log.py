"""Tests for `latency_log.LatencyLogWriter` -- structurally copied from
`body-layer/src/speech_log.py`'s `SpeechLogWriter`, so these tests mirror
what that module's own behaviour would need (none exist directly for it;
see this module's docstring)."""

from __future__ import annotations

import json
from pathlib import Path

from latency_log import LatencyLogWriter


def test_write_appends_one_json_line_with_t_wall(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    writer = LatencyLogWriter(path)
    writer.write({"stage": "capture", "correlation_id": "abc", "outcome": "ok"})

    lines = path.read_text().splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["stage"] == "capture"
    assert row["correlation_id"] == "abc"
    assert row["outcome"] == "ok"
    assert isinstance(row["t_wall"], float)


def test_write_appends_rather_than_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    writer = LatencyLogWriter(path)
    writer.write({"stage": "capture", "correlation_id": "one", "outcome": "ok"})
    writer.write({"stage": "speak", "correlation_id": "two", "outcome": "ok"})

    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["correlation_id"] == "one"
    assert json.loads(lines[1])["correlation_id"] == "two"


def test_write_failure_disables_further_writes(tmp_path: Path) -> None:
    """Same policy as `SpeechLogWriter`/`DetectionTraceWriter`: reported
    once, then this writer gives up for the rest of the run rather than
    raising on every subsequent call."""
    # A path under a file (not a directory) can never be opened for append.
    bogus_dir = tmp_path / "not-a-directory"
    bogus_dir.write_text("x")
    path = bogus_dir / "latency.jsonl"
    writer = LatencyLogWriter(path)

    writer.write({"stage": "capture", "outcome": "ok"})  # must not raise
    writer.write({"stage": "capture", "outcome": "ok"})  # still must not raise
    assert writer._disabled is True
