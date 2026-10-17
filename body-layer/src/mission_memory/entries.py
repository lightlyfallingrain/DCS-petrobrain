"""The mission-memory entry schema -- `plans/bl8-mission-memory/plan.md`
Decision 2.

**Pure data, zero imports from `belief/`.** Every dataclass here is frozen;
the debrief tool this schema exists for (`explore-notes.md`'s "two
consumers") must one day be able to parse the written JSONL file without
body-layer's `belief` package anywhere on its path. `Certainty` below
mirrors `belief.decay.Certainty`'s four literal values exactly, duplicated
rather than imported -- the one place in this module the belief package's
vocabulary leaks in at all, and it leaks in as a string, not an import.

**`schema: 1`, and every field the plan's Decision 2 table names is
present from the start** -- including `MotionInfo.dir` and `AttackRunPayload
.outcome`, both of which the plan ships nullable-forever-until-later (no
direction belief, no destruction determination exist yet). The schema must
not change shape once that work lands; only the values stop being `None`.

**Encoding**: `encode_entry`/`decode_entry` are the only two functions that
know how an `Entry` maps to a JSON-safe `dict`. `CompositionItem.hi` can be
`math.inf` (the open-ended `OP_MORETHAN15UNITS` bucket) -- `json.dumps`'s
default `allow_nan=True` emits the non-standard `Infinity` token for it,
and `json.loads` accepts that token back without a flag, so no special
casing is needed for that one field."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

SCHEMA_VERSION = 1

EntryKind = Literal["group", "air_defence", "attack_run", "mark", "fired_on"]
Provenance = Literal["observed", "commanded", "briefed"]

#: Mirrors `belief.decay.Certainty` -- see module docstring.
Certainty = Literal["observed", "tracked", "estimated", "lost"]

#: Mirrors `belief.motion.MotionState`.
MotionState = Literal["moving", "stopped"]

#: The eight-point compass, frozen at write time (explore-notes.md
#: Decision 9). Not yet produced by any admission rule in Stages 1-3 --
#: `MotionInfo.dir` stays `None` until the direction-belief work exists
#: (plan's Decision 2, point 1) -- but the schema carries it now so that
#: work slots in without a schema change.
Direction = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

AttackOutcome = Literal["destroyed", "survived", "unknown"]

MarkAnchor = Literal["ownship", "target"]


@dataclass(frozen=True, slots=True)
class PhaseInfo:
    """`belief.mission_phase.MissionPhaseInfo`'s field-for-field mirror,
    duplicated rather than imported for the same reason as `Certainty`
    above."""

    name: str
    waypoint_index: int


@dataclass(frozen=True, slots=True)
class SeenHow:
    """How the entry's subject was most recently observed, frozen at write
    time."""

    optic: str
    range_m: float | None
    confidence: float
    certainty: Certainty


@dataclass(frozen=True, slots=True)
class EntryPosition:
    """Plan Decision 2, points 2-3: `y` does not carry the same provenance
    as `x`/`z` (it is `Contact.last_alt_m`, a last-observed value, never a
    fused estimate -- `uncertainty_m` says nothing about it), and
    `as_of_sim` is deliberately separate from the entry's own `t_sim` (an
    entry written now may record a look taken moments ago)."""

    x: float
    z: float
    y: float | None
    uncertainty_m: float
    as_of_sim: float
    lat: float | None
    lon: float | None
    #: A frozen phrase, `X-B20`-gated -- see Decision 9. `None` is the
    #: correct, common case, not a defect.
    landmark: str | None


@dataclass(frozen=True, slots=True)
class CompositionItem:
    """One class bucket's structured belief plus its frozen spoken word
    (Decision 2, point 4). `count_word` is `belief.speech.
    cardinality_phrase`'s output, frozen at write time -- `None` precisely
    when that function returns `None` (an exactly-one interval has nothing
    to hedge)."""

    op_class: str
    lo: int
    hi: float
    confidence: float
    count_word: str | None


@dataclass(frozen=True, slots=True)
class MotionInfo:
    state: MotionState | None
    dir: Direction | None


@dataclass(frozen=True, slots=True)
class ThreatInfo:
    envelope_m: float
    source: str


@dataclass(frozen=True, slots=True)
class GroupPayload:
    composition: tuple[CompositionItem, ...]
    motion: MotionInfo
    ad_link: int | None


@dataclass(frozen=True, slots=True)
class AirDefencePayload:
    composition: tuple[CompositionItem, ...]
    group_link: int | None
    threat: ThreatInfo | None


@dataclass(frozen=True, slots=True)
class AttackRunPayload:
    target_seq: int | None
    target_ref: str | None
    weapon: str | None
    outcome: AttackOutcome


@dataclass(frozen=True, slots=True)
class MarkPayload:
    """`index` is the mark's own growing counter -- always overwritten by
    `store.MissionMemory.append` (the Co-moving Fields table's single
    construction site obligation), never trusted from the caller. A caller
    building this payload before calling `append` should pass `index=0` as
    a placeholder; `append` replaces it."""

    index: int
    label: str | None
    anchor: MarkAnchor


@dataclass(frozen=True, slots=True)
class FiredOnPayload:
    shooter_seq: int | None
    shooter_ref: str | None
    targets_ownship: bool


Payload = (
    GroupPayload | AirDefencePayload | AttackRunPayload | MarkPayload | FiredOnPayload
)


@dataclass(frozen=True, slots=True)
class Entry:
    """One mission-memory entry. See module docstring and plan Decision 2
    for the schema; `store.MissionMemory.append` is this project's single
    sanctioned site that constructs a *live* `Entry` (one written from a
    real admission decision) -- `decode_entry` below also constructs one,
    but only to rebuild a historical entry already decided and already on
    disk, never to mint a new `seq`/mark index."""

    schema: int
    seq: int
    kind: EntryKind
    provenance: Provenance
    t_sim: float
    t_wall: float
    phase: PhaseInfo | None
    pos: EntryPosition | None
    seen: SeenHow | None
    belief_ref: str | None
    strikes: int | None
    #: RESERVED -- always `None` in BL-8. Present so the schema never
    #: changes when IFF modelling lands.
    iff: None
    payload: Payload


def _encode_phase(phase: PhaseInfo | None) -> dict[str, object] | None:
    if phase is None:
        return None
    return {"name": phase.name, "waypoint_index": phase.waypoint_index}


def _encode_pos(pos: EntryPosition | None) -> dict[str, object] | None:
    if pos is None:
        return None
    return {
        "x": pos.x,
        "z": pos.z,
        "y": pos.y,
        "uncertainty_m": pos.uncertainty_m,
        "as_of_sim": pos.as_of_sim,
        "lat": pos.lat,
        "lon": pos.lon,
        "landmark": pos.landmark,
    }


def _encode_seen(seen: SeenHow | None) -> dict[str, object] | None:
    if seen is None:
        return None
    return {
        "optic": seen.optic,
        "range_m": seen.range_m,
        "confidence": seen.confidence,
        "certainty": seen.certainty,
    }


def _encode_composition(
    composition: tuple[CompositionItem, ...],
) -> list[dict[str, object]]:
    return [
        {
            "op_class": item.op_class,
            "lo": item.lo,
            "hi": item.hi,
            "confidence": item.confidence,
            "count_word": item.count_word,
        }
        for item in composition
    ]


def _encode_motion(motion: MotionInfo) -> dict[str, object]:
    return {"state": motion.state, "dir": motion.dir}


def _encode_threat(threat: ThreatInfo | None) -> dict[str, object] | None:
    if threat is None:
        return None
    return {"envelope_m": threat.envelope_m, "source": threat.source}


def _encode_payload(kind: EntryKind, payload: Payload) -> dict[str, object]:
    """Dispatches on `kind` -- `decode_entry`'s exact inverse, one branch
    per kind, matching `_decode_payload`'s own dispatch."""
    if kind == "group":
        group = cast(GroupPayload, payload)
        return {
            "composition": _encode_composition(group.composition),
            "motion": _encode_motion(group.motion),
            "ad_link": group.ad_link,
        }
    if kind == "air_defence":
        ad = cast(AirDefencePayload, payload)
        return {
            "composition": _encode_composition(ad.composition),
            "group_link": ad.group_link,
            "threat": _encode_threat(ad.threat),
        }
    if kind == "attack_run":
        run = cast(AttackRunPayload, payload)
        return {
            "target_seq": run.target_seq,
            "target_ref": run.target_ref,
            "weapon": run.weapon,
            "outcome": run.outcome,
        }
    if kind == "mark":
        mark = cast(MarkPayload, payload)
        return {"index": mark.index, "label": mark.label, "anchor": mark.anchor}
    fired_on = cast(FiredOnPayload, payload)
    return {
        "shooter_seq": fired_on.shooter_seq,
        "shooter_ref": fired_on.shooter_ref,
        "targets_ownship": fired_on.targets_ownship,
    }


