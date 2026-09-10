"""`find_place_by_name`: text-name -> position lookup over the store --
`plans/bl5-tool-api/plan.md` Decision 2. Nothing in `query/` answers "where
is the place called X" today; `describe_position` only goes the other way
(position -> description). This module is the small, deliberately-simple
addition that unblocks body-layer's `find_place` tool without body-layer
reaching into `store.reader.all_features` directly (that would break the
"go through `query`'s public API" precedent `belief.enrichment` already
established for the world-model seam).

Matching is a case-insensitive substring match over `StoredFeature.name`,
restricted to the same place-bearing kinds `describe_position` already
treats as place-shaped: `settlement`, `named_place`, `airfield`, `navaid`.
Deliberately **not** fuzzy/synonym matching -- "the LZ" or "the ridge to the
west" will not resolve here, only names literally close to a stored
feature's `name` field. See the plan's Risks & Unknowns.
"""

import sqlite3
from dataclasses import dataclass

from store.models import StoredFeature
from store.reader import all_features

#: The same place-bearing kind list `query.describe.describe_position`
#: already treats as place-shaped (settlements, named places, airfields,
#: navaids) -- kept in sync by hand since the two modules answer different
#: questions (position->description vs. name->position) and have no shared
#: constant to import from today.
PLACE_KINDS: list[str] = ["settlement", "named_place", "airfield", "navaid"]

#: Confidence for a case-insensitive exact match vs. a plain substring
#: match -- deliberately simple (no fuzzy/edit-distance scoring), per the
#: plan's Decision 2/Risks note.
_EXACT_MATCH_CONFIDENCE = 1.0
_SUBSTRING_MATCH_CONFIDENCE = 0.6


@dataclass(frozen=True)
class PlaceMatch:
    """One `find_place_by_name` result: a representative point for a
    matched feature (its first geometry vertex for `Point` features, or the
    centroid of its vertices for `LineString`/`Polygon` features -- there is
    no "the" point for a polygon/polyline, so this is a deliberate
    approximation, not a claim of precision) plus enough identity/provenance
    to let a caller report where the answer came from."""

    name: str
    kind: str
    feature_id: int | None
    x: float
    z: float
    confidence: float
    provenance: str


def _representative_point(feature: StoredFeature) -> tuple[float, float]:
    """First vertex for a `Point` feature; centroid (mean of vertices) for
    `LineString`/`Polygon` -- see `PlaceMatch`'s docstring."""
    if feature.geom_type == "Point" or len(feature.geometry) == 1:
        return feature.geometry[0]
    sum_x = sum(point[0] for point in feature.geometry)
    sum_z = sum(point[1] for point in feature.geometry)
    count = len(feature.geometry)
    return sum_x / count, sum_z / count


def _match_confidence(needle: str, name: str) -> float:
    return (
        _EXACT_MATCH_CONFIDENCE
        if name.lower() == needle
        else _SUBSTRING_MATCH_CONFIDENCE
    )


def find_place_by_name(
    conn: sqlite3.Connection,
    text: str,
    kinds: list[str] | None = None,
) -> list[PlaceMatch]:
    """Case-insensitive substring match of `text` against every place-shaped
    feature's `name` in the store (`kinds`, or `PLACE_KINDS` by default).
    Empty/whitespace-only `text` matches nothing rather than returning
    every place, mirroring `belief.tools.find_contact`'s same guard on the
    body-layer side. Unnamed features (`name is None`) never match. Results
    are sorted exact-match-first, then by name, for a deterministic order --
    there is no relevance ranking beyond that (no fuzzy score to sort by)."""
    needle = text.strip().lower()
    if not needle:
        return []

    search_kinds = kinds if kinds is not None else PLACE_KINDS
    candidates = all_features(conn, search_kinds)

    matches: list[PlaceMatch] = []
    for feature in candidates:
        if feature.name is None or needle not in feature.name.lower():
            continue
        x, z = _representative_point(feature)
        matches.append(
            PlaceMatch(
                name=feature.name,
                kind=feature.kind,
                feature_id=feature.id,
                x=x,
                z=z,
                confidence=_match_confidence(needle, feature.name),
                provenance=feature.provenance.get("name")
                or feature.provenance.get("geometry")
                or "unknown",
            )
        )

    matches.sort(key=lambda match: (-match.confidence, match.name.lower()))
    return matches
