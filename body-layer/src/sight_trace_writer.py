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
body direction (set by `logger._apply_active_gaze`, never a cockpit
readback). The head's own world-frame state (`mode`, `world_az_true_deg`/
`world_el_deg`, `goal_world_az_deg`/`goal_world_el_deg`, `aim_source`) is
carried separately, and the DCS-slave servo's own status (`sight_servo_
latest`, `GET /sight_servo/latest`) when available -- mode, the mark-
derived body direction, error, and the stall flag."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import Any, TextIO

from belief.optic_policy import OpticState
from belief.sight_effector import GuidanceUnitState
from belief.sight_head import SightHead

#: Same reasoning/value as `detection_trace_writer.DEFAULT_FLUSH_EVERY_N_
#: POLLS` -- a few polls' worth of buffering, not "as rarely as possible".
DEFAULT_FLUSH_EVERY_N_POLLS = 5


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
    ) -> None:
        """Appends this poll's one row. Called every poll, unconditionally
        (unlike the Lua-side per-frame log, which only runs while OBSERV
        is on -- body-layer's own 1 Hz poll cannot see a slew in progress
        either way, so "every poll" here is for continuity of the belief-
        side record, not resolution). `sight_servo_latest` is the raw
        `GET /sight_servo/latest` dict (`None` before the first sample, or
        for a caller that does not poll it) -- optional so every existing
        construction/call site keeps working."""
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

    servo_mode = None
    servo_error_azimuth_deg = None
    servo_error_elevation_deg = None
    servo_stalled = None
    if sight_servo_latest is not None:
        servo_mode = sight_servo_latest.get("mode")
        servo_error_azimuth_deg = sight_servo_latest.get("error_azimuth_deg")
        servo_error_elevation_deg = sight_servo_latest.get("error_elevation_deg")
        servo_stalled = sight_servo_latest.get("stalled")

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
        "servo_mode": servo_mode,
        "servo_error_azimuth_deg": servo_error_azimuth_deg,
        "servo_error_elevation_deg": servo_error_elevation_deg,
        "servo_stalled": servo_stalled,
        "observ_commanded": guidance_unit_state.observ_commanded,
        "observ_observed": guidance_unit_state.observ_observed,
        "optic_mode": (
            optic_state.look_optic.name if desired_azimuth_deg is not None else None
        ),
    }
