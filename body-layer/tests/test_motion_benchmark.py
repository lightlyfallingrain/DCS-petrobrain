"""Stage 0 part 3 benchmark -- `plans/movement-detection/plan.md`.

The only part of the transport's cost question answerable on the Mac today
(no DCS, no mission-scripting sandbox -- Stage 0 parts 1/2 are answered by
prior production use and by the Hook script's own `os.clock()`
self-measurement respectively, not by this test): parse -> join -> early-out
-> gate at a realistic N=300, synthesised end to end through the exact
functions `NakedEyePerceptionSource.poll` calls, not a hand-rolled stand-in.

This is a regression ceiling, not a precision timing tool (`pytest`'s own
wall-clock timing is noisy) -- the plan's expectation was that this cost is
"irrelevant next to the existing per-candidate `check_visibility` cost";
this test confirms that rather than assuming it, with a generous bound
(500 ms) well above any plausible real cost, so it fails loudly only on a
genuine pathological regression, not on ordinary machine noise."""

from __future__ import annotations

import time
from typing import Any

import pytest

from perception import association
from perception.association import WorldObjectCandidate
from perception.geometry import GeoPosition
from perception.motion import evaluate_motion_gate
from perception.naked_eye_source import _resolve_velocity_by_object_id

_N = 300


def _world_object(object_id: int) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": "T-72B",
        "coalition": 1.0,
        "lat_deg": 35.0 + (object_id % 100) * 0.001,
        "lon_deg": 35.9 + (object_id // 100) * 0.001,
        "altitude_m": 50.0,
        "heading_true_rad": 0.0,
        "is_ownship": False,
        "unit_name": f"Unit-{object_id}",
    }


def _synthesize(n: int) -> tuple[dict[str, Any], dict[str, Any]]:
    objects = [_world_object(i) for i in range(n)]
    world_objects = {"dcs_model_time_s": 1000.0, "objects": objects}
    # `_resolve_velocity_by_object_id` consumes an already-dict-shaped
    # `UnitVelocitySnapshot.to_dict()`-style snapshot, not the Hook's raw
    # wire string -- that string's own parse cost is exercised separately by
    # `test_unit_velocity_schema.py` (aircraft-layer), so this benchmark
    # starts from the post-parse shape, matching what `naked_eye_source.py`
    # actually receives from `aircraft_client.get_unit_velocity_latest()`.
    unit_velocity = {
        "dcs_model_time_s": 1000.5,
        "unit_count": n,
        "bridge_call_ms": 1.0,
        "samples": {
            f"Unit-{i}": {
                "vx": 1.0 + i % 5,
                "vy": 0.0,
                "vz": 2.0 + i % 3,
            }
            for i in range(n)
        },
    }
    return world_objects, unit_velocity


def test_parse_join_gate_at_300_units_is_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `from_dict`'s lat/lon -> DCS x/z conversion needs a real theatre in
    # the live path; substitute the identity conversion the rest of this
    # suite already uses (`test_naked_eye_source.py`'s own fixture) so this
    # benchmark measures the motion pipeline's own cost, not
    # `wgs84_to_dcs`'s coordinate-subsystem lookup cost.
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )

    world_objects, unit_velocity = _synthesize(_N)
    observer = GeoPosition(x=35.0, z=35.9, alt_m=1500.0)

    start = time.perf_counter()

    raw_objects = world_objects["objects"]
    velocity_by_object_id, _skew_s = _resolve_velocity_by_object_id(
        raw_objects, world_objects["dcs_model_time_s"], unit_velocity
    )
    candidates = [
        WorldObjectCandidate.from_dict(
            obj,
            theatre="Test",
            velocity=velocity_by_object_id.get(obj["object_id"]),
        )
        for obj in raw_objects
    ]
    results = [
        evaluate_motion_gate(
            observer, GeoPosition(x=c.x, z=c.z, alt_m=c.alt_m), c.velocity
        )
        for c in candidates
    ]

    elapsed_s = time.perf_counter() - start

    assert len(results) == _N
    assert elapsed_s < 0.5, (
        f"parse->join->gate over {_N} units took {elapsed_s * 1000:.2f} ms, "
        "expected well under 500 ms"
    )
