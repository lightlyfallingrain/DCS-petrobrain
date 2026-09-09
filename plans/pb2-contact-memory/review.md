## Review: Stage 0 (scope-channel repair) + Stage 1 (belief core)

Branch: `feature/pb2-contact-memory`. Reviewed against `plans/pb2-contact-memory/plan.md`
("Stage 0", "Stage 1", "Decision: how much this design leans on `object_id`",
"Interface confirmation") and `plans/pb2-contact-memory/implementation.md`'s stage 0/1 entries.
Stage -1 already reviewed/approved separately and is not re-reviewed here.

### Review Summary

Both stages match the plan closely, with no scope drift. I independently verified the two things
that matter most for this milestone rather than trusting the implementer's self-report:

- **No-omniscience invariant.** Grepped `body-layer/src/belief/*.py` myself for
  `derived_world_position` and `object_id`. The only hits are in `percept.py`'s docstrings
  (naming the field to explain why it's dropped) and in `percept_of()`'s one line that reads
  `observation.derived_world_position`/`observation.id` and discards them into `Percept`. No
  other file in `belief/` references either. `Percept` (`body-layer/src/belief/percept.py:31-46`)
  is confirmed structurally free of truth fields by reading the dataclass directly (7 fields, all
  perceived/bookkeeping — `t_sim`, `source`, `classification_raw`, `bearing_deg`, `range_m`,
  `ownship_at_observation`, `observation_id`).
- **Gating decision rule.** `ContactStore.ingest` (`body-layer/src/belief/contacts.py:146-159`)
  does exactly `len(passing) == 1` → merge, anything else (0 or ≥2) → new contact. No tiebreak,
  no best-match scoring — confirmed by reading `association_over_time.passes_gate`/`ingest`
  directly, not just the test that exercises it.
- **Naked-eye uncertainty formula.** `_naked_eye_uncertainty_m` (`association_over_time.py:142-148`)
  is `hypot(range_m * sin(half of _CLOCK_BUCKET_DEG), _range_bucket_width_m(range_m))`, and both
  `_CLOCK_BUCKET_DEG` and `_RANGE_BUCKETS_M` are imported directly from
  `perception/naked_eye_source.py` (confirmed those constants are defined there, not
  reinvented) — matches implementation.md's claim exactly.
- **Per-source id prefixes.** `perception/source.py:61-62` defines
  `OBSERVATION_ID_PREFIX_HYBRID = "HYBRID_OBS"` / `OBSERVATION_ID_PREFIX_NAKED_EYE = "NAKEDEYE_OBS"`,
  and both `hybrid_source.py` and `naked_eye_source.py` mint ids from their own prefix + a
  per-instance counter — structurally cannot collide.
- **Stage 0's `_type_match_score`** (`perception/association.py:249-273`) resolves
  `object_type` through `reporting_name_for`, scores raw and resolved-name against the
  classification keywords, takes the max. The before/after score table in implementation.md
  (Slava cruiser/MOSCOW 0→2, Tarantul III/MOLNIYA 0→3, SA-3 launcher/5p73 0→3, SA-3 radar/snr 0→5)
  is reproduced by `test_type_match_score_is_nonzero_for_real_reporting_name_tuples`, and the
  Ural-truck no-regression case has its own dedicated test.
- **hybrid_source.py** now reads all five `*_list_text` leaves, dedupes by text, associates each
  distinct text in order against a candidate pool with claimed candidates removed before the next
  leaf — read the actual `poll()` loop (`hybrid_source.py:141-180`), not just the tests.
- **Circular import.** The `TYPE_CHECKING`-only import of `Contact` into
  `association_over_time.py`, relying on `from __future__ import annotations`, is clean — it's a
  type-only forward reference, not a runtime workaround masking a real cycle. `contacts.py`
  importing `association_over_time` at runtime and `association_over_time` needing `Contact` only
  for a type hint is a legitimate one-directional dependency; no design smell here worth
  escalating into a merged module.
- **Two placeholder constants** (`SCOPE_UNCERTAINTY_M = 300.0`, `GATE_GROWTH_RATE_MPS = 20.0`,
  `association_over_time.py:99,106`) are both declared `Final` with comments in the code itself
  ("Placeholder... revisit once real sessions show...") — not just noted in implementation.md.
- **Scope creep check**: no `decay.py`, `events.py`, `tools.py`, `console.py`, or `emit_mode`
  exist anywhere in `src/`. `certainty`/`CONTACT_LOST`/etc. appear only in forward-looking
  docstring mentions inside `contacts.py`/`association_over_time.py` explaining what Stage 2 will
  add — no implementation of any of it landed early.
- **No orphaned work from the earlier dead stage-1 attempts.** `git log` shows exactly 4 stage-1
  commits (`021ae11`, `361c88d`, `88dde21`, `13fb848`) plus the stage-0 pair
  (`23f7157`, `38c421b`) and stage -1's own commits, all on this branch, working tree clean.
  `belief/__init__.py` and `percept.py` match what's actually landed — no stale references to
  modules that don't exist.

Verified checks myself rather than trusting "all green": `ruff format --check`, `ruff check`,
`mypy src` (16 files) and `mypy src tests` (30 files, matching implementation.md's count) all
pass with no issues; `pytest body-layer/tests -q` → **134 passed**, matching the claimed count.

### Required Fixes

None.

### Optional Refinements

- **`body-layer/CLAUDE.md`'s "Structure" section doesn't mention `belief/` yet**, though the plan
  lists `body-layer/CLAUDE.md` under "Modified" files. This is a pre-existing gap pattern (
  `naked_eye_source.py` from PB-1.5 isn't documented there either), so it's not new drift
  introduced by this work, and the package is still growing through Stage 4 — reasonable to defer
  a full write-up until the package settles rather than doc-and-redoc it twice. Worth a short
  pointer entry now or at Stage 2/4, whichever is more convenient (optional).
- **Minor bookkeeping slip in implementation.md**: the "12 + 7 = 19 new tests this session" tally
  for Stage 1 is off — `test_contacts.py` has 6 `test_*` functions, not 7 (one bullet item, "a
  structural grep-based test... with a sanity check", was double-counted as two tests). The 3
  `test_percept.py` tests from the already-committed `021ae11` weren't folded into that arithmetic
  either. The actual total (134 = 113 + 12 + 6 + 3) checks out; only the log's internal subtotal
  is wrong. No code or test-coverage impact — purely a documentation nit (optional).

### Verdict

APPROVED

### Review Confidence

Full read — read `percept.py`, `contacts.py`, `association_over_time.py`, `belief/__init__.py`,
the relevant sections of `perception/association.py`, `perception/hybrid_source.py`,
`perception/geometry.py`, `perception/source.py`, and `perception/naked_eye_source.py`'s bucket
constants in full. Ran format/lint/type/test myself rather than trusting the implementation log.
Test file contents (test_percept.py, test_contacts.py, test_association_over_time.py,
test_hybrid_source.py's new tests) were spot-checked for the specific acceptance cases the plan
names (SA-3 two-observation case, ambiguous-merge case, structural no-truth-field test), not read
line-by-line in full — low risk, since the underlying implementation was already read directly
and the test counts were independently confirmed via pytest.
