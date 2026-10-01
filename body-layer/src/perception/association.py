"""Single-detection <-> world-object association -- `plans/pb1-perception-
logger/plan.md`'s "Association design" section, resolved into code.

`HybridPerceptionSource` (`perception.hybrid_source`) calls `associate()`
each time it sees a new-or-changed HelperAI detection (`middle_list_text`),
to decide which `LoGetWorldObjects` candidate (if any) that detection refers
to. This module is pure and fixture-testable -- no network I/O, no
world-model queries -- per the plan's explicit requirement that the
decision logic be testable against recorded/hand-authored fixtures without a
live aircraft-layer connection.

**Scope note** (see `plans/pb1-perception-logger/plan.md`'s Invariant
Check): this is a *disambiguator*, not a *gate*. `HybridPerceptionSource`
already confirmed a real detection exists (HelperAI populated
`middle_list_text`) before calling `associate()` at all -- what this module
decides is only *which* world object that real detection most plausibly
refers to, and how confidently. Picking the wrong nearby object among
several similar ones is an association error, not an omniscience leak.

That describes `associate()`, which remains the module's subject. It is no
longer true of the module as a whole: `filter_ownship()` and
`filter_player_bubble()` below *are* unconditional pre-filters, called by
both `HybridPerceptionSource` and `NakedEyePerceptionSource` before any
channel-specific logic (`filter_player_bubble()` is the computation-scope
limit from `todo/todo.md`'s "Player bubble" item -- see that function's own
docstring and `PLAYER_BUBBLE_RADIUS_M`'s docstring for why it lives here and
not in `visibility.py`). They live here rather than in `geometry.py` -- the
more obvious home for something every tier shares -- because
`WorldObjectCandidate` is defined in this module. Placement is deliberate,
not expedient.

Algorithm (plan's "Association design" section, unchanged here):
1. Candidate pool = every `WorldObjectCandidate` passed in, no coalition/IFF
   filtering (plan decision, `Risks & Unknowns`).
2. Plausibility filter: drop candidates outside `RANGE_CAP_M` or outside
   `FORWARD_HEMISPHERE_HALF_WIDTH_DEG` of ownship's true heading.
3. Type-match scoring: keyword overlap between the detection's
   classification text and each surviving candidate's `object_type`, or its
   resolved reporting name, whichever scores higher (`_type_match_score`,
   `plans/pb2-contact-memory/plan.md` Stage 0).
4. Decision: zero survivors -> `None` (caller drops the detection, emits no
   `Observation`). Exactly one survivor, or one candidate strictly
   top-scored by more than `TYPE_MATCH_TIE_MARGIN`: confident single match
   (`CONFIDENT_ASSOCIATION_CONFIDENCE`, `CONFIDENT_ASSOCIATION_METHOD`). Two
   or more tied at the top score: ambiguous match from the *nearest* tied
   candidate (`AMBIGUOUS_ASSOCIATION_CONFIDENCE`,
   `AMBIGUOUS_ASSOCIATION_METHOD`).

All thresholds below are named, tunable starting constants, not inline
literals -- per the plan's own flagged risk that none of them are validated
against real multi-target scenes yet.
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from coordinates import wgs84_to_dcs
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.motion import Vec3
from perception.reporting_names import reporting_name_for
from perception.source import OwnshipState

#: Generous optical-detection envelope for a ground vehicle from a
#: helicopter -- not derived from any DCS sensor-range figure (none exists
#: for Petrovich, see the plan's Risks section), a plausibility bound only.
RANGE_CAP_M: Final[float] = 5000.0

#: The player bubble (`todo/todo.md`, "Player bubble: 10 km, settled
#: 2026-09-28", user direction): ground/air unit detection *computation* is
#: bounded to this radius around ownship. Nothing beyond it is considered at
#: all -- not gated late, not scored and discarded -- because it is applied
#: here, at `filter_player_bubble()` below, which both concrete
#: `PerceptionSource` tiers call immediately after `filter_ownship()` and
#: before anything else (gaze, group salience, `check_visibility`'s gate
#: chain, clustering, or -- for the hybrid channel -- `associate()`'s own
#: per-leaf loop): the earliest point in either poll where a candidate
#: becomes work rather than just a row in a list.
#:
#: **This is a computation-scope limit, not a perception limit, and the two
#: must never collapse into one constant even though they carry the same
#: number today.** `visibility.NAKED_EYE_RANGE_CAP_M` (10000.0) is a sanity
#: bound on what the naked eye is allowed to *claim* to have seen -- itself
#: an admitted guess, scaled by whichever optic is active. This constant
#: answers a different question: what is even worth computing in the first
#: place, regardless of which optic or channel might eventually look at it.
#: They will diverge the moment the 9K113 sight lands (per the todo item):
#: its cone reaches 20 km while the naked eye's own cap stays at 10 km, and
#: when that exception exists it will be evaluated *within* the bubble
#: filter below (narrowed to the sight's own FOV), not by raising this
#: radius -- raising it would reinstate the whole-sphere cost the bubble
#: exists to remove, at four times the area. Do not import this from
#: `visibility.py`, alias it to `NAKED_EYE_RANGE_CAP_M`, or vice versa --
#: `tests/test_association.py`'s `test_player_bubble_radius_is_not_...`
#: pair asserts neither module's source references the other's constant
#: name, specifically to catch that collapse.
#:
#: **Not measured, and deliberately not.** Nothing here establishes DCS's
#: own culling radius for `LoGetWorldObjects` -- large units may well be
#: reported well past this. This is a decision about what is *worth
#: computing*, taken on the pilot's own judgement about what he cares
#: about ("we don't usually care about things that far"), not a discovered
#: limit. Revisit if a sortie shows something important missed near the
#: boundary; it is a number to revisit, not a law.
#:
#: **Ground and air units only -- never apply this to world-model
#: geography** (landmarks, settlements, roads, beacons, airports). Those
#: are reached by proximity to a contact (`belief.enrichment`), not by
#: scanning a candidate pool, and this constant has no seam into that path
#: at all -- it only ever filters `WorldObjectCandidate` lists built from
#: `LoGetWorldObjects`.
PLAYER_BUBBLE_RADIUS_M: Final[float] = 10000.0

#: Half-width of the forward-hemisphere bearing window from ownship's true
#: heading, degrees. Not a claim about where the ASP-17 sight is pointed
#: (that signal is confirmed dead) -- a plausibility filter on where a
#: human-crewed optical detection could plausibly have come from.
FORWARD_HEMISPHERE_HALF_WIDTH_DEG: Final[float] = 90.0

#: Two candidates are "tied" (ambiguous) when their type-match scores differ
#: by no more than this. `0` means only a strict score tie counts as
#: ambiguous -- any candidate with a strictly higher keyword-overlap score
#: is treated as the unambiguous winner.
TYPE_MATCH_TIE_MARGIN: Final[int] = 0

CONFIDENT_ASSOCIATION_CONFIDENCE: Final[float] = 0.6
CONFIDENT_ASSOCIATION_METHOD: Final[str] = "bearing_range_terrain"

AMBIGUOUS_ASSOCIATION_CONFIDENCE: Final[float] = 0.25
AMBIGUOUS_ASSOCIATION_METHOD: Final[str] = "bearing_range_terrain_ambiguous_association"

_WORD_RE: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class WorldObjectCandidate:
    """One `LoGetWorldObjects` object, in the DCS-native x/z metres
    `perception.geometry` works in -- deliberately not the aircraft-layer
    wire shape (`lat_deg`/`lon_deg`), which is converted once via
    `from_dict` rather than carried through association's pure math."""

    object_id: int
    object_type: str
    x: float
    z: float
    alt_m: float
    #: `None` when the aircraft-layer poll that produced this candidate
    #: couldn't determine ownship identity that tick (`LoGetPlayerPlaneId()`
    #: failed) -- see `WorldObjectSample.is_ownship`'s docstring
    #: (`aircraft-layer/src/schema/world_objects.py`) for the tri-state
    #: contract. `filter_ownship()` below only drops candidates where this
    #: is `True`; `None` is kept rather than silently coerced to "not
    #: ownship" or "is ownship" either way.
    is_ownship: bool | None
    #: True heading, degrees -- converted once from the wire's
    #: `heading_true_rad` (`aircraft-layer/src/schema/world_objects.py`'s
    #: `WorldObjectSample`, a required, non-nullable field) by `from_dict`
    #: below, matching this module's existing degree convention for
    #: bearings. `None` only when a malformed/synthetic dict is missing the
    #: key outright (defensive; unreachable from the real wire schema) --
    #: never coerced to a guessed aspect, same tri-state discipline as
    #: `is_ownship` above (`plans/aspect-aware-profiles/plan.md`). Consumed
    #: by `visibility.check_visibility` for aspect-aware apparent extent
    #: (`object_model.apparent_extent_m`); `associate()`/`filter_ownship()`
    #: in this module don't need it.
    heading_true_deg: float | None = None
    #: DCS-native velocity, m/s (`perception.motion.Vec3`) -- `plans/
    #: movement-detection/plan.md`. `None` means "no velocity sample joined
    #: for this object this poll", which is **unknown, never "stopped"**:
    #: absent `UnitName`, a non-unique `UnitName` among this poll's
    #: candidates, or the velocity sample too stale/missing to trust (see
    #: `naked_eye_source.py`'s join step, which resolves this field --
    #: `associate()`/`filter_ownship()` in this module don't need it, same
    #: footing as `heading_true_deg` above). Deliberately never crosses out
    #: of `perception/` as a vector -- `perception.motion.is_apparently_
    #: moving` is the only thing allowed to turn it into something `belief/`
    #: can see.
    velocity: Vec3 | None = None

    @staticmethod
    def from_dict(
        data: dict[str, Any],
        *,
        theatre: str,
        velocity: dict[str, float] | None = None,
    ) -> WorldObjectCandidate:
        """Build a candidate from one aircraft-layer `GET /world_objects/latest`
        object dict (`aircraft-layer/src/schema/world_objects.py`'s
        `WorldObjectSample.to_dict` shape), converting its lat/lon to
        DCS-native x/z via world-model's coordinate subsystem -- the one
        seam this module has to a real dependency, kept out of the pure
        `associate()` function below so that function stays fixture-testable
        with plain `WorldObjectCandidate` instances.

        `velocity` is an already-resolved `{"vx", "vy", "vz"}` dict (the
        unit-velocity feed's own per-sample shape, `aircraft-layer/src/
        schema/unit_velocity.py`'s `UnitVelocitySample.to_dict`) -- the
        caller (`naked_eye_source.py`) is responsible for the unit_name join
        and skew check; this method's only job is the raw-floats -> `Vec3`
        conversion, the same "converted once in `from_dict`" pattern
        `heading_true_rad` -> degrees already uses above. `None` (the
        default) keeps every existing `from_dict` call site -- test
        fixtures included -- compiling and behaving exactly as before."""
        x, z = wgs84_to_dcs(theatre, float(data["lat_deg"]), float(data["lon_deg"]))
        is_ownship_raw = data.get("is_ownship")
        heading_true_rad = data.get("heading_true_rad")
        resolved_velocity = (
            None
            if velocity is None
            else Vec3(
                x=float(velocity["vx"]),
                y=float(velocity["vy"]),
                z=float(velocity["vz"]),
            )
        )
        return WorldObjectCandidate(
            object_id=int(data["object_id"]),
            object_type=str(data["object_type"]),
            x=x,
            z=z,
            alt_m=float(data["altitude_m"]),
            is_ownship=None if is_ownship_raw is None else bool(is_ownship_raw),
            heading_true_deg=(
                None
                if heading_true_rad is None
                else math.degrees(float(heading_true_rad))
            ),
            velocity=resolved_velocity,
        )


