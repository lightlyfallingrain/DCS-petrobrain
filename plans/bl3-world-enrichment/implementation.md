### Implementation Summary

Implemented BL-3 (world enrichment) per `plans/bl3-world-enrichment/plan.md`'s 7-step
Implementation Plan, on `feature/bl3-world-enrichment`. All 6 code steps landed; step 7 (live
sanity pass) ran fully offline against a real world-model region `.sqlite`
(`world-model/data/world-model/syria-full.sqlite`), no live DCS/aircraft-layer needed -- see
"Step 7" below.

`belief/contacts.py` was not touched (BL-2.6/`feature/classification-refinement` is mid-flight
on that file); `perception/geometry.py`'s `project_from_bearing_range` was not modified, only
extended alongside with a new function, per the plan's resolved decisions.

### Files Changed

- `body-layer/src/perception/geometry.py` -- added `project_terrain_aware(conn, theatre,
  observer, bearing_deg, range_m, *, max_iterations)`: a fixed-point iteration (horizontal
  position <-> target altitude via `store.reader.sample_grid`) that falls back to
  `project_from_bearing_range` if elevation is ever unavailable. `max_iterations` is a plain
  caller-supplied `int`, no attention/distance logic inside this module. Updated
  `project_from_bearing_range`'s docstring to cross-reference the new function instead of the
  stale "BL-3 replaces this" note.
- `body-layer/src/belief/decay.py` -- added `position_confidence(contact, now_sim) -> float`,
  exponential decay over `POSITION_HALF_LIFE_S` (`0.5 ** (elapsed_s / half_life)`, written via
  `math.pow` rather than the `**` operator -- see Notable Discoveries).
- `body-layer/src/belief/enrichment.py` (**new**) -- `SemanticFact`, the feature-confidence
  mapping table, `semantic_facts_for`, `WorldEnrichmentCache`, `relative_geometry`,
  `motion_when_seen`, `EnrichmentContext`, and `PROJECTION_ITERATIVE_RANGE_M` (2000.0,
  placeholder). See "Deviations from the plan's prose" below for two concrete resolutions the
  plan left implicit.
