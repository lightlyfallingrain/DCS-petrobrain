### Implementation Summary

Implemented Stages 1-4 of `plans/voice-command-completeness/plan.md` (Stage 5 explicitly out of
scope, per instruction). Wired the 20 previously-dead voice tokens (`report_all`,
`report_clock_1..12`, `report_bearing_*`, `report_bearing_deg`, `scan_bearing_deg`) into
`CrewConsole.handle_command` (renamed from `handle_f10_command`), added the numeric-bearing wire
fix in `audio-adapter`, and updated prose/roadmap.

Before starting: confirmed `plans/voice-command-completeness/plan.md`'s named test files against
the real tree (see "Notable Discoveries" — one file name was wrong) and grepped the modules being
touched for tests the plan didn't name (none found beyond the incorrect file reference).

### Files Changed

**body-layer**
- `src/belief/crew_console.py` — Stage 1: `handle_f10_command` → `handle_command`,
  `_F10_SCAN_REASON` → `_SCAN_COMMAND_REASON`, unknown-token branch now `logger.warning`s instead
  of silently returning `[]`, new `DISPATCHED_COMMAND_TOKENS` frozenset. Stage 2: `_handle_report`
  (the report-family dispatcher — read-only, no `AttentionArea`/task/gaze change), new dispatch
  tables `_CLOCK_REPORT_TOKENS`/`_CLOCK_REPORT_LABELS`/`_BEARING_REPORT_TOKENS`, `REPORT_MAX_GROUPS`
  constant. Stage 3: `_nearest_sector` (22.5° half-bucket quantisation onto the 8 compass
  `Sector`s), `scan_bearing_deg`/`report_bearing_deg` dispatch entries, `bearing_degrees` threaded
  through `handle_command`/`handle_transcript`/`_act_on_voice_decision`/`_describe_token_for_confirm`,
  `!voice` harness gained an optional trailing-integer bearing argument (peeled off the transcript's
  last word, so every pre-existing invocation is unaffected).
- `src/belief/speech.py` — `render_clear`, `render_no_view`, `render_report` (Stage 2).
- `src/belief/callouts.py` — extracted `group_facts` (the bucket+chain merge rule, now facts-only
  and generic via a `TypeVar` on `_chain_by_clock`) out of `group_candidates`, which is now a thin
  event→facts→`group_facts`→events wrapper (identity-mapped back via `id(facts)`, since
  `group_facts` never copies the dicts it reorganises). Added `report_priority` (facts-only sibling
  of `callout_priority`, drops the `-event.t_sim` term) and `CalloutScheduler.note_reply`
  (extends `busy_until_sim` via `max`, never preempts — contrast `note_urgent`, which resets).
- `src/belief/voice_commands.py` — `PendingConfirmation.bearing_degrees: int | None = None`.
- `src/logger.py` — `_poll_f10_commands`/`_poll_transcripts` call `handle_command`; `_poll_transcripts`
  validates and threads `bearing_degrees` from the wire (a wrong-typed value is skipped, matching
  the existing per-field validation posture). `--f10-commands` help text renamed.
- `body-layer/CLAUDE.md` — new "surface is commands, not F10 commands" framing paragraph after
  "What this is"; the `crew_console.py`/`voice_commands.py` Structure entries updated to describe
  the report families, bearing quantisation, `DISPATCHED_COMMAND_TOKENS`, and `note_reply`, and to
  stop claiming the 20 tokens are still a documented no-op.
- `body-layer/ROADMAP.md` — new Status entry for this milestone (Stages 1-4, unflown as of merge).

**audio-adapter**
- `src/transcript_queue.py` — `TranscriptEvent.bearing_degrees: int | None = None` + `to_dict` key
  (eight fields, not seven).
- `src/server.py` — `_handle_transcribe` passes `match.bearing_degrees` into the enqueued event.
- `src/vocabulary.py` — docstring-only note on `BEARING_RESOLUTION_DEG`: the 5° slot is a
  recognition checksum, independent of the later act-time quantisation onto compass sectors.

**Cross-cutting**
- `docs/concept/STATE_TRANSITIONS.md` — short addendum on the "Player commands" section noting the
  F10-primary framing has inverted (voice primary, F10 legacy transport).
