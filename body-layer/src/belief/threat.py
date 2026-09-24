"""Believed engagement envelopes, keyed strictly on belief -- `plans/
watch-reporting/plan.md` Stage 4. The only new module in this plan.

**Source and provenance.** `body-layer/data/threat_envelopes.json` (28
entries, extracted from `https://wiki.hoggitworld.com/view/Threat_Database`,
the saved source page committed beside it as provenance) -- a community
wiki, not DCS ground truth and not ED documentation: **provisional until
confirmed**, the same evidence class as the pydcs-derived projections in
`world-model`. This module reads the payload's own `source`/`source_file`/
`retrieved`/`provenance`/`units` header rather than restating them as
literals here, so the two cannot drift apart (`_HEADER` below, exposed for
any caller that wants to cite it).

**No fallback envelope, ever.** There is no default engagement range. A
contact whose class/type resolves to no row simply never produces a danger
call -- inventing a number would be an authoritative-sounding warning
derived from nothing, worse than silence.

**The structural no-omniscience guard: `envelope_for` takes a
`ClassificationBelief`, never an `Observation` or a raw DCS type string.**
The signature *is* the guard -- this module cannot be handed ground truth
because it does not accept the type that carries it. It imports nothing
from `perception.source`.

**Null handling is per-field, not uniform (4f-i) -- the payload's own
"a null MUST degrade to no warning" rule is correct for `range_max_m` and
backwards for the other three:**

| field | null degrades to | why |
|---|---|---|
| `range_max_m` | entry dropped entirely -- no envelope at all | nothing to test with no reach |
| `range_min_m` | `0.0` -- no inner hole | assume it can shoot you close in |
| `alt_min_m` | `0.0` -- no floor | assume flying low does not help |
| `alt_max_m` | kept `None` (unbounded) | carried for a future consumer; nothing here reads it (see 4f's own note: the lowest ceiling in the table, 1,372m, is not a combat-profile altitude for this aircraft) |

**Class-level rollup (Decision 4c) is derived at import time, not
hand-written.** For each row, `perception.object_model.profile_for(row.
threat)` resolves the same `op_class` the naked-eye channel would assign to
that type; the class's envelope is the *worst case* among its members --
longest `range_max_m`, and (conservative in the same direction) `range_min_m
=0`/`alt_min_m=0` regardless of what any individual member declares, since
"he knows only *that is a SAM*" cannot inherit one specific member's own
inner hole or floor. A row whose keyword resolves to `object_model.
DEFAULT_OP_CLASS` (unmatched) contributes to no real class -- that bucket is
never returned as a class-level classification value in the first place
(`classification.py`'s own exclusion), so it is never queried here either.
Same "computed once from a static table" precedent as `command_matcher.
VERB_ANCHOR_WORDS`: a new SAM added to `object_model.py` updates the class
worst case automatically.

**A finding this rollup exposes, recorded rather than patched here:** the
`OP_SRSAM` bucket spans SA-3 (~18 km per this table's own 25.0 km S-125
entry, or ~35.6 km if 2K12/SA-6 is folded in -- see the worked table in
the plan) down to SA-13 (~5.2 km), a roughly 4x-7x spread. The class-level
warning is therefore very early and often badly wrong in magnitude until
type-level recognition narrows it. That is a property of this project's
own `op_class` buckets, not a defect in this lookup.

**Type-level matching (`level == TYPE`) is a simple bidirectional
substring match** between the classification's own value (a reporting
name/type string) and each row's `threat` name, case-insensitive --
`object_model.profile_for`'s own "keyword found in text" shape, applied in
the other direction since there is no shared keyword table between the two
sources. Ties (more than one row matching) prefer the longer `threat`
string as the more specific name. **No fallback to the class-level rollup
when no type row matches** -- Decision 4c names only two lookup paths
(class rollup at `CLASS`, the per-type row at `TYPE`), and this module
does not invent a third; a specifically-identified threat absent from the
extracted table produces no warning, the same "no fallback, ever" rule
4a states for the missing-row case generally.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from belief.classification import ClassificationBelief, SpecificityLevel
from perception import object_model

#: `body-layer/data/threat_envelopes.json`, relative to this file:
#: `src/belief/threat.py` -> `src/belief` -> `src` -> `body-layer` -> `data`.
_DATA_PATH: Final[Path] = (
    Path(__file__).resolve().parent.parent.parent / "data" / "threat_envelopes.json"
)


@dataclass(frozen=True, slots=True)
class EngagementEnvelope:
    """One believed engagement envelope -- either a specific type's own
    row, or a class's derived worst case (`envelope_for`'s two resolution
    paths). All fields metres; `alt_max_m` is carried and never tested
    against (see module docstring's null-handling table)."""

    range_min_m: float
    range_max_m: float
    alt_min_m: float
    alt_max_m: float | None


@dataclass(frozen=True, slots=True)
class _ThreatRow:
    threat: str
    category: str
    range_min_m: float
    range_max_m: float
    alt_min_m: float
    alt_max_m: float | None


def _load_header_and_rows() -> tuple[dict[str, object], list[_ThreatRow]]:
    with _DATA_PATH.open(encoding="utf-8") as handle:
        raw = json.load(handle)
    header = {key: value for key, value in raw.items() if key != "entries"}
    rows: list[_ThreatRow] = []
    for entry in raw["entries"]:
        range_max_m = entry["range_max_m"]
        if range_max_m is None:
            # 4f-i: no reach at all -- there is nothing to test, and this
            # is the one field the payload's own "null means silence" rule
            # is correct for. Entry dropped entirely (only SA-5/S-200 in
            # the current 28-entry table).
            continue
        range_min_m = entry["range_min_m"]
        alt_min_m = entry["alt_min_m"]
        alt_max_m = entry["alt_max_m"]
        rows.append(
            _ThreatRow(
                threat=entry["threat"],
                category=entry["category"],
                range_min_m=float(range_min_m) if range_min_m is not None else 0.0,
                range_max_m=float(range_max_m),
                alt_min_m=float(alt_min_m) if alt_min_m is not None else 0.0,
                alt_max_m=float(alt_max_m) if alt_max_m is not None else None,
            )
        )
    return header, rows


#: The payload's own provenance header (`source`/`source_file`/
#: `retrieved`/`provenance`/`units`/`null_means`) -- read once at import,
#: never restated as a literal elsewhere in this module.
_LOADED: Final[tuple[dict[str, object], list[_ThreatRow]]] = _load_header_and_rows()
_HEADER: Final[dict[str, object]] = _LOADED[0]
_ROWS: Final[list[_ThreatRow]] = _LOADED[1]


def _row_envelope(row: _ThreatRow) -> EngagementEnvelope:
    return EngagementEnvelope(
        range_min_m=row.range_min_m,
        range_max_m=row.range_max_m,
        alt_min_m=row.alt_min_m,
        alt_max_m=row.alt_max_m,
    )


def _derive_class_envelopes() -> dict[str, EngagementEnvelope]:
    """Decision 4c's rollup -- see module docstring. Computed once at
    import, joining `_ROWS` through `object_model.profile_for` rather than
    a hand-written per-class table."""
    class_max_range_m: dict[str, float] = {}
    for row in _ROWS:
        op_class = object_model.profile_for(row.threat).op_class
        if op_class == object_model.DEFAULT_OP_CLASS:
            # Unmatched keyword -- contributes to no real class, and that
            # class is never returned as a class-level classification value
            # in the first place (`classification.py`'s own exclusion).
            continue
        class_max_range_m[op_class] = max(
            class_max_range_m.get(op_class, 0.0), row.range_max_m
        )
    return {
        op_class: EngagementEnvelope(
            # Conservative in the safe direction on every axis, per module
            # docstring: no inner hole, no floor, the class's own worst-case
            # reach -- "he knows only *that is a SAM*" cannot inherit one
            # specific member's own protective inner hole or altitude floor.
            range_min_m=0.0,
            range_max_m=range_max_m,
            alt_min_m=0.0,
            alt_max_m=None,
        )
        for op_class, range_max_m in class_max_range_m.items()
    }


_CLASS_ENVELOPES: Final[dict[str, EngagementEnvelope]] = _derive_class_envelopes()


def _match_type_row(value: str) -> _ThreatRow | None:
    """Bidirectional case-insensitive substring match between `value` (a
    reporting name / type string) and each row's `threat` name -- see
    module docstring's "Type-level matching" note. Ties prefer the longer
    `threat` string, a crude specificity proxy; `None` if nothing matches
    at all."""
    lowered = value.lower()
    matches = [
        row
        for row in _ROWS
        if row.threat.lower() in lowered or lowered in row.threat.lower()
    ]
    if not matches:
        return None
    return max(matches, key=lambda row: len(row.threat))


def envelope_for(classification: ClassificationBelief) -> EngagementEnvelope | None:
    """The believed engagement envelope for `classification`, or `None`
    when there is nothing to test with -- **the no-omniscience boundary in
    one line.**

    - `UNKNOWN`/`PRESENCE` -> `None`. A dot has no envelope.
    - `CLASS` -> the derived class worst case (`_CLASS_ENVELOPES`), or
      `None` if this class has no threat rows at all (ground armour/trucks
      -- see 4b, "no envelope worth modelling against a helicopter beyond
      gun range").
    - `TYPE` -> the specific row (`_match_type_row`), or `None` if no row
      matches -- no fallback to the class rollup, see module docstring."""
    if classification.level in (SpecificityLevel.UNKNOWN, SpecificityLevel.PRESENCE):
        return None
    if classification.value is None:
        return None
    if classification.level == SpecificityLevel.TYPE:
        row = _match_type_row(classification.value)
        return _row_envelope(row) if row is not None else None
    # SpecificityLevel.CLASS
    return _CLASS_ENVELOPES.get(classification.value)
