"""Firing-event wire format -- `plans/emitter-visibility/plan.md` Stage B
(`AC-B8`, the transport half of `[[BL-B73]]`/`[[BL-B74]]`).

`petrobrain-firing-events-hook.lua` registers `world.addEventHandler` in
the `"scripting"` mission state (the same bridge every other Hook script
in this module already uses), accumulates events in-state as they arrive,
and drains the accumulated batch once a second -- the same registration/
poll split the F10 command channel's Hook script (retired by `BL-B96`)
established, extended with an event *handler* rather than a player-driven
queue. The closed probe
(`docs/acceptance/2026-09-24-damage-and-firing-probes.md`, flown and
closed 2026-09-25) already confirmed `world.addEventHandler` is reachable
from that state and that a ground gun unit's `S_EVENT_SHOOTING_START`
names the player as its `target`.

Wire format (Hook -> collector), UDP, one JSON object per poll (matches
every other Hook-to-collector feed in this module):

    {"payload": "<count>|<dcs_model_time_s>|<entries>", "bridge_call_ms": <float>}

`entries` is `"<kind>:<t>:<initiator>:<targets_ownship01>:<x>:<z>;..."`,
semicolon-separated. `kind` is one of the fixed strings the Hook script's
own event-name reversal can produce and this module accepts (see
`ALLOWED_KINDS`) -- anything else is a malformed entry, not a silent drop
of one field.

**`x`/`z` are the seam for `[[BL-B74]]` (the SAM launch tail), not built
this stage.** They are populated (as plain floats) only for
`S_EVENT_SHOT` -- the initiator's own position *at event time*, read once
by the Hook script before the queue entry is built, never re-read later.
Every other kind carries the literal string `"nil"` in both fields, the
same tri-state convention `unit_velocity.py`'s `life`/`life0` already use
for "this poll could not read it" (here: "this kind carries no position").
`FiringRawEvent.x`/`z` are `None` in that case -- nothing in this stage's
collector logic (`collector.firing_receiver.EmitterTracker`) reads them
for anything but carrying them forward unused, per the plan's explicit
"build the seam, not the feature" scope.

`targets_ownship01` is a literal `0`/`1` -- `S_EVENT_SHOOTING_START`'s own
`target` field is only ever compared against `world.getPlayer()` once per
event, on the Hook-script side, and the wire carries only the resulting
boolean (never the raw target identity): the no-omniscience gate this
feature's own acceptance document names (*"this gives detection only"*)
has nothing to do with who is targeting whom beyond "is it us", so there
is no reason to cross more than that one bit.

**`mission_clock` (`BL-B124`, amendment 2026-11-25)** rides as its own
envelope key, never folded into `payload` -- mirrors `line_of_sight.py`'s
own `probes` key exactly, both in shape (a separate optional sub-wire
string, parsed by its own small dataclass) and in the reason (a second,
independently-evolving field should not force every consumer of the
first one to re-parse). Carries `"<abs_time_s>|<year>|<month>|<day>"`
(`timer.getAbsTime()` plus `env.mission.date`, both read inside the same
`net.dostring_in` call the firing-event drain already makes -- no new
DCS read, no new port) or the literal sentinel `"unavailable"` when the
Hook's own guarded read failed this poll; either collapses, on this side,
to `FiringEventBatch.mission_clock is None` -- see
`MissionClockSample.from_wire`'s own docstring for why "sentinel" and
"key absent entirely" are not distinguished.

**`own_events` (`[[BL-B67]]` Stage 5, `plans/bl-b67-atgm-run/plan.md`)**
is a **fourth** `|`-delimited segment on `payload` itself (not a separate
envelope key like `mission_clock` -- it is produced by the same
`S_EVENT_SHOT` handler the ordinary `entries` segment already drains,
not a second independently-evolving read), so the wire shape becomes
`"<count>|<dcs_model_time_s>|<entries>|<own_entries>"`. **A 3-segment
payload (no fourth `|`) parses with an empty `own_events` tuple** -- the
deployed Hook copy can lag the repo (plan's own "Risks & Unknowns"),
and this is the forward-compatible degrade, not an error.

`own_entries` is `"<OWN_SHOT|OWN_GONE entry>;..."`, semicolon-separated,
mirroring `entries`'s own separator. Two entry shapes:

    OWN_SHOT:<t>:<seq>:<type>:<category>:<guidance>:<exists01>
    OWN_GONE:<t>:<seq>

`seq` is the Hook's own `PB_OWN_WEAPON_SEQ` counter -- opaque, never a
DCS object id, and this module carries it no further than `OwnWeaponRawEvent.seq`
(`collector.firing_receiver.OwnWeaponLedger` is what turns a stream of
these into "which of our own missiles exist, in flight, or gone";
body-layer's `perception.own_weapons.OwnWeaponTracker` is the one place
that opaque number is ever compared against a previous poll's, and it
never crosses out of that module -- see its own docstring). `category`/
`guidance` are the shot weapon's `getDesc().category`/`.guidance` (`int`,
`None` if the Hook's own guarded read failed); `exists01` is `weapon
~= nil and weapon:isExist()` at `S_EVENT_SHOT` time, the launch's own
up-front existence check (round 7 decision 4's *"treat as not
launched"* case is exactly `exists01 == "0"`).

**`<type>` carries an independent length/charset bound on this side**
(security review carried-forward finding, `plans/bl-b67-atgm-run/
security-review.md`'s "Required Plan Changes" item 1): the Hook already
truncates to 48 characters and replaces `:;|` before it ever reaches the
wire (so a *well-behaved* Hook can never produce a field this bound
would reject), but this parser does not trust that truncation happened
-- an old or hand-edited deployed Hook copy is exactly the kind of thing
`FiringParseError` exists to catch rather than silently accept. A type
field longer than `MAX_OWN_WEAPON_TYPE_NAME_LEN` or containing one of the
wire's own delimiter characters (`:`, `;`, `|`) is rejected outright, the
same "malformed entry, not a silent drop of one field" posture the
module docstring states for `entries` above."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

#: The fixed set of event-kind strings this module accepts on the wire --
#: resolved Hook-side from DCS's own `world.event` enumerator (the same
#: "resolve the id to a name at runtime, never hardcode the number"
#: discipline `petrobrain-damage-events-probe-hook.lua` already
#: established), restated here as the collector-side allow-list so a
#: malformed or unexpected kind string is a parse error, not a silently
#: accepted fifth category. `S_EVENT_SHOT`/`S_EVENT_DEAD`/`S_EVENT_CRASH`
#: are accepted even though this stage's `EmitterTracker` does not yet act
#: on `S_EVENT_SHOT` (the `[[BL-B74]]` seam) -- the wire and the parser are
#: already general; only the state machine is deliberately narrow.
ALLOWED_KINDS: Final[tuple[str, ...]] = (
    "S_EVENT_SHOOTING_START",
    "S_EVENT_SHOOTING_END",
    "S_EVENT_SHOT",
    "S_EVENT_DEAD",
    "S_EVENT_CRASH",
)

#: The fixed set of own-weapon entry-kind strings this module accepts in
#: the `own_events` sub-wire (module docstring) -- `OWN_SHOT` (a new
#: `S_EVENT_SHOT` for us, read at event time) and `OWN_GONE` (the kept
#: weapon object's own `isExist()` turning `false`, read in the Hook's
#: 1 Hz drain). Not `ALLOWED_KINDS` above -- that set is DCS's own
#: `world.event` names; these two are this feature's own wire-local
#: labels, never confused with a real DCS event kind.
OWN_WEAPON_ALLOWED_KINDS: Final[tuple[str, ...]] = ("OWN_SHOT", "OWN_GONE")

#: Independent parser-side bound on the own-weapon `<type>` field
#: (module docstring's "`<type>` carries an independent length/charset
#: bound" paragraph) -- matches the Hook's own 48-character truncation
#: so a well-behaved Hook's longest legal value is never rejected, while
#: a malformed/hand-edited Hook copy still cannot smuggle an oversized
#: or delimiter-bearing string past this side.
MAX_OWN_WEAPON_TYPE_NAME_LEN: Final[int] = 48

#: The three wire-delimiter characters no free-text field on this feed's
#: own-weapon sub-wire may contain (module docstring) -- same reasoning
#: `_parse_entry` already applies to `initiator` below, restated as a
#: named set because `<type>` is checked independently of that function.
_OWN_WEAPON_TYPE_FORBIDDEN_CHARS: Final[frozenset[str]] = frozenset({":", ";", "|"})


class FiringParseError(ValueError):
    """Raised when a firing-event wire payload does not match the expected
    shape."""


@dataclass(frozen=True, slots=True)
class FiringRawEvent:
    """One raw DCS event, exactly as the Hook script observed it --
    pre-state-machine. `collector.firing_receiver.EmitterTracker` is what
    turns a stream of these into "which units are currently emitting";
    this type carries no derived state of its own."""

    kind: str
    t_sim: float
    initiator: str
    targets_ownship: bool
    x: float | None
    z: float | None


@dataclass(frozen=True, slots=True)
class OwnWeaponRawEvent:
    """One raw own-weapon entry (`[[BL-B67]]` Stage 5, module docstring) --
    `kind` is `"OWN_SHOT"`/`"OWN_GONE"` (`OWN_WEAPON_ALLOWED_KINDS`), `seq`
    is the Hook's own opaque per-shot counter. `type_name`/`category`/
    `guidance`/`exists_at_shot` are only ever populated for `"OWN_SHOT"`
    (`None` on `"OWN_GONE"`, which carries nothing but `seq`/`t_sim`) --
    `collector.firing_receiver.OwnWeaponLedger` is what turns a stream of
    these into "which of our own missiles exist, in flight, or gone"."""

    kind: str
    t_sim: float
    seq: int
    type_name: str | None = None
    category: int | None = None
    guidance: int | None = None
    exists_at_shot: bool | None = None


@dataclass(frozen=True, slots=True)
class MissionClockSample:
    """One poll's own mission wall-clock reading (`BL-B124`, amendment
    2026-11-25) -- `env.mission.date` (`Year`/`Month`/`Day`) plus
    `timer.getAbsTime()` (seconds since 00:00 of the mission's start day,
    still climbing past 86400 across midnight), both read inside the same
    `net.dostring_in("scripting", ...)` call the firing-event drain
    already makes. No new DCS read, no new port -- see this module's own
    docstring for the wire shape and `petrobrain-firing-events-hook.lua`'s
    `EVENT_POLL_CODE` for where these two reads happen.

    Body-layer derives sun elevation from `abs_time_s` + `year`/`month`/
    `day` + ownship lat/lon (`light_level.py`, Stage 2) -- that derivation
    lives entirely on the body-layer side; this type carries no astronomy
    of its own."""

    abs_time_s: float
    year: int
    month: int
    day: int

    @staticmethod
    def from_wire(raw: str) -> MissionClockSample | None:
        """Parse one `"<abs_time_s>|<year>|<month>|<day>"` sub-wire
        string. The literal sentinel `"unavailable"` (the Hook's own
        guarded-failure case, module docstring) parses to `None` --
        that is an *expected* state, not a malformed one, so it does not
        raise. Anything else that fails to parse raises
        `FiringParseError`; the caller (`FiringEventBatch.from_wire`)
        drops a malformed `mission_clock` sub-wire the same way
        `LineOfSightSnapshot.from_wire` drops a malformed `probes`
        sub-wire -- without failing the rest of the batch."""
        if raw == "unavailable":
            return None
        parts = raw.split("|")
        if len(parts) != 4:
            raise FiringParseError(
                "expected '<abs_time_s>|<year>|<month>|<day>' or "
                f"'unavailable', got {raw!r}"
            )
        abs_str, year_str, month_str, day_str = parts
        try:
            abs_time_s = float(abs_str)
            year = int(year_str)
            month = int(month_str)
            day = int(day_str)
        except ValueError as exc:
            raise FiringParseError(
                "expected '<abs_time_s>|<year>|<month>|<day>' or "
                f"'unavailable', got {raw!r}"
            ) from exc
        if not math.isfinite(abs_time_s):
            # `float()` parses "nan"/"inf"/"-inf" without raising, unlike
            # `int()` on `year`/`month`/`day` above -- `[[BL-B137]]`, found
            # by the `BL-B124` security deep analysis: an unguarded NaN/
            # Infinity here silently resolves, on the body-layer side, to
            # a concrete 90.0 deg sun elevation (full daylight), the one
            # outcome this feature's own design forbids (user Q6: "error
            # if not readable"). Rejected the same way as any other
            # malformed sub-wire -- the caller drops it to
            # `mission_clock=None`, never raises past this module.
            raise FiringParseError(f"abs_time_s must be finite, got {abs_str!r}")
        return MissionClockSample(
            abs_time_s=abs_time_s, year=year, month=month, day=day
        )

    def to_dict(self) -> dict[str, float | int]:
        return {
            "abs_time_s": self.abs_time_s,
            "year": self.year,
            "month": self.month,
            "day": self.day,
        }


@dataclass(frozen=True, slots=True)
class FiringEventBatch:
    """One poll's worth of drained firing events, plus that poll's own
    `dcs_model_time_s` -- mirrors `LineOfSightSnapshot`'s dual-clock shape,
    `received_wall_clock_s` stamped by the collector at receipt, not by the
    Hook script (same posture as every other feed in this module).

    `mission_clock` (`BL-B124`) defaults to `None` so every pre-amendment
    caller/fixture that builds a `FiringEventBatch` without it (this
    module's own tests, `collector.firing_receiver`'s test fixtures)
    keeps working unchanged."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    bridge_call_ms: float
    events: tuple[FiringRawEvent, ...]
    mission_clock: MissionClockSample | None = None
    #: `[[BL-B67]]` Stage 5 -- the fourth `|`-delimited segment (module
    #: docstring). Defaults to `()` so every pre-Stage-5 caller/fixture
    #: that builds a `FiringEventBatch` without it keeps working
    #: unchanged, same posture `mission_clock`'s own default took for
    #: `BL-B124`.
    own_events: tuple[OwnWeaponRawEvent, ...] = ()

    @staticmethod
    def from_wire(
        payload: str,
        *,
        bridge_call_ms: float,
        received_wall_clock_s: float,
        mission_clock_raw: str | None = None,
    ) -> FiringEventBatch:
        """Parse one compact wire string (module docstring) into a typed
        batch. `entries` may be empty (nothing fired this poll).
        `mission_clock_raw` is the envelope's own separate `"mission_
        clock"` key (`FiringEventsReceiver` passes it in) -- `None` or a
        malformed sub-wire is dropped to `mission_clock=None` without
        failing the rest of the batch, same posture
        `LineOfSightSnapshot.from_wire` already established for `probes`.

        **`payload` carries 3 segments (pre-`[[BL-B67]]` Stage 5) or 4**
        (module docstring's "a 3-segment payload... parses with an empty
        `own_events` tuple" paragraph) -- a malformed own-weapon entry
        inside a present fourth segment *does* fail the whole batch
        (unlike a malformed `mission_clock` sub-wire, which only drops
        that one field): the own-weapon entries are produced by this same
        feature's own Hook code, not a separately-evolving envelope key,
        so a malformed one indicates a real wire-format mismatch worth
        surfacing rather than silently swallowing."""
        parts = payload.split("|", 3)
        if len(parts) not in (3, 4):
            raise FiringParseError(
                f"expected '<count>|<t>|<entries>' or "
                f"'<count>|<t>|<entries>|<own_entries>', got {payload!r}"
            )
        count_str, t_str, entries_str = parts[0], parts[1], parts[2]
        own_entries_str = parts[3] if len(parts) == 4 else ""
        try:
            int(count_str)
        except ValueError as exc:
            raise FiringParseError(
                f"field 'count' must be an integer, got {count_str!r}"
            ) from exc
        try:
            dcs_model_time_s = float(t_str)
        except ValueError as exc:
            raise FiringParseError(
                f"field 'dcs_model_time_s' must be a number, got {t_str!r}"
            ) from exc

        events: list[FiringRawEvent] = []
        for entry in entries_str.split(";"):
            if not entry:
                continue
            events.append(_parse_entry(entry))

        own_events: list[OwnWeaponRawEvent] = []
        for own_entry in own_entries_str.split(";"):
            if not own_entry:
                continue
            own_events.append(_parse_own_weapon_entry(own_entry))

        mission_clock: MissionClockSample | None = None
        if mission_clock_raw:
            try:
                mission_clock = MissionClockSample.from_wire(mission_clock_raw)
            except FiringParseError:
                mission_clock = None

        return FiringEventBatch(
            dcs_model_time_s=dcs_model_time_s,
            received_wall_clock_s=received_wall_clock_s,
            bridge_call_ms=bridge_call_ms,
            events=tuple(events),
            mission_clock=mission_clock,
            own_events=tuple(own_events),
        )


