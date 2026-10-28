"""`SightTraceWriter` -- `--slew-trace` (`BL-B66` Stage 4b, extended by
`[[BL-B80]]` v2, `plans/9k113-sight-pointing/plan.md`).

A per-poll JSONL trace of the 9K113 sight's desired-vs-actual aim, so the
rate loop can be tuned from real data instead of guessing: user
direction, 2026-10-21, *"Put logging in so that the slew loop can be
adjusted based on data from logs. Actual vs desired angles especially,
slew command values, etc."*

**v2 columns** (replacing v1's 874/876-as-"readback" shape, since those
args echo the demand rather than a position -- see `belief.sight_head`'s
own docstring): "desired" is still `OpticState.look_azimuth_deg`/
`look_elevation_deg` (belief's own commanded aim, body-relative);
"actual" is `OpticState.actual_aim_azimuth_deg`/`actual_aim_elevation_
deg`, which for a sight-tier optic is now the simulated `SightHead`'s own
body direction (set by `body._apply_active_gaze`, never a cockpit
readback). The head's own world-frame state (`mode`, `world_az_true_deg`/
`world_el_deg`, `goal_world_az_deg`/`goal_world_el_deg`, `aim_source`) is
carried separately, and the DCS-slave servo's own status (`sight_servo_
latest`, `GET /sight_servo/latest`) when available -- mode, the mark-
derived body direction, error, and the stall flag.

**v4 columns** (2026-10-28, user direction after a sortie where the
simulated and DCS sight disagreed: *"9K113 pointing and/or sync between
simulated and DCS sight is incorrect"*): the servo's own setpoint, the
ASP-17 mark (crosshair-derived body direction) with its edge-park fields
and its DCS model time, so the simulated head and the real crosshair can
be compared row by row; ownship attitude (`pitch_deg`/`bank_deg`/heading/
position), since the head stabilises a *world* direction and every
body/world conversion depends on them; and `sight_fov`, the objects this
poll's perception evaluated through a sight optic and found inside its
field of view -- what the simulated 9K113 "sees". `sight_fov` carries
ground truth (true bearing/range per object, like the detection trace):
a debug log, never an input to Petrovich."""

from __future__ import annotations

import contextlib
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TextIO

from belief.optic_policy import OpticState
from belief.sight_effector import GuidanceUnitState
from belief.sight_head import SightHead
from perception.detection_trace import DetectionTrace, GateOutcome
from perception.source import OwnshipState

#: Same reasoning/value as `detection_trace_writer.DEFAULT_FLUSH_EVERY_N_
#: POLLS` -- a few polls' worth of buffering, not "as rarely as possible".
DEFAULT_FLUSH_EVERY_N_POLLS = 5

#: Gate outcomes a candidate can only reach *after* clearing the optic's
#: field-of-view gate (`GateOutcome`'s declaration order is the gate
#: order) -- i.e. it was inside the sight's FOV this poll, whether or not
#: range/size, terrain or forest then rejected it.
_INSIDE_FOV_OUTCOMES = frozenset(
    {
        GateOutcome.RANGE_OR_SIZE,
        GateOutcome.TERRAIN_LOS,
        GateOutcome.FOREST,
        GateOutcome.ADMITTED,
    }
)

#: `sight_servo_latest` keys copied through as `servo_<key>` columns,
#: verbatim -- `aircraft-layer`'s `schema.sight_servo.SightServoState`.
_SERVO_KEYS = (
    "mode",
    "dcs_model_time_s",
    "setpoint_azimuth_deg",
    "setpoint_elevation_deg",
    "mark_azimuth_deg",
    "mark_elevation_deg",
    "mark_clipped",
    "field_target_azimuth_deg",
    "field_target_elevation_deg",
    "error_azimuth_deg",
    "error_elevation_deg",
    "stalled",
    "stall_count",
)


