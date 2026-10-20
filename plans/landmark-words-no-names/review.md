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

---

### Re-review

Re-reviewed commit `4ea0fb64b52d6784b45df5778738771e8d8e038a` (tests only, plus a fixture
extension, on top of the reviewed tip `67ea0ce2`) against the three Required Fixes above.

**Diff**: `body-layer/tests/test_speech.py` (+119/-6) and
`plans/landmark-words-no-names/implementation.md` (+61). No production file touched — confirmed by
`git diff --stat` against `67ea0ce2`. The three new tests each build their semantic fact(s) from
the real `semantic_facts_for` producer (water: `nearest_water=_FakeInfo(name="Orontes",
subtype="river", ...)`; inside_settlement: `inside_settlement=_FakeInfo(name="Jableh",
subtype="town")`; engage-readback: `asdict`-ed `SemanticFact`s from a real
`semantic_facts_for(...)` call), not a hand-built `feature_id` string — exactly what the three
Required Fixes asked for.

**Each fix re-mutated and re-verified independently, not re-read from the implementation note:**

1. Swapped the water `feature_id` segment order in `enrichment.py`
   (`f"water:{water.name or 'unnamed'}:{_unnamed_water_label(water.subtype)}"` in place of the
   correct label-then-name order). Full `test_speech.py`+`test_enrichment.py` run: exactly
   `test_render_contact_report_end_to_end_named_water_speaks_generic_word` failed, with
   `"near Orontes."` in place of `"near a river"` — the name leaking through, the precise defect
   the fix targets. Reverted; `sha1sum enrichment.py` matched the pre-mutation value.
2. Swapped the `inside_settlement` `feature_id` segment order the same way. Exactly
   `test_render_contact_report_end_to_end_inside_settlement_speaks_generic_word` failed, with
   `"in the Jableh."` in place of `"in the town"`. Reverted; hash matched.
3. Reverted `render_engage_readback`'s call site from `_landmark_speech_text(best)` back to raw
   `best['text']`. Exactly `test_render_engage_readback_with_semantic_fact_speaks_landmark_word`
   failed, producing `"...near Jableh (250m)."` in place of `"...near a village."` — the proper
   name and bracketed distance leaking into an attack-run readback, the exact regression F7
   removes. Reverted; `sha1sum speech.py` matched.

Each mutation caused exactly one new failure (confirmed by running the two affected test files in
full, not `-k`-scoped), and no mutation was left in place after checking — hashes of both
production files matched their pre-mutation values, and `git status --porcelain` showed nothing
after all three.

**`_enrichment_context`'s new `description` parameter**: grepped every call site in
`test_speech.py` — all pre-existing ones pass no second argument, so the ternary falls to the
unchanged default (`_FakeDescription(nearest_settlement=_FakeInfo(name="Jableh",
distance_m=250.0))`), identical to the pre-change behaviour. Confirmed by the full run below
showing no unrelated test changed outcome.

**Checks, from `body-layer/` (venv `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`):**
- `ruff format --check src tests`: pass (155 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (CWD `body-layer/`): pass, 68 source files, no issues
- `pytest tests -q`: 2259 passed, 4 xfailed, zero failures on one full run; a prior full run hit
  the documented `test_mission_start_reset.py` connection-test flake
  (`test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure`), reran in
  isolation and passed cleanly — matches the stated known-flake class exactly, nothing new.
- `world-model` untouched by this diff (confirmed by `git diff --stat` scope above); its own
  checks were not re-run, consistent with "each touched subproject" in root `CLAUDE.md`'s
  Verification section.

All three Required Fixes from the original review are addressed, each independently confirmed by
mutation (not by re-reading the implementer's own account of the mutation), with no production
code change surviving the pass.

### Re-review Verdict

APPROVED

### Re-review Confidence

Full read of the diff; all three required fixes independently re-mutated and re-verified (not
re-read from `implementation.md`'s account), including hash-confirmed reversion of both touched
production files and a full-suite rerun of the known flake class.
