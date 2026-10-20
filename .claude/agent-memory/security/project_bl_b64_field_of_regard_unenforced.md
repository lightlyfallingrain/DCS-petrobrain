---
name: bl-b64-field-of-regard-unenforced
description: 9K113 sight (BL-B64) added field-of-regard data (regard_azimuth_half_deg etc.) to Optic but never enforced it as a selection bound -- required fix, caught by direct execution not reading. Recurred 2026-10-20 on a new producer (search_pattern/idle search legs) that was elevation-unaware, past the first fix's own scope
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

**Recurred once, on a new producer, 2026-10-20 (`plans/9k113-narrow-search/security-review.md`,
Required Fix).** The follow-up above fixed `look_sweep` (the sweep around an already-chosen look
target) by filtering through `within_field_of_regard` — azimuth *and* elevation, since
`within_field_of_regard` checks both. That looked like it closed the whole class. It did not: the
9k113-narrow-search feature added a second producer of sight-optic aim, `logger.
_sight_in_regard_sweep` (the idle search cycle's wide/narrow legs), built on `search_pattern` —
a much older function, written for `BINOCULAR_OPTIC`, which has no field of regard in elevation at
all. `search_pattern` caps azimuth (`max_half_width_deg`) but was never given an elevation clamp,
because it never needed one before. The new caller hands it `SIGHT_WIDE_OPTIC`/`SIGHT_NARROW_OPTIC`
— optics that *do* have `regard_elevation_down_deg=-15.0` — and `search_pattern`'s own geometry
(elevation derived from `atan2(altitude_agl_m, range_m)`, unbounded below) commands elevations past
that limit at any ownship altitude above ~625 m AGL for this branch's own near-band edge (2333 m) —
an ordinary cruise/orbit altitude, not a stress case. This became the real detection-gate boresight
(`Gaze.center_elevation_deg` → `within_optic_fov`), not a cosmetic value.

**Why the "closed" fix didn't generalise, and the sharper form of the original lesson**: the 2026-
10-15 follow-up's own widened audit ("what else produces or mutates a committed aim after the
target is validated") was run *at that time*, over the functions that existed *at that time*. It
could not see a producer that did not exist yet. **The lesson is not "audit every producer once" —
it is "a new producer of a bounded-optic's aim is a new instance of the question, not covered by a
closed finding."** Grepping for the deferral language again after this feature would not have
found it either, because nothing in `search_pattern` or its new caller says "deferred" or
"unenforced" — the gap is a silent omission (a function never asked to clamp a bound it didn't use
to need), not a documented one. The only thing that would have caught it ahead of time: when a new
caller hands an existing, elevation-unaware sweep function an optic that *does* have an elevation
field of regard, check that function's elevation output against the bound explicitly, the same way
you would check a brand-new function — "this function was already reviewed for this risk class"
is a claim about its *old* callers, not its new one.