- `todo/todo.md` — two new deferred items under "Cross-cutting / unscoped backlog": compass/absolute
  scans still not reaching `_active_gaze` (re-measured, not newly discovered), and the
  ownship-relative o'clock scan token family — both explicitly Stage 5 of this plan, sequenced
  together since the clean fix is the same `ScanPlan`-carries-legs generalisation for both.

### Tests Added

**body-layer**
- `tests/test_crew_console.py` — `DISPATCHED_COMMAND_TOKENS` completeness (every member returns
  non-empty or is `stop_talking`'s documented no-op); unknown-token warning; `report_all` clear/
  configured-contact/lost-contact-dropped/no-enrichment cases; `report_clock_3` clear and
  contact-match cases; `report_bearing_n`/`report_bearing_s` clear vs. rear-hemisphere refusal, and
  that a believed rear-hemisphere contact is still reported; `report_bearing_deg` quantisation
  (including the rear-hemisphere path) and no-bearing say-again; `scan_bearing_deg` quantised task
  registration and readback; `_nearest_sector` bucket boundaries; `_describe_token_for_confirm`
  sector-not-number wording for every new family; a confirm-band bearing round trip surviving
  "affirm" (the test that would fail if `PendingConfirmation.bearing_degrees` were removed); a
  reply extending `CalloutScheduler.busy_until_sim`.
- `tests/test_callouts.py` — `report_priority` ordering (mirrors the three `callout_priority`
  tests); `group_facts` chaining/non-chaining/no-relative_now-singleton; `group_candidates` proven a
  thin wrapper (still returns `Event`s, still chains); `note_reply` extends/never-shortens/extends-
  past-a-shorter-existing-budget.
- `tests/test_speech.py` — `render_clear` (bare vs. capitalized-directional), `render_no_view`
  (lowercase mid-sentence, contrasted explicitly with `render_clear`'s capitalization), `render_report`
  (join, and the truncation suffix).
- `tests/test_logger.py` — `_poll_transcripts` threading `bearing_degrees` through to
  `handle_transcript` (via a small recording double, since exercising the real dispatch needs a
  full `EnrichmentContext`/`TaskStore` that belongs to `test_crew_console.py`'s own tests) and
  skipping a wrong-typed `bearing_degrees`.

**audio-adapter**
- `tests/test_transcribe_api.py` — the `bearing_degrees` field now asserted in the round-trip
  test's field set; a new test posting a real "scan bearing three two zero" transcript through the
  real `command_matcher.match_transcript` path and asserting `bearing_degrees == 320` survives
  `POST /transcribe` → `GET /transcripts/poll` (the regression this stage exists to fix).

### Checks

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict, `PYTHONPATH=src:../world-model/src`): pass, no issues in 45 source files
- `pytest tests -q`: **1051 passed, 4 xfailed** (baseline 1016 passed / 4 xfailed — 35 new tests,
  no regressions)

**audio-adapter/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict): pass, no issues in 15 source files
- `pytest tests -q`: **179 passed, 1 skipped** (baseline 178 passed / 1 skipped — 1 new test, no
  regressions)

### Notable Discoveries

- **The plan named the wrong audio-adapter test file.** It says
  `audio-adapter/tests/test_transcript_queue.py`/`test_server.py` for the wire changes, but neither
  `TranscriptEvent` nor `POST /transcribe` is tested there — `test_server.py` only covers `/speak`/
  `/stop`. The real coverage lives in `audio-adapter/tests/test_transcribe_api.py`, confirmed by
  grep before writing anything. No file the plan named was missing entirely, unlike the two prior
  incidents this role's memory records (a phantom test name, and a file left off the list
  completely) — this was a real file, just named wrong, likely a stale reference to an earlier
  restructuring of that test suite.
- **`_terrain_aware_world_position`'s test-fixture stub ignores bearing/range entirely.** Every
  existing enrichment-based test in this codebase (`_enrichment_context` + `project_terrain_aware`
  monkeypatched to identity) reports a contact's `relative_now` from the *observing ownship's own
  position at the time of the contributing observation*, not from the percept's `bearing_deg`/
  `range_m` projected outward. This was not obvious from reading the source and cost real time to
  reverse-engineer empirically (a throwaway script in the scratchpad, deleted afterwards) before
  the report-family tests' expected clock/range values could be constructed correctly. Worth
  knowing for any future test needing a contact at a controlled bearing/range under this fixture:
  control it via `ownship_at_observation`'s x/z, not via the observation's own `bearing_deg`/
  `range_m` fields.
