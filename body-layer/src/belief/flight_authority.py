"""BL-16 (`plans/flight-desired-state/plan.md`, Stages 1-2) -- the body-
layer mirror of `Export.lua`'s `flight_desired` module: one desired
flight state and one mode authority (`fd_mode`), derived in Lua, never
here. `FlightAuthorityState` (single construction site, `advance_flight_
authority`) is a pure read-only mirror of `GET /flight_desired/latest`,
same "replace wholesale, never mutate, a missing sample leaves state
unchanged" shape `belief.ai_pilot_wheel.advance_parked_flight_state`/
`belief.flight_control.advance_flight_control_state` already use.

**Stage 1**: logged on the flight-control status line, read by nothing
else. **Stage 2**: `CrewConsole.flight_mode()`/`current_crew_state()`'s
`has_controls`/`held_*` read this mirror instead of `ParkedFlightState.
parked_active`/`FlightControlState.phase` (section 2 of the plan: "Lua
derives the mode every frame; nothing sets it directly" -- body-layer
never states the mode, it only reads what Lua already decided).
`decide_flight_speech` is the one place a forced loss of the stick
(`fd_mode` moving to `"off"` for a cause that is not the player's own
"I have controls"/a mission stop/a body-layer reset) becomes the urgent
"You have controls!" line -- everything else about a mode change stays
silent (U5/E8). It speaks only on a mode-authority edge (`fd_mode_n`
incrementing); request-level acks/refusals are Stage 3's own one
channel, not built here."""

from __future__ import annotations

from dataclasses import dataclass, replace

from aircraft_client import AircraftLayerClient

#: `fd_mode_cause` values that mean the player (or a system reset) let
#: go on purpose -- none of these get the urgent line, because nothing
#: was taken from him without warning (E8's own "losing the stick is
#: urgent; a mode change the player caused is silent").
_SILENT_OFF_CAUSES: frozenset[str] = frozenset({"release", "stop", "reset"})


def _as_optional_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    return value


def _as_optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_optional_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_optional_bool(value: object) -> bool | None:
    if not isinstance(value, bool):
        return None
    return value


@dataclass(frozen=True)
class FlightAuthorityState:
    """Petrovich's belief about the one desired flight state and the one
    mode authority, both derived in `Export.lua`'s `flight_desired`
    module -- every field here is a read-only mirror of `GET /
    flight_desired/latest` (`aircraft-layer/src/schema/
    flight_desired.py`'s `FlightDesiredState.to_api_dict`). Defaults are
    the "nothing received yet this process" state, same as every other
    `fd_mode == "off"`-shaped start."""

    fd_mode: str = "off"
    mode_cause: str | None = None
    mode_n: int | None = None
    has_m2: bool = False
    hdg_mode: str | None = None
    heading_deg: float | None = None
    hdg_ref: str | None = None
    turn_dir: int | None = None
    turn_rate_deg_s: float | None = None
    turn_style: str | None = None
    alt_m: float | None = None
    alt_ref: str | None = None
    ias_kmh: float | None = None
    manoeuvre: str | None = None
    manoeuvre_seq: int | None = None
    stamp_hdg: int | None = None
    stamp_alt: int | None = None
    stamp_spd: int | None = None
    hdg_true_deg: float | None = None
    hdg_mag_deg: float | None = None
    measured_agl_m: float | None = None
    measured_msl_m: float | None = None
    measured_ias_kmh: float | None = None
    overlay_course_deg: float | None = None
    reset_epoch: int | None = None


