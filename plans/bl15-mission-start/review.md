### Review Summary

Reviewed BL-15 Stages 1-2 as implemented on `feature/bl15-mission-start`
(commits `77dcb5b2`, `bbd09fa8`, `a99bd5a9`, diff base `eab86662`; `b1a72d7c`
is docs only). Scope: aircraft-layer mission-start signal
(Hook `onSimulationStart` -> loopback UDP 7799 -> `MissionStartCache` ->
`GET /mission_start/latest`), body-layer `_check_for_new_mission` +
`reset_for_new_mission()` across `ContactStore`, `TaskStore`,
`MissionMemory`, both perception sources, `ConsolePerceptionRunner`,
`CrewConsole`. Stages 3-4 (theatre switching, live acceptance) are correctly
untouched, as instructed, and Decision 1's loud-refusal mode and Decision 5's
per-mission log files are correctly deferred to a later batch (stage1-decisions.md
says so explicitly) — their absence here is not a defect.

Read the full diff (not spot-checked), ran every check myself from inside
each subproject's own venv (using the main checkout's `.venv` binaries, since
the worktree has none of its own — see note at the end), and mutation-tested
the one completeness test the implementer's own notes flagged as load-bearing.

**Completeness against `BL-B68`'s table**: every item in that table is
covered. `attack_run_state`, `optic_state`, `scan_plan` (on
`ConsolePerceptionRunner`), `mission_phase_tracker`, `enrichment`/
`WorldEnrichmentCache`, `attitude_history`, `optic`/`_last_look_direction` all
reset via `ConsolePerceptionRunner.reset_for_new_mission`'s re-invoked
`__init__` (they are not in its preserve-set); both perception sources'
dedup maps (`_object_id_to_last_observation_id`, `_previously_seen_at`,
`_acquired_at`, `_last_emitted_texts`, `_observation_count`, `_dropped_count`)
are cleared explicitly since their constructors can't be wholesale
re-invoked. I checked the one thing the plan explicitly carves out as *not*
needing a reset — `NakedEyePerceptionSource.scan_plan`/`optic`/`sight_cone`/
`suppressed_until_sim` — by tracing `_apply_active_gaze` (`logger.py`
~L1059-1086): all four are unconditionally overwritten from
`runner.scan_plan`/`runner.optic` on every `run_once()` call, which always
runs immediately after `_check_for_new_mission` in both poll loops. The
claim holds; this is not a gap.

**Shared-object ordering (b)**: `runner.store is crew_console.store` and
`runner.tasks is crew_console.tasks` both before and after a reset, because
`ContactStore.reset_for_new_mission`/`TaskStore.reset_for_new_mission`
mutate the existing object in place (`self.__init__()`) rather than
replacing it, and `_reset_mission_state` resets those shared objects exactly
once, before `runner.reset_for_new_mission`/`crew_console.
reset_for_new_mission` pass the same (already-reset) references straight
through. `CrewConsole`'s own completeness test asserts this by identity, not
just equality. The real wiring test
(`test_crew_text_poll_loop_resets_belief_on_mission_restart`) drives the
actual poll loop and confirms both `runner.tasks` and
`crew_console.commands_handled` reset together.

**`init=False` trap (c)**: confirmed correctly handled for
`ConsolePerceptionRunner._last_look_direction` (the one field of this shape
on either `ConsolePerceptionRunner` or `CrewConsole` — I independently
re-checked every `field(...)` declaration on both classes and found no
second instance). I mutation-tested this directly: removing the explicit
`self._last_look_direction = None` line restores the trap, and
`test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest`
fails immediately with a clear message naming the exact field. Confirms the
completeness test is load-bearing, not decorative.

