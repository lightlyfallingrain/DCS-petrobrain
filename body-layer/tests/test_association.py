"""Tests for `perception.association.associate`.

Fixtures below are hand-authored, not captured from a real DCS session --
per `plans/pb1-perception-logger/plan.md`'s own note that a live ambiguous
multi-object scene is harder to stage deliberately than to construct by
hand, and per the plan's requirement that `association.py` be testable
against fixtures with no live aircraft-layer connection. `WorldObjectCandidate`
instances are built directly with DCS-native x/z (bypassing
`WorldObjectCandidate.from_dict`'s lat/lon conversion, which is a thin,
separately-verifiable wrapper around world-model's `coordinates.wgs84_to_dcs`)
so these tests exercise `associate()`'s pure decision logic in isolation.
"""

from __future__ import annotations

import pytest

from perception import association
from perception.association import (
    AMBIGUOUS_ASSOCIATION_CONFIDENCE,
    AMBIGUOUS_ASSOCIATION_METHOD,
    CONFIDENT_ASSOCIATION_CONFIDENCE,
    CONFIDENT_ASSOCIATION_METHOD,
    OWNSHIP_ECHO_EXCLUSION_RADIUS_M,
    WorldObjectCandidate,
    associate,
    exclude_ownship,
)
from perception.source import OwnshipState

_OWNSHIP_T_SIM = 100.0


def _ownship(*, heading_true_deg: float = 0.0) -> OwnshipState:
    # x=0, z=0, alt=500 -- ownship at the coordinate origin, heading true
    # north unless overridden, matching perception.geometry's x=north/
    # z=east convention.
    return OwnshipState(
        t_sim=_OWNSHIP_T_SIM,
        x=0.0,
        z=0.0,
        alt_m=500.0,
        heading_true_deg=heading_true_deg,
    )


def _candidate(
    object_id: int, object_type: str, *, x: float, z: float, alt_m: float = 500.0
) -> WorldObjectCandidate:
    # alt_m defaults to ownship's own altitude (see _ownship) so range_m's
    # slant-range altitude component is zero and tests can assert exact
    # ground-distance values without doing trigonometry by hand.
    return WorldObjectCandidate(
        object_id=object_id, object_type=object_type, x=x, z=z, alt_m=alt_m
    )


def test_single_candidate_ahead_in_range_is_a_confident_match() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate(1, "Ural-4320", x=1000.0, z=0.0)

    result = associate("Ural truck", ownship, [candidate])

    assert result is not None
    assert result.candidate is candidate
    assert result.ambiguous is False
    assert result.confidence == CONFIDENT_ASSOCIATION_CONFIDENCE
    assert result.method == CONFIDENT_ASSOCIATION_METHOD
    assert result.range_m == 1000.0
    assert result.bearing_deg == 0.0


def test_no_candidates_returns_none() -> None:
    result = associate("Ural truck", _ownship(), [])

    assert result is None


def test_candidate_beyond_range_cap_is_dropped() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    far_candidate = _candidate(1, "Ural-4320", x=6000.0, z=0.0)

    result = associate("Ural truck", ownship, [far_candidate])

    assert result is None


def test_candidate_behind_ownship_is_dropped() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    # Directly behind ownship (bearing 180 deg) -- outside the +-90 deg
    # forward-hemisphere window from heading 0.
    behind_candidate = _candidate(1, "Ural-4320", x=-1000.0, z=0.0)

    result = associate("Ural truck", ownship, [behind_candidate])

    assert result is None


def test_only_the_forward_candidate_survives_when_one_is_behind() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    ahead = _candidate(1, "Ural-4320", x=1000.0, z=0.0)
    behind = _candidate(2, "Ural-4320", x=-1000.0, z=0.0)

    result = associate("Ural truck", ownship, [ahead, behind])

    assert result is not None
    assert result.candidate is ahead
    assert result.ambiguous is False


