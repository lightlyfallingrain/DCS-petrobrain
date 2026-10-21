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
import json
import logging
import math
import pathlib
import sqlite3
import sys
import threading
import time
import urllib.error
from pathlib import Path
from typing import Any, NoReturn

import pytest
from support.mock_aircraft_layer import MockAircraftLayerServer

import logger as logger_module
from aircraft_client import AircraftLayerError
from belief.attention import AttentionArea
from belief.audio_client import AudioAdapterError
from belief.console import Console
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from belief.mission_phase import (
    CompactRoutePoint,
    MissionPhaseTracker,
    MissionUnderstandingData,
)
from belief.sight_effector import GUIDANCE_UNIT_SWITCH_DELAY_S, GuidanceUnitState
from belief.tasks import TaskStore
from logger import (
    _SIGHT_WIDE_SEARCH_FAR_M,
    DEFAULT_SPEECH_LOG_PATH,
    LOOK_DIRECTION_FOV_HALF_DEG,
    ConsolePerceptionRunner,
    PerceptionLogger,
    _active_gaze,
    _apply_active_gaze,
    _build_sources,
    _commanded_or_default_sector,
    _format_gaze_line,
    _log_live_los_coverage_summary,
    _poll_transcripts,
    _push_gaze_line,
    _resolve_speech_log_path,
    _run_console_poll_loop,
    _run_console_repl,
    _run_crew_text_poll_loop,
    _search_sweep,
    _sight_in_regard_sweep,
    _sight_out_of_regard_sweep,
    _speech_log_sink,
    _split_sector_by_regard,
    _to_body_relative_steps,
    _warn_live_los_coverage_gap_once,
    format_observation_line,
    main,
)
from perception import association
from perception.forest import ForestOcclusion
from perception.gaze import FREE_SCAN_PLAN, ScanPlan, gaze_at
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.optics import SIGHT_NARROW_OPTIC, SIGHT_WIDE_OPTIC
from perception.source import DerivedWorldPosition, Observation, OwnshipState
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
        "altitude_agl_m": 350.0,
    }


class FakeAircraftClient:
    def __init__(self, telemetry: dict[str, Any] | None) -> None:
        self._telemetry = telemetry
        #: `plans/dcs-driven-los/plan.md` (X-B29) -- every `hour,
        #: fov_half_deg` pair `ConsolePerceptionRunner.run_once` has
        #: pushed, in order, for tests that want to assert on it.
        self.look_direction_pushes: list[tuple[int, int]] = []

    def get_telemetry_latest(self) -> dict[str, Any] | None:
        return self._telemetry

    def get_line_of_sight_latest(self) -> dict[str, Any] | None:
        return None

    def post_look_direction(self, hour: int, fov_half_deg: int) -> None:
        self.look_direction_pushes.append((hour, fov_half_deg))


class FakeSource:
    def __init__(self, observations: list[Observation]) -> None:
        self._observations = observations
        self.reset_count = 0

    def reset_for_new_mission(self) -> None:
        self.reset_count += 1

    def poll(self, now_sim: float, ownship_state: OwnshipState) -> list[Observation]:
        return self._observations


def _make_observation(
    ownship: OwnshipState,
    *,
    id: str = "OBS_1",
    source: str = "proxy_heuristic",
    classification_raw: str = "BMP",
    bearing_deg: float = 32.0,
    range_m: float = 3100.0,
) -> Observation:
    """`bearing_deg`/`range_m` default to every pre-existing caller's
    implied shared position -- added (BL-12 Stage 3) so a caller that
    needs a spatially *distinct* percept (not ambiguous against an
    existing contact's gate) can say so explicitly, rather than relying
    on every other observation in a test happening to share this
    fixture's one default position."""
    return Observation(
        id=id,
        contact_id=None,
        t_sim=ownship.t_sim,
        t_wall=0.0,
        source=source,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
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


def test_run_once_polls_no_source_while_on_the_ground() -> None:
    """`[[BL-B82]]`: ownship at or below `ON_GROUND_AGL_THRESHOLD_M` ->
    no source is polled at all, so a source that *would* have produced an
    observation this tick is simply never asked."""
    telemetry = {**_telemetry_dict(), "altitude_agl_m": 5.0}
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    observations = [_make_observation(ownship)]

    logger = PerceptionLogger(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource(observations)],
    )

    assert logger.run_once() == []


def test_run_once_resumes_polling_once_above_the_ground_threshold() -> None:
    """The gate is evaluated fresh every poll, not a one-shot latch --
    the same source produces nothing on the ground and something once
    ownship climbs."""
    ground_telemetry = {**_telemetry_dict(), "altitude_agl_m": 5.0}
    airborne_telemetry = {**_telemetry_dict(), "altitude_agl_m": 500.0}
    ownship = OwnshipState.from_telemetry_dict(airborne_telemetry)
    observations = [_make_observation(ownship)]
    source = FakeSource(observations)

    logger = PerceptionLogger(
        aircraft_client=FakeAircraftClient(ground_telemetry),  # type: ignore[arg-type]
        sources=[source],
    )
    assert logger.run_once() == []

    logger.aircraft_client._telemetry = airborne_telemetry  # type: ignore[attr-defined]
    lines = logger.run_once()

    assert len(lines) == 1
    assert "classification=BMP" in lines[0]


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


def test_console_runner_ingests_nothing_while_on_the_ground() -> None:
    """`[[BL-B82]]`: no source is polled this tick, so nothing is ingested
    -- a source producing an observation this poll is simply never asked,
    the same gate `PerceptionLogger.run_once` applies."""
    telemetry = {**_telemetry_dict(), "altitude_agl_m": 5.0}
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    observations = [_make_observation(ownship)]

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource(observations)],
    )

    returned = runner.run_once()

    assert returned == []
    assert runner.store.contacts == []
    assert runner.store.observations == {}


def test_console_runner_existing_belief_decays_but_is_not_wiped_on_the_ground() -> None:
    """Existing belief is kept while on the ground -- `self.store.tick`
    still runs unconditionally (it is the mechanism that ages/decays a
    contact), only *new* observations stop. A contact already in the
    store before a ground poll is still there after it."""
    airborne_telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(airborne_telemetry)
    store = ContactStore()
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(airborne_telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship)])],
        store=store,
    )
    runner.run_once()
    assert len(store.contacts) == 1

    ground_telemetry = {**_telemetry_dict(), "altitude_agl_m": 5.0}
    runner.aircraft_client._telemetry = ground_telemetry  # type: ignore[attr-defined]
    runner.sources = [FakeSource([])]
    runner.run_once()

    assert len(store.contacts) == 1


def test_console_runner_resumes_ingesting_once_above_the_ground_threshold() -> None:
    ground_telemetry = {**_telemetry_dict(), "altitude_agl_m": 5.0}
    airborne_telemetry = {**_telemetry_dict(), "altitude_agl_m": 500.0}
    ownship = OwnshipState.from_telemetry_dict(airborne_telemetry)
    source = FakeSource([_make_observation(ownship)])

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(ground_telemetry),  # type: ignore[arg-type]
        sources=[source],
    )
    runner.run_once()
    assert runner.store.contacts == []

    runner.aircraft_client._telemetry = airborne_telemetry  # type: ignore[attr-defined]
    runner.run_once()

    assert len(runner.store.contacts) == 1


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


def test_console_runner_group_trace_sink_defaults_to_none_and_is_a_true_noop() -> None:
    """`--group-trace` (`BL-12` amendment A4): `group_trace_sink` defaults
    to `None`, the same posture as `overlay_client` above, and `run_once`
    must not fail passing it straight through to `ContactStore.tick`."""
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship)])],
    )

    runner.run_once()

    assert runner.group_trace_sink is None


def test_console_runner_threads_group_trace_sink_into_store_tick() -> None:
    """`run_once` must pass its own `group_trace_sink` field to `self.
    store.tick`'s `group_trace_sink` keyword, not drop it on the floor --
    the one line this wiring actually adds. Spies on `ContactStore.tick`
    rather than engineering a real cluster-resolution scenario (`tests/
    test_groups.py` already owns that geometry), since what this module is
    responsible for is the plumbing, not `GroupStore.reconcile`'s own
    logic."""
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    received: list[Any] = []

    def fake_sink(record: Any) -> None:
        received.append(record)

    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([_make_observation(ownship)])],
        group_trace_sink=fake_sink,
    )
    original_tick = runner.store.tick
    tick_kwargs: list[Any] = []

    def spying_tick(*args: Any, **kwargs: Any) -> None:
        tick_kwargs.append(kwargs.get("group_trace_sink"))
        original_tick(*args, **kwargs)

    runner.store.tick = spying_tick  # type: ignore[method-assign]

    runner.run_once()

    assert tick_kwargs == [fake_sink]


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
    configured before the call that assigns those ids.

    **The follow-up poll's observation is given its own, distinct
    bearing/range (BL-12 Stage 3, 2026-10-12)** -- every other call here
    shares `_make_observation`'s default position by convenience, which
    this test does not care about (it is testing push-failure isolation,
    not ambiguity resolution), but Stage 3 does: at the shared default
    position, "Mi-8 helicopter" resolves to no `op_class`
    (`object_model.profile_for` does not recognise the keyword), so it is
    class-*unknown* rather than incompatible against both `CONTACT_1`
    (BMP-2) and `CONTACT_2` (Ural truck) -- genuinely ambiguous between
    them. Those two, at the same shared position, cluster into one group
    on the first poll's `tick()`, so Stage 3 branch 2 would fold this
    observation onto the nearest of them instead of founding `CONTACT_3`,
    which is not what this test is checking and would make the second
    assertion below fail for a reason unrelated to overlay-push
    isolation. A distinct position keeps the two questions separate."""
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
                    ownship,
                    id="OBS_2",
                    classification_raw="Mi-8 helicopter",
                    bearing_deg=200.0,
                    range_m=9000.0,
                )
            ]
        )
    ]
    runner.run_once()
    assert overlay_client.pushed == [
        "CONTACT_2: CONTACT_DETECTED, Ural truck, observed, currently visible.",
        "CONTACT_3: CONTACT_DETECTED, Mi-8 helicopter, observed, currently visible.",
    ]


# --- Cones 2C sortie finding: "show where Petrovich is looking" ------------
#
# The pilot could not judge two of the acceptance card's four blocks without
# this -- `_format_gaze_line`/`_push_gaze_line` are the overlay-facing read
# of `perception.gaze.gaze_at`, wired into both poll loops' existing
# per-poll overlay hook point.


def test_format_gaze_line_names_the_oclock_hour_in_free_scan() -> None:
    gaze = gaze_at(0.0, FREE_SCAN_PLAN)  # t_sim=0 -> SCAN_PLAN[0] == 12
    assert gaze.label == "12_oclock"

    line = _format_gaze_line(FREE_SCAN_PLAN, gaze)

    assert line == "Petrovich: looking 12 o'clock (free scan)"


def test_format_gaze_line_names_the_commanded_sector() -> None:
    plan = ScanPlan(commanded_sector="left", command_t_sim=0.0)
    gaze = gaze_at(0.0, plan)  # left's own legs start at 11 o'clock

    line = _format_gaze_line(plan, gaze)

    assert line == "Petrovich: looking 11 o'clock (commanded left scan)"


def test_format_gaze_line_names_a_commanded_legs_scan_generically() -> None:
    # A `commanded_legs`-only plan (Stage 5: a bare o'clock hour, or a
    # converted compass scan) has no single sector name to speak.
    plan = ScanPlan(commanded_sector=None, command_t_sim=0.0, commanded_legs=(1,))
    gaze = gaze_at(0.0, plan)

    line = _format_gaze_line(plan, gaze)

    assert line == "Petrovich: looking 1 o'clock (commanded scan)"


def test_push_gaze_line_pushes_once_and_is_a_no_op_on_no_change() -> None:
    overlay_client = FakeOverlayClient()

    # t_sim=0.0 and t_sim=1.0 both fall in FOCUS_DWELL_S's first 2 s window
    # (12 o'clock) -- the second call must not push a duplicate line.
    label_after_first = _push_gaze_line(
        overlay_client,
        FREE_SCAN_PLAN,
        0.0,
        None,  # type: ignore[arg-type]
    )
    label_after_second = _push_gaze_line(
        overlay_client,
        FREE_SCAN_PLAN,
        1.0,
        label_after_first,  # type: ignore[arg-type]
    )

    assert label_after_first == "12_oclock"
    assert label_after_second == label_after_first
    assert overlay_client.pushed == ["Petrovich: looking 12 o'clock (free scan)"]


def test_push_gaze_line_pushes_again_when_the_cone_changes() -> None:
    overlay_client = FakeOverlayClient()

    label = _push_gaze_line(
        overlay_client,
        FREE_SCAN_PLAN,
        0.0,
        None,  # type: ignore[arg-type]
    )
    # FOCUS_DWELL_S is 2.0 s -- t_sim=2.0 has stepped to the next cone (11).
    label = _push_gaze_line(
        overlay_client,
        FREE_SCAN_PLAN,
        2.0,
        label,  # type: ignore[arg-type]
    )

    assert label == "11_oclock"
    assert overlay_client.pushed == [
        "Petrovich: looking 12 o'clock (free scan)",
        "Petrovich: looking 11 o'clock (free scan)",
    ]


def test_push_gaze_line_failure_is_isolated_and_still_advances_the_label() -> None:
    # Same per-push isolation as the lifecycle-event overlay pushes: a
    # failed gaze push must not raise, and the dedup label must still
    # advance so a later successful push isn't suppressed by a stale label.
    failing_text = "Petrovich: looking 12 o'clock (free scan)"
    overlay_client = FakeOverlayClient(fail_on=frozenset({failing_text}))

    label = _push_gaze_line(
        overlay_client,
        FREE_SCAN_PLAN,
        0.0,
        None,  # type: ignore[arg-type]
    )

    assert label == "12_oclock"
    assert overlay_client.pushed == []


def test_console_runner_run_once_updates_scan_plan() -> None:
    telemetry = _telemetry_dict()
    ownship = OwnshipState.from_telemetry_dict(telemetry)
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[FakeSource([])],
    )
    assert runner.scan_plan == FREE_SCAN_PLAN

    runner.tasks.create(
        "scan_area",
        AttentionArea(
            id="AREA_1",
            center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
            radius_m=None,
            level="watch",
            source="scan_area",
            relative_sector="right",
        ),
        created_sim=ownship.t_sim,
        deadline_sim=ownship.t_sim + 60.0,
        reason="test",
    )
    runner.run_once()

    assert runner.scan_plan == ScanPlan(
        commanded_sector="right", command_t_sim=ownship.t_sim
    )


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
        "altitude_agl_m": 500.0,
    }


def _t72_world_object() -> dict[str, Any]:
    # association.wgs84_to_dcs is monkeypatched to identity below, so
    # lat_deg/lon_deg pass straight through as x/z (mirrors
    # test_naked_eye_source.py's own fixture posture) -- 500 m dead ahead of
    # the ownship above, well within a T-72's naked-eye range threshold
    # (~3500 m) and FOV. `unit_name` (`plans/bl11-stage4-fail-closed/
    # plan.md` step 4, `BL-11` Stage 4): the live-LOS join key -- gets one
    # so `FakeConsoleAircraftClient.get_line_of_sight_latest` below can
    # mark it clear and the fail-closed gate admits it, same as before
    # this plan.
    return {
        "object_id": 1,
        "object_type": "t-72",
        "coalition": 1.0,
        "lat_deg": 500.0,
        "lon_deg": 0.0,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": False,
        "unit_name": "unit_1",
    }


def _t72_world_object_no_live_verdict() -> dict[str, Any]:
    """Same geometry as `_t72_world_object` but with no `unit_name` at
    all (`test_naked_eye_source.py`'s own `unit_name=None` escape hatch)
    -- `FakeConsoleAircraftClient.get_line_of_sight_latest` then has no
    join key for this object, so the candidate reaches gate 4 with
    `live_los_clear is None` and is rejected fail-closed, incrementing
    `LiveLosCoverage.no_verdict`. Exists for the coverage-logging tests
    below, which need a real poll to actually produce a coverage gap."""
    return {**_t72_world_object(), "unit_name": None}


class FakeConsoleAircraftClient:
    """Duck-typed `AircraftLayerClient` covering everything `_build_sources`'
    two concrete tiers call: telemetry (both tiers), world objects (both
    tiers), and Petrovich's HelperAI indication (Hybrid only -- returning
    `None` here means Hybrid stays silent, only NakedEye is exercised).

    `plans/bl11-stage4-fail-closed/plan.md` step 4 (`BL-11` Stage 4):
    `get_line_of_sight_latest` synthesizes a working live-LOS join by
    default -- see `test_naked_eye_source.py`'s `FakeAircraftClient` for
    the full reasoning (duplicated here rather than shared)."""

    def __init__(
        self, telemetry: dict[str, Any], world_objects: dict[str, Any]
    ) -> None:
        self._telemetry = telemetry
        self._world_objects = world_objects
        #: `BL-15` Stage 1 -- `None` (the default) means no `onSimulationStart`
        #: has fired, same "not an error" empty-cache posture as a real
        #: `MissionStartCache`. Tests that exercise `_check_for_new_mission`'s
        #: wiring mutate this directly between/before driving the poll loop.
        self.mission_start_sequence: int | None = None
        #: `BL-15` Stage 3 -- the `theatre` field of the next `get_mission_
        #: start_latest` event, `None` by default (matching every existing
        #: Stage 1/2 test, which never cared about theatre switching).
        self.mission_start_theatre: str | None = None
        #: `BL-B66` (`plans/9k113-effectors/plan.md`) -- every
        #: `write_cockpit_switch` call this fake has recorded, oldest
        #: first.
        self.cockpit_switch_writes: list[tuple[int, int, float]] = []
        #: `BL-B66` Stage 4b -- `None` (the default) means no cockpit-
        #: switch sample has arrived yet, matching `get_cockpit_switch_
        #: state_latest`'s own pre-existing default. A test exercising the
        #: sight-position readback (`sight_az`/`sight_elev`) sets this
        #: directly between polls, the same way `mission_start_sequence`
        #: above is driven.
        self.cockpit_switch_state: dict[str, Any] | None = None
        #: `[[BL-B80]]` (`plans/9k113-sight-pointing/plan.md`) -- every
        #: `write_sight_target` call this fake has recorded, oldest first.
        self.sight_target_writes: list[tuple[float, float]] = []

    def get_telemetry_latest(self) -> dict[str, Any] | None:
        return self._telemetry

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        if "dcs_model_time_s" in self._world_objects:
            return self._world_objects
        return {**self._world_objects, "dcs_model_time_s": 0.0}

    def get_unit_velocity_latest(self) -> dict[str, Any] | None:
        return None

    def get_line_of_sight_latest(self) -> dict[str, Any] | None:
        objects = self._world_objects.get("objects", [])
        verdicts: dict[str, Any] = {}
        for obj in objects:
            name = obj.get("unit_name")
            if isinstance(name, str):
                verdicts[name] = {"building_clear": True, "terrain_clear": True}
        return {
            "dcs_model_time_s": self._world_objects.get("dcs_model_time_s", 0.0),
            "hour_used": None,
            "fov_half_deg_used": None,
            "verdicts": verdicts,
        }

    def get_firing_latest(self) -> dict[str, Any]:
        # `plans/emitter-visibility/plan.md` Stage B -- nobody-firing
        # default, same reasoning as `test_naked_eye_source.py`'s
        # `FakeAircraftClient.get_firing_latest`.
        return {
            "dcs_model_time_s": self._world_objects.get("dcs_model_time_s", 0.0),
            "received_wall_clock_s": 0.0,
            "active": {},
        }

    def post_look_direction(self, hour: int, fov_half_deg: int) -> None:
        pass

    def get_mission_start_latest(self) -> dict[str, Any] | None:
        if self.mission_start_sequence is None:
            return None
        return {
            "sequence": self.mission_start_sequence,
            "theatre": self.mission_start_theatre,
            "received_wall_clock_s": 0.0,
        }

    def get_petrovich_indication_latest(self) -> dict[str, Any] | None:
        return None

    def get_cockpit_switch_state_latest(self) -> dict[str, Any] | None:
        # `BL-B66` (`plans/9k113-effectors/plan.md`) -- `None` is the
        # ordinary startup state, same "not an error" posture as every
        # other `get_*` default on this fake; Stage 4b's tests drive
        # `self.cockpit_switch_state` directly.
        return self.cockpit_switch_state

    def write_cockpit_switch(self, device: int, cmd: int, value: float) -> None:
        # `BL-B66` -- recorded rather than a true no-op, so a test can
        # assert on the guidance-unit power-up sequence's actual writes.
        self.cockpit_switch_writes.append((device, cmd, value))

    def write_sight_target(self, az_cmd: float, elev_cmd: float) -> None:
        # `[[BL-B80]]` -- recorded rather than a true no-op, same reason
        # as `write_cockpit_switch` above.
        self.sight_target_writes.append((az_cmd, elev_cmd))


@pytest.fixture(autouse=True)
def _identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


def test_build_sources_wires_a_forest_occlusion_when_requested() -> None:
    """`plans/forest-occlusion/plan.md` Stage 2: `forest_occlusion=True`
    constructs one `ForestOcclusion` against the same `world_model_conn`/
    `theatre` `_build_sources` already received, and wires it into
    `NakedEyePerceptionSource` only (the scope/hybrid channel has no
    geometric gate chain for it to join, same reasoning as `trace_sink`)."""
    aircraft_client = FakeConsoleAircraftClient({}, {})
    conn = sqlite3.connect(":memory:")

    sources = _build_sources(
        aircraft_client,
        "Syria",
        conn,
        emit_mode="on_change",
        forest_occlusion=True,
    )

    naked_eye = next(s for s in sources if isinstance(s, NakedEyePerceptionSource))
    assert isinstance(naked_eye.forest, ForestOcclusion)
    assert naked_eye.forest.conn is conn
    assert naked_eye.forest.theatre == "Syria"


def test_build_sources_forest_defaults_off() -> None:
    """Omitting `forest_occlusion` entirely (the default) must be a true
    no-op, same contract as every other additive flag in this module."""
    aircraft_client = FakeConsoleAircraftClient({}, {})
    conn = sqlite3.connect(":memory:")

    sources = _build_sources(aircraft_client, "Syria", conn, emit_mode="on_change")

    naked_eye = next(s for s in sources if isinstance(s, NakedEyePerceptionSource))
    assert naked_eye.forest is None


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


# -- _search_sweep / _split_sector_by_regard / _commanded_or_default_sector
# / _sight_in_regard_sweep / _sight_out_of_regard_sweep
# (plans/9k113-narrow-search/plan.md) ---------------------------------------


def _ownship_for_search(
    *, alt_agl_m: float = 120.0, pitch_deg: float = 0.0, bank_deg: float = 0.0
) -> OwnshipState:
    return OwnshipState(
        t_sim=0.0,
        x=0.0,
        z=0.0,
        alt_m=500.0,
        heading_true_deg=0.0,
        pitch_deg=pitch_deg,
        bank_deg=bank_deg,
        alt_agl_m=alt_agl_m,
    )


def test_search_sweep_is_empty_for_a_free_scan() -> None:
    assert _search_sweep(FREE_SCAN_PLAN, _ownship_for_search()) == []


def test_search_sweep_is_centred_on_the_commanded_sectors_own_centre() -> None:
    """Amendment 2 -- the pre-existing defect this fixes: before it,
    `search_pattern` had no centre parameter at all and this function
    discarded the centre it unpacked, so `left`/`right`/`full` all swept
    around 0 deg (dead ahead) regardless of which sector was commanded.
    `left`'s own centre is -60 deg (`SECTOR_WEDGE_DEG`)."""
    plan = ScanPlan(commanded_sector="left", command_t_sim=0.0)
    pattern = _search_sweep(plan, _ownship_for_search())
    azimuths = [azimuth for azimuth, _ in pattern]
    # Every step sits near -60 (the sector's own 15 deg half-width,
    # `MAX_SEARCH_SECTOR_HALF_WIDTH_DEG`), never near 0 (dead ahead) --
    # the defect this fix closes would have centred this sweep on 0.0.
    assert all(-75.0 <= azimuth <= -45.0 for azimuth in azimuths)
    assert all(azimuth < -10.0 for azimuth in azimuths)


