---
name: project_9k113_axis_split
description: BL-B64 split into three entries (perception/effectors/ATGM) — the perception half's assets were already on disk, and two of its hardest design answers were sitting in docstrings that had already prescribed the design
metadata:
  type: project
---

Planning `BL-B64` (the 9K113 sight), 2026-10-15, two passes. `plans/9k113-sight/plan.md`.
Split into `BL-B64` (perception), `BL-B66` (effectors), `BL-B67` (ATGM run) by user direction
`docs/acceptance/2026-10-15-9k113-sight-direction.md` §5.

**The axis that splits a monolithic spec: what the crew member *perceives* (pure, in-process,
cheap) versus what *moves in the cockpit* (cross-subproject, unverified, expensive to accept).**
This project's optics have that seam by construction. Pass 1 found it; the user confirmed it and
gave a better reason than cheapness — **testability**: perception is the stage that can be flown.

## The transferable lesson from pass 1: three assets were already on disk

The multipliers were **measured and sitting in a docstring**, deliberately not instantiated
(`perception/optics.py`: wide 3.55/7.00/6.50, narrow 5.81/13.75/15.00). Found by reading the file
the plan was going to edit. `BINOCULAR_OPTIC` has never had a cockpit representation, so a
purely-simulated optic is the established pattern, not a shortcut.

## Pass 2's bigger lesson: the docstrings had already prescribed the designs

Two of the hardest questions in the amendment were **answered in comments written months earlier**,
by authors who had anticipated this exact feature:

- **The 20 km cone.** `association.PLAYER_BUBBLE_RADIUS_M`'s docstring already said the exemption
  *"will be evaluated **within** the bubble filter (narrowed to the sight's own FOV), **not by
  raising this radius** — raising it would reinstate the whole-sphere cost the bubble exists to
  remove, at four times the area."* The design question was already settled on disk.
- **Whether the cone pays off.** The performance reviewer's own memory predicted it: the bubble's
  measured saving is ~1.4% (not the 76.6% exclusion rate), and *"will diverge once a wider-range
  optic (9K113, 20 km cone) lands — that is when this filter starts actually saving LOS cost."*

**How to apply: before designing against a constant, read its docstring and search agent memory for
its last measurement.** In this codebase a long docstring is frequently a decision record, not
commentary.

## The finding neither the user nor the direction could have had

**A 20 km cone alone buys nothing.** `visibility.py:854` computes
`range_threshold_m = min(NAKED_EYE_RANGE_CAP_M, size_curve_threshold_m)` with the cap at 10 000, so
a narrow-sight candidate at 13.6 km is admitted by the cone and then clamped back and rejected. The
entry needs **two** changes (cone + optic-aware cap) and neither is sufficient alone. Found by
following the admitted candidate downstream rather than stopping at the filter being changed.

## Verifying a sizing figure paid off — the figure was right

The direction annotated narrow presence as *"~13.6 km for a 7 m vehicle, ~19.4 km for a 10 m one"*.
Checked rather than accepted: `7/0.003 × 5.81 = 13 556 m`, `10/0.003 × 5.81 = 19 367 m` from
`LOWRES_ANGULAR_RADIUS_RAD = 0.003`. **Exactly right.** Keep checking anyway — the same pass found
`NAKED_EYE_RANGE_CAP_M`'s own docstring stale (it claims a 7 m vehicle reaches 9333 m, from a
threshold value that no longer exists).

## When a spec claims an asymmetry the physics does not have, look at the instrumentation

Pass 1 was asked what *"poor vertical understanding"* meant, checked the optics, found the FOVs
symmetric, and concluded nothing in the optics supported it. **That negative finding was correct —
and all three candidate mechanisms it then proposed were drawn from the wrong layer.** The answer
(§2) was that **the sight is precise and the *instrumentation* is asymmetric**: there is an azimuth
scale and no elevation scale at all. **Look at what the operator can read, not at what the
instrument can see.**

## Two shape-versus-constants calls worth remembering

- **An inverted timing shape is a policy-shape change, but can still be one parameter.** §9 makes
  the sight the *resting* phase with the naked eye as the interruption — the inverse of binoculars.
  `optic_policy` hardcodes `SCANNING` as home in three places and its invariant is "GLASSING is
  reachable only from a scan boundary". The answer was **parameterise the home phase**
  (`OpticState.home_phase`), not add a fourth phase: OBSERV-off stays bit-identical (pinnable), and
  OBSERV-on is the exact mirror. One parameter earns its place when it *removes a duplicate
  machine*.
- **"Keep two fields distinct so a controller can be inserted later" was nearly free, and checking
  why is the lesson.** §12 deferred slew to the effectors but required that desired-vs-actual aim not
  be collapsed. The collapse exists today **on one line** (`logger.py` ~881–885, where
  `OpticDecision.look_azimuth_deg` becomes a `Gaze`) and **every downstream consumer already reads
  the actual side** — they read a `Gaze`, and `within_optic_fov` takes the boresight as a parameter
  precisely because *"an optic is pointed by the head, not bolted to the airframe"*. So the feared
  "refactor everything that assumed one field" did not exist. The real constraint was that `gaze_at`
  is a **pure function of `t_sim`** for replay determinism, so persistent state had to go on
  `OpticState` (already carried across polls, already frozen-and-replaced) rather than into
  `gaze_at`. **How to apply: when asked to future-proof a seam, find the conversion point and check
  which side the consumers already read — the answer is often that only one line is wrong.**

## Two corrections arrived mid-pass; one was the coordinator's own inference

The user corrected *"maximum angular velocity is a tunable constant"* — we command **deflection**,
DCS owns the rate limit, so there is no such constant on our side (§12a). **Removed outright rather
than marked superseded, on instruction: it was never the user's claim, so there was no decision
history to preserve** — unlike the Decision 2/3 reasoning, which was kept visible deliberately
because *why the optics were the wrong place to look* is the reusable part.

**The discrimination is worth keeping: supersede a reasoned position, delete a relayed error.**

Related: [[project_binocular_stage3b]], [[project_two_perception_mechanisms_relative_vs_map]],
[[project_cones_slice2_design]].
