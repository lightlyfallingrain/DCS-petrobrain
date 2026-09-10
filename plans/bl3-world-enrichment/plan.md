### Goal

Fill in `describe_contact`'s still-empty `position.confidence`, `relative_now`, `semantic`, and
`motion_when_seen` fields (`plans/body-layer/plan.md` §3.4) by adding terrain-aware world-position
estimation, a world-model semantic-facts lookup with caching, and live-ownship relative-geometry
recomputation — without touching BL-2's contact/classification logic or redesigning the frozen
response shape.

No DCS-internals unknowns are involved (this is intra-repo composition of already-verified
world-model/aircraft-layer APIs), so no Investigator pass is needed.

---

### Affected Modules / Files

- `body-layer/src/perception/geometry.py` — add a new terrain-aware projection function
  (`project_terrain_aware`, exact name TBD by Implementer). **Does not modify
  `project_from_bearing_range`** — that function stays exactly as-is because
  `belief.association_over_time`'s percept↔contact gating depends on its current flat behavior
  and tuned radius constants (`GATE_GROWTH_RATE_MPS`, `SCOPE_UNCERTAINTY_M`); changing it would
  silently retune BL-2's gate. The new function is BL-3-only, used solely for the `position` field
  shown to the brain.
- `body-layer/src/belief/decay.py` — add `position_confidence(contact, now_sim) -> float`, an
  exponential-decay function over `POSITION_HALF_LIFE_S` (already declared, only referenced by
  `certainty_of`'s hard cutoff today). This is the numeric confidence the plan's `position`,
  `semantic`, and `motion_when_seen` fields all key off. Purely additive — does not touch
  `certainty_of` or any BL-2.6 classification logic.
- `body-layer/src/belief/enrichment.py` (**new**) — the world-enrichment orchestration:
  - `SemanticFact` dataclass: `{text, confidence, provenance, feature_id}`.
  - A small, documented placeholder table mapping world-model's string confidence enum
    (`"high"/"medium"/"low"/"unknown"` from `StoredFeature.confidence`) to a numeric 0–1 value —
    same spirit as `association_over_time.SCOPE_UNCERTAINTY_M`: a declared, revisitable constant,
    not a derivation.
  - `semantic_facts_for(conn, theatre, position) -> list[SemanticFact]`: calls
    `query.describe_position` once and maps `nearest_settlement`/`inside_settlement`/
    `nearest_road`/`nearest_water`/`nearby_ridges`/`nearby_valleys` into the flat list, combining
    each feature's mapped confidence with `position_confidence`, and using `feature.id` (falling
    back to a stable string like `f"{kind}:{id}"`) for `feature_id`. Absent facts stay absent —
    same "absent, not null" rule `tools.py` already documents.
  - `WorldEnrichmentCache`: a plain `dict[str, tuple[GeoPosition, GeoPosition, list[SemanticFact]]]`
    keyed by `contact_id`, storing `(cached last_position, terrain-aware world position, semantic
    facts)`. On each lookup, compare the contact's *current* `last_position` (structural equality —
    `GeoPosition` is a frozen dataclass) against the cached one; recompute only on mismatch. This
    is the "semantic caching" the milestone brief names. **Deliberately lives outside
    `belief.contacts.Contact`** — not a new field on `Contact` — specifically to avoid touching
    `contacts.py`, which BL-2.6 (in progress on `feature/classification-refinement`) is also
    modifying (`Contact.classification` folding). Zero shared surface with that branch.
  - `relative_geometry(ownship: OwnshipState, target: GeoPosition) -> dict[str, object]`: reuses
    `geometry.bearing_deg`/`geometry.range_m`, adds a bearing→clock-position helper and
    `relative_alt_m = target.alt_m - ownship.alt_m`. Pure, cheap trig — **never cached**, since
    ownship moves every poll while the contact's belief position does not.
  - `motion_when_seen(store: ContactStore, contact: Contact) -> dict[str, object] | None`: walks
    `contact.contributing_observation_ids` back through `store.observations`, recomputes each
    percept's implied position (`association_over_time.implied_position`), and derives a
    direction from the two most recent *distinct* implied positions. Returns `None` (key omitted
    entirely, per the absent-not-null rule) when fewer than two distinct positions exist — e.g. a
    brand-new contact.
