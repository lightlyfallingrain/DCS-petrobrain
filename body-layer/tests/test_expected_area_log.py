"""Tests for `expected_area_log.ExpectedAreaLogWriter` -- the
`--expected-area-log` writer (`plans/expected-area-look/plan.md` Pass 3).
Mirrors `test_group_trace_log.py`'s own tests (same unbuffered-write/
disable-after-first-failure shape, same "closest existing pattern" the
module's own docstring names)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from expected_area_log import ExpectedAreaLogWriter


def test_write_appends_one_json_line_stamped_with_t_wall(tmp_path: Path) -> None:
    path = tmp_path / "expected-area.jsonl"
    writer = ExpectedAreaLogWriter(path)

    writer.write(
        {
            "t_sim": 12.0,
            "event": "open",
            "b_id": "CONTACT_2",
            "a_id": "CONTACT_1",
            "kind": "fold",
            "age_s": 1.0,
            "released": False,
        }
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["event"] == "open"
    assert row["b_id"] == "CONTACT_2"
    assert "t_wall" in row


def test_write_appends_rather_than_truncates(tmp_path: Path) -> None:
    path = tmp_path / "expected-area.jsonl"
    writer = ExpectedAreaLogWriter(path)

    writer.write({"t_sim": 0.0, "event": "open", "b_id": "CONTACT_2"})
    writer.write(
        {"t_sim": 10.0, "event": "verdict", "b_id": "CONTACT_2", "verdict": "same"}
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["event"] == "open"
    assert json.loads(lines[1])["event"] == "verdict"


def test_an_unwritable_path_disables_after_one_reported_failure(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A directory where the file should be makes every `open("a")` raise
    `OSError`. The writer must report once, on the first failed write, and
    silently no-op on every call after -- a failing debug log must never
    raise into `body._resolve_expected_area_checks`'s caller (the poll
    loop)."""
    path = tmp_path / "expected-area.jsonl"
    path.mkdir()
    writer = ExpectedAreaLogWriter(path)

    for _ in range(3):
        writer.write({"t_sim": 0.0, "event": "open", "b_id": "CONTACT_2"})

    assert capsys.readouterr().err.count("expected-area-log: write to") == 1