def test_search_sweep_ahead_is_unchanged_by_the_centre_fix() -> None:
    """`ahead`'s own centre is 0 deg, so this is the one sector the
    pre-existing defect was harmless for -- the fix is a true no-op here."""
    plan = ScanPlan(commanded_sector="ahead", command_t_sim=0.0)
    pattern = _search_sweep(plan, _ownship_for_search())
    azimuths = [azimuth for azimuth, _ in pattern]
    assert all(-15.0 <= azimuth <= 15.0 for azimuth in azimuths)


class TestSplitSectorByRegard:
    """Pure geometry -- `plans/9k113-narrow-search/plan.md` Stage 2.
    Worked against `SECTOR_WEDGE_DEG` and `regard_half_deg=60.0`, exactly
    the plan's own worked example."""

    def test_ahead_is_fully_inside_regard(self) -> None:
        in_span, out_spans = _split_sector_by_regard(0.0, 30.0, 60.0)
        assert in_span == (0.0, 30.0)
        assert out_spans == []

    def test_left_splits_into_one_in_span_and_one_out_span(self) -> None:
        in_span, out_spans = _split_sector_by_regard(-60.0, 30.0, 60.0)
        assert in_span == (-45.0, 15.0)
        assert out_spans == [(-75.0, 15.0)]

    def test_right_splits_into_one_in_span_and_one_out_span(self) -> None:
        in_span, out_spans = _split_sector_by_regard(60.0, 30.0, 60.0)
        assert in_span == (45.0, 15.0)
        assert out_spans == [(75.0, 15.0)]

    def test_full_splits_into_one_in_span_and_two_out_spans(self) -> None:
        in_span, out_spans = _split_sector_by_regard(0.0, 90.0, 60.0)
        assert in_span == (0.0, 60.0)
        assert out_spans == [(-75.0, 15.0), (75.0, 15.0)]

    def test_a_span_entirely_outside_regard_has_no_in_span(self) -> None:
        in_span, out_spans = _split_sector_by_regard(90.0, 10.0, 60.0)
        assert in_span is None
        assert out_spans == [(90.0, 10.0)]


class TestCommandedOrDefaultSector:
    def test_a_commanded_sector_is_respected_at_its_own_width(self) -> None:
        """`ahead`'s own 30 deg half-width is never widened to the sight's
        full regard -- only the no-commanded-sector default does that."""
        plan = ScanPlan(commanded_sector="ahead", command_t_sim=0.0)
        assert _commanded_or_default_sector(plan, 60.0) == (0.0, 30.0)

    def test_no_commanded_sector_defaults_to_the_full_regard_ahead(self) -> None:
        assert _commanded_or_default_sector(FREE_SCAN_PLAN, 60.0) == (0.0, 60.0)


class TestSightInRegardSweep:
    def test_default_sector_wide_sweep_spans_the_full_regard(self) -> None:
        """With nothing commanded, the wide leg's own sweep reaches out to
        the full +-60 deg regard -- requirement 2's "flight direction as
        normal default", amendment 2's "default search width ... is the
        full ±60° regard"."""
        pattern = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            _ownship_for_search(),
            optic=SIGHT_WIDE_OPTIC,
            near_m=2_333.0,
            far_m=5_647.0,
        )
        azimuths = [azimuth for azimuth, _ in pattern]
        assert min(azimuths) < -50.0
        assert max(azimuths) > 50.0

    def test_left_sector_sweep_is_confined_to_its_own_in_regard_sub_span(
        self,
    ) -> None:
        """`left`'s in-regard sub-span is `(-45, 15)` (`TestSplitSectorByRegard`
        above) -- every step stays within it, never reaching `left`'s own
        full `(-60, 30)` span."""
        plan = ScanPlan(commanded_sector="left", command_t_sim=0.0)
        pattern = _sight_in_regard_sweep(
            plan,
            _ownship_for_search(),
            optic=SIGHT_NARROW_OPTIC,
            near_m=5_647.0,
            far_m=13_556.0,
        )
        azimuths = [azimuth for azimuth, _ in pattern]
        assert all(-60.0 <= azimuth <= -30.0 for azimuth in azimuths)


class TestSightInRegardSweepElevation:
    """Security required fix (`plans/9k113-narrow-search/security-review.md`):
    `search_pattern`'s elevation is pure range/altitude geometry
    (`atan2(altitude_agl_m, range_m)`) with no awareness of the sight's own
    `regard_elevation_down_deg=-15.0`. At this feature's own shared near
    edge (`SIGHT_SEARCH_NEAR_M`) that geometry reaches -23.2 deg at 1000 m
    AGL -- 8.2 deg past the limit, and an ordinary cruise/orbit altitude,
    not a stress case (the review's own table). The pre-existing `within_
    field_of_regard` invariant tests (`TestSightingDwellCycle`'s idle-aim
    test, `TestIdleAimInvariant`) never caught this because they pass no
    `sight_*_search` sequences at all, which falls straight through to
    `_idle_sight_rest` and never calls `search_pattern` -- these drive the
    real, production near/far-edge wiring instead, at an altitude the
    review's table names as the one that fails unfiltered."""

    _ALT_AGL_M = 1000.0  # 8.2 deg past -15 deg down-regard at the near edge, unfiltered

    def _legs(
        self, alt_agl_m: float
    ) -> tuple[
        list[tuple[float, float]], list[tuple[float, float]], list[tuple[float, float]]
    ]:
        """The same three in-regard legs `PerceptionLogger.run_once` builds
        (`logger.py`'s `sight_wide_search=`/`sight_narrow_near_search=`/
        `sight_narrow_far_search=` wiring) -- same near/far edges, so this
        exercises the real production geometry, not a synthetic stand-in."""
        from belief.optic_policy import (
            SIGHT_SEARCH_FAR_M,
            SIGHT_SEARCH_MID_M,
            SIGHT_SEARCH_NEAR_M,
        )

        ownship = _ownship_for_search(alt_agl_m=alt_agl_m)
        wide = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            ownship,
            optic=SIGHT_WIDE_OPTIC,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=_SIGHT_WIDE_SEARCH_FAR_M,
        )
        narrow_near = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            ownship,
            optic=SIGHT_NARROW_OPTIC,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=SIGHT_SEARCH_MID_M,
        )
        narrow_far = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            ownship,
            optic=SIGHT_NARROW_OPTIC,
            near_m=SIGHT_SEARCH_MID_M,
            far_m=SIGHT_SEARCH_FAR_M,
        )
        return wide, narrow_near, narrow_far

    def test_wide_leg_at_1000m_agl_stays_within_regard(self) -> None:
        from perception.optics import within_field_of_regard

        wide, _, _ = self._legs(self._ALT_AGL_M)
        assert wide  # the near edge is still reachable after filtering, not emptied
        assert all(within_field_of_regard(SIGHT_WIDE_OPTIC, az, el) for az, el in wide)

    def test_narrow_near_leg_at_1000m_agl_stays_within_regard(self) -> None:
        from perception.optics import within_field_of_regard

        _, narrow_near, _ = self._legs(self._ALT_AGL_M)
        assert narrow_near
        assert all(
            within_field_of_regard(SIGHT_NARROW_OPTIC, az, el) for az, el in narrow_near
        )

    def test_narrow_far_leg_at_1000m_agl_stays_within_regard(self) -> None:
        from perception.optics import within_field_of_regard

        _, _, narrow_far = self._legs(self._ALT_AGL_M)
        assert narrow_far
        assert all(
            within_field_of_regard(SIGHT_NARROW_OPTIC, az, el) for az, el in narrow_far
        )

    def test_the_unfiltered_geometry_really_does_reach_past_the_down_limit(
        self,
    ) -> None:
        """Pins the premise the three tests above guard against, by calling
        `search_pattern` directly (the function `_sight_in_regard_sweep`
        wraps and filters) rather than `_sight_in_regard_sweep` itself --
        if this ever stops failing, the fix above has nothing left to do
        and should be revisited, not silently kept as dead code."""
        from belief.optic_policy import SIGHT_SEARCH_NEAR_M, search_pattern
        from perception.optics import within_field_of_regard

        unfiltered = search_pattern(
            center_azimuth_deg=0.0,
            sector_half_width_deg=60.0,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=_SIGHT_WIDE_SEARCH_FAR_M,
            altitude_agl_m=self._ALT_AGL_M,
            fov_full_width_deg=(SIGHT_WIDE_OPTIC.fov_half_angle_deg or 0.0) * 2.0,
            max_half_width_deg=60.0,
        )
        assert any(
            not within_field_of_regard(SIGHT_WIDE_OPTIC, az, el)
            for az, el in unfiltered
        )

    @pytest.mark.parametrize("alt_agl_m", [120.0, 1000.0])
    def test_a_multi_poll_cycle_never_commits_an_out_of_regard_aim(
        self, alt_agl_m: float
    ) -> None:
        """End-to-end: the three real legs built the way `run_once` builds
        them, driven through `decide()` for several polls -- enough to
        cycle `wide -> narrow_near -> narrow_far -> wide` more than once --
        checking the *committed* `(azimuth, elevation)` on each returned
        `OpticDecision`, not just the raw pattern. 120 m AGL is this
        feature's own existing test default (comfortably under the ~625 m
        threshold, so this also pins "the fix is a no-op at the altitude
        every other test in this module already uses"); 1000 m AGL is the
        altitude the security review measured as failing unfiltered."""
        from belief.optic_policy import OpticPhase, OpticState, decide
        from perception.optics import within_field_of_regard

        wide, narrow_near, narrow_far = self._legs(alt_agl_m)
        state = OpticState(
            phase=OpticPhase.SIGHTING,
            phase_started_sim=0.0,
            home_phase=OpticPhase.SIGHTING,
        )
        now_sim = 0.0
        for _ in range(12):
            state, decision = decide(
                state,
                now_sim=now_sim,
                scan_cycle_period_s=16.0,
                targets=[],
                steady=True,
                sight_wide_search=wide,
                sight_narrow_near_search=narrow_near,
                sight_narrow_far_search=narrow_far,
            )
            assert decision.look_azimuth_deg is not None
            assert decision.look_elevation_deg is not None
            assert within_field_of_regard(
                decision.optic,
                decision.look_azimuth_deg,
                decision.look_elevation_deg,
            )
            # Comfortably past SEARCH_STEP_S (0.8) each poll, same spacing
            # `TestSearchCycle` in test_optic_policy.py already uses, for
            # the same float-drift reason its own docstring gives.
            now_sim += 1.0


class TestSightInRegardSweepBoresightRelative:
    """F5 (`docs/acceptance/2026-10-20-sortie-feedback.md`): the 9K113's
    `regard_*` limits are relative to the airframe's own boresight, not to
    the ground -- *"nose low position at high altitude would allow a near
    scan... it is not about distance, but angles relative to boresight."*
    `TestSightInRegardSweepElevation` above pins the *level-flight* case
    (an altitude threshold); these pin that the same geometry is actually
    pitch/bank-dependent, not altitude-dependent, which is the defect F5
    reports against `bb6364b0`'s elevation fix."""

    def test_nose_down_brings_the_1000m_near_band_back_into_regard(self) -> None:
        """The exact case `TestSightInRegardSweepElevation` pins as
        out-of-regard at level flight (-23.2 deg, 8.2 deg past the -15 deg
        down limit) -- 10 deg of nose-down pitch is enough to bring it back
        inside, the user's own worked example."""
        from belief.optic_policy import SIGHT_SEARCH_NEAR_M, search_pattern
        from perception.optics import within_field_of_regard

        fov_full_width_deg = (SIGHT_WIDE_OPTIC.fov_half_angle_deg or 0.0) * 2.0
        # `sector_half_width_deg=1.0` is well under half the optic's own
        # field of view, so `search_pattern`'s own step-centring collapses
        # to a single azimuth-0 step (`_step_centres_deg`'s `steps_across
        # == 1` branch) -- and `near_m`/`far_m` one metre apart collapses
        # its elevation bands to one too, so this is a single, exactly-
        # known `(0.0, depression)` step, not an average over several.
        raw_steps = search_pattern(
            center_azimuth_deg=0.0,
            sector_half_width_deg=1.0,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=SIGHT_SEARCH_NEAR_M + 1.0,
            altitude_agl_m=1000.0,
            fov_full_width_deg=fov_full_width_deg,
        )
        assert raw_steps == [(0.0, pytest.approx(-23.2, abs=0.1))]

        level = _to_body_relative_steps(
            raw_steps, _ownship_for_search(alt_agl_m=1000.0)
        )
        nose_down = _to_body_relative_steps(
            raw_steps, _ownship_for_search(alt_agl_m=1000.0, pitch_deg=-10.0)
        )

        assert not within_field_of_regard(SIGHT_WIDE_OPTIC, *level[0])
        assert within_field_of_regard(SIGHT_WIDE_OPTIC, *nose_down[0])
        assert nose_down[0][1] == pytest.approx(-13.2, abs=0.1)

    def test_nose_up_pushes_a_near_step_out_of_regard_at_low_altitude(self) -> None:
        """The other half of the same F5 example -- *"Nose high at low alt
        would limit near scan"*: a step well inside the down limit at level
        flight (-10 deg, comfortably clear of the -15 deg boundary) is
        pushed past it by 10 deg of nose-up pitch alone, altitude
        unchanged. Synthetic `near_m` (not `SIGHT_SEARCH_NEAR_M`) -- chosen
        only to land the level-flight depression at a clean -10 deg so the
        boundary crossing is unambiguous; the production near edge is
        shallow enough at 120 m AGL that no plausible pitch pushes it out,
        which is exactly why this is a synthetic case, not a repeat of the
        production one."""
        from belief.optic_policy import search_pattern
        from perception.optics import within_field_of_regard

        alt_agl_m = 120.0
        near_m = alt_agl_m / math.tan(math.radians(10.0))  # -10 deg depression, level
        fov_full_width_deg = (SIGHT_WIDE_OPTIC.fov_half_angle_deg or 0.0) * 2.0
        raw_steps = search_pattern(
            center_azimuth_deg=0.0,
            sector_half_width_deg=1.0,
            near_m=near_m,
            far_m=near_m + 1.0,
            altitude_agl_m=alt_agl_m,
            fov_full_width_deg=fov_full_width_deg,
        )
        assert raw_steps == [(0.0, pytest.approx(-10.0, abs=0.05))]

        level = _to_body_relative_steps(
            raw_steps, _ownship_for_search(alt_agl_m=alt_agl_m)
        )
        nose_up = _to_body_relative_steps(
            raw_steps, _ownship_for_search(alt_agl_m=alt_agl_m, pitch_deg=10.0)
        )

        assert within_field_of_regard(SIGHT_WIDE_OPTIC, *level[0])
        assert not within_field_of_regard(SIGHT_WIDE_OPTIC, *nose_up[0])
        assert nose_up[0][1] == pytest.approx(-20.0, abs=0.05)

    def test_bank_rotates_an_out_of_regard_step_back_into_regard(self) -> None:
        """A step 2 deg past the down limit at wings-level (-17 deg, azimuth
        0) is carried by 30 deg of bank into a direction that is both
        shallower and off to one side -- (az~8.7, el~-14.7) -- demonstrating
        that the limit check moves with the airframe's roll axis, not just
        its pitch axis."""
        from perception.optics import within_field_of_regard

        raw_steps = [(0.0, -17.0)]
        level = _to_body_relative_steps(raw_steps, _ownship_for_search())
        banked = _to_body_relative_steps(raw_steps, _ownship_for_search(bank_deg=30.0))

        assert not within_field_of_regard(SIGHT_WIDE_OPTIC, *level[0])
        assert within_field_of_regard(SIGHT_WIDE_OPTIC, *banked[0])
        assert banked[0][0] == pytest.approx(8.69, abs=0.05)
        assert banked[0][1] == pytest.approx(-14.67, abs=0.05)

    def test_level_flight_is_unchanged_by_the_conversion(self) -> None:
        """Pitch/bank both `0.0` (`_ownship_for_search`'s own default) must
        reproduce `search_pattern`'s raw output exactly -- the conversion
        introduced by this fix is a true no-op at wings-level, unbanked
        flight, which is what every pre-existing test in this module (all
        written before F5) already assumed."""
        from belief.optic_policy import SIGHT_SEARCH_NEAR_M, search_pattern

        fov_full_width_deg = (SIGHT_WIDE_OPTIC.fov_half_angle_deg or 0.0) * 2.0
        raw_steps = search_pattern(
            center_azimuth_deg=0.0,
            sector_half_width_deg=60.0,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=_SIGHT_WIDE_SEARCH_FAR_M,
            altitude_agl_m=120.0,
            fov_full_width_deg=fov_full_width_deg,
            max_half_width_deg=60.0,
        )
        converted = _to_body_relative_steps(
            raw_steps, _ownship_for_search(alt_agl_m=120.0)
        )
        for (raw_az, raw_el), (conv_az, conv_el) in zip(
            raw_steps, converted, strict=True
        ):
            assert conv_az == pytest.approx(raw_az, abs=1e-6)
            assert conv_el == pytest.approx(raw_el, abs=1e-6)

    def test_sight_in_regard_sweep_itself_recovers_the_near_band_when_nose_down(
        self,
    ) -> None:
        """End-to-end through the real call site, not just the shared
        conversion helper: `_sight_in_regard_sweep`'s own near-band leg
        (`SIGHT_SEARCH_NEAR_M`..`_SIGHT_WIDE_SEARCH_FAR_M`, the same `wide`
        leg `run_once` builds) gains at least one more in-regard step with
        10 deg of nose-down pitch at 1000 m AGL than it has at level
        flight -- the comparative form of the same claim the pure-geometry
        test above pins exactly."""
        level = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            _ownship_for_search(alt_agl_m=1000.0),
            optic=SIGHT_WIDE_OPTIC,
            near_m=2_333.0,
            far_m=_SIGHT_WIDE_SEARCH_FAR_M,
        )
        nose_down = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            _ownship_for_search(alt_agl_m=1000.0, pitch_deg=-10.0),
            optic=SIGHT_WIDE_OPTIC,
            near_m=2_333.0,
            far_m=_SIGHT_WIDE_SEARCH_FAR_M,
        )
        assert len(nose_down) > len(level)

    def test_search_sweep_binocular_aim_is_also_rotated(self) -> None:
        """`_search_sweep` (the binocular search band) has no field of
        regard to filter against, but its aim still has to agree with every
        other optic's body-relative convention -- F5's own "binoculars have
        no regard, so the conversion matters there only for pointing the
        right way." A banked aircraft's binocular sweep must differ from
        its level-flight one."""
        plan = ScanPlan(commanded_sector="ahead", command_t_sim=0.0)
        level = _search_sweep(plan, _ownship_for_search())
        banked = _search_sweep(plan, _ownship_for_search(bank_deg=30.0))
        assert level != banked

    def test_sight_out_of_regard_sweep_aim_is_also_rotated(self) -> None:
        """Same claim as `_search_sweep` above, for the commanded-sector
        remainder a narrow sight can't reach (`_sight_out_of_regard_sweep`)."""
        plan = ScanPlan(commanded_sector="full", command_t_sim=0.0)
        level = _sight_out_of_regard_sweep(plan, _ownship_for_search())
        banked = _sight_out_of_regard_sweep(plan, _ownship_for_search(bank_deg=30.0))
        assert level != banked


