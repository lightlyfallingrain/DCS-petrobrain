---
name: bl-b64-field-of-regard-unenforced
description: 9K113 sight (BL-B64) added field-of-regard data (regard_azimuth_half_deg etc.) to Optic but never enforced it as a selection bound -- required fix, caught by direct execution not reading
metadata:
  type: project
---

`BL-B64`'s perception entry (`feature/9k113-sight`) added `Optic.regard_azimuth_half_deg`/
`regard_elevation_up_deg`/`regard_elevation_down_deg` (the 9K113's physical ±60°/+20°/−15°
pointing envelope, sourced from the manual) in Stage 1, with a docstring saying enforcement
was deferred to Stage 2. Stage 2 (the `SIGHTING` phase, `_decide_sighting`,
`belief/optic_policy.py`) landed and never added that check — `choose_look`/`is_worth_a_look`
pick a look target purely by tier-improvement-window and coverage, with no azimuth/elevation
bound at all. `regard_azimuth_half_deg is not None` is only ever tested as a boolean
("is this optic pointable", in `logger._apply_active_gaze`'s cone-construction guard) — never
compared against the chosen aim's actual value.

**Confirmed by direct execution, not by reading**: built both sibling checkouts' `src` onto
`PYTHONPATH` and called `_decide_sighting` directly with a contact at 85° body-relative azimuth
(25° past the sight's 60° limit) — it happily pointed the narrow sight there. The resulting
`SightCone` (built from `OpticState.actual_aim_azimuth_deg`, which is a pure pass-through of
whatever `_decide_sighting` picked, since the slew controller is deferred to `[[BL-B66]]`) then
admits real candidates at that bearing out to 20 km — an omniscience leak via a sight pointed
where it mechanically cannot point, for ordinary geometry (a contact to the side or below the
horizon), not an edge case.

**Why three review passes missed it**: each pass verified a true but narrower claim (cone
reads actual not desired aim; cone+cap are a correct pair; OBSERV-off tears the cone down).
None of those claims is "the chosen aim was checked against the mechanical envelope," and
Stage 1's own docstring framed enforcement as a known future deferral rather than a missing
Stage 2 item, so it never appeared on a reviewer's checklist.

**Transferable lesson**: when a plan explicitly defers enforcement of newly-added bound data to
"the next stage," check at the next stage's review whether that enforcement actually landed —
"planned for later" and "the later stage shipped" are two different facts, and nothing
mechanically connects them. Also: when a feature adds data describing a physical limit
(an envelope, a rate cap, a field of regard), grep for where that data is *read*, not just where
it is *set* — a field that is only ever tested with `is not None` is very likely being used as a
feature flag, not as the bound its docstring claims it is.

Full report: `plans/9k113-sight/security.md`, written 2026-10-15, verdict NEEDS FIXES.
