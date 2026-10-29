---
name: bl-b67-stage1-2-patterns
description: Reusable patterns found while implementing BL-B67 Stages 1-2 (ATGM run skeleton, single-unit aim) -- sight-lock in optic_policy, azimuth-only via empty word table, single-unit aim via a second gaze-centre field.
metadata:
  type: project
---

Implementing an ATGM-run-shaped feature on top of attack_run.py/optic_policy.py/sight_head.py/
naked_eye_source.py (`plans/bl-b67-atgm-run/plan.md`, Stages 1-2 only -- Stage 3+ not built).

**Why: pin a sight look to one contact (`sight_lock_contact_id`).** Added a new branch
(`_decide_sighting_locked`) reached from `_decide_sighting` right after the existing `sight_steady`
check, so a forced-OBSERV-off manoeuvre interrupt still wins "for free" -- no extra guard needed,
just branch order. The lock aims directly at the target's current body direction every poll (no
sweep steps), and holds the last aim when the contact momentarily drops out of `targets`.

**Why: drop an elevation word without a second code path.** `speech.alignment_phrase`'s
`_alignment_phrase_for` already treats an empty word table as "no phrase for this axis" (tier 2's
own fail-open elevation case relies on exactly this). So `attack_run.decide`'s `vertical: bool`
param just forces `elevation_table = ()` -- reuses an existing mechanism instead of adding a branch.
Worth checking for this shape whenever a plan asks to "drop a word/axis conditionally": look for
where the renderer already handles "nothing to say for this axis" before writing a new branch.

**Why: a second per-poll field beside an existing one.** `perception.association.SightCone` only
carries `azimuth_deg`, no elevation -- when a feature needs the sight's gaze-centre *elevation* too
(for picking the nearest cluster member to the gaze point), the natural move is a sibling field
(`NakedEyePerceptionSource.gaze_centre_elevation_deg`) assigned in `body._apply_active_gaze`
alongside `sight_cone`, from the same `OpticState.actual_aim_elevation_deg` read `sight_cone` is
itself built from. Don't widen `SightCone` itself for a one-feature need; a sibling field assigned
by the same call site is cheaper to reason about and does not touch `SightCone`'s other readers.

**Grep fences generalise by adding an alternation, not a second pattern.** `test_attack_run.py`'s
existing `_RELATIVE_DIRECTION_PATTERN` (`\brelative_direction\b|\bRelativeDirection\b`) does **not**
match `aim_unit_direction` as a substring -- had to add `|\baim_unit_direction\b` explicitly. A
`\bword\b` pattern never implicitly covers a *different* identifier that happens to share a
substring reading; check this before assuming an existing fence already covers a new field name.

**Testing a `ConsolePerceptionRunner`-level lifecycle (construction/clearing tied to another
field's same transition) needs the real threaded poll loop, not a hand-rolled reimplementation.**
`test_body.py`'s F4 scenario (`_f4_poll`) is a *simplified* reimplementation of the engage-apply
block for a different (differential) test's purposes -- it does not run the real code under test,
so it cannot catch a bug in the real `_run_crew_text_poll_loop`'s engage-apply block. For a new
runner-level field whose lifecycle is tied to an existing one's transitions, write the Co-moving
Fields test against the real threaded loop (the `test_crew_text_poll_loop_passes_the_used_optic_...`
pattern: monkeypatch `run_once` to a no-op, hand-set runner state, spy the drain methods, wait on a
`threading.Event()`, assert post-poll state). It costs more to write than a direct unit test but is
the only thing that actually exercises the real call site.

**A spy replacing a `drain_*` method in an integration test must still return a value the *next*
real call site can consume correctly**, or an unrelated assertion fails for a confusing reason. Hit
this directly: mocking `drain_atgm_engage` alone left the real (unmocked) `drain_attack_run` running
against a fixture with no registered `attack_target` task, which made it return `None` (its own
"selection gone" branch) and null out `attack_run_state` -- looking like the engage-apply block
itself was broken, when the actual cause was downstream in a different method entirely. Fix: either
register a real task, or also stub the sibling `drain_*` call with a passthrough when the test is
not about that call's own behaviour.
