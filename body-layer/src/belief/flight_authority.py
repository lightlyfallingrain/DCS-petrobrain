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
from typing import Final

import tuning
from aircraft_client import AircraftLayerClient
from belief.flight_control import HANDOVER_ACK_TIMEOUT_S, clamp_altitude, clamp_speed
from belief.speech import render_unable

#: How old a `flight` request may be when `Export.lua` applies it (BL-16
#: Stage 3, `plans/flight-desired-state/plan.md`, section 3a) -- must
#: stay at least one body-layer poll plus `Export.lua`'s own push cadence below
#: `belief.flight_control.HANDOVER_ACK_TIMEOUT_S`, which bounds the
#: whole round trip this deadline is the Lua-side half of
#: (`test_handover_ack_timeout_exceeds_accept_window_with_margin` pins
#: `HANDOVER_ACK_TIMEOUT_S >= FLIGHT_REQUEST_ACCEPT_WINDOW_S + 1.0 +
#: 0.2`). A request is carried as `until = send time + this window`;
#: `Export.lua` refuses it stale once its own model-time clock passes
#: that deadline.
FLIGHT_REQUEST_ACCEPT_WINDOW_S: Final[float] = tuning.real(
    "belief.flight_authority.FLIGHT_REQUEST_ACCEPT_WINDOW_S",
    1.5,
    lo=0.5,
    hi=10.0,
    status="judgement",
)

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


def _as_optional_degrees_0_360(value: object) -> float | None:
    """Same parse as `_as_optional_float`, wrapped into `[0, 360)` --
    `fd_hdg_true_deg`/`fd_hdg_mag_deg` are degree fields (`Export.lua`'s
    `flight_desired.lua` module docstring: `LoGetMagneticYaw` itself
    returns radians, converted and wrapped on that side), and this
    mirror wraps again defensively at the one boundary body-layer
    actually reads the wire at -- so a value arriving at exactly 360 or
    a hair negative (float rounding across the `math.deg`/`%` pair on
    the Lua side) still reads as this project's own canonical compass
    range, the same posture every other wrap in this subsystem takes at
    its own boundary rather than trusting the sender's own rounding."""
    degrees = _as_optional_float(value)
    if degrees is None:
        return None
    wrapped = degrees % 360.0
    return wrapped


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
    #: BL-16 Stage 3 -- the acceptance epoch/floor/ack-ring for the
    #: numbered `flight` channel (section 5). `acks` is `Export.lua`'s
    #: own semicolon-joined ring string ("N:a:m1;N+1:r:wrong_mode;..."),
    #: parsed by `parse_acks` below rather than here (a pure mirror
    #: refresh never interprets the payload it carries).
    epoch: int | None = None
    last_seq: int | None = None
    acks: str | None = None


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
        hdg_true_deg=_as_optional_degrees_0_360(sample.get("fd_hdg_true_deg")),
        hdg_mag_deg=_as_optional_degrees_0_360(sample.get("fd_hdg_mag_deg")),
        measured_agl_m=_as_optional_float(sample.get("fd_measured_agl")),
        measured_msl_m=_as_optional_float(sample.get("fd_measured_msl")),
        measured_ias_kmh=_as_optional_float(sample.get("fd_measured_ias")),
        overlay_course_deg=_as_optional_float(sample.get("fd_overlay_course")),
        reset_epoch=_as_optional_int(sample.get("fd_reset_epoch")),
        epoch=_as_optional_int(sample.get("fd_epoch")),
        last_seq=_as_optional_int(sample.get("fd_last_seq")),
        acks=_as_optional_str(sample.get("fd_acks")),
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


def _digit_readback(value: int) -> str:
    """Spells a non-negative integer digit by digit, space-separated --
    `CrewConsole._digit_readback`'s own algorithm, copied rather than
    imported: `crew_console.py` imports this module (`PendingTake`/
    `resolve_pending_take` etc.), so the reverse import would be
    circular. One line; keep the two in sync by hand if the convention
    ever changes."""
    return " ".join(str(int(value)))


