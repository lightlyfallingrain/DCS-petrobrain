"""Tests for `perception.domain.surface_domain` -- `plans/
bl-b104-ground-contacts-on-ground/plan.md` Stage 1's domain rule table."""

from __future__ import annotations

from perception.domain import HELI_SURFACE_AGL_MAX_M, surface_domain

_WS_TYPE_AIR = 1
_WS_TYPE_GROUND = 2
_WS_TYPE_NAVY = 3
_WS_TYPE_WEAPON = 4
_WS_TYPE_STATIC = 5
_WS_TYPE_DESTROYED = 6
_WS_TYPE_HELICOPTER = 2
_WS_TYPE_AIRPLANE = 1


def test_ground_is_surface() -> None:
    assert surface_domain(_WS_TYPE_GROUND, None, None) is True


def test_navy_is_surface() -> None:
    assert surface_domain(_WS_TYPE_NAVY, None, None) is True


def test_static_is_surface() -> None:
    assert surface_domain(_WS_TYPE_STATIC, None, None) is True


def test_weapon_is_air() -> None:
    assert surface_domain(_WS_TYPE_WEAPON, None, None) is False


def test_airplane_is_air() -> None:
    assert surface_domain(_WS_TYPE_AIR, _WS_TYPE_AIRPLANE, None) is False


def test_destroyed_is_unknown() -> None:
    assert surface_domain(_WS_TYPE_DESTROYED, None, None) is None


def test_missing_category_is_unknown() -> None:
    assert surface_domain(None, None, None) is None


def test_unrecognised_category_is_unknown() -> None:
    assert surface_domain(99, None, None) is None


def test_helicopter_with_unknown_agl_is_air() -> None:
    assert surface_domain(_WS_TYPE_AIR, _WS_TYPE_HELICOPTER, None) is False


def test_helicopter_below_threshold_is_surface() -> None:
    assert (
        surface_domain(_WS_TYPE_AIR, _WS_TYPE_HELICOPTER, HELI_SURFACE_AGL_MAX_M - 1.0)
        is True
    )


def test_helicopter_at_threshold_is_surface() -> None:
    assert (
        surface_domain(_WS_TYPE_AIR, _WS_TYPE_HELICOPTER, HELI_SURFACE_AGL_MAX_M)
        is True
    )


def test_helicopter_above_threshold_is_air() -> None:
    assert (
        surface_domain(_WS_TYPE_AIR, _WS_TYPE_HELICOPTER, HELI_SURFACE_AGL_MAX_M + 1.0)
        is False
    )


def test_airplane_ignores_agl() -> None:
    # A fixed-wing aircraft at a low AGL (e.g. a low pass) stays air --
    # only the helicopter subcategory consults AGL at all.
    assert surface_domain(_WS_TYPE_AIR, _WS_TYPE_AIRPLANE, 0.0) is False
