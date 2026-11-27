"""BL-16 mode 1 -- Petrovich flies on the raw cyclic/collective/pedal
axes while the controls are unparked (`plans/flight-control/plan.md`,
"Revised 2026-11-18 -- mode 1 (unparked, raw axes) re-cut"), Stage M1
(the seam and handover; the control law itself is Stage M2 -- `Export.
lua`'s own `flight_control.lua` module docstring has the full account of
what M1 ships).

`FlightControlState` carries the handover phase (`PILOT`/`TAKING`/
`ACTIVE`/`OVERLAY` -- Decision 24's "Petrovich has the controls is one
state across park and unpark", named for what the *player* experiences
rather than mirroring Lua's own `fc_mode` enum one-for-one: `OVERLAY`
covers both "mode 2 is flying while mode 1 stays armed" and "mode 1 was
never engaged at all and mode 2 just took a park", which Lua's own
`armed`/`off` split does not need to distinguish but body-layer's own
"who has the controls" question does) and read-only mirrors of `Export.
lua`'s own per-frame status. Single construction site, `advance_flight_
control_state` (`replace()` never constructs fresh) -- same shape
`belief.ai_pilot_wheel.ParkedFlightState`/`advance_parked_flight_state`
already use.

`take_controls`/`release_controls` are the two handover actions, as pure
functions (root `CLAUDE.md`, "Behaviour as actions and params").
**BL-16 Stage 3** (`plans/flight-desired-state/plan.md`, section 5):
they are now request *builders* with no `FlightControlState` parameter
at all -- there is no more `phase` to transition, and the voice-take's
own confirm/timeout handshake (what `decide_flight_control` used to own)
moves to `belief.flight_authority`'s ack-matching against `fd_acks`
(one numbered channel now carries both handover kinds).
`belief.crew_console.CrewConsole.take_controls`/`release_controls` are
the rule-callable wrappers that supply the live context (`has_controls`/
`on_ground`/IAS/attack-run) these functions need and queue the resulting
wire request (`CrewConsole.flight_control_transition`).

**Mode-1 goal actions (`increment_heading`/`set_heading`/... Decision
21's table) are NOT pure functions here** -- unlike mode 2's
`AiPilotWheelGoal`/rotation mechanism, mode 1's wire carries every goal
field in one message with no shared physical button to arbitrate over
(no rotation needed), so each `CrewConsole.axes_*` method builds its own
`FlightControlGoalRequest` directly and the one-shot field it sets is
applied by `body.py`'s `_apply_flight_control` exactly the way `ai_
pilot_goal_transition` already is. `clamp_altitude`/`clamp_speed` below
are the one piece of that shared logic worth a pure function (the floor/
ceiling clamps every altitude/speed action needs identically)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Final, Literal

import tuning
from aircraft_client import AircraftLayerClient

AltitudeRef = Literal["agl", "baro"]

#: At takeover, |bank| under this holds heading; at or above it, the
#: turn in progress continues (Decision 1 REVISED/24, user A2: "heading.
#: Let's say <5 deg bank gets level flight"). Sent to `Export.lua` in
#: every message's `limits` -- it is the one value the takeover-mode
#: snapshot needs, computed there rather than here (the live bank angle
#: at the instant of take is a Lua-side read, not a body-layer one).
TAKEOVER_LEVEL_BANK_DEG: Final[float] = tuning.real(
    "belief.flight_control.TAKEOVER_LEVEL_BANK_DEG",
    5.0,
    lo=0.0,
    hi=45.0,
    status="agreed-guess",
)

#: The terrain floor mode 1 holds once M3 builds the climb-for-terrain
#: logic (the user's own Q5 number, reused here -- mode 2 never declared
#: it, see the plan's "Behaviour constants" section: "P4 is unbuilt...
#: mode 1 declares its own constants with those defaults"). Not acted on
#: by `Export.lua` in Stage M1 (no shaper yet to hold a floor against);
#: sent in `limits` now so the wire channel does not need a reshape when
#: M3 lands.
FLOOR_AGL_M: Final[float] = tuning.real(
    "belief.flight_control.FLOOR_AGL_M",
    40.0,
    lo=0.0,
    hi=500.0,
    status="agreed-guess",
)

#: BL-16 lift-vector law, Stage LV-1 (`plans/flight-lift-vector/
#: plan.md`, U1/U8): `MIN_IAS_KMH` is removed entirely, not lowered --
#: the 80 km/h takeover refusal/self-release and every commanded-speed
#: floor are gone (the user's own informed choice, Q1 verbatim: "remove
#: the limit. Any speed. What does not work, I will bring back and we
#: fix"). What protects low speed now is `Export.lua`'s own gain
#: schedule (`flight_profile.lua`'s `schedule_gain_min`), not a wire
#: value this module ever sent.

#: The ceiling `set_speed`/`step_speed`/`set_speed_max` clamp to -- mode
#: 2's own Q5 ceiling (280 km/h), reused as a judgement call the same way
#: `belief.ai_pilot_wheel.AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M`'s docstring
#: already reuses a mode-2 figure elsewhere. Declared fresh here (not
#: imported from a mode-2 module) since that module never declared it
#: either (the plan's own "P4 is unbuilt... mode 1 declares its own
#: constants with those defaults" instruction).
MAX_IAS_KMH: Final[float] = tuning.real(
    "belief.flight_control.MAX_IAS_KMH",
    280.0,
    lo=100.0,
    hi=500.0,
    status="judgement",
)

#: M2's own bank for a commanded continuous turn ("turn left/right")
#: and for the heading channel's own rate-limit while converging to a
#: spoken heading -- `Export.lua`'s `law_turn_rate_at_bank(this, V_t)`
#: is the turn rate either channel's shaper rate-limits to. 20 deg is
#: the M0-A reference manoeuvre's own bank ("20° bank turns both
#: ways"), reused as a judgement call rather than measured for this
#: purpose specifically.
MAX_TURN_BANK_DEG: Final[float] = tuning.real(
    "belief.flight_control.MAX_TURN_BANK_DEG",
    20.0,
    lo=5.0,
    hi=45.0,
    status="judgement",
)

#: The altitude channel's own vertical-speed ceiling -- M0-A's
#: reference manoeuvre flew a "5 m/s climb and descent of 100 m",
#: reused here as the shaper's own rate limit rather than measured for
#: this purpose.
MAX_CLIMB_VS_MPS: Final[float] = tuning.real(
    "belief.flight_control.MAX_CLIMB_VS_MPS",
    5.0,
    lo=1.0,
    hi=15.0,
    status="judgement",
)

#: The speed channel's own along-track acceleration ceiling. Raised
#: 1.0 -> 2.0 by the LV-1 amendment (2026-11-24, fourth re-fly, Q2
#: "brisk"/E14): the user's own flown acceleration (150->250 km/h in
#: ~20 s) sustains 1.6-1.9 m/s^2, which the old 1.0 ceiling alone could
#: not reach (>=28 s plus the S-curve tails) regardless of how fast the
#: pitch/collective channels react -- `Export.lua`'s own `speed_accel_
#: cap_mps2` (`flight_profile.lua`) is raised alongside this one, to
#: the same ~1.9 figure, so this wire ceiling never clamps below it.
MAX_ACCEL_MPS2: Final[float] = tuning.real(
    "belief.flight_control.MAX_ACCEL_MPS2",
    2.0,
    lo=0.1,
    hi=5.0,
    status="agreed-guess",
)

#: A9's tolerance band for the speed channel: what "good enough" means
#: as a fraction of the commanded IAS, used by `Export.lua` only for
#: the status feed's `in_band_speed` and (M4) the settle test before a
#: Trimmer press -- never a deadband (Decision 18).
SPEED_BAND_FRAC: Final[float] = tuning.fraction(
    "belief.flight_control.SPEED_BAND_FRAC", 0.10, status="judgement"
)
#: A9's tolerance band for the altitude channel, as a fraction of the
#: commanded altitude -- see `ALT_BAND_MIN_M` for the floor that
#: applies alongside it at low altitude. Status-feed only, never a
#: deadband (Decision 18).
ALT_BAND_FRAC: Final[float] = tuning.fraction(
    "belief.flight_control.ALT_BAND_FRAC", 0.10, status="judgement"
)
#: The floor `ALT_BAND_FRAC` is clamped above, so a low-altitude hold
#: is not held to an unrealistically tight absolute band (the plan's
#: own example: "so 50 m AGL is not held to ±5 m" -- 10 m clears that
#: bar, 5 m would not).
ALT_BAND_MIN_M: Final[float] = tuning.real(
    "belief.flight_control.ALT_BAND_MIN_M",
    10.0,
    lo=1.0,
    hi=50.0,
    status="judgement",
)
#: A9's tolerance band for the turn-rate channel, as a fraction of the
#: commanded turn rate. Not yet read by any body-layer action (A9:
#: the bands feed only the status field and M4's settle test).
TURN_RATE_BAND_FRAC: Final[float] = tuning.fraction(
    "belief.flight_control.TURN_RATE_BAND_FRAC", 0.10, status="judgement"
)
#: No natural "10%" reading for a heading (D-c) -- 5° is the plan's own
#: recommended default.
HEADING_BAND_DEG: Final[float] = tuning.real(
    "belief.flight_control.HEADING_BAND_DEG",
    5.0,
    lo=1.0,
    hi=30.0,
    status="judgement",
)

#: U10's lease: Lua takes at an unpark only if body-layer has re-sent
#: `arm` within this many seconds (a safety margin; keep it at or below
#: 10 s, the ceiling `Export.lua` and the HTTP layer also enforce, or the
#: whole flight-control message is rejected at the wire). About three
#: missed ~1 Hz polls, closing the park-then-unpark escape route a
#: same-frame unpark take would otherwise remove from a dead Petrobrain
#: (Decision 2 stands for an *active* mode 1; this is what keeps the
#: *armed* escape open). `hi` is deliberately narrower than this constant's own old range
#: (security-m1-m2.md Finding B, change-request round): this value is
#: itself a safety margin, not an ordinary flight-behaviour knob, and
#: must stay at or below `Export.lua`'s own `FC_LIMIT_BOUNDS.arm_
#: lease_s` and the HTTP layer's `_FLIGHT_CONTROL_LIMITS_BOUNDS` (both
#: 10.0) -- a user override above either would be silently rejected
#: whole-message at the wire rather than applied.
ARM_LEASE_S: Final[float] = tuning.real(
    "belief.flight_control.ARM_LEASE_S",
    3.0,
    lo=0.5,
    hi=10.0,
    status="judgement",
)

#: "Slow down"/"speed up"'s own step size -- judgement call; mode 2's
#: wheel step is ~50 km/h, this is the one the plan's own "Behaviour
#: constants" table flags to revisit after Flight M-A.
SPEED_STEP_KMH: Final[float] = tuning.real(
    "belief.flight_control.SPEED_STEP_KMH",
    20.0,
    lo=1.0,
    hi=100.0,
    status="judgement",
)

#: How long a take request waits for `Export.lua`'s own ack (`fd_acks`)
#: before giving up, kept at least one poll plus `Export.lua`'s own push cadence
#: above `belief.flight_authority.FLIGHT_REQUEST_ACCEPT_WINDOW_S`, the
#: Lua-side half of the same deadline pair
#: (`test_handover_ack_timeout_exceeds_accept_window_with_margin` pins
#: the inequality). Judgement call -- this one bounds a network round
#: trip (voice command -> HTTP POST -> the next `GET /flight_desired/
#: latest` poll). Raised 2.0 to 3.0, BL-16 Stage 3 (`plans/
#: flight-desired-state/plan.md`, section 3a): it now bounds two
#: body-layer polls (the request is applied within one Lua frame, but
#: is only read back on body-layer's next ~1 Hz poll after that,
#: occasionally two) rather than one take.
HANDOVER_ACK_TIMEOUT_S: Final[float] = tuning.real(
    "belief.flight_control.HANDOVER_ACK_TIMEOUT_S",
    3.0,
    lo=0.5,
    hi=30.0,
    status="judgement",
)

#: Mode-1 batch (`plans/flight-control/plan.md`, "Revised 2026-11-19",
#: Decision 30) -- below this rotor RPM, `Export.lua`'s collective-rate
#: guard caps any further increase. The user's own number (Q-M1-1):
#: "Rotor RPM min allowed value to configurable param, set to 85%
#: initially."
ROTOR_RPM_FLOOR_PCT: Final[float] = tuning.real(
    "belief.flight_control.ROTOR_RPM_FLOOR_PCT",
    85.0,
    lo=50.0,
    hi=100.0,
    status="agreed-guess",
)

#: Decision 30 -- at or above this IAS, the same collective-rate guard
#: caps a further increase, to stay clear of retreating blade stall.
#: Originally the user's own agreed-guess number ("near or over
#: 250 km/h"); **corrected 2026-11-27** after the sixth re-fly ("Above
#: 230 km/h it forbids any collective increase" -> "no, that's well
#: within operating range", `docs/acceptance/2026-11-27-sortie-
#: feedback.md`). Re-based on the DCS Mi-24P V_NE table the user
#: supplied (`aircraft-layer/research/2026-11-27-mi24p-rotor-engine-
#: limits.md`): V_NE is altitude- and weight-dependent, but this field
#: is a single number sent once as part of `flight_control_limits()`,
#: with no altitude/weight channel of its own. Set flat to 335 km/h --
#: the normal-weight (<= 11 200 kg) V_NE up to 1 000 m barometric --
#: rather than plumbing altitude through this wire field: Petrovich's
#: operating band is 50-800 m AGL normal, 1-2 km rare
#: (`project_operating_altitude_envelope` memory), which the 335 figure
#: covers exactly at the low end and still only overstates by 15 km/h
#: at the top of the "rare" band (320 km/h at 1 000-2 000 m) -- a
#: smaller error than the guard's own 20 km/h margin already carries.
#: Weight is unknown to this module, so the normal-weight column is
#: used unconditionally (a heavier aircraft's true V_NE is lower; this
#: guard would not catch that case, same posture as every other
#: feedback-only guard in this Decision-30 batch).
RETREATING_BLADE_STALL_IAS_KMH: Final[float] = tuning.real(
    "belief.flight_control.RETREATING_BLADE_STALL_IAS_KMH",
    335.0,
    lo=100.0,
    hi=400.0,
    status="derived",
)

#: Decision 29 -- the break's own absolute height-loss budget above the
#: `FLOOR_AGL_M` floor it never descends below. The user's own number:
#: "moderate altitude drop allowed (~100 m, but never below 40 m AGL)".
BREAK_MAX_HEIGHT_LOSS_M: Final[float] = tuning.real(
    "belief.flight_control.BREAK_MAX_HEIGHT_LOSS_M",
    100.0,
    lo=20.0,
    hi=300.0,
    status="agreed-guess",
)

#: Decision 31 -- below this IAS, vortex ring state risk caps the
#: descent rate (every mode-1 state, not only a break). The user's own
#: number: "helicopters are prone to Vortex Ring State at slow speeds.
#: When speed is < 50 km/h, limit descent rate..."
VRS_IAS_THRESHOLD_KMH: Final[float] = tuning.real(
    "belief.flight_control.VRS_IAS_THRESHOLD_KMH",
    50.0,
    lo=20.0,
    hi=100.0,
    status="agreed-guess",
)

#: Decision 31's own descent-rate ceiling below `VRS_IAS_THRESHOLD_KMH`.
#: The user's own number, explicitly "configurable": "limit descent
#: rate to 4 m/s."
VRS_MAX_DESCENT_MPS: Final[float] = tuning.real(
    "belief.flight_control.VRS_MAX_DESCENT_MPS",
    4.0,
    lo=1.0,
    hi=10.0,
    status="agreed-guess",
)


@dataclass(frozen=True)
class FlightControlGoalRequest:
    """One `set`-kind wire request's worth of fields, built by a
    `CrewConsole.axes_*` action and carried by the one-shot `flight_
    control_goal_transition` field until `body.py`'s `_apply_flight_
    requests` sends it on the numbered `flight` channel (BL-16 Stage 3,
    `plans/flight-desired-state/plan.md`). Every field `None` means
    "omit it" on the wire (`Export.lua`'s own "a null field means keep
    yours").

    `turn_rate_deg_s` (mode-1 batch, Decision 27) is the signed rate
    override the break actions carry alongside `heading_deg` -- never
    meaningful alone, since a rate with no heading target is nothing to
    rate-limit. `None` means "use the ordinary `max_turn_bank_deg`-
    derived rate," the same "omit = keep the default" convention every
    other field here has."""

    heading_deg: float | None = None
    turn: Literal[-1, 0, 1] | None = None
    level_off: bool = False
    altitude_m: float | None = None
    altitude_ref: AltitudeRef | None = None
    ias_kmh: float | None = None
    turn_rate_deg_s: float | None = None


@dataclass(frozen=True)
class FlightControlState:
    """Petrovich's belief about mode 1's own diagnostics -- a read-only
    mirror of `Export.lua`'s per-frame `flight_control` status line.

    **BL-16 Stage 3** (`plans/flight-desired-state/plan.md`) removes
    `phase`/`take_seq`/`pending_take_says`/`took_at_sim`/`unpark_take`/
    `wire_seq`/`held_*`/`lua_take_seq`/`lua_last_cmd_seq` from this
    dataclass entirely: there is no more handover phase to track here
    (the mode authority is `belief.flight_authority.FlightAuthority
    State.fd_mode`, derived in Lua since Stage 2) and no more per-field
    `held_*` wire mirror (the commanded heading/altitude/speed is
    `FlightAuthorityState`'s own desired-state fields now). The voice-
    take confirm/timeout handshake these fields used to support moves to
    `belief.flight_authority`'s own ack-matching against `fd_acks`
    (`PendingTake`/`resolve_pending_take`), driven by the one numbered
    channel rather than polling `fc_take_seq`/`fc_last_cmd_seq` here.

    What remains is genuinely mode-1-specific and has no other home:
    measured telemetry (`measured_heading`/`measured_altitude`/
    `measured_speed`, the fallback "current" value `_axes_current_*`
    reads when `FlightAuthorityState` has nothing yet), the handover-
    diagnostics fields (`lua_mode`/`lua_take_origin`/`lua_release_
    reason`/`lua_refuse_cause`/`lua_takeover_mode`), the A9 bands
    (`in_band_*`, no consumer yet -- M4's own settle test), and the
    slip-ball calibration readout (sortie 2026-11-20, `aircraft-layer/
    research/2026-11-20-slip-ball-recon.md`, not yet read by any action
    or by `K_beta`, unmeasured sign/scale)."""

    measured_heading: float | None = None
    measured_altitude: float | None = None
    measured_speed: float | None = None
    lua_mode: str | None = None
    lua_take_origin: str | None = None
    lua_release_reason: str | None = None
    lua_refuse_cause: str | None = None
    lua_takeover_mode: str | None = None
    in_band_heading: bool | None = None
    in_band_altitude: bool | None = None
    in_band_speed: bool | None = None
    slip_ball_pilot_raw: float | None = None
    slip_ball_operator_raw: float | None = None
    slip_ball_lo_api: float | None = None
    #: BL-16 sortie 2026-11-20 (`docs/acceptance/
    #: 2026-11-20-sortie-feedback.md`) -- mirrors `Export.lua`'s own
    #: `fc_reset_epoch` echo, a diagnostic only since Stage 3 (the
    #: staleness floor it used to help reconcile is `flight_desired`'s
    #: own `fd_epoch`/`fd_last_seq` now).
    lua_reset_epoch: int | None = None


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


