"""Tests for `perception.naked_eye_source._resolve_los_by_unit_name` --
`plans/dcs-driven-los/plan.md` (X-B29). Mirrors the join-logic coverage
this module's own `_resolve_velocity_by_object_id` sibling is exercised
by (`test_motion_benchmark.py`), as a direct unit test rather than only
through the full `poll()` pipeline."""

from __future__ import annotations

from typing import Any

from perception.naked_eye_source import LOS_MAX_AGE_S, _resolve_los_by_unit_name


def _object(object_id: int, unit_name: str) -> dict[str, Any]:
    return {"object_id": object_id, "unit_name": unit_name}


def test_no_snapshot_resolves_nothing() -> None:
    resolved, skew_s, hour_used, fov_half_deg_used = _resolve_los_by_unit_name(
        [_object(1, "Truck-1")], 1000.0, None
    )
    assert resolved == {}
    assert skew_s is None
    assert hour_used is None
    assert fov_half_deg_used is None


def test_well_formed_snapshot_resolves_by_unit_name() -> None:
    snapshot = {
        "dcs_model_time_s": 1000.5,
        "hour_used": 3,
        "fov_half_deg_used": 90,
        "verdicts": {
            "Truck-1": {"building_clear": True, "terrain_clear": False},
        },
    }
    resolved, skew_s, hour_used, fov_half_deg_used = _resolve_los_by_unit_name(
        [_object(1, "Truck-1")], 1000.0, snapshot
    )
    assert resolved[1].building_clear is True
    assert resolved[1].terrain_clear is False
    assert resolved[1].live_los_clear is False
    assert skew_s == 0.5
    assert hour_used == 3
    assert fov_half_deg_used == 90


def test_live_los_clear_is_true_only_when_both_fields_are() -> None:
    snapshot = {
        "dcs_model_time_s": 1000.0,
        "hour_used": 0,
        "fov_half_deg_used": 45,
        "verdicts": {"Truck-1": {"building_clear": True, "terrain_clear": True}},
    }
    resolved, _, _, _ = _resolve_los_by_unit_name(
        [_object(1, "Truck-1")], 1000.0, snapshot
    )
    assert resolved[1].live_los_clear is True


def test_unit_not_in_the_published_wedge_is_simply_absent() -> None:
    """A unit outside the queried wedge, or past the sightline cap, is
    absent from `verdicts` -- not an error, and not coerced to a guess."""
    snapshot = {
        "dcs_model_time_s": 1000.0,
        "hour_used": 0,
        "fov_half_deg_used": 45,
        "verdicts": {},
    }
    resolved, skew_s, _, _ = _resolve_los_by_unit_name(
        [_object(1, "Truck-1")], 1000.0, snapshot
    )
    assert resolved == {}
    assert skew_s == 0.0


def test_skew_beyond_los_max_age_drops_every_verdict() -> None:
    snapshot = {
        "dcs_model_time_s": 1000.0,
        "hour_used": 0,
        "fov_half_deg_used": 45,
        "verdicts": {"Truck-1": {"building_clear": True, "terrain_clear": True}},
    }
    resolved, skew_s, hour_used, fov_half_deg_used = _resolve_los_by_unit_name(
        [_object(1, "Truck-1")], 1000.0 + LOS_MAX_AGE_S + 0.1, snapshot
    )
    assert resolved == {}
    assert skew_s is not None and skew_s > LOS_MAX_AGE_S
    # hour_used/fov_half_deg_used are still reported even on a stale skew
    # -- they describe what the Hook script queried, independent of
    # whether the join itself is trusted this poll.
    assert hour_used == 0
    assert fov_half_deg_used == 45


def test_non_unique_unit_name_drops_to_unresolved_for_both() -> None:
    """Mirrors `_resolve_velocity_by_object_id`'s own handling: a
    `unit_name` shared by two of this poll's candidates resolves to
    unresolved for both, rather than guessing which one a verdict belongs
    to."""
    snapshot = {
        "dcs_model_time_s": 1000.0,
        "hour_used": 0,
        "fov_half_deg_used": 45,
        "verdicts": {"Truck-1": {"building_clear": True, "terrain_clear": True}},
    }
    resolved, _, _, _ = _resolve_los_by_unit_name(
        [_object(1, "Truck-1"), _object(2, "Truck-1")], 1000.0, snapshot
    )
    assert resolved == {}


def test_malformed_verdict_shape_is_skipped() -> None:
    snapshot = {
        "dcs_model_time_s": 1000.0,
        "hour_used": 0,
        "fov_half_deg_used": 45,
        "verdicts": {"Truck-1": {"building_clear": "yes", "terrain_clear": True}},
    }
    resolved, _, _, _ = _resolve_los_by_unit_name(
        [_object(1, "Truck-1")], 1000.0, snapshot
    )
    assert resolved == {}
