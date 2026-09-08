"""Tests for the BL-0 replay harness (`replay.py`).

Uses a trivial `FakePerceptionSource` -- seeded from the committed
`tests/fixtures/world_objects_sample.json` fixture, standing in for a real
Tier 3 proxy's aircraft-layer client -- to prove the harness drives any
`PerceptionSource` end to end without a live DCS/aircraft-layer connection.
This is the same shape `plans/pb1-perception-logger/plan.md` stage 6's
interface-swap smoke test will later reuse, once a second concrete tier
exists to swap in.
"""

from __future__ import annotations

import json
from pathlib import Path

from perception.source import Observation, OwnshipState, PerceptionSource
from replay import load_ownship_frames, replay

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


class FakePerceptionSource:
    """Returns one synthetic `Observation` per poll, built from a fixture
    world-objects snapshot rather than a live aircraft-layer call --
    standing in for a real tier for harness testing purposes only."""

    def __init__(self, world_objects_fixture_path: Path) -> None:
        self._snapshot = json.loads(world_objects_fixture_path.read_text())
        self._poll_count = 0

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        self._poll_count += 1
        objects = self._snapshot["objects"]
        if not objects:
            return []
        first = objects[0]
        return [
            Observation(
                id=f"OBS_{self._poll_count}",
                contact_id=None,
                t_sim=now_sim,
                t_wall=0.0,
                source="proxy_heuristic",
                classification_raw=first["object_type"],
                bearing_deg=0.0,
                range_m=1000.0,
                ownship_at_observation=ownship_state,
                derived_world_position=None,
                provenance="test_fixture",
            )
        ]


def test_load_ownship_frames_sorts_by_t_sim() -> None:
    frames = load_ownship_frames(_FIXTURES_DIR / "telemetry_frames.json")

    assert [frame.t_sim for frame in frames] == [100.0, 100.2, 100.4]


def test_load_ownship_frames_converts_position_and_heading() -> None:
    frames = load_ownship_frames(_FIXTURES_DIR / "telemetry_frames.json")

    first = frames[0]
    assert first.x == 10000.0
    assert first.z == 20000.0
    assert first.alt_m == 450.0
    assert first.heading_true_deg == 0.0

    third = frames[2]
    assert third.heading_true_deg == 90.0


def test_replay_drives_source_once_per_frame_in_order() -> None:
    frames = load_ownship_frames(_FIXTURES_DIR / "telemetry_frames.json")
    source: PerceptionSource = FakePerceptionSource(
        _FIXTURES_DIR / "world_objects_sample.json"
    )

    results = list(replay(source, frames))

    assert len(results) == len(frames)
    for (frame, observations), expected_frame in zip(results, frames, strict=True):
        assert frame is expected_frame
        assert len(observations) == 1
        assert observations[0].classification_raw == "BMP-2"
        assert observations[0].t_sim == expected_frame.t_sim


def test_replay_yields_empty_observations_from_a_source_with_nothing_to_report() -> (
    None
):
    frames = load_ownship_frames(_FIXTURES_DIR / "telemetry_frames.json")

    class EmptySource:
        def poll(
            self, now_sim: float, ownship_state: OwnshipState
        ) -> list[Observation]:
            return []

    results = list(replay(EmptySource(), frames))

    assert all(observations == [] for _frame, observations in results)
