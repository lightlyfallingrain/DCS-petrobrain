"""Tests for `perception.emitters` -- `burning_emitters` (`plans/
emitter-visibility/plan.md`, `BL-B72` Stage A) and `firing_emitters`/
`resolve_emitters` (Stage B, `BL-B73`)."""

from __future__ import annotations

from perception.emitters import (
    FIRE_LIFE_FRACTION_MAX,
    Emitter,
    EmitterKind,
    burning_emitters,
    firing_emitters,
    resolve_emitters,
)


def _object(object_id: int, unit_name: str) -> dict[str, object]:
    return {"object_id": object_id, "unit_name": unit_name, "object_type": "T-72B"}


def _sample(life: float, life0: float) -> dict[str, object]:
    return {"life": life, "life0": life0}


def test_fraction_at_or_below_the_threshold_is_burning() -> None:
    """Measured bracket: *"fire is present at a life fraction <= 0.69"*
    (`docs/acceptance/2026-09-24-damage-and-firing-probes.md`) -- any
    default inside `(0.69, 0.84]` admits a fraction of exactly 0.69."""
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_1": _sample(life=0.69, life0=1.0)}

    result = burning_emitters(raw_objects, samples)

    assert result == {1: Emitter(kind=EmitterKind.BURNING)}


def test_fraction_at_or_above_0_84_is_not_burning() -> None:
    """*"...and absent at >= 0.84."*"""
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_1": _sample(life=0.84, life0=1.0)}

    result = burning_emitters(raw_objects, samples)

    assert result == {}


def test_healthy_unit_is_not_burning() -> None:
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_1": _sample(life=3.0, life0=3.0)}

    result = burning_emitters(raw_objects, samples)

    assert result == {}


def test_default_threshold_is_inside_the_measured_bracket() -> None:
    assert 0.69 < FIRE_LIFE_FRACTION_MAX <= 0.84


def test_no_samples_this_poll_returns_empty() -> None:
    raw_objects = [_object(1, "Unit_1")]

    assert burning_emitters(raw_objects, None) == {}
    assert burning_emitters(raw_objects, {}) == {}


def test_unit_with_no_matching_sample_is_not_burning() -> None:
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_2": _sample(life=0.5, life0=1.0)}

    assert burning_emitters(raw_objects, samples) == {}


def test_sample_missing_life_fields_is_not_burning() -> None:
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_1": {"vx": 0.0, "vy": 0.0, "vz": 0.0}}

    assert burning_emitters(raw_objects, samples) == {}


def test_life0_zero_is_not_burning() -> None:
    """Defensive: a `life0` of zero (malformed/destroyed) must never
    produce a division, and never reads as burning."""
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_1": _sample(life=0.0, life0=0.0)}

    assert burning_emitters(raw_objects, samples) == {}


def test_non_unique_unit_name_drops_to_unresolved_for_every_candidate() -> None:
    """Same collision rule `naked_eye_source._resolve_velocity_by_object_id`/
    `_resolve_los_by_unit_name` already establish: a `unit_name` shared by
    two or more of this poll's `raw_objects` resolves to unburning for
    every one of them, rather than guessing which sample belongs to which
    object_id."""
    raw_objects = [_object(1, "Unit_1"), _object(2, "Unit_1")]
    samples = {"Unit_1": _sample(life=0.5, life0=1.0)}

    assert burning_emitters(raw_objects, samples) == {}


def test_multiple_units_resolve_independently() -> None:
    raw_objects = [_object(1, "Unit_1"), _object(2, "Unit_2")]
    samples = {
        "Unit_1": _sample(life=0.5, life0=1.0),
        "Unit_2": _sample(life=1.0, life0=1.0),
    }

    assert burning_emitters(raw_objects, samples) == {
        1: Emitter(kind=EmitterKind.BURNING)
    }