@dataclass(frozen=True, slots=True)
class AssociationResult:
    """The outcome of a successful `associate()` call -- always carries a
    resolved candidate and its geometry; `associate()` returns `None`
    instead of this type when no candidate survives (see module docstring)."""

    candidate: WorldObjectCandidate
    bearing_deg: float
    range_m: float
    confidence: float
    method: str
    ambiguous: bool


def filter_ownship(
    candidates: Sequence[WorldObjectCandidate],
) -> list[WorldObjectCandidate]:
    """Drop any candidate whose `is_ownship` is `True` -- the aircraft-layer
    flag set from `LoGetPlayerPlaneId()` (see `WorldObjectCandidate.is_ownship`'s
    docstring), replacing an earlier 50 m proximity-radius heuristic that had
    a false-negative window for any genuine object within 50 m of ownship
    (troop insertion/extraction, close formation, hovering directly over a
    target -- `todo/todo.md` backlog item). Only `True` is dropped: `None`
    (ownship identity undetermined that poll) and `False` are both kept, per
    the same "don't fabricate a fact you don't have" reasoning as the flag's
    own tri-state contract. Both `HybridPerceptionSource` and
    `NakedEyePerceptionSource` call this on their raw `WorldObjectCandidate`
    list before running their own filtering, since both build that list from
    the same unfiltered `LoGetWorldObjects` snapshot."""
    return [candidate for candidate in candidates if candidate.is_ownship is not True]


