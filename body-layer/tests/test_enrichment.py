"""Tests for `belief.enrichment` -- `plans/bl3-world-enrichment/plan.md`.
World-model calls (`describe_position`) and the terrain-aware projection
(`perception.geometry.project_terrain_aware`) are monkeypatched, same
posture as `test_geometry.py`'s own LOS tests: this module is about the
semantic-mapping/caching/motion-derivation logic, not world-model's store
internals or the terrain fixed-point solve (covered by `test_geometry.py`).
No live DCS/world-model build required."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from belief import enrichment
from belief.contacts import ContactStore
from belief.enrichment import (
    NEAR_FACT_RADIUS_M,
    SemanticFact,
    WorldEnrichmentCache,
    _proximity_text,
    _within_near_radius,
    displayable_name,
    motion_when_seen,
    relative_geometry,
    semantic_facts_for,
)
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState

_FAKE_CONN = sqlite3.connect(":memory:")


def _ownship(
    x: float = 0.0, z: float = 0.0, alt_m: float = 500.0, heading_true_deg: float = 0.0
) -> OwnshipState:
    return OwnshipState(
        t_sim=0.0, x=x, z=z, alt_m=alt_m, heading_true_deg=heading_true_deg
    )


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    bearing_deg: float = 0.0,
    range_m: float = 1000.0,
    classification_raw: str = "Ural truck",
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
    )


# --- semantic_facts_for -----------------------------------------------


@dataclass
class _FakeInfo:
    name: str | None = None
    subtype: str | None = None
    distance_m: float = 100.0
    provenance: str = "osm"
    confidence: str = "high"


@dataclass
class _FakeLandcoverInfo:
    landcover_class: str = "forest"
    name: str | None = None
    provenance: str = "osm"
    confidence: str = "high"
    position_uncertainty_m: float = 1300.0


@dataclass
class _FakeCoastlineInfo:
    distance_m: float = 100.0
    side: str = "land"
    provenance: str = "osm"
    confidence: str = "high"
    position_uncertainty_m: float = 1300.0


@dataclass
class _FakeDescription:
    nearest_settlement: _FakeInfo | None = None
    inside_settlement: _FakeInfo | None = None
    nearest_road: _FakeInfo | None = None
    nearest_water: _FakeInfo | None = None
    nearby_ridges: _FakeInfo | None = None
    nearby_valleys: _FakeInfo | None = None
    inside_landcover: _FakeLandcoverInfo | None = None
    nearest_coastline: _FakeCoastlineInfo | None = None


def test_semantic_facts_for_empty_description_returns_no_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )
    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )
    assert facts == []


def test_semantic_facts_for_includes_every_present_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_settlement=_FakeInfo(name="Jableh", distance_m=500.0),
        inside_settlement=_FakeInfo(name="Jableh"),
        nearest_road=_FakeInfo(name="Route 1", subtype="highway", distance_m=50.0),
        # 700 m, not 2 km: this fixture exists to prove every field yields a
        # fact, so each feature has to sit inside NEAR_FACT_RADIUS_M. The
        # gating itself is tested separately below.
        nearest_water=_FakeInfo(name="Mediterranean Sea", distance_m=700.0),
        nearby_ridges=_FakeInfo(distance_m=800.0),
        nearby_valleys=_FakeInfo(distance_m=900.0),
        inside_landcover=_FakeLandcoverInfo(landcover_class="forest"),
        nearest_coastline=_FakeCoastlineInfo(distance_m=300.0, side="land"),
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )

    assert len(facts) == 8
    assert all(isinstance(fact, SemanticFact) for fact in facts)
    texts = [fact.text for fact in facts]
    assert any("Jableh" in text and "near" in text for text in texts)
    assert any("inside Jableh" == text for text in texts)
    assert any("Route 1" in text for text in texts)
    assert any("Mediterranean Sea" in text for text in texts)
    assert any("ridge" in text for text in texts)
    assert any("valley" in text for text in texts)
    assert any("in forest" == text for text in texts)
    assert any("near the coast" in text for text in texts)
    # D7: the two new facts are appended after every pre-existing one.
    assert facts[-2].feature_id == "landcover:forest"
    assert facts[-1].feature_id == "coastline"


def test_semantic_facts_for_confidence_combines_feature_and_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_settlement=_FakeInfo(name="Jableh", confidence="high")
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    high_position_conf = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]
    low_position_conf = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 0.5
    )[0]

    assert high_position_conf.confidence == pytest.approx(1.0)
    assert low_position_conf.confidence == pytest.approx(0.5)


def test_semantic_facts_for_unknown_confidence_string_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_settlement=_FakeInfo(name="Jableh", confidence="some_future_value")
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    fact = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]

    assert fact.confidence == pytest.approx(0.2)  # "unknown" bucket


def test_semantic_facts_for_unnamed_settlement_uses_placeholder_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(nearest_settlement=_FakeInfo(name=None))
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    fact = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]

    assert "unnamed" in fact.text
    assert fact.feature_id == "settlement:unnamed"


# --- D7: subtype-aware unnamed wording -----------------------------------


def test_semantic_facts_for_unnamed_built_up_settlement_says_built_up_area(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_settlement=_FakeInfo(name=None, subtype="built_up", distance_m=250.0),
        inside_settlement=_FakeInfo(name=None, subtype="built_up"),
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )

    assert facts[0].text == "near a built-up area (250m)"
    assert facts[1].text == "inside a built-up area"


@pytest.mark.parametrize(
    ("subtype", "expected_label"),
    [
        ("river", "a river"),
        ("lake", "a lake"),
        ("reservoir", "a reservoir"),
        ("river_area", "a river"),
    ],
)
def test_semantic_facts_for_unnamed_water_uses_subtype_label(
    monkeypatch: pytest.MonkeyPatch, subtype: str, expected_label: str
) -> None:
    description = _FakeDescription(
        nearest_water=_FakeInfo(name=None, subtype=subtype, distance_m=400.0)
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    fact = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]

    assert fact.text == f"near {expected_label} (400m)"


def test_semantic_facts_for_unnamed_water_unknown_subtype_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_water=_FakeInfo(name=None, subtype=None, distance_m=400.0)
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    fact = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]

    assert fact.text == "near water (400m)"


# --- D7: landcover fact ---------------------------------------------------


@pytest.mark.parametrize(
    ("landcover_class", "expected_text"),
    [
        ("forest", "in forest"),
        ("orchard", "in orchards"),
        ("scrub", "in scrubland"),
        ("fields", "in open fields"),
        ("barren", "on barren ground"),
    ],
)
def test_semantic_facts_for_landcover_class_texts(
    monkeypatch: pytest.MonkeyPatch, landcover_class: str, expected_text: str
) -> None:
    description = _FakeDescription(
        inside_landcover=_FakeLandcoverInfo(landcover_class=landcover_class)
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )

    assert len(facts) == 1
    assert facts[0].text == expected_text
    assert facts[0].feature_id == f"landcover:{landcover_class}"


def test_semantic_facts_for_landcover_built_up_class_produces_no_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D7: `built_up` is deliberately excluded -- `inside_settlement` already
    covers it, so a second fact would be redundant."""
    description = _FakeDescription(
        inside_landcover=_FakeLandcoverInfo(landcover_class="built_up")
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )

    assert facts == []


