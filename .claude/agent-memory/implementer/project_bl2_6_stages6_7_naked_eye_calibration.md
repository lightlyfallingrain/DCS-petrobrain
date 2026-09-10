---
name: bl2_6_stages6_7_naked_eye_calibration
description: BL-2.6 Stages 6-7 (naked-eye tier-derived classification + medres->lowres gate move) implementation notes
metadata:
  type: project
---

BL-2.6 Stages 6-7 (`plans/classification-refinement/plan.md`) split the naked-eye channel's tier
mechanism from its gate calibration into two commits, exactly as the plan's "mechanism and
calibration never share a commit" rule requires — see [[bl2_6_stages1_4_classification_lattice]]
for the earlier stages this builds on.

**Stage 6 mechanism, gate unchanged.** `visibility._achieved_tier(range_m, size_m)` computes the
achieved recognition tier (hires/medres/lowres) independently of the gate constant
(`NAKED_EYE_GATING_ANGULAR_RADIUS_RAD`), which stayed at `medres`. Result: the `"lowres"` branch
was provably dead code this commit — confirmed by running the full suite and finding nothing
reached it. This is the intended shape (mechanism first-unreachable, gate second-reachable), not
an oversight; worth stating explicitly in any review since a diff-only read of Stage 6 makes the
branch look untested.

**Stage 7 calibration flips which constraint binds for truck-sized objects.** Under the old
`medres` gate, Ural's threshold (3000 m) sat below `NAKED_EYE_RANGE_CAP_M` (5000 m) — size curve
discriminated. Under `lowres`, Ural's threshold becomes 5581 m, now *exceeding* the cap — so the
cap becomes the binding constraint for trucks-and-up, not just ships. A test written under the old
gate ("size curve binds below the cap") has its *premise*, not just its numbers, invalidated by
the gate move — renaming/rewriting it (not just changing asserted values) is the correct fix.

**`hires`-tier reporting-name fallback.** Not every `object_type` has an exact entry in the 595-row
reporting-name table (e.g. bare `"Infantry"` — only compound entries like `"Infantry AK"` match).
Falling back to `op_class`/level 2 rather than emitting `classification_raw=None` at `hires` range
keeps "Petrovich can never mis-identify, only fail to identify" (plan invariant) intact and avoids
a downstream `None`-handling burden. This fallback logic is entirely local to
`naked_eye_source._classification_for_tier` and needs its own test (a `hires`-range candidate with
an unmapped type) — easy to miss since most fixture types in `test_naked_eye_source.py` are bare
generic strings like `"Infantry"`/`"Ural-4320"` that don't have exact reporting-name entries.
