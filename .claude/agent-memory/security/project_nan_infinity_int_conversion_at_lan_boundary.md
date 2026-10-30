---
name: project_nan_infinity_int_conversion_at_lan_boundary
description: int(x) on an isinstance(x, int|float)-checked value still raises ValueError/OverflowError for NaN/Infinity -- a recurring gap at the aircraft-layer<->body-layer LAN-HTTP boundary, first found on BL-B104 (category/subcategory, Stage 1).
metadata:
  type: project
---

`BL-B104` (`plans/bl-b104-ground-contacts-on-ground/security-review.md`, Finding 1, 2026-10-30)
added two new wire fields (`category`/`subcategory`, `WorldObjectSample`/`WorldObjectCandidate`)
whose parsing type-checks the raw JSON value (`isinstance(raw, int | float)`, rejects `bool`) but
then calls `int(raw)` unconditionally. Python's `json.loads` accepts the non-standard `NaN`/
`Infinity`/`-Infinity` literals by default, and `int(float('nan'))` raises `ValueError`,
`int(float('inf'))` raises `OverflowError` -- neither is the module's own typed `*ParseError`, so
neither is caught by the `except <ModuleParseError>` wrapping the call site.

**Why this matters more at `body-layer/src/perception/association.py`'s `WorldObjectCandidate.
from_dict` than at the aircraft-layer ingest side**: that call site parses the raw dict straight
off `GET /world_objects/latest`'s HTTP response body, and `aircraft-layer/src/api/server.py`'s
`TelemetryAPIServer` binds `0.0.0.0` (LAN-facing by design) -- this is the actual LAN-reachable
boundary, not the loopback-only `Export.lua` ingest socket. An uncaught `ValueError` here
propagates out of the bare list-comprehension building `all_candidates` in
`naked_eye_source.py`'s poll method (no try/except there, unlike the `AircraftLayerError` catches
immediately above it for the velocity/LOS joins this feature's `review.md` already covers) and
drops that entire poll's naked-eye perception -- caught one level up by `body.py`'s
deliberately-bare `except Exception as exc:` around the poll cycle (so it does not crash the
whole process), but repeats every poll a malicious/misbehaving LAN peer keeps serving a bad value.

**The safe pattern already exists in the same codebase, in the same diff**: `line_of_sight.py`'s
`agl_m` parsing does `float(agl_raw) if isinstance(agl_raw, int | float) else None` -- `float()`
never raises on NaN/Infinity, unlike `int()`. **Check for this specific gap whenever a review
touches a new wire field that gets `int()`-converted from an aircraft-layer/body-layer JSON
boundary**: an `isinstance` check alone is not sufficient; also guard against non-finite floats
(`math.isfinite`) or catch `(ValueError, OverflowError)` before/around the `int()` call.

**Severity in this project's context**: low probability (no adversary currently on this project's
own LAN), low-medium impact (denial of one channel's perception for the affected poll(s),
self-healing, no code-exec/data-exposure escalation) -- required as a fix, not escalated to the
user as an accepted-risk decision, because the fix is small and mechanical and matches a pattern
the same commit already uses correctly two lines away.