def advance_flight_control_state(
    state: FlightControlState, client: AircraftLayerClient
) -> FlightControlState:
    """Advances `state` from the aircraft layer's `GET /flight_control/
    latest` feed, once per poll -- same "replace wholesale, never
    mutate, a `None` sample leaves `state` unchanged" shape `belief.
    ai_pilot_wheel.advance_parked_flight_state` already uses. Every
    field on `state` is a `lua_*`/`measured_*`/`in_band_*`/slip-ball
    mirror now (Stage 3) -- nothing on this dataclass is body-layer's
    own authoritative state any more."""
    sample = client.get_flight_control_latest()
    if sample is None:
        return state
    return replace(
        state,
        measured_heading=_as_optional_float(sample.get("fc_measured_heading")),
        measured_altitude=_as_optional_float(sample.get("fc_measured_altitude")),
        measured_speed=_as_optional_float(sample.get("fc_measured_speed")),
        lua_mode=sample.get("fc_mode")
        if isinstance(sample.get("fc_mode"), str)
        else None,
        lua_take_origin=(
            sample.get("fc_take_origin")
            if isinstance(sample.get("fc_take_origin"), str)
            else None
        ),
        lua_release_reason=(
            sample.get("fc_release_reason")
            if isinstance(sample.get("fc_release_reason"), str)
            else None
        ),
        lua_refuse_cause=(
            sample.get("fc_refuse_cause")
            if isinstance(sample.get("fc_refuse_cause"), str)
            else None
        ),
        lua_takeover_mode=(
            sample.get("fc_takeover_mode")
            if isinstance(sample.get("fc_takeover_mode"), str)
            else None
        ),
        in_band_heading=_as_optional_bool(sample.get("fc_in_band_heading")),
        in_band_altitude=_as_optional_bool(sample.get("fc_in_band_altitude")),
        in_band_speed=_as_optional_bool(sample.get("fc_in_band_speed")),
        slip_ball_pilot_raw=_as_optional_float(sample.get("fc_slip_ball_pilot_raw")),
        slip_ball_operator_raw=_as_optional_float(
            sample.get("fc_slip_ball_operator_raw")
        ),
        slip_ball_lo_api=_as_optional_float(sample.get("fc_slip_ball_lo_api")),
        lua_reset_epoch=_as_optional_int(sample.get("fc_reset_epoch")),
    )