- **`DISPATCHED_COMMAND_TOKENS` intentionally excludes `wake_petrovich`/`cancel_nevermind`/
  `say_again`** — all three are handled above `handle_command` (per the module's own pre-existing
  docstring) and never reach it as a dispatched token at all. The set totals 38 of the vocabulary's
  41 tokens; the remaining 3 are those routing tokens, not a gap.
- **`note_reply` is called unconditionally on every non-urgent `_print` line**, including a line
  `CalloutScheduler.tick` itself just drained and already accounted for in its own
  `busy_until_sim` update. This is deliberately redundant rather than conditioned on the call site —
  `max()` makes the second call a no-op in that case — because the plan's own instruction is to call
  it from `_print`'s non-urgent path, not to special-case which callers of `_print` should skip it.

---

## Stage 5 (2026-09-23)

Implemented Stage 5 of `plans/voice-command-completeness/plan.md`: the ownship-relative o'clock
scan family (`scan_clock_1..12`) and the fix for compass scans never reaching gaze. Worked from
`feature/binocular-optic` (which already carried Stages 1-4, merged), branching
`feature/scan-clock-ownship-relative` off it.

Before starting: confirmed the plan's named test files exist and grepped
`commanded_sector`/`ScanPlan(` across `src`/`tests` for every existing call site that a `ScanPlan`
field change would touch (`test_optic_policy.py`, `test_detection_trace.py`,
`test_emission_pipeline.py`, `test_gaze.py`, `test_logger.py`) — all construct `ScanPlan` via
keyword arguments only, so adding a new keyword-only `commanded_legs` field with a default was
additive to every one of them; none needed rewriting.

### Design choice: additive field, not a full `RelativeSector` retirement

The plan's Decision 5 mandates "let `ScanPlan` carry legs directly" as the generalisation, but
leaves open exactly how. Two readings were possible: (a) retire `commanded_sector` entirely in
favour of always carrying legs, or (b) add a new, separate `commanded_legs` field alongside the
existing one. Went with (b): `commanded_sector: RelativeSector | None` is untouched for
`ahead`/`left`/`right`/`full` (same wedge table, same `_search_sweep`/label-table readers, zero
test rewrites), and the new `commanded_legs: tuple[int, ...] | None` field carries a bare o'clock
hour or a converted absolute-sector's legs. `gaze_at` picks `commanded_sector` over
`commanded_legs` over free scan, in that priority order — the two are mutually exclusive by
`__post_init__` construction, so this is not a real ambiguity, just a fixed tie-break. This reads
(b) as the more literal implementation of "rather than widening `RelativeSector`... `_SECTOR_LEGS`
generalises directly" — the existing four-sector machinery stays exactly as it was, and the new
mechanism is bolted on beside it rather than folding it in and re-deriving `_SECTOR_LEGS`'s four
entries as `commanded_legs` values too (which would have touched every existing `ScanPlan`
construction site and, per the plan's own "sync owner" note on Stage 1 having kept tests green
throughout, seemed like the wrong kind of churn for a stage explicitly scoped to new capability).

### `legs_within_wedge`: a new general helper, not a lookup table

The absolute→relative conversion (`logger._active_gaze` converting a compass `AttentionArea.sector`
into legs using current heading) needed a way to ask "which o'clock hours fall inside this
arbitrary wedge" — `_SECTOR_LEGS` only has four pre-baked answers for the four named sectors, none
of which is guaranteed to align with an arbitrary heading-rotated compass sector. Wrote
`perception.gaze.legs_within_wedge(center_azimuth_deg, half_width_deg)`: enumerates all 12 hours,
filters to those within `half_width_deg` via the existing `angular_delta_deg`, and orders by signed
offset from center ascending (a left-to-right sweep). This ordering is **not** guaranteed to match
`_SECTOR_LEGS`'s own near-center-first sweep order for an equivalent wedge (verified directly:
`legs_within_wedge(-60.0, 30.0) == (9, 10, 11)`, not `(11, 10, 9)` the way `_SECTOR_LEGS["left"]`
reads) — the two tables serve different callers (a commanded named sector vs. a converted absolute
one) and were never required to agree on sweep order, only on which hours qualify. Documented this
explicitly in the test that would otherwise look like a bug (`test_legs_within_wedge_matches_the_
left_sectors_own_legs_as_a_set`).

