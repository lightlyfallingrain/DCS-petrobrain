"""Tests for `sight_trace_writer.SightTraceWriter` -- `--slew-trace`
(`BL-B66` Stage 4b, extended by `[[BL-B80]]` v2).

v1's "874/876 preferred as readback" tests are gone with that code (the
Removal commit) -- these cover the v2 shape: desired/actual (body),
the simulated head's own world-frame state, and the DCS-servo columns
sourced from an optional `sight_servo_latest` dict."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from belief.optic_policy import OpticState
from belief.sight_effector import GuidanceUnitState
from belief.sight_head import SightHead
from perception.detection_trace import DetectionTrace, GateOutcome
from perception.optics import SIGHT_WIDE_OPTIC
from perception.source import OwnshipState
from sight_trace_writer import SightTraceWriter


def _row(path: Path, index: int = 0) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return dict(json.loads(lines[index]))


class TestFieldSelection:
    def test_desired_and_actual_are_body_relative(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        optic_state = OpticState(
            look_azimuth_deg=10.0,
            look_elevation_deg=5.0,
            actual_aim_azimuth_deg=7.0,
            actual_aim_elevation_deg=4.0,
        )
        writer.write_poll(1.0, optic_state, GuidanceUnitState(), SightHead())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["desired_azimuth_deg"] == pytest.approx(10.0)
        assert row["actual_azimuth_deg"] == pytest.approx(7.0)
        assert row["error_azimuth_deg"] == pytest.approx(3.0)
        assert row["error_elevation_deg"] == pytest.approx(1.0)

    def test_everything_is_null_while_no_look_is_commanded(
        self, tmp_path: Path
    ) -> None:
        """Scanning, not sighting -- `OpticState()`'s own defaults."""
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(1.0, OpticState(), GuidanceUnitState(), SightHead())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["desired_azimuth_deg"] is None
        assert row["actual_azimuth_deg"] is None
        assert row["error_azimuth_deg"] is None
        assert row["optic_mode"] is None

    def test_optic_mode_is_the_active_looks_optic_name(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        optic_state = OpticState(
            look_azimuth_deg=0.0,
            look_elevation_deg=0.0,
            look_optic=SIGHT_WIDE_OPTIC,
        )
        writer.write_poll(1.0, optic_state, GuidanceUnitState(), SightHead())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["optic_mode"] == SIGHT_WIDE_OPTIC.name

    def test_observ_commanded_and_observed_are_carried_through(
        self, tmp_path: Path
    ) -> None:
        """`observ_commanded` moved off `GuidanceUnitState` onto the
        engine's own `EffectorRunState.commanded_values` (`plans/
        effector-sequences/plan.md` Stage 2, "What moves, what stays")."""
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        guidance_unit_state = GuidanceUnitState(observ_observed=False)
        writer.write_poll(
            1.0,
            OpticState(),
            guidance_unit_state,
            SightHead(),
            commanded_values={"observ": "on"},
        )
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["observ_commanded"] is True
        assert row["observ_observed"] is False

    def test_observ_commanded_defaults_to_false_when_none_given(
        self, tmp_path: Path
    ) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(1.0, OpticState(), GuidanceUnitState(), SightHead())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["observ_commanded"] is False

    def test_head_fields_carried_through(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        head = SightHead(
            mode="free",
            world_az_true_deg=12.0,
            world_el_deg=-3.0,
            goal_world_az_deg=15.0,
            goal_world_el_deg=-1.0,
            aim_source="seen",
        )
        writer.write_poll(1.0, OpticState(), GuidanceUnitState(), head)
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["head_mode"] == "free"
        assert row["head_world_azimuth_deg"] == pytest.approx(12.0)
        assert row["head_world_elevation_deg"] == pytest.approx(-3.0)
        assert row["head_goal_world_azimuth_deg"] == pytest.approx(15.0)
        assert row["head_goal_world_elevation_deg"] == pytest.approx(-1.0)
        assert row["aim_source"] == "seen"

    def test_servo_columns_null_without_a_servo_sample(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(1.0, OpticState(), GuidanceUnitState(), SightHead())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["servo_mode"] is None
        assert row["servo_stalled"] is None

    def test_servo_columns_read_from_the_servo_sample(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(
            1.0,
            OpticState(),
            GuidanceUnitState(),
            SightHead(),
            sight_servo_latest={
                "mode": "closed",
                "error_azimuth_deg": 0.01,
                "error_elevation_deg": -0.02,
                "stalled": False,
            },
        )
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["servo_mode"] == "closed"
        assert row["servo_error_azimuth_deg"] == pytest.approx(0.01)
        assert row["servo_error_elevation_deg"] == pytest.approx(-0.02)
        assert row["servo_stalled"] is False

    def test_asp17_mark_and_setpoint_columns_read_from_the_servo_sample(
        self, tmp_path: Path
    ) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(
            1.0,
            OpticState(),
            GuidanceUnitState(),
            SightHead(),
            sight_servo_latest={
                "dcs_model_time_s": 0.98,
                "setpoint_azimuth_deg": 4.0,
                "setpoint_elevation_deg": -3.0,
                "mark_azimuth_deg": 3.5,
                "mark_elevation_deg": -2.5,
                "mark_clipped": True,
                "field_target_azimuth_deg": 3.6,
                "field_target_elevation_deg": -2.4,
                "stall_count": 2,
            },
        )
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["servo_dcs_model_time_s"] == pytest.approx(0.98)
        assert row["servo_setpoint_azimuth_deg"] == pytest.approx(4.0)
        assert row["servo_setpoint_elevation_deg"] == pytest.approx(-3.0)
        assert row["servo_mark_azimuth_deg"] == pytest.approx(3.5)
        assert row["servo_mark_elevation_deg"] == pytest.approx(-2.5)
        assert row["servo_mark_clipped"] is True
        assert row["servo_field_target_azimuth_deg"] == pytest.approx(3.6)
        assert row["servo_field_target_elevation_deg"] == pytest.approx(-2.4)
        assert row["servo_stall_count"] == 2


class TestOwnship:
    def test_attitude_and_position_carried_through(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(
            1.0,
            OpticState(),
            GuidanceUnitState(),
            SightHead(),
            ownship=OwnshipState(
                t_sim=1.0,
                x=100.0,
                z=200.0,
                alt_m=650.0,
                heading_true_deg=292.0,
                pitch_deg=-6.5,
                bank_deg=12.0,
            ),
        )
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["ownship_x"] == pytest.approx(100.0)
        assert row["ownship_z"] == pytest.approx(200.0)
        assert row["ownship_alt_m"] == pytest.approx(650.0)
        assert row["ownship_heading_true_deg"] == pytest.approx(292.0)
        assert row["ownship_pitch_deg"] == pytest.approx(-6.5)
        assert row["ownship_bank_deg"] == pytest.approx(12.0)

    def test_attitude_null_without_telemetry(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(1.0, OpticState(), GuidanceUnitState(), SightHead())
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["ownship_pitch_deg"] is None
        assert row["ownship_bank_deg"] is None


def _trace(
    object_id: int, outcome: GateOutcome, optic: str, range_m: float = 3000.0
) -> DetectionTrace:
    return DetectionTrace(
        object_id=object_id,
        object_type="BMP-2",
        t_sim=1.0,
        true_bearing_deg=45.0,
        true_range_m=range_m,
        range_threshold_m=5000.0,
        threshold_bound="optic",
        outcome=outcome,
        true_elevation_deg=-2.0,
        optic=optic,
    )


class TestSightFov:
    def test_keeps_only_sight_optic_rows_past_the_fov_gate(
        self, tmp_path: Path
    ) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(
            1.0,
            OpticState(),
            GuidanceUnitState(),
            SightHead(),
            detection_records=[
                _trace(1, GateOutcome.ADMITTED, "sight_narrow"),
                _trace(2, GateOutcome.TERRAIN_LOS, "sight_wide"),
                _trace(3, GateOutcome.RANGE_OR_SIZE, "sight_narrow"),
                _trace(4, GateOutcome.FOREST, "sight_narrow"),
                _trace(5, GateOutcome.OPTIC_FOV, "sight_narrow"),
                _trace(6, GateOutcome.GAZE, "sight_narrow"),
                _trace(7, GateOutcome.PLAYER_BUBBLE, "sight_narrow"),
                _trace(8, GateOutcome.COCKPIT_MASK, "sight_narrow"),
                _trace(9, GateOutcome.ADMITTED, "unaided"),
                _trace(10, GateOutcome.ADMITTED, "binocular"),
            ],
        )
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        sight_fov = row["sight_fov"]
        assert isinstance(sight_fov, list)
        assert sorted(entry["object_id"] for entry in sight_fov) == [1, 2, 3, 4]

    def test_entries_nearest_first_with_truth_geometry(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(
            1.0,
            OpticState(),
            GuidanceUnitState(),
            SightHead(),
            detection_records=[
                _trace(1, GateOutcome.ADMITTED, "sight_narrow", range_m=4000.0),
                _trace(2, GateOutcome.TERRAIN_LOS, "sight_narrow", range_m=2500.0),
            ],
        )
        writer.flush()

        row = _row(tmp_path / "slew.jsonl")
        assert row["sight_fov"] == [
            {
                "object_id": 2,
                "object_type": "BMP-2",
                "optic": "sight_narrow",
                "outcome": "terrain_los",
                "true_bearing_deg": 45.0,
                "true_elevation_deg": -2.0,
                "true_range_m": 2500.0,
            },
            {
                "object_id": 1,
                "object_type": "BMP-2",
                "optic": "sight_narrow",
                "outcome": "admitted",
                "true_bearing_deg": 45.0,
                "true_elevation_deg": -2.0,
                "true_range_m": 4000.0,
            },
        ]

    def test_empty_without_records(self, tmp_path: Path) -> None:
        writer = SightTraceWriter(tmp_path / "slew.jsonl")
        writer.write_poll(1.0, OpticState(), GuidanceUnitState(), SightHead())
        writer.flush()

        assert _row(tmp_path / "slew.jsonl")["sight_fov"] == []


class TestBufferingAndFailure:
    def test_writes_every_poll_but_flushes_only_every_n(self, tmp_path: Path) -> None:
        path = tmp_path / "slew.jsonl"
        writer = SightTraceWriter(path, flush_every_n_polls=3)

        for i in range(2):
            writer.write_poll(float(i), OpticState(), GuidanceUnitState(), SightHead())
        # Not auto-flushed yet -- the internal counter, not a file read
        # (Python/OS write buffering makes "has it reached disk" an
        # unreliable thing to assert on directly).
        assert writer._polls_since_flush == 2
        writer.write_poll(2.0, OpticState(), GuidanceUnitState(), SightHead())
        # Third poll crosses the threshold -- `flush()` fires automatically
        # and resets the counter.
        assert writer._polls_since_flush == 0
        assert len(path.read_text(encoding="utf-8").splitlines()) == 3

    def test_close_flushes_and_closes(self, tmp_path: Path) -> None:
        path = tmp_path / "slew.jsonl"
        writer = SightTraceWriter(path)
        writer.write_poll(0.0, OpticState(), GuidanceUnitState(), SightHead())
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
            writer.write_poll(float(i), OpticState(), GuidanceUnitState(), SightHead())

        assert full_disk.writes == 1, "kept writing after the first failure"
        assert capsys.readouterr().err.count("sight-trace: write to") == 1
