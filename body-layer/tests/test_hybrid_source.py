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
from perception.hybrid_source import (
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
    assert observations[0].range_m == 1000.0


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
    assert obs.range_m == 1000.0
    assert obs.bearing_deg == 0.0
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
