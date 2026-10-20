"""Tests for `tools/join_voice_latency.py` -- the Stage 5 reducer
(`plans/voice-latency-instrumentation/plan.md`). A dev/pilot post-flight
aid, not a test harness itself, but its own join/ordering/gap-flagging
logic is ordinary pure-function code worth covering directly, same
posture as any other module in this codebase."""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from join_voice_latency import (
    group_by_correlation_id,
    load_belief_truth_log,
    load_latency_log,
    load_speech_log,
    main,
)


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def test_load_latency_log_tags_each_row_with_its_own_stage(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    _write_jsonl(
        path,
        [
            {
                "stage": "capture",
                "correlation_id": "corr-1",
                "outcome": "sent",
                "t_wall": 100.0,
                "post_duration_s": 0.5,
            },
            {
                "stage": "transcribe",
                "correlation_id": "corr-1",
                "outcome": "ok",
                "t_wall": 101.0,
                "transcribe_duration_s": 0.4,
            },
        ],
    )
    rows = load_latency_log(path)
    assert [row.stage for row in rows] == ["capture", "transcribe"]
    assert rows[0].t_wall == 100.0
    assert rows[0].fields["correlation_id"] == "corr-1"


def test_load_belief_truth_log_keeps_only_speech_kind_rows(tmp_path: Path) -> None:
    path = tmp_path / "belief_truth.jsonl"
    _write_jsonl(
        path,
        [
            {"kind": "belief_truth", "t_sim": 1.0},
            {
                "kind": "speech",
                "t_sim": 2.0,
                "text": "Target, armour, 2 o'clock.",
                "correlation_id": "corr-1",
                "push_duration_s": 0.3,
            },
        ],
    )
    rows = load_belief_truth_log(path)
    assert len(rows) == 1
    assert rows[0].stage == "spoken"
    assert rows[0].fields["text"] == "Target, armour, 2 o'clock."


def test_load_speech_log_tags_rows_as_transcript_stage(tmp_path: Path) -> None:
    path = tmp_path / "speech.jsonl"
    _write_jsonl(
        path,
        [
            {
                "transcript": "select target armor",
                "disposition": "act",
                "acted_token": "select_target",
                "correlation_id": "corr-1",
                "t_wall": 102.0,
            }
        ],
    )
    rows = load_speech_log(path)
    assert rows[0].stage == "transcript"
    assert rows[0].fields["disposition"] == "act"


def test_group_by_correlation_id_excludes_rows_with_no_id(tmp_path: Path) -> None:
    path = tmp_path / "latency.jsonl"
    _write_jsonl(
        path,
        [
            {"stage": "capture", "correlation_id": "corr-1", "t_wall": 1.0},
            {"stage": "capture", "correlation_id": None, "t_wall": 2.0},
            {"stage": "capture", "t_wall": 3.0},
        ],
    )
    rows = load_latency_log(path)
    groups = group_by_correlation_id(rows)
    assert set(groups) == {"corr-1"}
    assert len(groups["corr-1"]) == 1


def test_main_prints_timeline_in_pipeline_order_and_flags_missing_stages(
    tmp_path: Path, capsys: object
) -> None:
    """The whole chain for one correlation id, built from all three log
    kinds, deliberately out of file order -- `main`'s own ordering must
    come from the fixed pipeline table, not from how the rows were
    written."""
    latency_path = tmp_path / "latency.jsonl"
    _write_jsonl(
        latency_path,
        [
            {
                "stage": "speak",
                "correlation_id": "corr-1",
                "outcome": "ok",
                "t_wall": 104.0,
                "synth_duration_s": 0.2,
                "deliver_duration_s": 0.1,
            },
            {
                "stage": "capture",
                "correlation_id": "corr-1",
                "outcome": "sent",
                "t_wall": 100.0,
                "post_duration_s": 0.5,
            },
        ],
    )
    speech_path = tmp_path / "speech.jsonl"
    _write_jsonl(
        speech_path,
        [
            {
                "transcript": "select target armor",
                "disposition": "act",
                "acted_token": "select_target",
                "correlation_id": "corr-1",
                "t_wall": 102.0,
                "now_sim": 50.0,
            }
        ],
    )
    # No belief-truth-log given at all -- the "spoken" stage must be
    # flagged as never reached, not silently omitted. Also no "transcribe"
    # row, for the same reason.

    main(
        [
            "--latency-log",
            str(latency_path),
            "--speech-log",
            str(speech_path),
        ]
    )
    out = capsys.readouterr().out  # type: ignore[attr-defined]

    assert "=== corr-1 ===" in out
    capture_line = out.index("capture")
    transcript_line = out.index("transcript")
    speak_line = out.index("speak", transcript_line)
    assert capture_line < transcript_line < speak_line
    assert "never reached: transcribe, spoken" in out
    assert "1 correlated utterance(s); 0 row(s) with no id." in out


def test_main_counts_unattributed_rows_separately(
    tmp_path: Path, capsys: object
) -> None:
    latency_path = tmp_path / "latency.jsonl"
    _write_jsonl(
        latency_path,
        [
            {"stage": "capture", "outcome": "dropped", "t_wall": 100.0},
        ],
    )
    main(["--latency-log", str(latency_path)])
    out = capsys.readouterr().out  # type: ignore[attr-defined]
    assert "No correlated rows found." in out
    assert "0 correlated utterance(s); 1 row(s) with no id." in out


def test_truncated_last_line_is_skipped_and_all_other_rows_still_join(
    tmp_path: Path, capsys: object
) -> None:
    """`BL-B88` -- the realistic trigger for a malformed line is a process
    killed mid-write (a DCS crash, a mission reload, a power-cycle), which
    truncates exactly the *last* line of whichever file was open. That one
    line must cost itself, not every row in the file: the well-formed row
    above it still joins, the run completes, and the skipped count appears
    in the closing summary line (not only as a stderr warning nobody
    pipes)."""
    path = tmp_path / "latency.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "stage": "capture",
                    "correlation_id": "corr-1",
                    "outcome": "sent",
                    "t_wall": 100.0,
                }
            )
            + "\n"
        )
        # Truncated mid-write -- an opening object with no closing brace,
        # no trailing newline.
        handle.write('{"stage": "transcribe", "correlation_id": "cor')

    main(["--latency-log", str(path)])
    captured = capsys.readouterr()  # type: ignore[attr-defined]

    assert "=== corr-1 ===" in captured.out
    assert "capture" in captured.out
    assert "1 correlated utterance(s); 0 row(s) with no id." in captured.out
    assert "1 malformed line(s) skipped." in captured.out
    assert f"{path}:2" in captured.err