def filter_player_bubble(
    candidates: Sequence[WorldObjectCandidate],
    ownship: OwnshipState,
) -> list[WorldObjectCandidate]:
    """Drop any candidate further than `PLAYER_BUBBLE_RADIUS_M` from
    ownship -- see that constant's own docstring for why this exists and
    why it must stay independent of `visibility.NAKED_EYE_RANGE_CAP_M`.
    Both `HybridPerceptionSource` and `NakedEyePerceptionSource` call this
    immediately after `filter_ownship()`, before any gaze/salience/
    visibility/clustering/association work runs on the survivors -- a
    candidate beyond the bubble is never considered at all, not gated
    late. Equal-to-radius is kept (`<=`), matching `associate()`'s own
    `> RANGE_CAP_M` rejection convention elsewhere in this module."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    survivors: list[WorldObjectCandidate] = []
    for candidate in candidates:
        target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
        if range_m(observer, target) <= PLAYER_BUBBLE_RADIUS_M:
            survivors.append(candidate)
    return survivors


def associate(
    classification_raw: str,
    ownship: OwnshipState,
    candidates: Sequence[WorldObjectCandidate],
) -> AssociationResult | None:
    """Resolve one HelperAI detection against `candidates`. See the module
    docstring for the algorithm. Returns `None` when no candidate survives
    the plausibility filter -- the caller (`HybridPerceptionSource`) is
    responsible for dropping the detection in that case rather than
    fabricating placeholder geometry."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)

    survivors: list[tuple[WorldObjectCandidate, float, float]] = []
    for candidate in candidates:
        target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
        candidate_range_m = range_m(observer, target)
        if candidate_range_m > RANGE_CAP_M:
            continue
        candidate_bearing_deg = bearing_deg(observer, target)
        if not _within_forward_hemisphere(
            ownship.heading_true_deg, candidate_bearing_deg
        ):
            continue
        survivors.append((candidate, candidate_bearing_deg, candidate_range_m))

    if not survivors:
        return None

    if len(survivors) == 1:
        candidate, brg, rng = survivors[0]
        return AssociationResult(
            candidate=candidate,
            bearing_deg=brg,
            range_m=rng,
            confidence=CONFIDENT_ASSOCIATION_CONFIDENCE,
            method=CONFIDENT_ASSOCIATION_METHOD,
            ambiguous=False,
        )

    scored = [
        (
            candidate,
            brg,
            rng,
            _type_match_score(classification_raw, candidate.object_type),
        )
        for candidate, brg, rng in survivors
    ]
    scored.sort(key=lambda item: item[3], reverse=True)
    top_score = scored[0][3]
    tied = [item for item in scored if top_score - item[3] <= TYPE_MATCH_TIE_MARGIN]

    if len(tied) == 1:
        candidate, brg, rng, _score = tied[0]
        return AssociationResult(
            candidate=candidate,
            bearing_deg=brg,
            range_m=rng,
            confidence=CONFIDENT_ASSOCIATION_CONFIDENCE,
            method=CONFIDENT_ASSOCIATION_METHOD,
            ambiguous=False,
        )

    nearest_candidate, nearest_brg, nearest_rng, _score = min(
        tied, key=lambda item: item[2]
    )
    return AssociationResult(
        candidate=nearest_candidate,
        bearing_deg=nearest_brg,
        range_m=nearest_rng,
        confidence=AMBIGUOUS_ASSOCIATION_CONFIDENCE,
        method=AMBIGUOUS_ASSOCIATION_METHOD,
        ambiguous=True,
    )


