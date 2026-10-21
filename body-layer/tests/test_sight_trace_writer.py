"""Tests for `sight_trace_writer.SightTraceWriter` -- `--slew-trace`
(`BL-B66` Stage 4b, `plans/9k113-effectors/plan.md`).

Mirrors `detection_trace_writer.DetectionTraceWriter`'s own tests for the
buffering/disable-after-first-failure shape (via `write_logger.py`'s
wiring-level tests for the real poll loop, see `test_logger.py`), plus the
field-by-field logic unique to this writer: desired-vs-actual source
selection and the azimuth-only raw-to-degrees conversion."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from belief.optic_policy import OpticState
from belief.sight_effector import GuidanceUnitState
from perception.optics import SIGHT_WIDE_OPTIC
from sight_trace_writer import SightTraceWriter


def _row(path: Path, index: int = 0) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(json.loads(lines[index]))


class TestFieldSelection:
    def test_actual_azimuth_prefers_readback_and_converts_to_degrees(
        self, tmp_path: Path
    ) -> None:
        """Azimuth has a confirmed raw-to-degrees calibration
        (`sight_effector.sight_azimuth_raw_to_deg`) -- when a readback
        exists, it wins over the model value and the source says so."""
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        optic_state = OpticState(
            look_azimuth_deg=10.0,
            look_elevation_deg=5.0,
            actual_aim_azimuth_deg=10.0,  # model says "arrived"
            actual_aim_elevation_deg=5.0,
        )
        # 0.16500 raw * (60 / 0.44) = 22.5 deg -- the probe's own measured
        # conversion (`aircraft-layer/research/2026-10-17-9k113-effector-
        # and-slew-probe-findings.md` finding 2).
        guidance_unit_state = GuidanceUnitState(sight_az_raw=0.16500)
        writer.write_poll(1.0, optic_state, guidance_unit_state)
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["actual_azimuth_source"] == "readback"
        assert row["actual_azimuth_deg"] == pytest.approx(22.5)
        assert row["raw_sight_az"] == pytest.approx(0.16500)

    def test_actual_azimuth_falls_back_to_model_when_no_readback(
        self, tmp_path: Path
    ) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        optic_state = OpticState(
            look_azimuth_deg=10.0,
            look_elevation_deg=5.0,
            actual_aim_azimuth_deg=7.5,
            actual_aim_elevation_deg=5.0,
        )
        writer.write_poll(1.0, optic_state, GuidanceUnitState())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["actual_azimuth_source"] == "model"
        assert row["actual_azimuth_deg"] == pytest.approx(7.5)
        assert row["raw_sight_az"] is None

    def test_actual_elevation_is_always_model_source_never_readback(
        self, tmp_path: Path
    ) -> None:
        """Arg 876's degrees-per-unit is unmeasured -- even with a raw
        readback present, elevation's `_source` stays `"model"`, and the
        raw value is still logged separately so a conversion can be
        derived later without a second sortie."""
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        optic_state = OpticState(
            look_azimuth_deg=10.0,
            look_elevation_deg=5.0,
            actual_aim_azimuth_deg=10.0,
            actual_aim_elevation_deg=5.0,
        )
        guidance_unit_state = GuidanceUnitState(sight_elev_raw=-0.28125)
        writer.write_poll(1.0, optic_state, guidance_unit_state)
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["actual_elevation_source"] == "model"
        assert row["actual_elevation_deg"] == pytest.approx(5.0)
        assert row["raw_sight_elev"] == pytest.approx(-0.28125)

    def test_error_is_desired_minus_actual(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        optic_state = OpticState(
            look_azimuth_deg=10.0,
            look_elevation_deg=5.0,
            actual_aim_azimuth_deg=7.0,
            actual_aim_elevation_deg=4.0,
        )
        writer.write_poll(1.0, optic_state, GuidanceUnitState())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["error_azimuth_deg"] == pytest.approx(3.0)
        assert row["error_elevation_deg"] == pytest.approx(1.0)

    def test_everything_is_null_while_no_look_is_commanded(
        self, tmp_path: Path
    ) -> None:
        """Scanning, not sighting -- `OpticState()`'s own defaults."""
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(1.0, OpticState(), GuidanceUnitState())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["desired_azimuth_deg"] is None
        assert row["actual_azimuth_deg"] is None
        assert row["actual_azimuth_source"] is None
        assert row["error_azimuth_deg"] is None
        assert row["optic_mode"] is None

    def test_optic_mode_is_the_active_looks_optic_name(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        optic_state = OpticState(
            look_azimuth_deg=0.0,
            look_elevation_deg=0.0,
            look_optic=SIGHT_WIDE_OPTIC,
        )
        writer.write_poll(1.0, optic_state, GuidanceUnitState())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["optic_mode"] == SIGHT_WIDE_OPTIC.name

    def test_observ_commanded_and_observed_are_carried_through(
        self, tmp_path: Path
    ) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        guidance_unit_state = GuidanceUnitState(
            observ_commanded=True, observ_observed=False
        )
        writer.write_poll(1.0, OpticState(), guidance_unit_state)
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["observ_commanded"] is True
        assert row["observ_observed"] is False


class TestBufferingAndFailure:
    def test_writes_every_poll_but_flushes_only_every_n(self, tmp_path: Path) -> None:
        path = tmp_path / "slew.jsonl"
        writer = SightTraceWriter(path, flush_every_n_polls=3)

        for i in range(2):
            writer.write_poll(float(i), OpticState(), GuidanceUnitState())
        # Not auto-flushed yet -- the internal counter, not a file read
        # (Python/OS write buffering makes "has it reached disk" an
        # unreliable thing to assert on directly).
        assert writer._polls_since_flush == 2
        writer.write_poll(2.0, OpticState(), GuidanceUnitState())
        # Third poll crosses the threshold -- `flush()` fires automatically
        # and resets the counter.
        assert writer._polls_since_flush == 0
        assert len(path.read_text(encoding="utf-8").splitlines()) == 3

    def test_close_flushes_and_closes(self, tmp_path: Path) -> None:
        path = tmp_path / "slew.jsonl"
        writer = SightTraceWriter(path)
        writer.write_poll(0.0, OpticState(), GuidanceUnitState())
        writer.close()

        assert len(path.read_text(encoding="utf-8").splitlines()) == 1
        assert writer._file.closed

    def test_a_write_failure_disables_after_one_reported_failure(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Mirrors `test_detection_trace.py`'s own `_FullDiskFile` double
        -- `SightTraceWriter.__init__` opens its file eagerly (same shape
        as `DetectionTraceWriter`), so the simplest way to make a *write*
        fail (as opposed to the *open* failing, which `test_group_trace_
        log.py`'s directory trick exercises for the lazily-opened writers)
        is to swap in a double whose `write` raises `OSError` and whose
        `close` does not."""
        path = tmp_path / "slew.jsonl"
        writer = SightTraceWriter(path, flush_every_n_polls=1)

        class _FullDiskFile:
            def __init__(self) -> None:
                self.writes = 0

            def write(self, text: str) -> int:
                self.writes += 1
                raise OSError(28, "No space left on device")

            def flush(self) -> None:
                pass

            def close(self) -> None:
                pass

        full_disk = _FullDiskFile()
        writer._file = full_disk  # type: ignore[assignment]

        for i in range(3):
            writer.write_poll(float(i), OpticState(), GuidanceUnitState())

        assert full_disk.writes == 1, "kept writing after the first failure"
        assert capsys.readouterr().err.count("sight-trace: write to") == 1
