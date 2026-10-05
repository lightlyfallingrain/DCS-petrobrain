---
name: los-cone-scoping
description: X-B29 second revision — the gaze cone defines the LOS query set (94% measured cut), "look here, this wide" as a command, and the digit-dispatch trick that keeps the fixed-literal rule intact
metadata:
  type: project
---

**"LOS only matters for things that we would process, if there is LOS."** (User, 2026-10-05.) This
is the governing principle for `plans/dcs-driven-los/plan.md` and it retires a whole class of
reasoning — caps, truncation, coverage budgets, round-robin across ticks — that two earlier
architect passes spent pages on.

**Why:** every consumer of LOS in body-layer requires Petrovich to have looked at the thing. Watch
list and threat warnings need a *look* to update; belief's memory is independent of LOS entirely
(it remembers; only a status update needs a sightline). So a unit outside the gaze cone is not
"uncovered" — its LOS has no meaning. The visibility cone is the **definition of the query set**,
not an optimisation trading coverage for frame time.

**How to apply:**

- **Measure the gate chain before sizing anything.** `visibility.check_visibility` runs
  gaze → cockpit mask → optic FOV → range/size → **LOS last**. Measured from
  `~/dcs-detection-trace.jsonl` (dedupe by `(t_sim, object_id)` — an earlier pass did not and its
  per-poll counts did not reconcile): 172 units per poll in the 10 km bubble, **162 rejected at the
  gaze gate**, ~10 ever reach LOS. Two revisions sized a cap against 172. One query against the
  existing log would have prevented both.
- **`cockpit_mask` rejects ~0 per poll** because the 30° gaze cone sits wholly inside the 260° mask.
  It reads as the obvious safe filter and is nearly worthless. Check before proposing it.
- **A safe range cut does not exist inside the 10 km bubble.** Largest `size_m` is 100 m (ships),
  loosest presence threshold `RESOLUTION_ANGULAR_RADIUS_RAD = 0.00128`, binocular
  `presence_range_mult = 2.42` — even a 7 m vehicle computes to ~13.2 km. The bubble is already
  tighter than the detection envelope.

See [[los-fixed-literal-command-channel]] for how the direction crosses the seam.