### `AttentionArea.relative_clock_hour`: a third directional field, not a `RelativeSector` value

`scan_clock_1` needs an ownship-relative, per-poll-reprojected `AttentionArea` the same way
`relative_sector` already gets one — but a single o'clock hour isn't a `RelativeSector`. Added
`relative_clock_hour: int | None = None` to `AttentionArea`, pairwise mutually exclusive with
`sector`/`relative_sector` (extended `ContactStore.add_area`'s existing two-way exclusivity check
into a three-way one, `belief.tools.scan_area` threads the new keyword through unchanged in shape).
`project_relative_area` gained the clock-hour branch, reusing `perception.gaze._gaze_for_clock_hour`
for the relative-center azimuth and `FOCUS_CONE_HALF_WIDTH_DEG` (15°) for the half-width — a single
o'clock hour's own gaze cone width, not a wider sector wedge.

### `logger._active_gaze` gained a `heading_true_deg` parameter, default `0.0`

Required for the absolute→relative conversion. Rather than making every call site pass a real
heading, defaulted it to `0.0` — every existing test that calls `_active_gaze`/`_apply_active_gaze`
directly only ever constructs `relative_sector`-based tasks (heading-independent), so none needed
updating. `run_once` passes `ownship.heading_true_deg` for real. New tests that exercise the
compass-conversion path pass `heading_true_deg` explicitly.

### `_search_sweep`/binocular search band: deliberately not extended

`_search_sweep` (the binocular search-pattern sweep) still gates on `commanded_sector is None`
alone — a bare o'clock hour or a converted compass scan gets no binocular search band, same as a
compass scan got none before this stage (it never reached `_active_gaze` at all). Extending the
search band to the new `commanded_legs` cases would need a half-width derivation with no obvious
correct answer for a single 30°-wide o'clock leg (a zero-or-near-zero half-width degenerates
`search_pattern` to a single look position, which may or may not be wanted) — left for a later
stage since the plan's own scope for Stage 5 is gaze, not binocular search. Documented as a
deliberate scope boundary in both `logger.py`'s docstring and the ROADMAP entry, not silently
dropped.

### Files Changed (Stage 5)

**body-layer**
- `src/perception/gaze.py` — `ScanPlan.commanded_legs: tuple[int, ...] | None`, generalised
  `__post_init__`/`gaze_at`; new `legs_within_wedge` helper.
- `src/belief/attention.py` — `AttentionArea.relative_clock_hour: int | None`; `project_relative_area`
  handles it.
- `src/belief/contacts.py` — `ContactStore.add_area` gains `relative_clock_hour`, three-way mutual
  exclusivity.
- `src/belief/tools.py` — `scan_area` threads `relative_clock_hour` through to `add_area`.
- `src/belief/crew_console.py` — `_CLOCK_SCAN_TOKENS`, `_handle_scan`'s new `relative_clock_hour`
  parameter, `handle_command`/`_describe_task_for_speech`/`_describe_token_for_confirm`/
  `DISPATCHED_COMMAND_TOKENS` all extended.
- `src/logger.py` — `_active_gaze` gains `heading_true_deg`, resolves `relative_clock_hour`/`sector`
  in addition to `relative_sector`; `run_once`'s call site updated; `_format_gaze_line` gains a
  `commanded_legs` branch; `_search_sweep` docstring notes the deliberate non-extension.
- `body-layer/CLAUDE.md`, `body-layer/ROADMAP.md`, `todo/todo.md` — prose/status updates, closing
  both deferred backlog items this stage resolves.
- Tests: `tests/test_gaze.py`, `tests/test_attention.py`, `tests/test_contacts.py`,
  `tests/test_logger.py`, `tests/test_crew_console.py`.

**audio-adapter**
- `src/vocabulary.py` — nine `scan_clock_1..12` tokens (`_SCAN_CLOCK_TOKENS`) added to
  `VOICE_ONLY_TOKENS`, one phrasing each in `PHRASES`.
- `tests/test_command_matcher.py` — `"scan one o'clock"` added to the exact-phrase-per-family case
  table, proving the new tokens are reachable through the real match pipeline, not just present in
  the vocabulary tables.

### Tests Added

