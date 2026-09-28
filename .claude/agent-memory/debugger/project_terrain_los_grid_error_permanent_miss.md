---
name: terrain_los_grid_error_permanent_miss
description: world-model's coarse elevation grid can place a real unit "underground", causing a permanent, geometry-independent naked-eye LOS miss
metadata:
  type: project
---

`world-model/src/query/line_of_sight.py::line_of_sight_clear` compares real DCS-truth altitudes
against the world-model elevation grid's own estimate of terrain height, sampled via
`store.reader.sample_grid` — never through `describe.py`'s probe-store ATTACH fallback (it imports
`sample_grid` directly, to skip `describe_position`'s irrelevant joins, which also silently drops the
probe-store lookup that a real fix would want).

**Confirmed defect (2026-09-28, `plans/missed-aaa-detection/debug.md`):** if the stored elevation
grid at a unit's `(x, z)` reads even a little higher than the unit's real DCS altitude, every
sightline sample near that unit inherits the same overestimate — the unit reads as embedded in its
own local terrain, from every observer position, at every range and angle, permanently. This is not
an intermittent geometry-dependent miss; it is pinned to that unit's location in the store. Matches
"pilot saw it plainly close by / boresight / diving attack pass, Petrovich never called it, ever" —
a shape that rules out the cockpit mask, gaze, and optic FOV (all of which pass trivially for a
boresight target regardless of dive attitude, since `body_relative_direction` already folds
heading/pitch/bank in).

**Quantified**: `syria-full.sqlite`'s elevation grid is SRTM at 1000 m spacing
(`grid.provenance='srtm'`), and M7's own validation already recorded `mean delta -7.19 m, stddev
11.52 m` against DCS ground truth theatre-wide. Reproduced offline (monkeypatched `sample_grid`,
same pattern as `test_query_line_of_sight.py`) that a **+11.5 m** grid overestimate at the target's
own location — exactly that recorded stddev, not a contrived worst case — already flips a close
(~1 km slant) attack-pass geometry to a false "blocked" verdict, while a longer/shallower approach at
the same margin stays clear. Close-range, low-level, mountainous geometry is the worst case because
the sightline-to-terrain margin is smallest there; that is also exactly the geometry a real attack
run produces.

**No probe-store override was in play for this specific miss** — no `-probe.sqlite` exists for
`syria-full`, and `body-layer/src/logger.py` has no probe-store wiring at all, so the ATTACH-fallback
gap (real, but a separate issue from the SRTM baseline accuracy problem) did not change this
outcome; both `describe_position` and `line_of_sight_clear` were reading the same coarse base grid
either way.

**Escalated to Architect rather than patched** — every fix (global tolerance, excluding a final
stretch near the target, wiring the M8 probe fallback in, per-cell uncertainty, or the real
root-cause fix of a denser elevation source for mountainous theatres) trades directly against the
no-omniscience invariant: loosening the terrain-LOS check anywhere also unmasks units genuinely
hidden behind a real ridge at a similar margin. See the debug report for the five options and their
trade-offs.

**Re-fly recipe if this needs re-confirming on a live sortie**: add `--detection-trace <path>` (BL-9,
already wired in `logger.py`, additive) and fly the same close boresight pass. If the rejected
candidate's deciding gate is LOS at every recorded look for that id, and `sample_grid(conn,
"elevation", x, z)` at that unit's real position reads above its known DCS altitude, that confirms
the mechanism directly with no further inference needed.
