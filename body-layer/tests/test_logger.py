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
from typing import Any

from belief.contacts import ContactStore
from logger import ConsolePerceptionRunner, PerceptionLogger, format_observation_line
from perception.source import Observation, OwnshipState


def _telemetry_dict() -> dict[str, Any]:
    return {
        "dcs_model_time_s": 200.0,
        "position_x_m": 5000.0,
        "position_y_m": 400.0,
        "position_z_m": 8000.0,
        "heading_true_rad": 0.0,
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
    ownship: OwnshipState, *, id: str = "OBS_1", source: str = "proxy_heuristic"
) -> Observation:
    return Observation(
        id=id,
        contact_id=None,
        t_sim=ownship.t_sim,
        t_wall=0.0,
        source=source,
        classification_raw="BMP",
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