**body-layer**
- `tests/test_gaze.py` — `ScanPlan` mutual-exclusivity/empty-legs validation; `commanded_legs`
  single-hour and multi-hour cycling (cross-checked against the equivalent `commanded_sector`
  plan); `fixed_look` still wins over `commanded_legs`; `legs_within_wedge` at dead-ahead, at the
  rear (`+-180` wraparound), matched against `left`'s own wedge as a set, and a full-circle sweep
  asserting no compass-sector half-width (45°) ever yields zero legs.
- `tests/test_attention.py` — `project_relative_area` rotating a `relative_clock_hour` area by
  heading, including the `360`-wraparound case (mirrors the existing `relative_sector` tests).
- `tests/test_contacts.py` — `add_area`'s three-way mutual exclusivity (`relative_sector` +
  `relative_clock_hour`, `sector` + `relative_clock_hour`), and accepting `relative_clock_hour`
  alone.
- `tests/test_logger.py` — `_active_gaze` resolving a `relative_clock_hour` task; the measured
  pre-existing defect reproduced directly (`_active_gaze` returning `FREE_SCAN_PLAN` for a
  compass-only task, pre-Stage-5 behaviour, as a documented regression marker); the compass→legs
  conversion at heading 0 and heading 90 (proving the conversion tracks current heading, not a
  frozen one); `_format_gaze_line`'s `commanded_legs` branch; and the stage's own required
  end-to-end test — `test_run_once_compass_scan_actually_changes_naked_eye_gaze` — asserting the
  `ScanPlan` actually assigned to `NakedEyePerceptionSource` after a `scan north` task, and that
  `gaze_at` on that plan produces a *different* `Gaze` than free scan would have at the same
  `t_sim`, not merely a differently-typed `ScanPlan` object.
- `tests/test_crew_console.py` — `scan_clock_1` task registration (`relative_clock_hour` set,
  `relative_sector`/`sector` both `None`), its readback wording, its cancel-readback wording
  (`_describe_task_for_speech`'s third branch), and its confirm-prompt wording
  (`_describe_token_for_confirm`). `DISPATCHED_COMMAND_TOKENS`'s existing completeness test covers
  all nine new tokens automatically (no per-token test needed there).

**audio-adapter**
- `tests/test_command_matcher.py` — `"scan one o'clock"` -> `scan_clock_1` added to
  `test_exact_phrase_hits_every_token_family`.

### Checks

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict, `PYTHONPATH=src:../world-model/src`): pass, no issues in 45 source files
- `pytest tests -q`: **1076 passed, 4 xfailed** (baseline 1051 passed / 4 xfailed — 25 new tests, no
  regressions)

