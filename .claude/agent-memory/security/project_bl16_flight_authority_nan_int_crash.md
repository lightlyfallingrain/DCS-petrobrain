---
name: project_bl16_flight_authority_nan_int_crash
description: BL-16 flight-lift-vector security pass (branch fix/bl16-flight-epoch-bound @ bbddd80b) -- body-layer/src/belief/flight_authority.py's decide_carried_value_speech crashes on a non-finite fd_alt/fd_ias from GET /flight_desired/latest, the recurring unguarded-nonfinite-conversion category's seventh instance, first one on this specific mirror
metadata:
  type: project
---

`flight_authority.py` (new file, BL-16 Stage 3, `plans/flight-desired-state/plan.md`) mirrors
`GET /flight_desired/latest` with `_as_optional_float`/`_as_optional_degrees_0_360` --
`isinstance`-checked but not `math.isfinite`-checked, same shape as every other instance of
`.claude/agent-memory/dod/project_recurring_unguarded_nonfinite_float_before_conversion.md`.

**Why it is exploitable here specifically, not just theoretically**: `decide_carried_value_speech`
(lines 294-316) feeds `new.alt_m` through `clamp_altitude(alt_m, "agl"|"baro")`
(`belief/flight_control.py`) before comparing and converting with `int()`. `clamp_altitude`'s own
guard (`if ref == "agl" and m < FLOOR_AGL_M`) is NaN-comparison-false, so it returns `NaN`
*unchanged* rather than tripping the floor -- unlike `clamp_speed`'s `max(0.0, min(MAX_IAS_KMH,
kmh))`, which happens to resolve to `MAX_IAS_KMH` for a NaN input purely because of Python's
`min(a, b)` argument-order semantics (keeps `a` unless `b < a`, and `NaN < a` is always `False`).
Verified both in a live Python shell. The equality check right after (`flown_alt != new.alt_m`)
is then `True` for `NaN != NaN` (always true), so the branch that calls `int(flown_alt)` runs and
raises `ValueError: cannot convert float NaN to integer`.

**Reachability**: `aircraft_client._get_json`'s `json.loads` accepts the non-standard
`NaN`/`Infinity` JSON literals by default (same as `BL-B104`'s precedent at
`GET /world_objects/latest`), so a LAN actor able to answer this poll's `GET
/flight_desired/latest` (impersonating an unauthenticated LAN HTTP peer, or a man-in-the-middle on
the same segment -- this project's own stated threat class, `.claude/agents/security.md`'s
"infected computer in LAN scanning ports") can trigger this deterministically with
`{"fd_alt": NaN, ...}`. Under normal operation `Export.lua`'s own encode side cannot produce this
(`core.lua`'s `fmt_num_or_null`/`fmt_int_or_null` already guard with `is_finite_number`, fixed on
`fix/handover-ack-seq` before this batch) -- the gap is purely on the parse/mirror side, one hop
downstream of an already-fixed encode-side instance of the same category.

**Caught, not fatal**: `body.py`'s whole-poll-cycle `except Exception` (line 6379) swallows the
crash and logs it, so the process survives -- but the remainder of that poll (including the
ordered "You have controls!"/SAU-channel speech right after it in the same poll) is skipped.

**How to apply**: when reviewing any new `_as_optional_float`/mirror-style parse function for a
LAN-HTTP response, check every arithmetic/comparison chain downstream for an eventual `int()`/
`round()`/`math.floor()`, not just the immediate call site -- a NaN can travel through several
functions (a clamp, an equality check) before the conversion that actually raises, and an
intermediate guard that looks protective (`m < FLOOR_AGL_M`) can be NaN-silently bypassed exactly
like the position-belief clamp findings this category started with. The fix applied here: guard
at the mirror's own `_as_optional_float`/`_as_optional_degrees_0_360`, degrading a non-finite wire
value to `None` ("nothing received yet") rather than carrying it forward -- cheaper than guarding
every downstream consumer individually, and matches this project's own prescribed remedy.

Filed as a Required Fix in `plans/flight-lift-vector/security.md`, not a backlog ID -- it blocks
DoD and is fixed in this same batch, not deferred.
