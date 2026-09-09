## Review: Stage 3 (Emission policy and pipeline wiring)

Branch: `feature/pb2-contact-memory`. Reviewed against `plans/pb2-contact-memory/plan.md`'s
"Stage 3 — Emission policy and pipeline wiring" section and "Interface confirmation" gap 2, and
`plans/pb2-contact-memory/implementation.md`'s Stage 3 entry. Stages -1, 0, 1, 2 already
reviewed/approved above and not re-reviewed here.

### Review Summary

Read every changed file's full diff directly (not just the implementer's self-report) and ran
all verification commands myself.

- **Pre-Stage-3 behavior preservation.** `git diff` on `test_hybrid_source.py`, `test_logger.py`,
  and `test_naked_eye_source.py` shows pure additions — every hunk is a `+` block appended at
  end-of-file; no existing assertion line was touched. `logger.py`'s diff confirms `main()`'s
  original no-`--console` path now calls `_build_sources(..., emit_mode="on_change")` where it
  previously constructed the same two classes with no `emit_mode` argument at all — since the
  field defaults to `"on_change"`, this is behavior-preserving by construction, not just by test
  coverage. `hybrid_source.py`'s debounce check became
  `if self.emit_mode == "on_change" and distinct_texts == self._last_emitted_texts` — for the
  default mode this is identical to the prior unconditional check.
- **Naked-eye acquisition-cap vs. emission-cap split**, read directly in
  `naked_eye_source.py:195-311`: `_acquired_ids` is a genuinely separate field from
  `_previously_visible_ids`, both reset together on a telemetry gap. `_acquire_on_change` is
  the original logic verbatim (renamed into a method, `_previously_visible_ids` still updated
  unconditionally on every currently-visible id, capped-out objects still never retried). 
  `_acquire_every_poll` grows `_acquired_ids` by at most `NAKED_EYE_MAX_NEW_PER_POLL`
  not-yet-acquired objects per poll (nearest-first, same throttle), intersects with
  currently-visible each poll (so a departed object re-acquires on return), and emits every
  object currently in the acquired set regardless of when it joined — so an already-acquired
  object is never re-capped for repeat emission. This matches the plan's "gates entry into the
  acquired set, not emission" instruction exactly.
- **`test_every_poll_mode_progressively_acquires_capped_overflow`** genuinely exercises two
  sequential polls with 5 simultaneous candidates against a cap of 3: first poll asserts
  `len(first) == NAKED_EYE_MAX_NEW_PER_POLL` (3), second poll (all 5 still visible) asserts
  `len(second) == 5` — 3 re-emitting plus 2 newly acquired. This is a real multi-poll
  progressive-acquisition test, not a single-poll check with a misleading name.
- **The plan's core acceptance test**, `test_emission_pipeline.py`, drives a real
  `NakedEyePerceptionSource` (monkeypatched geometry/LOS the same way
  `test_naked_eye_source.py` does) through 61 polls at 1 Hz into a real
  `belief.contacts.ContactStore.ingest`/`tick`, then asserts
  `certainty_of(contact, 60.0) == "observed"` under `every_poll` and `!= "observed"` under
  `on_change` for the same stationary, continuously-visible object over the same window. This is
  exactly the wiring the plan calls for — belief-layer decay is what's being tested, not just
  that Observations keep being emitted.
- **`--console` scope.** `ConsolePerceptionRunner.run_once()` does ingest+tick and print one
  `t_sim=... contacts=N observations=N` line — no REPL, no command parsing, nothing beyond the
  minimal wiring the plan describes for this stage. Confirmed no `belief/tools.py` or
  `belief/console.py` exist yet (`ls body-layer/src/belief/`: `__init__.py`,
  `association_over_time.py`, `contacts.py`, `decay.py`, `events.py`, `percept.py` — unchanged
  file list since Stage 2's last commit, `git log -1 -- body-layer/src/belief/` still points at
  `2626c6c`). Stage 3 touched zero files under `belief/`.
