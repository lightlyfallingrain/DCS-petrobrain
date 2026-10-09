# WM-B7 — A coarse elevation grid from the ridge/valley lines — REJECTED

- [x] **WM-B7 — REJECTED 2026-10-05, same day it was filed. Its rationale was removed by a user
  decision hours later; the reasoning is kept because it is the record of why the elevation grid
  has no consumer left.** #status/done Replaced by [[WM-B8]] below.

  **Why it was filed**: to be the coarse, deterministic elevation source the *offline* LOS
  primitive would read at theatre scale once [[X-B29]] moved the live answer into DCS.

  **Why that disappeared**: the user relaxed the offline requirement the same day — *"we only need
  it for testing. If we build a fine grid for a very small area, we can use that for test
  scenarios. Recreating LOS of actual flights offline makes no sense, we cannot get required
  accuracy without DCS."* A fixture-scale fine grid is a **different artifact**, not a reshaping of
  this one, so it gets its own ID rather than inheriting this name and quietly changing what the
  old commits mean.

  **What this leaves**: nothing needs a theatre-scale elevation grid. `describe_position`'s
  `elevation.dcs_m` has zero production callers (its only non-test caller, `perception/geometry.
  elevation_at`, is itself uncalled); geomorphons reads SRTM `.hgt` directly; `query/divides.py`
  samples no elevation; enrichment uses the features' own `elevation_range_m`; mission-interpreter
  has no `elevation` reference in `src`. Retiring the stored grid is therefore a separate, later
  cleanup question — not blocked on anything, and worth about 46 MB of a 704 MB store.

  Original entry follows, kept for its design questions, several of which transfer to [[WM-B8]].

- [ ] **WM-B7 (original text) — A coarse elevation grid derived from the ridge/valley lines, as the
  deterministic test oracle. LOW PRIORITY.** #status/open User direction, 2026-10-05: *"I'd rather use coarse grid calculated
  from ridge/valley data and not poll elevation data in DCS."* Replacement work for [[X-B26]], which
  closed the same day by rejecting live elevation polling outright.

  **What this is for, and the reframing that makes it cheap.** Once [[X-B29]] moves the live
  line-of-sight answer into DCS, the stored elevation grid's only remaining job is standing in for
  DCS in tests and offline work — and body-layer's hard requirement is that *everything* must run
  with no live DCS session and no collector. A stand-in does not need to be accurate. **It needs
  to be deterministic and cheap**, which a surface interpolated from the landform lines already is:
  the ridge and valley rows carry `elevation_range_m` per line, so the high and low control points
  for such a surface are already in the store.

  **What it is explicitly NOT**: a better live elevation answer. If anything ever genuinely needs
  live elevation accuracy, the route is to build the probe ([[X-B26]]'s closing note records
  everything measured for that), not to make this grid better.

  Open design questions, none urgent:

  - What interpolation, and at what spacing. "Coarse" is the point — this competes against a
    2,365,517-sample grid that is 46 MB of a 704 MB store.
  - Whether it replaces the stored `grid`/`grid_sample` tables or sits beside them. Replacing them
    changes `store.schema.SCHEMA_VERSION` and the M8 probe-store pairing; a sibling does not.
  - How it behaves where there are no landform lines at all — flat desert has neither ridges nor
    valleys, and the relief gate removed everything under 50 m. An interpolation with no control
    points nearby must say so rather than inventing a plausible height.
  - Whether `query.line_of_sight`'s `_TERRAIN_TOLERANCE_M = 12.0` still makes sense against a
    much coarser surface. It was tuned against SRTM-derived samples.

  **Promoted from "maybe" to "the plan", user 2026-10-05.** Asked whether world-model's LOS
  primitive stays as the offline/test path once DCS answers LOS live, the user's answer was *"yes,
  there's no other way"* — and this grid is what that primitive will read. So this is no longer an
  optional cleanup of a redundant table; it is the elevation source the offline and test path
  stands on. Still **low priority in ordering**, not in importance.

  **Do not start this before [[X-B29]] lands.** Until the live LOS path actually moves to DCS, the
  existing grid is still answering a live question and replacing it with a coarse one would
  degrade something real.
