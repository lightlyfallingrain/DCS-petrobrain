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

---

## Review: Stage 2 (Decay, certainty, lifecycle)

Branch: `feature/pb2-contact-memory`. Reviewed against `plans/pb2-contact-memory/plan.md`'s
"Stage 2 — Decay, certainty, lifecycle" section and `plans/pb2-contact-memory/implementation.md`'s
Stage 2 entry. Stages -1, 0, 1 already reviewed/approved above and not re-reviewed here.

### Review Summary

**§3.4 claim verified.** Read `docs/concept/PETROBRAIN_RUNTIME.md` directly. There is no numbered
"§3.4" section anywhere in the doc and no concrete certainty enum/threshold table. The only
relevant content is the unnumbered `## Uncertainty and memory decay` heading (lines 440–469),
which names exactly four attributes with relative decay speeds (identity slow, exact position
fast, general area medium/slow, last movement direction medium) and exactly four example
wordings ("I see him." / "I think he was..." / "Last saw him..." / "I lost him."), with no named
levels or numbers. The implementer's claim is accurate, not a rationalization for skipping work.
The derived four-level ladder (`observed`/`tracked`/`estimated`/`lost`) maps onto the four
wordings in the obvious 1:1 order and is documented as a placeholder in `decay.py`'s module
docstring and per-constant comments — this is a reasonable, well-flagged interpretation, not a
drift from intent. No required fix here.

**Code read directly, not just tests:**

- `certainty_of` (`body-layer/src/belief/decay.py:97-109`) is genuinely pure — takes
  `(contact, now_sim)`, computes `elapsed_s = max(0.0, now_sim - contact.last_seen_sim)`, reads
  only `contact.last_seen_sim`, writes nothing, imports nothing time-related. Ladder is top-down
  first-match-wins as required (`observed` ≤5s, `tracked` ≤30s, `estimated` ≤120s, else `lost`).
  Negative elapsed time clamps to 0 (`observed`), tested explicitly.