class TestSightWideSearchFarM:
    """`_SIGHT_WIDE_SEARCH_FAR_M` -- `docs/acceptance/2026-10-20-sortie-
    feedback.md` F4: the wide sweep's far edge is wide's own useful reach,
    not `SIGHT_SEARCH_MID_M` (binoculars' own boundary, which the near
    band and the wide leg used to share)."""

    def test_matches_the_reference_vehicles_presence_reach_through_wide(
        self,
    ) -> None:
        from belief.optic_policy import SIGHT_SEARCH_NEAR_M

        expected = SIGHT_SEARCH_NEAR_M * SIGHT_WIDE_OPTIC.presence_range_mult
        assert _SIGHT_WIDE_SEARCH_FAR_M == pytest.approx(expected)

    def test_reaches_further_than_the_old_shared_near_band_boundary(
        self,
    ) -> None:
        from belief.optic_policy import SIGHT_SEARCH_MID_M

        assert _SIGHT_WIDE_SEARCH_FAR_M > SIGHT_SEARCH_MID_M

    def test_stays_inside_the_player_bubble(self) -> None:
        assert _SIGHT_WIDE_SEARCH_FAR_M < association.PLAYER_BUBBLE_RADIUS_M

    def test_presence_reach_is_already_the_farther_of_presence_and_class(
        self,
    ) -> None:
        """Falsifies the derivation's own claim rather than assuming it:
        `tier_ranges`' chained `min()`s make a class threshold never
        exceed its own optic's presence threshold, for the reference
        vehicle and `SIGHT_WIDE_OPTIC` this constant is built from -- so
        taking the presence reach alone already is "the farther of
        detection and classification reach"."""
        from perception.object_model import (
            apparent_extent_m,
            distinctiveness_of,
            profile_for,
        )
        from perception.visibility import tier_ranges

        profile = profile_for("T-72")
        extent = apparent_extent_m(profile, None)
        distinctiveness = distinctiveness_of(profile)
        presence_m, class_m, _type_m = tier_ranges(
            presence_size_m=profile.size_m,
            recognition_extent_m=extent,
            optic=SIGHT_WIDE_OPTIC,
            distinctiveness=distinctiveness,
        )
        assert class_m <= presence_m

    def test_wide_sweep_reaches_a_shallower_elevation_than_the_old_boundary(
        self,
    ) -> None:
        """`_sight_in_regard_sweep` itself, not the call site: with the
        production far edge it produces a shallower (less negative, i.e.
        further-reaching) elevation than it would with the old shared
        `SIGHT_SEARCH_MID_M` boundary, for the same near edge and
        altitude. Does **not** prove `run_once` actually passes this far
        edge -- see `test_run_once_passes_the_wide_legs_own_far_edge`
        below for that."""
        from belief.optic_policy import SIGHT_SEARCH_MID_M, SIGHT_SEARCH_NEAR_M

        old_pattern = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            _ownship_for_search(),
            optic=SIGHT_WIDE_OPTIC,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=SIGHT_SEARCH_MID_M,
        )
        new_pattern = _sight_in_regard_sweep(
            FREE_SCAN_PLAN,
            _ownship_for_search(),
            optic=SIGHT_WIDE_OPTIC,
            near_m=SIGHT_SEARCH_NEAR_M,
            far_m=_SIGHT_WIDE_SEARCH_FAR_M,
        )
        assert new_pattern[0][1] > old_pattern[0][1]

    def test_run_once_passes_the_wide_legs_own_far_edge(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Pins the call-site wiring itself: `run_once`'s own `decide_
        optic(...)` call is made with `far_m=_SIGHT_WIDE_SEARCH_FAR_M` for
        the `optic=SIGHT_WIDE_OPTIC` leg, not `SIGHT_SEARCH_MID_M` (the old
        shared boundary) -- the one line `docs/acceptance/
        2026-10-20-sortie-feedback.md` F4 asked to change. Computed fresh
        every poll regardless of sight phase (the same posture `search`'s
        own unconditional computation already has), so no `SIGHTING`
        dwell needs to be set up to observe it -- a default runner's very
        first poll already makes the call."""
        real_sweep = logger_module._sight_in_regard_sweep
        captured_far_m: list[float] = []

        def spy(
            *args: object, optic: object, far_m: float, **kwargs: object
        ) -> list[tuple[float, float]]:
            if optic is SIGHT_WIDE_OPTIC:
                captured_far_m.append(far_m)
            return real_sweep(*args, optic=optic, far_m=far_m, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(logger_module, "_sight_in_regard_sweep", spy)

        runner = ConsolePerceptionRunner(
            aircraft_client=FakeAircraftClient(_telemetry_dict()),  # type: ignore[arg-type]
            sources=[],
        )
        runner.run_once()

        assert captured_far_m == [_SIGHT_WIDE_SEARCH_FAR_M]


class TestSightOutOfRegardSweep:
    def test_no_commanded_sector_never_has_an_out_of_regard_remainder(self) -> None:
        """The synthesized default sector is exactly the regard width, by
        construction -- it can never have anything left outside it."""
        assert _sight_out_of_regard_sweep(FREE_SCAN_PLAN, _ownship_for_search()) == []

    def test_ahead_never_has_an_out_of_regard_remainder(self) -> None:
        """`ahead`'s own 30 deg span is fully inside the 60 deg regard."""
        plan = ScanPlan(commanded_sector="ahead", command_t_sim=0.0)
        assert _sight_out_of_regard_sweep(plan, _ownship_for_search()) == []

    def test_left_sweeps_the_one_out_of_regard_remainder(self) -> None:
        """`left`'s out-of-regard sub-span is `(-75, 15)` -- every step
        stays on that side, past the -60 deg regard boundary."""
        plan = ScanPlan(commanded_sector="left", command_t_sim=0.0)
        pattern = _sight_out_of_regard_sweep(plan, _ownship_for_search())
        azimuths = [azimuth for azimuth, _ in pattern]
        assert azimuths
        assert all(azimuth < -60.0 for azimuth in azimuths)

    def test_full_sweeps_both_out_of_regard_remainders(self) -> None:
        """`full`'s two remainder pieces, `(-75, 15)` and `(75, 15)` -- one
        list, both sides of the regard boundary represented."""
        plan = ScanPlan(commanded_sector="full", command_t_sim=0.0)
        pattern = _sight_out_of_regard_sweep(plan, _ownship_for_search())
        azimuths = [azimuth for azimuth, _ in pattern]
        assert any(azimuth < -60.0 for azimuth in azimuths)
        assert any(azimuth > 60.0 for azimuth in azimuths)


# -- _active_gaze / _apply_active_gaze (slice 2B; ScanPlan generalisation
# by 2C, plans/detection-cones-slice2/plan.md) ------------------------------


def _relative_area(area_id: str, relative_sector: str) -> AttentionArea:
    return AttentionArea(
        id=area_id,
        center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=None,
        level="watch",
        source="scan_area",
        relative_sector=relative_sector,  # type: ignore[arg-type]
    )


class _NoWorldObjectsClient:
    """Duck-typed stand-in carrying only the one method
    `NakedEyePerceptionSource.poll` needs -- always reports no snapshot, so
    `poll()` returns `[]` without needing a real `AircraftLayerClient`."""

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        return None


def _naked_eye_source() -> NakedEyePerceptionSource:
    return NakedEyePerceptionSource(
        aircraft_client=_NoWorldObjectsClient(),  # type: ignore[arg-type]
        theatre="Syria",
        world_model_conn=sqlite3.connect(":memory:"),
    )


def test_active_gaze_is_free_scan_with_no_pending_scan_task() -> None:
    assert _active_gaze(TaskStore()) == FREE_SCAN_PLAN


def test_active_gaze_resolves_a_pending_relative_sector_task() -> None:
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _relative_area("AREA_1", "left"),
        created_sim=3.0,
        deadline_sim=60.0,
        reason="scan-area",
    )

    plan = _active_gaze(tasks)

    assert plan == ScanPlan(commanded_sector="left", command_t_sim=3.0)


def test_active_gaze_ignores_a_cancelled_task() -> None:
    tasks = TaskStore()
    task = tasks.create(
        "scan_area",
        _relative_area("AREA_1", "ahead"),
        created_sim=0.0,
        deadline_sim=60.0,
        reason="scan-area",
    )
    tasks.cancel(task.id)

    assert _active_gaze(tasks) == FREE_SCAN_PLAN


def test_active_gaze_keeps_steering_a_succeeded_scan_task() -> None:
    # Cones 2C sortie fix: tick() resolves a scan_area task to "succeeded"
    # the instant any contact is seen in its area -- a commanded scan must
    # keep steering the gaze after that, not silently revert to free scan
    # (the sortie's "commanded scan left, still got reports from 12
    # o'clock" finding).
    tasks = TaskStore()
    task = tasks.create(
        "scan_area",
        _relative_area("AREA_1", "left"),
        created_sim=3.0,
        deadline_sim=60.0,
        reason="scan-area",
    )
    # Direct assignment rather than a real tick()/contact: the point under
    # test is _active_gaze's own status filter, not tick's resolution logic
    # (covered by test_tasks.py).
    task.status = "succeeded"

    plan = _active_gaze(tasks)

    assert plan == ScanPlan(commanded_sector="left", command_t_sim=3.0)


def test_active_gaze_keeps_steering_a_failed_scan_task() -> None:
    # Same fix, the deadline-timeout path: "failed" must not silently
    # revert to free scan either -- only an explicit cancel (or a newer
    # scan command) may end the mode.
    tasks = TaskStore()
    task = tasks.create(
        "scan_area",
        _relative_area("AREA_1", "right"),
        created_sim=3.0,
        deadline_sim=60.0,
        reason="scan-area",
    )
    task.status = "failed"

    plan = _active_gaze(tasks)

    assert plan == ScanPlan(commanded_sector="right", command_t_sim=3.0)


def test_active_gaze_picks_the_most_recently_created_pending_task() -> None:
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _relative_area("AREA_1", "ahead"),
        created_sim=0.0,
        deadline_sim=60.0,
        reason="scan-area",
    )
    tasks.create(
        "scan_area",
        _relative_area("AREA_2", "right"),
        created_sim=1.0,
        deadline_sim=60.0,
        reason="scan-area",
    )

    plan = _active_gaze(tasks)

    assert plan == ScanPlan(commanded_sector="right", command_t_sim=1.0)


# -- Stage 5 (plans/voice-command-completeness/plan.md Decision 5):
# compass-sector and relative_clock_hour tasks, and the absolute->relative
# heading conversion. --------------------------------------------------------


def _sector_area(area_id: str, sector: str) -> AttentionArea:
    return AttentionArea(
        id=area_id,
        center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=None,
        level="watch",
        source="scan_area",
        sector=sector,  # type: ignore[arg-type]
    )


def _clock_area(area_id: str, clock_hour: int) -> AttentionArea:
    return AttentionArea(
        id=area_id,
        center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=None,
        level="watch",
        source="scan_area",
        relative_clock_hour=clock_hour,
    )


def test_active_gaze_resolves_a_relative_clock_hour_task() -> None:
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _clock_area("AREA_1", 1),
        created_sim=3.0,
        deadline_sim=60.0,
        reason="scan-area",
    )

    plan = _active_gaze(tasks)

    assert plan == ScanPlan(
        commanded_sector=None, command_t_sim=3.0, commanded_legs=(1,)
    )


def test_active_gaze_was_previously_silently_skipping_a_compass_only_task() -> None:
    # The measured pre-existing defect this stage fixes: before Stage 5,
    # `_active_gaze` only ever read `task.area.relative_sector`, so a
    # compass-only task (`scan north`) fell through this filter entirely
    # and the function returned `FREE_SCAN_PLAN` even though a scan was
    # commanded and still active.
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _sector_area("AREA_1", "N"),
        created_sim=3.0,
        deadline_sim=60.0,
        reason="scan-area",
    )

    plan = _active_gaze(tasks, heading_true_deg=0.0)

    assert plan != FREE_SCAN_PLAN
    assert plan.commanded_legs is not None


def test_active_gaze_converts_a_compass_sector_to_relative_legs_using_heading() -> None:
    # Nose pointed north (heading 0): "scan north" should resolve to legs
    # centered on dead ahead (12 o'clock) -- 11, 12, 1.
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _sector_area("AREA_1", "N"),
        created_sim=0.0,
        deadline_sim=60.0,
        reason="scan-area",
    )

    plan = _active_gaze(tasks, heading_true_deg=0.0)

    assert plan == ScanPlan(
        commanded_sector=None, command_t_sim=0.0, commanded_legs=(11, 12, 1)
    )


def test_active_gaze_compass_conversion_tracks_current_heading() -> None:
    # Same commanded "scan north" task, but the nose is now pointed east
    # (heading 90) -- north is 90 degrees to the left of the nose, so the
    # resolved legs must shift accordingly (this is the "per tick, using
    # current heading" half of Decision 5).
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _sector_area("AREA_1", "N"),
        created_sim=0.0,
        deadline_sim=60.0,
        reason="scan-area",
    )

    plan_heading_0 = _active_gaze(tasks, heading_true_deg=0.0)
    plan_heading_90 = _active_gaze(tasks, heading_true_deg=90.0)

    assert plan_heading_0 != plan_heading_90
    assert plan_heading_0.commanded_legs == (11, 12, 1)
    # Relative bearing of true north with the nose on 90: 0 - 90 = -90 ->
    # dead left (9 o'clock), so the admitted legs center on 9.
    assert plan_heading_90.commanded_legs == (8, 9, 10)


def test_active_gaze_compass_conversion_handles_the_360_0_wrap() -> None:
    # Optional refinement, `plans/voice-command-completeness/review.md`:
    # Decision 2's own risk note named the 350/0/10 heading wrap as
    # unguarded -- the reviewer hand-verified `legs_within_wedge` directly
    # rather than through `_active_gaze`, and this file's existing compass
    # tests only cover heading 0 and heading 90, neither of which crosses
    # the 360/0 boundary the modulo arithmetic exists to handle. A
    # commanded "scan north" task must resolve to the same (11, 12, 1) legs
    # regardless of which side of the wrap the nose sits on.
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _sector_area("AREA_1", "N"),
        created_sim=0.0,
        deadline_sim=60.0,
        reason="scan-area",
    )

    plan_350 = _active_gaze(tasks, heading_true_deg=350.0)
    plan_0 = _active_gaze(tasks, heading_true_deg=0.0)
    plan_10 = _active_gaze(tasks, heading_true_deg=10.0)

    assert plan_350.commanded_legs == (11, 12, 1)
    assert plan_0.commanded_legs == (11, 12, 1)
    assert plan_10.commanded_legs == (11, 12, 1)
    assert plan_350 == plan_0 == plan_10


# --- attack run claims the gaze (plans/attack-run/plan.md Decision 9
# REVISED, Stage 5) -------------------------------------------------


def _contact_at_bearing_range(
    store: ContactStore, bearing_deg: float, range_m: float
) -> str:
    """Ingests one contact whose `Contact.last_position` resolves to the
    given true bearing/range from `(0, 0)` ownship (`implied_position`'s
    own formula, `belief.association_over_time`) and returns its minted
    id. `_active_gaze`'s attack-run branch reads `Contact.last_position`
    directly, unlike `CrewConsole`'s enrichment-mediated facts -- no
    `EnrichmentContext` stub needed here."""
    store.ingest(
        [
            Observation(
                id=f"OBS_{bearing_deg}_{range_m}",
                contact_id=None,
                t_sim=0.0,
                t_wall=0.0,
                source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
                classification_raw="BMP-2",
                bearing_deg=bearing_deg,
                range_m=range_m,
                ownship_at_observation=OwnshipState(
                    t_sim=0.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0
                ),
                derived_world_position=DerivedWorldPosition(
                    x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
                ),
                provenance="test_fixture",
                classification_level=2,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    return store.contacts[-1].id


def test_active_gaze_claims_a_fixed_look_at_the_engaged_attack_run_target() -> None:
    """Decision 9 REVISED -- *"an attack run fixes the look on the
    target"*, checked **before** the `scan_area` loop: a standing `scan
    left` command (registered here specifically because `_SECTOR_LEGS
    ["left"]` has no 12 -- the case that settled this decision) must be
    overridden while the run is engaged."""
    store = ContactStore()
    contact_id = _contact_at_bearing_range(store, bearing_deg=0.0, range_m=1000.0)
    tasks = TaskStore()
    tasks.create(
        "attack_target",
        None,
        created_sim=0.0,
        deadline_sim=float("inf"),
        reason="attack_target",
        contact_id=contact_id,
    )
    tasks.create(
        "scan_area",
        _relative_area("AREA_1", "left"),
        created_sim=0.0,
        deadline_sim=600.0,
        reason="scan-area",
    )
    ownship = OwnshipState(t_sim=1.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)

    plan = _active_gaze(
        tasks,
        ownship.heading_true_deg,
        store=store,
        ownship=ownship,
        attack_run_engaged=True,
    )

    assert plan == ScanPlan.fixed_look_at(azimuth_deg=0.0, elevation_deg=0.0)


def test_active_gaze_ignores_attack_run_when_not_engaged() -> None:
    """`attack_run_engaged=False` (selected but not `engage`d) must fall
    through to whatever is actually commanded -- the gaze claim tracks
    the run's *phase*, not the standing selection."""
    store = ContactStore()
    contact_id = _contact_at_bearing_range(store, bearing_deg=0.0, range_m=1000.0)
    tasks = TaskStore()
    tasks.create(
        "attack_target",
        None,
        created_sim=0.0,
        deadline_sim=float("inf"),
        reason="attack_target",
        contact_id=contact_id,
    )
    tasks.create(
        "scan_area",
        _relative_area("AREA_1", "left"),
        created_sim=0.0,
        deadline_sim=600.0,
        reason="scan-area",
    )
    ownship = OwnshipState(t_sim=1.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)

    plan = _active_gaze(
        tasks,
        ownship.heading_true_deg,
        store=store,
        ownship=ownship,
        attack_run_engaged=False,
    )

    assert plan == ScanPlan(commanded_sector="left", command_t_sim=0.0)


def test_active_gaze_attack_run_branch_is_a_true_noop_without_store_or_ownship() -> (
    None
):
    """`store`/`ownship` default to `None` so every existing call site
    that does not know about attack runs keeps working unchanged --
    `attack_run_engaged=True` with either missing must not raise and
    must fall through to the ordinary scan resolution."""
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _relative_area("AREA_1", "left"),
        created_sim=0.0,
        deadline_sim=600.0,
        reason="scan-area",
    )

    plan = _active_gaze(tasks, 0.0, attack_run_engaged=True)

    assert plan == ScanPlan(commanded_sector="left", command_t_sim=0.0)


class _RecordingSpeechWriter:
    """A `BeliefTruthLogWriter` double that records every `write_speech`
    call's kwargs -- `_speech_log_sink` has no pre-existing test, so this
    also covers the generic gaze/optic-forwarding behaviour this change
    did not intend to touch, not only the new `attack_run_fields`
    threading."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def write_speech(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def test_speech_log_sink_forwards_attack_run_fields() -> None:
    writer = _RecordingSpeechWriter()
    runner = ConsolePerceptionRunner(aircraft_client=None)  # type: ignore[arg-type]
    runner.last_t_sim = 5.0
    sink = _speech_log_sink(writer, runner)  # type: ignore[arg-type]

    sink(
        "Come left.",
        False,
        {
            "attack_run_target_contact_id": "CONTACT_1",
            "attack_run_tier": 1,
            "attack_run_azimuth_deg": -7.5,
            "attack_run_elevation_deg": 0.0,
        },
        None,
        None,
        None,
        None,
    )

    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["text"] == "Come left."
    assert call["attack_run_target_contact_id"] == "CONTACT_1"
    assert call["attack_run_tier"] == 1
    assert call["attack_run_azimuth_deg"] == -7.5
    assert call["attack_run_elevation_deg"] == 0.0


def test_speech_log_sink_omits_attack_run_fields_for_an_ordinary_line() -> None:
    writer = _RecordingSpeechWriter()
    runner = ConsolePerceptionRunner(aircraft_client=None)  # type: ignore[arg-type]
    runner.last_t_sim = 5.0
    sink = _speech_log_sink(writer, runner)  # type: ignore[arg-type]

    sink("Scanning right.", False, None, None, None, None, None)

    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["text"] == "Scanning right."
    assert call["attack_run_target_contact_id"] is None
    assert call["attack_run_tier"] is None
    assert call["attack_run_azimuth_deg"] is None
    assert call["attack_run_elevation_deg"] is None


def test_speech_log_sink_forwards_ownship_attitude() -> None:
    """Added for the 2026-10-15 attack-run sortie's open question -- see
    `_speech_log_sink`'s own docstring. `runner.last_ownship_state` must
    be read at the moment of the call, the same live-read reasoning the
    gaze/optic fields already follow."""
    writer = _RecordingSpeechWriter()
    runner = ConsolePerceptionRunner(aircraft_client=None)  # type: ignore[arg-type]
    runner.last_t_sim = 5.0
    runner.last_ownship_state = OwnshipState(
        t_sim=5.0,
        x=100.0,
        z=200.0,
        alt_m=450.0,
        heading_true_deg=270.0,
        pitch_deg=-3.5,
        bank_deg=12.0,
    )
    sink = _speech_log_sink(writer, runner)  # type: ignore[arg-type]

    sink("Lined up, obstructed.", False, None, None, None, None, None)

    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["ownship_pitch_deg"] == -3.5
    assert call["ownship_bank_deg"] == 12.0
    assert call["ownship_heading_true_deg"] == 270.0
    assert call["ownship_alt_m"] == 450.0


def test_speech_log_sink_omits_ownship_attitude_before_first_poll() -> None:
    """`runner.last_ownship_state` is `None` until the first poll
    completes -- the same "nothing to report yet" case
    `_render_eyesight_frame` already guards against. Must come through
    as `None`, never a fabricated `0.0` that would read as "level,
    unbanked"."""
    writer = _RecordingSpeechWriter()
    runner = ConsolePerceptionRunner(aircraft_client=None)  # type: ignore[arg-type]
    runner.last_t_sim = 5.0
    sink = _speech_log_sink(writer, runner)  # type: ignore[arg-type]

    sink("Scanning right.", False, None, None, None, None, None)

    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["ownship_pitch_deg"] is None
    assert call["ownship_bank_deg"] is None
    assert call["ownship_heading_true_deg"] is None
    assert call["ownship_alt_m"] is None


def test_speech_log_sink_forwards_correlation_and_push_timing() -> None:
    """`plans/voice-latency-instrumentation/plan.md` Stage 3 -- `_print`'s
    own four latest arguments relayed straight through to `write_speech`."""
    writer = _RecordingSpeechWriter()
    runner = ConsolePerceptionRunner(aircraft_client=None)  # type: ignore[arg-type]
    runner.last_t_sim = 5.0
    sink = _speech_log_sink(writer, runner)  # type: ignore[arg-type]

    sink("Target, armour, 2 o'clock.", False, None, "corr-1", 100.0, 100.05, 0.05)

    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["correlation_id"] == "corr-1"
    assert call["push_sent_wall"] == 100.0
    assert call["push_acked_wall"] == 100.05
    assert call["push_duration_s"] == 0.05


def test_speech_log_sink_omits_correlation_and_push_timing_when_absent() -> None:
    writer = _RecordingSpeechWriter()
    runner = ConsolePerceptionRunner(aircraft_client=None)  # type: ignore[arg-type]
    runner.last_t_sim = 5.0
    sink = _speech_log_sink(writer, runner)  # type: ignore[arg-type]

    sink("Scanning right.", False, None, None, None, None, None)

    assert len(writer.calls) == 1
    call = writer.calls[0]
    assert call["correlation_id"] is None
    assert call["push_sent_wall"] is None
    assert call["push_acked_wall"] is None
    assert call["push_duration_s"] is None


def test_apply_active_gaze_sets_scan_plan_only_on_naked_eye_sources() -> None:
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _relative_area("AREA_1", "ahead"),
        created_sim=0.0,
        deadline_sim=60.0,
        reason="scan-area",
    )
    naked_eye = _naked_eye_source()
    fake = FakeSource([])
    sources = [fake, naked_eye]

    _apply_active_gaze(sources, tasks)

    assert naked_eye.scan_plan == ScanPlan(commanded_sector="ahead", command_t_sim=0.0)
    assert not hasattr(fake, "scan_plan")


def test_apply_active_gaze_resets_to_free_scan_when_nothing_is_pending() -> None:
    naked_eye = _naked_eye_source()
    naked_eye.scan_plan = ScanPlan(commanded_sector="ahead", command_t_sim=0.0)

    _apply_active_gaze([naked_eye], TaskStore())

    assert naked_eye.scan_plan == FREE_SCAN_PLAN


# -- _apply_active_gaze's desired/actual aim split (plans/9k113-sight/
# plan.md section 15a) -----------------------------------------------------


def test_apply_active_gaze_builds_the_scan_plan_from_actual_aim() -> None:
    """With no prior `optic_state`, `advance_sight_aim`'s pass-through
    body makes actual equal desired instantly -- the `ScanPlan` the naked
    eye source receives must still come from the decision's own azimuth/
    elevation, same as before this field split existed."""
    from belief.optic_policy import OpticDecision
    from perception.optics import BINOCULAR_OPTIC

    naked_eye = _naked_eye_source()
    decision = OpticDecision(
        optic=BINOCULAR_OPTIC, look_azimuth_deg=12.0, look_elevation_deg=-3.0
    )

    _apply_active_gaze([naked_eye], TaskStore(), decision=decision)

    assert naked_eye.scan_plan == ScanPlan.fixed_look_at(
        azimuth_deg=12.0, elevation_deg=-3.0
    )


def test_apply_active_gaze_returns_the_updated_optic_state_with_actual_aim_set() -> (
    None
):
    from belief.optic_policy import OpticDecision, OpticState
    from perception.optics import BINOCULAR_OPTIC

    naked_eye = _naked_eye_source()
    decision = OpticDecision(
        optic=BINOCULAR_OPTIC, look_azimuth_deg=12.0, look_elevation_deg=-3.0
    )

    updated_state = _apply_active_gaze(
        [naked_eye], TaskStore(), decision=decision, optic_state=OpticState()
    )

    assert updated_state is not None
    assert updated_state.actual_aim_azimuth_deg == 12.0
    assert updated_state.actual_aim_elevation_deg == -3.0


def test_apply_active_gaze_clears_actual_aim_when_no_look_is_commanded() -> None:
    """A stale actual aim from the last glass phase must not linger once
    `decide` has gone back to `SCANNING` (no fixed look, `OpticDecision`'s
    azimuth/elevation both `None`) -- mirrors `OpticState.look_azimuth_
    deg`'s own None-while-scanning contract."""
    from belief.optic_policy import OpticDecision, OpticState
    from perception.optics import UNAIDED_OPTIC

    naked_eye = _naked_eye_source()
    prior_state = OpticState(actual_aim_azimuth_deg=12.0, actual_aim_elevation_deg=-3.0)
    decision = OpticDecision(optic=UNAIDED_OPTIC)

    updated_state = _apply_active_gaze(
        [naked_eye], TaskStore(), decision=decision, optic_state=prior_state
    )

    assert updated_state is not None
    assert updated_state.actual_aim_azimuth_deg is None
    assert updated_state.actual_aim_elevation_deg is None


def test_apply_active_gaze_returns_none_when_optic_state_was_never_given() -> None:
    """Every pre-existing caller (including the two tests above this
    section) passes no `optic_state` at all -- the return value must stay
    `None` for them, not manufacture a state nobody asked for."""
    naked_eye = _naked_eye_source()

    updated_state = _apply_active_gaze([naked_eye], TaskStore())

    assert updated_state is None


# -- `_apply_active_gaze`'s `sight_cone`/`suppressed_until_sim` build
# (`plans/9k113-sight/plan.md` §12/§12a, direction §6/§7) -------------------


def test_apply_active_gaze_builds_a_sight_cone_from_actual_aim() -> None:
    from belief.optic_policy import OpticDecision, OpticState
    from perception.optics import SIGHT_NARROW_OPTIC

    naked_eye = _naked_eye_source()
    decision = OpticDecision(
        optic=SIGHT_NARROW_OPTIC, look_azimuth_deg=12.0, look_elevation_deg=-3.0
    )

    _apply_active_gaze(
        [naked_eye], TaskStore(), decision=decision, optic_state=OpticState()
    )

    assert naked_eye.sight_cone is not None
    assert naked_eye.sight_cone.azimuth_deg == 12.0
    assert naked_eye.sight_cone.half_angle_deg == SIGHT_NARROW_OPTIC.fov_half_angle_deg
    assert naked_eye.sight_cone.depth_m == SIGHT_NARROW_OPTIC.range_cap_m


def test_apply_active_gaze_builds_no_cone_for_a_non_sight_optic() -> None:
    """`Optic.regard_azimuth_half_deg is None` for `UNAIDED_OPTIC`/
    `BINOCULAR_OPTIC` -- neither is pointed/slewed, so neither gets a
    cone, even with a fixed look commanded (e.g. a binocular glass)."""
    from belief.optic_policy import OpticDecision, OpticState
    from perception.optics import BINOCULAR_OPTIC

    naked_eye = _naked_eye_source()
    decision = OpticDecision(
        optic=BINOCULAR_OPTIC, look_azimuth_deg=12.0, look_elevation_deg=-3.0
    )

    _apply_active_gaze(
        [naked_eye], TaskStore(), decision=decision, optic_state=OpticState()
    )

    assert naked_eye.sight_cone is None


def test_apply_active_gaze_builds_no_cone_while_sighting_is_idle() -> None:
    """No fixed look commanded (idle-wide sighting, `decision.look_azimuth_
    deg is None`) -- actual aim is cleared, so there is no committed
    direction to point a cone at. The cone only follows a *committed* aim,
    never a teleporting one (plan §15a/§15b point 3)."""
    from belief.optic_policy import OpticDecision, OpticState
    from perception.optics import SIGHT_WIDE_OPTIC

    naked_eye = _naked_eye_source()
    prior_state = OpticState(actual_aim_azimuth_deg=12.0, actual_aim_elevation_deg=-3.0)
    decision = OpticDecision(optic=SIGHT_WIDE_OPTIC)

    _apply_active_gaze(
        [naked_eye], TaskStore(), decision=decision, optic_state=prior_state
    )

    assert naked_eye.sight_cone is None


def test_apply_active_gaze_sets_suppressed_until_sim_from_optic_state() -> None:
    from belief.optic_policy import OpticState

    naked_eye = _naked_eye_source()

    _apply_active_gaze(
        [naked_eye],
        TaskStore(),
        optic_state=OpticState(hands_busy_until_sim=42.0),
    )

    assert naked_eye.suppressed_until_sim == 42.0


def test_apply_active_gaze_suppressed_until_sim_is_none_by_default() -> None:
    naked_eye = _naked_eye_source()

    _apply_active_gaze([naked_eye], TaskStore())

    assert naked_eye.suppressed_until_sim is None


def test_run_once_wires_the_active_gaze_onto_a_naked_eye_source() -> None:
    # End-to-end: a pending scan-left task registered on the store the
    # runner ticks must be visible to a real NakedEyePerceptionSource by
    # the time `run_once` polls it -- this is the wiring that makes an F10
    # "scan left" command change what Petrovich can actually see.
    telemetry = _telemetry_dict()
    store = ContactStore()
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _relative_area("AREA_1", "left"),
        created_sim=0.0,
        deadline_sim=600.0,
        reason="scan-area",
    )
    naked_eye = _naked_eye_source()
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[naked_eye],
        store=store,
        tasks=tasks,
    )

    runner.run_once()

    assert naked_eye.scan_plan == ScanPlan(commanded_sector="left", command_t_sim=0.0)


def test_run_once_compass_scan_actually_changes_naked_eye_gaze() -> None:
    # The test that would have failed before Stage 5: a compass scan
    # ("scan north") used to register a real `AttentionArea`/`PendingIntent`
    # and speak a readback while `NakedEyePerceptionSource.scan_plan` stayed
    # `FREE_SCAN_PLAN` -- the pilot heard "Scanning north" and Petrovich kept
    # free-scanning regardless. This asserts the gaze the naked-eye source is
    # actually handed changes, not merely that a task was registered.
    telemetry = _telemetry_dict()  # heading_true_rad=0.0 -- nose points north
    store = ContactStore()
    tasks = TaskStore()
    tasks.create(
        "scan_area",
        _sector_area("AREA_1", "N"),
        created_sim=0.0,
        deadline_sim=600.0,
        reason="scan-area",
    )
    naked_eye = _naked_eye_source()
    runner = ConsolePerceptionRunner(
        aircraft_client=FakeAircraftClient(telemetry),  # type: ignore[arg-type]
        sources=[naked_eye],
        store=store,
        tasks=tasks,
    )

    runner.run_once()

    # The scan plan actually assigned to the source is a real commanded
    # one, not free scan -- heading 0 puts north dead ahead, so the
    # resolved legs are dead-ahead-and-either-side (11, 12, 1).
    assert naked_eye.scan_plan == ScanPlan(
        commanded_sector=None, command_t_sim=0.0, commanded_legs=(11, 12, 1)
    )
    # And the gaze it resolves to genuinely differs from what free scan
    # would have produced at the same t_sim -- this is the property that
    # actually matters: Petrovich's eyes moved differently because of the
    # command, not merely that a differently-shaped object got assigned.
    commanded_gaze = gaze_at(3.0, naked_eye.scan_plan)
    free_scan_gaze = gaze_at(3.0, FREE_SCAN_PLAN)
    assert commanded_gaze != free_scan_gaze


def test_run_once_pushes_look_direction_on_change_only() -> None:
    """`plans/dcs-driven-los/plan.md` (X-B29): the look-direction command
    is pushed from the same `scan_plan` the naked-eye source is handed
    (one source of truth), and only when it changes -- a second poll with
    an unchanged gaze must not re-push."""
    telemetry = _telemetry_dict()
    store = ContactStore()
    tasks = TaskStore()
    naked_eye = _naked_eye_source()
    client = FakeAircraftClient(telemetry)
    runner = ConsolePerceptionRunner(
        aircraft_client=client,  # type: ignore[arg-type]
        sources=[naked_eye],
        store=store,
        tasks=tasks,
    )

    runner.run_once()

    assert len(client.look_direction_pushes) == 1
    hour, fov_half_deg = client.look_direction_pushes[0]
    assert 0 <= hour <= 11
    assert fov_half_deg == LOOK_DIRECTION_FOV_HALF_DEG

    # Same telemetry (same t_sim via FakeAircraftClient, same scan_plan) --
    # the resolved gaze is identical, so no second push.
    runner.run_once()
    assert len(client.look_direction_pushes) == 1


# -- _poll_transcripts (plans/inbound-speech/plan.md Stage 3) ---------------


class FakeSpeechInputClient:
    """Stands in for `belief.audio_client.AudioAdapterClient` for
    `_poll_transcripts` -- returns a fixed list of transcript dicts once,
    then empty (mirroring `GET /transcripts/poll`'s real drain-on-GET
    behaviour), or raises `AudioAdapterError` if `should_fail` is set."""

    def __init__(
        self,
        transcripts: list[dict[str, object]] | None = None,
        should_fail: bool = False,
    ) -> None:
        self._transcripts = transcripts if transcripts is not None else []
        self.should_fail = should_fail
        self.poll_count = 0

    def get_transcripts(self) -> list[dict[str, object]]:
        self.poll_count += 1
        if self.should_fail:
            raise AudioAdapterError("poll failed (test double)")
        drained = self._transcripts
        self._transcripts = []
        return drained


def test_poll_transcripts_dispatches_a_matched_command_through_handle_transcript() -> (
    None
):
    console = CrewConsole(store=ContactStore())
    client = FakeSpeechInputClient(
        transcripts=[
            {
                "transcript": "scan left",
                "confidence": 0.9,
                "token": "scan_left",
                "match_ratio": 1.0,
                "verb_anchored": True,
                "ambiguous": False,
                "t_wall": 100.0,
            }
        ]
    )
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert client.poll_count == 1


def test_poll_transcripts_no_match_falls_through_to_handle_line() -> None:
    """A `token=None, verb_anchored=False` transcript (not a command
    attempt at all) must reach the ordinary typed-text path, exactly like
    Stage 2's `handle_transcript` fallthrough test."""
    escalated: list[str] = []

    class _RecordingBrainClient:
        def handle(self, payload: object) -> None:
            escalated.append("sent")

        def awaiting_reply_id(self) -> str | None:
            return None

    console = CrewConsole(store=ContactStore(), brain_client=_RecordingBrainClient())  # type: ignore[arg-type]
    client = FakeSpeechInputClient(
        transcripts=[
            {
                "transcript": "the tanks are on the ridge",
                "confidence": 0.5,
                "token": None,
                "match_ratio": 0.0,
                "verb_anchored": False,
                "ambiguous": False,
                "t_wall": 100.0,
            }
        ]
    )
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert escalated == ["sent"]


def test_poll_transcripts_empty_queue_dispatches_nothing() -> None:
    console = CrewConsole(store=ContactStore())
    client = FakeSpeechInputClient(transcripts=[])
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert client.poll_count == 1


def test_poll_transcripts_failed_poll_degrades_without_raising() -> None:
    console = CrewConsole(store=ContactStore())
    client = FakeSpeechInputClient(should_fail=True)
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]


def test_poll_transcripts_skips_malformed_items() -> None:
    console = CrewConsole(store=ContactStore())
    client = FakeSpeechInputClient(
        transcripts=[
            {"transcript": 123, "confidence": 0.9, "token": None},  # bad shape
            {
                "transcript": "scan left",
                "confidence": 0.9,
                "token": "scan_left",
                "match_ratio": 1.0,
                "verb_anchored": True,
                "ambiguous": False,
                "t_wall": 100.0,
            },
        ]
    )
    # Must not raise, and the well-formed second item must still dispatch.
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert client.poll_count == 1


class _RecordingCrewConsole:
    """Stands in for `CrewConsole` in `_poll_transcripts` -- records the
    exact arguments `handle_transcript` was called with, so a slots round
    trip through this function can be asserted without standing up a real
    `EnrichmentContext`/`TaskStore` (that belongs to `test_crew_console.
    py`'s own, deeper `handle_command`/`_handle_scan` tests)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str | None, dict[str, int | str] | None]] = []
        #: `correlation_id` for every call, in order -- kept separate from
        #: `calls` so every existing assertion on that tuple (transcript/
        #: token/slots only) keeps working unchanged.
        self.correlation_ids: list[str | None] = []

    def handle_transcript(
        self,
        transcript: str,
        confidence: float,
        token: str | None,
        match_ratio: float,
        verb_anchored: bool,
        ambiguous: bool,
        now_sim: float,
        slots: dict[str, int | str] | None = None,
        correlation_id: str | None = None,
    ) -> list[str]:
        self.calls.append((transcript, token, slots))
        self.correlation_ids.append(correlation_id)
        return []


def test_poll_transcripts_threads_slots_into_handle_transcript() -> None:
    """`plans/voice-command-completeness/plan.md` Stage 3's own regression
    guard, extended by `plans/watch-reporting/plan.md` Decision 2b-i's
    `bearing_degrees` -> `slots` migration: a parsed slot used to be
    dropped at the `TranscriptEvent` wire and never reached
    `handle_transcript` at all."""
    console = _RecordingCrewConsole()
    client = FakeSpeechInputClient(
        transcripts=[
            {
                "transcript": "scan bearing three two zero",
                "confidence": 0.9,
                "token": "scan_bearing_deg",
                "match_ratio": 1.0,
                "verb_anchored": True,
                "ambiguous": False,
                "t_wall": 100.0,
                "slots": {"bearing_degrees": 320},
            }
        ]
    )
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert console.calls == [
        ("scan bearing three two zero", "scan_bearing_deg", {"bearing_degrees": 320})
    ]
    assert console.correlation_ids == [None]


def test_poll_transcripts_threads_correlation_id_into_handle_transcript() -> None:
    """`plans/voice-latency-instrumentation/plan.md` Stage 3."""
    console = _RecordingCrewConsole()
    client = FakeSpeechInputClient(
        transcripts=[
            {
                "transcript": "scan left",
                "confidence": 0.9,
                "token": "scan_left",
                "match_ratio": 1.0,
                "verb_anchored": True,
                "ambiguous": False,
                "t_wall": 100.0,
                "correlation_id": "corr-abc123",
            }
        ]
    )
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert console.correlation_ids == ["corr-abc123"]


def test_poll_transcripts_skips_items_with_a_non_string_correlation_id() -> None:
    console = _RecordingCrewConsole()
    client = FakeSpeechInputClient(
        transcripts=[
            {
                "transcript": "scan left",
                "confidence": 0.9,
                "token": "scan_left",
                "match_ratio": 1.0,
                "verb_anchored": True,
                "ambiguous": False,
                "t_wall": 100.0,
                "correlation_id": 123,  # wrong type, must be skipped
            }
        ]
    )
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert console.calls == []


def test_poll_transcripts_skips_items_with_slots_that_are_not_a_dict() -> None:
    console = _RecordingCrewConsole()
    client = FakeSpeechInputClient(
        transcripts=[
            {
                "transcript": "scan bearing three two zero",
                "confidence": 0.9,
                "token": "scan_bearing_deg",
                "match_ratio": 1.0,
                "verb_anchored": True,
                "ambiguous": False,
                "t_wall": 100.0,
                "slots": "not-a-dict",  # wrong shape, must be skipped
            }
        ]
    )
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert console.calls == []


def test_poll_transcripts_skips_items_with_a_malformed_slot_value() -> None:
    """A `slots` value must be `int | str` -- a `bool` (a `int` subtype in
    Python) or any other type must be rejected the same way every other
    field's `isinstance` check already excludes `bool` from `int`/`float`
    above."""
    console = _RecordingCrewConsole()
    client = FakeSpeechInputClient(
        transcripts=[
            {
                "transcript": "scan bearing three two zero",
                "confidence": 0.9,
                "token": "scan_bearing_deg",
                "match_ratio": 1.0,
                "verb_anchored": True,
                "ambiguous": False,
                "t_wall": 100.0,
                "slots": {"bearing_degrees": True},
            }
        ]
    )
    _poll_transcripts(client, console, now_sim=0.0)  # type: ignore[arg-type]
    assert console.calls == []


def test_a_player_command_lowers_the_binoculars() -> None:
    """`plans/binocular-optic/plan.md` D4 ("not a special case per
    command... the pilot asking for something is itself evidence") wired
    through a counter rather than a callback -- `_run_crew_text_poll_loop`
    asks "did the player ask for anything just now" by comparing
    `CrewConsole.commands_handled` across one poll iteration, then lowers
    the binoculars if it changed. Reproduces that exact conditional (see
    `logger._run_crew_text_poll_loop`) rather than checking the counter and
    `lower_binoculars` as two unrelated facts, which is what let the real
    D4 gap (only `handle_command` incremented the counter -- a typed or
    voice-fallthrough free-form request did not) go uncaught: a resolvable
    F10 token always passed this test, whichever surface actually carried
    D4's rule.

    **Drives the free-form typed path** (`handle_line`, not
    `handle_command`) -- the surface the review found broken -- and
    asserts the binoculars actually come down as a consequence, not merely
    that the counter moved."""
    from belief.crew_console import CrewConsole
    from belief.optic_policy import OpticPhase, OpticState, lower_binoculars

    store = ContactStore()
    store.ingest(
        [
            Observation(
                id="OBS_1",
                contact_id=None,
                t_sim=0.0,
                t_wall=0.0,
                source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
                classification_raw="BMP-2",
                bearing_deg=0.0,
                range_m=1000.0,
                ownship_at_observation=OwnshipState(
                    t_sim=0.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0
                ),
                derived_world_position=DerivedWorldPosition(
                    x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
                ),
                provenance="test_fixture",
                classification_level=2,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id

    console = CrewConsole(store=store)
    optic_state = OpticState(
        phase=OpticPhase.GLASSING,
        phase_started_sim=0.0,
        look_azimuth_deg=30.0,
        look_elevation_deg=-5.0,
    )

    commands_before = console.commands_handled
    readback_lines = console.handle_line(f"watch {contact_id}", now_sim=1.0)
    assert readback_lines == [f"Watching {contact_id}."]  # a real free-form request

    if console.commands_handled != commands_before:
        optic_state = lower_binoculars(optic_state, now_sim=1.0)

    assert optic_state.phase is OpticPhase.SCANNING
    assert optic_state.look_azimuth_deg is None


def test_follow_already_on_target_does_not_lower_the_binoculars() -> None:
    """`plans/sortie-2026-09-26-fixes/decisions.md` Decision 2's one
    carve-out to the rule above: `follow <target>` naming the contact
    already being glassed is a request to continue, not to stop --
    lowering and immediately re-pointing at the same target would be
    strictly worse than doing nothing. Reproduces `_run_crew_text_poll_
    loop`'s exact conditional (mirroring `test_a_player_command_lowers_
    the_binoculars`'s own reproduction above), extended with the carve-out
    this fix adds, rather than checking `already_on_target`'s arithmetic
    and `lower_binoculars` as two unrelated facts."""
    from belief.optic_policy import OpticPhase, OpticState, lower_binoculars

    console = CrewConsole(store=ContactStore())
    optic_state = OpticState(
        phase=OpticPhase.GLASSING,
        phase_started_sim=0.0,
        look_azimuth_deg=30.0,
        look_elevation_deg=-5.0,
        look_contact_id="CONTACT_1",
    )

    commands_before = console.commands_handled
    console.commands_handled += 1  # simulate a dispatched "follow CONTACT_1"
    console.last_command_target_contact_id = "CONTACT_1"

    if console.commands_handled != commands_before:
        already_on_target = (
            console.last_command_target_contact_id is not None
            and optic_state.phase is OpticPhase.GLASSING
            and optic_state.look_contact_id == console.last_command_target_contact_id
        )
        if not already_on_target:
            optic_state = lower_binoculars(optic_state, now_sim=1.0)

    assert optic_state.phase is OpticPhase.GLASSING
    assert optic_state.look_azimuth_deg == 30.0


def test_follow_off_target_still_lowers_the_binoculars() -> None:
    """The other half of Decision 2's `follow` spec: naming a contact
    *other* than the one currently being glassed lowers the binoculars (so
    the scan can re-point at the named target), just like every other
    dispatched command -- the carve-out is narrow, not a blanket exemption
    for `follow`."""
    from belief.optic_policy import OpticPhase, OpticState, lower_binoculars

    console = CrewConsole(store=ContactStore())
    optic_state = OpticState(
        phase=OpticPhase.GLASSING,
        phase_started_sim=0.0,
        look_azimuth_deg=30.0,
        look_elevation_deg=-5.0,
        look_contact_id="CONTACT_1",
    )

    commands_before = console.commands_handled
    console.commands_handled += 1  # simulate a dispatched "follow CONTACT_2"
    console.last_command_target_contact_id = "CONTACT_2"

    if console.commands_handled != commands_before:
        already_on_target = (
            console.last_command_target_contact_id is not None
            and optic_state.phase is OpticPhase.GLASSING
            and optic_state.look_contact_id == console.last_command_target_contact_id
        )
        if not already_on_target:
            optic_state = lower_binoculars(optic_state, now_sim=1.0)

    assert optic_state.phase is OpticPhase.SCANNING
    assert optic_state.look_azimuth_deg is None


def test_an_unknown_contact_sizes_its_window_from_a_default_profile() -> None:
    """The no-omniscience property of the binocular trigger: a
    presence-level contact has no believed type, so the window is sized
    from the object model's default profile. A Petrovich who sized it by
    what the thing really is would be deciding with knowledge he does not
    have."""
    from belief.optic_policy import improvement_window_m

    unknown_lower, unknown_upper = improvement_window_m(
        "OP_GROUPSOMETHING", current_level="presence"
    )
    assert unknown_upper > unknown_lower > 0.0

    known_lower, known_upper = improvement_window_m("T-72", current_level="presence")
    assert (unknown_lower, unknown_upper) != (known_lower, known_upper)


def test_observ_off_command_stops_the_sight_through_the_real_poll_loop() -> None:
    """`BL-B64` Stage 2 review, Pass 2 required fix, exercised through the
    actual command -> drain -> decide sequence, not just `optic_policy`'s
    own unit tests (same pattern `test_a_player_command_lowers_the_
    binoculars` already uses for the binocular case) -- the gap the review
    found was invisible precisely because no existing test drove this path
    end to end.

    **Scope note (`[[BL-B80]]`):** the local snippet below reproduces only
    the hands-busy-suppression/cockpit-write half of the old `observ_
    transition == "off"` drain block, which is still what production code
    does on that command. It does **not** cover `home_phase`, which
    `[[BL-B80]]` moved out of this drain block entirely -- `home_phase` is
    now derived every poll from the *observed* arg-886 edge in `run_once`,
    not from this command. `optic_state.home_phase` is set directly below
    rather than through any reproduced drain logic, purely so `decide`'s
    phase dispatch has a starting state to suppress from."""
    from dataclasses import replace as _replace

    from belief.crew_console import CrewConsole
    from belief.optic_policy import (
        HANDS_BUSY_DURATION_S,
        OpticPhase,
        OpticState,
        decide,
    )

    console = CrewConsole(store=ContactStore(), tasks=TaskStore())
    optic_state = OpticState(
        phase=OpticPhase.SIGHTING,
        phase_started_sim=0.0,
        home_phase=OpticPhase.SIGHTING,
        look_contact_id="CONTACT_1",
        look_started_sim=0.0,
    )

    # The real command surface: "Observ off" speaks immediately...
    lines = console.handle_command("observ_off", now_sim=1.0)
    assert lines == ["Observ off."]
    assert console.observ_transition == "off"

    # ...and the poll loop's own drain block (logger.py) is what actually
    # touches `optic_state` -- reproduced verbatim rather than invoking the
    # whole runner.
    if console.observ_transition == "off":
        optic_state = _replace(
            optic_state,
            home_phase=OpticPhase.SCANNING,
            hands_busy_until_sim=1.0 + HANDS_BUSY_DURATION_S,
        )
        console.observ_transition = None

    # While the 1 s hand movement is still running, decide() suppresses
    # every optic -- the sight already stops speaking for Petrovich, even
    # though `phase` has not yet formally left SIGHTING.
    optic_state, decision = decide(
        optic_state,
        now_sim=1.0,
        scan_cycle_period_s=10.0,
        targets=[],
        steady=True,
    )
    assert decision.suppressed is True

    # The very next poll after the hand movement elapses: phase leaves
    # SIGHTING immediately, not after SIGHT_MAX_DWELL_S.
    optic_state, decision = decide(
        optic_state,
        now_sim=1.0 + HANDS_BUSY_DURATION_S,
        scan_cycle_period_s=10.0,
        targets=[],
        steady=True,
    )
    assert optic_state.phase is OpticPhase.SCANNING
    assert optic_state.home_phase is OpticPhase.SCANNING
    assert optic_state.look_contact_id is None


def test_run_once_caps_a_sight_tier_optic_during_gyro_alignment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`[[BL-B80]]` plan Stage 1's own test list, required fix 3 of the
    BL-B80 review: a `run_once`-level test that an OBSERV-on edge followed
    immediately by a poll inside the gyro-alignment window never yields
    `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`, even when `decide_optic` would
    otherwise choose one -- and that the cap lifts the moment the window
    ends, with no special-casing needed.

    Also exercises required fix 2 in the same run: while the cap is
    active, a stale sight-head readback already sitting in `guidance_
    unit_state` (left over from a previous OBSERV-on, as it is for the
    rest of a mission once any sample has ever arrived) must not leak
    into the gaze/optic-state perception reads -- `advance_sight_aim`
    must fall through to the pass-through model, not the readback's own
    converted degrees, while a non-sight-tier optic is in force."""
    import logger as logger_module
    from belief.optic_policy import OpticDecision, OpticState

    telemetry = _console_telemetry_dict()
    telemetry["altitude_agl_m"] = 500.0  # airborne
    sim_t = 100.0
    telemetry["dcs_model_time_s"] = sim_t

    aircraft_client = FakeConsoleAircraftClient(telemetry, {"objects": []})
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]

    # A rising OBSERV edge 2 s ago -- well inside the 10 s default
    # `GYRO_ALIGNMENT_S` window -- plus a stale readback sitting from a
    # previous OBSERV-on, converted (raw 0.5 -> ~68.18 deg) to a value
    # nowhere near the 12.0/-3.0 `decide_optic` will ask to look at, so
    # the test can tell whether the readback leaked through.
    runner.guidance_unit_state = GuidanceUnitState(
        observ_observed=True,
        observ_observed_since_sim=sim_t - 2.0,
        sight_az_raw=0.5,
        sight_elev_raw=0.3,
    )

    def fake_decide_optic(
        state: OpticState, **_kwargs: object
    ) -> tuple[OpticState, OpticDecision]:
        return state, OpticDecision(
            optic=SIGHT_WIDE_OPTIC, look_azimuth_deg=12.0, look_elevation_deg=-3.0
        )

    monkeypatch.setattr(logger_module, "decide_optic", fake_decide_optic)

    runner.run_once()

    # Inside the window: capped to BINOCULAR_OPTIC, never the sight-tier
    # optic `decide_optic` chose.
    from perception.optics import BINOCULAR_OPTIC

    assert runner.optic is BINOCULAR_OPTIC
    # Required fix 2: the stale readback must not have reached the gaze
    # -- `actual_aim_azimuth_deg` is the pass-through model's `desired`
    # (12.0), not the readback's converted ~68.18 deg.
    assert runner.optic_state.actual_aim_azimuth_deg == pytest.approx(12.0)
    assert runner.optic_state.actual_aim_elevation_deg == pytest.approx(-3.0)

    # The window ends: the very next poll's cap check simply passes, no
    # special-casing needed.
    sim_t += 10.5
    telemetry["dcs_model_time_s"] = sim_t
    runner.run_once()

    assert runner.optic is SIGHT_WIDE_OPTIC
    # Now that a sight-tier optic is actually in force, the readback is
    # allowed through and anchors the gaze to the real head position.
    assert runner.optic_state.actual_aim_azimuth_deg == pytest.approx(68.18, abs=0.01)


# -- speech-log defaulting (plans/binocular-optic/plan.md's speech-log side
# feature: "every not recognised command is appended to a log file, with
# timestamp" should not require the pilot to remember a flag) ------------


def test_speech_log_defaults_on_with_crew_text_and_speech_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = _resolve_speech_log_path(
        speech_log=None, no_speech_log=False, crew_text=True, speech_input=True
    )
    assert resolved == DEFAULT_SPEECH_LOG_PATH
    assert (tmp_path / DEFAULT_SPEECH_LOG_PATH.parent).is_dir()


def test_speech_log_does_not_default_without_crew_text_and_speech_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    # Neither flag.
    assert (
        _resolve_speech_log_path(
            speech_log=None, no_speech_log=False, crew_text=False, speech_input=False
        )
        is None
    )
    # Only one of the two.
    assert (
        _resolve_speech_log_path(
            speech_log=None, no_speech_log=False, crew_text=True, speech_input=False
        )
        is None
    )
    assert (
        _resolve_speech_log_path(
            speech_log=None, no_speech_log=False, crew_text=False, speech_input=True
        )
        is None
    )
    assert not (tmp_path / DEFAULT_SPEECH_LOG_PATH.parent).exists()


def test_no_speech_log_suppresses_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    resolved = _resolve_speech_log_path(
        speech_log=None, no_speech_log=True, crew_text=True, speech_input=True
    )
    assert resolved is None
    assert not (tmp_path / DEFAULT_SPEECH_LOG_PATH.parent).exists()


def test_explicit_speech_log_wins_over_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    explicit = tmp_path / "elsewhere" / "speech.jsonl"
    resolved = _resolve_speech_log_path(
        speech_log=explicit, no_speech_log=False, crew_text=True, speech_input=True
    )
    assert resolved == explicit
    # No default-path directory creation happens on the explicit-path route.
    assert not (tmp_path / DEFAULT_SPEECH_LOG_PATH.parent).exists()


def test_speech_log_default_degrades_to_none_when_directory_is_unwritable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An unwritable default location must not stop the logger from
    starting -- it degrades to no log and says so on stderr, exactly the
    posture `CrewConsole._log_transcript`'s own per-write try/except
    already has."""
    monkeypatch.chdir(tmp_path)

    def _boom(self: Path, parents: bool = False, exist_ok: bool = False) -> None:
        raise OSError("permission denied")

    monkeypatch.setattr(Path, "mkdir", _boom)

    resolved = _resolve_speech_log_path(
        speech_log=None, no_speech_log=False, crew_text=True, speech_input=True
    )

    assert resolved is None
    assert "speech-log" in capsys.readouterr().err


def test_speech_log_cli_validation_rejects_speech_log_with_no_speech_log(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`--speech-log` and `--no-speech-log` together must be rejected by
    `main()`'s own argparse validation, the same posture as the other
    `parser.error` mutual-exclusivity checks in this file."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "logger",
            "--aircraft-layer-url",
            "http://127.0.0.1:7791",
            "--theatre",
            "Syria",
            "--world-model-db",
            str(tmp_path / "wm.sqlite"),
            "--crew-text",
            "--speech-input",
            "--audio-adapter-url",
            "http://127.0.0.1:7795",
            "--speech-log",
            str(tmp_path / "speech.jsonl"),
            "--no-speech-log",
        ],
    )

    with pytest.raises(SystemExit):
        main()


def test_main_print_tuning_works_without_aircraft_layer_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--print-tuning` is the one flag that must work standalone --
    plans/configurable-constants/plan.md's 'Verifying a changed value
    took effect'. `main()` must not reject it for lacking
    `--aircraft-layer-url`, and must exit cleanly (no `SystemExit`) after
    printing."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PETROBRAIN_TUNING", raising=False)
    monkeypatch.setattr(sys, "argv", ["logger", "--print-tuning"])

    main()

    out = capsys.readouterr().out
    assert "no override file (PETROBRAIN_TUNING unset)" in out
    assert "at default" in out


