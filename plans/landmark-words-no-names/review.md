### Review Summary

Reviewed `feature/landmark-words-no-names` at tip `cfb65daa` (implementation `b292c1b4`, plan
`1727185d`) against `plans/landmark-words-no-names/plan.md` and
`docs/acceptance/2026-10-20-sortie-feedback.md` F7/"F7 — settled".

The implementation matches the plan closely and the stated behaviour is correct by inspection and
by exercise: spoken callouts (`render_engage_readback`, `_contact_report_text`) now say
"near a village" / "in the town" / "near a road" / "near a river" with no proper name and no
distance figure, while `SemanticFact.text`/`feature_id` are untouched so the debug console
(`belief.console.format_event_for_overlay`), the brain-facing tool surface
(`belief.tools.describe_our_position`/`_our_position_summary`, `TOOL_SET`), and mission memory
(`mission_memory/admission.py`, `mission_memory/marks.py`, both reading `facts[0].text` directly)
all keep the full name. Grepped every consumer of `SemanticFact`/`feature_id` in `body-layer/src`
(`console.py`, `enrichment.py`, `speech.py`, `tools.py`, `mission_memory/admission.py`,
`mission_memory/marks.py`) — no other speech-rendering path exists; `render_group_disclosure`
never renders a semantic fact at all. All claims in the plan's "What already exists" section
(road's `subtype`/`name` always `None`, `named_places_within_radius` never read by
`semantic_facts_for`, world-model's `area_m2` tag already read by `_preferred_settlement`) were
checked against the actual source, not taken on faith, and all held.

The `village`/`town` sizing rule, its tunable (`BUILT_UP_VILLAGE_MAX_AREA_M2`), and the rendered
`defaults.toml` line were checked per root `CLAUDE.md`'s tuning-verification procedure: bounds are
AST literals, the rendered line's arithmetic is right, no cross-key coupling exists for this new
key, and the staleness test (`test_tuning_defaults_toml.py`) passes. The rendered line does carry a
pre-existing generator defect (a dropped leading backtick across a line wrap) — confirmed this
already affects two unrelated pre-existing entries (`ATTACK_RUN_ELEVATION_GATE_DEG`,
`ATTACK_RUN_LINED_UP_AZIMUTH_DEG`), so it is not new to this change; noted as optional below.

All checks pass in both touched subprojects (ruff format/check, mypy --strict, pytest), and the one
test failure seen on a full run (`test_connection_reporter_reannounces_after_a_recovery_and_a_
second_drop`, plus once an unrelated `test_log_live_los_coverage_summary_logs_zero_over_evaluated_
when_healthy`) reproduced as the documented flake class and passed cleanly in isolation both times.

**The one real gap, found by mutation, not by reading:** three of the new/changed code paths have
no test that would catch a regression in them. See Required Fixes — these are cheap, targeted test
additions, not a design problem; the behaviour itself is correct as written.

### Required Fixes

- **`water` facts' `feature_id` wiring has no end-to-end test connecting `enrichment.py`'s actual
  construction to `speech.py`'s consumption.** `test_enrichment.py`'s water tests check `fact.text`
  but never `fact.feature_id`; `test_speech.py`'s `test_landmark_speech_text_water` hand-builds a
  `feature_id` string (`"water:a river:Orontes"`) that *assumes* the format `enrichment.py`
  produces, rather than deriving it from a real `semantic_facts_for` call. **Verified by mutation**:
  swapping the two segments in `enrichment.py`'s water `feature_id` construction
  (`f"water:{water.name or 'unnamed'}:{_unnamed_water_label(water.subtype)}"` instead of the
  correct order) — which would make a named river/lake speak its own name instead of "a river" —
  passes the entire test suite with zero failures. Add one test exercising a named water body
  through `semantic_facts_for` → `_contact_report_text`/`render_contact_report` (mirroring the
  existing "Jableh" settlement end-to-end test), asserting the spoken text contains the generic
  water word and never the water body's own name.
- **`inside_settlement` facts have the same gap.** Only `_landmark_speech_text`'s own hand-built
  unit test (`test_landmark_speech_text_inside_settlement_speaks_in_the_word`) exercises this kind,
  again assuming rather than deriving the `feature_id` format. **Verified by mutation**: swapping
  the segment order in `enrichment.py`'s `inside_settlement` `feature_id` construction produces no
  test failure anywhere in the suite (confirmed; one unrelated timing flake appeared and separately
  reproduced and passed in isolation, unconnected to this mutation). Add an end-to-end test (a
  position *inside* a named settlement, through the real `semantic_facts_for` → speech chain)
  asserting `"in the {word}"` and no proper name.
- **`render_engage_readback`'s semantic/landmark branch (lines ~528-535) has zero test coverage,
  before or after this change**, and this is one of only two call sites the plan names. No test in
  `test_speech.py` ever calls `render_engage_readback` with a non-empty `facts["semantic"]` list.
  **Verified by mutation**: reverting that call site's `_landmark_speech_text(best)` back to raw
  `best['text']` (i.e. re-introducing the exact behaviour F7 removes — the proper name and the
  bracketed distance leaking into an attack-run readback) passes the entire suite. Add one test
  calling `render_engage_readback` with a `semantic` fact present (no `terrain_qualifier`) and
  asserting the generic landmark word appears with no name/distance.

None of these three are design defects — the production code is correct by inspection and by the
two mutation checks that *did* get caught (the settlement-size boundary test, and the two
`_contact_report_text` name-leak tests). They are coverage gaps specifically in the new/changed
code, confirmed to be silent (would ship a regression with every check green).

### Optional Refinements

- The rendered `defaults.toml` entry for `BUILT_UP_VILLAGE_MAX_AREA_M2` has a dropped leading
  backtick where the `#:` source comment's first sentence wraps across lines (renders as
  `landmark-words-no-names\` (F7 settled, ...` — missing open-backtick, stray close-backtick).
  Confirmed pre-existing in the generator (two other entries show the identical defect), so not a
  regression from this change and not this plan's to fix — worth a standalone ticket against
  `tools/generate_defaults.py` since root `CLAUDE.md` flags exactly this class of defect as having
  gone unnoticed through three prior review passes.
- Dropping the coastline distance figure (acknowledged in the plan's own "Risks & Unknowns" as a
  generalisation the user didn't explicitly ask for) is consistent and reasonable; flagged there,
  not escalated — agree with the plan's own call.

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read of both diffs (`body-layer/`, `world-model/`); all checklist items verified against
source, not assumed from the plan/implementation docs. Three findings confirmed by actual mutation
testing (introduce the bug, show the suite stays green, revert), not just by reading — per the
"verify by mutation" standing practice. All subproject commands (ruff format/check, mypy --strict,
pytest) run directly, including an isolated rerun of the two flaky tests that failed on a full run.