- `body-layer/src/belief/tools.py` — `_contact_facts`/`_contact_result`/`get_contacts`/
  `describe_contact` gain an optional `enrichment: EnrichmentContext | None = None` parameter
  (bundling `conn`, `theatre`, current `OwnshipState`, and a `WorldEnrichmentCache`), defaulting to
  `None` so BL-2's existing behavior and tests are unchanged when it's omitted. When supplied,
  `_contact_facts` adds `position.confidence`, `relative_now`, `semantic`, and
  `motion_when_seen` keys. This is an additive parameter and an additive set of dict keys — the
  existing `classification` key BL-2.6 is reshaping is untouched.
- `body-layer/src/belief/console.py` — `Console` gains an optional `EnrichmentContext` so `show
  <id>` can print the new fields; `format_event_for_overlay` optionally appends one short semantic
  fragment (the highest-confidence `SemanticFact.text`) to the mirrored line — the BL-2.5-inherited
  follow-up named in the milestone brief. Guarded the same way: no enrichment context, no change
  in output.
- `body-layer/src/logger.py` — `ConsolePerceptionRunner` gains `last_ownship_state` (mirroring the
  existing `last_t_sim` pattern) updated every poll, and builds an `EnrichmentContext` once
  (reusing the `world_model_conn`/`theatre` it already opens for `NakedEyePerceptionSource`'s LOS
  gate) to pass into the REPL's `tools.py` calls.
- Tests: `body-layer/tests/test_geometry.py` (terrain-aware projection, against the same
  known-elevation fixtures/control points world-model's own tests use — no new control-point
  infrastructure), `test_decay.py` (position_confidence), `test_enrichment.py` (new — semantic
  mapping, cache hit/miss, motion derivation, all against fakes, no live DCS/world-model build
  required), `test_tools.py` (enrichment param threading, absent-when-None).

---

### Implementation Plan

