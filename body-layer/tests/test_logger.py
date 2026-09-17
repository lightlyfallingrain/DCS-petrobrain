"""Tests for `logger.PerceptionLogger`/`format_observation_line` and (PB-2
Stage 3) `logger.ConsolePerceptionRunner`.

Uses fake `AircraftLayerClient`-shaped objects and fake `PerceptionSource`s
-- concrete tiers exist now (`HybridPerceptionSource`,
`NakedEyePerceptionSource`), but `PerceptionLogger` itself is written
entirely against the `PerceptionSource` protocol and doesn't need a real one
to demonstrate its own poll/format/print logic, or (PB-1.5) that it polls
and concatenates more than one source correctly. `ConsolePerceptionRunner`
is tested the same way, against a real `belief.contacts.ContactStore` (no
fake needed -- it's already pure/fixture-testable per `test_contacts.py`).
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from aircraft_client import AircraftLayerError
from belief.console import Console
from belief.contacts import ContactStore
from belief.mission_phase import (
    CompactRoutePoint,
    MissionPhaseTracker,
    MissionUnderstandingData,
)
from logger import (
    ConsolePerceptionRunner,
    PerceptionLogger,
    _run_console_poll_loop,
    _run_console_repl,
    format_observation_line,
)
from perception import association
from perception.geometry import GeoPosition
from perception.source import Observation, OwnshipState
from store.writer import open_for_build


def _telemetry_dict() -> dict[str, Any]:
    return {
        "dcs_model_time_s": 200.0,
        "position_x_m": 5000.0,
        "position_y_m": 400.0,
        "position_z_m": 8000.0,
        "heading_true_rad": 0.0,
        "pitch_rad": 0.0,
        "bank_rad": 0.0,
        "altitude_msl_m": 350.0,
    }


class FakeAircraftClient:
    def __init__(self, telemetry: dict[str, Any] | None) -> None:
        self._telemetry = telemetry

    def get_telemetry_latest(self) -> dict[str, Any] | None:
        return self._telemetry


class FakeSource:
    def __init__(self, observations: list[Observation]) -> None:
        self._observations = observations

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        return self._observations


def _make_observation(
    ownship: OwnshipState,
    *,
    id: str = "OBS_1",
    source: str = "proxy_heuristic",
    classification_raw: str = "BMP",
) -> Observation:
    return Observation(
        id=id,
        contact_id=None,
        t_sim=ownship.t_sim,
        t_wall=0.0,
        source=source,
        classification_raw=classification_raw,
        bearing_deg=32.0,
        range_m=3100.0,
        ownship_at_observation=ownship,
        derived_world_position=None,
        provenance="test",
    )


def test_format_observation_line_includes_all_pb1_fields() -> None:
    ownship = OwnshipState.from_telemetry_dict(_telemetry_dict())
    observation = _make_observation(ownship)

    line = format_observation_line(ownship, observation)

    assert "t_sim=200.00" in line
    assert "aircraft=(5000.0, 8000.0, 350.0)" in line
    assert "source=proxy_heuristic" in line
    assert "classification=BMP" in line
    assert "bearing_deg=32.0" in line
    assert "range_m=3100" in line


def test_run_once_returns_empty_when_no_telemetry_yet() -> None:
    logger = PerceptionLogger(
        aircraft_client=FakeAircraftClient(None),  # type: ignore[arg-type]
        sources=[FakeSource([])],
    )

    assert logger.run_once() == []


def test_run_once_formats_and_returns_lines_for_each_observation() -> None:
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    observations = [_make_observation(ownship)]

    logger = PerceptionLogger(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource(observations)],
    )

    lines = logger.run_once()

    assert len(lines) == 1
    assert "classification=BMP" in lines[0]


def test_run_once_prints_to_configured_output() -> None:
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    observations = [_make_observation(ownship)]
    output = io.StringIO()

    logger = PerceptionLogger(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource(observations)],
        output=output,
    )

    logger.run_once()

    assert "classification=BMP" in output.getvalue()


def test_run_once_polls_every_source_and_concatenates_observations() -> None:
    # PB-1.5: PerceptionLogger.sources is a plain list, polled and
    # concatenated in order -- no CompositePerceptionSource abstraction
    # (plans/pb1.5-naked-eye-detection/plan.md's Affected Modules section).
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    hybrid_observation = _make_observation(
        ownship, id="OBS_hybrid", source="petrovich_detection_associated"
    )
    naked_eye_observation = _make_observation(
        ownship, id="OBS_naked_eye", source="naked_eye_visual_filtered"
    )

    logger = PerceptionLogger(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[
            FakeSource([hybrid_observation]),
            FakeSource([naked_eye_observation]),
        ],
    )

    lines = logger.run_once()

    assert len(lines) == 2
    assert "source=petrovich_detection_associated" in lines[0]
    assert "source=naked_eye_visual_filtered" in lines[1]


def test_console_runner_returns_empty_when_no_telemetry_yet() -> None:
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(None),  # type: ignore[arg-type]
        sources=[FakeSource([])],
    )

    assert runner.run_once() == []
    assert runner.store.contacts == []


def test_console_runner_ingests_observations_into_its_store() -> None:
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    observations = [_make_observation(ownship)]

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource(observations)],
    )

    returned = runner.run_once()

    assert returned == observations
    assert len(runner.store.contacts) == 1
    assert len(runner.store.observations) == 1


def test_console_runner_reuses_a_store_across_calls() -> None:
    # Mirrors how main() drives a fixed ContactStore across the whole poll
    # loop -- the same object accumulates contacts/observations poll over
    # poll, it is not rebuilt each run_once() call.
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    store = ContactStore()
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship, id="OBS_1")])],
        store=store,
    )

    runner.run_once()
    runner.sources = [FakeSource([_make_observation(ownship, id="OBS_2")])]
    runner.run_once()

    assert len(store.observations) == 2


def test_console_runner_tracks_last_t_sim_for_the_repl() -> None:
    # PB-2 Stage 4: main()'s REPL thread reads `last_t_sim` as `now_sim` for
    # whatever console command the operator just typed -- unset until the
    # first successful poll, then updated every poll after.
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(None),  # type: ignore[arg-type]
        sources=[FakeSource([])],
    )
    assert runner.last_t_sim is None

    runner.aircraft_client = FakeAircraftClient(telemetry)  # type: ignore[assignment]
    runner.run_once()

    assert runner.last_t_sim == ownship.t_sim


class FakeOverlayClient:
    """A `push_text_line`-only double (BL-2.5). `fail_on` names texts that
    raise `AircraftLayerError` instead of recording -- used to exercise
    `ConsolePerceptionRunner.run_once`'s per-push isolation."""

    def __init__(self, fail_on: frozenset[str] = frozenset()) -> None:
        self.pushed: list[str] = []
        self._fail_on = fail_on

    def push_text_line(self, text: str) -> None:
        if text in self._fail_on:
            raise AircraftLayerError("simulated push failure")
        self.pushed.append(text)