**Would the completeness tests catch a newly-added, unreset field (d)?**
Yes for the five classes using the re-invoked-`__init__` pattern
(`ContactStore`, `TaskStore`, `MissionMemory`'s state minus the sink,
`ConsolePerceptionRunner`, `CrewConsole`) — `dataclasses.fields()`/`vars()`
enumeration at test time means a new field is automatically poisoned and
checked, with no hand-maintained list to fall out of sync. **No** for
`NakedEyePerceptionSource`/`HybridPerceptionSource` — their reset tests
(`test_reset_for_new_mission_clears_dedup_and_counter_state`) assert a fixed,
hand-written list of attribute names; a new dedup/counter field added to
either class later would silently leak across a mission restart with no
test failure. This is explicitly acknowledged in the plan ("no cheap 'fresh
instance' to diff against" — the constructors require live collaborators
that can't be re-synthesized for a throwaway comparison instance) and is not
a scope deviation, but it is the one place this plan's own safety property
("a newly added field resets by default") does not actually hold. See
Optional Refinements.

**Thread safety (e)**: no new hazard. The `--console` REPL
(`belief.console.Console`) and the `--crew-text` crew console
(`belief.crew_console.CrewConsole`) both hold `store`/`tasks` by reference
from before any reset; since reset mutates those objects in place rather
than replacing them, no stale reference is created. Concurrent read/write
between the poll thread and the REPL thread on `ContactStore`'s internal
dicts is a pre-existing property of this codebase (not introduced or
worsened by this change) — `ContactStore.ingest`/`tick` were never
synchronized against the REPL thread before this feature either.

**First-poll no-op (f)**: correct and tested four ways
(`test_check_for_new_mission_does_nothing_on_first_poll_even_with_sequence_present`,
plus the sequence-change/unchanged/empty-cache cases). `None` is used as the
"never checked" sentinel, distinct from "sequence 0 seen," matching Decision
2 ("yes" to "no reset on first poll").

**Schema rejection (g)**: `MissionStartEvent.from_dict` rejects missing
`sequence`, non-int `sequence`, `bool`-as-`int`, and non-string `theatre`,
mirroring `F10CommandEvent.from_dict` exactly as the security plan review's
carried-forward requirement asked. `MissionStartReceiver._handle_datagram`
drops non-JSON, non-dict, and schema-rejected payloads at debug level without
crashing the receive loop. Verified by reading `test_mission_start_schema.py`
(8 cases) and `test_mission_start_receiver.py`.

**Decisions 1 and 5 (next batch)**: confirmed absent from this diff, as
instructed — no loud-refusal-mode code, no per-mission log file rolling.
Correctly out of scope here.

**Checks** (run myself, from inside each subproject, using the main
checkout's `.venv` since the worktree has none of its own — see note below):
- aircraft-layer: `ruff format --check src tests` / `ruff check src tests` —
  pass. `mypy --strict src` (run via `cd aircraft-layer && mypy src`) —
  pass, 25 source files. `pytest tests -q` — 374 passed.
  `luac5.1 -p` on the new Hook script — pass.
- body-layer: `ruff format --check src tests` / `ruff check src tests` —
  pass. `mypy --strict src` — pass, 68 source files. `pytest tests -q` —
  2179 passed, 4 xfailed (pre-existing, unrelated to this change — confirmed
  by name, all concern unrelated modules).
- A whole-subproject `ruff format --check .`/`ruff check .` on both
  subprojects (not scoped to `src`/`tests`) fails, but only on two
  pre-existing, untouched `research/*.py`/`research/*.md` files (one each in
  aircraft-layer and body-layer) — confirmed by diffing the touched-file
  list against the failures; neither file is in this feature's diff. Not
  this feature's problem, not flagged as a required fix.

### Required Fixes

None.

### Optional Refinements

- **`NakedEyePerceptionSource.reset_for_new_mission`/
  `HybridPerceptionSource.reset_for_new_mission` have no completeness
  guarantee against a future added field** (see "(d)" above) — their tests
  assert a fixed list of attribute names rather than enumerating the
  dataclass's actual fields. A cheaper partial fix than "diff against a
  fresh instance" (which the plan correctly rules out, since the
  constructors require live collaborators): a test that enumerates
  `dataclasses.fields()` on each class and asserts every field name is
  accounted for by one of three buckets — the constructor-required/preserved
  set, the explicit per-poll-overwritten set (`scan_plan`/`optic`/
  `sight_cone`/`suppressed_until_sim`/`live_los_coverage`), or the
  explicit dedup/counter set `reset_for_new_mission` clears. A field
  matching none of the three fails the test by construction, without
  needing a throwaway "fresh" instance. Worth doing before this becomes the
  next `BL-B68`-shaped gap, but not blocking — the plan already named this
  tradeoff and it is symmetric with the costs it was traded against.
- **`LiveLosCoverage` (`NakedEyePerceptionSource.live_los_coverage`) is not
  reset and not mentioned anywhere in the plan or `BL-B68`'s table.** On
  inspection this looks like a deliberate omission rather than a gap — its
  own docstring describes it as "an always-on regression guard... for the
  lifetime of the source," summed and logged once at end-of-run
  (`_log_live_los_coverage_summary`), not pilot-facing belief state — so
  carrying it across a mission restart is arguably correct (it is a coverage
  metric about the terrain model, not about the current mission). Flagging
  only because it is the one piece of `NakedEyePerceptionSource` state the
  diff is silent on; if it is meant to be per-mission (e.g. a debrief tool
  wants per-sortie coverage numbers once Stage 3's theatre switching can
  change the underlying model mid-run), it will need the same treatment that
  dedup/counter state got.

### Verdict

APPROVED

### Review Confidence

Full read — read every changed file in the diff, including all touched
tests across both subprojects, both `ROADMAP/` entries, the security plan
review, and the user's own decisions. Ran format/lint/type/test myself in
both subprojects (not trusting the implementer's own report) and
mutation-tested the one load-bearing completeness test to confirm it
actually fails when the mechanism it guards is removed.

**One environment note, not a scope gap**: this worktree was created with no
`.venv` in either subproject (git worktrees don't carry gitignored
directories). I ran every check using the main checkout's
`<subproject>/.venv/bin/<tool>` binaries invoked from inside this worktree's
subproject directories (`cd <worktree>/aircraft-layer && /Users/sg/Code/
DCS-petrobrain/aircraft-layer/.venv/bin/mypy src`, same pattern for
body-layer) — `mypy`'s CWD-only config discovery still resolves correctly
this way since the config file is read from the CWD, not from the
interpreter's own location. Results matched the implementer's own reported
counts exactly.

---

## Batch 2

Reviewed BL-15's second implementation batch on `feature/bl15-mission-start`:
commits `593c206e`, `cf4b7d3c`, `1265abac`, `6cd8c409`, diff base `97b76dec`
(this file's own Batch 1 approval). Scope: (A) runtime theatre switching with
the user's revised loud-refusal mode (`stage1-decisions.md` decision 1
REVISED, 2026-10-19), (B) per-mission log re-roll (decision 5), (C)
strengthened field-coverage completeness tests for the two perception
sources (Batch 1's own optional refinement 1).

Branch address verified first: `git rev-parse HEAD` landed at `89ca6c2a`
(ancestor of the named tip), tree clean, `git merge --ff-only
6cd8c409f2d8b6cc8cf391bb2c9cc2f69d53232c` fast-forwarded cleanly. All five
named input documents present and read in full.

**Read the full diff** (12 files, ~1730 insertions across the four commits),
ran every check myself from inside each subproject's own venv (main
checkout's `.venv` binaries, same reason as Batch 1 — this worktree carries
no `.venv` of its own), and mutation-tested three separate load-bearing
mechanisms rather than one, since this batch touches three independent
hazard classes (refusal dispatch, security ordering, stale closures).

### (a) Refusal mode matches the user's words, and the command-path hunt

`WORLD_MODEL_NOT_LOADED_REFUSAL = "system error, world model not loaded"` —
the user's own wording, verbatim, declared once as a literal rather than a
template (so voice/text/overlay all say exactly the same words). Checked at
the top of all three production entry points (`handle_command`, `handle_line`,
`handle_transcript`) via a shared `_refusal_response` helper repeated at each
call site, correctly — there is no single dispatcher all three already funnel
through (confirmed by reading each: F10/voice-act reach `handle_command`
directly, typed/fallthrough-voice reach `handle_line` directly, voice itself
enters `handle_transcript`), so "repeated at three call sites" is the actual
single source of truth here, not a missed consolidation.

**Mutation-tested**: removed the refusal check from `handle_command` alone —
`test_refused_handle_command_returns_the_fixed_refusal_line` and
`test_refused_does_not_end_silence_or_increment_commands_handled` both failed
immediately (`commands_handled` went 1→2 when it should have stayed at 1).
Confirms the gate is load-bearing at each of the three sites independently,
not just logically present. Restored before continuing.

Old store dropped not kept: `_enter_refusal_mode` closes
`runner.world_model_conn` and sets it `None`, clears `runner.enrichment`,
empties `runner.sources` (stops perception outright, not a degraded run
against a missing store). A later successful switch clears `crew_console.
refused` (`_maybe_switch_theatre`'s success path, last statement before the
info log). Confirmed by `test_maybe_switch_theatre_succeeds_rebuilds_sources_
and_clears_refusal`.

**One command path genuinely worth tracing further, not missed but worth
naming explicitly**: `_enter_refusal_mode`/`_maybe_switch_theatre` are called
from *both* poll loops (`_run_console_poll_loop` and
`_run_crew_text_poll_loop`), and `--console`'s path passes `crew_console=None`
— correctly a no-op for the refusal-setting line, since `--console` has no
`CrewConsole` surface to refuse commands on at all (documented in both the
function's own docstring and `body-layer/CLAUDE.md`). This is the right
design, not a gap — `--console` is a debug harness with no production command
surface — but it does mean "every player command on every surface" is
accurate only for the two surfaces that have one (crew-text, F10, voice all
funnel through `CrewConsole`); `--console`'s own REPL commands are explicitly
out of that guarantee by design, and this is stated plainly rather than
glossed over.

**The brain-layer reply path and proactive callouts — found a real gap, but
one the current call graph happens to mask, not an active defect.** I traced
every call that can speak without being a direct player command:
`crew_console.drain_events` (lifecycle-event callouts) and `crew_console.
drain_brain` (asynchronous brain-layer replies) are both called
unconditionally every poll in `_run_crew_text_poll_loop`, after
`runner.run_once()`, with **no `self.refused` check anywhere in either
method**. Neither is one of the three gated entry points, and neither needed
to be *named* as one in the brief, but the review question stands: could
either still speak stale belief while refused?

Traced it through: `_enter_refusal_mode` is reachable *only* from
`_maybe_switch_theatre`, which is called *only* from `_check_for_new_mission`
*after* `_reset_mission_state` has already run that same call — so by
construction, every time `crew_console.refused` becomes `True`, `ContactStore`
is already empty, `TaskStore` is already empty, and `CrewConsole._pending_
escalations` has already been cleared (not preserved by `reset_for_new_
mission`). With `runner.sources = []` for the rest of refusal mode, no new
observations are ever ingested, so `ContactStore.tick()` iterates over nothing
every subsequent poll — no `CONTACT_LOST`/`CONTACT_DETECTED`/range-crossing
events are ever generated for `drain_events` to speak. A brain reply that
lands late for an utterance from before the reset finds `_pending_escalations.
pop(reply.utterance_id, None)` returns `None` (discarded silently,
`_handle_brain_reply`'s own documented "superseded client-side" case) — no
stale brain-layer speech either. I confirmed this by reading, not by running
a scenario that doesn't exist yet in the test suite.

**This correctness is real today but entirely incidental — it depends on an
invariant (refusal mode is only ever entered immediately after a full
reset) that is enforced by call-graph shape in two different functions
across two files, asserted nowhere, and tested nowhere.** If a future change
adds a second path into `_enter_refusal_mode` that does not go through
`_reset_mission_state` first (e.g., a startup-time degrade path, or a health
check that re-validates the store mid-mission without a sequence change),
`drain_events`/`drain_brain` would resume speaking about whatever belief was
standing at that moment with no gate stopping them — silently, exactly the
failure class this project's reviewer memory and `CLAUDE.md`'s "verify state,
not the account of it" both warn about. This is the kind of thing `/invariant-
check`-style mechanical enforcement exists for, and there is none here.

**Required fix**: add either (preferred, cheap, structural rather than
incidental) an explicit `if self.refused: return []` guard at the top of
`drain_events` and `drain_brain` — the same shape `_refusal_response` already
gives the three command entry points, just without a spoken line since
nothing asked a question — or, at minimum, a test that documents and locks in
the current invariant (e.g., construct a `CrewConsole` with `refused=True`
and a *non-empty* store/pending-escalation state directly, bypassing the
reset-always-precedes-refusal call graph, and assert `drain_events`/
`drain_brain` produce nothing). The guard is the better fix: it makes "no
proactive speech while refused" a property of `CrewConsole` itself rather
than a consequence of how two other functions in `logger.py` happen to call
each other today, and costs four lines.

### (b) `theatre: null` keeps current store

Confirmed in `_maybe_switch_theatre`: `event_theatre is None` returns
immediately with an info log, no store change, no refusal — matches decision
1 REVISED's carry-forward ("a `None` theatre has always meant 'unknown,' not
'mismatch'" — the function's own docstring states this was never revised by
the loud-refusal decision, correctly, since the earlier-approved Batch 1
behaviour for this exact case is untouched by Batch 2). Consistent.

### (c) `THEATRE_PROJECTIONS` membership check ordering (security Mode-2 requirement)

Read the implemented code directly (`logger.py:1744` onward): the membership
check (`if event_theatre not in THEATRE_PROJECTIONS`) runs and returns
(entering refusal mode) *before* `candidate_db = world_model_dir /
f"{event_theatre.lower()}-full.sqlite"` is ever constructed and before
`open_world_model` is ever called — exactly the ordering the security plan
review's carried-forward Mode-2 requirement asked for, matching `main()`'s
own startup guard precedent. This is a code-order property, not something a
behavioural test can distinguish from "check after" (both end in refusal for
an unbuilt-store scenario), so I verified it by reading the control flow
directly rather than attempting to mutation-test it — the right instrument
for an ordering guarantee is reading the order, not running the program.

### (d) Old connection closed only after new is live

Confirmed in `_maybe_switch_theatre`'s success path: `old_conn =
runner.world_model_conn` is captured, `new_conn`/`runner.sources` are built
and assigned to `runner.world_model_conn`/`runner.theatre` first, and only
then `if old_conn is not None: old_conn.close()`. All on the poll thread
(`_check_for_new_mission` is called synchronously inside each poll loop's own
`while` body, no new thread spawned for the switch) — both `_run_console_poll_
loop` and `_run_crew_text_poll_loop` confirmed identical in this respect.

### (e) Stale-closure hunt

All four closures the implementer's notes name were verified fixed by
reading, not just by the notes' own claim:

- `_mark_here_fn`/`_mark_target_fn` — now read `runner.theatre` live
  (`assert runner.theatre is not None` at call time), not a bound parameter.
  **Mutation-tested indirectly via the existing test**:
  `test_mark_here_fn_reads_runner_theatre_live_across_a_switch` asserts the
  recorded mark's lat/lon actually changes after mutating `runner.theatre`
  between two calls to the *same* closure instance — a genuine behavioural
  proof, not a structural one.
- `crew_console.speech_log_sink` (`_speech_log_sink(belief_truth_writer,
  runner)`) — re-built in `_reroll_run_logs` over the new writer.
  **Mutation-tested directly**: removed the rebuild line from
  `_reroll_run_logs` and reran `tests/test_run_log_reroll.py` —
  `test_reroll_closes_the_old_belief_truth_writer_and_rewires_crew_console_
  sink` failed with `ValueError: I/O operation on closed file`, reproducing
  exactly the silent-failure-turned-exception the implementer's notes
  describe. Restored before continuing.
- `_mission_memory_step`'s `theatre` argument — both poll loops now pass
  `runner.theatre` (with `assert runner.theatre is not None`) instead of the
  closed-over parameter. Confirmed by reading both call sites.
- `runner.enrichment` — cleared in both `_maybe_switch_theatre` (success
  path, forces a fresh rebuild against the new connection) and
  `_enter_refusal_mode` (failure path, so a later recovery never inherits a
  reference into an already-closed connection). Confirmed by reading.

**Hunted for anything else capturing `theatre`/`conn`/a writer by value**,
beyond what the notes name: grepped every `theatre: str` parameter and every
closure-returning function in `logger.py`. `_run_console_poll_loop`'s own
`theatre: str` parameter is used only once, to open the initial connection/
sources at thread start — never read again inside that function's `while`
loop body (confirmed by grep: the local name appears nowhere else in the
function), so it is not a live stale-closure hazard the way the four above
were; the loop's own `_mission_memory_step` call already reads `runner.
theatre` (identical fix to the crew-text loop, confirmed by reading). The one
deliberately-unfixed case is `_run_console_repl`'s own `repl_conn`/
`repl_enrichment`, built once from the `theatre`/`world_model_db` `main()`
passed at construction and never refreshed — correctly left alone and
explicitly flagged in the implementation notes and `body-layer/CLAUDE.md`,
since `--console` has no `CrewConsole`/refusal surface and widening this
REPL's own connection-rebuild logic is out of this batch's stated scope. No
unaccounted-for closure found.

### (f) Log re-roll (decision 5)

All five per-run logs covered, three distinct re-wiring shapes handled
correctly for the right reasons (open-file-handle closes for the two writers
that hold one, plain-field reassignment for the three that don't,
`mission_memory._sink` specifically overwritten after `reset_for_new_
mission`'s own preserve-then-overwrite sequencing). Reroll only fires when
`_check_for_new_mission` reports an actual reset, so the *first* mission of a
process keeps `main()`'s original stamped names (confirmed: `_reroll_
run_logs` is called conditionally on `_check_for_new_mission`'s return value,
never unconditionally per poll). Everything runs synchronously on the poll
thread, no new thread. `--console`'s own no-`CrewConsole` guard confirmed via
`test_reroll_console_mode_skips_speech_log_with_crew_console_none` (passing
`crew_console=None` with a non-`None` `speech_log_base` must not raise, and
doesn't).

**Mutation-tested** (see (e) above — the belief-truth-writer rewire is the
one of the five with the sharpest failure mode, write-to-closed-file, and it
reproduced on cue).

### (g) Tests fail when the behaviour is broken

Three independent mutations, all reproducing the exact failure mode the
implementation notes describe, all restored afterward:

1. Removed `handle_command`'s refusal check → 2 of 6 refusal tests failed
   (commands_handled changed when it shouldn't have).
2. Removed the `speech_log_sink` rebuild from `_reroll_run_logs` → the
   targeted reroll test failed with `ValueError: I/O operation on closed
   file`.
3. (By reading rather than mutation, per (c) above — ordering is not a
   mutation-testable property with the current test shapes.)

### Checks (run myself, from inside each subproject's own venv)

**body-layer/**
- `ruff format --check src tests` — pass (155 files already formatted).
- `ruff check src tests` — pass.
- `mypy --strict` (`cd body-layer && mypy src`) — pass, 68 source files.
- `pytest tests -q` — 2209 passed, 4 xfailed (same 4 pre-existing xfails as
  Batch 1, unrelated to this change).

**aircraft-layer/**: not touched by this batch, no checks run (confirmed by
the diff stat — all 12 changed files are under `body-layer/` or `plans/`).

### Completeness against the field-coverage refinement (C)

`NakedEyePerceptionSource`/`HybridPerceptionSource` now each carry a
`test_reset_for_new_mission_field_coverage_is_complete` test that enumerates
`dataclasses.fields()` at test time and asserts the full field set equals the
union of three explicit, named buckets (preserved / per-poll-overwritten /
explicitly reset for naked-eye; preserved / reset for hybrid, which has no
per-poll-overwritten field). This closes exactly the gap Batch 1's own
Optional Refinement named — a field added later and placed in none of the
three buckets now fails this test by construction (plain set-equality
assertion, no mutation test needed to confirm — the mechanism is simple
enough to verify by inspection). `live_los_coverage` is now in the explicitly-
reset bucket (reversing Batch 1's "process-lifetime regression guard"
reading), consistent with decision 5's per-mission log rollover reasoning —
a coverage counter spanning several missions no longer corresponds to any
single log file once logs roll per mission.

### Required Fixes

- **Add an explicit `self.refused` guard to `CrewConsole.drain_events` and
  `CrewConsole.drain_brain`** (or, at minimum, a test asserting they produce
  nothing while refused against a non-empty store/pending-escalation state
  constructed directly, not via the reset-always-precedes-refusal call path)
  — see "(a)" above. Today's correctness is real but incidental: it depends
  on `_enter_refusal_mode` only ever being reached immediately after
  `_reset_mission_state` has already emptied belief/tasks/pending
  escalations, an invariant enforced by nothing but the current shape of two
  functions' call graph across `logger.py`, asserted nowhere, and would fail
  silently (not loudly — no test, no crash, just Petrovich quietly speaking
  about contacts that should not exist) if a future change ever reaches
  refusal mode by a path that does not go through a full reset first. The
  guard is four lines and makes "no proactive speech while refused" a
  property of `CrewConsole` rather than a coincidence of call order.

### Optional Refinements

- **No wiring-level test exercises `_run_console_poll_loop`'s own theatre-
  switch/refusal path end-to-end**, only `_run_crew_text_poll_loop`'s (via
  `test_crew_text_poll_loop_resets_belief_on_mission_restart_and_switches_
  theatre` and its no-store twin). The unit-level `_maybe_switch_theatre`/
  `_check_for_new_mission` tests do cover `crew_console=None` explicitly
  (`test_enter_refusal_mode_is_a_true_no_op_for_console_mode`), so the
  underlying function logic is proven; what's missing is the same
  real-thread proof the crew-text path has. Low priority — `--console` is a
  debug harness, not the pilot-facing path, and the function-level coverage
  already demonstrates correctness for the `crew_console=None` branch
  specifically.
- **`fired_on_tracker` (both poll loops) is not reset on a mission restart**
  and is not mentioned anywhere in this batch or `BL-B68`'s completeness
  table. Out of this batch's actual scope (it predates BL-15 and Batch 1's
  review already approved the reset mechanism's coverage against that
  table), but worth a note for whoever next extends the reset-completeness
  table, since it is exactly the kind of per-mission-scoped state the
  pattern exists to catch.

### Verdict

APPROVED WITH MINOR FIXES

The one Required Fix is a robustness/structural gap, not an observed defect
— no test today exercises the call path that would expose it, and the
current call graph genuinely prevents it from firing. It is required rather
than optional because it is exactly the property the dispatching brief asked
to have verified (proactive callouts speaking stale belief while refused),
the fix is small, and leaving the invariant implicit is the known failure
shape this project's own process guidance (`CLAUDE.md`'s "verify state, not
the account of it"; the reviewer's "verify by mutation, per entry" memory
guidance) exists to prevent. Everything else in this batch — the refusal
dispatch at all three entry points, the security ordering, the four
confirmed stale-closure fixes, the log re-roll's five distinct shapes, and
the field-coverage completeness refinement — is correct, tested, and
mutation-confirmed where mutation-testing is the right instrument.

### Review Confidence

Full read — read every changed file across all four commits (not
spot-checked), ran format/lint/type/test myself in body-layer's own venv
(not trusting the implementer's reported counts, though they matched
exactly), and mutation-tested three independent mechanisms (refusal
dispatch at a specific entry point, the belief-truth-writer stale-closure
fix, and confirmed the theatre-live-read fix behaviourally via the existing
lat/lon-change test) rather than reading the diff and trusting the
implementer's own account of what each test proves. The one gap found
(drain_events/drain_brain) was found by tracing the actual call graph that
makes refusal mode reachable, not by pattern-matching on what the brief
asked me to check — the brief asked the right question and the call graph
happened to (currently) answer it safely, which is itself the finding worth
recording.

## Batch 3 — review of the fix commit (`ea5f77fc`, diff base `465c4611`)

Reviews the Batch 2 required fix (`CrewConsole.drain_events`/`drain_brain`
guard against `self.refused`) and the related `fired_on_tracker` reset
(Batch 2's optional refinement, promoted to done in this batch). Diff scope:
`body-layer/src/belief/crew_console.py`, `body-layer/src/logger.py`,
`body-layer/src/mission_memory/admission.py`, plus their tests — read in
full via `git diff 465c4611 ea5f77fc`, not the whole-batch diff.

### The `drain_events`/`drain_brain` guard

Both methods now open with `if self.refused: return []` (or its
`drain_brain`-specific equivalent below), placed **after** the one step
that has to run regardless of `refused` and **before** every step that
speaks or mutates state on the model's behalf — read directly, not taken on
the implementer's account:

- `drain_events`: `self.scheduler.tick(...)` runs unconditionally first,
  then the guard, then `_print`. Confirmed by reading `CalloutScheduler.
  tick` (`belief/callouts.py`) start to finish: the only state it mutates
  on a successful pick is its own `busy_until_sim`/`_consumed`/
  `_last_spoken_sim`/`_last_spoken_signature`, plus (via `route_event` ->
  `acknowledge_event`) marking the chosen `Event` acknowledged in the
  store — no `_print`, no network call, no reference into `CrewConsole`
  itself. So "the event really is consumed out of the store, not left to
  surface stale once refusal clears" is correct exactly as claimed.
- `drain_brain`: `self.brain_client.poll_replies()` is drained inside the
  guard's own branch (not skipped), each reply is popped from
  `_pending_escalations`/discarded from `_stand_by_spoken_for` directly,
  and `_handle_brain_reply`/`_speak_stand_by_if_due` are never called.
  Read `_handle_brain_reply`: it calls `self._print` unconditionally and,
  via `_handle_brain_pick`/`_handle_brain_confirm`, can call `self._act`
  (mutates `_pending_confirmation`/tasks/attention) — both are real side
  effects a discarded return value would not undo, so bypassing the
  method entirely (rather than calling it and dropping its result) is the
  only way to actually stop them, exactly the distinction the Batch 2
  review's "(a)" asked for.

**All three command entry points** (`handle_line`, `handle_command`, and
the third call site at `crew_console.py:3325`) already routed through
`_refusal_response` before this batch, confirmed unchanged by this diff —
so with this fix, every path that can produce speech now checks `refused`:
the three command entry points via `_refusal_response`, and the two
proactive-drain entry points via their own direct guard. Grepped
`self._print(` and `self._act(` across the file against every caller's
guard rather than trusting the two names the dispatching brief listed, to
make sure no fifth entry point was missed — none found.

**Mutation-tested both guards by removal myself** (not trusting the
implementer's reported failure), restoring after each:
- Removing `drain_events`'s guard: both of its four new tests fail,
  `AssertionError: assert ['BMP-2.'] == []` — a real, unacknowledged event
  built directly on the store (bypassing the reset-always-precedes-refusal
  call graph) gets spoken when the guard is gone.
- Removing `drain_brain`'s guard: both of its tests fail,
  `AssertionError: assert ['Unable, no such command.'] == []` — same shape.

Confirmed the four new tests do not merely assert the returned list is
empty while quietly letting a side effect through: `test_refused_drain_
brain_speaks_nothing_against_a_pending_escalation` also asserts
`overlay.pushed == []` and `console._pending_confirmation is None`, which
is exactly the side-effect class `_handle_brain_reply`/`_act` could leave
behind if the guard called the method and discarded its result instead of
bypassing it — the test would not have caught a reversion to that shape by
checking the return value alone.

### `scheduler.tick` running while refused — one minor, bounded side effect

Checked specifically for this per the dispatching brief, beyond what either
required fix was scoped to catch. `CalloutScheduler.tick` sets `self.
busy_until_sim = now_sim + estimate_speech_duration_s(text) +
INTER_UTTERANCE_GAP_S` on every successful pick (`callouts.py:1358-1360`),
**unconditionally** — including while `drain_events` is about to discard
that same `text` because `refused` is `True`. The scheduler has no way to
know its caller is about to throw the result away, so it occupies itself
for the estimated speech duration of a line nobody hears.

**Consequence, traced through to its end rather than left as a theoretical
gap:** because `tick`'s own guard (`if now_sim < self.busy_until_sim:
return []`) fires *before* any candidate is scored, a second `drain_events`
call made while still busy returns `[]` immediately without touching the
store at all — so events are discarded from the store at roughly real
speech cadence while refused (one phantom "speak" per
`estimate_speech_duration_s` + `INTER_UTTERANCE_GAP_S`), not instantly.
This matches the implementer's own stated intent ("consumed... rather than
piling up") and does not misbehave — it just paces the discard. The only
observable cost is a bounded one: if refusal clears at a `now_sim` still
inside a phantom `busy_until_sim` window set moments before clearing, the
very next real `drain_events` call can return `[]` for up to
`estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S` (a few seconds
at current, explicitly-uncalibrated constants) even though nothing is
actually being said — a short, silent gap immediately after refusal
clears, not a wrong or stale line. Does not compound across polls (each
busy window is independent and self-expires) and is invisible from the
pilot's seat as anything other than "the first callout after a theatre
recovery landed a couple of seconds later than it might have." Not a
required fix — logging it as an optional refinement below so it is not
rediscovered as a mystery later.

### `fired_on_tracker.reset_for_new_mission()`

`FiredOnTracker` has no live-collaborator fields (`_scanned_event_count:
int = 0`, `_last_write_sim: dict = field(default_factory=dict)`), so
`self.__init__()` gives the same genuine, mutation-verified completeness
guarantee `ContactStore`/`TaskStore` already have — not the weaker
hand-written-list form this project's own reviewer memory
(`project_reset_pattern_completeness_test_gap_classes.md`) flags for
`NakedEyePerceptionSource`/`HybridPerceptionSource`. Confirmed by reading
the dataclass definition directly, not assumed from the method's name.

**Wiring confirmed at both call sites**, by reading rather than by the
implementation notes' claim: `_reset_mission_state` gained a `fired_on_
tracker: FiredOnTracker | None = None` parameter (default preserves every
pre-existing 3-argument call site, including the direct unit-test calls in
`test_mission_start_reset.py`), `_check_for_new_mission` gained the same
parameter and passes it straight through, and both `_run_console_poll_loop`
and `_run_crew_text_poll_loop` already construct one `FiredOnTracker()` per
loop (pre-existing, for their own `_mission_memory_step` calls) and now
pass `fired_on_tracker=fired_on_tracker` into their `_check_for_new_mission`
call — grepped every occurrence of the name in `logger.py` to confirm both
loops, not just the one the implementation notes walked through in detail.

**Mutation-tested the wiring myself**: removed the `if fired_on_tracker is
not None: fired_on_tracker.reset_for_new_mission()` line from `_reset_
mission_state` — `test_reset_mission_state_resets_fired_on_tracker_when_
given` fails with `AssertionError: assert 500 == 0`, reproducing the stale-
index defect the method's own docstring describes. Restored; full suite
green again.

### Tests fail when the fix is removed

Four independent mutations, all confirmed by me (not read off the
implementer's account), all restored afterward:

1. `drain_events` guard removed -> both of its new tests fail
   (`['BMP-2.'] == []`).
2. `drain_brain` guard removed -> both of its new tests fail
   (`['Unable, no such command.'] == []`).
3. `fired_on_tracker` reset line removed from `_reset_mission_state` ->
   `test_reset_mission_state_resets_fired_on_tracker_when_given` fails
   (`500 == 0`).

### Checks (run myself, from inside body-layer's own venv)

- `ruff format --check src tests` — pass (155 files already formatted).
- `ruff check src tests` — pass.
- `mypy --strict` (`cd body-layer && .venv/bin/mypy src`) — pass, 68 source
  files.
- `pytest tests -q` — 2216 passed, 4 xfailed (same 4 pre-existing xfails;
  up from Batch 2's 2209 by exactly the 7 new tests this batch adds —
  4 for the guard, 3 for `fired_on_tracker`).

`aircraft-layer/`: not touched by this fix commit (confirmed by `git diff
465c4611 ea5f77fc --stat` — every changed file is under `body-layer/` or
`plans/`), no checks run.

### Required Fixes

None. The Batch 2 required fix is implemented as a structural guard on
`CrewConsole` itself (not a consequence of call-graph shape), mutation-
confirmed on both methods, and does not merely suppress the return value
while letting `_print`/`_act` side effects through — confirmed by reading
`_handle_brain_reply` and by the new tests' own side-effect assertions.

### Optional Refinements

- **`CalloutScheduler.tick`'s phantom `busy_until_sim` occupancy while
  refused** (see above) — bounded, self-expiring, and does not misbehave,
  but is worth a one-line docstring note on `drain_events` (or on `tick`
  itself) recording that a discarded pick still occupies the scheduler for
  its estimated speech duration, so a future reader investigating "why did
  the first callout after a theatre recovery land a couple seconds late"
  does not have to re-derive this from `callouts.py:1358`. Low priority —
  no incorrect speech results, only a bounded, silent delay.
- **`drain_brain`'s refused branch duplicates the `try`/`except Exception`
  around `poll_replies()`** that the non-refused branch also has, rather
  than factoring the poll-and-handle-failure step into one shared helper
  both branches call. The implementation notes' stated reason (the two
  branches do genuinely different things with the result) is sound, and
  the duplication is four lines, but a future change to the exception
  message or log level would need to remember to touch both copies. Purely
  cosmetic — not worth blocking on.

### Verdict

APPROVED

Both parts of this fix do exactly what Batch 2's review required and
nothing more: the guard is structural (a property of `CrewConsole`, not an
accident of call order), covers the side-effect-bearing path as well as
the return value, is mutation-confirmed on both methods by me directly,
and the related `fired_on_tracker` reset closes the optional refinement
Batch 2 flagged with the same completeness-test rigor the rest of this
feature's reset mechanism already has. One minor, bounded, self-expiring
side effect was found while checking beyond the brief's two named
mechanisms (`scheduler.tick`'s phantom occupancy) — logged as an optional
refinement, not a blocker, since it produces a short silence, never a
wrong or stale line.

### Review Confidence

Full read — read the scoped diff (`465c4611..ea5f77fc`) in full across all
three source files and both test files, not the whole-feature diff; ran
format/lint/type/test myself in body-layer's own venv rather than trusting
the implementation notes' reported counts (they matched: 2216 passed, 4
xfailed); mutation-tested all three mechanisms this batch touches (both
guards, the `fired_on_tracker` wiring) by removing each and watching the
specific test fail, then restoring. Went one step further than the
dispatching brief's two named checks and traced `CalloutScheduler.tick`'s
own side effects by reading the method in full, which is how the
phantom-occupancy finding above was found — not by pattern-matching on
what was asked, the same discipline Batch 2's review notes paid off with.
