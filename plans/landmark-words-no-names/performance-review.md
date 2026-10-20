### Performance Review

Reviewed `feature/landmark-words-no-names` at tip `4ea0fb64b52d6784b45df5778738771e8d8e038a`
(batch diff `f60f99da..4ea0fb64`) against `plans/landmark-words-no-names/plan.md`. Scope: the
runtime (per-poll/per-contact) spoken-callout path in `body-layer/src/belief/enrichment.py` and
`body-layer/src/belief/speech.py`, plus one additive read in `world-model/src/query/describe.py`.
Phase: Petrobrain Runtime (perception/belief/speech poll loop) — no hard real-time budget in force
yet per root `CLAUDE.md`, but "no per-request allocations on hot paths" and "prefer batching" still
apply, and this path is a known cost hotspot (`BL-B49`, memory
`project_report_query_enrichment_dominates.md`: `semantic_facts_for` floors at ~63 ms/contact on
real `syria-full.sqlite`).

### Findings

#### `_settlement_size_word` (new, `enrichment.py`)

- **Location:** `enrichment.py::_settlement_size_word`, called from `semantic_facts_for`'s
  settlement/inside_settlement branches, inside `WorldEnrichmentCache.get_or_compute` (cached per
  contact id / 50 m position cell — unchanged by this diff).
- **Risk:** None credible. Two string equality checks and at most one float comparison, no
  allocation beyond the returned literal `"village"`/`"town"` string (interned). It runs only on a
  cache miss, same frequency `semantic_facts_for` already ran at before this change — it adds work
  *inside* an existing cached call, not a new call site.
- **Action:** MONITOR (folded into the existing BL-B49 entry, not a new concern).
- **Mitigation:** none needed.

#### `feature_id` string construction (`enrichment.py`, settlement/inside_settlement/water)

- **Location:** `semantic_facts_for`, three f-string formats changed from 1 segment to 2–3
  segments (e.g. `f"settlement:{size_word}:{settlement.name or 'unnamed'}"`).
- **Risk:** None credible. Same number of f-string builds as before (one per fact, and the set of
  facts per position is small and bounded — settlement/inside_settlement/road/water/ridge/valley/
  landcover/coastline, never more than a handful), just a longer string. No new iteration, no new
  query — `settlement.area_m2` is a field already present on the `SettlementInfo` row this
  function already receives, not an extra fetch.
- **Action:** MONITOR.
- **Mitigation:** none needed.

#### `world-model/query/describe.py::_settlement_info` — `area_m2` field addition

- **Location:** `_settlement_info`, one new line: `area_m2=feature.tags.get("area_m2")`.
- **Risk:** None. `feature.tags` is already loaded for this row — `_preferred_settlement`, two
  functions above, already reads the same tag for its own tie-break. This is a dict `.get()` on
  data already in memory, not a new column read or query. Confirmed the only two call sites of
  `describe_position` outside the runtime path (`world-model/src/build/validate.py`'s
  `spot_check_positions`) iterate a small, fixed, named `list[SpotCheckPoint]` (operator-authored
  spot checks), not a full-theatre scan — so Milestone 5/7 whole-theatre batch runs are unaffected;
  this field is never read in a per-feature ingest loop.
- **Action:** MONITOR.
- **Mitigation:** none needed.

#### `_landmark_speech_text` replacing `_round_enrichment_fragment` (`speech.py`)

- **Location:** `speech.py::_landmark_speech_text`, called once per call site
  (`render_engage_readback`, `_contact_report_text`) — same two call sites, same call frequency as
  the function it replaces.
- **Risk:** None credible. The new function does: one `dict.get` for `feature_id`, one `str.
  partition`, a linear scan over a 4-tuple of literal prepositions (`_landmark_preposition`), one
  regex search reused from before (`_TRAILING_DISTANCE_RE`, same pattern as the deleted
  `_ENRICHMENT_DISTANCE_RE`), and a few small string formats. This is marginally *cheaper* than the
  function it replaces (no `round()`/arithmetic on the distance figure — the figure is dropped
  rather than rounded-and-spelled), not more expensive. No per-request allocation pattern that
  wasn't already present (string building here is unavoidable text-rendering work, not a
  data-structure allocation on a hot loop).
- **Action:** MONITOR.
- **Mitigation:** none needed.

### Context checked, not just assumed

- `semantic_facts_for`'s only runtime call site is `WorldEnrichmentCache.get_or_compute`
  (`enrichment.py:756`), which short-circuits on a cache hit (same `contact_id` + 50 m position
  cell) before reaching any of this diff's changed code — this diff does not add a cache-busting
  dependency (no new mutable input read into the cache key) and does not change hit-rate behaviour.
- The other two `semantic_facts_for` callers (`mission_memory/marks.py`, `belief/tools.py`) are
  both existing per-command/per-mark call sites, not a poll-loop or batch path, and neither is
  touched by this diff.
- No new SQL query, no new loop over a world-model table, and no new I/O was introduced anywhere in
  the batch diff — grepped both diffs for new `conn.execute`/`for ... in` constructs touching
  stored features; none found outside the pre-existing bounded fact list.

### Verdict

APPROVED

No action required now or later beyond what BL-B49 already tracks (the pre-existing
`semantic_facts_for`/`describe_position` cost itself, unrelated to this batch). This change adds
O(1) string formatting on top of an already-cached, already-bounded call path, removes one
`round()`/arithmetic step, and its one world-model field addition reads already-loaded data with no
new query — credible risk is effectively zero at both current and whole-theatre scale.