def test_semantic_facts_for_no_landcover_produces_no_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )

    assert facts == []


# --- D7: coast fact ---------------------------------------------------


def test_semantic_facts_for_coast_far_at_sea_says_over_the_sea(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_coastline=_FakeCoastlineInfo(
            distance_m=5000.0, side="sea", position_uncertainty_m=1300.0
        )
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    fact = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]

    assert fact.text == "over the sea, off the coast (5000m)"
    assert fact.feature_id == "coastline"


def test_semantic_facts_for_coast_sea_within_uncertainty_hedges_to_near_coast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D5's own risk note: `side` is unreliable within `position_uncertainty_m`
    of the coastline, so even a `side == "sea"` reading that close hedges to
    "near the coast" rather than asserting "over the sea"."""
    description = _FakeDescription(
        nearest_coastline=_FakeCoastlineInfo(
            distance_m=500.0, side="sea", position_uncertainty_m=1300.0
        )
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    fact = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]

    assert fact.text == "near the coast (500m)"


def test_semantic_facts_for_coast_land_within_radius_says_near_coast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_coastline=_FakeCoastlineInfo(distance_m=1000.0, side="land")
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    fact = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )[0]

    assert fact.text == "near the coast (1000m)"


def test_semantic_facts_for_coast_land_beyond_radius_produces_no_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_coastline=_FakeCoastlineInfo(distance_m=6000.0, side="land")
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )

    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )

    assert facts == []


def test_semantic_facts_for_no_coastline_produces_no_fact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )

    assert facts == []


# --- WorldEnrichmentCache -----------------------------------------------


def _store_with_one_contact() -> tuple[ContactStore, str]:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    return store, contact_id


def test_cache_miss_on_first_lookup_computes_and_stores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_project_terrain_aware(
        conn: sqlite3.Connection,
        theatre: str,
        observer: GeoPosition,
        bearing: float,
        rng: float,
        *,
        max_iterations: int,
    ) -> GeoPosition:
        calls.append(max_iterations)
        return GeoPosition(x=observer.x + rng, z=observer.z, alt_m=observer.alt_m)

    monkeypatch.setattr(enrichment, "project_terrain_aware", fake_project_terrain_aware)
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    store, _contact_id = _store_with_one_contact()
    contact = store.contacts[0]
    cache = WorldEnrichmentCache()

    world_position, facts = cache.get_or_compute(
        _FAKE_CONN, "Syria", store, contact, now_sim=0.0
    )

    assert len(calls) == 1
    assert facts == []
    assert world_position.x == pytest.approx(1000.0)


def test_cache_hit_when_last_position_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_project_terrain_aware(
        conn: sqlite3.Connection,
        theatre: str,
        observer: GeoPosition,
        bearing: float,
        rng: float,
        *,
        max_iterations: int,
    ) -> GeoPosition:
        calls.append(1)
        return GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    monkeypatch.setattr(enrichment, "project_terrain_aware", fake_project_terrain_aware)
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    store, _contact_id = _store_with_one_contact()
    contact = store.contacts[0]
    cache = WorldEnrichmentCache()

    cache.get_or_compute(_FAKE_CONN, "Syria", store, contact, now_sim=0.0)
    cache.get_or_compute(_FAKE_CONN, "Syria", store, contact, now_sim=5.0)

    assert len(calls) == 1  # second call was a cache hit, no recompute


def test_cache_miss_when_last_position_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def fake_project_terrain_aware(
        conn: sqlite3.Connection,
        theatre: str,
        observer: GeoPosition,
        bearing: float,
        rng: float,
        *,
        max_iterations: int,
    ) -> GeoPosition:
        calls.append(1)
        return GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    monkeypatch.setattr(enrichment, "project_terrain_aware", fake_project_terrain_aware)
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    store, _contact_id = _store_with_one_contact()
    contact = store.contacts[0]
    cache = WorldEnrichmentCache()
    cache.get_or_compute(_FAKE_CONN, "Syria", store, contact, now_sim=0.0)

    # A second observation moves the contact -- must invalidate the cache.
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=10.0, range_m=1500.0)], now_sim=10.0
    )
    contact = store.contacts[0]
    cache.get_or_compute(_FAKE_CONN, "Syria", store, contact, now_sim=10.0)

    assert len(calls) == 2


def test_cache_picks_iterative_max_iterations_within_range_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_max_iterations = []

    def fake_project_terrain_aware(
        conn: sqlite3.Connection,
        theatre: str,
        observer: GeoPosition,
        bearing: float,
        rng: float,
        *,
        max_iterations: int,
    ) -> GeoPosition:
        seen_max_iterations.append(max_iterations)
        return GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    monkeypatch.setattr(enrichment, "project_terrain_aware", fake_project_terrain_aware)
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=500.0)], now_sim=0.0)
    contact = store.contacts[0]
    cache = WorldEnrichmentCache()
    cache.get_or_compute(_FAKE_CONN, "Syria", store, contact, now_sim=0.0)

    assert seen_max_iterations == [5]


def test_cache_picks_single_shot_max_iterations_far_and_unwatched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_max_iterations = []

    def fake_project_terrain_aware(
        conn: sqlite3.Connection,
        theatre: str,
        observer: GeoPosition,
        bearing: float,
        rng: float,
        *,
        max_iterations: int,
    ) -> GeoPosition:
        seen_max_iterations.append(max_iterations)
        return GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    monkeypatch.setattr(enrichment, "project_terrain_aware", fake_project_terrain_aware)
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=5000.0)], now_sim=0.0)
    contact = store.contacts[0]
    cache = WorldEnrichmentCache()
    cache.get_or_compute(_FAKE_CONN, "Syria", store, contact, now_sim=0.0)

    assert seen_max_iterations == [1]


def test_cache_picks_iterative_max_iterations_when_watched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_max_iterations = []

    def fake_project_terrain_aware(
        conn: sqlite3.Connection,
        theatre: str,
        observer: GeoPosition,
        bearing: float,
        rng: float,
        *,
        max_iterations: int,
    ) -> GeoPosition:
        seen_max_iterations.append(max_iterations)
        return GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    monkeypatch.setattr(enrichment, "project_terrain_aware", fake_project_terrain_aware)
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: _FakeDescription()
    )

    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=5000.0)], now_sim=0.0)
    contact = store.contacts[0]
    contact.attention = "watch"
    cache = WorldEnrichmentCache()
    cache.get_or_compute(_FAKE_CONN, "Syria", store, contact, now_sim=0.0)

    assert seen_max_iterations == [5]


# --- relative_geometry ---------------------------------------------------


def test_relative_geometry_target_dead_ahead() -> None:
    ownship = _ownship(x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)
    target = GeoPosition(x=1000.0, z=0.0, alt_m=500.0)

    result = relative_geometry(ownship, target)

    assert result["bearing_deg"] == pytest.approx(0.0)
    assert result["range_m"] == pytest.approx(1000.0)
    assert result["clock_position"] == 12
    assert result["relative_alt_m"] == pytest.approx(0.0)


def test_relative_geometry_target_at_three_oclock() -> None:
    ownship = _ownship(x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)
    target = GeoPosition(x=0.0, z=1000.0, alt_m=600.0)

    result = relative_geometry(ownship, target)

    assert result["clock_position"] == 3
    assert result["relative_alt_m"] == pytest.approx(100.0)


def test_relative_geometry_accounts_for_ownship_heading() -> None:
    # Target due east; ownship heading east means the target is dead ahead
    # (clock 12), not at clock 3.
    ownship = _ownship(x=0.0, z=0.0, alt_m=500.0, heading_true_deg=90.0)
    target = GeoPosition(x=0.0, z=1000.0, alt_m=500.0)

    result = relative_geometry(ownship, target)

    assert result["clock_position"] == 12


# --- motion_when_seen ------------------------------------------------------


def test_motion_when_seen_returns_none_for_a_single_observation() -> None:
    store, _contact_id = _store_with_one_contact()
    contact = store.contacts[0]
    assert motion_when_seen(store, contact) is None


def test_motion_when_seen_derives_direction_from_two_distinct_positions() -> None:
    store = ContactStore()
    # Bearing 0 (north/+x) at both t=0 and t=10, but further out the second
    # time -- must stay within belief.association_over_time's spatial gate
    # (uncertainty + growth*elapsed) so the two percepts merge into one
    # contact rather than founding a second one.
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)],
        now_sim=0.0,
    )
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=10.0, bearing_deg=0.0, range_m=1100.0)],
        now_sim=10.0,
    )
    assert len(store.contacts) == 1
    contact = store.contacts[0]

    motion = motion_when_seen(store, contact)

    assert motion is not None
    assert motion["direction_deg"] == pytest.approx(0.0)
    assert motion["speed_mps"] == pytest.approx(10.0)


def test_motion_when_seen_skips_duplicate_positions() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)],
        now_sim=0.0,
    )
    # Same implied position as OBS_1 (identical bearing/range/observer).
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=5.0, bearing_deg=0.0, range_m=1000.0)],
        now_sim=5.0,
    )
    contact = store.contacts[0]

    assert motion_when_seen(store, contact) is None


# --- near-radius gating and non-Latin-1 names (live findings, 2026-09-18) ---
#
# Both came out of the first sortie that had Petrovich speaking. He reported
# "near <Arabic name> (~28700m)" -- a landmark 28.7 km away, named in a script
# DCS cannot render. Two independent defects in one line.


def test_far_settlement_produces_no_near_fact() -> None:
    """28.7 km is not near anything. Before gating, describe_position's
    nearest-of-each-kind result was reported regardless of distance."""
    assert not _within_near_radius("settlement", 28700.0)


def test_settlement_just_inside_the_radius_still_counts() -> None:
    assert _within_near_radius("settlement", 999.0)
    assert _within_near_radius("settlement", 1000.0)


def test_every_gated_kind_shares_todays_placeholder_radius() -> None:
    """All kinds sit at 1000 m deliberately -- one honest placeholder rather
    than five invented numbers. This test exists so that differentiating them
    later is a conscious edit with a visible diff, not an accident."""
    assert set(NEAR_FACT_RADIUS_M) == {
        "settlement",
        "road",
        "water",
        "ridge",
        "valley",
    }
    assert set(NEAR_FACT_RADIUS_M.values()) == {1000.0}


def test_unknown_kind_is_admitted_rather_than_muted() -> None:
    """A missing table entry should degrade to the old ungated behaviour, not
    silently drop a whole class of fact."""
    assert _within_near_radius("airfield", 50_000.0)


def test_arabic_name_is_dropped_so_the_caller_falls_back_to_a_label() -> None:
    """DCS renders no Arabic; the generic label is the honest degradation."""
    assert displayable_name("وادي حامر") is None


def test_latin1_names_survive_including_accents() -> None:
    assert displayable_name("Al Qaryatayn") == "Al Qaryatayn"
    assert displayable_name("Saint-Étienne") == "Saint-Étienne"


def test_displayable_name_passes_none_through() -> None:
    assert displayable_name(None) is None


# --- proximity wording: "on"/"next to" at short range (2026-09-19 roadmap
# item) ------------------------------------------------------------------


def test_proximity_text_at_zero_distance_says_on() -> None:
    assert _proximity_text("a road", 0.0) == "on a road"


def test_proximity_text_in_the_next_to_band_says_next_to() -> None:
    # 10.0 exactly is the band boundary and belongs to "next to", since the
    # user's rule is strictly "<10m" for "on".
    assert _proximity_text("a road", 10.0) == "next to a road"
    assert _proximity_text("a road", 50.0) == "next to a road"
    assert _proximity_text("a road", 99.0) == "next to a road"


def test_proximity_text_single_metres_is_on_not_near() -> None:
    """User direction 2026-09-19: "<10m from road -> on road". An earlier
    pass read the roadmap's "0 m" literally and left a 0.5-10 m gap that
    rendered as "near a road (~4 metres)" -- absurd for something a crew
    member would simply call *on* the road, and below what any eye resolves.
    The three bands now tile with no gap."""
    assert _proximity_text("a road", 0.0) == "on a road"
    assert _proximity_text("a road", 4.0) == "on a road"
    assert _proximity_text("a road", 9.9) == "on a road"


def test_proximity_text_at_or_above_the_next_to_band_falls_back_to_near() -> None:
    assert _proximity_text("a road", 100.0) == "near a road (100m)"
    assert _proximity_text("a road", 250.0) == "near a road (250m)"


def test_semantic_facts_for_road_on_top_of_says_on_the_road(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(nearest_road=_FakeInfo(name=None, distance_m=0.0))
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )
    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )
    assert facts[0].text == "on a road"


def test_semantic_facts_for_road_close_by_says_next_to_the_road(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = _FakeDescription(
        nearest_road=_FakeInfo(name="Route 1", distance_m=40.0)
    )
    monkeypatch.setattr(
        enrichment, "describe_position", lambda conn, theatre, x, z: description
    )
    facts = semantic_facts_for(
        _FAKE_CONN, "Syria", GeoPosition(x=0.0, z=0.0, alt_m=0.0), 1.0
    )
    assert facts[0].text == "next to Route 1"
