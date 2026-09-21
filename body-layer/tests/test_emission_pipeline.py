"""Stage 3 acceptance test (`plans/pb2-contact-memory/plan.md` Stage 3):
`emit_mode="every_poll"` must keep a continuously-visible object's belief
`certainty` at `"observed"` across many consecutive polls, instead of
letting it decay the way a source that only emits `on_change` would --
exactly the Interface confirmation section's gap 2 ("source-level debounce
starves the belief layer").

Drives a real `NakedEyePerceptionSource` (monkeypatched the same way
`test_naked_eye_source.py` does -- no live DCS/world-model needed) across a
simulated 60 s at 1 Hz, feeding every poll's `Observation`s into a real
`belief.contacts.ContactStore` (`ingest` + `tick`, mirroring how
`logger.py`'s `--console` pipeline drives the two together). This is the
one test in this stage that exercises source + belief together, rather than
either module in isolation.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import pytest

from belief.contacts import ContactStore
from belief.decay import certainty_of
from perception import association, visibility
from perception.gaze import ScanPlan
from perception.naked_eye_source import NakedEyePerceptionSource
from perception.source import OwnshipState

#: A persistent commanded "ahead" scan (`plans/detection-cones-slice2/
#: plan.md`'s 2C) rather than the free-scan default -- this fixture's
#: whole point is a *continuously* visible candidate, which the o'clock
#: scan loop no longer gives for free (a dead-ahead candidate is only
#: gazed 2 of every 16 s under free scan). A single-leg sector degenerates
#: to a static gaze by construction (`perception.gaze.gaze_at`'s own
#: docstring), so this reproduces exactly what "continuously visible"
#: needs without touching the scan-loop mechanism this file isn't testing.
_PERSISTENT_AHEAD_SCAN: ScanPlan = ScanPlan(commanded_sector="ahead", command_t_sim=0.0)

_THEATRE = "Syria"
_FAKE_CONN = sqlite3.connect(":memory:")
_POLL_INTERVAL_S = 1.0
_SIMULATED_DURATION_S = 60.0


def _ownship() -> OwnshipState:
    return OwnshipState(t_sim=100.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0)


def _world_object(object_id: int, *, lat_deg: float, lon_deg: float) -> dict[str, Any]:
    return {
        "object_id": object_id,
        "object_type": "Infantry",
        "coalition": 1.0,
        "lat_deg": lat_deg,
        "lon_deg": lon_deg,
        "altitude_m": 500.0,
        "heading_true_rad": 0.0,
        "is_ownship": False,
    }


class FakeAircraftClient:
    """A stationary, continuously-visible object -- every poll returns the
    same single candidate, mirroring PB-1.5's fake-client pattern."""

    def __init__(self, world_objects: dict[str, Any]) -> None:
        self._world_objects = world_objects

    def get_world_objects_latest(self) -> dict[str, Any]:
        return self._world_objects


@pytest.fixture(autouse=True)
def identity_wgs84_to_dcs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        association, "wgs84_to_dcs", lambda theatre, lat, lon: (lat, lon)
    )


@pytest.fixture(autouse=True)
def clear_line_of_sight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(visibility, "line_of_sight_clear", lambda *a, **k: True)


def _run_pipeline(emit_mode: str) -> tuple[ContactStore, list[float]]:
    """Poll a stationary, continuously-visible naked-eye candidate once per
    second for `_SIMULATED_DURATION_S`, ingesting+ticking each poll's
    observations into a fresh `ContactStore` (mirroring how `logger.py`'s
    `--console` pipeline drives a source and the store together). Returns
    the store plus the sim-times at which a poll actually emitted."""
    world_objects = {"objects": [_world_object(1, lat_deg=500.0, lon_deg=0.0)]}
    client = FakeAircraftClient(world_objects)
    source = NakedEyePerceptionSource(
        aircraft_client=client,  # type: ignore[arg-type]
        theatre=_THEATRE,
        world_model_conn=_FAKE_CONN,
        emit_mode=emit_mode,  # type: ignore[arg-type]
        scan_plan=_PERSISTENT_AHEAD_SCAN,
    )
    store = ContactStore()
    emitted_at: list[float] = []

    now_sim = 0.0
    while now_sim <= _SIMULATED_DURATION_S:
        observations = source.poll(now_sim, _ownship())
        if observations:
            emitted_at.append(now_sim)
        store.ingest(observations, now_sim=now_sim)
        store.tick(now_sim)
        now_sim += _POLL_INTERVAL_S

    return store, emitted_at


def test_every_poll_mode_keeps_a_continuously_visible_contact_observed() -> None:
    store, emitted_at = _run_pipeline("every_poll")

    assert len(store.contacts) == 1
    # Every poll (after the acquisition throttle admits the sole object on
    # the first poll) re-emits -- continuity is the whole point of Stage 3.
    assert len(emitted_at) >= int(_SIMULATED_DURATION_S / _POLL_INTERVAL_S)

    contact = store.contacts[0]
    assert certainty_of(contact, _SIMULATED_DURATION_S) == "observed"


def test_on_change_mode_does_not_stay_observed_over_the_same_window() -> None:
    # Contrast case: on_change emits exactly once (the object never leaves
    # the visible set, so it debounces after acquisition) -- by 60s later,
    # certainty has decayed past "observed", the gap Stage 3 exists to close.
    store, emitted_at = _run_pipeline("on_change")

    assert len(store.contacts) == 1
    assert len(emitted_at) == 1

    contact = store.contacts[0]
    assert certainty_of(contact, _SIMULATED_DURATION_S) != "observed"
