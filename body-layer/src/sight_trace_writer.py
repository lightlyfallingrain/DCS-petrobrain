"""`SightTraceWriter` -- BL-B66 Stage 4b (`plans/9k113-effectors/plan.md`).

A per-poll JSONL trace of the 9K113 sight's desired-vs-actual aim, so
`[[BL-B80]]`'s rate loop can be tuned from real data instead of guessing:
user direction, 2026-10-21, *"Put logging in so that the slew loop can be
adjusted based on data from logs. Actual vs desired angles especially,
slew command values, etc."*

Follows `detection_trace_writer.DetectionTraceWriter`'s own shape
(buffer a few polls, flush periodically, disable-after-first-write-error
rather than crash the sortie) at a fraction of the complexity: there is no
ground-truth/belief join here, just `belief.optic_policy.OpticState` and
`belief.sight_effector.GuidanceUnitState`, both already belief-side and
already public.

**"Desired" is `OpticState.look_azimuth_deg`/`look_elevation_deg`
(belief's own commanded aim); "actual" is the sight head's real position
when a readback exists (`GuidanceUnitState.sight_az_raw`/
`sight_elev_raw`, raw args 874/876), else `OpticState.actual_aim_azimuth_
deg`/`actual_aim_elevation_deg`'s own *model* of the head.** Both axes'
raw readbacks are converted to degrees via `belief.sight_effector`'s
`sight_azimuth_raw_to_deg`/`sight_elevation_raw_to_deg` -- as of
`[[BL-B80]]`, elevation's conversion exists too (derived, not yet
independently measured live -- see that module's own comment), so
`actual_elevation_source` can read `"readback"` the same way azimuth's
already could, once both the conversion and a raw sample exist."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path
from typing import TextIO

from belief.optic_policy import OpticState
from belief.sight_effector import (
    GuidanceUnitState,
    sight_azimuth_raw_to_deg,
    sight_elevation_raw_to_deg,
)

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
    ) -> None:
        """Appends this poll's one row. Called every poll, unconditionally
        (unlike the Lua-side per-frame log, which only runs while OBSERV
        is on -- body-layer's own 1 Hz poll cannot see a slew in progress
        either way, so "every poll" here is for continuity of the belief-
        side record, not resolution)."""
        if self._disabled:
            return
        try:
            self._file.write(json.dumps(_row(t_sim, optic_state, guidance_unit_state)))
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
    t_sim: float, optic_state: OpticState, guidance_unit_state: GuidanceUnitState
) -> dict[str, object | None]:
    raw_az = guidance_unit_state.sight_az_raw
    raw_el = guidance_unit_state.sight_elev_raw

    actual_azimuth_deg: float | None
    actual_azimuth_source: str | None
    if raw_az is not None:
        actual_azimuth_deg = sight_azimuth_raw_to_deg(raw_az)
        actual_azimuth_source = "readback"
    elif optic_state.actual_aim_azimuth_deg is not None:
        actual_azimuth_deg = optic_state.actual_aim_azimuth_deg
        actual_azimuth_source = "model"
    else:
        actual_azimuth_deg = None
        actual_azimuth_source = None

    # `[[BL-B80]]`: elevation now has a conversion too (derived, same
    # "prefer readback, fall back to model" split azimuth already has).
    actual_elevation_deg: float | None
    actual_elevation_source: str | None
    if raw_el is not None:
        actual_elevation_deg = sight_elevation_raw_to_deg(raw_el)
        actual_elevation_source = "readback"
    elif optic_state.actual_aim_elevation_deg is not None:
        actual_elevation_deg = optic_state.actual_aim_elevation_deg
        actual_elevation_source = "model"
    else:
        actual_elevation_deg = None
        actual_elevation_source = None

    desired_azimuth_deg = optic_state.look_azimuth_deg
    desired_elevation_deg = optic_state.look_elevation_deg

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

    return {
        "t": t_sim,
        "desired_azimuth_deg": desired_azimuth_deg,
        "desired_elevation_deg": desired_elevation_deg,
        "actual_azimuth_deg": actual_azimuth_deg,
        "actual_azimuth_source": actual_azimuth_source,
        "actual_elevation_deg": actual_elevation_deg,
        "actual_elevation_source": actual_elevation_source,
        "error_azimuth_deg": error_azimuth_deg,
        "error_elevation_deg": error_elevation_deg,
        "raw_sight_az": raw_az,
        "raw_sight_elev": raw_el,
        "observ_commanded": guidance_unit_state.observ_commanded,
        "observ_observed": guidance_unit_state.observ_observed,
        "optic_mode": (
            optic_state.look_optic.name if desired_azimuth_deg is not None else None
        ),
    }