def take_controls(
    *,
    overlay_flying: bool,
    on_ground: bool,
    attack_run_engaged: bool,
) -> dict[str, object]:
    """Decision 22's `flight.take_controls` -- **BL-16 Stage 3**: a pure
    request builder with no state of its own (the voice-take confirm/
    timeout handshake moves to `belief.flight_authority.PendingTake`/
    `resolve_pending_take`, driven by the numbered channel's own
    `fd_acks` rather than a local `phase`). `overlay_flying` wins first
    (the 2026-11-17 no-op: "'you have controls' is no-op, say nothing" --
    not an error, `acted=False` only). The two refusals that follow
    match in the order the plan lists them; neither is more
    authoritative than the other, this order is simply deterministic.

    **BL-16 lift-vector law, Stage LV-1 (U1/U8)**: `TOO_SLOW` is gone --
    a take is accepted at any airspeed now, so this function no longer
    takes a `too_slow` parameter at all.

    On success: `{"ok": True, "acted": True}` -- the caller
    (`CrewConsole.take_controls`) queues the wire `take` request and
    holds the confirmation text until it is acked."""
    if overlay_flying:
        return {"ok": True, "acted": False}
    if on_ground:
        return {"ok": False, "reason": "ON_GROUND"}
    if attack_run_engaged:
        return {"ok": False, "reason": "ATTACK_RUN_ENGAGED"}
    return {"ok": True, "acted": True}