def encode_entry(entry: Entry) -> dict[str, object]:
    """`Entry` -> a JSON-safe `dict`. The only function in this module
    that walks the whole entry; `decode_entry` is its exact inverse."""
    return {
        "schema": entry.schema,
        "seq": entry.seq,
        "kind": entry.kind,
        "provenance": entry.provenance,
        "t_sim": entry.t_sim,
        "t_wall": entry.t_wall,
        "phase": _encode_phase(entry.phase),
        "pos": _encode_pos(entry.pos),
        "seen": _encode_seen(entry.seen),
        "belief_ref": entry.belief_ref,
        "strikes": entry.strikes,
        "iff": None,
        "payload": _encode_payload(entry.kind, entry.payload),
    }


def _decode_phase(data: dict[str, object] | None) -> PhaseInfo | None:
    if data is None:
        return None
    return PhaseInfo(
        name=cast(str, data["name"]),
        waypoint_index=cast(int, data["waypoint_index"]),
    )


def _decode_pos(data: dict[str, object] | None) -> EntryPosition | None:
    if data is None:
        return None
    return EntryPosition(
        x=cast(float, data["x"]),
        z=cast(float, data["z"]),
        y=cast("float | None", data["y"]),
        uncertainty_m=cast(float, data["uncertainty_m"]),
        as_of_sim=cast(float, data["as_of_sim"]),
        lat=cast("float | None", data["lat"]),
        lon=cast("float | None", data["lon"]),
        landmark=cast("str | None", data["landmark"]),
    )


