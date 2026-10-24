"""The 9K113 guidance unit's own observed cockpit state (lamps/switch
readback) plus the sight-slew wire -- `plans/9k113-effectors/plan.md`
(BL-B66) and `plans/9k113-sight-pointing/plan.md` (`[[BL-B80]]`).

**Sequencing moved out, Stage 2, `plans/effector-sequences/plan.md`
("What moves, what stays").** This module used to also *drive* the
guidance-unit power-up sequence and the single OBSERV/weapons-safety
writes (`start_power_up`/`advance_power_up`/`write_observ`/`write_
weapon_safety`, plus `_POWER_UP_SWITCHES` and the device/cmd constants
those four functions alone used). All of that is now data
(`config/sequences/mi-24p/*.md`) walked by `belief.effector_engine`,
which knows device/cmd/arg numbers only via the curated registry it
loads, not as constants in this file. **What stays here**:
`GuidanceUnitState`'s *readback* fields (`BL-B80`'s `SightHead`/
`home_phase` derivation and `sight_ready()` read them directly, and
`sight_trace_writer`'s `observ_commanded` column -- sourced from the
engine's own `EffectorRunState.commanded_values` now, not this class --
keeps reading `observ_observed` from here unchanged), `sight_ready()`
itself, `refresh_readback`, and the slew/pointing wire
(`write_sight_target`), none of which this plan's Stage 2 touches.

**`[[BL-B80]]` (`plans/9k113-sight-pointing/plan.md`, re-plan v2) adds the
real pointing channel.** `write_sight_target` sends a **world** goal
direction plus rate and `t_sim` straight through in degrees -- no raw
command-unit conversion on this side any more (v1's azimuth/elevation
degree<->raw conversions are removed: `Export.lua`'s own per-frame servo
owns that conversion now, since the wire itself carries degrees). The
gyro-alignment window is no longer a timer either: `GuidanceUnitState`
gains `align_observed`/`ready_observed`/`launch_perm_observed`, the real
898/960/962 lamp readbacks, and `belief.sight_head.SightHead`'s own
`mode` (driven by `align_observed`) is what gates perception -- see that
module's own docstring. The per-frame rate-limiting/servo loop itself
lives in `Export.lua`, not here (the plan's "Architecture: who owns
what")."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from aircraft_client import AircraftLayerClient

#: The continuous (polled) set's own code-required args (plan S4.4a) --
#: always unioned into `effector_registry.load_polled_config`'s result,
#: with a warning (never a D5 error) if `polled.toml` omits one. Declared
#: beside its readers: `"home_phase"`/`"SightHead.mode"`/`"sight_ready"`
#: each name the one consumer that needs this arg every poll regardless
#: of what any sequence file does (`logger.py`'s `home_phase` derivation,
#: `belief.sight_head.SightHead.mode`, and `sight_ready()` below).
REQUIRED_POLLED_ARGS: Final[dict[int, str]] = {
    886: "home_phase",
    898: "SightHead.mode",
    960: "sight_ready",
}


@dataclass(frozen=True, slots=True)
class GuidanceUnitState:
    """The 9K113 guidance unit's own *observed* state, carried on
    `logger.ConsolePerceptionRunner` the same way `OpticState`/
    `AttackRunState` are -- replaced wholesale each poll via `replace()`,
    never mutated. **One construction site only** (`ConsolePerceptionRunner`'s
    `field(default_factory=GuidanceUnitState)` and mission-reset's
    re-run `__init__`) -- every function in this module returns
    `replace(state, ...)`, never constructs this class fresh (plan's
    "Construction-site check").

    `guidance_unit_ready_prev_observed` carries `ready_observed`'s own
    value as of the end of the *previous* poll, so `CrewConsole.drain_
    guidance_unit_ready` can tell an observed off->on edge (speak) from
    an already-lit lamp (stay silent) or a first-ever sample that
    already reads lit, as a warm air start's does (also stay silent --
    there is no prior `False` reading to rise from). Bug fix, `plans/
    9k113-sight-pointing/plan.md` decision 2 ("only on change"): the
    one-shot `bool` latch this field replaced spoke on the very first
    poll that ever read the lamp lit, including a warm air start's first
    sample, and then never spoke again for the rest of the mission even
    across a power cycle.

    `observ_observed`/`weapon_safety_observed` are the cockpit's own
    telemetry readback for OBSERV. and the weapons safety bar.
    `observ_observed` is a `REQUIRED_POLLED_ARGS` member (`logger.py`'s
    poll loop derives `OpticState.home_phase` from it every poll).
    `weapon_safety_observed` **has no reader as of Stage 4** (`plans/
    effector-sequences/plan.md`): arg 673 is no longer polled by any
    code, having lost its old per-frame reader
    (`push_cockpit_switch_state`) with nothing replacing it yet -- it
    stays whatever it last was until `BL-B67` decides whether 673 joins
    `polled.toml` or is read at need.

    **`align_observed`/`ready_observed` (`[[BL-B80]]` v2) are the real
    898 (Л5 gyro alignment)/960 (guidance-unit READY) lamp readbacks**,
    both `REQUIRED_POLLED_ARGS` members -- `belief.sight_head.SightHead.
    mode` reads `align_observed` directly (its `caged` -> `free`
    transition); `sight_ready()` below reads `ready_observed`. `None`
    whenever no lamp sample has arrived yet -- absence is never read as
    `False`, same posture every other `*_observed` field in this class
    already takes. **`launch_perm_observed` (962) has no reader as of
    Stage 4**, same posture as `weapon_safety_observed` above -- carried
    for `BL-B67`, which decides whether it joins `polled.toml`."""

    guidance_unit_ready_prev_observed: bool | None = None
    observ_observed: bool | None = None
    weapon_safety_observed: bool | None = None
    align_observed: bool | None = None
    ready_observed: bool | None = None
    launch_perm_observed: bool | None = None


def sight_ready(state: GuidanceUnitState) -> bool:
    """The readiness predicate -- `[[BL-B80]]` v2 replaces v1's zero-
    real-warm-up `state.sight_ready` latch with the real 960 (guidance-
    unit READY) lamp: `True` exactly when `ready_observed is True` (an
    absent or `False` reading is not ready)."""
    return state.ready_observed is True


def write_sight_target(
    aircraft_client: AircraftLayerClient,
    goal_azimuth_deg: float,
    goal_elevation_deg: float,
    rate_azimuth_deg_s: float,
    rate_elevation_deg_s: float,
    t_sim: float,
) -> None:
    """Sends the simulated sight head's current **world** goal direction,
    rate, and the sim time it was computed at, to `Export.lua`'s per-
    frame servo (`[[BL-B80]]` v2, `plans/9k113-sight-pointing/plan.md`'s
    "Wire (sight_target)" section). **No raw command-unit conversion
    here** -- v1's degree<->raw conversions are removed; the wire itself
    now carries degrees, and `Export.lua`'s own servo converts internally.
    Called once per poll by `logger.py` while the sight head is `free`,
    **not** rate-limited here -- Export.lua's setpoint tracks the head via
    the same rate-limit function, from the same start, so it needs no
    resync (the plan's "Why goal, not head position, on the wire").
    Raises `AircraftLayerError` on a dropped write, same posture as
    every other write in this codebase."""
    aircraft_client.write_sight_target(
        goal_azimuth_deg,
        goal_elevation_deg,
        rate_azimuth_deg_s,
        rate_elevation_deg_s,
        t_sim,
    )


def _threshold_or_none(raw: float | None) -> bool | None:
    """`raw >= 0.5`, or `None` when `raw` is absent or non-finite --
    `>= 0.5` is the same threshold `Export.lua` used to apply itself
    before Stage 4 moved it here (plan S4.4: "the rule and the threshold
    are unchanged; only where they run moves"). A non-finite `raw` (NaN)
    is treated the same as absent, never as a value -- `AircraftLayerClient.
    read_args`/`get_watched_args_latest` already reject a NaN before it
    reaches here, but this function does not assume that upstream guard
    is the only caller."""
    if raw is None or not math.isfinite(raw):
        return None
    return raw >= 0.5


def refresh_readback(
    state: GuidanceUnitState,
    readback_args: Mapping[str, float] | None,
) -> GuidanceUnitState:
    """Refreshes `observ_observed`/`align_observed`/`ready_observed` from
    the continuous watched-args feed's own `"886"`/`"898"`/`"960"` (plan
    S4.4 -- `REQUIRED_POLLED_ARGS`'s own three args). `weapon_safety_
    observed`/`launch_perm_observed` (673/962) are **not** touched here
    any more -- Stage 4 removed their old per-frame reader with nothing
    replacing it yet (see `GuidanceUnitState`'s own docstring); they stay
    whatever they last were.

    `readback_args` is the `"args"` map `GET /watched_args/latest`
    carries (same shape Stage 2's `cockpit_switch` feed used, preserved
    so `logger.py`'s poll block changes only *which* client call feeds
    this function, not this function's own signature). `None` (no sample
    yet, or the latest sample's `watch_id` does not match what body-layer
    currently wants installed -- `logger.py`'s own check, not this
    function's) leaves every field unchanged, same posture every field
    in this class already takes."""
    if readback_args is None:
        return state
    observe = _threshold_or_none(readback_args.get("886"))
    align = _threshold_or_none(readback_args.get("898"))
    ready = _threshold_or_none(readback_args.get("960"))
    return replace(
        state,
        observ_observed=observe if observe is not None else state.observ_observed,
        align_observed=align if align is not None else state.align_observed,
        ready_observed=ready if ready is not None else state.ready_observed,
    )
