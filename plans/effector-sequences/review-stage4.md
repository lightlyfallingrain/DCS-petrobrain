# Review: BL-B90 Stage 4 — "readback by need" (option B)

Branch `feature/effector-sequences-stage4`, reviewed detached at `5da55c713d9186e4c905d9ecd6d2899e3513336a`
("BL-B90 Stage 4 (body-layer): one-shot reads, assumed_writes, polled.toml") — the worktree's own
branch (`1d02e5e1`) had diverged (not an ancestor either direction), so per dispatch instructions I
checked out the named tip detached rather than fast-forwarding. Tree was clean before and after.

Diff reviewed: `c231efda..5da55c71` (`ec02bcf4` aircraft-layer, `5da55c71` body-layer), 39 files,
+4786/-1498.

## Checks run

- `aircraft-layer`: `ruff format --check`, `ruff check`, `mypy src` (strict), `pytest -q` — all
  clean, 608 passed.
- `body-layer`: `ruff format --check`, `ruff check`, `mypy src` (strict), `pytest -q` — all clean,
  2650 passed, 4 xfailed.
- Mutation-verified live (not just read): `_effective_value`'s `>=`→`>` (E4) — red for the stated
  reason, restored, suite green. `math.isfinite` dropped from `AircraftLayerClient.read_args`
  (E9/security required change 1) — red for the stated reason (NaN/inf no longer raise), restored,
  suite green. `admit_read`'s per-frame cap removed (L6, flagged in `implementation.md` as not run
  live by the implementer) — red (`test_at_cap_not_admitted`, `test_mutation_no_cap` both fail),
  restored, suite green. Working tree confirmed clean after each restore.

## Required Fixes