1. **Terrain-aware projection** (`geometry.py`). Add `project_terrain_aware(..., max_iterations:
   int)`: iteratively converge on a horizontal position consistent with observer altitude, bearing,
   slant range, and the world-model terrain elevation *at that horizontal position* (a fixed-point
   problem — the horizontal/vertical split of slant range depends on target altitude, which depends
   on terrain elevation, which depends on horizontal position). Reuse `sample_grid` directly for the
   per-iteration elevation reads (`line_of_sight_clear`'s existing pattern), not
   `describe_position` (avoids repeating its road/settlement/navaid joins every iteration).
   `max_iterations` is a caller-supplied parameter, not a module constant — see the distance/
   attention gating below. Falls back to the flat `project_from_bearing_range` result if elevation
   data is ever unavailable (`sample_grid` returns `None`) rather than guessing. Unit test against
   fixtures with a known slope, at both `max_iterations=1` and `=5`.

   **Gating (user decision, 2026-09-10):** the caller (`enrichment.py`, step 3) picks
   `max_iterations` per contact rather than the module using one fixed value everywhere:
   `1` (single-shot) by default, `5` (iterative) when either `range_m ≤
   PROJECTION_ITERATIVE_RANGE_M` (new constant, placeholder `2000`, same "declared and
   revisitable" status as `SCOPE_UNCERTAINTY_M`) or `contact.attention == "watch"` (the bare
   attention enum already on `Contact` since PB-2 Stage 4 — no new field needed). This keeps the
   expensive path for contacts that are either close or already flagged as worth the player's
   attention, and the cheap path for everything else in a `get_contacts` sweep. Placement note:
   this if this two-line policy lived in `geometry.py` it would need to import `belief.contacts`
   for the `Attention` type, which `perception/` must never import (see BL-2.6's own
   `perception → belief` import discipline) — so the gating logic belongs in `enrichment.py`
   (already `belief`-side), which calls `project_terrain_aware` with a plain `int` it already
   computed. `geometry.py` itself stays ignorant of attention/distance policy, same posture as
   `classification_level` on `Observation`.
2. **Position confidence** (`decay.py`). Add `position_confidence`, pure exponential decay,
   documented in the module's existing "one table" convention.
3. **Semantic facts + cache** (`enrichment.py`). Build `SemanticFact`, the confidence-mapping
   table, `semantic_facts_for`, and `WorldEnrichmentCache`. Test the mapping and cache hit/miss
   behavior against a small fixture region `.sqlite` (reuse world-model's test fixtures rather than
   building a new one).
4. **Relative geometry + motion** (`enrichment.py`). Add `relative_geometry` and
   `motion_when_seen`. Test both against synthetic `Contact`/`ContactStore` fixtures — no live
   session needed.
5. **Wire into `tools.py`**. Add the optional `EnrichmentContext` parameter; extend
   `_contact_facts` to populate the four new keys only when supplied. Confirm existing BL-2 tests
   pass unchanged (they call without the new parameter).
6. **Wire into `console.py`/`logger.py`**. Thread `EnrichmentContext` through the REPL and
   `format_event_for_overlay`. Add `ConsolePerceptionRunner.last_ownship_state`.
7. **Live sanity pass** (per `body-layer/CLAUDE.md`'s testing posture, this is the one stage that
   isn't pure-fixture): run `--console --overlay` against a real world-model region `.sqlite` and
   confirm `show <id>` prints plausible semantic text and relative geometry, and that the overlay
   line is not truncated/garbled by the added fragment.

---

### Risks & Unknowns

- **BL-2.6 rebase.** `feature/classification-refinement` (parked at Stage 5, awaiting live
  acceptance) also touches `tools.py` (`facts.classification` reshape) and `console.py`
  (`format_event_for_overlay`). This plan's changes to both files are additive — new dict keys, a
  new optional parameter, an appended text fragment — and deliberately avoid `contacts.py`
  entirely, so the two branches should merge with at most a straightforward textual conflict, not
  a logic conflict. Called out explicitly per the task brief; do not assume zero-conflict.
- **Iterative terrain-fit convergence.** Unverified how well 5 iterations converges for steep
  local terrain (e.g. Kola's high-relief slopes, per the `M7 direction` memory) vs. flat desert. If
  it oscillates or converges slowly, the fallback is accepting a fixed, undocumented error margin
  rather than an unbounded loop — needs a real test against a sloped fixture before trusting it.
- **`PROJECTION_ITERATIVE_RANGE_M` and the `attention == "watch"` escalation are both first-guess
  gating rules**, same placeholder status as the confidence-mapping table below — tune once a live
  session shows whether far-but-watched contacts (or close-but-unwatched ones just inside the
  threshold) get visibly worse position quality than they should.
- **Confidence-mapping placeholder.** The string→numeric world-model confidence table and the
  `position_confidence × feature_confidence` combination formula are both first-guess constants,
  same status as `SCOPE_UNCERTAINTY_M` — expect to retune once real sessions show whether
  `semantic` entries read as over- or under-confident.
- **`describe_position` cost.** It runs several spatial joins (named places, navaids, roads,
  settlements, ridges/valleys) per call; `get_contacts` listing many contacts without cache hits
  could be slow. The cache (step 3) is the mitigation, but its hit rate depends on how often
  contacts' `last_position` actually changes vs. how often `get_contacts` is polled — not
  measured yet.
- **`motion_when_seen` data quality.** Derived from only two implied positions with no smoothing;
  a single noisy scope-channel percept could flip the reported direction. Documented as a known
  weakness, not fixed here — averaging/smoothing is a natural BL-4 refinement, not scope creep to
  add now.

---

### Decisions — resolved by the user, 2026-09-10

- **Terrain-aware projection method → distance/attention-gated, not a single fixed choice.**
  Neither "always iterative" nor "always single-shot" — the user asked whether this could instead
  be gated: single-shot far away, iterative when close or the contact has the player's attention.
  Yes: see the gating rule under Implementation Plan step 1. `max_iterations` becomes a
  per-contact-call parameter chosen by `enrichment.py`, defaulting to single-shot (`1`) and
  escalating to iterative (`5`) inside `PROJECTION_ITERATIVE_RANGE_M` (placeholder `2000`, tune
  later) or when `contact.attention == "watch"`.
- **Two projection functions' coexistence → same module, docstrings only.** Confirmed per the
  architect's recommendation — no separate `terrain_projection.py` submodule.

---

### Second-Order Effect

Unblocks BL-4's relevance scoring and area attention (both need a real world position and
semantic location to reason about "near the village" / "near ownship"), and gives BL-5's
`describe_contact`/`get_contacts` tools their full frozen §3.4 shape a milestone early — but it
also means BL-4 inherits this plan's placeholder confidence-mapping and unsmoothed motion estimate
as load-bearing inputs, not just cosmetic display fields, so those placeholders are worth revisiting
before BL-4 leans on them for scoring decisions.