def decide_carried_value_speech(
    prev: FlightAuthorityState, new: FlightAuthorityState
) -> list[FlightAuthorityDecision]:
    """U2 (`plans/flight-desired-state/plan.md`, section 3, answered
    yes): "a carried value the new mode cannot fly exactly is announced
    once, not urgent" -- the m2->m1 half (first needed in Stage 3; the
    m1->m2 half, `m2_flown`, is Stage 4). Fires on the same `fd_mode_n`
    edge `decide_flight_speech` watches (same "no edge to observe"
    guard), only when the edge lands in `m1` with cause `unpark` --
    every other edge carries nothing new to announce.

    Compares each of ias/altitude against mode 1's own clamp
    (`belief.flight_control.clamp_speed`/`clamp_altitude`, the body-side
    twins of the `fc_limits.min_ias_kmh`/`max_ias_kmh`/`floor_agl_m`
    values `Export.lua`'s `build_take_seed` now clamps the unpark seed
    to) and returns one non-urgent decision per part that differs.
    `new.ias_kmh`/`alt_m` -- the exact commanded value `fd_ias`/`fd_alt`
    carries -- is never written here; only what mode 1 will actually
    fly is clamped, in this comparison and in `build_take_seed`. Spoken
    after the mode-change check above (section 3a's own speech order:
    mode-change lines first, then U2's carried-value lines)."""
    if prev.mode_n is None or new.mode_n is None or prev.mode_n == new.mode_n:
        return []
    if new.fd_mode != "m1" or new.mode_cause != "unpark":
        return []
    out: list[FlightAuthorityDecision] = []
    if new.ias_kmh is not None:
        flown_ias = clamp_speed(new.ias_kmh)
        if flown_ias != new.ias_kmh:
            out.append(
                FlightAuthorityDecision(
                    says=f"Speed {_digit_readback(int(flown_ias))}.", urgent=False
                )
            )
    if new.alt_m is not None:
        flown_alt: float | None = None
        is_baro = False
        if new.alt_ref == "agl":
            flown_alt = clamp_altitude(new.alt_m, "agl")
        elif new.alt_ref == "baro":
            flown_alt = clamp_altitude(new.alt_m, "baro")
            is_baro = True
        if flown_alt is not None and flown_alt != new.alt_m:
            suffix = " barometric" if is_baro else ""
            out.append(
                FlightAuthorityDecision(
                    says=f"{int(flown_alt)} meters{suffix}.", urgent=False
                )
            )
    return out


def parse_acks(acks: str | None) -> list[tuple[int, str, str]]:
    """Parses `Export.lua`'s own ack-ring string ("N:a:m1;N+1:r:
    wrong_mode;...", section 5) into `(seq, status, detail)` triples.
    `status` is `"a"`/`"r"`; `detail` the mode letter or refusal reason.
    A malformed entry is skipped (never raises) -- the ring is a best-
    effort diagnostic feed, not a channel `match_acks`-style callers can
    afford to crash on."""
    if not acks:
        return []
    out: list[tuple[int, str, str]] = []
    for entry in acks.split(";"):
        parts = entry.split(":", 2)
        if len(parts) != 3:
            continue
        seq_text, status, detail = parts
        try:
            seq = int(seq_text)
        except ValueError:
            continue
        if status not in ("a", "r"):
            continue
        out.append((seq, status, detail))
    return out


@dataclass(frozen=True)
class PendingTake:
    """BL-16 Stage 3 -- a voice take's own deferred ack (section 3a),
    replacing `belief.flight_control.FlightControlState.took_at_sim`/
    `pending_take_says`/`take_seq`. `says` is the confirmation text
    (`"I have controls."`), held unspoken until `resolve_pending_take`
    finds this `seq` accepted in `fd_acks`."""

    seq: int
    says: str
    sent_at_sim: float


def resolve_pending_take(
    pending: PendingTake | None, acks: str | None, now_sim: float
) -> tuple[PendingTake | None, FlightAuthorityDecision | None]:
    """The voice-take confirm/timeout handshake (`plans/
    flight-desired-state/plan.md`, section 3a), replacing `belief.
    flight_control.decide_flight_control`'s own `TAKING` branch --
    driven by `fd_acks` rather than polling `fc_take_seq`/`fc_mode`.

    - **Accepted** (`"N:a:m1"` for this `seq`): speaks `pending.says`
      urgently (Decision 13's handover contract), clears `pending`.
    - **Refused** (`"N:r:<reason>"` for this `seq`): speaks "Unable,
      not ready.", clears `pending` -- the refusal reason is not spoken
      verbatim (U1/3a names no new wording for this path; every refusal
      reason here reduces to "not ready" from the player's seat).
    - **Timeout** (`now_sim - sent_at_sim >= HANDOVER_ACK_TIMEOUT_S`,
      no ack either way yet): same "Unable, not ready." line, cleared.
    - **Still waiting**: `pending` unchanged, no decision."""
    if pending is None:
        return None, None
    for seq, status, _detail in parse_acks(acks):
        if seq != pending.seq:
            continue
        if status == "a":
            return None, FlightAuthorityDecision(says=pending.says, urgent=True)
        return None, FlightAuthorityDecision(says="Unable, not ready.", urgent=False)
    if now_sim - pending.sent_at_sim >= HANDOVER_ACK_TIMEOUT_S:
        return None, FlightAuthorityDecision(says="Unable, not ready.", urgent=False)
    return pending, None


