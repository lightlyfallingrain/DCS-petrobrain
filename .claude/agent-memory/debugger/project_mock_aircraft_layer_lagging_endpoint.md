---
name: mock-aircraft-layer-lagging-endpoint
description: body-layer's shared MockAircraftLayerServer not implementing a route a later Stage starts depending on causes a silent behaviour shift in unrelated mock-flight tests, not a clean failure at the missing route
metadata:
  type: project
---

`body-layer/tests/support/mock_aircraft_layer.py`'s `MockAircraftLayerServer` is shared by every
`tests/test_*mock_flight*` test. It only ever implements the aircraft-layer HTTP routes someone
has explicitly added a `do_GET` branch for. When a later feature wires a *new* consumer onto an
endpoint the mock never implemented (`BL-B124` Stage 4 reading `GET /firing/latest`'s
`mission_clock` for ambient light level), the missing route doesn't fail loudly at that call
site — it 404s, gets caught by the existing `AircraftLayerError` degrade-to-`None` posture (by
design, for "aircraft-layer instance predates this endpoint"), and the *feature's own* fallback
policy then kicks in silently. Here that policy was "unreadable clock → forced full dark, never
a daylight no-op" (user direction), so every scenario mock-flight test started flying at night
without any test failing *at that point* — the failure only surfaced several calls downstream,
as a `POST /command/look_direction` 501 inside unrelated gaze-scheduling code, once forced-dark
changed scan/gaze timing enough to newly reach a code path the mock also never implemented
(`do_POST` at all). Confirmed by bisecting `BL-B124`'s own stage commits (see
`plans/bl-b124-light-level/review-bl-b137.md` and `debug-mock-flights.md`): tests passed through
Stage 3, failed from Stage 4 onward, on `main`, mock-server-side only.

**Why this matters generally**: a "degrade gracefully when the route is absent" posture is
correct for genuine version-skew (old aircraft-layer predating a new endpoint), but the *same*
mechanism silently launders a test-support mock that is simply behind the feature it's now
exercising. The two cases are indistinguishable from the call site's perspective.

**What to check when a mock-flight/scenario test regresses after a Stage that reads a "new"
aircraft-layer endpoint**: grep `mock_aircraft_layer.py`'s `_Handler.do_GET`/`do_POST` for the
endpoint the new Stage calls. If it's missing, the fix is to add the route with data that
reproduces the *pre-existing* real-world default (here: a daylight `mission_clock`, not a
`do_POST` stub) — not to make the missing route return 200 blindly, which would let the
scenario silently run under whatever degraded state the feature's absence-handling produces
and stop testing what it was written for. See [[bl-b124-mission-clock-mock]] if that memory
exists, or `debug-mock-flights.md` for the worked fix.
