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
functions over `FlightControlState` (root `CLAUDE.md`, "Behaviour as
actions and params" -- plan's own instruction: "it also holds the
actions as pure functions and `decide_flight_control`, which is the one
'when'"). `belief.crew_console.CrewConsole.take_controls`/`release_
controls` are the rule-callable wrappers that supply the live context
(`has_controls`/`on_ground`/IAS/attack-run) these functions need and
apply the result to `self.flight_control_state`.

`decide_flight_control` is the one "when" apart from those two actions:
park/unpark edges, the ack timeout, Lua's own self-release, and a
refused unpark take -- everything that happens because of what *Export.
lua or the clock* did this poll, never because of what the player said
this dispatch (that is `take_controls`/`release_controls`'s own job).

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

FlightControlPhase = Literal["PILOT", "TAKING", "ACTIVE", "OVERLAY"]
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

#: Below this IAS, mode 1 refuses a takeover (`TOO_SLOW`) and `Export.
#: lua`'s own envelope check self-releases an already-active session
#: (Decision 3, user: "~80"). Also the unpark-take precondition Lua
#: checks on its own, independently, from the same wire value.
MIN_IAS_KMH: Final[float] = tuning.real(
    "belief.flight_control.MIN_IAS_KMH",
    80.0,
    lo=20.0,
    hi=200.0,
    status="agreed-guess",
)

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

#: The envelope-release bank limit `Export.lua` checks every active
#: frame (plus its own hard-coded margin) -- judgement call, A9 favours
#: robustness over tight tracking.
MAX_BANK_DEG: Final[float] = tuning.real(
    "belief.flight_control.MAX_BANK_DEG",
    30.0,
    lo=10.0,
    hi=60.0,
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

#: The speed channel's own along-track acceleration ceiling -- no
#: probe ever measured a step-response accel figure for this (M0-E was
#: not flown), so this is a placeholder, owed by M0-E like every gain
#: `Export.lua`'s own "M2 control law constants" block names.
MAX_ACCEL_MPS2: Final[float] = tuning.real(
    "belief.flight_control.MAX_ACCEL_MPS2",
    1.0,
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
#: `arm` within this many seconds -- about three missed ~1 Hz polls,
#: closing the park-then-unpark escape route a same-frame unpark take
#: would otherwise remove from a dead Petrobrain (Decision 2 stands for
#: an *active* mode 1; this is what keeps the *armed* escape open).
ARM_LEASE_S: Final[float] = tuning.real(
    "belief.flight_control.ARM_LEASE_S",
    3.0,
    lo=0.5,
    hi=30.0,
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

#: How long `TAKING` waits for `Export.lua` to confirm `active` before
#: giving up and speaking "Unable, not ready." -- judgement call, same
#: shape as `RULE_GATE_HOLD_TIMEOUT_S`'s own role for mode 2's takeover-
#: settle window, just a separate constant: this one bounds a network
#: round trip (voice command -> HTTP POST -> the next `GET /flight_
#: control/latest` poll), not a belief-state settle.
HANDOVER_ACK_TIMEOUT_S: Final[float] = tuning.real(
    "belief.flight_control.HANDOVER_ACK_TIMEOUT_S",
    2.0,
    lo=0.5,
    hi=30.0,
    status="judgement",
)


@dataclass(frozen=True)
class FlightControlGoalRequest:
    """One goal-channel message's worth of fields, built by a `CrewConsole.
    axes_*` action and carried by the one-shot `flight_control_goal_
    transition` field until `body.py`'s `_apply_flight_control` sends it
    and bumps `FlightControlState.wire_seq`. Every field `None` means
    "omit it" on the wire (`Export.lua`'s own "a null field means keep
    yours")."""

    heading_deg: float | None = None
    turn: Literal[-1, 0, 1] | None = None
    level_off: bool = False
    altitude_m: float | None = None
    altitude_ref: AltitudeRef | None = None
    ias_kmh: float | None = None


@dataclass(frozen=True)
class FlightControlState:
    """Petrovich's belief about mode 1. `phase`/`take_seq`/`pending_
    take_says`/`unpark_take`/`wire_seq` are body-layer's own authoritative
    fields (never overwritten by `advance_flight_control_state`, which
    only refreshes the `lua_*`/`held_*`/`measured_*` mirrors below).
    `took_at_sim` is the sim time the current `TAKING` phase was entered,
    `None` otherwise -- `decide_flight_control`'s own ack-timeout clock.

    **`wire_seq` vs. `take_seq`**: `wire_seq` is the one strictly-
    increasing counter every message's own `"seq"` field carries
    (`Export.lua`'s `fc_last_cmd_seq` applies it across every `cmd` kind
    alike -- a `goal` message is dropped exactly as stale as a `take` if
    sent out of order against it), bumped by `_apply_flight_control` on
    every send regardless of kind. `take_seq` is the *semantic* id of
    the current (or most recent) takeover -- what Lua echoes back on
    `fc_take_seq` to say "this specific take is now active" -- and only
    ever changes on an actual take, voice or unpark. The two would
    collide (an intervening goal send bumping what a take confirmation
    is compared against) if conflated into one field.

    `held_heading`/`held_altitude`/`held_altitude_ref`/`held_speed`
    mirror `Export.lua`'s own `fc_goal_*` fields -- the goal mode 1 is
    holding on the wire, `None` until a goal has ever been commanded
    this activation (there is no AI pilot reporting its own value the
    way mode 2's overlay readback does). `measured_heading`/`measured_
    altitude`/`measured_speed` mirror `fc_measured_*` -- plain telemetry,
    always known once Lua is active, used as the fallback "current"
    value by the handful of actions that need one before any goal has
    been commanded (`CrewConsole.current_crew_state`'s own merge of the
    two is what the `"flight_control*"` gates actually see).

    `in_band_heading`/`in_band_altitude`/`in_band_speed` mirror `fc_in_
    band_*` (M2's own A9 computation, `None` before `fc_law` exists --
    off/taking/armed, or an M1-only `Export.lua` that never computes
    them at all). No action in this module reads them yet -- A9's own
    "what the bands are used for" names only the status field and M4's
    settle test, both still ahead -- but mirroring them here, where
    every other wire status field is already mirrored, costs nothing
    and saves M4 a second pass through this dataclass."""

    phase: FlightControlPhase = "PILOT"
    take_seq: int = 0
    pending_take_says: str | None = None
    took_at_sim: float | None = None
    unpark_take: bool = False
    wire_seq: int = 0
    held_heading: float | None = None
    held_altitude: float | None = None
    held_altitude_ref: AltitudeRef | None = None
    held_speed: float | None = None
    measured_heading: float | None = None
    measured_altitude: float | None = None
    measured_speed: float | None = None
    lua_mode: str | None = None
    lua_take_seq: int | None = None
    lua_take_origin: str | None = None
    lua_release_reason: str | None = None
    lua_refuse_cause: str | None = None
    lua_takeover_mode: str | None = None
    in_band_heading: bool | None = None
    in_band_altitude: bool | None = None
    in_band_speed: bool | None = None


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


def _as_optional_ref(value: object) -> AltitudeRef | None:
    if value == "agl":
        return "agl"
    if value == "baro":
        return "baro"
    return None


def advance_flight_control_state(
    state: FlightControlState, client: AircraftLayerClient
) -> FlightControlState:
    """Advances `state` from the aircraft layer's `GET /flight_control/
    latest` feed, once per poll -- same "replace wholesale, never
    mutate, a `None` sample leaves `state` unchanged" shape `belief.
    ai_pilot_wheel.advance_parked_flight_state` already uses. Only the
    `lua_*`/`held_*`/`measured_*`/`in_band_*` mirrors move; `phase`/`take_seq`/
    `pending_take_says`/`took_at_sim`/`unpark_take`/`wire_seq` are
    body-layer's own fields and are carried through unchanged -- this
    function never decides the handover phase, `decide_flight_control`
    does, from the mirrors this function just refreshed."""
    sample = client.get_flight_control_latest()
    if sample is None:
        return state
    return replace(
        state,
        held_heading=_as_optional_float(sample.get("fc_goal_heading")),
        held_altitude=_as_optional_float(sample.get("fc_goal_altitude")),
        held_altitude_ref=_as_optional_ref(sample.get("fc_goal_altitude_ref")),
        held_speed=_as_optional_float(sample.get("fc_goal_speed")),
        measured_heading=_as_optional_float(sample.get("fc_measured_heading")),
        measured_altitude=_as_optional_float(sample.get("fc_measured_altitude")),
        measured_speed=_as_optional_float(sample.get("fc_measured_speed")),
        lua_mode=sample.get("fc_mode")
        if isinstance(sample.get("fc_mode"), str)
        else None,
        lua_take_seq=_as_optional_int(sample.get("fc_take_seq")),
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
    )


def take_controls(
    state: FlightControlState,
    now_sim: float,
    *,
    overlay_flying: bool,
    on_ground: bool,
    too_slow: bool,
    attack_run_engaged: bool,
) -> tuple[FlightControlState, dict[str, object]]:
    """Decision 22's `flight.take_controls`. `overlay_flying` wins first
    (the 2026-11-17 no-op: "'you have controls' is no-op, say nothing" --
    not an error, `acted=False` only). The three refusals that follow
    match in the order the plan lists them; none is more authoritative
    than another, this order is simply deterministic.

    On success: `TAKING`, `take_seq` bumped, `took_at_sim` set (the ack-
    timeout clock `decide_flight_control` reads). The caller
    (`CrewConsole.take_controls`) is responsible for recording `says`
    and sending the wire `take` message -- this function only decides
    the belief-state transition."""
    if overlay_flying:
        return state, {"ok": True, "acted": False}
    if on_ground:
        return state, {"ok": False, "reason": "ON_GROUND"}
    if too_slow:
        return state, {"ok": False, "reason": "TOO_SLOW"}
    if attack_run_engaged:
        return state, {"ok": False, "reason": "ATTACK_RUN_ENGAGED"}
    new_state = replace(
        state,
        phase="TAKING",
        take_seq=state.take_seq + 1,
        took_at_sim=now_sim,
    )
    return new_state, {"ok": True, "acted": True}


def release_controls(
    state: FlightControlState, *, overlay_flying: bool
) -> tuple[FlightControlState, dict[str, object]]:
    """Decision 22's `flight.release_controls`. `overlay_flying` (U9,
    answered 2026-11-18: *"respond 'unable' when in AI overlay mode.
    Don't remember, Player will handle."*) raises unable `AI_OVERLAY` --
    nothing here is remembered; the next unpark still takes per Decision
    24 regardless of this call. Otherwise: `acted=True` only while
    actually holding the controls (`TAKING`/`ACTIVE`), `acted=False`
    (silent, the player already has them) from `PILOT`."""
    if overlay_flying:
        return state, {"ok": False, "reason": "AI_OVERLAY"}
    if state.phase in ("TAKING", "ACTIVE"):
        new_state = replace(
            state,
            phase="PILOT",
            pending_take_says=None,
            took_at_sim=None,
        )
        return new_state, {"ok": True, "acted": True}
    return state, {"ok": True, "acted": False}


@dataclass(frozen=True)
class FlightControlDecision:
    """What `decide_flight_control` found this poll, for `CrewConsole`'s
    own drain to speak -- `None` when nothing happened. `says` carries
    the exact text (the one-shot `pending_take_says` for a confirmed
    voice take, or the fixed urgent lines for the other three kinds);
    `urgent` is threaded straight to `_print`'s `bypass_gate`."""

    says: str
    urgent: bool


def decide_flight_control(
    state: FlightControlState, now_sim: float, *, parked_active: bool
) -> tuple[FlightControlState, FlightControlDecision | None]:
    """The one "when" apart from `take_controls`/`release_controls`
    (root `CLAUDE.md`, "Behaviour as actions and params") -- everything
    that happens because of what `Export.lua`, ED's AI, or the clock did
    this poll, read from the mirrors `advance_flight_control_state` just
    refreshed and `parked_active` (mode 2's own freshly-refreshed
    `ParkedFlightState.parked_active`, read here rather than imported,
    the same "two co-moving fields, one caller reads both" shape `body.
    py`'s existing call sites already use).

    Checked in this order, each one `return`s immediately so at most one
    fires per poll (the events are mutually exclusive by construction --
    a poll can only observe one of them):

    1. **Park edge while flying** (Decision 24, Co-moving rows 8/8b):
       `parked_active` just became true while `phase` was `TAKING`/
       `ACTIVE`/`PILOT`. `TAKING`/`ACTIVE` -> `Export.lua` already self-
       armed (its own park-edge branch); `PILOT` -> nothing to arm yet
       (he was not flying mode 1), so this is a no-op for `PILOT` -- only
       `TAKING`/`ACTIVE` move to `OVERLAY`. Silent either way.
    2. **Unpark while OVERLAY/armed, Lua confirms active from the unpark
       origin** (row 9): silent, `take_seq` adopts Lua's own.
    3. **Unpark while OVERLAY/armed, Lua refuses** (row 9a): urgent
       "You have controls!" -- a forced handover, not a player command.
    4. **Lua's own self-release while ACTIVE** (row 7): urgent "You have
       controls!".
    5. **Ack timeout while TAKING** (row 5): "Unable, not ready.",
       `pending_take_says` discarded unspoken.
    6. **Lua confirms active for a voice take while TAKING** (row 4):
       `pending_take_says` spoken once, then cleared.

    A no-op (`state` unchanged, `None`) covers every other poll."""
    if parked_active and state.phase in ("TAKING", "ACTIVE"):
        new_state = replace(
            state,
            phase="OVERLAY",
            unpark_take=True,
            pending_take_says=None,
            took_at_sim=None,
        )
        return new_state, None

    if state.phase == "OVERLAY" and not parked_active:
        if state.lua_mode == "active" and state.lua_take_origin == "unpark":
            new_state = replace(
                state,
                phase="ACTIVE",
                take_seq=(
                    state.lua_take_seq
                    if state.lua_take_seq is not None
                    else state.take_seq
                ),
                unpark_take=True,
            )
            return new_state, None
        if state.lua_mode == "off" and state.lua_release_reason == "refused":
            new_state = replace(state, phase="PILOT", unpark_take=False)
            return new_state, FlightControlDecision(
                says="You have controls!", urgent=True
            )
        # Still waiting for Lua to report the unpark's own outcome.
        return state, None

    if (
        state.phase == "ACTIVE"
        and state.lua_mode == "off"
        and state.lua_release_reason
        in (
            "envelope",
            "nan",
            "dead",
        )
    ):
        new_state = replace(state, phase="PILOT", pending_take_says=None)
        return new_state, FlightControlDecision(says="You have controls!", urgent=True)

    if state.phase == "TAKING":
        if state.lua_mode == "active" and state.lua_take_seq == state.take_seq:
            says = state.pending_take_says
            new_state = replace(
                state, phase="ACTIVE", pending_take_says=None, took_at_sim=None
            )
            if says is not None:
                return new_state, FlightControlDecision(says=says, urgent=True)
            return new_state, None
        if (
            state.took_at_sim is not None
            and now_sim - state.took_at_sim >= HANDOVER_ACK_TIMEOUT_S
        ):
            new_state = replace(
                state, phase="PILOT", pending_take_says=None, took_at_sim=None
            )
            return new_state, FlightControlDecision(
                says="Unable, not ready.", urgent=False
            )

    return state, None


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
    """Decision 21's `set_speed`/`step_speed` clamp -- `[MIN_IAS_KMH,
    MAX_IAS_KMH]`."""
    return max(MIN_IAS_KMH, min(MAX_IAS_KMH, kmh))


def flight_control_limits(on_ground_agl_threshold_m: float) -> dict[str, float]:
    """The `limits` bundle sent in every `flight_control` wire message
    (the plan's own "Wire" section) -- `on_ground_agl_threshold_m` is
    `belief.crew_console.ON_GROUND_AGL_THRESHOLD_M`, reused rather than
    re-declared (plan: "reused, through `crew_console.on_ground`, for
    the refusal"); passed in by the caller (`body.py`) rather than
    imported here, since `belief.crew_console` imports *this* module for
    `FlightControlState` and the reverse import would cycle."""
    return {
        "takeover_level_bank_deg": TAKEOVER_LEVEL_BANK_DEG,
        "floor_agl_m": FLOOR_AGL_M,
        "min_ias_kmh": MIN_IAS_KMH,
        "max_ias_kmh": MAX_IAS_KMH,
        "on_ground_agl_threshold_m": on_ground_agl_threshold_m,
        "arm_lease_s": ARM_LEASE_S,
        "max_bank_deg": MAX_BANK_DEG,
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
    return fields