def test_console_runner_without_overlay_client_pushes_nothing() -> None:
    # --overlay defaults off: overlay_client stays None, a true no-op --
    # run_once must behave exactly as before, no AttributeError, no
    # aircraft-layer call attempted for this purpose.
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship)])],
    )

    runner.run_once()

    assert runner.overlay_client is None
    assert len(runner.store.events) == 1  # the event still fires...
    # ...it is simply never mirrored anywhere, which is exactly the point.


def test_console_runner_pushes_one_line_per_newly_materialized_event() -> None:
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    overlay_client = FakeOverlayClient()

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship, classification_raw="BMP")])],
        overlay_client=overlay_client,  # type: ignore[arg-type]
    )

    runner.run_once()

    (contact,) = runner.store.contacts
    (event,) = runner.store.events
    assert event.kind == "CONTACT_DETECTED"
    assert overlay_client.pushed == [
        f"{contact.id}: CONTACT_DETECTED, {contact.last_class_raw}, observed, currently visible."
    ]


def test_console_runner_overlay_push_failure_is_isolated_per_push() -> None:
    """The plan's one load-bearing try/except (Risks & Unknowns): a failed
    push for one event must not stop the poll loop, must not drop the
    observations already collected this poll, and must not skip pushing the
    remaining events in the same batch. Two distinct-class observations in
    one poll are guaranteed to become two separate contacts
    (association_over_time's class-incompatibility gate), so both fire
    CONTACT_DETECTED in the same `tick()` call -- exactly the "remaining
    events in the same batch" case.

    Contact ids are predicted rather than read back after the fact
    (`ContactStore._new_contact_id` is a monotonic per-store counter
    starting at 1, and this test uses a single fresh store -- `CONTACT_1`
    for the batch's first observation, `CONTACT_2` for its second, `CONTACT_3`
    for the follow-up poll's one observation), since `fail_on` must be
    configured before the call that assigns those ids."""
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    failing_text = "CONTACT_1: CONTACT_DETECTED, BMP-2, observed, currently visible."
    overlay_client = FakeOverlayClient(fail_on=frozenset({failing_text}))
    observations = [
        _make_observation(ownship, id="OBS_bmp", classification_raw="BMP-2"),
        _make_observation(ownship, id="OBS_truck", classification_raw="Ural truck"),
    ]

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource(observations)],
        overlay_client=overlay_client,  # type: ignore[arg-type]
    )

    returned = runner.run_once()

    # Both observations were still collected and ingested -- a failed push
    # for the first event's line did not drop anything already gathered
    # this poll.
    assert returned == observations
    assert len(runner.store.contacts) == 2
    assert len(runner.store.events) == 2
    assert runner.last_t_sim == ownship.t_sim
    # The failing push never landed; the *other* event in the same batch
    # still got pushed -- the failure did not skip the rest of the batch.
    assert overlay_client.pushed == [
        "CONTACT_2: CONTACT_DETECTED, Ural truck, observed, currently visible."
    ]

    # The next poll's pushes proceed normally -- one failure does not wedge
    # the overlay client for subsequent polls.
    runner.sources = [
        FakeSource(
            [
                _make_observation(
                    ownship, id="OBS_2", classification_raw="Mi-8 helicopter"
                )
            ]
        )
    ]
    runner.run_once()
    assert overlay_client.pushed == [
        "CONTACT_2: CONTACT_DETECTED, Ural truck, observed, currently visible.",
        "CONTACT_3: CONTACT_DETECTED, Mi-8 helicopter, observed, currently visible.",
    ]