def test_main_rejects_missing_aircraft_layer_url_without_print_tuning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PETROBRAIN_TUNING", raising=False)
    monkeypatch.setattr(sys, "argv", ["logger"])

    with pytest.raises(SystemExit):
        main()


def test_main_rejects_neither_theatre_pair_nor_mission_understanding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 5 (multi-theatre-afghanistan plan): with neither
    `--theatre`/`--world-model-db` nor `--mission-understanding` given,
    `main()` must reject rather than silently falling back to a default
    theatre."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        ["logger", "--aircraft-layer-url", "http://127.0.0.1:7791"],
    )

    with pytest.raises(SystemExit):
        main()


def test_main_rejects_mission_understanding_without_world_model_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 5: deriving theatre from `--mission-understanding` requires
    `--world-model-dir` -- without it there is nowhere to resolve the
    per-theatre store path to."""
    monkeypatch.chdir(tmp_path)
    mission_understanding_path = (
        Path(__file__).parent / "fixtures" / "mission_understanding_sample.json"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "logger",
            "--aircraft-layer-url",
            "http://127.0.0.1:7791",
            "--mission-understanding",
            str(mission_understanding_path),
        ],
    )

    with pytest.raises(SystemExit):
        main()


def test_main_rejects_world_model_db_theatre_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stage 5's mismatch guard: a `--world-model-db` built for a
    different theatre than the resolved `--theatre` must be rejected
    before the first poll, rather than silently applying the wrong
    projection to every contact."""
    from store.models import Region
    from store.writer import insert_region

    db_path = tmp_path / "afghanistan-full.sqlite"
    conn = open_for_build(db_path)
    insert_region(
        conn,
        Region(
            name="afghanistan-full",
            theatre="Afghanistan",
            centre_x=0.0,
            centre_z=0.0,
            half_extent_x_m=1000.0,
            half_extent_z_m=1000.0,
            built_at="2026-10-05T00:00:00+00:00",
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "logger",
            "--aircraft-layer-url",
            "http://127.0.0.1:7791",
            "--theatre",
            "Syria",
            "--world-model-db",
            str(db_path),
        ],
    )

    with pytest.raises(SystemExit):
        main()