def release_controls(*, overlay_flying: bool, flying_axes: bool) -> dict[str, object]:
    """Decision 22's `flight.release_controls` -- **BL-16 Stage 3**: a
    pure request builder, `flying_axes` replacing the old `state.phase
    in ("TAKING", "ACTIVE") or state.lua_mode in ("active", "taking")`
    check (the caller passes `flight_authority_state.fd_mode in
    ("taking", "m1")`, the one mode authority). `overlay_flying` (U9,
    answered 2026-11-18: *"respond 'unable' when in AI overlay mode.
    Don't remember, Player will handle."*) raises unable `AI_OVERLAY` --
    nothing here is remembered; the next unpark still takes per Decision
    24 regardless of this call. `acted=False` (silent, the player
    already has the controls) only when `flying_axes` is already
    `False`."""
    if overlay_flying:
        return {"ok": False, "reason": "AI_OVERLAY"}
    if flying_axes:
        return {"ok": True, "acted": True}
    return {"ok": True, "acted": False}


def clamp_altitude(m: float, ref: AltitudeRef) -> float:
    """Decision 21's "Clamped at the floor" -- only meaningful for the
    AGL reference (a barometric floor cannot be derived without knowing
    terrain height, which Stage M1 has no shaper to track; see `Export.
    lua`'s own module docstring on what Stage M3 adds). A barometric
    target passes through unclamped."""
    if ref == "agl" and m < FLOOR_AGL_M:
        return FLOOR_AGL_M
    return m