def _within_forward_hemisphere(
    ownship_heading_deg: float, candidate_bearing_deg: float
) -> bool:
    delta = (candidate_bearing_deg - ownship_heading_deg + 180.0) % 360.0 - 180.0
    return abs(delta) <= FORWARD_HEMISPHERE_HALF_WIDTH_DEG


def _keywords(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _type_match_score(classification_raw: str, object_type: str) -> int:
    """Keyword overlap between HelperAI's coarse classification text (e.g.
    `"Slava cruiser"`) and a candidate's DCS unit-type identifier (e.g.
    `"MOSCOW"`). HelperAI's own classification text is drawn from ED's
    reporting-name vocabulary, not the raw `object_type` string -- the two
    are frequently unrelated words (`"Slava cruiser"` vs `"MOSCOW"`,
    `"SA-3 launcher"` vs `"5p73 s-125 ln"`), so scoring against the raw type
    alone silently returns 0 for most non-coincidental cases (see
    `plans/pb2-contact-memory/plan.md` Stage 0, and
    `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-
    detection.md` Finding 6 for the real tuples that surfaced this). Resolve
    `object_type` through `reporting_names.reporting_name_for` and score
    against **both** the raw type and the resolved reporting name, taking
    the max -- so a candidate whose raw type happens to share a keyword
    (e.g. the Ural-truck coincidence) still scores at least as well as
    before, and nothing that matched before this fix regresses."""
    classification_keywords = _keywords(classification_raw)
    raw_score = len(classification_keywords & _keywords(object_type))

    reporting_name = reporting_name_for(object_type)
    if reporting_name is None:
        return raw_score

    reporting_score = len(classification_keywords & _keywords(reporting_name))
    return max(raw_score, reporting_score)
