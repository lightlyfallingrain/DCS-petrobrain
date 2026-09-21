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


def _observation_at(
    *,
    obs_id: str,
    t_sim: float,
    bearing_deg: float,
    range_m: float,
    classification_raw: str = "Ural truck",
    classification_level: int = 2,
) -> Observation:
    """Like `_observation` but with a configurable `bearing_deg`, for tests
    that need a contact off a specific relative bearing rather than always
    dead ahead -- `last_position` is still derived from `bearing_deg`/
    `range_m` off the observer, never from `derived_world_position`
    (`belief.association_over_time.implied_position`), so
    `derived_world_position` here is a deliberately-wrong placeholder that
    must not affect the result."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
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


def test_cancel_reaches_an_already_succeeded_task() -> None:
    # Cones 2C sortie fix: a scan_area task is a standing mode, so a
    # cancel issued after the task has already succeeded (the common case
    # -- tick resolves it the instant any contact is seen) must still be
    # able to end it, not leave it stuck in a terminal-looking state.
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
    assert tasks.get(task.id).status == "succeeded"  # type: ignore[union-attr]

    assert tasks.cancel(task.id) is True

    assert tasks.get(task.id).status == "cancelled"  # type: ignore[union-attr]


def test_cancel_reaches_an_already_failed_task() -> None:
    store = ContactStore()
    tasks = TaskStore()
    area = _area()
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )
    tasks.tick(store, now_sim=40.0)  # nothing observed -> "failed" by deadline
    assert tasks.get(task.id).status == "failed"  # type: ignore[union-attr]

    assert tasks.cancel(task.id) is True

    assert tasks.get(task.id).status == "cancelled"  # type: ignore[union-attr]


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


def test_tick_resolves_relative_scan_area_against_its_live_projection() -> None:
    """Regression for the review's finding: `TaskStore.tick` must not judge
    a relative-sector scan task against `PendingIntent.area`'s captured
    (and, post-reprojection, stale) reference. A "left" scan requested with
    ownship on heading 0 projects to absolute bearings [270, 330) (`plans/
    f10-command-vocabulary/plan.md`'s o'clock table: `left` is centered -60
    degrees relative, 30-degree half-width). A contact dead ahead (bearing
    0) sits inside the *unprojected* permissive circle but well outside
    that projected wedge, and must not complete the task; a contact at
    bearing 300 (inside the wedge) must."""
    store = ContactStore()
    tasks = TaskStore()
    ownship_origin = GeoPosition(x=0.0, z=0.0, alt_m=500.0)

    area = store.add_area(
        center=ownship_origin,
        radius_m=2000.0,
        level="watch",
        source="scan_area",
        relative_sector="left",
    )
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )

    # Reproject onto ownship's current pose (heading 0) -- this is what
    # replaces the store's area with a new object and is what makes
    # `task.area` (the captured reference) go stale.
    store.reproject_relative_areas(
        ownship_position=ownship_origin, heading_true_deg=0.0
    )
    assert task.area is not store.get_area(area.id)

    # Dead ahead: inside the 2000m circle, outside the projected [270, 330)
    # wedge. Must NOT complete the task.
    store.ingest(
        [_observation_at(obs_id="OBS_1", t_sim=15.0, bearing_deg=0.0, range_m=500.0)],
        now_sim=15.0,
    )
    tasks.tick(store, now_sim=15.0)
    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "pending"

    # Inside the projected wedge (bearing 300). Must complete the task.
    store.ingest(
        [_observation_at(obs_id="OBS_2", t_sim=16.0, bearing_deg=300.0, range_m=500.0)],
        now_sim=16.0,
    )
    tasks.tick(store, now_sim=16.0)
    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "succeeded"
    assert resolved.result_contact_ids == [
        contact.id for contact in store.contacts if contact.last_seen_sim == 16.0
    ]


def test_tick_falls_back_to_captured_area_when_the_live_area_is_gone() -> None:
    """`TaskStore.tick`'s `store.get_area(task.area.id) or task.area`
    fallback -- documented as a safety net for an invariant violation, not
    the intended path (`tools.cancel_task` always cancels the task before
    removing its area, so a still-`pending` task's area id should never go
    missing). Directly exercise the fallback branch by removing the area
    out from under a still-`pending` task without going through
    `cancel_task`, and confirm `tick` still runs the containment check
    (against the stale-but-present captured reference) rather than raising
    or silently treating every task as unmatched."""
    store = ContactStore()
    tasks = TaskStore()
    area = store.add_area(
        center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=1000.0,
        level="watch",
        source="scan_area",
    )
    task = tasks.create(
        kind="scan_area", area=area, created_sim=10.0, deadline_sim=40.0, reason="test"
    )

    assert store.remove_area(area.id) is True

    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=15.0, range_m=100.0)], now_sim=15.0
    )
    tasks.tick(store, now_sim=15.0)

    resolved = tasks.get(task.id)
    assert resolved is not None
    assert resolved.status == "succeeded"
