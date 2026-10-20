### Goal

Make Petrovich's **spoken** callouts refer to a nearby landmark by what it is ("a village", "a
road", "a river") instead of its proper name or a bracketed distance figure, while the debug
console, the overlay-without-crew-text lifecycle mirror, and mission memory keep the full name —
per `docs/acceptance/2026-10-20-sortie-feedback.md` F7 ("settled").

### What the sortie feedback actually settled

> 1 - village and town are enough
> 2 - drop [the bracketed distance]
> 3 - mission memory [keeps names]
> 4 - use no name, just landmark feature like road, river etc

So: "near a village" / "in the town", "near a road", "near a river" — no proper names, no
`(Nm)`/`(~N metres)` figure, anywhere speech renders a `belief.enrichment.SemanticFact`.

### What already exists here (read before this plan, not reinvented)

- `enrichment.py`'s `semantic_facts_for` already has three precedents for exactly this shape of
  degrade-to-generic wording: `_unnamed_settlement_label` ("a built-up area"/"an unnamed
  settlement"), `_unnamed_water_label` (river/lake/reservoir word from `WaterInfo.subtype`), and
  road's own fallback (`displayable_name(road.name) or road.subtype or "a road"`). All three only
  fire today when a **name is absent** — the gap this plan closes is making the generic word
  available **unconditionally**, not just as a name's fallback.
- `SemanticFact.feature_id` already encodes "what kind of thing this is" as a stable prefix
  (`"settlement:"`, `"road:"`, `"water:"`, `"ridge:"`, `"valley:"`, `"landcover:"`,
  `"coastline"`) — this plan reuses that seam rather than adding a parallel discriminator field.
- `speech.py` already has exactly one post-process step over a `SemanticFact.text` fragment:
  `_round_enrichment_fragment` (the F3 tilde fix lives right next to it). This plan replaces that
  one step, at its two existing call sites, rather than adding a second processing path.
- `road.subtype` and `road.name` are **always `None`** in the current store — confirmed from
  `world-model/src/roadnet/rn4.py`'s own docstring ("`road` features carry `subtype=None`
  regardless of what this module can determine") and `WM-M5`'s decision 7. So every road fact
  **already** reads "a road" today, with no name ever — road needs the distance drop only, no
  name-replacement logic.
- DCS `towns.lua` entries ingest as `named_place` (`world-model/src/dcs_data/towns.py`'s own
  docstring: "DCS's offline named-place..."), which feeds `PositionDescription.
  named_places_within_radius` — a field `semantic_facts_for` **never reads**. So the "DCS
  towns.lua entries carry neither \[subtype\]" case named in this task's brief does not actually
  arise on the path this plan touches: every `SettlementInfo` row `nearest_settlement`/
  `inside_settlement` can return is an OSM-ingested polygon, and `world-model/src/build/
  ingest_osm.py`'s `_classify_area` always assigns one of `{"city", "town", "village",
  "built_up"}` to a `settlement`-kind feature — `subtype` is never `None` in practice for this
  field. "Built-up" (no `place=*` tag at all) is the real size-less case, and is handled below via
  an area threshold.
- Mission memory (`admission.py`/`marks.py`) calls `enrichment.semantic_facts_for` **directly**
  and reads `facts[0].text` — never through `speech.py`. Since this plan does not touch
  `SemanticFact.text`/`confidence`/`provenance`, mission memory keeps full names automatically,
  with no code change needed there.
- `belief.console.format_event_for_overlay` and `belief.tools.describe_our_position`/
  `_our_position_summary` (registered in `TOOL_SET`, the brain's query surface) also read
  `SemanticFact.text` directly and are left untouched — debug detail and brain-facing tool data,
  not a canned pilot-facing callout. No voice/F10 path speaks `describe_our_position`'s summary
  verbatim today (grepped `crew_console.py` for `.summary` — no hits), so this is a live boundary,
  not a hypothetical one. If the brain later starts reading tool results aloud as free text, this
  question reopens there — out of scope now (F2 in the same sortie feedback: free-text brain
  replies aren't built yet).

### Affected Modules / Files

- `world-model/src/query/describe.py` — `SettlementInfo` gains `area_m2: float | None`;
  `_settlement_info` populates it from `feature.tags.get("area_m2")` (already computed and stored
  per-feature, just not surfaced here — `_preferred_settlement` already reads the same tag two
  functions above). Additive, read-only; within the "truly needed" bar for the in-process import
  (root `CLAUDE.md`, "Module independence").
- `world-model/tests/test_describe_position.py` — cover the new field.
- `body-layer/src/belief/enrichment.py` — a settlement size-word helper and a new tunable; extend
  `feature_id`'s encoding for `settlement`/`inside_settlement`/`water` facts to carry the generic
  word speech needs, unconditionally (not just when name is absent). `SemanticFact.text`/
  `confidence`/`provenance` unchanged for every kind.
- `body-layer/src/belief/speech.py` — delete `_round_enrichment_fragment` and
  `_ENRICHMENT_DISTANCE_RE` (fully superseded); add one function building the name-free,
  distance-free spoken phrase; update its two call sites (`render_engage_readback`,
  `_contact_report_text`).
- `body-layer/config/defaults.toml` — regenerate (`tools/generate_defaults.py --write`) for the
  new tunable.
- `body-layer/tests/test_enrichment.py` — update 3 `feature_id` assertions to the new format; add
  size-word tests.
- `body-layer/tests/test_speech.py` — remove the two `_round_enrichment_fragment` tests, add tests
  for the new function (settlement/road/water/ridge-valley/coastline/missing-`feature_id`
  fallback).
- `body-layer/tests/test_crew_console.py` — two pinned strings ("`... near Jableh (~200
  metres).`" at the lines currently ~1799 and ~3354) change to the new generic wording.

### Implementation Plan

**Stage 1 — generic wording threaded from world-model through to speech**

1. World-model: add `SettlementInfo.area_m2: float | None`, populated in `_settlement_info`.
2. `enrichment.py`:
   - Add `_settlement_size_word(subtype: str | None, area_m2: float | None) -> str` (`"village"`
     or `"town"`): `"village"`→village, `"town"`/`"city"`→town (user: "village and town are
     enough" — city folds into town), anything else (`"built_up"`, or an unrecognised/missing
     subtype) → `area_m2 < BUILT_UP_VILLAGE_MAX_AREA_M2` → `"village"`, else `"town"`; if
     `area_m2` is also `None`, default to `"village"` — stated default: with no size evidence at
     all, the smaller claim is the safer one to make, same posture as this module's other
     absent-data degradations (`_unnamed_settlement_label`, `_within_near_radius`'s "admit rather
     than drop").
   - New tunable (`plans/configurable-constants/plan.md`'s mechanism, "standard practice" per
     root `CLAUDE.md`): `BUILT_UP_VILLAGE_MAX_AREA_M2: Final[float] = tuning.real(
     "belief.enrichment.BUILT_UP_VILLAGE_MAX_AREA_M2", 1_000_000.0, lo=100_000.0, hi=5_000_000.0,
     status="judgement")` — 1 km², first guess, tune by flying (same status as
     `NEAR_FACT_RADIUS_M`/`TERRAIN_QUALIFIER_MAX_M` elsewhere in this file).
   - Extend `feature_id` to carry the generic word as a middle segment, for the two kinds whose
     `text` can carry a proper name: `f"settlement:{size_word}:{name or 'unnamed'}"`,
     `f"inside_settlement:{size_word}:{name or 'unnamed'}"`, and
     `f"water:{_unnamed_water_label(water.subtype)}:{name or 'unnamed'}"` — computed
     unconditionally, not only in the name-absent branch as today. Road needs no format change
     (already name-free in practice, see above); ridge/valley/landcover/coastline keep their
     existing `feature_id` (already generic kinds with no name ever).
   - One-line update to the module docstring's "`SemanticFact.feature_id`" note: the fallback
     string's shape now has 2 or 3 colon-separated segments depending on kind, not always 1.
3. `speech.py`:
   - Delete `_round_enrichment_fragment` and `_ENRICHMENT_DISTANCE_RE` — every behaviour they had
     (round-and-prefix a trailing `(Nm)`) is superseded, not extended.
   - Add `_landmark_speech_text(fact: dict[str, object]) -> str`:
     - Read the leading preposition off `text` (`"on "`, `"next to "`, `"near "`, `"inside "` —
       the exact vocabulary `_proximity_text`/the inside-settlement branch already produce);
       default `"near "` if `text` starts with none of them (defensive: a hand-built fact dict in
       a test, or any future fact shape).
     - Read `feature_id`; if absent, fall back to stripping only a trailing `(...)` distance
       parenthetical from `text` and return that (the one behaviour `_round_enrichment_fragment`
       is still owed to a caller that hands in a bare `{"text": ..., "confidence": ...}` dict with
       no `feature_id` — see the two existing `_contact_report_text` tests that do exactly this).
     - Otherwise switch on `feature_id`'s first `:`-segment (the kind):
       - `"settlement"`/`"inside_settlement"`: size word is `feature_id`'s middle segment.
         `"inside_settlement"` speaks as `f"in the {word}"` (matching the user's own "in the
         town" example — "inside" is kept as the debug/mission-memory vocabulary, not the spoken
         one); every other preposition speaks as `f"{preposition}a {word}"`.
       - `"road"`: `f"{preposition}a road"`.
       - `"water"`: `f"{preposition}{feature_id}'s middle segment"` (already "a river"/"a
         lake"/"a reservoir"/"water").
       - `"ridge"`/`"valley"`/`"landcover"`: return `text` unchanged — never carried a name or a
         distance figure.
       - `"coastline"`: strip the trailing distance parenthetical only, same regex as the
         fallback case above; no word substitution needed (`"near the coast"`/`"over the sea,
         off the coast"` are already generic).
   - Update `render_engage_readback` and `_contact_report_text` to call
     `_landmark_speech_text(best)` in place of `_round_enrichment_fragment(best['text'])`.

