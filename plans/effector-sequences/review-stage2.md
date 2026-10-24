### Review Summary

BL-B90 Stage 2 (effector sequence engine, wired into the poll loop), branch
`feature/effector-sequences`, tip `b94d59e5eb773eecfe815b06df9d8b68b15fdc6f` (the tip's own
explore-notes-only commit on top of `a5658d3e`). Reviewed against `plans/effector-sequences/plan.md`
D1-D13/R1-R13/Co-moving Fields, `explore-notes.md`'s 2026-10-23 sections, `implementation.md`'s
"Stage 2" entry, `review-stage1.md`'s carry-forward items, and `body-layer/CLAUDE.md`/
`aircraft-layer/CLAUDE.md`.

**Merge conflict (`71dd23ce`, main's `fix/guidance-ready-edge` into this branch) reviewed
separately**: the only conflict was `body-layer/ROADMAP/body-layer-backlog.md`, resolved by keeping
both sides' lines (`BL-B91`/`BL-B92`) — trivial, nothing lost, no code conflict. The ready-edge fix
itself (`previously_observed is False and ready_observed is True`, no latch) is intact after the
merge and unaffected by Stage 2's own changes to the surrounding poll block (confirmed by reading
`logger.py`'s poll block and `crew_console.drain_guidance_unit_ready` directly, not by diff
inspection alone).

**Checks (this worktree, tip `b94d59e5`, tools resolved from the main checkout's `.venv`s per the
task's instruction since this worktree has none):**
- `body-layer/`: `ruff format --check src tests tools` — pass (180 files); `ruff check src tests
  tools` — pass; `cd body-layer && .venv/bin/mypy src` — pass (74 files); `.venv/bin/mypy tools` —
  pass (9 files); `pytest tests -q` — 2549 passed, 4 xfailed.
- `aircraft-layer/`: `ruff format --check src tests` — pass (75 files); `ruff check src tests` —
  pass; `.venv/bin/mypy src` — pass (27 files); `pytest tests -q` — 533 passed.
- All numbers match `implementation.md`'s own reported figures exactly.

### Parity, gating, and scope

- **Takeoff order/values**: `copilot-takeoff.md`'s four rows (missile_power → cplr_distr →
  sight_power → scho_pwr_b1, all "on") reproduce `_POWER_UP_SWITCHES`' device/cmd pairs exactly
  (confirmed against `test_effector_engine.py`'s fixture defs and the real committed registry's
  `(device, cmd, arg)` triples). `test_takeoff_runs_the_guidance_unit_power_up_sequence_through_
  the_real_poll_loop` asserts the byte-identical write sequence `[(6,3028,1.0), (16,3015,1.0),
  (7,3001,1.0), (6,3030,1.0)]` through the real poll loop, with `EFFECTOR_SEQUENCE_STEP_DELAY_S`
  spacing checked by advancing *sim* time correctly (no sim-time trap — confirmed by reading the
  test body, not just its name).
- **R12 self-check replacing the `!= on` conditions**: `copilot-takeoff.md`'s rows now carry no
  `condition` cell at all; the engine's own implicit self-check (`effector_engine.advance`) is what
  makes a repeat takeoff or hot/air start a no-op. **Verified by mutation** (see below), not just by
  reading the test names.