def clamp_speed(kmh: float) -> float:
    """Decision 21's `set_speed`/`step_speed` clamp. **BL-16 lift-vector
    law, Stage LV-1 (U8, no floor)**: the lower bound (`MIN_IAS_KMH`) is
    gone entirely -- `[0, MAX_IAS_KMH]` now, never a floor above the
    commanded value."""
    return max(0.0, min(MAX_IAS_KMH, kmh))


def flight_control_limits(on_ground_agl_threshold_m: float) -> dict[str, float]:
    """The `limits` bundle sent in every `flight_control` wire message
    (the plan's own "Wire" section) -- `on_ground_agl_threshold_m` is
    `belief.crew_console.ON_GROUND_AGL_THRESHOLD_M`, reused rather than
    re-declared (plan: "reused, through `crew_console.on_ground`, for
    the refusal"); passed in by the caller (`body.py`) rather than
    imported here, since `belief.crew_console` imports *this* module for
    `FlightControlState` and the reverse import would cycle. **No
    `max_bank_deg` field any more** (F-M1, mode-1 batch: "remove the 30
    degree limit. Set no limit for now") -- removed from the wire
    entirely, not widened, so a stale consumer never finds a number
    that no longer means anything. **No `min_ias_kmh` field any more
    either** (BL-16 lift-vector law, Stage LV-1, U1/U8) -- same
    reasoning, removed rather than widened."""
    return {
        "takeover_level_bank_deg": TAKEOVER_LEVEL_BANK_DEG,
        "floor_agl_m": FLOOR_AGL_M,
        "max_ias_kmh": MAX_IAS_KMH,
        "on_ground_agl_threshold_m": on_ground_agl_threshold_m,
        "arm_lease_s": ARM_LEASE_S,
        # M2 additions -- the shaper's own rate limits and A9's bands,
        # read by `Export.lua`'s control law, never acted on here.
        "max_turn_bank_deg": MAX_TURN_BANK_DEG,
        "max_climb_vs_mps": MAX_CLIMB_VS_MPS,
        "max_accel_mps2": MAX_ACCEL_MPS2,
        "speed_band_frac": SPEED_BAND_FRAC,
        "alt_band_frac": ALT_BAND_FRAC,
        "alt_band_min_m": ALT_BAND_MIN_M,
        "turn_rate_band_frac": TURN_RATE_BAND_FRAC,
        "heading_band_deg": HEADING_BAND_DEG,
        # Mode-1 batch additions (Decisions 29-31) -- the rotor-RPM
        # floor, the retreating-blade-stall IAS, the break's own
        # height-loss budget, and the VRS descent-rate cap, all read by
        # `Export.lua`'s law, never acted on here.
        "rotor_rpm_floor_pct": ROTOR_RPM_FLOOR_PCT,
        "retreating_blade_stall_ias_kmh": RETREATING_BLADE_STALL_IAS_KMH,
        "break_max_height_loss_m": BREAK_MAX_HEIGHT_LOSS_M,
        "vrs_ias_threshold_kmh": VRS_IAS_THRESHOLD_KMH,
        "vrs_max_descent_mps": VRS_MAX_DESCENT_MPS,
    }


def goal_request_fields(request: FlightControlGoalRequest) -> dict[str, Any]:
    """The `goal` object's own fields for the wire -- `level_off=False`
    (the dataclass default, "nothing to say about it") omits the field
    entirely rather than sending a meaningless `false` (`Export.lua`
    only ever checks `level_off == true`)."""
    fields: dict[str, Any] = {}
    if request.heading_deg is not None:
        fields["heading_deg"] = request.heading_deg
    if request.turn is not None:
        fields["turn"] = request.turn
    if request.level_off:
        fields["level_off"] = True
    if request.altitude_m is not None:
        fields["alt_m"] = request.altitude_m
    if request.altitude_ref is not None:
        fields["alt_ref"] = request.altitude_ref
    if request.ias_kmh is not None:
        fields["ias_kmh"] = request.ias_kmh
    if request.turn_rate_deg_s is not None:
        fields["turn_rate_deg_s"] = request.turn_rate_deg_s
    return fields