- `lifecycle_event_kind` (`body-layer/src/belief/events.py:51-79`) is a pure 3-branch comparison
  over `(previous_certainty, current_certainty)` with no `Contact`/`ContactStore` access. Verified
  the "skip two ticks" case by construction, not just by reading the docstring: because
  `certainty_of` is computed fresh from `now_sim - last_seen_sim` every call (not from
  `last_emitted_certainty`'s tick time), a contact that goes straight from `observed` to `lost`
  without an intervening tick still gets `was_lost=False, is_lost=True` → `CONTACT_LOST` correctly
  emitted, once. `contacts.py:210-225`'s `tick()` confirms this — it always calls `certainty_of`
  against real elapsed time, never against "time since last tick." The `None → lost` special case
  (no synthetic detected+lost pair) is a deliberate, documented design call, consistent with "no
  event that misrepresents what was actually perceived."
- **Determinism test** (`test_contacts.py:198-211`,
  `test_identical_replay_twice_produces_byte_identical_events`) does exercise real sim-time-driven
  logic — `_replay_detected_lost_reacquired` drives `ingest`/`tick` through a detected → (decay to)
  lost → reacquired sequence using explicit `now_sim` values, and the assertion is
  `store_a.events == store_b.events` (dataclass equality, so field-for-field: id, contact_id,
  kind, t_sim, certainty all compared), not just `len(...) ==`. Confirmed `decay.py`/`events.py`/
  `contacts.py` contain no `time.time()`/`datetime`/`perf_counter` calls (grepped directly) — if
  wall-clock time leaked in anywhere, event ids/kinds are still deterministic (minted from a
  counter, and t_sim is an explicit argument), but `certainty` values would become sensitive to
  real inter-call latency and could plausibly diverge near a boundary across two sequential
  replay calls in the same test process. The test would catch that class of regression, not just
  confirm something trivially deterministic by construction.
- **Boundary coverage** (`test_decay.py`, 9 tests): each of the three thresholds
  (`OBSERVED_WINDOW_S`, `POSITION_HALF_LIFE_S`, `LOST_THRESHOLD_S`) has its own at-boundary and
  just-past-boundary test, plus zero-elapsed, far-past-lost, and negative-elapsed cases. One test
  per edge, not one broad test — matches the plan's "each `certainty` row is pinned by a test."
  `test_events.py` (6 tests) covers every `lifecycle_event_kind` branch including same-level
  no-ops and all three sub-level combinations while alive.
- **Identity invariant.** Grepped `decay.py`/`events.py` myself for `derived_world_position` and
  `object_id` — no hits in either file. The Stage 1 structural grep test in `test_contacts.py`
  (`test_belief_source_never_references_derived_world_position`) globs all of `belief/*.py`, so it
  already covers these two new files without modification.
- **Six half-life constants**: `OBSERVED_WINDOW_S`, `POSITION_HALF_LIFE_S`, `LOST_THRESHOLD_S` are
  read by `certainty_of`; `MOTION_HALF_LIFE_S`, `GENERAL_AREA_HALF_LIFE_S`, `IDENTITY_HALF_LIFE_S`
  are declared `Final[float]` module-level constants with comments explicitly stating "not yet
  consumed" and which future milestone (BL-3/BL-4) will consume them. `ruff check` passes clean —
  module-level `Final` constants aren't flagged as unused by ruff/mypy the way a local variable
  would be, and there's no dead code path referencing them; they read as a documented, intentional
  placeholder table, not leftover debug scaffolding.
- **No scope creep**: grepped `src/` for `emit_mode`, and confirmed no `tools.py`/`console.py`
  exist under `belief/` (directory listing: `__init__.py`, `association_over_time.py`,
  `contacts.py`, `decay.py`, `events.py`, `percept.py`). `percept.py` and
  `association_over_time.py` untouched this stage, consistent with implementation.md's claim.

Ran checks myself rather than trusting the log: `ruff format --check src tests`,
`ruff check src tests`, `cd body-layer && mypy src` (18 files) all pass clean;
`pytest body-layer/tests -q` → **151 passed**, matching the claimed count exactly
(134 + 9 + 6 + 2). `git status` confirms a clean working tree; `git log` shows the two claimed
commits (`e00e505` decay/events + tests, `2626c6c` contacts.py wiring + integration tests) plus
the two doc-log commits on top, all on this branch.

### Required Fixes

None.

### Optional Refinements

- **`Contact.last_emitted_certainty` documentation vs. mutation surface**: the field is documented
  as "written only by `ContactStore.tick`," which is true of production code paths, but it's a
  plain mutable dataclass field with no property/setter enforcement — nothing stops a future
  caller (e.g. Stage 4's console/tools code) from setting it directly and silently breaking the
  invariant `tick()` relies on. Not a Stage 2 defect (Stage 1 already established this pattern for
  `Contact`'s other fields via `record()`), but worth a note for whoever writes `tools.py` in
  Stage 4 not to touch this field directly (optional).
- **`OBSERVED_WINDOW_S = 5.0` is described as "close to one polling interval" but body-layer polls
  at ~1 Hz** — a 5x margin above the stated poll rate. This is flagged and justified in the code
  comment as accounting for "no direct signal for was this contact in the most recent poll's
  batch," so it's a documented judgment call, not an oversight, and is explicitly a placeholder
  per the plan's "tune against real sessions, do not argue now" instruction. No action needed now;
  worth revisiting alongside the other placeholder constants when real session data exists
  (optional).

### Verdict

APPROVED

### Review Confidence

Full read — read `decay.py`, `events.py`, and the changed portions of `contacts.py` in full;
read `docs/concept/PETROBRAIN_RUNTIME.md`'s relevant section directly rather than trusting the
implementer's paraphrase; read `test_decay.py` and `test_events.py` in full (both are short and
exhaustive); read the new `test_contacts.py` additions (replay helper, ordering test, determinism
test, tick-mutation test) in full. Ran format/lint/type/test myself. Did not re-read Stage 0/1
files already verified in the section above.
