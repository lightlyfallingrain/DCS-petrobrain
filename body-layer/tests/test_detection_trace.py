"""Tests for `perception.detection_trace`, `visibility.check_visibility`'s
new `trace` parameter, `naked_eye_source.NakedEyePerceptionSource`'s cluster/
observation annotation, and `detection_trace_writer.DetectionTraceWriter`'s
belief join (BL-9, `plans/bl9-debug-visualization/plan.md`).

Fixture conventions mirror `test_visibility.py`/`test_naked_eye_source.py`:
`WorldObjectCandidate` instances are built directly with DCS-native x/z, and
`visibility.line_of_sight_clear` is monkeypatched to always return `True`
so these tests exercise the cockpit-mask/angular-radius gates (and now the
trace they emit) without a real world-model `.sqlite`.
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from belief.contacts import ContactStore
from detection_trace_writer import DetectionTraceWriter
from perception import association, naked_eye_source, visibility
from perception.association import WorldObjectCandidate
from perception.detection_trace import (
    DetectionTrace,
    DetectionTraceCollector,
    GateOutcome,
)
from perception.gaze import ScanPlan
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC
from perception.source import OwnshipState
from perception.visibility import check_visibility
from replay import load_ownship_frames, replay

_FAKE_CONN = sqlite3.connect(":memory:")
_THEATRE = "Syria"
_FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def clear_line_of_sight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: True)


def _ownship(*, t_sim: float = 100.0, heading_true_deg: float = 0.0) -> OwnshipState:
    return OwnshipState(
        t_sim=t_sim, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=heading_true_deg
    )


def _candidate(
    object_type: str, *, object_id: int = 1, x: float, z: float, alt_m: float = 500.0
) -> WorldObjectCandidate:
    return WorldObjectCandidate(
        object_id=object_id,
        object_type=object_type,
        x=x,
        z=z,
        alt_m=alt_m,
        is_ownship=False,
    )


# --- Gate-outcome classification -------------------------------------------


def test_cockpit_mask_failure_is_recorded_with_no_achieved_tier() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    # Directly astern -- rejected by the mask's rear cutoff regardless of
    # range/size.
    candidate = _candidate("Infantry", x=-100.0, z=0.0)
    trace = DetectionTraceCollector()

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE, trace=trace)

    assert result is None
    assert len(trace.records) == 1
    entry = trace.records[0]
    assert entry.outcome == GateOutcome.COCKPIT_MASK
    assert entry.achieved_tier is None
    assert entry.observation_id is None
    # Threshold info is still populated even though the mask gate fired
    # first -- see DetectionTrace's own docstring.
    assert entry.range_threshold_m > 0.0
    assert entry.threshold_bound in ("size_curve", "range_cap")


def test_range_or_size_failure_records_size_curve_bound() -> None:
    # Infantry: medres threshold ~514 m, lowres(gating)*4 threshold 2400 m
    # (see test_visibility.py's own worked numbers). Comfortably outside
    # the range cap (10000 m), so the size curve is the binding term.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=2401.0, z=0.0)
    trace = DetectionTraceCollector()

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE, trace=trace)

    assert result is None
    entry = trace.records[0]
    assert entry.outcome == GateOutcome.RANGE_OR_SIZE
    assert entry.threshold_bound == "size_curve"
    assert entry.true_range_m == pytest.approx(2401.0)


def test_range_or_size_failure_records_range_cap_bound() -> None:
    # A ship-sized object's size curve computes far beyond the range cap
    # (module docstring: ~133 km for a ship), so the cap is the binding
    # term -- placed just outside the cap itself.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Kilo", x=10001.0, z=0.0)
    trace = DetectionTraceCollector()

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE, trace=trace)

    assert result is None
    entry = trace.records[0]
    assert entry.outcome == GateOutcome.RANGE_OR_SIZE
    assert entry.threshold_bound == "range_cap"
    assert entry.range_threshold_m == pytest.approx(visibility.NAKED_EYE_RANGE_CAP_M)


def test_terrain_los_failure_is_recorded(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: False)
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=250.0, z=0.0)
    trace = DetectionTraceCollector()

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE, trace=trace)

    assert result is None
    entry = trace.records[0]
    assert entry.outcome == GateOutcome.TERRAIN_LOS
    assert entry.achieved_tier is None


def test_admission_records_achieved_tier() -> None:
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=250.0, z=0.0)
    trace = DetectionTraceCollector()

    result = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE, trace=trace)

    assert result is not None
    entry = trace.records[0]
    assert entry.outcome == GateOutcome.ADMITTED
    # **"medres", not "lowres" (slice 2A, `plans/detection-cones-slice2/
    # plan.md` decision 3).** Infantry now carries `distinctiveness=5.0`
    # (`object_model._OP_CLASS_DISTINCTIVENESS`), which clamps its class
    # threshold to its own presence threshold (600 m for UNAIDED_OPTIC) --
    # far past the old, un-clamped naked-eye class threshold (128.57 m)
    # this test originally pinned. At 250 m Infantry now clears class
    # (600 m) but not type (64.29 m, unaffected by distinctiveness -- see
    # `_achieved_tier`'s own docstring for why), so it resolves `medres`.
    assert entry.achieved_tier == "medres"
    assert entry.true_bearing_deg == pytest.approx(result.bearing_deg)
    assert entry.true_range_m == pytest.approx(result.range_m)
    # Not yet annotated with cluster/observation detail -- that is
    # naked_eye_source.py's job, exercised separately below.
    assert entry.cluster_member_object_ids is None
    assert entry.observation_id is None


def test_trace_none_is_a_true_no_op() -> None:
    # Every existing test_visibility.py case passes trace=None implicitly
    # (its default) -- this just confirms the call still works and returns
    # identically whether or not the parameter is passed explicitly.
    ownship = _ownship(heading_true_deg=0.0)
    candidate = _candidate("Infantry", x=250.0, z=0.0)

    explicit_none = check_visibility(
        ownship, candidate, _FAKE_CONN, _THEATRE, trace=None
    )
    implicit_default = check_visibility(ownship, candidate, _FAKE_CONN, _THEATRE)

    assert explicit_none == implicit_default


# --- NakedEyePerceptionSource cluster/observation annotation ---------------


@pytest.fixture(autouse=True)
def identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


class FakeAircraftClient:
    def __init__(self, world_objects: dict[str, Any] | None) -> None:
        self._world_objects = world_objects

    def get_world_objects_latest(self) -> dict[str, Any] | None:
        return self._world_objects

    def get_unit_velocity_latest(self) -> dict[str, Any] | None:
        return None


def _world_object(
    object_id: int, object_type: str, *, lat_deg: float, lon_deg: float
) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": object_type,
        "coalition": 1.0,
        "lat_deg": lat_deg,
        "lon_deg": lon_deg,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": False,
    }


def test_admitted_candidates_are_annotated_with_cluster_and_observation_id() -> None:
    world_objects = {
        "objects": [_world_object(7, "Infantry", lat_deg=250.0, lon_deg=0.0)]
    }
    trace = DetectionTraceCollector()
    source = NakedEyePerceptionSource(
        aircraft_client=FakeAircraftClient(world_objects),  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
        trace_sink=trace,
    )

    # t_sim=0.0: SCAN_PLAN's index 0, the "12 o'clock" free-scan leg
    # (`perception.gaze.gaze_at`) -- the candidate sits dead ahead
    # (azimuth 0), inside the default +/-15 deg gaze cone active at this
    # sim time (`plans/detection-cones-slice2/plan.md`'s 2C).
    observations = source.poll(0.0, _ownship())

    assert len(observations) == 1
    entry = next(record for record in trace.records if record.object_id == 7)
    assert entry.outcome == GateOutcome.ADMITTED
    assert entry.cluster_member_object_ids == (7,)
    assert entry.observation_id == observations[0].id


def test_gate_rejected_candidates_are_never_annotated() -> None:
    # Directly astern (azimuth 180 relative to heading 0) -- rejected by
    # the cockpit mask's own rear cutoff, but 2C's gaze gate now runs
    # *first* in the chain (`plans/detection-cones-slice2/plan.md` hard
    # part 3) and no o'clock cone reaches anywhere near 180 deg (the
    # widest any cone's centre gets from boresight is 90 deg, plus a 15
    # deg half-width), so this candidate is rejected by GAZE, not
    # COCKPIT_MASK, under any `ScanPlan` -- the plan's own accepted
    # consequence ("the trace stops observing the mask's rejection rate"),
    # not a bug. `test_cockpit_mask_failure_is_recorded_with_no_achieved_
    # tier` above still exercises the mask gate directly via
    # `check_visibility` (gaze=None), unaffected by this change.
    world_objects = {
        "objects": [_world_object(9, "Infantry", lat_deg=-100.0, lon_deg=0.0)]
    }
    trace = DetectionTraceCollector()
    source = NakedEyePerceptionSource(
        aircraft_client=FakeAircraftClient(world_objects),  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
        trace_sink=trace,
    )

    observations = source.poll(0.0, _ownship())

    assert observations == []
    entry = trace.records[0]
    assert entry.outcome == GateOutcome.GAZE
    assert entry.cluster_member_object_ids is None
    assert entry.observation_id is None


def test_admitted_but_throttled_candidate_stays_unannotated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The cap is pinned to 3 for this test rather than read from the module
    # (2026-09-25): it was raised to 5 on the user's subitizing grounding,
    # and this test is about the *mechanism* -- a gate-admitted but
    # emission-throttled candidate stays unannotated -- not about the
    # value. Hardcoding four candidates against a live constant made the
    # test silently stop exercising throttling the moment the cap moved
    # past four, which is exactly what happened.
    monkeypatch.setattr(naked_eye_source, "NAKED_EYE_MAX_NEW_GROUPS_PER_POLL", 3)
    # With the cap at 3 -- and the cross-offsets below
    # keep every candidate angularly separable, so four admissions are four
    # *groups*, not one. The fourth (furthest) is therefore gate-admitted
    # but emission-throttled this poll, so its trace entry stays ADMITTED
    # with no cluster/observation detail (DetectionTrace's own docstring
    # point). Renamed from NAKED_EYE_MAX_NEW_PER_POLL by slice 2A.5, which
    # changed the cap's unit from objects to groups -- this scenario is
    # unaffected because its candidates never clustered.
    #
    # **Rescaled again, 2C** (`plans/detection-cones-slice2/plan.md`): the
    # original 190 deg spread put objects 3/4 far outside the default
    # +/-15 deg gaze cone -- reuses `test_naked_eye_source.py`'s own
    # rescaled `_CAP_TEST_RANGES_M`/`_CAP_TEST_CROSS_OFFSETS_M` values
    # (first four of five), whose derivation (in that module's own
    # docstring) already confirms, against `perception.clustering.
    # angular_separation_rad`/`angular_size_rad`, both that every candidate
    # stays inside +/-15 deg (max 12.77 deg) and that no pair merges
    # (worst separability margin 0.30 deg) -- a subset of an already-
    # verified separable set stays separable, so this is a direct reuse,
    # not a fresh derivation.
    world_objects = {
        "objects": [
            _world_object(1, "Infantry", lat_deg=60.0, lon_deg=0.0),
            _world_object(2, "Infantry", lat_deg=150.0, lon_deg=34.0),
            _world_object(3, "Infantry", lat_deg=260.0, lon_deg=55.0),
            _world_object(4, "Infantry", lat_deg=390.0, lon_deg=72.0),
        ]
    }
    trace = DetectionTraceCollector()
    source = NakedEyePerceptionSource(
        aircraft_client=FakeAircraftClient(world_objects),  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        trace_sink=trace,
    )

    # t_sim=0.0: the "12 o'clock" free-scan leg, active for this whole
    # single poll.
    observations = source.poll(0.0, _ownship())

    admitted_ids = {
        record.object_id
        for record in trace.records
        if record.outcome == GateOutcome.ADMITTED
    }
    assert admitted_ids == {1, 2, 3, 4}
    throttled = next(record for record in trace.records if record.object_id == 4)
    assert throttled.observation_id is None
    assert len(observations) == 3


# --- Behavioral equivalence: the trace must not perturb what it measures ---


def _replay_with_trace_sink(
    trace_sink: DetectionTraceCollector | None,
) -> tuple[list[Any], ContactStore]:
    frames = load_ownship_frames(_FIXTURES_DIR / "telemetry_frames.json")
    world_objects = {
        "objects": [
            _world_object(101, "Infantry", lat_deg=10005.0, lon_deg=20005.0),
            _world_object(102, "T-72B", lat_deg=9995.0, lon_deg=20040.0),
        ]
    }
    # 2C (`plans/detection-cones-slice2/plan.md`): the default o'clock scan
    # loop only gazes a +/-15 deg cone at a time, and neither candidate sits
    # dead ahead of this fixture's fixed heading -- object 102 (T-72B, true
    # azimuth ~97.1 deg) is inside a commanded "right" scan's "3 o'clock"
    # leg (90 deg, 7.1 deg of margin), which is active across this fixture's
    # whole 0.4 s span (`command_t_sim=96.0` puts elapsed time at 4.0-4.4 s,
    # inside the 3 o'clock leg's [4, 6) s window). This test is about the
    # trace sink not perturbing behaviour, not about the scan loop itself,
    # so a persistent commanded scan (rather than free scan) is the right
    # tool -- it only needs *some* admission to exercise the comparison.
    source = NakedEyePerceptionSource(
        aircraft_client=FakeAircraftClient(world_objects),  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
        trace_sink=trace_sink,
        scan_plan=ScanPlan(commanded_sector="right", command_t_sim=96.0),
    )
    store = ContactStore()
    all_observations = []
    for frame, observations in replay(source, frames):
        store.ingest(observations, now_sim=frame.t_sim)
        store.tick(frame.t_sim)
        all_observations.extend(observations)
    return all_observations, store


def test_trace_sink_does_not_perturb_the_observation_contact_or_event_streams() -> None:
    observations_without_trace, store_without_trace = _replay_with_trace_sink(None)
    observations_with_trace, store_with_trace = _replay_with_trace_sink(
        DetectionTraceCollector()
    )

    assert observations_without_trace, "fixture should produce at least one Observation"

    assert [obs.id for obs in observations_without_trace] == [
        obs.id for obs in observations_with_trace
    ]
    # `t_wall` is a real wall-clock read (`time.time()`) at each call site,
    # so it legitimately differs between the two independent replay runs --
    # excluded here, not evidence of perturbation. Every other field is
    # compared, including `derived_world_position`/`count_bucket`/
    # `continues_observation_id`.
    for without, with_trace in zip(
        observations_without_trace, observations_with_trace, strict=True
    ):
        assert dataclasses.replace(without, t_wall=0.0) == dataclasses.replace(
            with_trace, t_wall=0.0
        )

    assert [c.id for c in store_without_trace.contacts] == [
        c.id for c in store_with_trace.contacts
    ]
    for without, with_trace in zip(
        store_without_trace.contacts, store_with_trace.contacts, strict=True
    ):
        assert without.last_position == with_trace.last_position
        assert without.classification == with_trace.classification
        assert (
            without.contributing_observation_ids
            == with_trace.contributing_observation_ids
        )

    assert store_without_trace.events == store_with_trace.events


# --- Belief join (detection_trace_writer.py) --------------------------------


def test_writer_joins_admitted_entry_to_its_contact(tmp_path: Any) -> None:
    store = ContactStore()
    world_objects = {
        "objects": [_world_object(55, "Infantry", lat_deg=250.0, lon_deg=0.0)]
    }
    trace = DetectionTraceCollector()
    source = NakedEyePerceptionSource(
        aircraft_client=FakeAircraftClient(world_objects),  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode="every_poll",
        trace_sink=trace,
    )

    # t_sim=0.0: the "12 o'clock" free-scan leg, active for this whole
    # single poll.
    observations = source.poll(0.0, _ownship())
    store.ingest(observations, now_sim=0.0)
    assert len(store.contacts) == 1
    contact = store.contacts[0]

    trace_path = tmp_path / "trace.jsonl"
    writer = DetectionTraceWriter(trace_path, flush_every_n_polls=1)
    writer.write_poll(trace, store)
    writer.close()

    lines = trace_path.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["object_id"] == 55
    assert record["outcome"] == "admitted"
    assert record["observation_id"] == observations[0].id
    assert record["contact_id"] == contact.id


def test_writer_leaves_contact_id_null_when_never_admitted(tmp_path: Any) -> None:
    store = ContactStore()
    trace = DetectionTraceCollector()
    trace.record(
        DetectionTrace(
            object_id=3,
            object_type="Infantry",
            t_sim=100.0,
            true_bearing_deg=0.0,
            true_range_m=5000.0,
            range_threshold_m=2400.0,
            threshold_bound="size_curve",
            outcome=GateOutcome.RANGE_OR_SIZE,
        )
    )

    trace_path = tmp_path / "trace.jsonl"
    writer = DetectionTraceWriter(trace_path, flush_every_n_polls=1)
    writer.write_poll(trace, store)
    writer.close()

    record = json.loads(trace_path.read_text().strip())
    assert record["outcome"] == "range_or_size"
    assert record["contact_id"] is None
    assert record["observation_id"] is None


def test_write_poll_clears_the_collector(tmp_path: Any) -> None:
    store = ContactStore()
    trace = DetectionTraceCollector()
    trace.record(
        DetectionTrace(
            object_id=1,
            object_type="Infantry",
            t_sim=100.0,
            true_bearing_deg=0.0,
            true_range_m=100.0,
            range_threshold_m=2400.0,
            threshold_bound="size_curve",
            outcome=GateOutcome.ADMITTED,
            achieved_tier="hires",
        )
    )
    writer = DetectionTraceWriter(tmp_path / "trace.jsonl", flush_every_n_polls=1)

    writer.write_poll(trace, store)

    assert trace.records == []
    writer.close()


def test_trace_records_the_optic_the_candidate_was_judged_through() -> None:
    """`plans/binocular-optic/plan.md` Stage 1. Without this the row's own
    `range_threshold_m` is unexplainable: the same contact at the same
    range yields a different threshold depending on an instrument the row
    would not otherwise name."""
    trace = DetectionTraceCollector()

    check_visibility(
        _ownship(),
        _candidate("Infantry", x=1_000.0, z=0.0),
        _FAKE_CONN,
        _THEATRE,
        optic=BINOCULAR_OPTIC,
        trace=trace,
    )

    assert [entry.optic for entry in trace.records] == [BINOCULAR_OPTIC.name]


def test_trace_defaults_to_the_unaided_optic() -> None:
    """The overwhelmingly common row, and the one every existing debrief
    tool reads -- it must not become `None` or an empty string."""
    trace = DetectionTraceCollector()

    check_visibility(
        _ownship(),
        _candidate("Infantry", x=1_000.0, z=0.0),
        _FAKE_CONN,
        _THEATRE,
        trace=trace,
    )

    assert [entry.optic for entry in trace.records] == [UNAIDED_OPTIC.name]
