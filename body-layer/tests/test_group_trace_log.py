"""Tests for `group_trace_log.GroupTraceLogWriter` -- the `--group-trace`
writer (`BL-12` amendment A4). Mirrors `test_logger.py`'s own
`SpeechLogWriter` tests (same unbuffered-write/disable-after-first-failure
shape) rather than `DetectionTraceWriter`'s, which buffers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from group_trace_log import GroupTraceLogWriter


def test_write_appends_one_json_line_stamped_with_t_wall(tmp_path: Path) -> None:
    path = tmp_path / "group-trace.jsonl"
    writer = GroupTraceLogWriter(path)

    writer.write(
        {
            "now_sim": 12.0,
            "phase": "found",
            "group_id": "GROUP_1",
            "member_contact_ids": ["CONTACT_1", "CONTACT_2"],
            "centroid_x": 100.0,
            "centroid_z": 0.0,
            "extent_m": 50.0,
            "composition": [["OP_TRUCK", 2]],
        }
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["phase"] == "found"
    assert row["group_id"] == "GROUP_1"
    assert "t_wall" in row


def test_write_appends_rather_than_truncates(tmp_path: Path) -> None:
    path = tmp_path / "group-trace.jsonl"
    writer = GroupTraceLogWriter(path)

    writer.write({"now_sim": 0.0, "phase": "found", "group_id": "GROUP_1"})
    writer.write({"now_sim": 10.0, "phase": "expired", "group_id": "GROUP_1"})

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["phase"] == "found"
    assert json.loads(lines[1])["phase"] == "expired"


def test_an_unwritable_path_disables_after_one_reported_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Mirrors `test_an_unwritable_speech_log_says_so_once_and_keeps_the_
    command_working`: a directory where the file should be makes every
    `open("a")` raise `OSError`. The writer must report once, on the first
    failed write, and silently no-op on every call after -- a failing
    debug log must never raise into `GroupStore.reconcile`'s caller."""
    path = tmp_path / "group-trace.jsonl"
    path.mkdir()
    writer = GroupTraceLogWriter(path)

    for _ in range(3):
        writer.write({"now_sim": 0.0, "phase": "found", "group_id": "GROUP_1"})

    assert capsys.readouterr().err.count("group-trace: write to") == 1