def test_ambiguous_multi_candidate_scene_picks_nearest_tied_candidate() -> None:
    # Two same-type objects, both ahead and in range, both matching
    # "Ural truck" equally well -- a genuinely ambiguous scene per the
    # plan's Association design section.
    ownship = _ownship(heading_true_deg=0.0)
    nearer = _candidate(1, "Ural-4320", x=1000.0, z=0.0)
    farther = _candidate(2, "Ural-4320", x=2000.0, z=0.0)

    result = associate("Ural truck", ownship, [nearer, farther])

    assert result is not None
    assert result.candidate is nearer
    assert result.ambiguous is True
    assert result.confidence == AMBIGUOUS_ASSOCIATION_CONFIDENCE
    assert result.method == AMBIGUOUS_ASSOCIATION_METHOD


def test_strictly_better_type_match_breaks_a_tie() -> None:
    # Two candidates in range/bearing, but only one's object_type shares a
    # keyword with the detection text -- an unambiguous top-scored winner
    # even though both survived the plausibility filter.
    ownship = _ownship(heading_true_deg=0.0)
    matching = _candidate(1, "Ural-4320", x=1500.0, z=0.0)
    non_matching = _candidate(2, "BMP-2", x=1000.0, z=0.0)

    result = associate("Ural truck", ownship, [matching, non_matching])

    assert result is not None
    assert result.candidate is matching
    assert result.ambiguous is False
    assert result.confidence == CONFIDENT_ASSOCIATION_CONFIDENCE


def test_forward_hemisphere_window_is_relative_to_ownship_heading() -> None:
    # Ownship heading east (90 deg); a candidate due north of ownship
    # (bearing 0 deg from origin) is at the edge of a heading-relative
    # window, not a north-relative one -- exercises that the filter uses
    # ownship.heading_true_deg, not a fixed compass reference.
    ownship = _ownship(heading_true_deg=90.0)
    east_of_ownship = _candidate(1, "Ural-4320", x=0.0, z=1000.0)

    result = associate("Ural truck", ownship, [east_of_ownship])

    assert result is not None
    assert result.candidate is east_of_ownship


def test_world_object_candidate_from_dict_converts_lat_lon_via_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def fake_wgs84_to_dcs(theatre: str, lat: float, lon: float) -> tuple[float, float]:
        calls.append((theatre, lat, lon))
        return 1234.0, 5678.0

    monkeypatch.setattr(association, "wgs84_to_dcs", fake_wgs84_to_dcs)

    candidate = WorldObjectCandidate.from_dict(
        {
            "object_id": 42,
            "object_type": "Ural-4320",
            "lat_deg": 35.1,
            "lon_deg": 35.9,
            "altitude_m": 120.0,
        },
        theatre="Syria",
    )

    assert calls == [("Syria", 35.1, 35.9)]
    assert candidate.object_id == 42
    assert candidate.object_type == "Ural-4320"
    assert candidate.x == 1234.0
    assert candidate.z == 5678.0
    assert candidate.alt_m == 120.0


def test_exclude_ownship_drops_a_candidate_essentially_co_located_with_ownship() -> (
    None
):
    # Reproduces the PB-1.5 live-sortie bug: LoGetWorldObjects is unfiltered
    # ground truth and includes the player's own aircraft (see
    # exclude_ownship's docstring). A candidate a few metres from ownship --
    # well within the exclusion radius, the kind of residual you'd expect
    # between two independent DCS-reported positions for the same aircraft
    # -- must be dropped as the ownship echo, not treated as a real contact.
    ownship = _ownship()
    self_echo = _candidate(999, "Mi-24P", x=3.0, z=-2.0)

    assert exclude_ownship([self_echo], ownship) == []


def test_exclude_ownship_keeps_a_candidate_outside_the_radius() -> None:
    ownship = _ownship()
    far_candidate = _candidate(
        1, "Ural-4320", x=OWNSHIP_ECHO_EXCLUSION_RADIUS_M + 1.0, z=0.0
    )

    assert exclude_ownship([far_candidate], ownship) == [far_candidate]


def test_exclude_ownship_drops_a_candidate_exactly_at_the_radius_boundary() -> None:
    # exclude_ownship keeps only strictly-greater-than-radius candidates
    # (range_m > OWNSHIP_ECHO_EXCLUSION_RADIUS_M), so a candidate exactly at
    # the radius is still treated as the ownship echo and dropped.
    ownship = _ownship()
    boundary_candidate = _candidate(
        1, "Ural-4320", x=OWNSHIP_ECHO_EXCLUSION_RADIUS_M, z=0.0
    )

    assert exclude_ownship([boundary_candidate], ownship) == []