- **Gating stays in code, untouched**: `_handle_observ_on`'s `if not self.sight_ready: return
  [render_unable("GUIDANCE_NOT_READY").text]` and `_handle_weapons_armed`/`_handle_weapons_safe`
  (unconditional, "weapons armed"/"weapons safe" fixed phrasing) are unchanged; all four handlers
  now set a `*_transition` one-shot field for the poll loop to turn into `fire_trigger(...)` rather
  than writing directly — the pilot's own command readback ("Observ on.") is still spoken
  immediately regardless of whether the sequence file backing it loaded (plan's own stated risk,
  confirmed present).
- **"Guidance unit ready" edge, after the merge**: `logger.py`'s poll block calls
  `crew_console.drain_guidance_unit_ready` with `previously_observed`/`ready_observed`
  unconditionally every poll, in the plan's own stated order (refresh readback → takeoff edge →
  transitions → `advance_effectors` → ready edge → `drain_config_error`) — the merge did not
  reintroduce the pre-fix "speaks on any lit sample" latch; `guidance_unit_ready_prev_observed` is
  still the only state carried, no re-added `announced` bool.
- **BL-B80 untouched**: `sight_head.py` and `run_sight_servo`/the slew wire are not in this diff at
  all (confirmed: not in `git diff --stat`). `sight_effector.py`'s surviving functions
  (`sight_ready`, `refresh_readback`, `write_sight_target`) and `GuidanceUnitState`'s readback
  fields are unchanged in meaning; only the sequencing half (`start_power_up`/`advance_power_up`/
  `write_observ`/`write_weapon_safety`, the device/cmd constants, and the four sequencing fields on
  `GuidanceUnitState`) was removed, exactly as the plan's "What moves, what stays" table specifies.
  `sight_trace_writer.py`'s `observ_commanded` column keeps its name and `False`-when-`None`
  default, now sourced from `EffectorRunState.commanded_values` instead.
- **Co-moving Fields construction-site check**: `grep -rn 'EffectorRunState(\|GuidanceUnitState('
  body-layer/src` — exactly one site each, both `field(default_factory=...)` on
  `ConsolePerceptionRunner`. No helper builds a "fresh state for trigger X".

### D1/D9 ordering — verified, including the poll-loop-gap question the task raised

- **D1 per-trigger queue**: `fire_trigger` idle→running / running→pending / pending→no-op
  transitions, and independent per-trigger queues, are covered by dedicated engine tests and match
  the plan exactly.
- **D9 (failed write blocks later writes to the same switch this poll)**: `test_d9_failed_on_then_
  off_ends_off` fires OBSERV_ON then OBSERV_OFF, fails the `observ` write via the fake client's
  `fail_device_cmds`, confirms **zero** writes land while the fault holds (both triggers' own rows
  correctly wait/retry rather than landing out of order), then clears the fault and confirms both
  land in fire order within the same poll, ending at `commanded_values["observ"] == "off"` — this
  is the plan's own worked example, and it is a real, mutation-provable test (not merely
  structurally present): deleting the `if row.effector in failed_effectors: break` guard in
  `advance` would let OFF's write race ahead of ON's retry, which this test would catch.
- **This D9 ordering is tested only at the engine level, as the task brief flagged — checked
  whether the poll-loop gap matters, and it does not here.** `logger.py` calls
  `advance_effectors` (`effector_engine.advance`) exactly once per poll (grep confirms one call
  site at line 3535), *after* every trigger-firing branch for that poll has already run, passing
  the single `effector_readback` snapshot fetched once at the top of the block. The poll loop
  introduces no additional ordering surface beyond "call `advance` once, with the current state and
  one readback snapshot" — the exact shape the engine-level test already exercises end to end. A
  wiring-level regression here would have to be "call `advance` twice in one poll" or "pass a stale
  state object", neither of which the diff does. No additional poll-loop test is required for D9
  specifically.

### D5/D6 — one required fix (mutation-tested)

- **Registry-cascade tradeoff, re-verified as review-stage1 asked**: `_load_effector_config`
  aggregates both loaders' error lists into one console banner, and the Stage-1-flagged "one
  RegistryError visible first" claim holds — `test_load_effector_config_aggregates_errors_from_
  both_loaders` drives it directly with faked loader results, confirming both a registry-level and
  a sequence-level error land in the same banner and each produce their own `logger.error` line.
- **`EffectorDef.unverified` is no longer a dead field** — `test_load_effector_config_logs_the_
  unverified_effector` confirms the startup `INFO` line names `cplr_distr`.
- **Required fix — the SPU-8 intercom gate in `drain_config_error` is not actually exercised in
  isolation, despite the one test's own docstring/comment claiming it is.** Mutation-tested: deleting
  `if not intercom_open: return` from `drain_config_error` leaves the **entire suite green**,
  including `test_config_error_held_while_silenced_and_intercom_closed_then_speaks_once` — the test
  that is supposed to be the intercom gate's own coverage (the fake client's own code comment in
  `test_logger.py` says so verbatim: *"A test exercising `drain_config_error`'s intercom gate drives
  this directly"*). The reason: every phase of that test where the intercom is closed also has
  `crew_console.silenced = True`, so the `silenced` check alone already returns early — the test
  never reaches a state where `intercom_open is False` and `silenced is False` at the same time, so
  the intercom gate's own contribution to the outcome is never observed. **Required fix**: add a
  phase to that test (or a new one) with `silenced = False` and the intercom still closed, asserting
  no speech, before the intercom opens — the same shape the test already uses for the silenced gate,
  just with the roles swapped. A regression that always spoke the config-error line regardless of
  SPU-8 state (e.g. the one audio line firing before the intercom is actually up, the exact failure
  D6 exists to prevent) would ship undetected today. Saved as a transferable reviewer-memory lesson
  (`feedback_sibling_gate_masked_by_adjacent_flag_in_same_test.md`) since this is a recognisable
  pattern (two independent gates, one test, one gate's window always shadowed by the other).
- **D6 mission-restart preservation**: `config_error_pending` is explicitly passed through
  `reset_for_new_mission`'s `__init__` re-invocation (not merely absent from a "clear" list), and
  `test_config_error_pending_survives_a_mission_restart` plus the generic preserve-set sweep in
  `test_mission_start_reset.py` both cover it. Correct.
- **Banner**: printed to stderr wrapped in `"=" * 78` rule lines with a leading
  "EFFECTOR CONFIG ERROR" header — reasonably unmissable for a human reading the console; each
  finding also gets its own `logger.error` line. No stronger "unmissable" mechanism exists or is
  asked for by the plan.

### Per-aircraft / first-wins (R13)

- `effector_registry.load_registry`'s collision rule is now "first (TOML file order) wins, reject
  the rest" — `test_colliding_device_cmd_arg_first_wins` confirms the winner survives, the loser is
  named in the error with "already claimed by". `resolved.items()` is iterated for the collision
  scan *after* full population, so "first" is genuinely file order, not an artifact of concurrent
  mutation during iteration (checked by reading the loop structure directly, not assumed).
- `load_registries_by_aircraft`/`load_sequences` isolate one aircraft directory's bad registry from
  another's (`test_load_registries_by_aircraft_isolates_a_bad_aircraft_directory`,
  `test_bad_registry_in_one_aircraft_directory_does_not_affect_another`) — confirmed by reading both
  tests, not just their names.
- A sequence file's `aircraft` header not matching the directory it is found in is its own file
  error (`test_aircraft_header_not_matching_its_own_directory_is_a_file_error`), and the duplicate
  `(aircraft, role, trigger)` key check still rejects both files sharing it, unaffected by the
  directory move.
- `aircraft_dir_name` is the single lower-casing site; `effector_sequences.py` imports it rather than
  re-deriving — confirmed, no second lower-casing anywhere in the diff.

### Tunables — rendered `defaults.toml` read directly, not the source comment

- `[belief.effector_engine]` section: `EFFECTOR_CONDITION_READBACK_WAIT_S = 5.0` (range 1.0–30.0)
  and `EFFECTOR_SEQUENCE_STEP_DELAY_S = 1.0` (range 0.5–5.0) both render correctly — the comment
  shown is each constant's actual first sentence, arithmetic matches the source (`tuning.real(...,
  1.0, lo=0.5, hi=5.0, ...)` etc.), no truncated backtick spans, no stale figure.
  `EFFECTOR_SEQUENCE_STEP_DELAY_S`'s source docstring's *second* sentence ("A `tuning.toml` still
  naming the old key gets this module's own 'unknown key' warning...") does **not** render into
  `defaults.toml` — this is the generator's documented behaviour (first sentence only), and in this
  case it is not a loss: the fact is a deprecation notice about the *old* key name, not a
  behavioural warning about the *current* key's own value, and the runtime's existing "unknown key"
  warning (per `body-layer/CLAUDE.md`'s "Tuning" section) covers the actual case at the moment it
  matters (someone's old `tuning.toml` is loaded). Not a required fix.
- `GUIDANCE_UNIT_SWITCH_DELAY_S` is gone from `defaults.toml`, as D10 specifies.
- **Cross-key coupling**: no ordering/ratio relationship is asserted between
  `EFFECTOR_SEQUENCE_STEP_DELAY_S` and `EFFECTOR_CONDITION_READBACK_WAIT_S` (e.g. the wait should
  arguably stay ≥ the step delay for a multi-row sequence to make sense), and none is enforced at
  import or elsewhere. The plan does not state this as a required invariant, and both constants'
  defaults (1.0 and 5.0) satisfy it comfortably, so this is **not** a required fix — flagging as an
  optional note for whoever next tunes either value down.

### Aircraft-layer `"args"` map (R7)

- `CockpitSwitchState.to_api_dict()` gains `"args"` as a pure derived view of the six existing raw
  fields, re-keyed by DCS arg number as a string; every existing key is unchanged, so this is
  backward compatible for every existing consumer (adding a dict key cannot break a reader that
  does not look for it). `test_cockpit_switch.py`'s two assertion dicts both gained the key.
- **Needs a collector restart on the Windows DCS machine, no `Export.lua` redeploy** — confirmed
  correct: `to_api_dict` runs inside the aircraft-layer collector/API process (Python), not inside
  `Export.lua`; nothing on the DCS/Lua side changed, so only the Python process needs to reload the
  new code.
- Body-layer against an older collector (no `"args"` key): `_raw_value_for` returns `None` via
  `readback.get(str(arg))` on a `dict` missing the key — reads as "no readback yet", correctly
  entering the existing unknown-readback wait/timeout path rather than raising or misreading `0.0`
  as a value. The plan's own stated WARNING for this case ("cockpit_switch feed has no args map")
  is in `logger.py`'s poll block per the plan text — confirmed present.

### Comments pruned (per the Implementer's "prune the comment you are standing next to")

- `sight_effector.py`'s wholesale rewrite removed several dated research citations
  ("Confirmed live 2026-10-17 (`aircraft-layer/research/2026-10-17-...`)", "ON arms the circuit,
  OFF safes it" with its Finding 6 citation) that were attached to the now-deleted device/cmd
  constants and sequencing functions. **Not a required fix**: the underlying research notes
  themselves are untouched (this diff doesn't touch `research/`), the facts those citations
  supported (arg numbers, value→raw mappings) are now carried structurally in the generated raw
  dump + curated registry (a stronger provenance mechanism — DCS build + input sha256 vs. a
  code-comment citation), and the one citation that is a live, open flight question —
  `cplr_distr`'s `unverified = true` with its exact user quote and acceptance-doc reference — is
  preserved verbatim in `effectors.toml`, not dropped. No durable dated-finding line was lost
  without a replacement home.
- `logger.py`'s OBSERV-write-block comments were replaced with a pointer to `advance_effectors`
  (the write moved there); the surrounding hands-busy-suppression comment, which is still this
  module's own job, was kept — correctly scoped, not an over-prune.

### Required Fixes

- **Add a `silenced=False`/intercom-still-closed phase to
  `test_config_error_held_while_silenced_and_intercom_closed_then_speaks_once`** (or a new test),
  asserting no speech while the intercom is closed and the pilot is *not* silenced, before the
  intercom opens — see "D5/D6" above. Confirmed by mutation that the intercom gate is otherwise
  unverified; the gate's own code is correct, only its test coverage is missing.

### Optional Refinements

- Consider a cross-key bound/assertion (or at minimum a comment) relating
  `EFFECTOR_SEQUENCE_STEP_DELAY_S` and `EFFECTOR_CONDITION_READBACK_WAIT_S` if either is ever tuned
  independently — not needed at current defaults.
- The dated research citations pruned from `sight_effector.py` could be carried into
  `effectors.toml`'s per-entry comments (the way `cplr_distr`'s already is) the next time that file
  is hand-edited, for symmetry — not required, since the raw dump's own provenance header already
  supersedes the need for them.

### Verdict

**APPROVED WITH MINOR FIXES** — one required fix (test-coverage gap on the SPU-8 intercom gate,
mutation-confirmed; the gated code itself is correct), everything else holds under direct reading
and mutation testing.

### Review Confidence

Full read of `effector_engine.py`, `effector_registry.py`, `effector_sequences.py`,
`sight_effector.py`, `sight_trace_writer.py`, the relevant `logger.py`/`crew_console.py` sections
(poll block, `_load_effector_config`, `drain_config_error`, `drain_guidance_unit_ready`,
`reset_for_new_mission` x2, the four command handlers), `cockpit_switch.py`'s `to_api_dict`, all
five shipped sequence files, `effectors.toml`, and `defaults.toml`'s rendered `[belief.
effector_engine]` section. Read `test_effector_engine.py` and `test_effector_registry.py`'s new/
changed tests in full; read the relevant sections of `test_logger.py` (takeoff/air-start/config-error
tests) in full rather than trusting test names. Ran every check myself in this worktree against the
actual tip rather than trusting `implementation.md`'s reported numbers (they matched exactly).
**Verified by mutation, not just by reading**, three separate claims: R12's self-check (confirmed
load-bearing — breaking it fails 5 tests across both engine and poll-loop level), D9's write-ordering
guard (read the code path rather than mutating it, since `test_d9_failed_on_then_off_ends_off`
already demonstrates the exact failure mode the plan describes), and the SPU-8 intercom gate
(confirmed **not** load-bearing against the existing suite — the one required fix above). Did not
re-read `switch-reference.md`, `generate_effector_registry.py`, or `render_switch_reference.py` —
unchanged in substance since Stage 0/Stage 1's own review (only path-constant moves for R13), and
Stage 1's review already covered their staleness test and generator logic in full. Did not
independently re-verify Stage 0's ED-forms research note (`aircraft-layer/research/
2026-10-23-mi24p-clickabledata-forms.md`) — out of this stage's scope and already the input to a
Stage 0/0d review, not Stage 2's.

---

### Fix re-review (2026-10-23)

Scope: the two fix commits on top of this review's own tip, `feature/effector-sequences` now at
`0605611f` -- `03e175c5` (cherry-picked from `b9c9644c`, this review's required fix: the
intercom-gate test phase) and `0605611f` (the performance change request from
`performance-stage1-2.md`: gate `GET /spu8/state` behind `crew_console.config_error_pending`). The
security deep-analysis commit in between (`d3432963`) touches docs only.

**Required fix verified, by mutation, not just by reading the new test phase.** Deleted `if not
intercom_open: return` from `CrewConsole.drain_config_error` (`body-layer/src/belief/
crew_console.py`) and ran `test_config_error_held_while_silenced_and_intercom_closed_then_
speaks_once` in isolation -- it now fails exactly where the new phase asserts
`config_error_pending is True` (actual `False`: the line spoke immediately once unsilenced, intercom
still closed), the precise failure the fix's own phase exists to catch. Restored the two lines by
hand; `git diff` on the file is empty after restore, confirming an exact restore rather than a
by-eye one. This closes the one required fix from the review above -- the gate is no longer
unverified.

**Performance guard verified, by mutation, for both halves.**

- *Load-bearing:* reverted `logger.py`'s `~3581` guard to the unconditional pre-fix call (removed
  the `if crew_console.config_error_pending:` wrapper) and ran
  `test_no_spu8_poll_when_config_error_not_pending` in isolation -- failed as expected (`assert 33
  == 0`, 33 unconditional GETs over the poll window), matching `implementation.md`'s own reported
  mutation result exactly. Restored by hand; `git diff` on the file is empty after restore.
- *Behaviour preserved:* re-ran `test_config_error_held_while_silenced_and_intercom_closed_then_
  speaks_once`, `test_no_spu8_poll_when_config_error_not_pending`, and
  `test_config_error_pending_survives_a_mission_restart` together against the restored code -- all
  three pass. The line still speaks once, exactly once, after the gate opens; it is still held
  while silenced; it survives a mission restart (preserved through `reset_for_new_mission`'s
  `__init__` re-invocation, unchanged by this diff). A failed fetch is tolerated and retried:
  `get_spu8_state_latest` (guarded or not) sits inside `_run_crew_text_poll_loop`'s own per-poll
  `try: ... except Exception as exc:` block (`logger.py` ~3760, pre-existing, unchanged by this
  diff) -- any exception from the fetch is caught, logged via `logger.exception` or
  `connection.report_failure` (connection-loss case), and the next poll runs normally; the guard
  does not add a second failure path.

**No case found where `config_error_pending` flips `True` again after startup without the fetch
then resuming.** Grepped every read/write site
(`grep -n "config_error_pending" body-layer/src/belief/crew_console.py body-layer/src/logger.py`):
it is set once, at `CrewConsole` construction (`logger.py` ~4741, `config_error_pending=had_
config_errors`, computed by `_load_effector_config()` before the poll loop or `CrewConsole` exist),
preserved (never re-derived) across a mission restart by `reset_for_new_mission`'s `__init__`
re-invocation (`crew_console.py` ~1431), and cleared exactly once, on a successful speak, in
`drain_config_error` (~1590). There is no second site that sets it `True`. So the guard's premise --
"once cleared, the GET never needs to fire again for this process's lifetime" -- holds for every
reachable state, not just the common one.

**Checks, this worktree, tip `0605611f` (tools resolved from the main checkout's `.venv` per the
task's instruction, cwd inside this worktree's `body-layer/`):**
- `ruff format --check src tests tools` -- pass (180 files)
- `ruff check src tests tools` -- pass
- `cd body-layer && .venv/bin/mypy src` -- pass (74 files)
- `pytest tests -q` -- 2550 passed, 4 xfailed (one more than this review's own earlier run of
  2549 -- the one new test added by the performance fix, `test_no_spu8_poll_when_config_error_
  not_pending`; no other count changed)

#### Verdict

**APPROVED.** The one required fix from the original review is genuinely closed (mutation-tested),
the performance change request is correctly applied and mutation-tested on both its load-bearing
and its behaviour-preservation claims, and no `config_error_pending` lifecycle gap exists. Clear to
proceed to DoD.

#### Review Confidence

Full read of both fix commits' diffs (`body-layer/src/logger.py`, `body-layer/src/belief/
crew_console.py`, `body-layer/tests/test_logger.py`) and the `aircraft_client.py`/`_get_json`
failure-handling path they rely on. Verified by mutation: the intercom gate (required fix), the
perf guard's load-bearing half, and re-ran the perf guard's behaviour-preservation tests together
rather than individually. Did not re-review anything outside the two fix commits -- Stage 2's own
substance (engine, registry, sequences, aircraft-layer `"args"` map) was the original review's
scope above and is unchanged by these commits.