def _write_mission_understanding_with_theatre(path: Path, theatre_value: str) -> None:
    """Minimal `--emit-compact`-shaped artifact with an arbitrary (possibly
    malicious) `theatre.value` -- `load_mission_understanding` places no
    constraint on that string's content (`_parse_theatre` only checks it is
    a `str`), so this is exactly what a `.miz`-derived artifact can carry
    through unvalidated per `plans/multi-theatre-afghanistan/security.md`."""
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "phases": [],
                "route": [],
                "theatre": {
                    "value": theatre_value,
                    "epistemic_status": "FACT",
                    "basis": ["miz:theatre"],
                    "confidence": None,
                },
            }
        )
    )


@pytest.mark.parametrize(
    "theatre_value",
    [
        "Narnia",
        "/etc/passwd",
        "//attacker-host/share/x",
        "Syria?mode=rwc&x=",
    ],
    ids=["unknown-theatre", "absolute-path", "unc-path", "query-string-injection"],
)
def test_main_rejects_unregistered_theatre_from_mission_understanding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    theatre_value: str,
) -> None:
    """Security (multi-theatre-afghanistan plan, required fix): a
    mission-understanding-derived `theatre` that is not an exact key in
    `coordinates.projections.THEATRE_PROJECTIONS` must be rejected by
    `main()` before any path is built or any file is opened -- whatever
    the string actually contains (an unknown name, an absolute-path
    override, a UNC-path override, or a SQLite URI-query-string injection
    suffix shaped like security.md's own reproduction: an `&`-separated
    second query parameter, which is what makes SQLite's URI parser split
    the filename at the attacker's injected `?` -- a bare `"Syria?mode=rwc"`
    with no second parameter instead fails as a malformed access-mode
    string, which doesn't exercise the mechanism this case is named for.
    `open_world_model` must never be called for any of these -- tightened
    (reviewer finding on f7f2827) from asserting only *some* `SystemExit`,
    which also passed when just the optional `try/except` guard (not the
    required registry check) converted a downstream failure into the same
    SystemExit, silently passing even with the required fix removed."""
    monkeypatch.chdir(tmp_path)
    mission_understanding_path = tmp_path / "mission_understanding.json"
    _write_mission_understanding_with_theatre(mission_understanding_path, theatre_value)

    def _fail_if_open_world_model_called(*_args: object, **_kwargs: object) -> NoReturn:
        pytest.fail(
            "open_world_model was called -- the registry-check rejection "
            "must happen strictly before any world-model store is opened"
        )

    monkeypatch.setattr(
        logger_module, "open_world_model", _fail_if_open_world_model_called
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "logger",
            "--aircraft-layer-url",
            "http://127.0.0.1:7791",
            "--mission-understanding",
            str(mission_understanding_path),
            "--world-model-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit):
        main()

    # No file matching the attacker-influenced suffix was ever created or
    # opened -- the rejection happens before any path is built.
    assert not any(tmp_path.glob("*-full.sqlite"))

    # Assert the specific rejection reason, not just that *some* SystemExit
    # occurred -- this is what actually fails if the required registry
    # check is removed while the optional except-block stays in place (see
    # docstring above).
    stderr = capsys.readouterr().err
    assert "not a known theatre" in stderr


def test_main_gives_clean_error_for_unbuilt_theatre_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Security (multi-theatre-afghanistan plan, optional item): a
    validated, known theatre whose store has not been built yet must give
    a clean `parser.error` naming the expected path, not a raw `sqlite3`
    traceback -- the mismatch guard's `open_world_model`/`load_only_region`
    call is wrapped in `try/except (sqlite3.Error, OSError)`."""
    monkeypatch.chdir(tmp_path)
    mission_understanding_path = tmp_path / "mission_understanding.json"
    _write_mission_understanding_with_theatre(mission_understanding_path, "Syria")
    expected_store = tmp_path / "syria-full.sqlite"
    assert not expected_store.exists()

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "logger",
            "--aircraft-layer-url",
            "http://127.0.0.1:7791",
            "--mission-understanding",
            str(mission_understanding_path),
            "--world-model-dir",
            str(tmp_path),
        ],
    )

    with pytest.raises(SystemExit):
        main()

    err = capsys.readouterr().err
    assert "world model" in err
    assert str(expected_store) in err


def test_say_again_disposition_reaches_the_speech_log_file_end_to_end(
    tmp_path: Path,
) -> None:
    """Not just a writer unit test: wires a real `SpeechLogWriter` through
    `CrewConsole.transcript_log` the same way `main()` does, then confirms
    a genuinely unrecognised (`say_again`) utterance lands in the file --
    the exact case the user wants to later mine for what gets garbled or
    mistranscribed."""
    from speech_log import SpeechLogWriter

    log_path = tmp_path / "speech.jsonl"
    writer = SpeechLogWriter(log_path)
    console = CrewConsole(store=ContactStore(), transcript_log=writer.write)

    # verb_anchored=True, token=None: heard as an attempted command but
    # nothing matched -- classify_response's say_again route.
    console.handle_transcript(
        transcript="scan uh the thing",
        confidence=0.9,
        token=None,
        match_ratio=0.0,
        verb_anchored=True,
        ambiguous=False,
        now_sim=10.0,
    )

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    row = json.loads(lines[0])
    assert row["transcript"] == "scan uh the thing"
    assert row["disposition"] == "say_again"
    assert row["acted_token"] is None
    assert "t_wall" in row


def test_an_unwritable_speech_log_says_so_once_and_keeps_the_command_working(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`BL-11` Stage 5. `CrewConsole._log_transcript` swallows every
    exception so a logging failure never costs the player the command they
    just spoke -- which is right, and also meant an unwritable path
    produced no symptom anywhere at all. Both halves are asserted: one
    report, and the dispatch still returns a spoken line."""
    from speech_log import SpeechLogWriter

    # A directory where the file should be: every `open("a")` raises.
    log_path = tmp_path / "speech.jsonl"
    log_path.mkdir()
    writer = SpeechLogWriter(log_path)
    console = CrewConsole(store=ContactStore(), transcript_log=writer.write)

    for _ in range(3):
        spoken = console.handle_transcript(
            transcript="scan uh the thing",
            confidence=0.9,
            token=None,
            match_ratio=0.0,
            verb_anchored=True,
            ambiguous=False,
            now_sim=10.0,
        )
        assert spoken, "a failing debug log must not cost the player a reply"

    assert capsys.readouterr().err.count("speech-log: write to") == 1


# --- the poll thread must survive a raising dispatch -----------------------


def test_console_poll_loop_survives_a_raising_poll_and_keeps_going(
    tmp_path: pathlib.Path,
) -> None:
    """The poll loop runs on a *daemon* thread, so an exception escaping it
    kills the thread without killing the process: the REPL keeps accepting
    input, the overlay holds its last frame, and perception/belief/speech
    are dead for the rest of the sortie with only a stderr traceback to say
    so. Nothing in the cockpit reports it.

    That cost -- a whole flight, silently -- is why the guard catches
    everything rather than an enumerated set. A skipped poll costs one
    cycle at 5 Hz and the next one recovers.

    Found by the security pass on `plans/watch-reporting/`
    (`security-review.md`); pre-existing rather than introduced there, and
    unreachable through today's narrow wire path, which is exactly why no
    existing test covered it.

    Drives the real `_run_console_poll_loop` on a real thread, with a
    `run_once` that raises on its first call and succeeds afterwards, and
    asserts the second poll actually happened -- not merely that the thread
    is still alive, which a loop that had exited cleanly would also
    satisfy.
    """
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": [_t72_world_object()]}
    )
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]

    real_run_once = runner.run_once
    calls: list[int] = []
    # Signalled by the *second* poll, so the test waits on the thing it is
    # asserting rather than on a deadline -- this runs a real thread, and a
    # poll-count spin loop is exactly the shape that goes flaky under load.
    recovered = threading.Event()

    def flaky_run_once() -> None:
        calls.append(len(calls))
        if len(calls) == 1:
            raise RuntimeError("simulated dispatch failure inside the poll body")
        real_run_once()
        recovered.set()

    runner.run_once = flaky_run_once  # type: ignore[method-assign]
    stop_event = threading.Event()

    poll_thread = threading.Thread(
        target=_run_console_poll_loop,
        args=(runner, aircraft_client, "Syria", db_path, 0.01, stop_event),
    )
    poll_thread.start()
    try:
        assert recovered.wait(timeout=10.0), (
            "the poll loop did not run a second cycle after the first raised "
            "-- the guard is missing and the thread died silently"
        )
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    # The first poll raised; the loop kept going and the second one ran to
    # completion, ingesting normally.
    assert len(calls) >= 2
    assert runner.last_t_sim == 200.0
    assert len(runner.store.observations) == 1