def _parse_entry(entry: str) -> FiringRawEvent:
    # `kind` is always one of `ALLOWED_KINDS` (fixed strings, no colons) and
    # `t`/`targets_ownship01`/`x`/`z` are always numeric-or-"nil" (no colons
    # either) -- only `initiator` (a mission-editor unit name, free text)
    # can contain a colon, same defensive posture `unit_velocity.py`/
    # `line_of_sight.py` already take toward untrusted Hook-side strings.
    # So split the two *fixed-shape* ends off first (one colon from the
    # left for `kind`, three colons from the right for `targets_ownship01`/
    # `x`/`z`), leaving whatever remains in the middle as `t:initiator`,
    # which splits unambiguously on its own first colon (`t` is always
    # numeric and therefore never contains one).
    head = entry.split(":", 1)
    if len(head) != 2:
        raise FiringParseError(
            "expected '<kind>:<t>:<initiator>:<targets_ownship01>:<x>:<z>', "
            f"got {entry!r}"
        )
    kind, rest = head
    tail = rest.rsplit(":", 3)
    if len(tail) != 4:
        raise FiringParseError(
            "expected '<kind>:<t>:<initiator>:<targets_ownship01>:<x>:<z>', "
            f"got {entry!r}"
        )
    t_and_initiator, targets_ownship_str, x_str, z_str = tail
    mid = t_and_initiator.split(":", 1)
    if len(mid) != 2:
        raise FiringParseError(
            "expected '<kind>:<t>:<initiator>:<targets_ownship01>:<x>:<z>', "
            f"got {entry!r}"
        )
    t_str, initiator = mid

    if kind not in ALLOWED_KINDS:
        raise FiringParseError(f"unrecognized event kind {kind!r} in entry {entry!r}")
    if not initiator:
        raise FiringParseError(f"empty initiator in entry {entry!r}")
    try:
        t_sim = float(t_str)
    except ValueError as exc:
        raise FiringParseError(
            f"field 't' must be a number in entry {entry!r}"
        ) from exc
    targets_ownship = _parse_bool01(targets_ownship_str, entry)
    x = _parse_optional_float(x_str, entry)
    z = _parse_optional_float(z_str, entry)

    return FiringRawEvent(
        kind=kind,
        t_sim=t_sim,
        initiator=initiator,
        targets_ownship=targets_ownship,
        x=x,
        z=z,
    )