1. **Decision 5 ("rewrite") was implemented as a translation/adapter layer inside the test fake,
   not the call-site rewrite the plan specifies and the user approved.** The plan's own text
   (`plan.md:1641-1647`) spells out what "rewrite" means here: *"the ~28 places in `test_logger.py`
   that set the fake's `cockpit_switch_state` (named booleans such as `{"ready_lamp": True}`) move
   to the arg-keyed shape (`{"watch_id": …, "args": {"960": 1.0}}`)"* — and explicitly rejects the
   alternative: *"a body-layer adapter that rebuilds the old named dict from the new map, exists
   only to spare test edits and leaves two readback shapes in the code."* The user's `"rewrite"`
   answered that exact framing.

   What shipped instead (`test_logger.py`): `_GROUND_TRUTH_RAW_ARG` (a name→arg table) plus
   `_merged_raw_args` (a translation function) let every pre-existing
   `cockpit_switch_state = {"ready_lamp": True, ...}` literal keep working unchanged against the
   new `read_args`/`get_watched_args_latest` fake methods. This is the rejected adapter, relocated
   from body-layer production code into the test fake — the stated flaw ("leaves two readback
   shapes in the code") still applies: the ~40 call sites still write the pre-Stage-4 named-boolean
   shape, translated internally rather than expressed in the shape the real wire now carries.
   `implementation.md` ("A deliberate implementation choice") discloses this honestly and explicitly
   asks the reviewer to judge — my judgment is that this is a narrower reading than the plan's own
   wording and the user's approval support, and it is also the exact shape of a decision this
   project's `AGENTS.md` Escalation Rules call out by name ("existing tests must be rewritten rather
   than extended"), which the plan cites for this stage.

   The same disclosure surfaces a second, real consequence: the continuous feed's confirmation
   (`watch_id` match) now takes one extra poll after `set_watch_args` is first called, where the old
   per-poll `cockpit_switch_state` readback was visible the same poll it was set. This is legitimate
   production behaviour inherent to the redesign (not a test artefact — the design's own
   `watch_args_due`/"not confirmed" WARNING machinery already accounts for a settling period), and
   every affected real-poll-loop test already tolerates it via its own polling-with-deadline loop, so
   I am not flagging the lag itself as a defect. It is only surfaced here because the translation
   layer's behaviour differs subtly from what rewritten call sites exercising `get_watched_args_latest`
   directly would have shown from the start — another reason the call sites should be rewritten
   rather than shimmed.

   **Fix**: rewrite the ~40 `test_logger.py` call sites (both the ~28 `cockpit_switch_state =
   {...}` assignments and the smaller number of only-named-key reads) to drive
   `get_watched_args_latest`/`set_watch_args`/`read_args` directly in the arg-keyed shape the real
   wire carries, and remove `_merged_raw_args` and `_GROUND_TRUTH_RAW_ARG`. What each test asserts
   should not change (the plan's own "the change is mechanical" framing), only the literal shape
   each test drives the fake with.

2. **`body-layer/CLAUDE.md`'s BL-B90 module-map paragraph is stale** — confirmed unchanged in this
   diff (`git diff` against it is empty). It still describes the pre-Stage-4 shape generically ("a
   row writes unless its own effector is already observed at the target value") with no mention of
   the one-shot-read-per-run/per-wait-row mechanism (S4.3), `assumed_writes`, `absolute_write`, the
   `polled.toml`/`REQUIRED_POLLED_ARGS` split (S4.4a), or `ArgReadBroker`/`read_args`/`watch_args` —
   all of which Stage 4 introduced and which a reader of this file would otherwise have no reason to
   expect. `aircraft-layer/CLAUDE.md`'s matching paragraph **was** correctly updated in this diff;
   this is the missing sibling update. Add a paragraph (or extend the existing one) describing the
   two readback classes, their consumers, and pointing at `plan.md`'s S4.1–S4.4a the way the
   aircraft-layer file now points at the plan's Stage 4 section.

Nothing else in the design or its tests needs to change before merge.

## Optional Refinements

- `plan.md` S4.5 says `test_export_lua_constants_parity.py` "also covers `MAX_READS_PER_FRAME`."
  What shipped is a correctly-written mutation test for the per-frame cap (`TestAdmitRead` in
  `test_watched_args_lua.py`, verified live above), but there is no Python-side twin constant for
  `MAX_READS_PER_FRAME` to check parity against (it is a pure Lua-side transport bound with no
  consumer on the Python side), so a "parity" test in that file would have nothing to compare
  against. The coverage that matters (the cap itself, and the mutation that would break it) exists
  and is correct; only the plan's filename reference doesn't quite match where the test landed.
  Worth a one-line note in the plan or `implementation.md` closing the loop, not a blocker.
- `implementation.md`'s own disclosure of the Decision 5 reading and the one-poll confirmation lag
  is exactly the kind of transparent flagging this project wants — calling that out as a positive,
  not a finding.

## Verdict

CHANGES REQUIRED

## Review Confidence

Full read of the Stage 4 spec (S4.1–S4.11), the security plan review, the explore-notes decisions,
and `implementation.md`'s own log; full diff read of `effector_engine.py`, `effector_registry.py`,
`sight_effector.py`, `aircraft_client.py`, `arg_read_broker.py`, `Export.lua`'s new command-socket
handling, `watched_args.py`, and the bookkeeping files (AC-B11, BL-B67, `aircraft-layer/CLAUDE.md`,
`triggers.md`, `polled.toml`). Three mutations run live against the actual checked-out source
(not just read), not just the implementer's own report. `test_logger.py`'s ~40 call sites were
read in diff form and cross-checked against the plan's explicit text, not independently re-derived
from scratch line by line.

## Re-review (2026-10-24)

Branch `feature/effector-sequences-stage4`, checked out detached at `b5fce2fdfbe6cce2d56a84dc9538947216e8a377`
("Review fixes: rewrite test_logger.py call sites, update BL-B90 doc") — the worktree's own branch
(`1d02e5e1`) had diverged, so per dispatch instructions I checked out the named tip detached. Tree
was clean before and after.

Diff reviewed: `4997764e..b5fce2fd` (the reviewed tip at `4997764e`'s own review commit to this
tip), 4 files: test_logger.py, body-layer/CLAUDE.md, plan.md, implementation.md. No production code
touched (`src/`, `dcs-export/` both empty in this diff) — confirmed by `git diff --name-only`
restricted to those paths.

### Fix 1: the adapter is gone, call sites rewritten

`_GROUND_TRUTH_RAW_ARG` and `_merged_raw_args` are both deleted; grepped the whole file for
`cockpit_switch_state`/`_merged_raw_args`/`_GROUND_TRUTH_RAW_ARG` — the one hit left
(line 914) is a historical comment ("the old `get_cockpit_switch_state_latest`'s `None` default"),
not a live reference. The fake's own field is now `raw_args: dict[str, float]`, string-arg-keyed
exactly as the real wire carries it, and every call site I diffed drives it directly
(`{"960": 1.0}`, `{"886": 0.0, "673": 0.0}`, etc.) — no named-boolean literal or translation
survives.

Verified the one outlier literal's dropped keys (`"t"`, `"received_wall_clock_s"`, `"observe_on"`,
`"weapons_armed"`) by hand against `git show 5da55c71:body-layer/tests/test_logger.py`'s old
`_merged_raw_args`: for that literal (`test_slew_trace_is_written_from_the_real_poll_loop`'s second
`cockpit_switch_state` assignment), the old translation produced `{886: 1.0, 673: 0.0, 898: 1.0}`
(`"t"`/`"received_wall_clock_s"` were never in `_GROUND_TRUTH_RAW_ARG` at all, so they never
reached `merged`). The new literal is `{"886": 1.0, "898": 1.0}` — 673 (`weapons_armed`, value
0.0) is dropped. Checked the test body itself (read in full, not skimmed): it asserts only on
OBSERV (886, via the `(7, 3002, ...)` writes) and the alignment lamp (898, via `sight_head.mode`);
arg 673 is never read back or asserted on anywhere in that test. The drop is correct — a dead
literal, not a weakened assertion.

Mutation spot-check (not just read): patched the fake's `get_watched_args_latest` to return
`"args": {}` unconditionally (discarding `self.raw_args`) and ran the three guidance-unit-lamp
tests (`test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop`,
`test_guidance_unit_ready_is_silent_on_a_warm_air_start_through_the_real_poll_loop`,
`test_guidance_unit_ready_speaks_again_after_a_power_cycle_through_the_real_poll_loop`) — all three
failed red for the stated reason (`sight_ready`/`crew_console.sight_ready` never became `True`,
since the continuous feed now always reports no args). Restored from a `cp` backup taken before
the mutation; confirmed by `shasum` that the restored file is byte-identical to the pre-mutation
tip. This closes the loop the plan's own wording was checking for: the rewritten call sites are
load-bearing on the real `raw_args`/`get_watched_args_latest` path, not vestigial.

**Verdict on Fix 1: resolved as specified.** The call sites drive the arg-keyed shape directly;
no adapter remains in any form.

### Fix 2: `body-layer/CLAUDE.md`'s BL-B90 paragraph

Read the diff and cross-checked each new claim against the code:

- One-shot reads at run start / after each wait row, `assumed_writes` engine-wide keyed by arg,
  `absolute_write` confirmed-shape-only — matches `effector_engine.py` (`EffectorRunState.
  assumed_writes`) and `effector_registry.py` (`_ABSOLUTE_WRITE_SHAPES = frozenset({"default_2_
  position_tumb"})`, `EffectorDef.absolute_write`).
- `polled.toml` + `REQUIRED_POLLED_ARGS` union, required-first ordering, 64-arg cap, bad-entry/
  missing-required-arg severity split — matches `sight_effector.REQUIRED_POLLED_ARGS` and
  `effector_registry.load_polled_config`/`PolledSet`.
- `EFFECTOR_CONDITION_READBACK_WAIT_S`'s "per snapshot" wording — checked the **rendered**
  `config/defaults.toml`, not the source comment: its first sentence reads "How long a run waits,
  per snapshot (Stage 4: once at run start, once again after each wait row), for `client.
  read_args` to succeed..." — matches.
- The now-corrected `sight_effector.py` bullet ("untouched by BL-B90" removed, replaced with the
  raw-`"args"`-map/`REQUIRED_POLLED_ARGS` note) matches the real diff of that module in the Stage
  4 commit.

**Verdict on Fix 2: resolved as specified.**

### Optional refinement applied

`plan.md`'s `test_export_lua_constants_parity.py`/`MAX_READS_PER_FRAME` claim is corrected in
place, superseded rather than deleted, pointing at `TestAdmitRead` in `test_watched_args_lua.py` —
matches where the review found the real coverage.

### Checks run (this pass, independently)

- `body-layer`: `ruff format --check`, `ruff check` (`src tests tools`): clean. `mypy src`: clean,
  74 files. `mypy tools`: clean, 10 files. `pytest tests -q`: 2650 passed, 4 xfailed — matches the
  implementer's reported counts.
- `aircraft-layer` (untouched this round, re-run anyway per the dispatch instruction to check both
  subprojects): `ruff format --check`, `ruff check` (`src tests`): clean. `mypy src`: clean, 28
  files. `pytest tests -q`: 608 passed.

## Verdict

APPROVED

## Review Confidence

Full read of this round's diff (4 files). Both required fixes verified by reading the code they
reference, not just the prose describing them, plus one live mutation against the actual
checked-out `test_logger.py` (not just the implementer's own report) confirming the rewritten call
sites are load-bearing. All four subprojects' checks (format/lint/type/test for both
aircraft-layer and body-layer) re-run independently rather than trusted from `implementation.md`.
