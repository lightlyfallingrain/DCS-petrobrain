### Review Summary

Reviewed `feature/contact-report-wording` commit `9035317` against `body-layer/ROADMAP.md`'s
"Contact report fine tuning" entry's four cheap items and `plans/contact-report-wording/implementation.md`.
This is a pure presentation-layer change (`speech.py`/`enrichment.py`), no belief-state or
world-model touch. Verified each of the seven "check hardest" points directly against source,
not just the implementation log's claims, and reran body-layer's full verification suite myself.

1. **SAM/acronym scoping** — confirmed genuinely structural, not table-content-dependent.
   `_respell_for_tts` is only called from `_unit_type_display`/`_plural_unit_type_display`'s
   `level == "type"` branch; the `level == "class"` branch (where `"SAM"` lives, via
   `_OP_CLASS_DISPLAY["OP_SRSAM"/"OP_MRSAM"] == "SAM"`) never calls it — grepped every call site.
   Independently, grepped `perception/data/dcs_type_to_reporting_name.tsv` (595 rows) for `sam`
   case-insensitive: only `NASAMS_*`/`USS_Samuel_Chase` substrings, no bare `"SAM"` reporting
   name, so even if the level check were ever bypassed, `_TTS_TOKEN_RESPELL` has no `"sam"` key
   to act on. Two independent layers of protection, both verified, neither hypothetical.
2. **`_format_range_km`'s "very close" boundary** — `range_m < 500.0`, confirmed 500.0 itself
   renders `"0.5 kilometres"`, not `"very close"` (test asserts this explicitly). Both call sites
   (`_contact_report_text`, `_render_lifecycle_text`) only concatenate the returned string; nothing
   downstream parses it as a number.
3. **`_proximity_text` gap** — the (0.5, 10) m band is real and confirmed to fall through to the
   pre-existing `"near {label} ({distance_m:.0f}m)"` shape unchanged (e.g. `"near a road (5m)"`),
   documented inline and test-pinned (`test_proximity_text_below_the_next_to_band_falls_back_to_near`).
   Neither the roadmap item nor the brief names a third band, so leaving it as the pre-existing
   shape is a reasonable, disclosed choice rather than an oversight. All five call sites in
   `semantic_facts_for` (settlement, road, water, ridge, valley) route through the shared helper —
   confirmed by reading the diff, not just the log's claim.
4. **1000 m `NEAR_FACT_RADIUS_M` gate** — untouched; `_within_near_radius` callers and the constant
   itself are unchanged in the diff.
5. **Scope discipline** — grepped the diff for bearing/orientation, range-uncertainty vocabulary,
   and airborne/aircraft classification changes; none present. `query.describe`/`RoadInfo` and
   `object_model.py` are untouched.
6. **Updated pre-existing assertions** — all five (`test_speech.py` x4, `test_crew_console.py` x1)
   changed only the literal wording (`"5"` -> `"5 kilometres"`, `"(~200m)"` -> `"(~200 metres)"`,
   etc.), not thresholds or control flow; confirmed by reading the diff directly.
7. **`speak_samples.py`** — the new `WORDING_SAMPLES` section builds `facts` dicts and renders them
   through the real `_contact_report_text`, same pattern as the pre-existing cardinality samples —
   not hardcoded strings.

**Worked-example corrections** — independently reproduced both: `"LR"` does not occur in
`_OP_CLASS_DISPLAY`/`_OP_CLASS_DISPLAY_PLURAL` or the 595-row/377-distinct-name TSV (grepped
myself); the TSV's actual entry is `Mi-8MT -> Mi-8` (mixed case), not `"MI-8"`. Leaving `"LR"` out
rather than inventing a use, and keying the table on the real `"Mi-8"` string, are both correct
calls, and the generalization to the sibling `Mi-24`/`Mi-26`/`Mi-28` designations is disclosed as
a judgment call rather than silently smuggled in.

**Verification run myself** (not just trusted from the log), `body-layer/`, its own venv:
`ruff format --check` — pass, `ruff check` — pass, `mypy src --strict` — pass, `pytest tests -q` —
677 passed (up from 664 on `main`, +13 as claimed).

### Required Fixes

None.

### Optional Refinements

- `body-layer/ROADMAP.md`'s "Contact report fine tuning" entry is a running list the four cheap
  sub-items (spell units, acronym respelling, "very close", on/next-to thresholds) belong to; the
  branch does not mark them done or otherwise annotate the entry, and the checkbox correctly stays
  `[ ]` open only because the bearing and airborne-classification items are still outstanding. A
  future reader skimming the roadmap (rather than `implementation.md`) has no signal these four are
  already shipped and could re-scope or re-do them. Adding a short "done" marker on the four
  completed sub-bullets (without closing the parent checkbox) would close that gap. (optional —
  bookkeeping only, doesn't affect correctness or the shipped behavior)

### Verdict
APPROVED

### Review Confidence
Full read — read every changed line in `speech.py`, `enrichment.py`, both test files, and
`speak_samples.py`; independently reproduced the SAM-safety, "LR"/"Mi-8" vocabulary, and
verification-suite claims from source rather than trusting the implementation log.
