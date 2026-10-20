### Implementation Summary

Implemented as planned: spoken callouts now say "near a village"/"in the town"/"near a road"/
"near a river" instead of a proper name plus a bracketed distance figure, anywhere speech renders
a `belief.enrichment.SemanticFact`. `SemanticFact.text`/`feature_id` themselves are untouched, so
the debug console, the overlay mirror, and mission memory keep the full name — no code change was
needed in `mission_memory/` or `belief/console.py` (confirmed: neither reads through the new
speech-side function).

### Files Changed

- `world-model/src/query/describe.py` — `SettlementInfo` gains `area_m2: float | None`, populated
  in `_settlement_info` from `feature.tags.get("area_m2")` (the same tag
  `_preferred_settlement`'s tie-break already reads). Docstring updated to describe the new field.
- `world-model/tests/test_describe_position.py` — one assertion added on `inside_settlement.area_m2`
  in the existing `test_describe_position_inside_settlement_prefers_named_over_unnamed` fixture
  (the "Big Village" polygon already carries `area_m2=6400.0`).
- `body-layer/src/belief/enrichment.py` — `import tuning`; new tunable
  `BUILT_UP_VILLAGE_MAX_AREA_M2` (1 km², `lo=100_000.0, hi=5_000_000.0, status="judgement"`); new
  `_settlement_size_word(subtype, area_m2) -> "village" | "town"`; `semantic_facts_for`'s
  settlement/inside_settlement/water fact construction now computes the generic word
  unconditionally and carries it as `feature_id`'s middle segment
  (`f"settlement:{size_word}:{name}"`, `f"inside_settlement:{size_word}:{name}"`,
  `f"water:{water_label}:{name}"`). Road needed no format change (`road.name`/`road.subtype` are
  always `None` in the current store, confirmed in the plan). Module docstring's
  `SemanticFact.feature_id` note updated for the new 2-or-3-segment shape.
- `body-layer/src/belief/speech.py` — deleted `_round_enrichment_fragment` and
  `_ENRICHMENT_DISTANCE_RE`; added `_TRAILING_DISTANCE_RE` (renamed, same regex),
  `_LANDMARK_PREPOSITIONS`/`_landmark_preposition`, `_strip_trailing_distance`, and
  `_landmark_speech_text(fact) -> str`, which switches on `feature_id`'s leading `kind:` segment
  (settlement/inside_settlement/road/water/ridge/valley/landcover/coastline/no-feature_id
  fallback) per the plan. Updated the two call sites (`render_engage_readback`,
  `_contact_report_text`) to call `_landmark_speech_text(best)`. Pruned/updated three stale
  docstring passages that named the deleted function (module docstring's "Contact report format"
  note, the "Contact report fine tuning" dated item, and the note pointing at `enrichment.py`'s
  short-range wording) rather than leaving them describing code that no longer exists.
- `body-layer/config/defaults.toml` — regenerated (`tools/generate_defaults.py --write`); rendered
  `[belief.enrichment]` section now includes `BUILT_UP_VILLAGE_MAX_AREA_M2 = 1000000.0`. Checked
  the rendered line itself, not just the source `#:` comment — matches, and the generator's
  existing leading-backtick-stripping quirk (seen identically on two pre-existing
  `belief.attack_run` entries) is pre-existing behaviour, not a new defect from this comment.
- `body-layer/tests/test_enrichment.py` — added `area_m2` field to `_FakeInfo`; updated the one
  `feature_id` assertion that changed format (`"settlement:unnamed"` ->
  `"settlement:village:unnamed"`); added 8 `_settlement_size_word` unit tests (village/town/
  city-folds-to-town/built_up below-at-above threshold/built_up no-area default/unrecognised
  subtype uses area).
- `body-layer/tests/test_speech.py` — replaced the two `_round_enrichment_fragment` tests with
  `_strip_trailing_distance` tests (same two cases); added 9 `_landmark_speech_text` tests
  (settlement near/on, inside_settlement, road, water, ridge/valley unchanged, landcover
  unchanged, coastline, no-feature_id fallback). Added `area_m2` to `_FakeInfo`. Updated two tests
  that asserted a real settlement name ("Jableh") appeared in rendered speech
  (`test_route_event_contact_detected_includes_clock_range_when_enriched`,
  `test_render_contact_report_includes_semantic_fragment_when_enriched`) — see "Notable
  Discoveries" below, these were not in the plan's test-impact list.
- `body-layer/tests/test_console.py`, `body-layer/tests/test_tools.py`,
  `body-layer/tests/test_crew_console.py` — added `area_m2: float | None = None` to each file's
  own `_FakeInfo` dataclass. Required because `semantic_facts_for` now reads
  `settlement.area_m2` unconditionally for every settlement/inside-settlement fact, and these
  fakes stand in for `SettlementInfo` via a monkeypatched `describe_position` — without the field,
  `AttributeError` at test run time, not a wrong assertion.
- `body-layer/tests/test_crew_console.py` — updated the one live pinned string (`"Watching T-72, 12
  o'clock, 0.5 kilometres near Jableh (~200 metres)."` -> `"...near a village."`).
- `body-layer/docs/STRUCTURE.md` — updated the `enrichment.py` and `speech.py` entries (both
  directly describe the mechanism this change replaces) rather than leaving them describing
  `_round_enrichment_fragment`, which no longer exists.

### Tests Added

- World-model: one `area_m2` assertion (see above).
- `_settlement_size_word`: 8 tests covering every branch (village/town/city-folds/built_up
  below-at-above threshold/no-area default/unrecognised-subtype-uses-area).
- `_strip_trailing_distance`: 2 tests (drops a trailing distance parenthetical; passes through
  text with none).
- `_landmark_speech_text`: 9 tests, one per `feature_id` kind plus the no-`feature_id` fallback.

### Checks

**body-layer/** (from `body-layer/`, venv at `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`):
- `ruff format --check src tests`: pass (155 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src` (run from inside `body-layer/`): pass (68 source files, no issues)
- `pytest -q` (`PYTHONPATH=src:../world-model/src`): pass — 2256 passed, 4 xfailed (pre-existing
  xfails, unrelated to this change). Re-ran `test_logger.py -k connection_reporter` and
  `test_mission_start_reset.py -k connection` (the two documented flakes) in isolation: 8 passed.

**world-model/** (from `world-model/`, venv at `/mnt/e/DCS-petrobrain/world-model/.venv/bin/`):
- `ruff format --check src tests`: pass (118 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src` (run from inside `world-model/`): pass (72 source files, no issues)
- `pytest tests -q`: pass — 568 passed, 3 skipped (pre-existing skips, unrelated)

### Notable Discoveries

- **Two tests the plan's test-impact list did not name, and both would have failed silently as
  wrong-reason passes if left alone**: `test_speech.py::test_route_event_contact_detected_
  includes_clock_range_when_enriched` and `::test_render_contact_report_includes_semantic_
  fragment_when_enriched` both asserted `"Jableh" in speech.text` — a live proper-name-in-speech
  assertion that is exactly the behaviour F7 removes. Updated both to assert `"near a village" in
  speech.text` and `"Jableh" not in speech.text`. The plan's own "What already exists" section
  focused on `enrichment.py`'s feature_id/wording precedents and the three files it listed for
  `test_speech.py` changes (the two `_round_enrichment_fragment` tests plus new
  `_landmark_speech_text` tests); it did not audit every pre-existing assertion against a shared
  `_enrichment_context` fixture's "Jableh" settlement for whether the *name itself* would now
  leak into asserted text. Caught by running the full suite rather than only the tests the plan
  named.
- **A `_FakeInfo`-shaped fixture class exists in five test files** (`test_enrichment.py`,
  `test_speech.py`, `test_console.py`, `test_tools.py`, `test_crew_console.py`), each a separate,
  undeclared copy standing in for world-model's `SettlementInfo`/`WaterInfo`/`RoadInfo` via a
  monkeypatched `describe_position`. None of them originally carried `area_m2`, and
  `semantic_facts_for` now reads `settlement.area_m2` unconditionally (not only when a subtype is
  absent), so every one of the five needed the field added or every settlement-involving test in
  that file would raise `AttributeError` rather than fail a wrong assertion. The plan's "Affected
  Modules" list named only `test_enrichment.py` for this; the other four were found by running the
  full suite, not by the plan's own list — flagging this as the kind of gap the project's own
  "missing entry is the dangerous one" guidance warns about: a fixture silently stops exercising
  what it was written for only when the test file is actually run.
- **The plan's second "pinned string" location (`test_crew_console.py`, "the lines currently
  ~1799 and ~3354") was half correct.** Line ~1799 (now ~1800 after edits) was a live pinned
  assertion and was updated. Line ~3354 is inside a docstring describing *historical* behaviour
  (`test_report_all_speaks_a_known_contact`'s "It used to read `...near Jableh (~200 metres).`"
  note, from the BL-13 Stage 3 summary-format change) — the test's live assertion
  (`["One armor, at 3 o'clock, inside 2 kilometres."]`) does not mention a settlement at all and
  needed no change. Left that historical docstring line untouched (it documents a *past* format
  change, dated and already superseded once before this plan; the per-project rule against
  deleting a dated statement applies) rather than touching code that was not actually affected.
- `road.name`/`road.subtype` being always `None` in the current store (confirmed in the plan)
  meant the road branch genuinely needed no feature_id format change — verified this still holds
  by inspection of `world-model/src/roadnet/rn4.py`'s docstring, unchanged by this plan.
- No deviation from the plan's design beyond the two test-impact gaps above; implementation
  matches Stage 1/Stage 2 as written.