def _decode_seen(data: dict[str, object] | None) -> SeenHow | None:
    if data is None:
        return None
    return SeenHow(
        optic=cast(str, data["optic"]),
        range_m=cast("float | None", data["range_m"]),
        confidence=cast(float, data["confidence"]),
        certainty=cast(Certainty, data["certainty"]),
    )


def _decode_composition(data: list[dict[str, object]]) -> tuple[CompositionItem, ...]:
    return tuple(
        CompositionItem(
            op_class=cast(str, item["op_class"]),
            lo=cast(int, item["lo"]),
            hi=cast(float, item["hi"]),
            confidence=cast(float, item["confidence"]),
            count_word=cast("str | None", item["count_word"]),
        )
        for item in data
    )


def _decode_group_payload(data: dict[str, object]) -> GroupPayload:
    motion_data = cast(dict[str, object], data["motion"])
    return GroupPayload(
        composition=_decode_composition(
            cast("list[dict[str, object]]", data["composition"])
        ),
        motion=MotionInfo(
            state=cast("MotionState | None", motion_data["state"]),
            dir=cast("Direction | None", motion_data["dir"]),
        ),
        ad_link=cast("int | None", data["ad_link"]),
    )


def _decode_air_defence_payload(data: dict[str, object]) -> AirDefencePayload:
    threat_data = cast("dict[str, object] | None", data["threat"])
    threat = (
        None
        if threat_data is None
        else ThreatInfo(
            envelope_m=cast(float, threat_data["envelope_m"]),
            source=cast(str, threat_data["source"]),
        )
    )
    return AirDefencePayload(
        composition=_decode_composition(
            cast("list[dict[str, object]]", data["composition"])
        ),
        group_link=cast("int | None", data["group_link"]),
        threat=threat,
    )


def _decode_attack_run_payload(data: dict[str, object]) -> AttackRunPayload:
    return AttackRunPayload(
        target_seq=cast("int | None", data["target_seq"]),
        target_ref=cast("str | None", data["target_ref"]),
        weapon=cast("str | None", data["weapon"]),
        outcome=cast(AttackOutcome, data["outcome"]),
    )


def _decode_mark_payload(data: dict[str, object]) -> MarkPayload:
    return MarkPayload(
        index=cast(int, data["index"]),
        label=cast("str | None", data["label"]),
        anchor=cast(MarkAnchor, data["anchor"]),
    )


def _decode_fired_on_payload(data: dict[str, object]) -> FiredOnPayload:
    return FiredOnPayload(
        shooter_seq=cast("int | None", data["shooter_seq"]),
        shooter_ref=cast("str | None", data["shooter_ref"]),
        targets_ownship=cast(bool, data["targets_ownship"]),
    )


def _decode_payload(kind: EntryKind, data: dict[str, object]) -> Payload:
    """Dispatches on `kind` -- a new kind is one branch here plus one
    `_decode_<kind>_payload` function, never a second switch elsewhere."""
    if kind == "group":
        return _decode_group_payload(data)
    if kind == "air_defence":
        return _decode_air_defence_payload(data)
    if kind == "attack_run":
        return _decode_attack_run_payload(data)
    if kind == "mark":
        return _decode_mark_payload(data)
    return _decode_fired_on_payload(data)


def decode_entry(data: dict[str, object]) -> Entry:
    """A JSON-safe `dict` (as produced by `encode_entry`, or read back from
    one JSONL line) -> `Entry`. Raises `KeyError` on a missing field --
    this schema has no optional keys, only nullable values, so a missing
    key is a corrupt or pre-schema file, not a case to degrade silently."""
    kind = cast(EntryKind, data["kind"])
    payload = _decode_payload(kind, cast("dict[str, object]", data["payload"]))
    return Entry(
        schema=cast(int, data["schema"]),
        seq=cast(int, data["seq"]),
        kind=kind,
        provenance=cast(Provenance, data["provenance"]),
        t_sim=cast(float, data["t_sim"]),
        t_wall=cast(float, data["t_wall"]),
        phase=_decode_phase(cast("dict[str, object] | None", data["phase"])),
        pos=_decode_pos(cast("dict[str, object] | None", data["pos"])),
        seen=_decode_seen(cast("dict[str, object] | None", data["seen"])),
        belief_ref=cast("str | None", data["belief_ref"]),
        strikes=cast("int | None", data["strikes"]),
        iff=None,
        payload=payload,
    )
