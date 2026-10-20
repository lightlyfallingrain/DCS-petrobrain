"""Tests for `logger._reroll_run_logs` -- `plans/bl15-mission-start/plan.md`
Stage 1 Decision 5 ("per mission", not a marker line): on an in-process
mission (re)start, the per-run logs roll to a fresh stamped filename, the
same mechanism `BL-11` Stage 5 already applies once at process start.

Exercises the mechanism directly (not through a real poll loop thread) --
`test_logger.py`'s own poll-loop tests are the wiring-level proof that the
real loops call this at the right point."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from aircraft_client import AircraftLayerClient
from belief.crew_console import CrewConsole
from belief_truth_log import BeliefTruthLogWriter
from detection_trace_writer import DetectionTraceWriter
from logger import ConsolePerceptionRunner, _reroll_run_logs, _speech_log_sink
from mission_memory.entries import FiredOnPayload
from mission_memory.store import MissionMemory


def _runner() -> ConsolePerceptionRunner:
    return ConsolePerceptionRunner(aircraft_client=cast(AircraftLayerClient, object()))


def test_reroll_closes_the_old_detection_trace_writer_and_opens_a_new_one(
    tmp_path: Path,
) -> None:
    base = tmp_path / "trace.jsonl"
    old_writer = DetectionTraceWriter(base)

    new_writer, _ = _reroll_run_logs(
        _runner(),
        None,
        MissionMemory(),
        trace_writer=old_writer,
        belief_truth_writer=None,
        detection_trace_base=base,
        belief_truth_log_base=None,
        speech_log_base=None,
        group_trace_base=None,
        mission_memory_base=None,
        when=1760000000.0,
    )

    assert new_writer is not None
    assert new_writer is not old_writer
    assert old_writer._file.closed
    assert new_writer._path != old_writer._path
    assert new_writer._path.exists()


def test_reroll_closes_the_old_belief_truth_writer_and_rewires_crew_console_sink(
    tmp_path: Path,
) -> None:
    base = tmp_path / "belief_truth.jsonl"
    old_writer = BeliefTruthLogWriter(base)
    runner = _runner()
    runner.last_t_sim = 5.0
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    crew_console.speech_log_sink = _speech_log_sink(old_writer, runner)

    _, new_writer = _reroll_run_logs(
        runner,
        crew_console,
        MissionMemory(),
        trace_writer=None,
        belief_truth_writer=old_writer,
        detection_trace_base=None,
        belief_truth_log_base=base,
        speech_log_base=None,
        group_trace_base=None,
        mission_memory_base=None,
        when=1760000000.0,
    )

    assert new_writer is not None
    assert new_writer is not old_writer
    assert old_writer._file.closed

    # The closure `crew_console.speech_log_sink` was re-built over the new
    # writer, not left pointing at the old (now-closed) one -- the trap this
    # function's own docstring names explicitly.
    assert crew_console.speech_log_sink is not None
    crew_console.speech_log_sink("hello", False, None, None, None, None, None)
    assert new_writer._path.read_text().strip() != ""


def test_reroll_rewires_crew_console_transcript_log(tmp_path: Path) -> None:
    base = tmp_path / "speech.jsonl"
    runner = _runner()
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    _reroll_run_logs(
        runner,
        crew_console,
        MissionMemory(),
        trace_writer=None,
        belief_truth_writer=None,
        detection_trace_base=None,
        belief_truth_log_base=None,
        speech_log_base=base,
        group_trace_base=None,
        mission_memory_base=None,
        when=1760000000.0,
    )

    assert crew_console.transcript_log is not None
    crew_console.transcript_log({"transcript": "watch nearest"})
    rolled = list(tmp_path.glob("speech-*.jsonl"))
    assert len(rolled) == 1
    assert "watch nearest" in rolled[0].read_text()


def test_reroll_rewires_runner_group_trace_sink(tmp_path: Path) -> None:
    base = tmp_path / "group_trace.jsonl"
    runner = _runner()

    _reroll_run_logs(
        runner,
        None,
        MissionMemory(),
        trace_writer=None,
        belief_truth_writer=None,
        detection_trace_base=None,
        belief_truth_log_base=None,
        speech_log_base=None,
        group_trace_base=base,
        mission_memory_base=None,
        when=1760000000.0,
    )

    assert runner.group_trace_sink is not None
    runner.group_trace_sink({"phase": "overlap"})
    rolled = list(tmp_path.glob("group_trace-*.jsonl"))
    assert len(rolled) == 1
    assert "overlap" in rolled[0].read_text()


def test_reroll_rewires_mission_memory_sink(tmp_path: Path) -> None:
    base = tmp_path / "mission_memory.jsonl"
    mission_memory = MissionMemory()

    _reroll_run_logs(
        _runner(),
        None,
        mission_memory,
        trace_writer=None,
        belief_truth_writer=None,
        detection_trace_base=None,
        belief_truth_log_base=None,
        speech_log_base=None,
        group_trace_base=None,
        mission_memory_base=base,
        when=1760000000.0,
    )

    mission_memory.append(
        kind="fired_on",
        provenance="observed",
        t_sim=1.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref="CONTACT_1",
        strikes=None,
        payload=FiredOnPayload(
            shooter_seq=None, shooter_ref="CONTACT_1", targets_ownship=True
        ),
    )

    rolled = list(tmp_path.glob("mission_memory-*.jsonl"))
    assert len(rolled) == 1
    assert "CONTACT_1" in rolled[0].read_text()


def test_reroll_is_a_no_op_for_a_log_that_was_never_enabled(tmp_path: Path) -> None:
    """`base is None` for every log here -- a reroll call where nothing was
    ever enabled must not create any file and must return the (both-None)
    writers unchanged."""
    runner = _runner()
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    trace_writer, belief_truth_writer = _reroll_run_logs(
        runner,
        crew_console,
        MissionMemory(),
        trace_writer=None,
        belief_truth_writer=None,
        detection_trace_base=None,
        belief_truth_log_base=None,
        speech_log_base=None,
        group_trace_base=None,
        mission_memory_base=None,
        when=1760000000.0,
    )

    assert trace_writer is None
    assert belief_truth_writer is None
    assert crew_console.transcript_log is None
    assert runner.group_trace_sink is None
    assert list(tmp_path.iterdir()) == []


def test_reroll_console_mode_skips_speech_log_with_crew_console_none(
    tmp_path: Path,
) -> None:
    """`--console` has no `CrewConsole` -- a `speech_log_base` passed
    through anyway (it never is, from `_run_console_poll_loop`'s own call
    site, but this confirms the guard) must not raise."""
    runner = _runner()
    base = tmp_path / "speech.jsonl"

    _reroll_run_logs(
        runner,
        None,
        MissionMemory(),
        trace_writer=None,
        belief_truth_writer=None,
        detection_trace_base=None,
        belief_truth_log_base=None,
        speech_log_base=base,
        group_trace_base=None,
        mission_memory_base=None,
        when=1760000000.0,
    )  # must not raise

    assert list(tmp_path.iterdir()) == []