- `body-layer/src/belief/tools.py` -- `_contact_facts`/`_contact_result`/`get_contacts`/
  `describe_contact` gained the optional `enrichment: EnrichmentContext | None = None` parameter
  named in the plan; `find_contact` also gained it (a deliberate, documented extension beyond the
  plan's explicit function list -- see Deviations). `_contact_facts` also gained a `store:
  ContactStore` parameter (needed to call `WorldEnrichmentCache.get_or_compute`/
  `motion_when_seen`, both of which need the store) -- all three call sites already had `store`
  in scope, so this is a pure signature change, no new state threading. `enrichment=None` leaves
  every function's output byte-for-byte identical to before (verified by
  `test_describe_contact_facts_shape`/`test_describe_contact_facts_never_carry_bl3_scope_keys`,
  both unmodified).
- `body-layer/src/belief/console.py` -- `Console` gained an optional `enrichment` field;
  `_dispatch`/`_handle_contacts`/`_handle_show`/`_handle_find` thread it through;
  `_SHOW_FACT_KEYS` gained `relative_now`/`semantic`/`motion_when_seen` (safe additions -- the
  block-formatter already skips absent keys); `format_event_for_overlay` gained an optional
  `enrichment` parameter that appends the highest-confidence `SemanticFact.text` to the mirrored
  line, `None` unchanged.
- `body-layer/src/logger.py` -- `ConsolePerceptionRunner` gained `world_model_conn`/`theatre`
  (set once by `_run_console_poll_loop`, same thread-affinity reasoning as `sources`),
  `last_ownship_state` (mirrors `last_t_sim`, not otherwise consumed this milestone), and
  `enrichment: EnrichmentContext | None` (built lazily on first successful poll, then mutated in
  place -- `ownship` is the only field that changes poll to poll, so the same
  `WorldEnrichmentCache` persists). `run_once` updates `enrichment.ownship` every poll and passes
  `self.enrichment` into `format_event_for_overlay`. `_run_console_repl` syncs
  `console.enrichment = runner.enrichment` before every command (mirroring how it already reads
  `runner.last_t_sim`).

### Tests Added

- `test_geometry.py` -- `project_terrain_aware` over flat terrain (matches the flat projection
  exactly, both `max_iterations=1` and `=5`), over a known linear slope (one-shot matches the
  flat horizontal position with a corrected altitude; 5 iterations converges closer to the
  observer, consistent with the terrain sampled at the converged point), and the
  elevation-unavailable fallback.
- `test_decay.py` -- `position_confidence` at zero elapsed (1.0), at one/two half-lives
  (0.5/0.25), negative-elapsed clamping, and monotonic decay.
- `test_enrichment.py` (new) -- `semantic_facts_for` (empty description, all six fields present,
  confidence combination, unknown-confidence fallback, unnamed-settlement text);
  `WorldEnrichmentCache` (miss-then-store, hit on unchanged `last_position`, miss on changed
  `last_position`, `max_iterations` selection for close/far/watched contacts); `relative_geometry`
  (dead-ahead, 3-o'clock, heading-relative clock position); `motion_when_seen` (`None` for one
  observation, direction+speed from two distinct positions within the gate radius, `None` when
  both positions coincide).
- `test_tools.py` -- `enrichment=None` matches BL-2's exact shape; `enrichment` given adds
  `position.confidence`/`semantic`/`relative_now` (and omits `motion_when_seen` for a
  single-observation contact); `get_contacts`/`find_contact` thread `enrichment` through every
  result.
- `test_console.py` -- `show <id>` includes/omits the BL-3 fields depending on
  `Console.enrichment`; `format_event_for_overlay` appends/omits the semantic fragment depending
  on its `enrichment` argument.

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (run as `cd body-layer && .venv/bin/mypy src`, per this subproject's CWD
  requirement): pass, no errors
- `pytest body-layer/tests -q`: pass, 243 passed (210 baseline + 33 new)
- Also ran `ruff format --check`/`ruff check`/`mypy` directly against each new/changed test file
  individually (not part of the mandated command list, but kept consistent with existing test
  files, all of which pass `mypy --strict` cleanly today)

### Step 7: live sanity pass

Ran fully offline against `world-model/data/world-model/syria-full.sqlite` (a real, already-built
full-theatre region database already present locally -- no live DCS or aircraft-layer connection
needed, matching the task brief's framing of what step 7 actually requires). Exercised
`project_terrain_aware` (5 iterations, converged from `alt_m=500` flat assumption down to
`alt_m=17.8`, consistent with real coastal-plain elevation near the sampled point),
`semantic_facts_for` (a real `nearest_road` fact from the store's actual road layer), and the
full `tools.describe_contact(..., enrichment=...)` path end-to-end, producing exactly the shape
the plan's Goal describes: `position.confidence`, `semantic`, `relative_now` populated,
`motion_when_seen` correctly absent (single contributing observation). See the transcript in this
session's tool output for the full JSON.

**Finding: the two locally-available fixture `.sqlite`s are not equally usable.**
`world-model/data/world-model/latakia-20km.sqlite` (the smaller, feature-richer build --
settlement/water/ridge/valley layers all present) predates the M7 Stage 2 `grid.provenance`
schema bump (`project_m7_stage2_srtm_provenance` memory) and fails immediately with
`sqlite3.OperationalError: no such column: provenance` on *any* `describe_position` call, not
just the new terrain-aware path -- this is a pre-existing gap in current `main`, not something
this branch introduced. `syria-full.sqlite` has the current schema and a real elevation grid, but
its `feature` table only has `airfield`/`named_place`/`navaid`/`road`/`runway` rows -- no
`settlement`/`water`/`ridge`/`valley` (that ingestion apparently never ran for the full-theatre
build). The live pass above therefore only exercised the `nearest_road` branch of
`semantic_facts_for` for real; the other five branches are covered by `test_enrichment.py`'s
fakes, not by a live store. Not a BL-3 code defect -- flagged for whoever next needs a
schema-current, feature-complete local fixture (rebuilding `latakia-20km.sqlite`, or running the
missing ingestion stages against `syria-full.sqlite`).

### Deviations from the plan's prose

- **Recovering a bearing/range pair for `project_terrain_aware`.** The plan's step 1/3 describe
  feeding a contact's "position" into the terrain-aware projection, but `Contact` only stores the
  already-flattened `last_position`, never the bearing/range pair that produced it.
  `_terrain_aware_world_position` (`enrichment.py`) resolves this by walking
  `contact.contributing_observation_ids` back through `ContactStore.observations` (the same
  pattern `motion_when_seen` needs anyway) to recover the most recent contributing `Percept` and
  re-deriving from *its* `ownship_at_observation`/`bearing_deg`/`range_m`. Documented in the
  module docstring as a concrete resolution of an implicit gap, not an improvised redesign.
- **`SemanticFact.feature_id`.** The plan says to prefer `StoredFeature.id`, falling back to a
  stable string only when absent. In practice none of `query.describe.PositionDescription`'s
  per-field info dataclasses (`SettlementInfo`, `RoadInfo`, `WaterInfo`, `TerrainLineInfo`)
  expose the underlying `StoredFeature.id` at all -- `describe_position` never threads it
  through. The fallback string is therefore always used (kind + name, or a 100m-bucketed
  distance for the nameless ridge/valley lines).
- **`find_contact` also threads `enrichment`.** The plan's Affected Modules section names only
  `_contact_facts`/`_contact_result`/`get_contacts`/`describe_contact`. `find_contact` builds the
  same `ContactResult` via the same `_contact_result` call as `get_contacts`, so leaving it
  unenriched would have been a silent, surprising gap (identical-looking results with different
  shapes depending on which of two near-identical tools returned them). Extended for consistency
  -- local, reversible, purely additive (optional param, `None` default, zero behavior change
  without it), so proceeded without escalating per `AGENTS.md`'s auto-advance rule.

### Notable Discoveries

- **`float ** float` returns `Any` under `mypy --strict`.** `0.5 ** (elapsed_s /
  POSITION_HALF_LIFE_S)` triggered `no-any-return` even though every operand is a plain `float`
  -- a known typeshed quirk (the `**` operator's overloads admit a `complex` result in general,
  so mypy can't narrow it to `float`). Fixed with `math.pow(0.5, ...)`, which has an unambiguous
  `float -> float` signature. Worth remembering for any other exponentiation in this codebase.
- **`project_terrain_aware`'s single-shot (`max_iterations=1`) behavior is subtle.** One
  iteration samples terrain at the *flat* horizontal position (computed from the observer-altitude
  assumption) and only corrects the reported altitude -- it does not yet re-solve the horizontal
  position itself. That only happens from the second iteration on, once the corrected altitude
  feeds back into a smaller horizontal range. This matches the plan's fixed-point framing exactly,
  but is easy to misread as "single-shot does nothing" -- confirmed and pinned by
  `test_project_terrain_aware_converges_on_a_known_slope`.
- **`WorldEnrichmentCache`'s cached `SemanticFact.confidence` values go stale between recomputes.**
  Since a cache hit is keyed only on `Contact.last_position` matching, not on `now_sim`, a
  contact whose position hasn't changed but whose `position_confidence` has decayed further will
  keep returning the confidence numbers computed at the last cache miss until its position
  actually moves (or a new contact triggers a fresh gate). Documented in the cache's own
  docstring as a deliberate perf/staleness tradeoff, consistent with the plan's own "cache hit
  rate not measured yet" Risk.