def _parse_own_weapon_entry(entry: str) -> OwnWeaponRawEvent:
    """Parse one `own_entries` entry (module docstring):
    `OWN_SHOT:<t>:<seq>:<type>:<category>:<guidance>:<exists01>` or
    `OWN_GONE:<t>:<seq>`. No field here can contain a colon by
    construction (the Hook sanitises `<type>` before it ever reaches the
    wire), so a plain `split(":")` is unambiguous, unlike `_parse_entry`'s
    own `initiator` field above."""
    parts = entry.split(":")
    kind = parts[0]
    if kind not in OWN_WEAPON_ALLOWED_KINDS:
        raise FiringParseError(
            f"unrecognized own-weapon entry kind {kind!r} in entry {entry!r}"
        )
    if kind == "OWN_GONE":
        if len(parts) != 3:
            raise FiringParseError(f"expected 'OWN_GONE:<t>:<seq>', got {entry!r}")
        t_str, seq_str = parts[1], parts[2]
        return OwnWeaponRawEvent(
            kind=kind, t_sim=_parse_float(t_str, entry), seq=_parse_int(seq_str, entry)
        )

    # OWN_SHOT
    if len(parts) != 7:
        raise FiringParseError(
            "expected 'OWN_SHOT:<t>:<seq>:<type>:<category>:<guidance>:"
            f"<exists01>', got {entry!r}"
        )
    _, t_str, seq_str, type_str, category_str, guidance_str, exists_str = parts
    t_sim = _parse_float(t_str, entry)
    seq = _parse_int(seq_str, entry)
    type_name = _parse_optional_own_weapon_type(type_str, entry)
    category = _parse_optional_int(category_str, entry)
    guidance = _parse_optional_int(guidance_str, entry)
    exists_at_shot = _parse_bool01(exists_str, entry)
    return OwnWeaponRawEvent(
        kind=kind,
        t_sim=t_sim,
        seq=seq,
        type_name=type_name,
        category=category,
        guidance=guidance,
        exists_at_shot=exists_at_shot,
    )


