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

Algorithm (plan's "Association design" section, unchanged here):
1. Candidate pool = every `WorldObjectCandidate` passed in, no coalition/IFF
   filtering (plan decision, `Risks & Unknowns`).
2. Plausibility filter: drop candidates outside `RANGE_CAP_M` or outside
   `FORWARD_HEMISPHERE_HALF_WIDTH_DEG` of ownship's true heading.
3. Type-match scoring: keyword overlap between the detection's
   classification text and each surviving candidate's `object_type`.
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

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from coordinates import wgs84_to_dcs
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.source import OwnshipState

#: Generous optical-detection envelope for a ground vehicle from a
#: helicopter -- not derived from any DCS sensor-range figure (none exists
#: for Petrovich, see the plan's Risks section), a plausibility bound only.
RANGE_CAP_M: Final[float] = 5000.0

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

#: Any candidate within this distance of ownship's own position is treated
#: as the player's own aircraft appearing in its own `LoGetWorldObjects`
#: table, not a distinct object -- `LoGetWorldObjects` is confirmed global,
#: unfiltered ground truth with no own-aircraft exclusion (see
#: `aircraft-layer/src/schema/world_objects.py`'s module docstring, and the
#: forum thread it cites confirming multiplayer returns "data from all
#: devices"). Without this, ownship shows up as a phantom near-zero-range
#: contact (see `plans/pb1.5-naked-eye-detection/debug.md` for the live-
#: sortie symptom this fixes -- pinned-minimum range bucket, meaningless
#: jittery bearing from a near-zero baseline vector, and the unclassified
#: `OP_GROUPSOMETHING` fallback since aircraft types match no keyword).
#: `50.0` m is chosen well above the Mi-24P's own physical extent (~17 m
#: fuselage/rotor span) and any plausible per-tick position residual between
#: `LoGetSelfData` (ownship telemetry) and `LoGetWorldObjects`'s own-aircraft
#: entry, and well below both channels' real range caps (2500-5000 m) so it
#: cannot plausibly suppress a real target.
OWNSHIP_ECHO_EXCLUSION_RADIUS_M: Final[float] = 50.0

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

    @staticmethod
    def from_dict(data: dict[str, Any], *, theatre: str) -> WorldObjectCandidate:
        """Build a candidate from one aircraft-layer `GET /world_objects/latest`
        object dict (`aircraft-layer/src/schema/world_objects.py`'s
        `WorldObjectSample.to_dict` shape), converting its lat/lon to
        DCS-native x/z via world-model's coordinate subsystem -- the one
        seam this module has to a real dependency, kept out of the pure
        `associate()` function below so that function stays fixture-testable
        with plain `WorldObjectCandidate` instances."""
        x, z = wgs84_to_dcs(theatre, float(data["lat_deg"]), float(data["lon_deg"]))
        return WorldObjectCandidate(
            object_id=int(data["object_id"]),
            object_type=str(data["object_type"]),
            x=x,
            z=z,
            alt_m=float(data["altitude_m"]),
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


def exclude_ownship(
    candidates: Sequence[WorldObjectCandidate], ownship: OwnshipState
) -> list[WorldObjectCandidate]:
    """Drop any candidate within `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` of
    ownship's own position -- see that constant's docstring for why this is
    necessary. Both `HybridPerceptionSource` and `NakedEyePerceptionSource`
    call this on their raw `WorldObjectCandidate` list before running their
    own filtering, since both build that list from the same unfiltered
    `LoGetWorldObjects` snapshot."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    return [
        candidate
        for candidate in candidates
        if range_m(
            observer, GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
        )
        > OWNSHIP_ECHO_EXCLUSION_RADIUS_M
    ]


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
    `"Ural truck"`) and a candidate's DCS unit-type identifier (e.g.
    `"Ural-4320"`). **Unvalidated against real multi-object scenes** -- see
    `plans/pb1-perception-logger/plan.md`'s Risks section; this is a
    starting guess, not a validated vocabulary table."""
    return len(_keywords(classification_raw) & _keywords(object_type))
