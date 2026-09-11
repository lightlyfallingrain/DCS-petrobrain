"""Tests for `belief.tasks` -- `PendingIntent`/`TaskStore` (`plans/
bl6-commands-inspect-adapt/plan.md`)."""

from __future__ import annotations

from belief.attention import AttentionArea
from belief.contacts import ContactStore
from belief.tasks import TaskStore
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    range_m: float,
    classification_raw: str = "Ural truck",
    classification_level: int = 2,
) -> Observation:
    """`last_position` is derived from `bearing_deg`/`range_m` off the
    observer (`belief.association_over_time.implied_position`), not from
    `derived_world_position` -- bearing is fixed at 0 (due north) so
    `range_m` alone controls how far from the origin the resulting contact
    lands, for a simple area-membership check against an origin-centered
    `AttentionArea`."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=range_m,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=range_m, z=0.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


def _area(
    *,
    area_id: str = "AREA_1",
    center: GeoPosition | None = None,
    radius_m: float = 1000.0,
) -> AttentionArea:
    return AttentionArea(
        id=area_id,
        center=center if center is not None else GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=radius_m,
        level="watch",
        source="scan_area",
    )


def test_task_succeeds_when_a_matching_contact_appears_after_creation() -> None:
    store = ContactStore()
    tasks = TaskStore()
    area = _area()
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )

    # A contact observed *after* task creation, inside the area.
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=15.0, range_m=100.0)], now_sim=15.0
    )
    tasks.tick(store, now_sim=15.0)

    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "succeeded"
    assert resolved.result_contact_ids == [store.contacts[0].id]


def test_task_ignores_a_contact_observed_before_creation() -> None:
    store = ContactStore()
    tasks = TaskStore()
    # Contact observed at t=5, before the task is created at t=10 -- must
    # not count as "appeared after this scan was requested."
    store.ingest([_observation(obs_id="OBS_1", t_sim=5.0, range_m=100.0)], now_sim=5.0)

    area = _area()
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )
    tasks.tick(store, now_sim=15.0)

    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "pending"


def test_task_times_out_when_nothing_is_found_by_the_deadline() -> None:
    store = ContactStore()
    tasks = TaskStore()
    area = _area()
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )

    tasks.tick(store, now_sim=39.0)
    assert tasks.get(task.id).status == "pending"  # type: ignore[union-attr]

    tasks.tick(store, now_sim=40.0)
    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "failed"
    assert resolved.result_contact_ids == []


def test_task_ignores_a_contact_outside_the_area() -> None:
    store = ContactStore()
    tasks = TaskStore()
    area = _area(radius_m=100.0)
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )

    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=15.0, range_m=5000.0)], now_sim=15.0
    )
    tasks.tick(store, now_sim=40.0)

    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "failed"


def test_cancel_stops_future_ticks_from_resolving_the_task() -> None:
    store = ContactStore()
    tasks = TaskStore()
    area = _area()
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )

    assert tasks.cancel(task.id) is True
    assert tasks.get(task.id).status == "cancelled"  # type: ignore[union-attr]

    # A matching contact appears, and the deadline passes -- a cancelled
    # task must not flip to succeeded or failed on a later tick.
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=15.0, range_m=100.0)], now_sim=15.0
    )
    tasks.tick(store, now_sim=100.0)

    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "cancelled"


def test_cancel_unknown_task_returns_false() -> None:
    tasks = TaskStore()
    assert tasks.cancel("TASK_999") is False


def test_tick_is_idempotent_for_the_same_now_sim() -> None:
    store = ContactStore()
    tasks = TaskStore()
    area = _area()
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=15.0, range_m=100.0)], now_sim=15.0
    )

    tasks.tick(store, now_sim=15.0)
    first = tasks.get(task.id)
    assert first is not None
    assert first.status == "succeeded"
    first_result_ids = list(first.result_contact_ids)

    tasks.tick(store, now_sim=15.0)
    second = tasks.get(task.id)
    assert second is not None
    assert second.status == "succeeded"
    assert second.result_contact_ids == first_result_ids