@dataclass(frozen=True)
class PendingFlightReadback:
    """BL-16 Stage 3b (`plans/flight-desired-state/plan.md`, section 3a)
    -- one flight-category command's own readback, held unspoken from
    the moment its numbered `set` request is sent until `fd_acks`
    resolves that `seq`. `lines` is already the fully-rendered readback
    text, computed by the rule at dispatch time (mode-aware, via
    `CrewConsole.flight_mode()`/`rules.actions._by_mode`) -- 3a's ack
    mode letter is read only to decide *whether* to speak the text,
    never to re-render it, since U1's own "the readback is the
    request's own absolute value in m1, or `m2_flown` of it in m2" is
    already true of `lines` by construction (the action computed it in
    whichever mode was live at send time, which agrees with the ack's
    mode barring the rare mode-change-mid-flight race the suppression
    rules below exist for)."""

    seq: int
    lines: tuple[str, ...]
    sent_at_sim: float


#: 3a's own refusal-wording map: "Each Lua reason maps onto an existing
#: `render_unable` token ... No new spoken wording." `wrong_mode` is the
#: one reason that is not simply `NOT_READY` (U9's "AI overlay" wording,
#: `belief.speech._UNABLE_TEMPLATES["AI_OVERLAY"]`); every other closed
#: reason `Export.lua`'s `flight` channel can answer with (section 5's
#: own closed set, plus `bounds`) reduces to `NOT_READY` from the
#: player's seat, the same posture `resolve_pending_take` already takes
#: for the handover's own refusal. A reason not in this table (there is
#: none today; defensive against a future Lua reason this map has not
#: been extended for) falls back to `NOT_READY` too, per 3a's own "uses
#: NOT_READY and flags it, rather than writing a new line."
_FLIGHT_REFUSAL_UNABLE_TOKENS: dict[str, str] = {
    "wrong_mode": "AI_OVERLAY",
}


def resolve_pending_flight_readbacks(
    pending: list[PendingFlightReadback],
    acks: str | None,
    now_sim: float,
    *,
    suppress_accepted: bool = False,
) -> tuple[list[PendingFlightReadback], list[FlightAuthorityDecision]]:
    """3a's own ack-driven readback resolver, generalised from `resolve_
    pending_take` to every ordinary flight-channel command -- U1's own
    decision: *"Readback on acting on command -> wait for lua."*

    **Strict FIFO by `seq`, never arrival order** (3a: "ack outcomes in
    seq order, never arrival order"): only the *front* of `pending` is
    ever checked against `acks`; an unresolved front entry blocks every
    later one this poll, even if a later one's own ack already arrived
    (a UDP re-order, or two sends landing inside one poll's push
    window) -- the only way to guarantee seq order against a ring that
    can resolve out of order.

    Each resolved front entry yields decisions, never urgent (3a names
    no urgent flight-channel readback -- the handover's own "You have
    controls!"/"I have controls." stays `resolve_pending_take`'s own
    urgent path):

    - **accepted** (`"N:a:<mode>"`) -- every one of `lines`, verbatim,
      in order.
    - **refused** (`"N:r:<reason>"`) -- one `unable(reason)` line via
      `_FLIGHT_REFUSAL_UNABLE_TOKENS`.
    - **no ack within `belief.flight_control.HANDOVER_ACK_TIMEOUT_S`**
      of `sent_at_sim` -- one "Unable, not ready." line (3a: "a timeout
      is always the truth" -- `Export.lua` refuses anything past its
      own `until` deadline, so this can never contradict a late Lua
      accept; 3a's own "clock anomaly" case, a late-accepted ack for an
      already-timed-out `seq`, is left unhandled here exactly as
      `plans/flight-desired-state/implementation.md`'s Stage 3
      deviation (3) already flags for the handover's own equivalent).

    `suppress_accepted=True` (3a's own mode-off-edge suppression,
    `CrewConsole.drain_flight_control`'s own caller) still resolves
    (and removes) an accepted entry -- its `seq` is consumed from the
    ring exactly as if it had spoken -- it just yields no decision for
    it, since the value it would have named was already cleared with
    the mode. A refusal or timeout is never suppressed either way (3a
    names only the accepted case)."""
    acks_by_seq = {seq: (status, detail) for seq, status, detail in parse_acks(acks)}
    remaining = list(pending)
    decisions: list[FlightAuthorityDecision] = []
    while remaining:
        head = remaining[0]
        found = acks_by_seq.get(head.seq)
        if found is not None:
            remaining.pop(0)
            status, detail = found
            if status == "a":
                if not suppress_accepted:
                    decisions.extend(
                        FlightAuthorityDecision(says=line, urgent=False)
                        for line in head.lines
                    )
            else:
                reason = _FLIGHT_REFUSAL_UNABLE_TOKENS.get(detail, "NOT_READY")
                decisions.append(
                    FlightAuthorityDecision(
                        says=render_unable(reason).text, urgent=False
                    )
                )
            continue
        if now_sim - head.sent_at_sim >= HANDOVER_ACK_TIMEOUT_S:
            remaining.pop(0)
            decisions.append(
                FlightAuthorityDecision(says="Unable, not ready.", urgent=False)
            )
            continue
        break
    return remaining, decisions