def test_console_runner_prints_a_periodic_contact_count_line() -> None:
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    output = io.StringIO()

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship)])],
        output=output,
    )

    runner.run_once()

    assert "contacts=1" in output.getvalue()
    assert "observations=1" in output.getvalue()


# --- BL-7: mission_phase_tracker threading through run_once -----------------


def test_console_runner_updates_mission_phase_tracker_on_the_poll_thread() -> None:
    """`--mission-understanding` (BL-7): `run_once` calls `mission_phase_
    tracker.update()` with ownship's position on every poll, when a tracker
    is configured -- the only place this field is ever mutated."""
    telemetry = _telemetry_dict()  # position_x_m=5000.0, position_z_m=8000.0
    data = MissionUnderstandingData(
        phases=(),
        route=(
            CompactRoutePoint(
                index=0,
                x=5000.0,
                y=8000.0,
                place_name=None,
                epistemic_status="FACT",
                basis=(),
            ),
        ),
    )
    tracker = MissionPhaseTracker(data=data)
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([])],
        mission_phase_tracker=tracker,
    )

    assert tracker.last_reached_waypoint_index == -1
    runner.run_once()
    assert tracker.last_reached_waypoint_index == 0


def test_console_runner_without_mission_phase_tracker_is_a_no_op() -> None:
    telemetry = _telemetry_dict()
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([])],
    )
    assert runner.mission_phase_tracker is None
    runner.run_once()
    assert runner.mission_phase_tracker is None


# --- Stage 6 regression: real sqlite3.Connection across the --console poll
# thread boundary -----------------------------------------------------------
#
# Every other test in this module (and in test_naked_eye_source.py /
# test_visibility.py) monkeypatches `visibility.line_of_sight_clear`, so
# `store.reader.sample_grid` is never actually called against a real
# connection -- exactly why the live thread-affinity bug
# (`sqlite3.ProgrammingError: SQLite objects created in a thread can only be
# used in that same thread`) was never caught by the suite. This section
# builds a real (empty-grid) world-model `.sqlite` with world-model's own
# `store.writer.open_for_build`, drives it through the actual
# `_run_console_poll_loop` `main()` uses for `--console` on a real background
# thread, and lets `NakedEyePerceptionSource` genuinely reach
# `line_of_sight_clear` -> `sample_grid` -> a real sqlite query on that
# thread -- the exact call chain from the traceback.


def _console_telemetry_dict() -> dict[str, Any]:
    return {
        "dcs_model_time_s": 200.0,
        "position_x_m": 0.0,
        "position_y_m": 500.0,
        "position_z_m": 0.0,
        "heading_true_rad": 0.0,
        "pitch_rad": 0.0,
        "bank_rad": 0.0,
        "altitude_msl_m": 500.0,
    }


def _t72_world_object() -> dict[str, Any]:
    # association.wgs84_to_dcs is monkeypatched to identity below, so
    # lat_deg/lon_deg pass straight through as x/z (mirrors
    # test_naked_eye_source.py's own fixture posture) -- 500 m dead ahead of
    # the ownship above, well within a T-72's naked-eye range threshold
    # (~3500 m) and FOV.
    return {
        "object_id": 1,
        "object_type": "t-72",
        "coalition": 1.0,
        "lat_deg": 500.0,
        "lon_deg": 0.0,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": False,
    }


