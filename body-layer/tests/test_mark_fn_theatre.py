"""`logger._mark_here_fn`/`_mark_target_fn` read `runner.theatre` live --
`BL-15` Stage 3's own fix to a stale-closure bug these two functions would
otherwise have introduced: before this stage, each took `theatre: str` as
a plain constructor-time parameter, bound once by `main()` before the poll
loop starts. A runtime theatre switch (`_maybe_switch_theatre`) updates
`runner.theatre` in place, but reassigning that outer local variable never
reaches a closure that already captured the old value by parameter
binding -- the same trap `_speech_log_sink`'s own docstring describes for
`belief_truth_writer`, here for `theatre` instead.

Confirms the fix the direct way: construct the closure once, call it twice
with `runner.theatre` changed in between, and check the recorded mark's
`lat`/`lon` (derived from `theatre` via `coordinates.dcs_to_wgs84`) changed
with it -- proof the closure is reading `runner.theatre` at call time, not
at construction time."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from aircraft_client import AircraftLayerClient
from belief.enrichment import EnrichmentContext
from body import ConsolePerceptionRunner, _mark_here_fn, _mark_target_fn
from mission_memory.entries import MarkPayload
from mission_memory.store import MissionMemory
from perception.geometry import open_world_model
from perception.source import OwnshipState
from store.writer import open_for_build


def _runner_with_enrichment(db_path: Path, theatre: str) -> ConsolePerceptionRunner:
    conn = open_for_build(db_path)
    conn.close()
    read_conn = open_world_model(db_path)
    runner = ConsolePerceptionRunner(
        aircraft_client=cast(AircraftLayerClient, object()), theatre=theatre
    )
    ownship = OwnshipState(t_sim=0.0, x=0.0, z=0.0, alt_m=100.0, heading_true_deg=0.0)
    runner.enrichment = EnrichmentContext(
        conn=read_conn, theatre=theatre, ownship=ownship
    )
    return runner


def test_mark_here_fn_reads_runner_theatre_live_across_a_switch(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "region.sqlite"
    runner = _runner_with_enrichment(db_path, "Syria")
    memory = MissionMemory()
    mark_here = _mark_here_fn(memory, runner)

    mark_here(now_sim=0.0)
    assert len(memory.entries) == 1
    first_pos = memory.entries[0].pos
    assert first_pos is not None

    # Simulate a successful runtime theatre switch (`_maybe_switch_theatre`
    # mutates `runner.theatre` in place -- this is exactly that mutation,
    # without constructing a second world-model store just for this test).
    runner.theatre = "Afghanistan"
    mark_here(now_sim=1.0)
    assert len(memory.entries) == 2
    second_pos = memory.entries[1].pos
    assert second_pos is not None

    # Different theatres project the same x/z to different lat/lon --
    # if the closure were still reading its old, captured "Syria" value,
    # these would be identical.
    assert (first_pos.lat, first_pos.lon) != (second_pos.lat, second_pos.lon)


def test_mark_target_fn_reads_runner_theatre_live_across_a_switch(
    tmp_path: Path,
) -> None:
    from belief.contacts import ContactStore
    from perception.source import DerivedWorldPosition, Observation

    db_path = tmp_path / "region.sqlite"
    runner = _runner_with_enrichment(db_path, "Syria")
    ownship = OwnshipState(t_sim=0.0, x=0.0, z=0.0, alt_m=100.0, heading_true_deg=0.0)
    store = ContactStore()
    store.ingest(
        [
            Observation(
                id="OBS_1",
                contact_id=None,
                t_sim=0.0,
                t_wall=0.0,
                source="naked_eye_visual_filtered",
                classification_raw="BMP-2",
                bearing_deg=0.0,
                range_m=1000.0,
                ownship_at_observation=ownship,
                derived_world_position=DerivedWorldPosition(
                    x=0.0, z=0.0, confidence=0.9, method="bearing_range_terrain"
                ),
                provenance="test_fixture",
                classification_level=2,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    runner.store = store
    memory = MissionMemory()
    mark_target = _mark_target_fn(memory, runner)

    mark_target(contact_id, 0.0)
    assert len(memory.entries) == 1
    first_pos = memory.entries[0].pos
    assert first_pos is not None

    runner.theatre = "Afghanistan"
    mark_target(contact_id, 1.0)
    assert len(memory.entries) == 2
    second_pos = memory.entries[1].pos
    assert second_pos is not None

    assert (first_pos.lat, first_pos.lon) != (second_pos.lat, second_pos.lon)
    for entry in memory.entries:
        assert isinstance(entry.payload, MarkPayload)
