### Implementation Summary

Implemented the four "unblocked/cheap" items from `body-layer/ROADMAP.md`'s "Contact report
fine tuning — a running list" entry. Left out everything explicitly marked out of scope
(bearing-from-feature wording, range uncertainty, airborne classification).

### Files Changed
- `body-layer/src/belief/speech.py` —
  - `_format_range_km`: now returns spelled-out units (`"5 kilometres"`, not `"5 km"`), and
    returns `"very close"` below the new `_VERY_CLOSE_RANGE_M` (500 m) threshold instead of a
    rounded figure. Kept British "kilometres" spelling — matches the file's own pre-existing
    usage (module docstring's worked example, `tools.py`'s `_format_range_km` docstring), never
    actually emitted as code before this change.
  - `_round_enrichment_fragment`: rounded distance now reads `"(~400 metres)"`, not
    `"(~400m)"`.
  - Both call sites (`_contact_report_text`, `_render_lifecycle_text`'s
    `CONTACT_CLASSIFICATION_CHANGED` branch) updated to drop the now-redundant trailing `" km"`
    literal, since `_format_range_km` includes the unit itself.
  - New `_TTS_TOKEN_RESPELL` table + `_respell_for_tts` helper: per-token, case-insensitive,
    whitespace-tokenized respelling, applied only at `_unit_type_display`'s/
    `_plural_unit_type_display`'s `type` level (never at `class` level, where `_OP_CLASS_DISPLAY`
    already lives — this is what keeps `"SAM"` untouched without an explicit exclusion). Table
    populated with the `Mi-8`/`Mi-24`/`Mi-26`/`Mi-28` family only (see Notable Discoveries).
- `body-layer/src/belief/enrichment.py` — new `_ON_FEATURE_MAX_M` (0.5 m)/`_NEXT_TO_MIN_M`
  (10 m)/`_NEXT_TO_MAX_M` (100 m) constants and a `_proximity_text(label, distance_m)` helper,
  used by all five of `semantic_facts_for`'s `"near {label} (Nm)"` constructions (settlement,
  road, water, ridge, valley). At/under 0.5 m: `"on {label}"`. In the 10–100 m band: `"next to
  {label}"`. Otherwise unchanged. Generic over `label`, not road-specific, per the roadmap
  item's "for any feature reference" instruction.
- `body-layer/tools/speak_samples.py` — new `WORDING_SAMPLES` table + a second printed section
  in `main()`, covering all four items with hand-built `facts` dicts (range spelling, "very
  close", Mi-8 respelling + the SAM exception, and the semantic-fragment on/next-to/near-rounded
  cases) — the same acceptance-aid pattern the cardinality samples already use.
- `body-layer/tests/test_speech.py` — updated 4 pre-existing assertions to the new spelled-out
  wording; added 8 new tests for `_respell_for_tts`/the table wiring and the `"very close"`
  threshold.
- `body-layer/tests/test_enrichment.py` — added 6 new tests for `_proximity_text` and its
  integration into `semantic_facts_for` via `nearest_road`.
- `body-layer/tests/test_crew_console.py` — updated 1 pre-existing exact-text assertion
  (`watch_nearest`) to the new spelled-out wording.

### Tests Added
- `test_respell_for_tts_respells_a_known_designation`, `..._is_case_insensitive`,
  `..._leaves_unlisted_tokens_alone`, `..._never_touches_sam` — the acronym table's own behavior.
- `test_unit_type_display_type_level_respells_for_tts`,
  `test_plural_unit_type_display_type_level_respells_for_tts` — confirms the table is wired into
  the actual rendering path, not just correct in isolation.
- `test_format_range_km_says_very_close_under_half_a_kilometre` — the 500 m threshold, plus the
  boundary (500.0 itself is not "very close").
- `test_proximity_text_at_zero_distance_says_on`,
  `test_proximity_text_in_the_next_to_band_says_next_to`,
  `test_proximity_text_below_the_next_to_band_falls_back_to_near`,
  `test_proximity_text_at_or_above_the_next_to_band_falls_back_to_near` — the three-band wording
  directly.
- `test_semantic_facts_for_road_on_top_of_says_on_the_road`,
  `test_semantic_facts_for_road_close_by_says_next_to_the_road` — integration through
  `semantic_facts_for`.

### Checks
(body-layer/)
- ruff format --check: pass
- ruff check: pass
- mypy src --strict: pass
- pytest -q: pass (677 passed, up from 664 on `main`; net +13)

### Notable Discoveries
- **The roadmap's own worked example for item 2, `"LR"`, does not occur anywhere in the actual
  sayable vocabulary.** Checked `_OP_CLASS_DISPLAY`/`_OP_CLASS_DISPLAY_PLURAL` (the class-level
  words) and `perception/data/dcs_type_to_reporting_name.tsv` (the 377-distinct-name catalogue
  that backs every `type`-level classification value) — no `"LR"` token anywhere. Per the brief's
  own instruction ("only tokens that actually occur"), it was left out of the table rather than
  added speculatively. The example was presumably a stand-in for the *class* of bug (an acronym
  read as separate letters with no gap), not a literal transcription.
- **The roadmap's other example, `"MI-8"`, is also not the literal sayable string** — the real
  reporting-name catalogue holds `"Mi-8"` (mixed case). Implemented the fix keyed on that actual
  string (case-insensitive match handles both spellings), and extended it to the three sibling
  `Mi-XX` designations (`Mi-24`/`Mi-26`/`Mi-28`) on the reasoning that they share the identical
  "two-letter-prefix-plus-digits" shape that caused the live mispronunciation, even though only
  `Mi-8` was actually heard live — a judgment call, documented inline and here rather than
  silently generalized.
- **`tools.py` has its own, separate `_format_range_km`**, used only by `_contact_summary`
  (the console-debug text surface). Traced its only caller chain (`console.py` → never reaches
  `CrewConsole._print`/TTS) and confirmed it is out of scope: only `belief.speech.OutgoingSpeech.
  text` ever reaches `srs_client`/TTS, via `crew_console.py`'s `_print`. Left untouched.
- No test-inventory mismatches against the plan text found for this item — the brief named
  `speech.py`/`enrichment.py` and both `test_speech.py`/`test_enrichment.py` existed with the
  expected coverage; the one test the change actually touched outside those two files
  (`test_crew_console.py`'s `watch_nearest` exact-text assertion) was found by grepping for the
  old `" km"`/`"(~200m)"` literal shape, not named in the brief.
