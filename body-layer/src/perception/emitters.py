"""Emitter resolution -- `plans/emitter-visibility/plan.md`, Stage A
(`BL-B72`): the shared mechanism by which a unit's own emission (gun fire,
a SAM launch's smoke trail, or a burning hull) makes it detectable at any
range out to the player bubble and through tree cover, without raising
classification or identification. See `docs/acceptance/
2026-10-15-firing-unit-visibility.md` for the user's own words and
`perception.visibility.check_visibility`'s own docstring for where the
`emitter` parameter this module feeds actually bypasses gates.

**One mechanism, three emitter kinds (only one built this stage).** The
plan's "The one mechanism, three emitters" section is explicit that
body-layer must see *"this object is emitting, and has been since t"* and
nothing about how that was learned -- `EmitterKind.BURNING` is the only
value this module resolves today; `FIRING`/`LAUNCH_SMOKE` (`BL-B73`/
`BL-B74`) wait on `AC-B8`'s event channel and fold into this same
`dict[int, Emitter]` shape when they land (plan's "Co-moving Fields"
table), never a parallel map `visibility.py` has to consult twice.

**Burning is a polled state, not an event, and that is why it is pure.**
`burning_emitters` is a stateless function of this poll's own
`GET /world_objects/latest` object dicts and `GET /unit_velocity/latest`
samples -- no latch, no missed burst, no start-without-end, because there
is nothing to accumulate between polls (plan: "Stage A has no state at
all: the predicate is recomputed from each poll's samples"). `naked_eye_
source.py` calls this once per poll, exactly where it already resolves
velocity and LOS by the same join."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

import tuning


class EmitterKind(str, Enum):
    """Which of the three emitter sources made a candidate self-reveal.
    Only `BURNING` is ever produced today (`BL-B73`/`BL-B74` add the other
    two). A plain `str` subclass, same convention as `perception.
    detection_trace.GateOutcome`, so `.value` serialises directly to JSON
    and onto `DetectionTrace.emitter_kind` without a custom encoder."""

    BURNING = "burning"


@dataclass(frozen=True, slots=True)
class Emitter:
    """One candidate's resolved emitter state for this poll -- the only
    thing `visibility.check_visibility` needs to decide whether to bypass
    gates 3/5, and the only thing `naked_eye_source.py` needs to pick the
    right `PROVENANCE_EMITTER_*` value. Carries no lifetime/position data
    of its own in this stage (Stage A's burning predicate has none to
    carry -- it is recomputed fresh every poll); `BL-B73`/`BL-B74` are
    expected to extend this dataclass with `since_sim`/`targets_ownship`/
    frozen position fields rather than replace it, per the plan's
    "Co-moving Fields" table."""

    kind: EmitterKind


#: **Below or at this fraction of `getLife0()` (`life / life0`), a unit
#: is burning and becomes detectable at any range through tree cover;
#: above it, it is not.** A *smaller* value here narrows the fire band
#: (fewer units burn), so `hi` is the over-triggering-risk direction and
#: `lo` the under-triggering one -- both bounded to the measured bracket
#: itself, since any value outside it would contradict the one sortie
#: that measured it. **Measured, not guessed, but a bracket rather than a
#: point** (`docs/acceptance/2026-09-24-damage-and-firing-probes.md`,
#: flown 2026-09-25, FLOWN AND CLOSED -- do not re-fly it): "fire is
#: present at a life fraction <= 0.69 and absent at >= 0.84. The
#: threshold lies in (0.69, 0.84]." This default is the band's midpoint,
#: a **stated assumption awaiting a sortie** (plan Risks: "Handled as
#: `tuning.real(..., status='assumption')` at the band's midpoint... not
#: an open question and not a reason to probe again" -- `tuning.Status`
#: has no literal `"assumption"` value, so this is declared
#: `"judgement"`, the closest of the five real values to "a reasoned pick
#: inside an already-measured bracket, not a fresh guess") -- a future
#: flight narrows this within the bracket `lo`/`hi` already enforce; it
#: does not need a new probe to do it. Whether the true threshold is
#: global or per-type is the same probe's other open follow-up, also not
#: resolved here: this module applies one global fraction to every unit.
FIRE_LIFE_FRACTION_MAX: Final[float] = tuning.real(
    "perception.emitters.FIRE_LIFE_FRACTION_MAX",
    0.765,
    lo=0.69,
    hi=0.84,
    status="judgement",
)


def burning_emitters(
    raw_objects: list[dict[str, Any]],
    samples: dict[str, Any] | None,
) -> dict[int, Emitter]:
    """Resolve which of this poll's `raw_objects` (raw `GET
    /world_objects/latest` object dicts, `unit_name`/`object_id` fields
    included) are burning, per `getLife()`/`getLife0()` carried on this
    poll's `GET /unit_velocity/latest` `samples` dict (`AC-B7`'s wire
    shape, keyed by `unit_name` -- the same per-sample dict `perception.
    motion`'s velocity join already reads, now also carrying `"life"`/
    `"life0"`).

    Returns only entries that actually resolved to burning -- `.get(
    object_id)` returning `None` covers every "not burning" and "unknown"
    case uniformly (no samples this poll, missing/non-unique `unit_name`,
    no life data on this unit's sample, or a healthy fraction), mirroring
    `naked_eye_source._resolve_velocity_by_object_id`'s own return
    contract.

    **Non-unique `unit_name` collision handling, the same rule
    `_resolve_velocity_by_object_id`/`_resolve_los_by_unit_name` already
    establish**: a `unit_name` shared by two or more of *this poll's*
    `raw_objects` drops to unresolved for every one of them, rather than
    guessing which one a matched sample belongs to."""
    if not samples:
        return {}

    name_counts: Counter[str] = Counter(
        name for obj in raw_objects if isinstance(name := obj.get("unit_name"), str)
    )

    result: dict[int, Emitter] = {}
    for obj in raw_objects:
        name = obj.get("unit_name")
        object_id = obj.get("object_id")
        if not isinstance(name, str) or not isinstance(object_id, int):
            continue
        if name_counts[name] > 1:
            continue
        sample = samples.get(name)
        if not isinstance(sample, dict):
            continue
        life = sample.get("life")
        life0 = sample.get("life0")
        if not isinstance(life, int | float) or not isinstance(life0, int | float):
            continue
        if life0 <= 0:
            continue
        fraction = life / life0
        if 0.0 <= fraction <= FIRE_LIFE_FRACTION_MAX:
            result[object_id] = Emitter(kind=EmitterKind.BURNING)
    return result