# --- the three trace consumers must all see the same poll's records --------


def test_all_three_trace_consumers_see_one_polls_records(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`--detection-trace`, `--eyesight-view` and `--belief-truth-log` share
    one `DetectionTraceCollector`, and exactly one consumer clears it. That
    ordering is the sharp edge of this wiring: reorder the branches so the
    clear runs first and the other two silently see nothing — no exception,
    no empty-file error, just two instruments that quietly stop reporting.

    Which is precisely the failure these instruments exist to catch. The
    87.5 km position defect they were built for had been in the trace data
    every poll for a whole sortie while nobody could see it.

    The module-level tests cover each consumer against fakes. This drives
    the real `_run_console_poll_loop` on a real thread with all three
    enabled at once and asserts each one actually received the poll — the
    only arrangement that fails if the branches are reordered."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    trace_path = tmp_path / "trace.jsonl"
    belief_truth_path = tmp_path / "belief_truth.jsonl"

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": [_t72_world_object()]}
    )
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    stop_event = threading.Event()

    poll_thread = threading.Thread(
        target=_run_console_poll_loop,
        args=(runner, aircraft_client, "Syria", db_path, 10.0, stop_event),
        kwargs={
            "detection_trace_path": trace_path,
            "eyesight_view": True,
            "belief_truth_log_path": belief_truth_path,
        },
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

    # 1. the detection trace, which is also the consumer that clears.
    assert trace_path.exists(), "detection trace never written"
    assert trace_path.read_text().strip(), "detection trace written but empty"

    # 2. the belief-truth log, which reads before the clear.
    assert belief_truth_path.exists(), "belief-truth log never written"
    assert belief_truth_path.read_text().strip(), (
        "belief-truth log written but empty -- it read after the collector "
        "was cleared, which is the reorder this test exists to catch"
    )

    # 3. the eyesight view, which renders to stdout from a copy.
    printed = capsys.readouterr().out
    assert printed.strip(), (
        "eyesight view printed nothing -- it rendered after the collector "
        "was cleared, which is the reorder this test exists to catch"
    )


# -- Live LOS coverage logging (`plans/bl11-stage4-fail-closed/plan.md`
# review round 1's required fix, plus the user's own end-of-run-summary
# design call) ---------------------------------------------------------------


def _naked_eye_source_stub() -> NakedEyePerceptionSource:
    """A `NakedEyePerceptionSource` for exercising
    `_warn_live_los_coverage_gap_once`/`_log_live_los_coverage_summary` in
    isolation from a real poll -- `aircraft_client` is never called by
    either function under test, so `None` is enough (`live_los_coverage`
    itself is the only field either function reads)."""
    return NakedEyePerceptionSource(
        aircraft_client=None,  # type: ignore[arg-type]
        theatre="Syria",
        world_model_conn=sqlite3.connect(":memory:"),
    )


def test_warn_live_los_coverage_gap_once_fires_exactly_once_under_continuous_growth(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """This is the review's own reproduction of the defect, run against
    the fix: `no_verdict` growing every poll (a continuously dead feed)
    used to log on every one of these polls -- the exact flood the
    docstring claimed not to produce. Driven over 10 polls, the same
    count the Reviewer used. Asserts the record count is exactly 1, not
    `>= 1` -- `>= 1` is what the pre-fix flood already satisfies."""
    source = _naked_eye_source_stub()
    warned = False
    with caplog.at_level(logging.WARNING, logger=logger_module.__name__):
        for no_verdict in range(1, 11):
            source.live_los_coverage.no_verdict = no_verdict
            warned = _warn_live_los_coverage_gap_once([source], warned)

    assert warned is True
    warnings = [r for r in caplog.records if "live LOS coverage gap" in r.getMessage()]
    assert len(warnings) == 1, warnings


def test_warn_live_los_coverage_gap_once_never_fires_while_no_verdict_stays_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The healthy-sortie case: a live feed with no coverage gap at all
    must never log the transition warning, across many polls."""
    source = _naked_eye_source_stub()
    warned = False
    with caplog.at_level(logging.WARNING, logger=logger_module.__name__):
        for _ in range(10):
            warned = _warn_live_los_coverage_gap_once([source], warned)

    assert warned is False
    assert caplog.records == []


def test_log_live_los_coverage_summary_logs_zero_over_evaluated_when_healthy(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The guard-visibly-passing case (user's own design call): a sortie
    with real gate-4 traffic but no coverage gap still gets an end-of-run
    line, reading `0/<evaluated>` rather than nothing at all."""
    source = _naked_eye_source_stub()
    source.live_los_coverage.evaluated = 7
    source.live_los_coverage.no_verdict = 0

    with caplog.at_level(logging.INFO, logger=logger_module.__name__):
        _log_live_los_coverage_summary([source])

    messages = [r.getMessage() for r in caplog.records]
    assert messages == [
        "live LOS coverage: 0/7 gate-4 evaluations had no live verdict this sortie"
    ], messages


def test_console_poll_loop_logs_the_coverage_summary_in_its_finally_block(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`_run_console_poll_loop`'s own teardown, not a direct call: drives
    a real poll with a candidate carrying no `unit_name` (no live-LOS
    join key), so gate 4 rejects it fail-closed and `no_verdict` becomes
    1 -- then stops the loop and asserts the summary line landed with the
    real totals, proving it runs from `finally:` and not just when called
    directly."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": [_t72_world_object_no_live_verdict()]}
    )
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    stop_event = threading.Event()

    poll_thread = threading.Thread(
        target=_run_console_poll_loop,
        args=(runner, aircraft_client, "Syria", db_path, 10.0, stop_event),
    )
    with caplog.at_level(logging.INFO, logger=logger_module.__name__):
        poll_thread.start()
        try:
            deadline = time.monotonic() + 5.0
            while runner.last_t_sim is None and time.monotonic() < deadline:
                time.sleep(0.02)
        finally:
            stop_event.set()
            poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    summaries = [
        r.getMessage() for r in caplog.records if "live LOS coverage:" in r.getMessage()
    ]
    assert summaries == [
        "live LOS coverage: 1/1 gate-4 evaluations had no live verdict this sortie"
    ], summaries


def test_crew_text_poll_loop_logs_the_coverage_summary_in_its_finally_block(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Same proof as the console-loop test above, for
    `_run_crew_text_poll_loop`'s own `finally:` -- the two loops share no
    code path for this, each wires the summary call independently, and
    the review's blast-radius lesson (`plans/bl11-stage4-fail-closed/
    review.md`) is exactly that a fix applied to one loop and not its
    twin goes unnoticed."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": [_t72_world_object_no_live_verdict()]}
    )
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    crew_console = CrewConsole(store=runner.store)
    stop_event = threading.Event()

    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            db_path,
            10.0,
            stop_event,
        ),
    )
    with caplog.at_level(logging.INFO, logger=logger_module.__name__):
        poll_thread.start()
        try:
            deadline = time.monotonic() + 5.0
            while runner.last_t_sim is None and time.monotonic() < deadline:
                time.sleep(0.02)
        finally:
            stop_event.set()
            poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    summaries = [
        r.getMessage() for r in caplog.records if "live LOS coverage:" in r.getMessage()
    ]
    assert summaries == [
        "live LOS coverage: 1/1 gate-4 evaluations had no live verdict this sortie"
    ], summaries


# -- `BL-B71`'s review fix round, corrected 2026-10-16 (user direction:
# "actual behavior must measure by used optic") -- `_run_crew_text_poll_
# loop` must pass `drain_attack_run` the optic that actually resolved
# this poll's look (`runner.optic`), not the guidance ladder's own grant
# (`runner.optic_state.guidance_optic`), which is `None` through ordinary
# glassing with no standing guidance request at all. -------------------


def test_crew_text_poll_loop_passes_the_used_optic_not_the_guidance_grant(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Drives the real `_run_crew_text_poll_loop` with `run_once` replaced
    by a no-op, so the loop body runs against hand-set `runner` state
    rather than a freshly recomputed one -- the only piece this test
    cares about is which field the loop's own `drain_attack_run` call
    site reads, not how `decide_optic` arrives at either value (that is
    `test_optic_policy.py`'s job).

    The scenario is the narrower case the review's divergence note
    named: ordinary glassing has `runner.optic` at `BINOCULAR_OPTIC`
    this poll (`OpticPhase.GLASSING`, continuing a steady look), while
    `runner.optic_state.guidance_optic` is `None` -- no attack-run
    guidance grant exists at all. `crew_console.drain_attack_run` is
    replaced with a spy (not a stub of `decide`'s own logic -- that is
    covered directly by `test_attack_run.py`'s `resolving_optic` tests)
    so this test asserts exactly one thing: the value crossing the
    `logger.py`/`crew_console.py` boundary.

    Confirmed to fail for the stated reason: reverting the call site
    to `resolving_optic=runner.optic_state.guidance_optic` makes
    `captured["resolving_optic"]` come back `None` instead of
    `BINOCULAR_OPTIC` -- `UNAIDED_OPTIC` is what `_no_look_cause` would
    then test range against, misattributing a live binocular look as
    "too far." Restored afterward; `git diff --stat` empty."""
    from belief.attack_run import AttackRunState
    from belief.optic_policy import OpticPhase, OpticState
    from perception.optics import BINOCULAR_OPTIC

    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": []}
    )
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    crew_console = CrewConsole(store=runner.store)

    # Hand-set the state a completed poll would have left behind, rather
    # than letting a real `run_once()` compute it -- `decide_optic`'s own
    # GLASSING-continuation branch is exercised elsewhere
    # (`test_optic_policy.py`); this test only needs the two fields to
    # disagree the way the bug made them agree.
    runner.last_t_sim = 0.0
    runner.last_ownship_state = OwnshipState(
        t_sim=0.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0
    )
    runner.optic = BINOCULAR_OPTIC
    runner.optic_state = OpticState(
        phase=OpticPhase.GLASSING, phase_started_sim=0.0, guidance_optic=None
    )
    runner.attack_run_state = AttackRunState()
    monkeypatch.setattr(runner, "run_once", lambda: None)

    captured: dict[str, object] = {}
    done = threading.Event()

    def spy_drain_attack_run(
        state: AttackRunState | None,
        now_sim: float,
        ownship: OwnshipState,
        *,
        resolving_optic: object = None,
    ) -> AttackRunState | None:
        captured["resolving_optic"] = resolving_optic
        done.set()
        return state

    monkeypatch.setattr(crew_console, "drain_attack_run", spy_drain_attack_run)

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            db_path,
            10.0,
            stop_event,
        ),
    )
    poll_thread.start()
    try:
        assert done.wait(timeout=5.0), (
            "drain_attack_run was never called -- the hand-set poll state "
            "did not reach the call site under test"
        )
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert captured["resolving_optic"] is BINOCULAR_OPTIC
    assert captured["resolving_optic"] is not runner.optic_state.guidance_optic


# -- `BL-15` Stage 1 (`plans/bl15-mission-start/plan.md`) -- the real poll
# loop detects a genuine mission (re)start and resets belief/mission
# memory. The per-class completeness guarantee (every field not in a
# documented preserve-set resets to its constructor default) lives in
# `test_mission_start_reset.py`; this is the wiring-level proof that
# `_check_for_new_mission` is actually reached from `_run_crew_text_poll_
# loop`, once per poll, before `run_once()`. -------------------------


def test_crew_text_poll_loop_resets_belief_on_mission_restart(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Drives the real `_run_crew_text_poll_loop` with `run_once` replaced
    by a no-op (same technique as the optic test above) -- this test only
    cares whether the loop's own `_check_for_new_mission` call site fires a
    reset when the aircraft layer reports a new `sequence`, not how
    `run_once` itself behaves."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": []}
    )
    # Simulate a process that has already seen sequence 1 (its own first
    # poll, already settled) -- the aircraft layer now reports sequence 2,
    # a genuine restart, from this poll loop's very first iteration.
    aircraft_client.mission_start_sequence = 2

    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    runner.last_mission_start_sequence = 1
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    crew_console.commands_handled = 5  # mission-scoped -- must reset

    runner.tasks.create(
        "scan_area",
        AttentionArea(
            id="AREA_1",
            center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
            radius_m=None,
            level="watch",
            source="scan_area",
            relative_sector="right",
        ),
        created_sim=0.0,
        deadline_sim=100.0,
        reason="test",
    )
    assert runner.tasks.tasks  # pre-condition: not already empty

    monkeypatch.setattr(runner, "run_once", lambda: None)

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            db_path,
            10.0,
            stop_event,
        ),
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_mission_start_sequence != 2 and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert runner.last_mission_start_sequence == 2
    assert runner.tasks.tasks == []
    assert crew_console.commands_handled == 0


def test_crew_text_poll_loop_switches_theatre_on_mission_restart(
    tmp_path: Path,
) -> None:
    """`BL-15` Stage 3, wiring-level proof: the real `_run_crew_text_poll_
    loop` passes `world_model_dir`/`trace_sink`/`forest_occlusion` through
    to `_check_for_new_mission` correctly, and an event naming a new
    theatre actually switches `runner.theatre`/`runner.world_model_conn`
    rather than the unit-level `_maybe_switch_theatre` tests (`test_
    mission_start_reset.py`) merely exercising the function in isolation."""
    from store.models import Region
    from store.writer import insert_region

    syria_path = tmp_path / "syria-full.sqlite"
    afghanistan_path = tmp_path / "afghanistan-full.sqlite"
    for path, theatre in ((syria_path, "Syria"), (afghanistan_path, "Afghanistan")):
        conn = open_for_build(path)
        insert_region(
            conn,
            Region(
                name=f"{theatre.lower()}-full",
                theatre=theatre,
                centre_x=0.0,
                centre_z=0.0,
                half_extent_x_m=1000.0,
                half_extent_z_m=1000.0,
                built_at="2026-10-19T00:00:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": []}
    )
    aircraft_client.mission_start_sequence = 2
    aircraft_client.mission_start_theatre = "Afghanistan"

    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    runner.last_mission_start_sequence = 1
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            syria_path,
            10.0,
            stop_event,
        ),
        kwargs={"world_model_dir": tmp_path},
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_mission_start_sequence != 2 and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert runner.theatre == "Afghanistan"
    assert crew_console.refused is False


def test_crew_text_poll_loop_refuses_commands_when_new_theatre_has_no_store(
    tmp_path: Path,
) -> None:
    """Same wiring, the degrade path: the mission's new theatre has no
    store at `world_model_dir`, so the real poll loop must enter refusal
    mode rather than crash or silently keep the old store running."""
    syria_path = tmp_path / "syria-full.sqlite"
    conn = open_for_build(syria_path)
    conn.close()

    aircraft_client = FakeConsoleAircraftClient(
        _console_telemetry_dict(), {"objects": []}
    )
    aircraft_client.mission_start_sequence = 2
    aircraft_client.mission_start_theatre = "Afghanistan"  # no store built for it

    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    runner.last_mission_start_sequence = 1
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            syria_path,
            10.0,
            stop_event,
        ),
        kwargs={"world_model_dir": tmp_path},
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while crew_console.refused is False and time.monotonic() < deadline:
            time.sleep(0.02)
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert crew_console.refused is True
    assert crew_console.handle_command("watch_nearest", now_sim=0.0) == [
        "system error, world model not loaded"
    ]


def test_connection_reporter_says_disconnected_once_then_connected_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One line when the collector goes away, one when it returns, and
    nothing for the retries in between.

    The poll loop retries every `poll_interval_s`, so before this an
    unreachable aircraft layer printed a fresh traceback every second for
    as long as it stayed down. The pilot needs the state change, not the
    same fact once a second (user direction, 2026-10-02).

    Asserts the actual emitted messages rather than call counts -- these
    are lines a person reads on a terminal while flying, so the test pins
    what they say.
    """
    reporter = logger_module._ConnectionReporter()
    dead = AircraftLayerError("request to http://host/x failed: refused")

    with caplog.at_level(logging.INFO, logger=logger_module.__name__):
        reporter.report_failure(dead)
        reporter.report_failure(dead)
        reporter.report_failure(dead)
        reporter.report_success()
        reporter.report_success()

    messages = [record.getMessage() for record in caplog.records]
    assert messages == [
        "aircraft layer disconnected (request to http://host/x failed: refused)",
        "aircraft layer connected",
    ], messages


def test_connection_reporter_announces_the_first_connection(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A first successful poll says "connected" rather than staying silent.

    The state starts unknown rather than connected precisely so this
    happens -- "it is working" is worth one line at startup, and without
    it the pilot cannot tell a healthy run from one that has not reached
    the collector yet.
    """
    reporter = logger_module._ConnectionReporter()

    with caplog.at_level(logging.INFO, logger=logger_module.__name__):
        reporter.report_success()

    assert [r.getMessage() for r in caplog.records] == ["aircraft layer connected"]


def test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Each real transition gets its own line -- the suppression is of
    repeats, not of subsequent events."""
    reporter = logger_module._ConnectionReporter()
    dead = AircraftLayerError("request to http://host/x failed: refused")

    with caplog.at_level(logging.INFO, logger=logger_module.__name__):
        reporter.report_failure(dead)
        reporter.report_success()
        reporter.report_failure(dead)
        reporter.report_failure(dead)
        reporter.report_success()

    assert [r.getMessage() for r in caplog.records] == [
        "aircraft layer disconnected (request to http://host/x failed: refused)",
        "aircraft layer connected",
        "aircraft layer disconnected (request to http://host/x failed: refused)",
        "aircraft layer connected",
    ]


def test_only_a_dead_socket_counts_as_connection_loss() -> None:
    """A defect in our own poll cycle still gets its traceback.

    `AircraftLayerError` is raised both for an unreachable collector and
    for a reply that is not valid JSON, so the cause chain is what
    separates them. Collapsing a real defect into a quiet "disconnected"
    line is the failure this distinction exists to prevent -- it would
    hide exactly the bug a flight is meant to surface.
    """
    refused = AircraftLayerError("unreachable")
    refused.__cause__ = urllib.error.URLError("connection refused")
    timed_out = AircraftLayerError("unreachable")
    timed_out.__cause__ = TimeoutError("timed out")
    bad_json = AircraftLayerError("invalid JSON from http://host/x: line 1")

    assert logger_module._is_connection_loss(refused) is True
    assert logger_module._is_connection_loss(timed_out) is True
    assert logger_module._is_connection_loss(bad_json) is False
    assert logger_module._is_connection_loss(ValueError("something else")) is False


# --- _wait_for_next_tick (BL-11 Stage 1) ---------------------------------


def test_wait_for_next_tick_sleeps_only_the_remainder_of_the_interval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The defect this fixes: the loops used to wait the *whole* interval
    after the work, so a 1.0 s setting with 0.33 s of work realised 1.33 s.
    Sleeping to a deadline means the wait absorbs the work."""
    waits: list[float] = []
    monkeypatch.setattr(logger_module.time, "monotonic", lambda: 100.33)
    stop_event = threading.Event()
    monkeypatch.setattr(stop_event, "wait", lambda timeout: waits.append(timeout))

    next_tick = logger_module._wait_for_next_tick(stop_event, 101.0, 1.0)

    assert waits == [pytest.approx(0.67)]
    assert next_tick == pytest.approx(102.0)


def test_wait_for_next_tick_does_not_sleep_when_the_work_overran(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An overrunning poll gets no sleep at all -- it is already late."""
    waits: list[float] = []
    monkeypatch.setattr(logger_module.time, "monotonic", lambda: 101.4)
    stop_event = threading.Event()
    monkeypatch.setattr(stop_event, "wait", lambda timeout: waits.append(timeout))

    next_tick = logger_module._wait_for_next_tick(stop_event, 101.0, 1.0)

    assert waits == []
    assert next_tick == pytest.approx(102.4)


def test_wait_for_next_tick_drops_missed_ticks_rather_than_queueing_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The stated overrun policy (`_wait_for_next_tick`'s own docstring):
    a poll that overran by several intervals re-bases its next deadline on
    the clock now, so the debt is *dropped*. Advancing by one interval
    regardless would queue the missed ticks and make the loop run
    back-to-back with no sleep until it had repaid them -- on a thread that
    is already behind, and with nothing to catch up on, since every poll
    reads the latest telemetry rather than a backlog."""
    waits: list[float] = []
    # Four intervals past a 1.0 s deadline.
    monkeypatch.setattr(logger_module.time, "monotonic", lambda: 105.0)
    stop_event = threading.Event()
    monkeypatch.setattr(stop_event, "wait", lambda timeout: waits.append(timeout))

    next_tick = logger_module._wait_for_next_tick(stop_event, 101.0, 1.0)

    assert waits == []
    # 106.0, not 102.0: the three skipped ticks are gone, and the next poll
    # gets a full interval of sleep rather than none.
    assert next_tick == pytest.approx(106.0)


def test_wait_for_next_tick_returns_immediately_when_stopping() -> None:
    """A set `stop_event` must not hold the loop for a whole interval --
    `Event.wait` returns at once, which is what makes shutdown prompt."""
    stop_event = threading.Event()
    stop_event.set()

    started = time.monotonic()
    logger_module._wait_for_next_tick(stop_event, started + 5.0, 5.0)

    assert time.monotonic() - started < 1.0


def test_no_stale_five_hertz_claims_remain_in_src() -> None:
    """`BL-11` Stage 1/6: body-layer's poll interval has been 1.0 s since
    `abf49cd` and has never been 5 Hz -- that is `Export.lua`'s producer
    rate. Three docstrings claiming otherwise produced `BL-B30`'s wrong
    premise, so a reappearance is worth failing a build over.

    `perception/motion.py` is deliberately exempt: its 5 Hz claim is a
    *behavioural* assumption about object arrival rate, tracked as
    `BL-B34`, not a statement about this loop's own rate."""
    src = Path(logger_module.__file__).parent
    offenders = sorted(
        str(path.relative_to(src))
        for path in src.rglob("*.py")
        if path.name != "motion.py"
        and any(claim in path.read_text(encoding="utf-8") for claim in ("5 Hz", "5Hz"))
    )

    assert offenders == []


# -- Live LOS coverage logging, plain-logger entry point
# (`plans/bl11-stage4-fail-closed/implementation.md` round 3, Security's
# advisory finding) -----------------------------------------------------


def _run_plain_logger_main_for_n_polls(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    url: str,
    n_polls: int,
) -> None:
    """Drives `main()`'s bare `else:` branch (no `--console`/`--crew-text`)
    through exactly `n_polls` iterations of its `while True:` loop, then
    stops it the same way a real operator does -- `KeyboardInterrupt` --
    by rebinding the `time` name inside `logger` module's own namespace
    (not the real `time` module's `sleep` attribute) to a stand-in that
    raises on the `n_polls`-th call rather than actually sleeping.

    **Deliberately not `monkeypatch.setattr(logger_module.time, "sleep",
    ...)`** -- that mutates the real, process-wide `time` module, so any
    *other* thread calling `time.sleep` during this test (e.g. a leftover
    `belief.brain_client.BrainLayerClient` daemon poll thread from an
    earlier test in the same pytest session, still retry-backoff-sleeping
    because nothing stops a `daemon=True` thread) gets an unrelated
    `KeyboardInterrupt` raised inside it too -- observed as a
    `PytestUnhandledThreadExceptionWarning` the first time this was tried.
    Rebinding `logger_module.time` itself only changes what `logger.py`'s
    own `time.sleep(...)` call resolves to; every other module's `import
    time` still gets the real one.

    `main()` itself is not restructured; this calls it exactly as the CLI
    would, the same `sys.argv`-monkeypatch pattern
    `test_main_rejects_neither_theatre_pair_nor_mission_understanding`
    already uses elsewhere in this file for `main()`'s argparse path --
    extended here to also drive the loop body, since the plain-logger
    branch has no extracted `_run_*_poll_loop` function of its own to call
    directly (unlike `--console`/`--crew-text`)."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "logger",
            "--aircraft-layer-url",
            url,
            "--theatre",
            "Syria",
            "--world-model-db",
            str(db_path),
        ],
    )

    real_time = time

    class _RaiseAfterNSleeps:
        """Stands in for the `time` module as seen from inside `logger.py`
        only -- every other attribute `main()` touches before reaching the
        poll loop (`time.time()`, for `_per_run_log_paths`'s stamping)
        delegates to the real module unchanged; only `sleep` is faked."""

        def __init__(self) -> None:
            self._calls = 0

        def sleep(self, _seconds: float) -> None:
            self._calls += 1
            if self._calls >= n_polls:
                raise KeyboardInterrupt

        def __getattr__(self, name: str) -> object:
            return getattr(real_time, name)

    monkeypatch.setattr(logger_module, "time", _RaiseAfterNSleeps())
    logger_module.main()


def test_plain_logger_path_warns_on_the_live_los_coverage_gap_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Security's advisory finding: `main()`'s plain-logger `else:` branch
    (reached with neither `--console` nor `--crew-text`) shares
    `_build_sources` with the two instrumented poll loops, so it is
    subject to the identical fail-closed gate 4 -- but before this fix,
    nothing in this branch ever called `_warn_live_los_coverage_gap_once`
    at all, so a dead live-LOS feed here produced no signal whatsoever,
    not even delayed. Drives two polls against a single frame with no
    `"line_of_sight"` key at all (the feed-absent cause, `naked_eye_source.
    _resolve_live_los_by_object_id`'s `line_of_sight is None` branch) and
    a world object with no `unit_name` either, so gate 4 rejects it
    fail-closed on both polls. The transition fires on poll 1
    (`no_verdict` 0 -> 1) and must not fire again on poll 2 (`no_verdict`
    1 -> 2, not a zero-to-nonzero transition) -- asserts exactly one
    record, not `>= 1`, the same distinction round 2's pure-function test
    makes for the same reason."""
    frames = [
        {
            "telemetry": _console_telemetry_dict(),
            "world_objects": {"objects": [_t72_world_object_no_live_verdict()]},
        }
    ]
    server = MockAircraftLayerServer(frames)
    url = server.start()
    try:
        with caplog.at_level(logging.WARNING, logger=logger_module.__name__):
            _run_plain_logger_main_for_n_polls(monkeypatch, tmp_path, url, n_polls=2)
    finally:
        server.stop()

    warnings = [r for r in caplog.records if "live LOS coverage gap" in r.getMessage()]
    assert len(warnings) == 1, warnings


def test_plain_logger_path_logs_the_coverage_summary_in_its_finally_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Same finding, the other half: before this fix, this branch's
    `finally:` only closed `world_model_conn` -- a dead feed here was
    silent in the strongest sense this whole plan exists to prevent, not
    even summarised post-flight. Same two-poll drive as the warning test
    above (one frame, no live-LOS feed at all, held across both polls by
    `MockAircraftLayerServer`'s "holds at the last frame" semantics), so
    the accumulated totals are `evaluated=2, no_verdict=2` by the time
    `KeyboardInterrupt` unwinds into `finally:`."""
    frames = [
        {
            "telemetry": _console_telemetry_dict(),
            "world_objects": {"objects": [_t72_world_object_no_live_verdict()]},
        }
    ]
    server = MockAircraftLayerServer(frames)
    url = server.start()
    try:
        with caplog.at_level(logging.INFO, logger=logger_module.__name__):
            _run_plain_logger_main_for_n_polls(monkeypatch, tmp_path, url, n_polls=2)
    finally:
        server.stop()

    summaries = [
        r.getMessage() for r in caplog.records if "live LOS coverage:" in r.getMessage()
    ]
    assert summaries == [
        "live LOS coverage: 2/2 gate-4 evaluations had no live verdict this sortie"
    ], summaries


# -- Logging visibility under the real, unconfigured default (`plans/
# bl11-stage4-fail-closed/dod-check.md`'s required fix): every test above
# this point proves the call fires, using `caplog.at_level(...)`, which
# forcibly lowers the effective level for its block -- exactly the thing
# that hid this defect from four review rounds. These two prove the two
# log lines are visible with *no* level override at all, i.e. under
# whatever `main()` itself configures (`_configure_logger_for_main`), the
# same way a real operator running `python -m logger ...` would see
# them. ------------------------------------------------------------------


def test_log_live_los_coverage_summary_is_visible_under_default_logging_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """No `caplog.at_level` anywhere in this test -- `capsys` captures
    whatever actually lands on the real `sys.stderr` stream, which is
    exactly what the DoD's repro ran against directly
    (`PYTHONPATH=... python -c "logger.logger.info(...)"`). Same two-poll
    drive as `test_plain_logger_path_logs_the_coverage_summary_in_its_
    finally_block` above, so the expected totals are identical; the only
    difference is the absence of a level override, which is the point."""
    frames = [
        {
            "telemetry": _console_telemetry_dict(),
            "world_objects": {"objects": [_t72_world_object_no_live_verdict()]},
        }
    ]
    server = MockAircraftLayerServer(frames)
    url = server.start()
    try:
        _run_plain_logger_main_for_n_polls(monkeypatch, tmp_path, url, n_polls=2)
    finally:
        server.stop()

    stderr = capsys.readouterr().err
    assert (
        "live LOS coverage: 2/2 gate-4 evaluations had no live verdict this sortie"
        in stderr
    ), stderr


def test_live_los_coverage_gap_warning_is_visible_under_default_logging_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The transition warning's half of the same proof. This one worked
    even before the fix, by accident of `logging.lastResort`'s own
    `WARNING` threshold -- nothing pinned that it stays visible once
    `_configure_logger_for_main` starts managing this logger's level and
    handler explicitly, so this is a regression guard for the fix itself,
    not only a test of pre-existing behaviour."""
    frames = [
        {
            "telemetry": _console_telemetry_dict(),
            "world_objects": {"objects": [_t72_world_object_no_live_verdict()]},
        }
    ]
    server = MockAircraftLayerServer(frames)
    url = server.start()
    try:
        _run_plain_logger_main_for_n_polls(monkeypatch, tmp_path, url, n_polls=2)
    finally:
        server.stop()

    stderr = capsys.readouterr().err
    assert "live LOS coverage gap" in stderr, stderr


# -- `BL-B66` review required fix (`plans/9k113-effectors/review.md`) -- the
# `_run_crew_text_poll_loop` wiring for the guidance-unit power-up (takeoff
# detection -> sequencer advance -> `sight_ready` -> "Guidance unit ready"
# spoken exactly once) and the OBSERV/weapons-safety cockpit write-through
# had no test driving the *real* poll loop, only `belief.sight_effector`'s
# own pure-function tests in isolation. Confirmed by the reviewer via
# mutation: forcing the takeoff rising-edge `if` to `False`, and separately
# removing the `announced` guard in `CrewConsole.drain_guidance_unit_ready`,
# both left the full suite green. These tests drive `_run_crew_text_poll_
# loop` on a real thread, same technique as `test_crew_text_poll_loop_
# resets_belief_on_mission_restart` above, mutating the fake client's
# telemetry between polls the way a real sortie's clock would. --------------


def test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop(
    tmp_path: Path,
) -> None:
    """The full Stage 2 sequence, through the real loop: no write while
    still on the ground; the four switches written in order on the
    takeoff rising edge; `sight_ready` becomes `True` only after the
    fourth; "Guidance unit ready." spoken exactly once across several
    subsequent polls, not once per poll."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    telemetry = _console_telemetry_dict()
    telemetry["altitude_agl_m"] = 5.0  # on the ground (<= the 10 m threshold)
    telemetry["dcs_model_time_s"] = 0.0

    aircraft_client = FakeConsoleAircraftClient(telemetry, {"objects": []})
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    crew_console.output = io.StringIO()

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            db_path,
            0.01,
            stop_event,
        ),
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_t_sim is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert runner.last_t_sim is not None, "the first on-ground poll never landed"

        # No power-up while still on the ground.
        assert aircraft_client.cockpit_switch_writes == []
        assert crew_console.sight_ready is False

        # Takeoff: the rising edge.
        telemetry["altitude_agl_m"] = 500.0
        sim_t = 1.0
        telemetry["dcs_model_time_s"] = sim_t

        deadline = time.monotonic() + 5.0
        while (
            len(aircraft_client.cockpit_switch_writes) < 4
            and time.monotonic() < deadline
        ):
            # `sight_ready` must not flip true before the fourth switch is
            # written -- checked every iteration a partial count is seen,
            # not only at the end, so a sequencer that readied early would
            # be caught even if the 4th write landed on the very next tick.
            seen = len(aircraft_client.cockpit_switch_writes)
            if 0 < seen < 4:
                assert crew_console.sight_ready is False, (
                    f"sight_ready went true after only {seen} of 4 switches"
                )
            # Each write is gated by `GUIDANCE_UNIT_SWITCH_DELAY_S` of *sim*
            # time, not wall time -- advance the fake's own clock, or the
            # sequence stalls after the first switch.
            sim_t += GUIDANCE_UNIT_SWITCH_DELAY_S + 0.1
            telemetry["dcs_model_time_s"] = sim_t
            time.sleep(0.02)

        assert aircraft_client.cockpit_switch_writes == [
            (6, 3028, 1.0),
            (16, 3015, 1.0),
            (7, 3001, 1.0),
            (6, 3030, 1.0),
        ], aircraft_client.cockpit_switch_writes

        # A few more polls, sim time still advancing -- "Guidance unit
        # ready." must stay spoken exactly once, not once per poll
        # (the reviewer's second mutation: removing the `announced` guard).
        for _ in range(6):
            sim_t += 0.5
            telemetry["dcs_model_time_s"] = sim_t
            time.sleep(0.02)
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert crew_console.sight_ready is True
    assert runner.guidance_unit_state.sight_ready is True
    assert runner.guidance_unit_state.guidance_unit_ready_announced is True
    assert isinstance(crew_console.output, io.StringIO)
    spoken = crew_console.output.getvalue()
    assert spoken.count("Guidance unit ready.") == 1, spoken


def test_second_takeoff_in_the_same_mission_does_not_rerun_the_power_up(
    tmp_path: Path,
) -> None:
    """Plan §2: `takeoff_seen` is a one-shot latch per mission -- a
    touch-and-go (landing, then taking off again) must not re-run the
    four-switch sequence. Starts from an already-ready `GuidanceUnitState`
    (bypassing the full sequence, which the test above already covers) so
    this test only has to drive the second edge."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    telemetry = _console_telemetry_dict()
    telemetry["altitude_agl_m"] = 500.0  # already airborne
    sim_t = 100.0
    telemetry["dcs_model_time_s"] = sim_t

    aircraft_client = FakeConsoleAircraftClient(telemetry, {"objects": []})
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    runner.guidance_unit_state = GuidanceUnitState(
        takeoff_seen=True,
        power_up_stage=4,
        sight_ready=True,
        guidance_unit_ready_announced=True,
    )
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            db_path,
            0.01,
            stop_event,
        ),
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_t_sim is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert runner.last_t_sim is not None

        # Land, then take off again.
        telemetry["altitude_agl_m"] = 5.0
        sim_t += 1.0
        telemetry["dcs_model_time_s"] = sim_t
        deadline = time.monotonic() + 5.0
        while not crew_console.on_ground and time.monotonic() < deadline:
            time.sleep(0.01)
        assert crew_console.on_ground is True, "the landing was never observed"

        telemetry["altitude_agl_m"] = 500.0
        sim_t += 1.0
        telemetry["dcs_model_time_s"] = sim_t
        deadline = time.monotonic() + 5.0
        while crew_console.on_ground and time.monotonic() < deadline:
            time.sleep(0.01)
        assert crew_console.on_ground is False, "the second takeoff was never observed"

        # A few more polls to give a wrongly-re-armed sequencer a chance to
        # write again.
        for _ in range(5):
            sim_t += GUIDANCE_UNIT_SWITCH_DELAY_S + 0.1
            telemetry["dcs_model_time_s"] = sim_t
            time.sleep(0.02)
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert aircraft_client.cockpit_switch_writes == []
    assert runner.guidance_unit_state.power_up_stage == 4


def test_observ_and_weapons_safety_write_through_the_real_poll_loop(
    tmp_path: Path,
) -> None:
    """Stage 3/4: once `sight_ready`, "Observ on" writes arg 886 (device
    7, cmd 3002, value 1.0); "weapons armed"/"weapons safe" write arg 673
    (device 6, cmd 3020) -- all through the real `handle_command` ->
    `_run_crew_text_poll_loop` drain path, not just the handler setting
    the one-shot transition field. Also: "Observ on" *before* ready writes
    nothing and is refused (the gate is synchronous in `_handle_observ_on`,
    unit-tested in `test_crew_console.py`, but reproduced here against the
    real loop so a future change to the gate's wiring is caught here too)."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    telemetry = _console_telemetry_dict()
    # On the ground, matching `CrewConsole.on_ground`'s own default
    # (`True`) -- so the first poll is *not* a takeoff rising edge, and
    # the power-up sequence genuinely has not started yet for the
    # pre-ready OBSERV-on refusal below.
    telemetry["altitude_agl_m"] = 5.0
    sim_t = 100.0
    telemetry["dcs_model_time_s"] = sim_t

    aircraft_client = FakeConsoleAircraftClient(telemetry, {"objects": []})
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    # Not yet ready -- the pre-ready OBSERV-on refusal is checked against
    # this state before the sequence is set up to complete.
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            db_path,
            0.01,
            stop_event,
        ),
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_t_sim is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert runner.last_t_sim is not None
        assert crew_console.sight_ready is False

        # OBSERV on before ready: refused, no write.
        lines = crew_console.handle_command("observ_on", now_sim=sim_t)
        assert lines == ["Unable, guidance unit not ready."]
        time.sleep(0.1)
        assert aircraft_client.cockpit_switch_writes == []

        # Make the guidance unit ready without re-running takeoff detection
        # (already covered above) -- jump the state directly, same as the
        # second-takeoff test.
        runner.guidance_unit_state = GuidanceUnitState(
            takeoff_seen=True,
            power_up_stage=4,
            sight_ready=True,
            guidance_unit_ready_announced=True,
        )
        deadline = time.monotonic() + 5.0
        while not crew_console.sight_ready and time.monotonic() < deadline:
            time.sleep(0.01)
        assert crew_console.sight_ready is True

        lines = crew_console.handle_command("observ_on", now_sim=sim_t)
        assert lines == ["Observ on."]
        deadline = time.monotonic() + 5.0
        while (
            7,
            3002,
            1.0,
        ) not in aircraft_client.cockpit_switch_writes and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (7, 3002, 1.0) in aircraft_client.cockpit_switch_writes

        lines = crew_console.handle_command("weapons_armed", now_sim=sim_t)
        assert lines == ["Weapons armed."]
        deadline = time.monotonic() + 5.0
        while (
            6,
            3020,
            1.0,
        ) not in aircraft_client.cockpit_switch_writes and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (6, 3020, 1.0) in aircraft_client.cockpit_switch_writes

        lines = crew_console.handle_command("weapons_safe", now_sim=sim_t)
        assert lines == ["Weapons safe."]
        deadline = time.monotonic() + 5.0
        while (
            6,
            3020,
            0.0,
        ) not in aircraft_client.cockpit_switch_writes and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (6, 3020, 0.0) in aircraft_client.cockpit_switch_writes
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    assert runner.guidance_unit_state.observ_commanded is True
    assert runner.guidance_unit_state.weapon_safety_commanded == "safe"


def test_slew_trace_is_written_from_the_real_poll_loop(tmp_path: Path) -> None:
    """`BL-B66` Stage 4b -- `--slew-trace` is wired through a real
    `_run_crew_text_poll_loop` run, not only exercised against
    `SightTraceWriter`/`sight_effector` in isolation (the wiring-gap
    lesson from this branch's own review: a module's unit tests passing
    does not mean the poll loop actually calls it). Drives OBSERV on, a
    sight-position readback arriving via the fake's `cockpit_switch_state`,
    and OBSERV off again -- then asserts on the rows actually written to
    disk, in order."""
    db_path = tmp_path / "region.sqlite"
    conn = open_for_build(db_path)
    conn.close()

    telemetry = _console_telemetry_dict()
    telemetry["altitude_agl_m"] = 500.0  # airborne; no takeoff edge to chase
    sim_t = 100.0
    telemetry["dcs_model_time_s"] = sim_t

    aircraft_client = FakeConsoleAircraftClient(telemetry, {"objects": []})
    runner = ConsolePerceptionRunner(aircraft_client=aircraft_client)  # type: ignore[arg-type]
    # Already ready -- the power-up sequence itself is covered above.
    runner.guidance_unit_state = GuidanceUnitState(
        takeoff_seen=True,
        power_up_stage=4,
        sight_ready=True,
        guidance_unit_ready_announced=True,
    )
    crew_console = CrewConsole(store=runner.store, tasks=runner.tasks)
    slew_trace_path = tmp_path / "slew.jsonl"

    stop_event = threading.Event()
    poll_thread = threading.Thread(
        target=_run_crew_text_poll_loop,
        args=(
            runner,
            crew_console,
            aircraft_client,
            "Syria",
            db_path,
            0.01,
            stop_event,
        ),
        kwargs={"slew_trace_path": slew_trace_path},
    )
    poll_thread.start()
    try:
        deadline = time.monotonic() + 5.0
        while runner.last_t_sim is None and time.monotonic() < deadline:
            time.sleep(0.01)
        assert runner.last_t_sim is not None
        # At least one row before OBSERV is ever touched -- Stage 4b's own
        # "every poll, unconditionally" contract (unlike the Lua-side
        # per-frame log, which is OBSERV-gated).
        deadline = time.monotonic() + 5.0
        while not slew_trace_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert slew_trace_path.exists(), "no row was ever written"

        lines = crew_console.handle_command("observ_on", now_sim=sim_t)
        assert lines == ["Observ on."]
        deadline = time.monotonic() + 5.0
        while (
            7,
            3002,
            1.0,
        ) not in aircraft_client.cockpit_switch_writes and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (7, 3002, 1.0) in aircraft_client.cockpit_switch_writes

        # A sight-position readback arrives (as if from a hand-slew) --
        # the next poll's row must carry it, converted to degrees, with
        # `actual_azimuth_source == "readback"`.
        aircraft_client.cockpit_switch_state = {
            "t": sim_t,
            "received_wall_clock_s": 0.0,
            "observe_on": True,
            "weapons_armed": False,
            "sight_az": 0.16500,
            "sight_elev": -0.28125,
        }
        deadline = time.monotonic() + 5.0
        while (
            runner.guidance_unit_state.sight_az_raw is None
            and time.monotonic() < deadline
        ):
            sim_t += 0.5
            telemetry["dcs_model_time_s"] = sim_t
            time.sleep(0.02)
        assert runner.guidance_unit_state.sight_az_raw == pytest.approx(0.16500)
        # One more poll so the readback this test just set actually lands
        # in a written row (the write happens with that poll's own state,
        # not retroactively).
        sim_t += 0.5
        telemetry["dcs_model_time_s"] = sim_t
        time.sleep(0.1)

        lines = crew_console.handle_command("observ_off", now_sim=sim_t)
        assert lines == ["Observ off."]
        deadline = time.monotonic() + 5.0
        while (
            7,
            3002,
            0.0,
        ) not in aircraft_client.cockpit_switch_writes and time.monotonic() < deadline:
            time.sleep(0.01)
        assert (7, 3002, 0.0) in aircraft_client.cockpit_switch_writes
        time.sleep(0.1)
    finally:
        stop_event.set()
        poll_thread.join(timeout=5.0)

    assert not poll_thread.is_alive()
    rows = [
        json.loads(line)
        for line in slew_trace_path.read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) >= 2, "expected at least the pre- and post-readback rows"
    assert any(row["observ_commanded"] is True for row in rows)
    readback_rows = [row for row in rows if row["actual_azimuth_source"] == "readback"]
    assert readback_rows, rows
    assert readback_rows[-1]["actual_azimuth_deg"] == pytest.approx(22.5)
    assert readback_rows[-1]["raw_sight_az"] == pytest.approx(0.16500)
    assert readback_rows[-1]["raw_sight_elev"] == pytest.approx(-0.28125)
    # `[[BL-B80]]`: elevation now has a conversion too (derived) -- -0.28125
    # raw * 20.0 = -5.625 deg (`sight_elevation_raw_to_deg`'s one formula,
    # both signs).
    assert readback_rows[-1]["actual_elevation_source"] == "readback"
    assert readback_rows[-1]["actual_elevation_deg"] == pytest.approx(-5.625)
    assert any(row["observ_commanded"] is False for row in rows)
