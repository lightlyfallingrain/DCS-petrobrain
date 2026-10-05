---
name: project_terrain_callout_stage5_wiring_gap
description: terrain-feature-probing Rev3 Stages 3a-5 review — NEEDS REVISION on an untested wiring seam, not the mechanism itself
metadata:
  type: project
---

Reviewed `feature/terrain-callout-stages-345` tip `4da9758` (Stages 3a/3b/4/5 of
`plans/terrain-feature-probing/plan.md` Revision 3 — dominance rule, `query/divides.py`,
`bearing_deg`, the divide-relative callout). Mechanism code was clean: dominance-factor boundary and
`DIVIDE_MERGE_M` merge step both failed their own tests when empirically disabled, no-omniscience
boundary held (`contact.last_position` only), caching containment held (never in
`WorldEnrichmentCache`), mechanism/calibration split was real (`d1d4a88`/`9125fe1`).

**The gap: `terrain_divide_qualifier`'s pure function was unit-tested (5 cases in
`test_enrichment.py`), but the *wiring* carrying its result into the spoken callout was not tested
anywhere.** `tools.py::_add_enrichment_facts` writes `facts["terrain_qualifier"]`;
`speech.py::_contact_report_text` reads it and overrides the semantic-fragment selection. `grep -rn
"terrain_qualifier" body-layer/tests/` returned zero hits. Confirmed empirically by wrapping each
side's logic in `if False and ...` independently — both left the full suite at 1430/4, unchanged.
The five fixture files that gained a `divides_between` stub all stub it to `0` unconditionally
(to stop an unrelated `sqlite3.OperationalError` against a schema-less fake conn), which means none
of them ever exercise the branch they were touched for.

**Pattern for future review**: a well-tested pure function feeding a one-line "wire it into the
output" change is exactly the shape that skips a test, because the function's own tests look like
sufficient coverage on a file-list skim. The check is the same standing one as the sibling-channel
rule ([[reviewer-wiring-grep]] if that memory exists) — grep for the *consuming* site's own key
string across `tests/`, not just the producing function's test file.

See [[precise_position_belief_hybrid_gap]] for the sibling case this generalizes (a channel
skipped, not a wiring seam skipped) — same root cause, different shape.

Full detail: `plans/terrain-feature-probing/review-rev3.md`.