**Stage 2 — tests and the generated defaults file**

1. World-model: `test_describe_position.py` gets one assertion on `area_m2` being surfaced.
2. `test_enrichment.py`: update the 3 `feature_id` assertions (`"settlement:unnamed"` →
   `"settlement:village:unnamed"` or whatever the fixture's subtype/area resolve to;
   `"landcover:forest"`/`"coastline"` unaffected since those kinds don't change format) and add
   `_settlement_size_word` unit tests: village, town, city→town, built_up below/at/above the
   threshold, built_up with `area_m2=None` → village default.
3. `test_speech.py`: remove `test_round_enrichment_fragment_rounds_trailing_distance`/
   `test_round_enrichment_fragment_passes_through_text_without_distance`; add
   `_landmark_speech_text` tests for settlement (near/inside), road, water, ridge/valley,
   coastline, and the no-`feature_id` fallback (confirms the two existing
   `test_contact_report_text_*semantic_fragment*` tests still pass unmodified — they hand in
   `{"text": "near a road (50m)", "confidence": 0.9}` with no `feature_id`).
4. `test_crew_console.py`: work out what the `Jableh` fixture (`name="Jableh"`, `distance_m=250.0`,
   no `subtype`/`area_m2` set) resolves to under the new default (`"village"`, since an
   unrecognised/missing subtype with no area falls back to the smaller word) and update the two
   pinned strings from `"...near Jableh (~200 metres)."` to `"...near a village."`.
5. Regenerate `body-layer/config/defaults.toml` (`tools/generate_defaults.py --write`) and confirm
   `tests/test_tuning_defaults_toml.py` passes.

### Risks & Unknowns

- `BUILT_UP_VILLAGE_MAX_AREA_M2`'s 1 km² is an unvalidated first guess, same status as this
  module's other placeholder radii — tune by flying.
- The `feature_id` format change (1 segment → 2–3 for settlement/inside_settlement/water) touches
  3 existing test assertions and the field's own documented "fallback string" shape; a future
  reader relying on `feature_id` splitting into exactly `kind:identity` elsewhere would need to
  know about the new middle segment. Grepped every consumer (`tools.py`'s `"feature_id"` key is a
  *different* type, `PlaceMatch.feature_id` from `find_place_by_name`, unrelated) — no other
  consumer parses this string today.
- Dropping coastline's distance figure was not something the user explicitly heard and flagged
  (F7's example sentences never mention the coast) — it's this plan's own generalisation of "drop
  the bracketed distance" to every landmark kind speech can render, for consistency rather than
  leaving one kind as an arbitrary exception. Flagged, not escalated.
- `describe_our_position`/`TOOL_SET`/`belief.console` keep full names by design (see "What already
  exists" above) — if free-text brain replies start reading tool results aloud, this boundary
  needs revisiting there, not here.

### Second-order effect

None identified beyond the brain-facing/debug boundary noted above — this is a narrow, speech-only
wording change with no effect on belief state, contact lifecycle, or any gating logic.
