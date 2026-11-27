---
name: project_nan_propagates_through_astronomy_to_forbidden_daylight_default
description: a NaN/Infinity wire value does not always stop at a wrong comparison -- traced end-to-end through BL-B124's sun_elevation_deg formula it resolves to a concrete, wrong answer (90 deg, full daylight) that silently defeats the feature's own fail-safe design
metadata:
  type: project
---

Third generalisation of the NaN/Infinity-at-wire-boundary gap
([[project_nan_infinity_int_conversion_at_lan_boundary]] tracks the `int()`-raises shape,
[[project_nan_infinity_comparison_not_just_int_conversion]] the silent-wrong-boolean shape; filed
as `[[BL-B135]]`/`[[BL-B137]]`). `BL-B124`'s `schema.firing.MissionClockSample.from_wire` parses
`abs_time_s` with `float(abs_str)` (never raises on `"nan"`/`"inf"`/`"-inf"`, unlike the sibling
`year`/`month`/`day` fields' `int()` calls, which do), and `body.py`'s `_parse_mission_clock_dict`
accepts it through the same `isinstance(x, (int, float))` guard every other instance of this gap
shares.

**New lesson, worth checking directly rather than assuming "NaN in → exception or silently-wrong-
comparison out" covers every case**: traced through `perception.light_level.sun_elevation_deg`'s
astronomy formula, a NaN `abs_time_s` does not stay NaN. Every intermediate (`total_hours_utc`,
`d`, `g`, `ecliptic_longitude`, `declination`, `local_hour_angle`, `sin_altitude`) is NaN in turn,
but the function's own final clamp, `sin_altitude = max(-1.0, min(1.0, sin_altitude))`, resolves
it to a **concrete, wrong, in-range value**: `min(1.0, nan)` returns `1.0` (a NaN comparison is
always `False`, so Python's `min`/`max` keep their *first* argument whenever the comparison that
would have replaced it is NaN), then `max(-1.0, 1.0)` returns `1.0`. `asin(1.0)` in degrees is
exactly `90.0` — sun directly overhead. Downstream, `light_factor()`'s `sun_elevation_deg >=
EYE_FULL_DAYLIGHT_SUN_ELEV_DEG` branch fires cleanly on `90.0`, returning `(1.0, 1.0, 1.0)`: full
clear-day optic performance, the exact outcome this feature's own design explicitly forbids from
a bad reading ("mission should always have both readable. Error if not," user Q6).

**Also closes the feature's own freeze-guard by construction, not by bad luck.** `BL-B124`'s
Stage 4-5 review added a "sample counts as fresh only if it differs from the stored one" check
specifically to stop a frozen/dead feed being mistaken for a live one
(`project_dostring_in_numeric_splice_naN_clamp_gap`-adjacent lesson: never assume a guard elsewhere
backstops a gap). A NaN-bearing tuple defeats that guard structurally: `nan != nan` is `True` in
Python, so the exact same malformed sample compares as "different from itself" on every poll,
permanently taking the "fresh" branch and never reaching the staleness/error path that would have
logged the one `ERROR` the design promises.

**Severity was downgraded on reachability, not on consequence**: the UDP channel carrying
`mission_clock` (`collector.firing_receiver.FiringEventsReceiver`) binds `127.0.0.1` by default —
loopback-only, unlike `api.server`'s LAN-facing `0.0.0.0` `GET /firing/latest`, which is read-only
(no write path for a LAN peer to inject a crafted sample over HTTP). So exploiting this needs code
already running locally on the DCS box, not merely "an infected machine scanning the LAN" — a
bigger prior compromise than this project's stated secondary threat model. Filed low/low anyway,
consistent with the other three instances, but flagged as the worst-consequence instance so far
(silent, zero-observability, inverts the feature's own explicitly-named-dangerous direction) rather
than downgraded to "not worth filing."

**Check whenever reviewing a new astronomy/trig/clamp chain fed by a wire-boundary float**: trace
a literal `float('nan')`/`float('inf')` through the actual formula rather than assuming it either
raises or silently mis-compares — a `max(lo, min(hi, x))`-shaped clamp resolves NaN to a concrete
in-range value (`project-nan-comparison-incidental-guards.md` already showed this for `_clamp`
helpers; this is the same mechanism one layer further downstream, through `asin`/`degrees` instead
of a bare clamp).
