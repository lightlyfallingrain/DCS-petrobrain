---
name: project_bl_b67_atgm_run_plan_review
description: BL-B67 (ATGM attack run) Mode 1 plan review — APPROVED, no new write-path category; corrects AC-B11's "eventually six handlers" prediction to "stays five"
metadata:
  type: project
---

`plans/bl-b67-atgm-run/security-plan-review.md`, tip `858625061c9ee6cdac95b3f69152b8c320e6b872`.
**APPROVED**, no required fixes, no new dependency.

**Why worth remembering**: the plan's two new effector writes (`select_station` turning
`SHSCHO-KNOB-PTR`, `radiation_reset` pressing `OP-AIM-RESET-RAD-PTR`) both resolve through
`effector_engine` to the *existing* `client.write_cockpit_switch` → `POST /command/cockpit_switch`
call — the BL-B66 generic-write exception
([[project_cockpit_write_vocabulary_invariant]]/[[project_bl_b66_9k113_effectors_deep_analysis]]).
No new write primitive, no new POST handler on aircraft-layer. The two new aircraft-layer endpoints
this plan adds (`GET /payload/latest`, `GET /fire_button/latest`) are both read-only GETs with no
request body.

**Correction filed against a standing finding, not just this report**: `AC-B11`
(`aircraft-layer/ROADMAP/AC-B11.md`) predicted "eventually six, once `BL-B67` lands" POST handlers
carrying the unbounded-`Content-Length` shape. As actually scoped, `BL-B67` adds zero new POST
handlers — the prediction was wrong, and `AC-B11`'s own file was corrected in place (2026-10-29)
rather than leaving the stale prediction to mislead whoever next reads it as "six handlers, fix
them all." **Lesson: a filed backlog item's prediction about a *future* feature is itself a claim
that can go stale — check it against the plan that actually lands, not just against the plan that
existed when the prediction was written.**

**Also checked and clean, worth not re-deriving**: own-weapon `LoGetWorldObjects` object ids are
designed to stay inside `perception/own_weapons.py` and never cross into `belief/` (grep fence
planned) — a no-omniscience/architecture concern, not a computer-security one, so passed to
Reviewer without a verdict here, per the narrowed Security scope. No LLM/brain-layer call anywhere
in this plan — `atgm_run.decide` is a pure function, speech render functions build fixed-template
strings from a 3-valued enum, so no prompt-injection surface exists to check.