def advance_flight_authority(
    state: FlightAuthorityState, client: AircraftLayerClient
) -> FlightAuthorityState:
    """Advances `state` from `GET /flight_desired/latest`, once per
    poll. A missing sample (nothing received yet) leaves `state`
    unchanged -- same convention as `advance_flight_control_state`."""
    sample = client.get_flight_desired_latest()
    if sample is None:
        return state
    fd_mode_raw = sample.get("fd_mode")
    fd_mode = fd_mode_raw if isinstance(fd_mode_raw, str) else state.fd_mode
    return replace(
        state,
        fd_mode=fd_mode,
        mode_cause=_as_optional_str(sample.get("fd_mode_cause")),
        mode_n=_as_optional_int(sample.get("fd_mode_n")),
        has_m2=bool(sample.get("fd_has_m2")) if "fd_has_m2" in sample else state.has_m2,
        hdg_mode=_as_optional_str(sample.get("fd_hdg_mode")),
        heading_deg=_as_optional_float(sample.get("fd_heading")),
        hdg_ref=_as_optional_str(sample.get("fd_hdg_ref")),
        turn_dir=_as_optional_int(sample.get("fd_turn_dir")),
        turn_rate_deg_s=_as_optional_float(sample.get("fd_turn_rate")),
        turn_style=_as_optional_str(sample.get("fd_turn_style")),
        alt_m=_as_optional_float(sample.get("fd_alt")),
        alt_ref=_as_optional_str(sample.get("fd_alt_ref")),
        ias_kmh=_as_optional_float(sample.get("fd_ias")),
        manoeuvre=_as_optional_str(sample.get("fd_manoeuvre")),
        manoeuvre_seq=_as_optional_int(sample.get("fd_manoeuvre_seq")),
        stamp_hdg=_as_optional_int(sample.get("fd_stamp_hdg")),
        stamp_alt=_as_optional_int(sample.get("fd_stamp_alt")),
        stamp_spd=_as_optional_int(sample.get("fd_stamp_spd")),
        hdg_true_deg=_as_optional_float(sample.get("fd_hdg_true_deg")),
        hdg_mag_deg=_as_optional_float(sample.get("fd_hdg_mag_deg")),
        measured_agl_m=_as_optional_float(sample.get("fd_measured_agl")),
        measured_msl_m=_as_optional_float(sample.get("fd_measured_msl")),
        measured_ias_kmh=_as_optional_float(sample.get("fd_measured_ias")),
        overlay_course_deg=_as_optional_float(sample.get("fd_overlay_course")),
        reset_epoch=_as_optional_int(sample.get("fd_reset_epoch")),
    )


@dataclass(frozen=True)
class FlightAuthorityDecision:
    """What `decide_flight_speech` found this poll -- `None` when
    nothing happened. Always the urgent "You have controls!" line today
    (Stage 2 speaks only on a forced mode-authority edge); kept as its
    own type, not a bare string, so a later stage can add a non-urgent
    decision without reshaping every call site."""

    says: str
    urgent: bool


def decide_flight_speech(
    prev: FlightAuthorityState, new: FlightAuthorityState
) -> FlightAuthorityDecision | None:
    """The one "when" for the mode authority (root `CLAUDE.md`,
    "Behaviour as actions and params") -- speaks only on an `fd_mode_n`
    edge (section 2's own `fd_mode_n`, incremented once per change in
    `Export.lua`), never on every poll. `mode_n` absent on either side
    (nothing received yet, or the very first sample this process) is
    treated as "no edge to observe" -- there is nothing to compare
    against.

    Urgent "You have controls!" exactly when the new mode is `"off"`
    and `mode_cause` is not one of `_SILENT_OFF_CAUSES` (E8): an unpark
    Lua refused (`unpark_refused`/`unpark_unarmed`), or Lua's own
    envelope/NaN/dead self-release (`envelope`/`nan`/`dead`). Every
    other edge -- taking, a successful unpark into `m1`, any park into
    `m2` -- is silent (U5): the player set the mode himself, or Lua
    handed him the controls back on request, neither of which he needs
    told."""
    if prev.mode_n is None or new.mode_n is None or prev.mode_n == new.mode_n:
        return None
    if new.fd_mode == "off" and new.mode_cause not in _SILENT_OFF_CAUSES:
        return FlightAuthorityDecision(says="You have controls!", urgent=True)
    return None
