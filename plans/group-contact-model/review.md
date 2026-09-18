### Review Summary

Stage 4b (branch `feature/group-contact-speech`, commit `6b7cdec`) adds the hedged group-cardinality
speech clause and the `CONTACT_CARDINALITY_CHANGED` event. Reviewed against the plan's "Stage 4b
design — speech and events (2026-09-19)" section and the "Settled: how a group is spoken (user,
2026-09-19)" decisions, with the implementation log in `implementation.md`'s Stage 4b section.

All eight "check hardest" items were verified directly against the diff, not taken on the
implementer's word:

1. **Regression guard.** Confirmed via `git diff` on `test_speech.py`: only one existing test's body
   changed (`test_render_contact_report_maps_default_op_class_to_display_word`), no other existing
   `def test_` line touched. Traced the dead-code claim myself in `classification.py`:
   `Contact.record` takes `SpecificityLevel(percept.classification_level)` directly from the
   `Observation`, with no `_op_class_of` resolution step on that path at all — so a hand-built
   fixture can construct `classification_level=2` + `classification_raw="OP_GROUPSOMETHING"` even
   though `_op_class_of` itself would never return that combination through a real resolver. The
   fixture change (level 2 → 1, `"group."` → `"ground."`) is a legitimate correction of a test that
   was exercising an unreachable state, not a hidden regression. `_contact_report_text`'s guard
   branch (`phrase is None` → identical `_unit_type_display` call, same args) is exactly what the
   design specified.
2. **Branch not early return.** Confirmed — `_contact_report_text` computes `text` via an `if/else`
   and falls through to the shared trailing clock/range/semantic logic unchanged.
3. **Attachment points.** Confirmed by reading the code: `render_contact_report`,
   `_render_lifecycle_text`'s `CONTACT_DETECTED`/`CONTACT_REACQUIRED`, and
   `render_watch_nearest_readback` all route through `_contact_report_text`.
   `CONTACT_CLASSIFICATION_CHANGED` builds its line directly from `_unit_type_display` and never
   calls `_contact_report_text` — verified by reading that branch, it genuinely does not gain the
   clause.
4. **Scope cut holds.** `_cardinality_phrase` has three return points, none numeric: `None`,
   `"many"` (`lo >= 16`, so `hi == inf` cases fall here), `"a handful"` (`lo == 4 and hi <= 5`
   exactly), else `"several"` — including fold-derived non-named intervals like `(4, 7)`, tested
   directly.
5. **`CONTACT_CARDINALITY_CHANGED`.** No template (falls to `_render_lifecycle_text`'s explicit
   `None` branch), wired into `tick()` at lifecycle → classification → cardinality → attention
   (read the diff directly), reuses `EVENT_COOLDOWN_S`/`_cooldown_elapsed` — no second constant
   introduced.
6. **Count-arithmetic keys additive.** `contact_counts` stays a bare int in `escalation.py` and the
   existing `{total, visible, watched}` dict in `get_situation` — both unchanged; `estimated_units`
   added as a sibling key in all three places (`get_stats`, `get_situation`, `_situational_header`).
7. **Scope discipline.** Grepped the full diff for "very close", "metre"/"kilomet" (outside the
   already-existing `_format_range_km` docstring and one Sec-1-quoting docstring line), acronym
   spacing — none leaked in.
8. **Test-inventory finding.** Verified `test_console_module_contains_no_belief_logic` genuinely
   filters `not name.startswith("_")` — a public `estimated_units_lower_bound` would have broken it.
   Renaming to `_estimated_units_lower_bound` matches the established `_cardinality_facts`/
   `_classification_facts` convention for tools.py-internal helpers and is the correct fix, not a
   dodge: the function has no `console.py` caller by design (only `get_stats`/`get_situation`/
   `escalation.py` consume it), so the test's actual invariant (every *console-facing* tool has a
   console caller) is preserved rather than weakened.

Ran body-layer's full verification myself: `ruff format --check` (79 files formatted), `ruff check`
(all checks passed), `mypy src` (no issues, 34 files), `pytest tests -q` — **659 passed**, matching
the expected count (642 baseline + 17 new: 14 in `test_speech.py`, 3 in `test_events.py`).

### Required Fixes

None.

### Optional Refinements

- None worth calling out — the implementation matches the design closely enough that there is no
  daylight between "what was built" and "what §1–§6 specified" to leave a stylistic nit against.

### Verdict

APPROVED

### Review Confidence

Full read — read every changed file in the diff (`speech.py`, `events.py`, `contacts.py`,
`tools.py`, `escalation.py`, and all four test files), cross-checked the two highest-risk claims
(regression-guard fixture change, `OP_GROUPSOMETHING` unreachability) against the actual
`classification.py`/`contacts.py` source rather than trusting the implementation log's prose, and
ran the full body-layer verification suite directly rather than relying on the reported numbers.