**audio-adapter/**
- `ruff check src tests`: pass
- `mypy src`: pass, no issues in 15 source files
- `pytest tests -q`: **179 passed, 1 skipped** (baseline 179 passed / 1 skipped — no new test
  functions added, one new case folded into an existing parametrised-by-dict test, no regressions)

### Notable Discoveries

- **The nine new tokens are genuinely unbenched.** No recordings of `scan_clock_1..12` exist in
  this project's corpus (`audio-adapter/research/2026-09-19-corpus-bench-results.md` predates
  them entirely) — their recognition accuracy on the user's own voice is unmeasured, same cost
  class the plan itself names for `cancel_scan`/`cancel_watch` before 2026-09-23. Flagged in
  `vocabulary.py`'s own comment so a future reader does not assume bench coverage that was never
  run.
- **`legs_within_wedge`'s sweep order genuinely diverges from `_SECTOR_LEGS`'s for an equivalent
  wedge** (see "Design choice" above) — worth knowing before reusing this helper anywhere that
  cares about sweep order rather than just membership, since it is easy to assume the two agree.
- **The binocular search band gap for the new commanded-legs cases is a real, if narrow, product
  gap**: a player scanning `1 o'clock` or a compass direction gets no glassing sweep the way
  `ahead`/`left`/`right`/`full` already do. Left open deliberately (see "Design choice" above) —
  worth a follow-on stage if the user wants it.

### 2026-09-23 — Closing the review's Optional Refinements

`plans/voice-command-completeness/review.md`'s milestone was **APPROVED with no required
fixes**; this pass closes its four Optional Refinements. No behaviour change except item 3's
decision (documented, no code semantics changed there either — a comment only).

1. **End-to-end test for `_handle_report`'s multi-contact grouping/truncation**
   (`test_report_all_groups_and_truncates_multiple_contacts`, `test_crew_console.py`). Four
   distinct classification types (`BMP-2`/`T-72`/`BTR-70`/`ZSU-23-4`), each due east at a
   different range (1/2/3/4 km) so each forms its own singleton `group_facts` bucket — four
   groups, capped at `REPORT_MAX_GROUPS` (3), ordered nearest-first, with a trailing "And more."
   Reproduces the reviewer's own throwaway-script scenario as a pinned regression test; passed
   first try against the real dispatch path, confirming the review's by-hand verification.
2. **Wrap-case test for the absolute→relative conversion**
   (`test_active_gaze_compass_conversion_handles_the_360_0_wrap`, `test_logger.py`). A commanded
   "scan north" resolved at heading 350°/0°/10° all yield the identical `(11, 12, 1)` legs —
   confirms no discontinuity at the 360°/0° wrap, mirroring the reviewer's own hand-verification
   of `legs_within_wedge` but through `_active_gaze` and pinned as a regression.
3. **`ScanPlan.__post_init__`'s missing `fixed_look`/`commanded_sector`/`commanded_legs`
   exclusivity — decided NOT to tighten.** Added a comment on the field/`__post_init__` boundary
   in `gaze.py` explaining the decision rather than a `ValueError`: `fixed_look` exists so
   binoculars can override a commanded scan, and a future glass phase remembering what was
   commanded underneath the stare (so the pre-binocular scan resumes rather than falling back to
   free scan once binoculars come down) is a plausible legitimate use of both fields set at once
   — `gaze_at`'s existing tie-break already resolves that combination correctly with no code
   change needed. Tightening now would have to be reversed the moment such a caller appears, for
   no safety this class currently lacks. No production path constructs the combination today
   (`fixed_look_at` always passes `commanded_sector=None`/leaves `commanded_legs` at its `None`
   default; `logger._apply_active_gaze` only ever replaces `resolved_plan` wholesale, never
   merges) — purely a documentation change, no test added, no behaviour touched.
4. **Boundary test at the cockpit mask's `rear_cutoff_deg` (130°)**
   (`test_report_bearing_s_just_inside_rear_cutoff_says_clear` /
   `..._just_past_rear_cutoff_cannot_see_it`, `test_crew_console.py`). Heading chosen so `S`'s
   sector center (180°) sits at exactly 129°/131° relative — pins the `>=` comparison in
   `_handle_report`'s `rear_hemisphere` check directly, at the one boundary the two pre-existing
   tests (dead-ahead, dead-astern) were nowhere near. Added `_enrichment_context_with_heading`,
   a small twin of the existing `_enrichment_context` fixture with a caller-controlled ownship
   heading — needed since no existing helper let a test place a sector center at an exact
   relative bearing.

#### Files Changed
- `body-layer/src/perception/gaze.py` — comment-only addition documenting refinement 3's decision
  on `ScanPlan.__post_init__`. No code/behaviour change.
- `body-layer/tests/test_crew_console.py` — three new tests (refinements 1 and 4) plus the
  `_enrichment_context_with_heading` fixture helper.
- `body-layer/tests/test_logger.py` — one new test (refinement 2).

#### Checks

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (strict, `PYTHONPATH=src:../world-model/src`): pass, no issues in 45 source files
- `pytest tests -q`: **1080 passed, 4 xfailed** (baseline 1076 passed / 4 xfailed — 4 new tests,
  no regressions)

**audio-adapter/** (untouched this pass, re-verified per task instructions)
- `ruff check src tests`: pass
- `mypy src`: pass, no issues in 15 source files
- `pytest tests -q`: **179 passed, 1 skipped** (matches baseline, unchanged)

#### Notable Discoveries
- All three tests requiring precise numeric predictions (the four-group report text, the 350/0/10
  wrap, and the 129°/131° boundary) passed on the first run against the real code — the review's
  own by-hand verification of these same three risk areas held up under an automated regression
  test, not just under one-time manual execution.
- The plan's test-impact expectations (per this role's own process step 1b) were treated as a
  hypothesis rather than trusted: `plans/voice-command-completeness/review.md` itself was read in
  full, and each of the two touched test files was checked for related existing coverage
  (`grep`'d for `_active_gaze`/`rear_cutoff`/`report_all` test names) before writing new tests, to
  avoid duplicating or contradicting an existing test. No mismatch found — the review's four
  items were the complete, correctly-scoped list for this pass.