def _parse_float(raw: str, entry: str) -> float:
    try:
        return float(raw)
    except ValueError as exc:
        raise FiringParseError(
            f"field 't' must be a number in entry {entry!r}"
        ) from exc


def _parse_int(raw: str, entry: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise FiringParseError(
            f"field 'seq' must be an integer in entry {entry!r}"
        ) from exc


def _parse_optional_int(raw: str, entry: str) -> int | None:
    if raw == "nil":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise FiringParseError(
            f"expected an integer or 'nil', got {raw!r} in entry {entry!r}"
        ) from exc


def _parse_optional_own_weapon_type(raw: str, entry: str) -> str | None:
    """`<type>` -- `"nil"` (the Hook's own guarded `getTypeName()` read
    failed) parses to `None`; anything else is bound-checked independently
    of the Hook's own truncation (module docstring's security paragraph)."""
    if raw == "nil":
        return None
    if len(raw) > MAX_OWN_WEAPON_TYPE_NAME_LEN:
        raise FiringParseError(
            f"own-weapon type name exceeds {MAX_OWN_WEAPON_TYPE_NAME_LEN} "
            f"characters in entry {entry!r}"
        )
    if any(ch in _OWN_WEAPON_TYPE_FORBIDDEN_CHARS for ch in raw):
        raise FiringParseError(
            f"own-weapon type name contains a forbidden delimiter "
            f"character in entry {entry!r}"
        )
    return raw


def _parse_bool01(raw: str, entry: str) -> bool:
    if raw == "1":
        return True
    if raw == "0":
        return False
    raise FiringParseError(
        f"expected a literal '0' or '1' targets_ownship flag, got {raw!r} in entry {entry!r}"
    )


def _parse_optional_float(raw: str, entry: str) -> float | None:
    if raw == "nil":
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise FiringParseError(
            f"expected a number or 'nil', got {raw!r} in entry {entry!r}"
        ) from exc
