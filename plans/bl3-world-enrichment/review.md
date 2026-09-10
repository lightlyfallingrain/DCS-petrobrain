### Review Summary

BL-3 (world enrichment) reviewed against `plans/bl3-world-enrichment/plan.md` and
`plans/bl3-world-enrichment/implementation.md` on `feature/bl3-world-enrichment`
(changes currently staged, not yet committed). Read every changed file in full
(`geometry.py`, `decay.py`, `enrichment.py`, `tools.py`, `console.py`, `logger.py`, and
all five touched/added test files) and ran the full verification suite myself.

**Guardrails verified, not just claimed:**

- `belief/contacts.py` — zero diff. Confirmed via `git diff --cached --stat`; not in the
  changed-file list at all. `Contact.attention` (a plain mutable field, `"normal"` default,
  already existed pre-BL-3 from PB-2 Stage 4) is read, never redefined, by `enrichment.py`'s
  gating — no touch to BL-2.6's in-flight classification work on the sibling branch.
- `geometry.py` — `project_from_bearing_range` body is byte-identical; only its docstring
  changed (stale "BL-3 replaces this" note → cross-reference). `project_terrain_aware` is a
  new, separate function. Confirmed `max_iterations` is a plain caller-supplied `int` inside
  `geometry.py` — no `Attention`/distance logic anywhere in that module; the gating decision
  (`percept.range_m <= PROJECTION_ITERATIVE_RANGE_M or contact.attention == "watch"`) lives
  entirely in `enrichment.py`'s `_terrain_aware_world_position`, exactly per the plan's stated
  import-discipline reasoning.
- `tools.py`/`console.py` additivity — confirmed by reading, not just trusting the log:
  `test_describe_contact_facts_shape` and `test_describe_contact_facts_never_carry_bl3_scope_keys`
  (pre-existing, unmodified) call `describe_contact`/pass no `enrichment` arg and still assert
  BL-2's exact original shape; both pass. New tests
  (`test_describe_contact_without_enrichment_matches_bl2_shape`,
  `test_format_event_for_overlay_unchanged_without_enrichment`) independently re-assert the same
  invariant for the new call sites. `enrichment=None` is threaded as the actual default on every
  signature, not just documented as one.
- Overlay restraint invariant — `format_event_for_overlay(..., enrichment=None)` (the default)
  takes the exact same code path as before BL-3 and the new test locks the literal string output;
  matches the standing BL-2.5-overlay-restraint posture (prior restyle flown and rejected live).
- Gating actually wired: traced `_terrain_aware_world_position` — close-range
  (`percept.range_m <= 2000.0`) or `contact.attention == "watch"` → `max_iterations=5`, else `1`.
  All three cases (close, far-unwatched, watched) have dedicated tests in `test_enrichment.py`
  that capture the actual `max_iterations` value passed to `project_terrain_aware` via a
  monkeypatched stub, not just asserting the output shape.
- Absent-not-null: `motion_when_seen` omits the key entirely (`if motion is not None:
  facts["motion_when_seen"] = motion`), `semantic_facts_for` only appends a `SemanticFact` when
  the corresponding `PositionDescription` field is non-`None`. Verified with a real test
  (`"motion_when_seen" not in facts` for a single-observation contact, both in `test_tools.py` and
  `test_enrichment.py`).
- Coordinate math confined to `geometry.py`'s new function; `enrichment.py` only calls into it
  and into `bearing_deg`/`range_m`, no inline trig of its own outside `_clock_position`'s bearing
  bucketing (not coordinate math, just a display mapping).
- No DCS-install writes; all reads are through the existing world-model seam
  (`query.describe_position`, `store.reader.sample_grid`) already used elsewhere in this
  subproject.
- No `world-model/data/` paths staged (`git diff --cached --stat` checked directly).

**Three documented deviations — all reviewed as real, reasonable, and non-breaking:**

1. Recovering bearing/range via `contributing_observation_ids` → `ContactStore.observations`
   (`_terrain_aware_world_position`) instead of reprojecting the already-flattened
   `last_position`. Correct call — `last_position` alone cannot recover a bearing/range pair,
   and this reuses the same walk-back pattern `motion_when_seen` needs anyway. Falls back to
   `contact.last_position` unchanged when no contributing observation remains in the log
   (defensive, doesn't crash).
2. `SemanticFact.feature_id` always using the fallback string — verified against
   `query/describe.py`'s actual per-field info dataclasses; confirmed none of them expose a raw
   `StoredFeature.id`. Real gap in the upstream API, not an implementer shortcut; correctly
   documented rather than silently worked around.
3. `find_contact` gaining `enrichment` beyond the plan's literal list — correct call under
   AGENTS.md's auto-advance rule (local, reversible, purely additive, optional param defaulting
   to `None`). Leaving it out would have been the actual inconsistency, since `find_contact` and
   `get_contacts` build results through the identical `_contact_result` path.

**Verification run directly (not just trusted from implementation.md):**

```
cd body-layer && .venv/bin/ruff format --check src tests   → pass (42 files)
cd body-layer && .venv/bin/ruff check src tests             → pass
cd body-layer && .venv/bin/mypy src --strict                → pass, no errors
cd body-layer && .venv/bin/pytest tests -q                  → 243 passed
```

Matches the reported 210 baseline + 33 new exactly.

### Required Fixes

- **Stage the implementer-memory files before declaring done.**
  `.claude/agent-memory/implementer/MEMORY.md` is modified-but-unstaged and
  `.claude/agent-memory/implementer/project_bl3_world_enrichment.md` is untracked. Neither is
  code, but `CLAUDE.md`'s Definition of Done requires a clean working tree with all
  new/modified files staged before any task is declared complete — worth a `git add` pass
  before this goes to DoD, otherwise DoD's own "clean working tree" check will just bounce it
  back.

### Optional Refinements

- `WorldEnrichmentCache`'s cached `SemanticFact.confidence` goes stale between recomputes since
  the cache key is `last_position` equality only, not `now_sim` — already documented in the
  cache's own docstring and the plan's Risks section as a deliberate tradeoff. Worth a follow-up
  once real session data shows the staleness window matters (already flagged for BL-4, no action
  needed now).
- `_terrain_aware_world_position`'s fallback to `contact.last_position` when no contributing
  observation survives in `store.observations` is silent (no log/marker distinguishing "used
  terrain-aware projection" from "fell back to flat"). Low-risk since it only affects the
  `position`/`semantic`/`relative_now` display fields, not gating, but could make a future
  debugging session second-guess why a contact's `semantic` facts look stale. Not worth blocking
  on.

### Verdict

APPROVED WITH MINOR FIXES

### Review Confidence

Full read — read every changed source and test file in full (not spot-checked), traced the
gating logic by hand against its three test cases, and ran the complete format/lint/type/test
command sequence myself rather than trusting the implementer's reported numbers.
