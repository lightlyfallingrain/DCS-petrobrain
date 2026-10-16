"""Firing-event wire format -- `plans/emitter-visibility/plan.md` Stage B
(`AC-B8`, the transport half of `[[BL-B73]]`/`[[BL-B74]]`).

`petrobrain-firing-events-hook.lua` registers `world.addEventHandler` in
the `"scripting"` mission state (the same bridge every other Hook script
in this module already uses), accumulates events in-state as they arrive,
and drains the accumulated batch once a second -- the same registration/
poll split `petrobrain-f10-commands-hook.lua` established, extended with an
event *handler* rather than a player-driven queue. The closed probe
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
is no reason to cross more than that one bit."""

from __future__ import annotations

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
class FiringEventBatch:
    """One poll's worth of drained firing events, plus that poll's own
    `dcs_model_time_s` -- mirrors `LineOfSightSnapshot`'s dual-clock shape,
    `received_wall_clock_s` stamped by the collector at receipt, not by the
    Hook script (same posture as every other feed in this module)."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    bridge_call_ms: float
    events: tuple[FiringRawEvent, ...]

    @staticmethod
    def from_wire(
        payload: str, *, bridge_call_ms: float, received_wall_clock_s: float
    ) -> FiringEventBatch:
        """Parse one compact wire string (module docstring) into a typed
        batch. `entries` may be empty (nothing fired this poll)."""
        parts = payload.split("|", 2)
        if len(parts) != 3:
            raise FiringParseError(f"expected '<count>|<t>|<entries>', got {payload!r}")
        count_str, t_str, entries_str = parts
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

        return FiringEventBatch(
            dcs_model_time_s=dcs_model_time_s,
            received_wall_clock_s=received_wall_clock_s,
            bridge_call_ms=bridge_call_ms,
            events=tuple(events),
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