class SightTraceWriter:
    """Appends one JSON line per poll to `path`, buffering a few polls'
    worth before flushing -- disk I/O only at `write_poll`/`flush`/
    `close`, never on perception's or belief's own critical path."""

    def __init__(
        self,
        path: Path,
        flush_every_n_polls: int = DEFAULT_FLUSH_EVERY_N_POLLS,
    ) -> None:
        self._path = path
        self._file: TextIO = path.open("a", encoding="utf-8")
        self._flush_every_n_polls = flush_every_n_polls
        self._polls_since_flush = 0
        #: Set by `_fail` after the first write error -- see that method.
        self._disabled = False

    def write_poll(
        self,
        t_sim: float,
        optic_state: OpticState,
        guidance_unit_state: GuidanceUnitState,
        sight_head: SightHead,
        sight_servo_latest: dict[str, Any] | None = None,
        commanded_values: Mapping[str, str] | None = None,
        ownship: OwnshipState | None = None,
        detection_records: Sequence[DetectionTrace] = (),
    ) -> None:
        """Appends this poll's one row. Called every poll, unconditionally
        (unlike the Lua-side per-frame log, which only runs while OBSERV
        is on -- body-layer's own 1 Hz poll cannot see a slew in progress
        either way, so "every poll" here is for continuity of the belief-
        side record, not resolution). `sight_servo_latest` is the raw
        `GET /sight_servo/latest` dict (`None` before the first sample, or
        for a caller that does not poll it) -- optional so every existing
        construction/call site keeps working.

        `commanded_values` is `belief.effector_engine.EffectorRunState.
        commanded_values` (`plans/effector-sequences/plan.md`, "What moves,
        what stays" -- `observ_commanded` moved off `GuidanceUnitState` to
        here, Stage 2). `None` -- the default, for every existing call site
        that predates the engine -- reads as "no successful write yet",
        the same `False` default `observ_commanded` already had on
        `GuidanceUnitState` before the move.

        `ownship` is this poll's telemetry (`None` writes null attitude
        columns). `detection_records` is this poll's detection-trace
        entries; only sight-optic rows inside the FOV are kept, as
        `sight_fov`."""
        if self._disabled:
            return
        try:
            self._file.write(
                json.dumps(
                    _row(
                        t_sim,
                        optic_state,
                        guidance_unit_state,
                        sight_head,
                        sight_servo_latest,
                        commanded_values,
                        ownship,
                        detection_records,
                    )
                )
            )
            self._file.write("\n")
        except OSError as exc:
            self._fail(exc)
            return

        self._polls_since_flush += 1
        if self._polls_since_flush >= self._flush_every_n_polls:
            self.flush()

    def flush(self) -> None:
        if self._disabled:
            return
        try:
            self._file.flush()
        except OSError as exc:
            self._fail(exc)
        self._polls_since_flush = 0

    def close(self) -> None:
        """Flush and close, never raising -- same posture as
        `DetectionTraceWriter.close`, for the same reason (the poll loop's
        `finally:` block calls this; an unguarded `OSError` here would be a
        traceback on shutdown in exactly the full-disk scenario this
        module exists to make legible)."""
        self.flush()
        with contextlib.suppress(OSError):
            self._file.close()

    def _fail(self, exc: OSError) -> None:
        """Report one write failure, then stop writing for the rest of the
        run -- same posture as `DetectionTraceWriter._fail`, see that
        method's own docstring for the full reasoning (a full disk mid-
        flight must not become a per-poll traceback storm)."""
        self._disabled = True
        print(
            f"sight-trace: write to {self._path} failed ({exc}); "
            f"no further sight-trace rows will be written this run",
            file=sys.stderr,
        )


def _row(
    t_sim: float,
    optic_state: OpticState,
    guidance_unit_state: GuidanceUnitState,
    sight_head: SightHead,
    sight_servo_latest: dict[str, Any] | None,
    commanded_values: Mapping[str, str] | None = None,
    ownship: OwnshipState | None = None,
    detection_records: Sequence[DetectionTrace] = (),
) -> dict[str, object | None]:
    desired_azimuth_deg = optic_state.look_azimuth_deg
    desired_elevation_deg = optic_state.look_elevation_deg
    actual_azimuth_deg = optic_state.actual_aim_azimuth_deg
    actual_elevation_deg = optic_state.actual_aim_elevation_deg

    error_azimuth_deg = (
        desired_azimuth_deg - actual_azimuth_deg
        if desired_azimuth_deg is not None and actual_azimuth_deg is not None
        else None
    )
    error_elevation_deg = (
        desired_elevation_deg - actual_elevation_deg
        if desired_elevation_deg is not None and actual_elevation_deg is not None
        else None
    )

    servo = sight_servo_latest or {}

    return {
        "t": t_sim,
        "desired_azimuth_deg": desired_azimuth_deg,
        "desired_elevation_deg": desired_elevation_deg,
        "actual_azimuth_deg": actual_azimuth_deg,
        "actual_elevation_deg": actual_elevation_deg,
        "error_azimuth_deg": error_azimuth_deg,
        "error_elevation_deg": error_elevation_deg,
        "head_mode": sight_head.mode,
        "head_world_azimuth_deg": sight_head.world_az_true_deg,
        "head_world_elevation_deg": sight_head.world_el_deg,
        "head_goal_world_azimuth_deg": sight_head.goal_world_az_deg,
        "head_goal_world_elevation_deg": sight_head.goal_world_el_deg,
        "aim_source": sight_head.aim_source,
        **{f"servo_{key}": servo.get(key) for key in _SERVO_KEYS},
        "observ_commanded": ((commanded_values or {}).get("observ") == "on"),
        "observ_observed": guidance_unit_state.observ_observed,
        "optic_mode": (
            optic_state.look_optic.name if desired_azimuth_deg is not None else None
        ),
        "ownship_x": ownship.x if ownship is not None else None,
        "ownship_z": ownship.z if ownship is not None else None,
        "ownship_alt_m": ownship.alt_m if ownship is not None else None,
        "ownship_heading_true_deg": (
            ownship.heading_true_deg if ownship is not None else None
        ),
        "ownship_pitch_deg": ownship.pitch_deg if ownship is not None else None,
        "ownship_bank_deg": ownship.bank_deg if ownship is not None else None,
        "sight_fov": _sight_fov(detection_records),
    }


def _sight_fov(records: Sequence[DetectionTrace]) -> list[dict[str, object]]:
    """This poll's sight-optic candidates that were inside the FOV, nearest
    first. Empty when no sight optic was looked through this poll."""
    inside = [
        record
        for record in records
        if record.optic.startswith("sight") and record.outcome in _INSIDE_FOV_OUTCOMES
    ]
    inside.sort(key=lambda record: record.true_range_m)
    return [
        {
            "object_id": record.object_id,
            "object_type": record.object_type,
            "optic": record.optic,
            "outcome": record.outcome.value,
            "true_bearing_deg": record.true_bearing_deg,
            "true_elevation_deg": record.true_elevation_deg,
            "true_range_m": record.true_range_m,
        }
        for record in inside
    ]
