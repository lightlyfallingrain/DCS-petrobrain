"""World-enrichment orchestration -- `plans/bl3-world-enrichment/plan.md`.
Fills in `describe_contact`'s still-empty `position.confidence`,
`relative_now`, `semantic`, and `motion_when_seen` fields
(`plans/body-layer/plan.md` §3.4) without touching `belief.contacts.
Contact` or its classification logic (`feature/classification-refinement`
is mid-flight on that exact file; this module has zero shared surface with
it) and without changing `perception.geometry.project_from_bearing_range`
(BL-2's gating primitive).

**Where a contact's terrain-aware world position comes from.** `Contact`
stores `last_position` -- as of `plans/precise-position-belief/plan.md`
Stage 4, the *fused* position `Contact.position` (`belief.position_belief.
PositionEstimate`) resolves to, refined across every look via covariance
fusion, never a single raw percept's own flat projection -- plus the ids of
the observations that contributed to it, never a bearing/range pair. To
feed `perception.geometry.project_terrain_aware` (which needs a fresh
observer/bearing/range, not an already-flattened position),
`_terrain_aware_world_position` below walks `contact.
contributing_observation_ids` back through `ContactStore.observations` (the
same pattern `motion_when_seen` uses) to recover the most recent
contributing `Percept`'s own *observer* position, then derives a fresh
bearing/range pair from that observer *to `contact.last_position`* (the
fused mean) -- never using the percept's own perceived bearing/range
directly, which would silently discard every improvement fusion made since
that one look (Stage 4's own fix for exactly that bug, see that function's
own docstring).

**`SemanticFact.feature_id`.** The plan's prose says to use `StoredFeature.
id`, falling back to a stable `f"{kind}:{id}"` string only when absent.
In practice none of `query.describe.PositionDescription`'s per-field info
dataclasses (`SettlementInfo`, `RoadInfo`, `WaterInfo`, `TerrainLineInfo`)
expose the underlying `StoredFeature.id` at all -- `describe_position`
never threads it through. The fallback string is therefore always used
here, built from each fact's kind plus whatever naming information that
kind's info dataclass does carry (name, or a distance bucket for the
nameless ridge/valley lines) -- not a numeric database id.

**osm-landcover-optimization (Design D7)**: `semantic_facts_for` gains
subtype-aware wording for unnamed settlements/water (world-model's
`SettlementInfo`/`WaterInfo` now carry `subtype`) and two new facts,
appended after the pre-existing ones so `belief.tools`/`belief.speech`'s
`max(..., key=confidence)` selection keeps its current tie-break behaviour
(first maximum wins) unchanged for the current-location phrasing that
already existed: a landcover fact (only when `inside_landcover` is
non-`None` and its class isn't `"built_up"` -- that case is already covered
by `inside_settlement`) and a coast fact (only when `nearest_coastline` is
within `COAST_FACT_RADIUS_M` or already reports `side == "sea"` -- D5's own
risk note that `side` is unreliable *near* the coast is why the wording
hedges to "near the coast" rather than asserting a side in that band, only
asserting "over the sea" once far enough out that the position uncertainty
itself can't explain the `side` reading).

**Contact report fine tuning -- the cheap `enrichment.py` items** (`ROADMAP.
md`, opened 2026-09-18, this pass 2026-09-19). `semantic_facts_for`'s
`"near {label} ({distance}m)"` fact constructions (settlement/road/water)
now go through a shared `_proximity_text(label, distance_m)`
helper: under `_ON_FEATURE_MAX_M` (10 m), `"on {label}"`, no figure; in the
`_NEXT_TO_MIN_M`..`_NEXT_TO_MAX_M` band (10-100 m), `"next to {label}"`, also
no figure. The three bands tile with no gap
-- both replace the bare-distance shape entirely at the range where the fact
of proximity matters more than the number, per the roadmap item. Generic
over `label` (a proper name, or a generic noun phrase like `"a road"`)
rather than road-specific, since the item asks for this wording for any
feature reference. `speech.py`'s own module docstring has the matching
`speech.py`-side items (spelled-out units, acronym respelling).

**`plans/terrain-feature-probing/plan.md` Revision 3, Stage 3a (2026-10-05)
-- the position-qualifier dominance rule.** Ridge/valley no longer go
through `_proximity_text`/`NEAR_FACT_RADIUS_M` at all: against the real
geomorphons output (234,799 lines theatre-wide, ~0.8 ridge lines/km2 at
Baalbek density), *something* of one kind or the other is within any
sensible "near" radius almost everywhere, so a plain nearest-of-each-kind
gate admits essentially always. `_dominant_terrain_kind` (fed from
`PositionDescription.nearby_ridges`/`nearby_valleys`) instead emits **at
most one** of `"on a ridge"`/`"in a valley"`, and only when the nearer kind
is within `TERRAIN_QUALIFIER_MAX_M` **and** nearer than the other kind by at
least `TERRAIN_DOMINANCE_FACTOR` -- Decision 3's rule, verbatim. The default
answer is to name nothing: a contact near both kinds, or far from both,
gets no terrain-position fact at all. See `terrain_divide_qualifier` below
for the separate, ownship-relative *"next valley"*/*"beyond the ridge"*
form (Decision 2/5), which is never computed here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from typing import Final

from belief.association_over_time import implied_position
from belief.contacts import Contact, ContactStore
from belief.decay import position_confidence
from belief.percept import Percept, percept_of
from perception.geometry import (
    GeoPosition,
    bearing_deg,
    project_terrain_aware,
    range_m,
)
from perception.source import OwnshipState
from query.describe import TerrainLineInfo, describe_position
from query.divides import divides_between
from store.reader import nearest_feature

#: The width of naked-eye's own clock-position reporting vocabulary, 30
#: degrees per hour -- moved here from `belief.association_over_time` by
#: `plans/precise-position-belief/plan.md` Stage 1: it is a *speech*
#: vocabulary constant (how a clock position is spoken/read back), not a
#: gating one, and belongs on the reporting side next to `_clock_position`
#: below, which already duplicated it as a literal `30.0`. `belief.
#: optic_policy.LookTarget.bearing_uncertainty_deg`'s default imports this
#: too (`plans/binocular-optic/stage3b.md` D1's "one fact, two honest
#: derivations" reasoning still holds after the move).
CLOCK_BUCKET_DEG: Final[float] = 30.0

#: Slant range within which a contact's terrain-aware position is worth the
#: extra iteration cost (`project_terrain_aware`'s `max_iterations=5`) --
#: below this, or when `Contact.attention == "watch"`, the fixed-point
#: solve is run to convergence; otherwise a single pass
#: (`max_iterations=1`) is used. Placeholder, same status as
#: `perception.hybrid_source.SCOPE_UNCERTAINTY_M` -- tune once a live
#: session shows whether far-but-watched contacts (or close-but-unwatched
#: ones just inside this threshold) get visibly worse position quality than
#: they should.
PROJECTION_ITERATIVE_RANGE_M: Final[float] = 2000.0

#: Number of fixed-point iterations for a "worth the cost" contact (close,
#: or watched) vs. the single-shot default for everything else. See
#: `PROJECTION_ITERATIVE_RANGE_M` above and `perception.geometry.
#: project_terrain_aware`'s own docstring for what an iteration does.
_ITERATIVE_MAX_ITERATIONS: Final[int] = 5
_SINGLE_SHOT_MAX_ITERATIONS: Final[int] = 1

#: World-model's `StoredFeature.confidence` string enum
#: (`"high"`/`"medium"`/`"low"`/`"unknown"`, see `world-model/src/store/
#: models.py`'s docstring and its callers) mapped to a numeric 0-1 value --
#: same "declared and revisitable" status as `perception.hybrid_source.
#: SCOPE_UNCERTAINTY_M`, not a derivation. Combined with a contact's own
#: `position_confidence` (simple product, `_combined_confidence` below) to
#: produce `SemanticFact.confidence` -- both the mapping and the
#: combination formula are first-guess placeholders (see the plan's Risks
#: & Unknowns).
_FEATURE_CONFIDENCE_NUMERIC: dict[str, float] = {
    "high": 1.0,
    "medium": 0.7,
    "low": 0.4,
    "unknown": 0.2,
}

#: `world-model`'s `WaterInfo.subtype` (river/lake/reservoir/river_area)
#: mapped to a semantic-fact noun phrase for an *unnamed* water feature
#: (D7 "near a river|lake|reservoir (Nm)"). `river_area` (the polygon
#: variant of a mapped river, D2 "Areas" rule 1) reads the same as `river`
#: -- there is no separate natural-language distinction worth making here.
_WATER_SUBTYPE_LABELS: dict[str, str] = {
    "river": "a river",
    "lake": "a lake",
    "reservoir": "a reservoir",
    "river_area": "a river",
}

#: `world-model`'s `LandcoverInfo.landcover_class` mapped to the D7 fact
#: text -- `"built_up"` deliberately excluded (already covered by
#: `inside_settlement`, D7's own note).
_LANDCOVER_CLASS_TEXTS: dict[str, str] = {
    "forest": "in forest",
    "orchard": "in orchards",
    "scrub": "in scrubland",
    "fields": "in open fields",
    "barren": "on barren ground",
}

#: How close `nearest_coastline` must be for a coast fact to fire at all,
#: when `side` isn't already `"sea"` (D7). Named the way the plan itself
#: names it, not a private `_`-prefixed constant, since it is the one new
#: D7 knob a caller might reasonably want to see/tune.
COAST_FACT_RADIUS_M: Final[float] = 5000.0

#: Maximum distance at which a "near X" landmark fact is worth stating, per
#: feature kind. Without this, `describe_position` returns the *nearest*
#: feature of each kind regardless of how far it is, and the crew hears
#: "near Wadi Hamer (~28700m)" -- 28.7 km is not near anything (observed
#: live, 2026-09-18).
#:
#: **Keyed by kind because the useful radius genuinely differs by what the
#: landmark is** (user direction, 2026-09-18): a road is a tighter
#: reference than a village, which is tighter than a mountain or a lake --
#: you can be 5 km from a mountain and still sensibly be "near" it, but 5 km
#: from a road means the road tells you nothing about where you are. Those
#: distinctions are not calibrated yet, so **every kind is 1000 m for now**,
#: deliberately: one honest placeholder beats five invented numbers. The
#: table exists so differentiating them later is an edit, not a refactor.
#:
#: `COAST_FACT_RADIUS_M` above is deliberately *not* folded in here: the
#: coast fact makes a different claim ("which side of the coastline are we
#: on"), which stays meaningful much further out than a landmark reference
#: does, and its radius was chosen for that reason.
NEAR_FACT_RADIUS_M: Final[dict[str, float]] = {
    "settlement": 1000.0,
    "road": 1000.0,
    "water": 1000.0,
}


def _within_near_radius(kind: str, distance_m: float) -> bool:
    """Whether a `near X` fact of this kind is close enough to be worth
    saying. An unknown kind is admitted rather than dropped -- a missing
    table entry should degrade to today's ungated behaviour, not silently
    mute a whole class of fact."""
    return distance_m <= NEAR_FACT_RADIUS_M.get(kind, float("inf"))


#: Decision 3 (`plans/terrain-feature-probing/plan.md` Revision 3) -- the
#: nearer of {nearest ridge, nearest valley} must be within this distance
#: for a position qualifier to be worth saying at all. First guess, "under a
#: third of the median line length" (~1 km at theatre average): beyond this,
#: at the real geomorphons line density, the nearest line is noise rather
#: than a feature the contact is meaningfully next to. Tune by flying, same
#: status as `DIVIDE_MERGE_M` in `query.divides`.
TERRAIN_QUALIFIER_MAX_M: Final[float] = 300.0

#: Decision 3 -- the nearer kind must beat the other kind by at least this
#: factor (nearer-kind distance * this <= other-kind distance) or neither is
#: named. Without this, a contact sitting between a ridge and a valley at
#: similar distances would arbitrarily pick whichever is a metre closer.
#: First guess, tune by flying.
TERRAIN_DOMINANCE_FACTOR: Final[float] = 2.0

#: Decision 5's fixed phrasing for the position-qualifier fact -- no
#: trailing distance figure (unlike `_proximity_text`'s "near X (Nm)"
#: shape): once `_dominant_terrain_kind` has fired, the exact distance adds
#: nothing a pilot would want read back.
_TERRAIN_POSITION_TEXT: Final[dict[str, str]] = {
    "ridge": "on a ridge",
    "valley": "in a valley",
}


def _dominant_terrain_kind_from_distances(
    ridge_distance_m: float | None, valley_distance_m: float | None
) -> str | None:
    """Decision 3's dominance rule, operating on bare distances so both
    `_dominant_terrain_kind` below (fed `TerrainLineInfo.distance_m` from a
    `describe_position` call already made) and `terrain_divide_qualifier`
    (fed a direct `nearest_feature` distance, to avoid a second full
    `describe_position` call at the target) can share one rule. A missing
    kind (`None`) is treated as infinitely far, not excluded from the
    comparison -- a lone nearby ridge with no valley feature in range still
    needs to clear the distance gate, which it does trivially since nothing
    closer exists to contest it."""
    if ridge_distance_m is None and valley_distance_m is None:
        return None
    near_kind, near_d = min(
        (("ridge", ridge_distance_m), ("valley", valley_distance_m)),
        key=lambda c: c[1] if c[1] is not None else float("inf"),
    )
    other_d = valley_distance_m if near_kind == "ridge" else ridge_distance_m
    if near_d is None or near_d > TERRAIN_QUALIFIER_MAX_M:
        return None
    if other_d is not None and other_d < near_d * TERRAIN_DOMINANCE_FACTOR:
        return None
    return near_kind


def _dominant_terrain_kind(
    ridge: TerrainLineInfo | None, valley: TerrainLineInfo | None
) -> str | None:
    """`description.nearby_ridges`/`nearby_valleys` -> the one dominant kind
    worth a position-qualifier fact, or `None` -- see
    `_dominant_terrain_kind_from_distances` for the rule itself."""
    return _dominant_terrain_kind_from_distances(
        ridge.distance_m if ridge is not None else None,
        valley.distance_m if valley is not None else None,
    )


#: At or below this distance, a feature reference reads as "on {label}"
#: rather than "near {label} (Nm)" -- 2026-09-19 roadmap item: at zero
#: distance the exact figure is meaningless (there is nothing left to
#: measure), so the wording drops it entirely rather than saying "near a
#: road (0m)".
#:
#: **Raised 0.5 -> 10 m (user, 2026-09-19: "<10m from road -> on road").**
#: The first pass read the item's "0 m" literally and used a float-noise
#: epsilon, which left an unworded 0.5-10 m gap falling through to
#: "near a road (~4 metres)" -- absurd phrasing for something a crew member
#: would simply call *on* the road. The user's threshold is the honest one:
#: within ten metres of a linear feature you are on it, not near it, and no
#: eye resolves the difference anyway.
_ON_FEATURE_MAX_M: Final[float] = 10.0

#: The "next to {label}" band -- 10 to 100 m, per the same roadmap item:
#: close enough that "near ... (Nm)" undersells how close this is, too far
#: to say "on" it. `_NEXT_TO_MIN_M` meets `_ON_FEATURE_MAX_M` exactly, so
#: the three bands tile the range with no gap; the earlier version left one
#: and it produced nonsense at its bottom end.
_NEXT_TO_MIN_M: Final[float] = 10.0
_NEXT_TO_MAX_M: Final[float] = 100.0


def _proximity_text(label: str, distance_m: float) -> str:
    """Distance-based feature-reference wording, shared by every "near X"
    fact `semantic_facts_for` builds (settlement/road/water -- ridge/valley
    moved off this helper entirely in `plans/terrain-feature-probing/
    plan.md` Revision 3, Stage 3a, onto the fixed `_TERRAIN_POSITION_TEXT`
    phrasing below instead) -- generic over `label` rather than
    road-specific, since the roadmap item asks for "on"/"next to" wording
    for any feature reference, not just roads. `label` is the same string
    each call site already built for the pre-existing "near {label} (Nm)"
    shape (a proper name, or a generic noun phrase like `"a road"`), so
    `"on a road"`/`"next to a road"` is what an unnamed feature gets --
    grammar polish beyond that (swapping the article for "the") is exactly
    the class of fine tuning `speech.py`'s 2026-09-19 standing rule keeps
    out of scope.

    Below `_ON_FEATURE_MAX_M`: `"on {label}"`, no distance figure (there is
    nothing left to measure). Within the `_NEXT_TO_MIN_M`.._NEXT_TO_MAX_M
    band: `"next to {label}"`, also no figure -- both replace the bare-number
    shape at the distance where the *fact* of proximity matters more than
    the number (this is a wording decision made once, here, rather than
    `speech.py`'s `_round_enrichment_fragment` continuing to round a figure
    these two cases no longer carry at all). Otherwise, the pre-existing
    `"near {label} ({distance}m)"` shape, unchanged -- `speech.py` still
    rounds/spells that figure for TTS at render time."""
    if distance_m < _ON_FEATURE_MAX_M:
        return f"on {label}"
    if _NEXT_TO_MIN_M <= distance_m < _NEXT_TO_MAX_M:
        return f"next to {label}"
    return f"near {label} ({distance_m:.0f}m)"


def displayable_name(name: str | None) -> str | None:
    """`name` if it can be shown and spoken, otherwise `None` so the caller
    falls back to a generic label ("a village", "a wadi").

    **DCS cannot render non-Latin-1 text in its overlay**, so a Syrian
    place name in Arabic script arrives in the cockpit as blanks or boxes
    (observed live, 2026-09-18) -- and a TTS voice reading English would
    make nothing useful of it either. Dropping to the generic label is the
    honest degradation: "near a wadi" is true, readable and speakable,
    where the original name is none of those things on this display.

    Not transliteration, deliberately. Romanising Arabic properly needs a
    library this project's stdlib-only rule does not admit, and a crude
    character-map transliteration produces names no map agrees with, which
    is worse than no name at all.

    **The upstream half shipped as `WM-B1` (2026-10-02):**
    `world-model`'s `build.ingest_osm._select_name` now prefers OSM's
    `name:en`, then `int_name`, then `name`, accepting a candidate only if
    it actually encodes to Latin-1 -- the same test this function applies,
    deliberately duplicated rather than imported, because `body-layer` may
    import `world-model` but not the reverse (root `CLAUDE.md`, "Module
    independence"). **Keep the two in sync by hand**; if they diverge, a
    name accepted at ingest is still dropped here, which looks like the
    fix not working.

    This guard stays, and still earns its place: measured on the real
    store, 40% of named places held an unrenderable name and only 67% of
    those had a usable romanisation available, so roughly a third still
    arrive here needing the generic label."""
    if name is None:
        return None
    try:
        name.encode("latin-1")
    except UnicodeEncodeError:
        return None
    return name


@dataclass(frozen=True, slots=True)
class SemanticFact:
    """One world-model place reference near a contact's (terrain-aware)
    position. `confidence` already folds in the contact's own
    `belief.decay.position_confidence` -- a consumer does not need to
    separately discount a stale contact's semantic facts."""

    text: str
    confidence: float
    provenance: str
    feature_id: str


def _combined_confidence(feature_confidence: str, position_conf: float) -> float:
    numeric = _FEATURE_CONFIDENCE_NUMERIC.get(
        feature_confidence, _FEATURE_CONFIDENCE_NUMERIC["unknown"]
    )
    return numeric * position_conf


def _unnamed_settlement_label(subtype: str | None) -> str:
    """D7: an unnamed built-up settlement reads as "a built-up area";
    anything else unnamed keeps the pre-D7 generic wording."""
    if subtype == "built_up":
        return "a built-up area"
    return "an unnamed settlement"


def _unnamed_water_label(subtype: str | None) -> str:
    """D7: "near a river|lake|reservoir (Nm)" from `subtype` for unnamed
    water; the pre-D7 generic "water" wording is the fallback for a
    `subtype` this table doesn't recognize (e.g. an older/foreign store
    row)."""
    if subtype is not None and subtype in _WATER_SUBTYPE_LABELS:
        return _WATER_SUBTYPE_LABELS[subtype]
    return "water"


def semantic_facts_for(
    conn: sqlite3.Connection,
    theatre: str,
    position: GeoPosition,
    position_conf: float,
) -> list[SemanticFact]:
    """Flatten `query.describe.describe_position`'s
    `nearest_settlement`/`inside_settlement`/`nearest_road`/`nearest_water`/
    `nearby_ridges`/`nearby_valleys`/`inside_landcover`/`nearest_coastline`
    fields into a list of `SemanticFact`s, one call to `describe_position`.
    Absent facts stay absent -- a `None` field on `PositionDescription`
    simply does not produce a `SemanticFact`, same "absent, not null" rule
    `belief.tools` already documents. The two osm-landcover-optimization
    facts (landcover, coast) are appended after every pre-existing one --
    see the module docstring's D7 status note on why order matters here."""
    description = describe_position(conn, theatre, position.x, position.z)
    facts: list[SemanticFact] = []

    settlement = description.nearest_settlement
    if settlement is not None and _within_near_radius(
        "settlement", settlement.distance_m
    ):
        name = displayable_name(settlement.name) or _unnamed_settlement_label(
            settlement.subtype
        )
        facts.append(
            SemanticFact(
                text=_proximity_text(name, settlement.distance_m),
                confidence=_combined_confidence(settlement.confidence, position_conf),
                provenance=settlement.provenance,
                feature_id=f"settlement:{settlement.name or 'unnamed'}",
            )
        )

    inside = description.inside_settlement
    if inside is not None:
        name = displayable_name(inside.name) or _unnamed_settlement_label(
            inside.subtype
        )
        facts.append(
            SemanticFact(
                text=f"inside {name}",
                confidence=_combined_confidence(inside.confidence, position_conf),
                provenance=inside.provenance,
                feature_id=f"inside_settlement:{inside.name or 'unnamed'}",
            )
        )

    road = description.nearest_road
    if road is not None and _within_near_radius("road", road.distance_m):
        label = displayable_name(road.name) or road.subtype or "a road"
        facts.append(
            SemanticFact(
                text=_proximity_text(label, road.distance_m),
                confidence=_combined_confidence(road.confidence, position_conf),
                provenance=road.provenance,
                feature_id=f"road:{road.name or road.subtype or 'unnamed'}",
            )
        )

    water = description.nearest_water
    if water is not None and _within_near_radius("water", water.distance_m):
        name = displayable_name(water.name) or _unnamed_water_label(water.subtype)
        facts.append(
            SemanticFact(
                text=_proximity_text(name, water.distance_m),
                confidence=_combined_confidence(water.confidence, position_conf),
                provenance=water.provenance,
                feature_id=f"water:{water.name or 'unnamed'}",
            )
        )

    dominant_terrain = _dominant_terrain_kind(
        description.nearby_ridges, description.nearby_valleys
    )
    if dominant_terrain is not None:
        terrain_info = (
            description.nearby_ridges
            if dominant_terrain == "ridge"
            else description.nearby_valleys
        )
        assert terrain_info is not None
        facts.append(
            SemanticFact(
                text=_TERRAIN_POSITION_TEXT[dominant_terrain],
                confidence=_combined_confidence(terrain_info.confidence, position_conf),
                provenance=terrain_info.provenance,
                feature_id=f"{dominant_terrain}:{round(terrain_info.distance_m / 100.0) * 100}",
            )
        )

    landcover = description.inside_landcover
    if landcover is not None and landcover.landcover_class != "built_up":
        text = _LANDCOVER_CLASS_TEXTS.get(landcover.landcover_class)
        if text is not None:
            facts.append(
                SemanticFact(
                    text=text,
                    confidence=_combined_confidence(
                        landcover.confidence, position_conf
                    ),
                    provenance=landcover.provenance,
                    feature_id=f"landcover:{landcover.landcover_class}",
                )
            )

    coastline = description.nearest_coastline
    if coastline is not None and (
        coastline.distance_m <= COAST_FACT_RADIUS_M or coastline.side == "sea"
    ):
        if (
            coastline.side == "sea"
            and coastline.distance_m >= coastline.position_uncertainty_m
        ):
            text = f"over the sea, off the coast ({coastline.distance_m:.0f}m)"
        else:
            text = f"near the coast ({coastline.distance_m:.0f}m)"
        facts.append(
            SemanticFact(
                text=text,
                confidence=_combined_confidence(coastline.confidence, position_conf),
                provenance=coastline.provenance,
                feature_id="coastline",
            )
        )

    return facts


def _recent_percepts(store: ContactStore, contact: Contact) -> list[Percept]:
    """`contact.contributing_observation_ids` resolved back to `Percept`s
    via `store.observations`, most recent first. Shared by
    `_terrain_aware_world_position` (wants only the latest) and
    `motion_when_seen` (wants the two most recent distinct positions)."""
    observations = store.observations
    percepts: list[Percept] = []
    for observation_id in reversed(contact.contributing_observation_ids):
        observation = observations.get(observation_id)
        if observation is not None:
            percepts.append(percept_of(observation))
    return percepts


def _terrain_aware_world_position(
    conn: sqlite3.Connection,
    theatre: str,
    store: ContactStore,
    contact: Contact,
) -> GeoPosition:
    """`contact.last_position`'s terrain-aware counterpart.

    **Reprojects the contact's *fused* believed position, not the last
    contributing percept's own raw bearing/range** (`plans/
    precise-position-belief/plan.md` Stage 4 -- a real bug this plan's own
    Risks section named: `Contact.last_position` is now `Contact.position`'s
    covariance-fused mean, refined across every look, but this function used
    to walk back to the single most recent `Percept` and reproject *its*
    bearing/range instead, so every semantic fact and terrain-aware position
    silently kept using one raw look while the fused estimate improved
    invisibly beside it -- unit tests on the fusion itself would all still
    pass, since none of them render a report). The fix: derive a fresh
    bearing/range pair from the most recent percept's own observer position
    *to `contact.last_position`* (the fused mean), instead of using that
    percept's own perceived bearing/range directly -- `project_terrain_
    aware`'s fixed-point terrain solve still needs *some* observer/bearing/
    range triple to iterate from (see that function's own docstring), and
    the most recent look's observer is the most reasonable vantage point to
    iterate from, but the *target* fed into it is always the fused position
    now, never the raw look.

    Only the observer (for the fixed-point solve's starting point) and the
    iteration-count policy (`PROJECTION_ITERATIVE_RANGE_M`, watched-contact
    override) still come from the most recent contributing `Percept` --
    falls back to `contact.last_position` unchanged (already the flat
    projection) if no contributing observation is still in the log."""
    percepts = _recent_percepts(store, contact)
    if not percepts:
        return contact.last_position
    percept = percepts[0]

    observer = GeoPosition(
        x=percept.ownship_at_observation.x,
        z=percept.ownship_at_observation.z,
        alt_m=percept.ownship_at_observation.alt_m,
    )
    target = contact.last_position
    look_bearing_deg = bearing_deg(observer, target)
    look_range_m = range_m(observer, target)

    max_iterations = (
        _ITERATIVE_MAX_ITERATIONS
        if (
            look_range_m <= PROJECTION_ITERATIVE_RANGE_M or contact.attention == "watch"
        )
        else _SINGLE_SHOT_MAX_ITERATIONS
    )
    return project_terrain_aware(
        conn,
        theatre,
        observer,
        look_bearing_deg,
        look_range_m,
        max_iterations=max_iterations,
    )


@dataclass
class WorldEnrichmentCache:
    """Per-contact cache of `(last known Contact.last_position, terrain-aware
    world position, semantic facts)`, keyed by `contact_id` -- the
    "semantic caching" the milestone brief names. Deliberately lives outside
    `belief.contacts.Contact` (not a new field on it) to keep zero shared
    surface with `feature/classification-refinement`'s in-flight changes to
    that file.

    A cache hit requires `Contact.last_position` (structural equality --
    `GeoPosition` is a frozen dataclass) to still match what was cached;
    any change recomputes both the world position and the semantic facts.
    Note that the *confidence* numbers inside a cached `SemanticFact` list
    are only as fresh as the last recompute -- they do not re-decay between
    cache hits, a deliberate perf/staleness tradeoff (see the plan's Risks
    & Unknowns on cache hit rate)."""

    _cache: dict[str, tuple[GeoPosition, GeoPosition, list[SemanticFact]]] = field(
        default_factory=dict
    )

    def get_or_compute(
        self,
        conn: sqlite3.Connection,
        theatre: str,
        store: ContactStore,
        contact: Contact,
        now_sim: float,
    ) -> tuple[GeoPosition, list[SemanticFact]]:
        cached = self._cache.get(contact.id)
        if cached is not None and cached[0] == contact.last_position:
            return cached[1], cached[2]

        world_position = _terrain_aware_world_position(conn, theatre, store, contact)
        position_conf = position_confidence(contact, now_sim)
        facts = semantic_facts_for(conn, theatre, world_position, position_conf)
        self._cache[contact.id] = (contact.last_position, world_position, facts)
        return world_position, facts


def _clock_position(relative_bearing_deg: float) -> int:
    """A true bearing relative to ownship heading, in `[0, 360)`, mapped to
    a 1-12 clock position (`12` dead ahead)."""
    clock = round(relative_bearing_deg / CLOCK_BUCKET_DEG) % 12
    return 12 if clock == 0 else clock


def relative_geometry(ownship: OwnshipState, target: GeoPosition) -> dict[str, object]:
    """Live ownship-relative geometry to `target` -- bearing/range (reusing
    `perception.geometry.bearing_deg`/`range_m`), a clock position relative
    to ownship's current heading, and relative altitude. **Never cached**
    (unlike `WorldEnrichmentCache` above): ownship moves every poll even
    when a contact's belief position does not, so this must be recomputed
    on every call."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    true_bearing_deg = bearing_deg(observer, target)
    relative_bearing_deg = (true_bearing_deg - ownship.heading_true_deg) % 360.0
    return {
        "bearing_deg": true_bearing_deg,
        "range_m": range_m(observer, target),
        "clock_position": _clock_position(relative_bearing_deg),
        "relative_alt_m": target.alt_m - ownship.alt_m,
    }


def terrain_divide_qualifier(
    conn: sqlite3.Connection,
    theatre: str,
    ownship: OwnshipState,
    target: GeoPosition,
) -> str | None:
    """Decision 2/5's divide-relative qualifier (`plans/
    terrain-feature-probing/plan.md` Revision 3) -- *"next valley"*/
    *"beyond the ridge"*, or `None` when the pilot's phrase would not mean
    anything (0 or >=2 ridge crossings between `ownship` and `target`).

    **Ownship-relative, so never cached in `WorldEnrichmentCache`**
    (Decision 1) -- call this directly from the uncached contact-report
    build path (`belief.tools._add_enrichment_facts`), the exact place
    `relative_geometry` above already lives and for the identical reason:
    `ownship` moves every poll even when the target's believed position
    does not, so a cached divide count would go stale mid-flight and
    produce a confidently wrong "next valley".

    When exactly one divide fires, the wording is picked by whether the
    *target* itself sits in a dominant valley (`_dominant_terrain_kind_
    from_distances`, Decision 3's rule, evaluated at the target): valley
    dominant -> `"next valley"`; anything else (ridge dominant, or no
    dominant form at all) -> the generic `"beyond the ridge"`, since
    "next valley" would overclaim exactly where the contact is relative to
    the ridge it crossed.

    Deliberately queries `store.reader.nearest_feature` directly for
    `["ridge"]`/`["valley"]` at the target, rather than a second full
    `query.describe.describe_position` call -- the dominance test only
    needs the two distances, and a full `describe_position` call also
    joins settlement/road/water/etc. this caller has no use for (see
    `query.describe`'s own module docstring on why `query.line_of_sight`
    avoids `describe_position` for the same reason)."""
    divide_count = divides_between(
        conn, theatre, (ownship.x, ownship.z), (target.x, target.z)
    )
    if divide_count != 1:
        return None
    ridge_match = nearest_feature(conn, ["ridge"], target.x, target.z)
    valley_match = nearest_feature(conn, ["valley"], target.x, target.z)
    dominant = _dominant_terrain_kind_from_distances(
        ridge_match[1] if ridge_match is not None else None,
        valley_match[1] if valley_match is not None else None,
    )
    return "next valley" if dominant == "valley" else "beyond the ridge"


def motion_when_seen(store: ContactStore, contact: Contact) -> dict[str, object] | None:
    """Direction (and, where elapsed time allows, speed) derived from the
    two most recent *distinct* implied positions among `contact`'s
    contributing observations -- walks `contact.contributing_observation_ids`
    back through `store.observations` the same way
    `_terrain_aware_world_position` does, reusing `belief.
    association_over_time.implied_position` (the same flat bearing/range
    projection `Contact.record` itself uses) for each percept's position.
    Returns `None` (key omitted entirely by the caller, per the
    absent-not-null rule) when fewer than two distinct positions exist,
    e.g. a brand-new contact.

    No smoothing/averaging -- a single noisy percept can flip the reported
    direction. Documented as a known weakness (the plan's Risks &
    Unknowns), not fixed here; smoothing is a natural BL-4 refinement."""
    distinct: list[tuple[GeoPosition, float]] = []
    for percept in _recent_percepts(store, contact):
        position = implied_position(percept)
        if not distinct or distinct[-1][0] != position:
            distinct.append((position, percept.t_sim))
        if len(distinct) == 2:
            break

    if len(distinct) < 2:
        return None

    (newer_position, newer_t_sim), (older_position, older_t_sim) = distinct
    result: dict[str, object] = {
        "direction_deg": bearing_deg(older_position, newer_position)
    }
    elapsed_s = abs(newer_t_sim - older_t_sim)
    if elapsed_s > 0:
        result["speed_mps"] = range_m(older_position, newer_position) / elapsed_s
    return result


@dataclass
class EnrichmentContext:
    """Everything `belief.tools`' enrichment-aware functions need beyond
    what they already take: the world-model connection/theatre (the
    in-process seam, `body-layer/CLAUDE.md`'s "World-model seam"), the
    *current* ownship position (for `relative_geometry`, which is never
    cached), and a `WorldEnrichmentCache`. Built once per live session by
    `logger.ConsolePerceptionRunner` and updated in place each poll
    (`ownship` is mutable, not replaced) rather than reconstructed --
    `cache` must persist across polls for caching to do anything."""

    conn: sqlite3.Connection
    theatre: str
    ownship: OwnshipState
    cache: WorldEnrichmentCache = field(default_factory=WorldEnrichmentCache)