- **Type discipline.** `Literal["on_change", "every_poll"]` is declared once per source
  (`hybrid_source.py`, `naked_eye_source.py`) and once in `logger.py`'s `_build_sources` — no
  bare `str` parameter anywhere in the call chain. Verified mypy actually catches a typo: edited
  `logger.py`'s `emit_mode="every_poll"` call site to `"every_pol"` and reran
  `mypy src` — it failed with `Argument "emit_mode" to "_build_sources" has incompatible type
  "Literal['every_pol']"`; restored the file and reran clean. Not a decorative annotation.
- **Module boundary.** Only `hybrid_source.py`, `naked_eye_source.py`, `logger.py`, their tests,
  and `body-layer/CLAUDE.md` changed this stage (confirmed via per-commit `git diff --stat` for
  all four Stage 3 commits). No `belief/tools.py`, `belief/console.py`, `decay.py`, `events.py`,
  `percept.py`, or `association_over_time.py` touched.
- **`body-layer/CLAUDE.md`** gained a "Running the live logger" `--console` paragraph and a
  `src/belief/` Structure bullet (the latter backfilling a gap the Stage 0/1 review had already
  flagged as optional/deferred) plus a `src/logger.py` bullet update — matches what actually
  landed, no aspirational claims about Stage 4 functionality.

Ran all verification myself rather than trusting the log:

- `ruff format --check src tests`: pass (35 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from `body-layer/`): pass, no issues in 18 source files
- `pytest tests -q`: **163 passed** — confirmed via `git diff --stat` that Stage 3 added exactly
  12 new `test_*` functions (2 in `test_hybrid_source.py`, 4 in `test_naked_eye_source.py`, 4 in
  `test_logger.py`, 2 in `test_emission_pipeline.py`) and 0 existing test bodies were modified;
  163 = 151 (Stage 2's confirmed count) + 12.
- `git status`: clean working tree. `git log` shows exactly the four claimed Stage 3 commits
  (`c019787`, `dc93004`, `206aff8`, plus the implementation-log commit `ac7f7a0`) on top of
  Stage 2's last commit, all on this branch. The unrelated `todo/todo.md` modification noted in
  implementation.md as "outside this stage's scope" is correctly not part of any Stage 3 commit
  and the working tree is clean, so it isn't a loose end here.

### Required Fixes

None.

### Optional Refinements

- **`hybrid_source.py`'s `_last_emitted_texts` is still updated unconditionally under
  `every_poll`**, per the implementer's own note, even though `every_poll` never reads it. Dead
  writes, not a correctness issue — harmless and cheap to leave as-is rather than special-casing
  the assignment for a mode that doesn't consume it (optional, no action needed).
- **`_acquire_on_change`/`_acquire_every_poll` duplicate the "sort by range, slice to cap" shape**
  (`naked_eye_source.py:262-266` and `:293-297`). Both are short and the underlying set semantics
  genuinely differ (as documented at length in the module docstring and implementation.md), so
  extracting a shared helper would likely cost more clarity than it saves at this size — worth
  revisiting only if a third acquisition mode is ever added (optional).

### Verdict

APPROVED

### Review Confidence

Full read — read the complete diffs for `hybrid_source.py`, `naked_eye_source.py`, `logger.py`,
`body-layer/CLAUDE.md`, and all four Stage 3 test files (`test_hybrid_source.py`,
`test_naked_eye_source.py`, `test_logger.py`, `test_emission_pipeline.py` in full, the latter
being the plan's core acceptance test). Ran format/lint/type/test myself and independently
verified the mypy typing claim by introducing and reverting a real typo rather than trusting the
report. Did not re-verify Stage -1/0/1/2 files, per the existing approvals above.

---

## Review: Stage 4 (Tools and console)

Branch: `feature/pb2-contact-memory`. Reviewed against `plans/pb2-contact-memory/plan.md`'s
"Stage 4 — Tools and console" section and `plans/pb2-contact-memory/implementation.md`'s Stage 4
entry. Stages -1 through 3 already reviewed/approved above and not re-reviewed here.

### Review Summary

Read `tools.py`, `console.py`, `contacts.py`'s diff, `logger.py`'s full diff, `test_tools.py`,
`test_console.py` and `test_logger.py`'s diff in full; ran verification commands myself.

- **`facts` absent-not-empty invariant.** `test_describe_contact_facts_never_carry_bl3_scope_keys`
  genuinely checks `key not in facts` for `semantic`/`general_area`/`relative_now`/`clock` (the
  plan text says `urgency` lives in `phrasing_hints`, not `facts` — checked separately below).
  Reading `tools.py`'s `_contact_facts` directly: the dict literal assigns exactly `id`,
  `classification`, `certainty`, `visible`, `last_seen_ago_s`, `position`, `sources`, `attention`,
  plus a conditional `attention_source` — none of the BL-3/BL-4 keys are assigned at all, not
  conditionally omitted. `_contact_phrasing_hints` returns only `{"certainty": ...}` — `urgency`
  is never assigned anywhere in the file. Confirmed absence is structural (no key ever created),
  not a runtime filter that could regress.
- **Identity invariant.** `grep -n "derived_world_position\|object_id" src/belief/tools.py
  src/belief/console.py src/belief/contacts.py` returns nothing. `tools.py`'s docstring reword
  (flagged by the implementer as tripping Stage 1's grep-based structural test) reads as a genuine
  reword — it now says "`Observation`'s DCS ground-truth position field" instead of naming the
  field, and the code itself only ever reads `Contact.last_position`, which `contacts.py`
  populates via `association_over_time.implied_position(percept)` (a `Percept`, never an
  `Observation`). `test_tools.py`/`test_console.py`'s own fixtures plant
  `derived_world_position=(99999.0, 99999.0)` and assert the returned `position` is *not* that
  value — a real leak would fail these tests, not just the grep. No bypass.
- **§3.3 tool shape.** `ContactResult` (`{facts, summary, phrasing_hints}`) matches §3.4's
  documented triple; the four real tools' signatures are reasonable, provisional interpretations
  consistent with how prior stages handled the same doc-gap (no literal §3.3 schema exists to
  check against character-for-character).
- **Console is logic-free.** Read `console.py` end to end: every one of `contacts`/`show`/
  `history`/`find`/`watch`/`unwatch`/`stats` parses its argument and calls straight into a
  `belief.tools` function, formatting the returned dict/list into strings. No certainty
  computation, gating, or filtering decision happens in `console.py` — the `filter` string is
  validated against a literal tuple and passed through to `tools.get_contacts`, not applied
  locally. `test_console_module_contains_no_belief_logic` mechanically pins this (every public
  `tools.py` function name must appear in `console.py`'s source; `console.py` must not import
  `belief.decay`/`belief.association_over_time`) — verified this actually runs and passes.
- **`watch_contact`/`unwatch_contact`/`get_stats` reasoning holds.** Both watch functions are
  three-line find-and-set operations; `get_stats` is three `len()` calls. None compute certainty,
  gate contacts, or make a policy judgment — they're bookkeeping, consistent with the plan's "no
  console-only logic" constraint and the implementer's own justification for adding them to
  `tools.py` rather than `console.py`.
- **`Attention` stays a bare enum.** `contacts.py`'s diff is purely additive: `Attention =
  Literal["normal", "watch"]` plus two new `Contact` fields, both defaulted. No cooldown, no
  relevance scoring, no BL-4 policy — `watch_contact`/`unwatch_contact` in `tools.py` just set/
  clear the two fields. No encroachment on BL-4's scope.
- **Scripted-session acceptance test.** `test_scripted_console_session_over_a_replayed_stream`
  ingests a real `Observation`, ticks the store, and runs `contacts` → `show` → `watch` →
  `contacts watched` → (tick past `LOST_THRESHOLD_S`) → `contacts visible` → `history` → `find` →
  `unwatch` → `stats`, asserting exact transcript strings at each step (e.g. `"CONTACT_1: Ural
  truck, observed, currently visible."`, the lost-state summary, the `CONTACT_LOST` event kind,
  final `stats` line). This checks actual output text, not just "doesn't crash."
- **Backward compatibility.** `git diff` on `contacts.py` shows the two new `Contact` fields both
  defaulted (`attention: Attention = "normal"`, `attention_source: str | None = None`); `git diff`
  on pre-existing test files (`test_logger.py`, `test_hybrid_source.py`, `test_naked_eye_source.py`,
  `test_contacts.py`) between the Stage 3 approval commit and HEAD shows only `test_logger.py`
  changed, and that diff is a pure 19-line addition (one new test function) — zero existing
  assertion lines touched anywhere.
- **`logger.py`'s REPL threading.** Read `_run_poll_loop`/`_run_console_repl`/`main()` in full.
  The poll thread mutates `ContactStore` (`ingest`/`tick`) while the REPL thread reads it via
  `belief.tools` functions with no lock. Checked whether this is a plausible crash/corruption risk
  rather than theoretical: `ContactStore.contacts`/`.observations`/`.events` are all properties
  that return a **fresh copy** (`list(self._contacts.values())`, `dict(self._observations)`,
  `list(self._events)`) — under CPython's GIL, these copy constructors run as a single atomic C
  call with no bytecode-boundary yield point, so a concurrent `dict`/`list` mutation on the poll
  thread cannot produce a "changed size during iteration" exception or a torn read. The one
  cross-thread mutation of a *shared object* is `watch_contact`/`unwatch_contact` setting
  `contact.attention`/`.attention_source` on the main thread while the poll thread's `record()`/
  `tick()` may concurrently set `last_position`/`last_class_raw`/`sighting_spans`/
  `last_emitted_certainty` on the same `Contact` — disjoint attribute sets, and individual
  attribute assignment is itself atomic under the GIL, so at worst a command sees a `Contact`
  mid-update (e.g. `last_position` updated but `last_seen_sim` not yet) — a stale-read hazard, not
  a crash or corruption. Given this is an explicitly single-operator debug console over an
  in-memory store (per `logger.py`'s own docstring, "not a claim of hardened concurrency"), this
  is a defensible best-effort posture, not a required fix.

Ran all verification myself:

- `ruff format --check src tests`: pass (39 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from `body-layer/`): pass, no issues in 20 source files
- `pytest tests -q`: **196 passed** — consistent with the claimed 163 + 33 new, 0 modified (only
  `test_logger.py` among pre-existing test files changed, and only by one added test)
- `git status`: clean. `git log` shows the four claimed Stage 4 commits (`3642599`, `56faed5`,
  `9ef3aa0`, `17a916f`) cleanly on top of Stage 3's approval commit.

### Required Fixes

None.

### Optional Refinements

- **No dedicated `urgency`-absence test.** `test_describe_contact_facts_never_carry_bl3_scope_keys`
  checks `semantic`/`general_area`/`relative_now`/`clock` in `facts`, but `urgency`'s absence
  (correctly, in `phrasing_hints`) is only verified by reading `tools.py`'s source, not pinned by
  a test the way the other four keys are. Low risk since `_contact_phrasing_hints` is a three-line
  function unlikely to grow accidentally, but a one-line `assert "urgency" not in
  result["phrasing_hints"]` would close the gap symmetrically with the `facts` test (optional).
- **REPL threading has no lock**, as discussed above — defensible for this stage's single-operator
  debug-console posture, but worth a one-line note (already present in `logger.py`'s docstring) if
  `--console` is ever used with more than one concurrent reader/writer. No action needed now.

### Verdict

APPROVED

### Review Confidence

Full read — read `tools.py`, `console.py`, `contacts.py`'s diff, `logger.py`'s full diff and
docstring, `test_tools.py` and `test_console.py` in full, and `test_logger.py`'s diff. Verified
the absent-not-empty and identity invariants directly against source and fixture data (not just
trusting the implementer's self-report), and reasoned through the REPL's thread-safety from
`ContactStore`'s actual property implementations rather than accepting the "best-effort" framing
on faith. Ran format/lint/type/test myself. Did not re-verify Stage -1/0/1/2/3 files, per the
existing approvals above.

---

## Review: Stage 5 (Cross-channel fusion validation)

Branch: `feature/pb2-contact-memory`. Reviewed against `plans/pb2-contact-memory/plan.md`'s
"Stage 5 — Cross-channel fusion validation" section, `plans/pb2-contact-memory/implementation.md`'s
Stage 5 entry, and the new `todo/todo.md` backlog item ("BL-2's certainty/classification fusion
is last-writer-wins, not quality-weighted"). Stages -1 through 4 already reviewed/approved above
and not re-reviewed here. This is a test-only stage — one new file,
`body-layer/tests/test_cross_channel_fusion.py` (6 tests), no production code touched.

### Review Summary

Read the full new test file, `belief/decay.py`, `belief/contacts.py`,
`belief/association_over_time.py`, and `perception/object_model.py`'s `profile_for` in full; ran
a live interpreter check against the actual keyword table; ran verification commands myself.

- **Same-poll fusion test** (`test_same_poll_both_channels_on_same_object_merge_into_one_contact`)
  genuinely feeds a scope `Observation` (`SOURCE_PETROVICH_DETECTION_ASSOCIATED`, free-text
  `"Ural truck"`) and a naked-eye `Observation` (`SOURCE_NAKED_EYE_VISUAL_FILTERED`, bucketed
  `"OP_TRUCK"`) through one `ContactStore.ingest()` call. `ContactStore.ingest` (`contacts.py:186-
  204`) processes the batch in a loop, gating each observation against the *current* `_contacts`
  dict — since the first observation's own contact-creation mutates that dict in place, the
  second is genuinely gated against a real contact, not a coincidence of loose radii (both are at
  bearing 0°/range 1000m, so `distance_m == 0 <= gate_radius`). `contributing_observation_ids`
  and `_sources_in` (reading through `store.observations`, keyed correctly per `contacts.py`'s
  actual field names) confirm both sources landed on one contact.
- **Adjacent-poll fusion test** — two genuinely separate `ingest()` calls at `t_sim=0.0` and
  `t_sim=1.0`. Read `association_over_time.passes_gate`/`spatial_gate_radius_m` directly: the
  second call's gate radius is computed against the *existing* contact's `last_seen_sim` (set by
  the first `record()` call), so this exercises the real elapsed-time growth term
  (`GATE_GROWTH_RATE_MPS * 1.0` = 20m of margin on top of ~277-300m of source uncertainty) — no
  scaffolding pre-assigns a contact id; `Contact.from_percept`/`_new_contact_id` mint it exactly
  as production code does.
- **"Certainty reflects the better observation" finding — verified independently, not taken on
  faith.** Read `decay.certainty_of` (`decay.py:97-109`): it is a pure function of
  `now_sim - contact.last_seen_sim` with no reference to `uncertainty_radius_m`, observation
  source, or any per-observation quality signal — confirms the test's/backlog's claim exactly.
  Read `Contact.record` (`contacts.py:97-106`): `self.last_class_raw = percept.classification_raw`
  unconditionally overwrites on every call, with no comparison against the previous value —
  confirms `last_class_raw` is genuinely last-writer-wins, not merely under-tested. The test
  itself (`test_certainty_tracks_recency_of_last_contributing_observation_not_quality`) asserts
  real, falsifiable behavior at two points (`certainty_of(..., 40.0) == "estimated"` before the
  second observation, `== "observed"` and `last_class_raw == "Ural truck"` after it) — this is an
  honest test of current behavior, not one relaxed to pass regardless of input; flipping either
  assertion's expected value would fail against the real code. The backlog entry
  (`todo/todo.md:255`) accurately states the mechanism (`certainty_of` is recency-only,
  `last_class_raw` is last-writer-wins) and the concrete failure mode (a later, wider-uncertainty
  observation fully resets certainty over an earlier, tighter one) without overstating it as a bug
  — it correctly frames Stage 2's pure-recency ladder as a documented placeholder design, per that
  stage's own review, not a defect introduced here.
- **Negative case geometry.** `test_two_distinct_nearby_objects_stay_two_contacts` separates the
  two objects by bearing (0° vs 90°, both range 1000m) rather than range, ~1414m apart. Verified
  against `association_over_time.uncertainty_radius_m`/`spatial_gate_radius_m` directly: the
  gating percept here is the second (naked-eye) observation, whose own range-derived uncertainty
  at range=1000m (~277m, matches the figure the test cites from
  `test_association_over_time.py`'s sibling test) plus zero elapsed-time growth (same poll) is
  nowhere near the ~1414m separation — the negative case genuinely fails the gate, not by
  coincidence. The implementer's reported false-merge discovery with a range-separated fixture
  (1000m vs 1600m along the same bearing) is consistent with the formula: naked-eye's down-range
  term is a *range-bucket width*, which grows with range, so a range-separated pair can end up
  with a *larger* gate radius than the physical gap between them at longer range — this reflects a
  genuine, correct understanding of the gate formula, not a fixture hack. On whether the
  range-growing-uncertainty behavior itself needs a comment: it doesn't — wider uncertainty at
  longer range for a fixed angular/range-bucket quantisation is physically correct behavior
  (`association_over_time.py`'s module docstring already documents the down-range term as
  "the width of the `OP_D*` range bucket the observation fell into"), not a gap. No action needed.
- **Weak cross-channel class compatibility test.** `profile_for("SA-3 launcher")` was independently
  run against the real keyword table (not assumed): confirmed it resolves to `DEFAULT_OP_CLASS`
  (`"OP_GROUPSOMETHING"`) — the table keys the real DCS S-125 SA-3 system on `"s-125"` (a real
  `object_type` substring, per `object_model.py:105-113`'s own comment on the reporting-name vs.
  NATO-shorthand rework), which `"sa-3 launcher"` does not contain, so no pass-1 or pass-2 match
  occurs and the fallback correctly fires. `_op_class_of` (`association_over_time.py:170-181`)
  treats a `DEFAULT_OP_CLASS` result as `None`, i.e. `unknown`, exactly as the test's docstring
  claims. The test proves the three-valued gate's designed behavior (unknown never blocks a
  spatially-valid merge) against a real weak-vocabulary case — this is Stage 1's design being
  validated, not re-implemented; no new gating logic was added.
- **Scope discipline.** `git show --stat e927899` (the Stage 5 commit) touches exactly
  `.claude/agent-memory/implementer/MEMORY.md`, one new agent-memory file,
  `body-layer/tests/test_cross_channel_fusion.py`, and `plans/pb2-contact-memory/implementation.md`
  — zero changes under `belief/` or `perception/`. `git diff e927899^ e927899 --stat -- body-layer/
  tests` shows only the one new test file; no pre-existing test file was modified.
- **Identity invariant.** Every fixture's `_observation()` helper populates
  `derived_world_position` (a real, non-optional `Observation` field, so its presence is
  structurally required, not a leak by itself) with an arbitrary marker value
  (`x=99999.0, z=99999.0`). Checked every assertion in the file: none reference
  `derived_world_position` or any object-id field — assertions only check `len(store.contacts)`,
  `contributing_observation_ids`, `_sources_in(...)` (which reads `Observation.source`, not
  position), `certainty_of(...)`, and `last_class_raw`. No gating expectation or identity
  assertion is smuggling in ground-truth data.

Ran all verification myself:

- `ruff format --check src tests`: pass (40 files already formatted)
- `ruff check src tests`: pass
- `mypy src` (from `body-layer/`): pass, no issues in 20 source files (unchanged file count,
  consistent with "test-only stage")
- `pytest tests -q`: **202 passed** — consistent with the claimed 196 + 6 new, 0 modified; `git
  diff e927899^ e927899 --stat -- body-layer/tests` confirms no pre-existing test file changed
- `git status`: clean working tree. `git log` shows `e927899` ("Add Stage 5 cross-channel fusion
  validation tests (PB-2)") followed by `b894769` (two `todo/todo.md` backlog additions,
  correctly outside this stage's scope per the task brief) — both committed, nothing pending.

### Required Fixes

None.

### Optional Refinements

None. This stage is deliberately minimal (validation-only, no production code) and the one
finding it surfaced is already correctly captured as a backlog item rather than papered over.

### Verdict

APPROVED

PB-2/BL-2's fixture-testable work is now complete. Stage 6 (live acceptance) requires a real DCS
sortie and is user-only — nothing further for Reviewer to do on this branch until that runs.

### Review Confidence

Full read — read the complete new test file, `belief/decay.py`, `belief/contacts.py`, and
`belief/association_over_time.py` in full, and independently ran `object_model.profile_for("SA-3
launcher")` against the live keyword table rather than trusting the implementer's or the test
docstring's claim. Verified the commit's file scope directly via `git show --stat` and `git diff
--stat`. Ran format/lint/type/test myself. Did not re-verify Stage -1/0/1/2/3/4 files, per the
existing approvals above.
