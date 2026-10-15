"""Emitter resolution -- `plans/emitter-visibility/plan.md`: the shared
mechanism by which a unit's own emission (gun fire, a SAM launch's smoke
trail, or a burning hull) makes it detectable at any range out to the
player bubble and through tree cover, without raising classification or
identification. See `docs/acceptance/2026-10-15-firing-unit-visibility.md`
for the user's own words and `perception.visibility.check_visibility`'s
own docstring for where the `emitter` parameter this module feeds actually
bypasses gates.

**One mechanism, three emitter kinds (two built, one a seam).** The plan's
"The one mechanism, three emitters" section is explicit that body-layer
must see *"this object is emitting, and has been since t"* and nothing
about how that was learned. `EmitterKind.BURNING` (Stage A, `BL-B72`) and
`EmitterKind.FIRING` (Stage B, `BL-B73`) are both resolved here;
`LAUNCH_SMOKE` (`BL-B74`) is not built this stage -- `resolve_emitters`
below only ever folds `BURNING`/`FIRING` into the one `dict[int, Emitter]`
`visibility.py` consults, never a parallel map it has to check twice.

**Burning is a polled state, not an event, and that is why it is pure.**
`burning_emitters` is a stateless function of this poll's own
`GET /world_objects/latest` object dicts and `GET /unit_velocity/latest`
samples -- no latch, no missed burst, no start-without-end, because there
is nothing to accumulate between polls (plan: "Stage A has no state at
all: the predicate is recomputed from each poll's samples").

**Firing is an event, and the state that makes it a poll-shaped answer
anyway lives upstream, in the collector, not here.** `firing_emitters`
below is just as pure as `burning_emitters` -- it only ever reads this
poll's `GET /firing/latest` snapshot (`aircraft_layer.collector.
firing_receiver.EmitterTracker.snapshot()`'s wire shape) and this poll's
`raw_objects`, joined by `unit_name`. The latch, the watchdog, and the
per-kind death semantics the plan's "Co-moving Fields" table specifies are
`EmitterTracker`'s job (plan's "Answers to the five design questions" #1:
body-layer's perception is deliberately recomputed-per-poll and stateless,
so a latch/watchdog machine would be its first stateful input and would
break replay determinism). By the time a `FIRING` entry reaches this
module, "is this unit currently firing" is already a plain yes/no this
poll can answer the same way it answers "is this unit burning."

**`resolve_emitters` is the single merge point for both maps, per the
plan's own instruction** (`Co-moving Fields` table, last row): a unit
could in principle both fire and burn, and `FIRING` wins over `BURNING`
for wording priority -- resolved once, here, never twice (naked_eye_
source.py calls this one function, not the two kind-specific ones
separately, so there is exactly one place this precedence can be got
wrong)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any, Final

import tuning


class EmitterKind(str, Enum):
    """Which of the three emitter sources made a candidate self-reveal.
    `LAUNCH_SMOKE` (`BL-B74`) is named here, per the plan's own docstring
    convention of naming every kind in this enum even before it is
    produced, but `resolve_emitters` below never returns it this stage. A
    plain `str` subclass, same convention as `perception.detection_trace.
    GateOutcome`, so `.value` serialises directly to JSON and onto
    `DetectionTrace.emitter_kind` without a custom encoder."""

    BURNING = "burning"
    FIRING = "firing"
    LAUNCH_SMOKE = "launch_smoke"


@dataclass(frozen=True, slots=True)
class Emitter:
    """One candidate's resolved emitter state for this poll -- the only
    thing `visibility.check_visibility` needs to decide whether to bypass
    gates 3/5, and the only thing `naked_eye_source.py` needs to pick the
    right `PROVENANCE_EMITTER_*` value.

    `targets_ownship` (`BL-B73`) is `False` for every `BURNING` emitter
    (burning carries no notion of a target at all) and for a `FIRING`
    emitter the collector's `EmitterTracker` did not resolve a named
    ownship target for -- `naked_eye_source.py` reads it only when
    `kind is FIRING`, mirroring the plan's own distinction between
    *"taking fire"* and *"something firing... far"*."""

    kind: EmitterKind
    targets_ownship: bool = False


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


def firing_emitters(
    raw_objects: list[dict[str, Any]],
    firing_active: dict[str, Any] | None,
) -> dict[int, Emitter]:
    """Resolve which of this poll's `raw_objects` are currently firing, per
    `GET /firing/latest`'s `"active"` map (`aircraft_layer.collector.
    firing_receiver.EmitterTracker.snapshot()`'s wire shape --
    `{unit_name: {"kind", "since_sim", "targets_ownship"}}`), joined by
    `unit_name` -- the same join key, and the same non-unique-`unit_name`-
    drops-to-unresolved rule, `burning_emitters` above already establishes.

    **No latch, no watchdog, no sim-time skew check here.** `firing_active`
    is already the collector's own answer to "who is currently firing" --
    the latch that keeps a sub-poll burst visible and the watchdog that
    bounds a `START` with no `END` are `EmitterTracker.ingest()`'s job
    (`collector.firing_receiver`'s own docstring), run before this poll's
    `GET /firing/latest` was ever fetched. This function only ever reads
    the result, exactly as `burning_emitters` only ever reads this poll's
    life fraction -- neither accumulates anything of its own between
    polls.

    Returns only entries whose `"kind"` is `EmitterKind.FIRING.value`
    (`collector.firing_receiver.EMITTER_KIND_FIRING`, the two sides' shared
    string convention, `.get(object_id)` returning `None` covering every
    "not firing" and "unknown" case uniformly, same contract as
    `burning_emitters`."""
    if not firing_active:
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
        entry = firing_active.get(name)
        if not isinstance(entry, dict):
            continue
        if entry.get("kind") != EmitterKind.FIRING.value:
            continue
        targets_ownship = entry.get("targets_ownship")
        result[object_id] = Emitter(
            kind=EmitterKind.FIRING,
            targets_ownship=bool(targets_ownship) if targets_ownship else False,
        )
    return result


def resolve_emitters(
    raw_objects: list[dict[str, Any]],
    unit_velocity_samples: dict[str, Any] | None,
    firing_active: dict[str, Any] | None,
) -> dict[int, Emitter]:
    """The single merge point `naked_eye_source.py` calls instead of
    `burning_emitters`/`firing_emitters` separately -- the plan's "Co-moving
    Fields" table requires precedence between the two be resolved **once**,
    here, "never in two places." `FIRING` wins over `BURNING` for wording
    priority when a unit happens to be both (a burning vehicle whose crew
    is still fighting it): `visibility.check_visibility`'s tier clamp is
    identical either way (both kinds clamp to `lowres`/presence), so the
    only thing this precedence actually decides is which `PROVENANCE_
    EMITTER_*` value -- and therefore which callout wording and priority --
    `naked_eye_source.py` picks for the object."""
    merged = burning_emitters(raw_objects, unit_velocity_samples)
    merged.update(firing_emitters(raw_objects, firing_active))
    return merged
