"""Tests for `perception.hybrid_source.HybridPerceptionSource`.

Uses a fake `AircraftLayerClient`-shaped object (duck-typed, matching
`get_petrovich_indication_latest`/`get_world_objects_latest`) -- no network
I/O, mirroring `test_logger.py`'s fake-client pattern. `association.
wgs84_to_dcs` is monkeypatched to an identity-ish mapping so candidate
positions in these tests are plain numbers, not real theatre projection
math (already covered by `test_association.py`'s own conversion test and
world-model's own coordinate-subsystem tests).
"""

from __future__ import annotations

from typing import Any

import pytest

from perception import association
from perception.estimation import perturbed_bearing_range
from perception.geometry import GeoPosition, bearing_deg, range_m
from perception.hybrid_source import (
    SCOPE_UNCERTAINTY_M,
    SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    HybridPerceptionSource,
)
from perception.source import OwnshipState

_THEATRE = "Syria"


def _ownship() -> OwnshipState:
    return OwnshipState(t_sim=100.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _world_object(
    object_id: int,
    object_type: str,
    *,
    lat_deg: float,
    lon_deg: float,
    is_ownship: bool | None = False,
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": object_type,
        "coalition": 1.0,
        "lat_deg": lat_deg,
        "lon_deg": lon_deg,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": is_ownship,
    }


class FakeAircraftClient:
    def __init__(
        self,
        indications: list[dict[str, Any] | None],
        world_objects: dict[str, Any] | None,
    ) -> None:
        self._indications = indications
        self._world_objects = world_objects
        self.world_objects_calls = 0

    def get_petrovich_indication_latest(self) -> dict[str, Any] | None:
        return self._indications.pop(0)

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        self.world_objects_calls += 1
        return self._world_objects


@pytest.fixture(autouse=True)
def identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    # lat_deg/lon_deg pass straight through as x/z -- lets tests author
    # candidate positions directly without real projection math.
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


def _indication(fields: dict[str, str] | None) -> dict[str, Any]:
    return {
        "dcs_model_time_s": 100.0,
        "received_wall_clock_s": 1000.0,
        "fields": fields or {},
    }


def _true_bearing_range(
    ownship: OwnshipState, candidate_x: float, candidate_z: float
) -> tuple[float, float]:
    """True `(bearing_deg, range_m)` from `ownship` to a candidate at
    `(candidate_x, candidate_z)`, altitude-matched -- the same
    `perception.geometry` primitives `association.associate` itself calls,
    used here only to derive what a test's *expected* perturbed value
    should be, never to bypass the real perturbation path."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    target = GeoPosition(x=candidate_x, z=candidate_z, alt_m=ownship.alt_m)
    return bearing_deg(observer, target), range_m(observer, target)


def _expected_perturbed(
    observation_id: str,
    object_id: int,
    true_bearing_deg: float,
    true_range_m: float,
) -> tuple[float, float]:
    """The exact perturbed `(bearing_deg, range_m)` this channel must emit
    for a given `Observation.id`/`object_id`/true geometry -- computed via
    the real `perturbed_bearing_range` this module now calls (the required
    review fix), not re-derived by hand. Mirrors `naked_eye_source`'s own
    tests not asserting truth-exact geometry any more."""
    return perturbed_bearing_range(
        observation_id=observation_id,
        object_id=object_id,
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_range_m,
        sigma_cross_m=SCOPE_UNCERTAINTY_M,
        sigma_down_m=SCOPE_UNCERTAINTY_M,
    )


def test_no_indication_yet_returns_empty() -> None:
    client = FakeAircraftClient([None], world_objects=None)
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    assert source.poll(100.0, _ownship()) == []


def test_no_populated_classification_returns_empty() -> None:
    client = FakeAircraftClient([_indication(None)], world_objects=None)
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    assert source.poll(100.0, _ownship()) == []


def test_new_classification_with_no_world_objects_snapshot_drops() -> None:
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"})], world_objects=None
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    assert source.poll(100.0, _ownship()) == []


def test_new_classification_with_no_plausible_candidate_drops() -> None:
    world_objects = {
        "objects": [
            _world_object(1, "Ural-4320", lat_deg=6000.0, lon_deg=0.0)  # out of range
        ]
    }
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"})], world_objects=world_objects
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    assert source.poll(100.0, _ownship()) == []


def test_ownship_echo_is_excluded_and_detection_drops_with_no_other_candidate() -> None:
    # Reproduces the PB-1.5 live-sortie bug for the association/scope
    # channel too: LoGetWorldObjects includes the player's own aircraft,
    # identified here by the aircraft-layer's is_ownship flag rather than
    # proximity. With no other candidate present, filter_ownship leaves
    # associate() with nothing to resolve against, so the detection is
    # dropped rather than associated with ownship itself.
    world_objects = {
        "objects": [
            _world_object(999, "Mi-24P", lat_deg=3.0, lon_deg=-2.0, is_ownship=True)
        ]
    }
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"})], world_objects=world_objects
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    assert source.poll(100.0, _ownship()) == []


def test_ownship_echo_does_not_prevent_a_real_candidate_from_associating() -> None:
    # The echo deliberately carries the SAME object_type as the real target.
    # With a mismatched type (e.g. "Mi-24P"), `associate()`'s own type-match
    # tie-break discards it regardless of `filter_ownship`, and this test
    # passes whether or not the fix is present -- it did exactly that until
    # Pass 3 caught it (back when exclusion was proximity-based). Tying the
    # type removes that confound, so the only thing that can still
    # discriminate is the ownship exclusion itself.
    world_objects = {
        "objects": [
            _world_object(
                999, "Ural-4320", lat_deg=3.0, lon_deg=-2.0, is_ownship=True
            ),  # ownship echo
            _world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0),  # real target
        ]
    }
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"})], world_objects=world_objects
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    true_bearing_deg, true_range_m = _true_bearing_range(_ownship(), 1000.0, 0.0)
    _, expected_range_m = _expected_perturbed(
        observations[0].id, 1, true_bearing_deg, true_range_m
    )
    assert observations[0].range_m == pytest.approx(expected_range_m)


def test_new_classification_with_a_confident_candidate_emits_one_observation() -> None:
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"})], world_objects=world_objects
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.classification_raw == "Ural truck"
    assert obs.source == SOURCE_PETROVICH_DETECTION_ASSOCIATED
    true_bearing_deg, true_range_m = _true_bearing_range(_ownship(), 1000.0, 0.0)
    expected_bearing_deg, expected_range_m = _expected_perturbed(
        obs.id, 1, true_bearing_deg, true_range_m
    )
    assert obs.range_m == pytest.approx(expected_range_m)
    assert obs.bearing_deg == pytest.approx(expected_bearing_deg)
    # The channel no longer hands belief truth-exact geometry (the required
    # review fix) -- pin that the perturbation actually moved the numbers,
    # not just that the expected-value helper agrees with itself.
    assert obs.range_m != true_range_m
    assert obs.position_uncertainty is not None
    assert obs.position_uncertainty.sigma_cross_m == SCOPE_UNCERTAINTY_M
    assert obs.position_uncertainty.sigma_down_m == SCOPE_UNCERTAINTY_M
    assert obs.derived_world_position is not None
    assert obs.derived_world_position.confidence == pytest.approx(0.6)
    assert obs.provenance == "petrovich_indication+world_objects"


def test_ambiguous_candidate_sets_ambiguous_provenance_and_low_confidence() -> None:
    world_objects = {
        "objects": [
            _world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0),
            _world_object(2, "Ural-4320", lat_deg=2000.0, lon_deg=0.0),
        ]
    }
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"})], world_objects=world_objects
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1
    obs = observations[0]
    assert obs.derived_world_position is not None
    assert obs.derived_world_position.confidence == pytest.approx(0.25)
    assert obs.provenance == "petrovich_indication+world_objects/ambiguous_association"


def test_repeated_identical_classification_is_debounced() -> None:
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(
        [
            _indication({"middle_list_text": "Ural truck"}),
            _indication({"middle_list_text": "Ural truck"}),
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())

    assert len(first) == 1
    assert second == []
    # World objects fetched only once -- the debounced poll never reaches
    # the association step at all.
    assert client.world_objects_calls == 1


def test_classification_change_re_emits() -> None:
    world_objects = {
        "objects": [
            _world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0),
            _world_object(2, "BMP-2", lat_deg=1000.0, lon_deg=0.0),
        ]
    }
    client = FakeAircraftClient(
        [
            _indication({"middle_list_text": "Ural truck"}),
            _indication({"middle_list_text": "BMP"}),
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())

    assert len(first) == 1
    assert len(second) == 1
    assert second[0].classification_raw == "BMP"


# --- PB-2 Stage 0b: multiple simultaneous list-text leaves
# (`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-
# detection.md` Finding 6) yield multiple `Observation`s per poll, each
# claiming a distinct candidate.


def test_sa3_launcher_and_radar_leaves_yield_two_observations() -> None:
    # Reproduces Finding 6's real sampled tuple: middle_list_text and
    # lower_list_text both read "SA-3 launcher" (deduplicated to one
    # distinct text) while lower_lower_list_text reads "SA-3 Low Blow radar"
    # -- two distinct real objects held at the same time, not one.
    world_objects = {
        "objects": [
            _world_object(1, "5p73 s-125 ln", lat_deg=1000.0, lon_deg=0.0),
            _world_object(2, "snr s-125 tr", lat_deg=1000.0, lon_deg=50.0),
        ]
    }
    client = FakeAircraftClient(
        [
            _indication(
                {
                    "middle_list_text": "SA-3 launcher",
                    "lower_list_text": "SA-3 launcher",
                    "lower_lower_list_text": "SA-3 Low Blow radar",
                }
            )
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 2
    classifications = {obs.classification_raw for obs in observations}
    assert classifications == {"SA-3 launcher", "SA-3 Low Blow radar"}
    # Each observation claims its own candidate, not the same one twice --
    # the two candidates sit at different ranges from ownship (z=0 vs z=50),
    # so distinct ranges is proof of distinct candidates.
    ranges = {round(obs.range_m, 3) for obs in observations}
    assert len(ranges) == 2


def test_slava_cruiser_and_tarantul_corvette_leaves_yield_two_observations() -> None:
    # Reproduces Finding 6's other real sampled tuple: middle_list_text
    # "Slava cruiser" and lower_list_text "Tarantul III corvette" -- two
    # distinct real ships held at the same time.
    world_objects = {
        "objects": [
            _world_object(1, "MOSCOW", lat_deg=1000.0, lon_deg=0.0),
            _world_object(2, "MOLNIYA", lat_deg=1000.0, lon_deg=50.0),
        ]
    }
    client = FakeAircraftClient(
        [
            _indication(
                {
                    "middle_list_text": "Slava cruiser",
                    "lower_list_text": "Tarantul III corvette",
                }
            )
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 2
    classifications = {obs.classification_raw for obs in observations}
    assert classifications == {"Slava cruiser", "Tarantul III corvette"}


def test_repeated_text_across_leaves_is_deduplicated_to_one_observation() -> None:
    # middle_list_text and lower_list_text carrying the SAME text (a single
    # highlighted row plus its own neighbour echo, per Finding 6's Ural-truck
    # samples) must not produce two Observations for one real object.
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(
        [
            _indication(
                {
                    "middle_list_text": "Ural truck",
                    "lower_list_text": "Ural truck",
                }
            )
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    observations = source.poll(100.0, _ownship())

    assert len(observations) == 1


def test_detection_clearing_then_reappearing_with_same_text_re_emits() -> None:
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(
        [
            _indication({"middle_list_text": "Ural truck"}),
            _indication(None),  # detection momentarily clears
            _indication({"middle_list_text": "Ural truck"}),  # reappears, same text
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())
    third = source.poll(100.4, _ownship())

    assert len(first) == 1
    assert second == []
    assert len(third) == 1


def test_continuity_resolves_across_a_leaf_gap_for_the_same_object_id() -> None:
    """`plans/contact-duplication-ambiguity-runaway/plan.md`'s object-
    permanence mechanism, newly in scope for this channel: the same
    resolved `object_id`, re-associated after several polls where the leaf
    text was entirely absent, must still resolve `continues_observation_id`
    to the last observation emitted before the gap."""
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(
        [
            _indication({"middle_list_text": "Ural truck"}),
            _indication(None),
            _indication(None),
            _indication({"middle_list_text": "Ural truck"}),
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    first = source.poll(100.0, _ownship())
    assert len(first) == 1
    assert first[0].continues_observation_id is None

    assert source.poll(100.2, _ownship()) == []
    assert source.poll(100.4, _ownship()) == []
    reacquired = source.poll(100.6, _ownship())

    assert len(reacquired) == 1
    assert reacquired[0].continues_observation_id == first[0].id


def test_continuity_never_cross_tags_two_different_leaves() -> None:
    """Two simultaneous leaves resolving to two distinct `object_id`s must
    never have their `continues_observation_id`s cross, even after both
    leaves go through a debounce cycle."""
    world_objects = {
        "objects": [
            _world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0),
            _world_object(2, "BMP-2", lat_deg=2000.0, lon_deg=500.0),
        ]
    }
    client = FakeAircraftClient(
        [
            _indication({"middle_list_text": "Ural truck", "lower_list_text": "BMP"}),
            _indication(None),
            _indication({"middle_list_text": "Ural truck", "lower_list_text": "BMP"}),
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(aircraft_client=client, theatre=_THEATRE)  # type: ignore[arg-type]

    first = source.poll(100.0, _ownship())
    assert len(first) == 2
    assert all(obs.continues_observation_id is None for obs in first)

    assert source.poll(100.2, _ownship()) == []
    second = source.poll(100.4, _ownship())

    assert len(second) == 2
    truck_first = next(obs for obs in first if obs.classification_raw == "Ural truck")
    bmp_first = next(obs for obs in first if obs.classification_raw == "BMP")
    truck_second = next(obs for obs in second if obs.classification_raw == "Ural truck")
    bmp_second = next(obs for obs in second if obs.classification_raw == "BMP")

    assert truck_second.continues_observation_id == truck_first.id
    assert bmp_second.continues_observation_id == bmp_first.id
    assert truck_second.continues_observation_id != bmp_first.id
    assert bmp_second.continues_observation_id != truck_first.id


def test_every_poll_mode_re_emits_an_unchanged_detection_set() -> None:
    # Stage 3 (plans/pb2-contact-memory/plan.md Interface confirmation gap
    # 2): under emit_mode="every_poll", a statically visible detection must
    # keep producing an Observation every poll rather than being debounced
    # away after the first -- the belief layer, not this source, now owns
    # de-duplication.
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(
        [
            _indication({"middle_list_text": "Ural truck"}),
            _indication({"middle_list_text": "Ural truck"}),
            _indication({"middle_list_text": "Ural truck"}),
        ],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        emit_mode="every_poll",
    )

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())
    third = source.poll(100.4, _ownship())

    assert len(first) == 1
    assert len(second) == 1
    assert len(third) == 1


def test_every_poll_mode_still_returns_nothing_when_detection_clears() -> None:
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=1000.0, lon_deg=0.0)]
    }
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"}), _indication(None)],
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        emit_mode="every_poll",
    )

    first = source.poll(100.0, _ownship())
    second = source.poll(100.2, _ownship())

    assert len(first) == 1
    assert second == []


# --- Required review fix (`plans/precise-position-belief/review.md`): this
# channel must perturb, not hand belief `associate()`'s truth-exact geometry
# -- see `perception.estimation`'s module docstring and `hybrid_source.py`'s
# `SCOPE_UNCERTAINTY_M` docstring. The test below is the one the review
# named explicitly: this is the invariant the whole milestone exists to
# hold, and it is the one a prior implementer's mechanical Stage 1
# declaration (the `PositionUncertainty(300, 300)` field) silently did not.


def test_repeated_scope_observations_of_a_stationary_object_do_not_converge_on_truth() -> (
    None
):
    """A heavily-observed contact seen only through the scope/hybrid channel
    must NOT converge on exact ground truth behind a cosmetic uncertainty
    band -- the "precise and wrong" behaviour `perception.estimation`'s
    per-object systematic bias exists to guarantee structurally. Poll a
    stationary target many times (`emit_mode="every_poll"` so debounce
    never suppresses a re-observation) and check the mean of the emitted
    ranges, not any single look: per-look noise should average toward zero
    across enough looks, but the never-redrawn systematic bias must not --
    so the mean stays measurably off true range, by roughly the bias this
    object's id actually draws."""
    true_range_m = 1000.0
    world_objects = {
        "objects": [_world_object(1, "Ural-4320", lat_deg=true_range_m, lon_deg=0.0)]
    }
    n_polls = 60
    client = FakeAircraftClient(
        [_indication({"middle_list_text": "Ural truck"})] * n_polls,
        world_objects=world_objects,
    )
    source = HybridPerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        emit_mode="every_poll",
    )

    ranges_m = [
        source.poll(100.0 + i * 0.2, _ownship())[0].range_m for i in range(n_polls)
    ]

    mean_range_m = sum(ranges_m) / len(ranges_m)
    # The per-object systematic bias is `SYSTEMATIC_BIAS_FRACTION *
    # SCOPE_UNCERTAINTY_M` on the down-range axis at most -- confirm the
    # averaged-over-many-looks estimate sits measurably away from truth
    # (not within a few metres, which per-look noise alone could produce by
    # chance), demonstrating the bias, not the noise, is what survives
    # averaging.
    assert abs(mean_range_m - true_range_m) > 20.0
    # No single look ever lands on exact truth either -- the mechanical,
    # unperturbed behaviour this fix replaces.
    assert all(range_m_value != true_range_m for range_m_value in ranges_m)