class FakeConsoleAircraftClient:
    """Duck-typed `AircraftLayerClient` covering everything `_build_sources`'
    two concrete tiers call: telemetry (both tiers), world objects (both
    tiers), and Petrovich's HelperAI indication (Hybrid only -- returning
    `None` here means Hybrid stays silent, only NakedEye is exercised)."""

    def __init__(
        self, telemetry: dict[str, Any], world_objects: dict[str, Any]
    ) -> None:
        self._telemetry = telemetry
        self._world_objects = world_objects

    def get_telemetry_latest(self) -> dict[str, Any] | None:
        return self._telemetry

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        return self._world_objects

    def get_petrovich_indication_latest(self) -> dict[str, Any] | None:
        return None


@pytest.fixture(autouse=True)
def _identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


def test_console_poll_loop_uses_a_thread_local_world_model_connection(
    tmp_path: Path,
) -> None:
    """Regression test for the live-sortie finding: before the fix,
    `main()` opened `world_model_conn` on the main thread and handed it to
    `ConsolePerceptionRunner.sources`, which the background poll thread then
    queried -- `sqlite3.ProgrammingError` on the first poll that reached
    `NakedEyePerceptionSource`'s visibility check. `_run_console_poll_loop`
    now opens the connection and builds `sources` on the poll thread itself,
    so this must complete cleanly and actually ingest the T-72 observation
    into the store."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)  # real schema, no grid rows needed --
    conn.close()  # sample_grid's query is what must succeed thread-locally,
    # not any particular grid content.

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": [_t72_world_object()]}
    )
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    stop_event = threading.Event()

    # A long poll interval so exactly one run_once() completes: the test
    # thread stops the loop the moment it observes last_t_sim, well before
    # the poll thread's stop_event.wait(...) would let a second poll start.
    poll_thread = threading.Thread(
        target=_run_console_poll_loop,
        args=(runner, aircraft_client, "Syria", db_path, 10.0, stop_event),
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_t_sim is None and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert runner.last_t_sim == 200.0
    assert len(runner.store.observations) == 1
    (observation,) = runner.store.observations.values()
    assert observation.source == "naked_eye_visual_filtered"


# --- BL-5 live acceptance regression: the REPL thread must not read
# enrichment through the poll thread's `sqlite3.Connection` -----------------
#
# `ConsolePerceptionRunner.enrichment` (BL-3) is built on the poll thread and
# holds that thread's `world_model_conn`. Before the fix, `_run_console_repl`
# copied it straight into `Console.enrichment`, so any enrichment-aware
# command (`situation`/`position`/`place`/`show`/`contacts`/`find`) run from
# the REPL thread queried the poll thread's connection and raised
# `sqlite3.ProgrammingError` -- the exact live-sortie crash
# (`plans/bl5-tool-api/debug.md`). This drives the real
# `_run_console_poll_loop` on a background thread (same as the Stage 6 test
# above) and `_run_console_repl` on the calling thread (a *different* real
# thread than the poll loop, via pytest's own test thread), feeding it a
# `situation` command through a monkeypatched `sys.stdin` -- exactly the
# "situation" command the user typed live.


def test_repl_thread_builds_its_own_enrichment_connection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": [_t72_world_object()]}
    )
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_console_poll_loop,
        args=(runner, aircraft_client, "Syria", db_path, 10.0, stop_event),
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_ownship_state is None and time.monotonic() < deadline:
            time.sleep(0.02)
        assert runner.last_ownship_state is not None  # poll completed once

        output = io.StringIO()
        console = Console(store=runner.store, output=output)
        monkeypatch.setattr("sys.stdin", io.StringIO("situation\nposition\n"))

        # Before the fix, this raised sqlite3.ProgrammingError -- the poll
        # thread's connection was read from this (different) thread.
        _run_console_repl(runner, console, db_path, "Syria")
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    lines = output.getvalue().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        assert "requires live ownship telemetry" not in line


def test_console_runner_reprojects_relative_areas_before_ingest() -> None:
    # `plans/f10-command-vocabulary/plan.md` D2/D3: `run_once` must
    # re-project every ownship-anchored area onto *this* tick's telemetry
    # before ingesting/ticking contacts, so a scan area actually tracks the
    # nose rather than lagging one poll behind.
    telemetry = _telemetry_dict()  # heading_true_rad=0.0, x=5000.0, z=8000.0
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    store = ContactStore()
    area = store.add_area(
        center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=5000.0,
        level="watch",
        source="scan_area",
        relative_sector="ahead",
    )
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship)])],
        store=store,
    )

    runner.run_once()

    projected = next(a for a in store.areas if a.id == area.id)
    assert projected.center == GeoPosition(
        x=ownship.x, z=ownship.z, alt_m=ownship.alt_m
    )
    assert projected.wedge_deg == (0.0, 30.0)