def test_malformed_object_entries_are_skipped_not_raised() -> None:
    raw_objects: list[dict[str, object]] = [
        {"object_id": 1},  # no unit_name
        {"unit_name": "Unit_2"},  # no object_id
        _object(3, "Unit_3"),
    ]
    samples = {
        "Unit_3": _sample(life=0.5, life0=1.0),
    }

    assert burning_emitters(raw_objects, samples) == {
        3: Emitter(kind=EmitterKind.BURNING)
    }


def _firing_active(name: str, *, targets_ownship: bool = False) -> dict[str, object]:
    return {"kind": "firing", "since_sim": 50.0, "targets_ownship": targets_ownship}


def test_firing_unit_resolves_to_an_emitter() -> None:
    raw_objects = [_object(1, "Unit_1")]
    active = {"Unit_1": _firing_active("Unit_1")}

    result = firing_emitters(raw_objects, active)

    assert result == {1: Emitter(kind=EmitterKind.FIRING, targets_ownship=False)}


def test_firing_unit_targeting_ownship() -> None:
    raw_objects = [_object(1, "Unit_1")]
    active = {"Unit_1": _firing_active("Unit_1", targets_ownship=True)}

    result = firing_emitters(raw_objects, active)

    assert result == {1: Emitter(kind=EmitterKind.FIRING, targets_ownship=True)}


def test_no_active_firing_this_poll_returns_empty() -> None:
    raw_objects = [_object(1, "Unit_1")]

    assert firing_emitters(raw_objects, None) == {}
    assert firing_emitters(raw_objects, {}) == {}


def test_unit_with_no_matching_active_entry_is_not_firing() -> None:
    raw_objects = [_object(1, "Unit_1")]
    active = {"Unit_2": _firing_active("Unit_2")}

    assert firing_emitters(raw_objects, active) == {}


def test_a_non_firing_kind_in_the_active_map_is_ignored() -> None:
    """`EmitterTracker` is the only producer of this map and never emits
    anything but `"firing"` today, but `firing_emitters` checks the kind
    explicitly rather than trusting every entry -- defensive against a
    future `LAUNCH_SMOKE` entry (`[[BL-B74]]`) landing in the same map and
    being misread as gun fire."""
    raw_objects = [_object(1, "Unit_1")]
    active = {
        "Unit_1": {"kind": "launch_smoke", "since_sim": 1.0, "targets_ownship": False}
    }

    assert firing_emitters(raw_objects, active) == {}


def test_firing_non_unique_unit_name_drops_to_unresolved() -> None:
    raw_objects = [_object(1, "Unit_1"), _object(2, "Unit_1")]
    active = {"Unit_1": _firing_active("Unit_1")}

    assert firing_emitters(raw_objects, active) == {}


def test_resolve_emitters_firing_wins_over_burning_for_the_same_unit() -> None:
    """The plan's "Co-moving Fields" table, last row: a unit both burning
    and firing resolves to `FIRING` for wording priority -- resolved once,
    in `resolve_emitters`, never in two places."""
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_1": _sample(life=0.5, life0=1.0)}  # burning
    active = {"Unit_1": _firing_active("Unit_1")}  # also firing

    result = resolve_emitters(raw_objects, samples, active)

    assert result == {1: Emitter(kind=EmitterKind.FIRING, targets_ownship=False)}


def test_resolve_emitters_keeps_burning_when_not_firing() -> None:
    raw_objects = [_object(1, "Unit_1")]
    samples = {"Unit_1": _sample(life=0.5, life0=1.0)}

    result = resolve_emitters(raw_objects, samples, None)

    assert result == {1: Emitter(kind=EmitterKind.BURNING)}


def test_resolve_emitters_merges_independent_units() -> None:
    raw_objects = [_object(1, "Unit_1"), _object(2, "Unit_2")]
    samples = {"Unit_1": _sample(life=0.5, life0=1.0)}
    active = {"Unit_2": _firing_active("Unit_2")}

    result = resolve_emitters(raw_objects, samples, active)

    assert result == {
        1: Emitter(kind=EmitterKind.BURNING),
        2: Emitter(kind=EmitterKind.FIRING, targets_ownship=False),
    }
