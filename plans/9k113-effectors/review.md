# Review: BL-B66 (9K113 effectors), Stages 1-4

Reviewed against `plans/9k113-effectors/plan.md` (text above the `# Superseded text below`
divider), `explore-notes.md`, `security-plan-review.md`, `docs/acceptance/
2026-10-17-9k113-procedures-direction.md`, and `plans/9k113-effectors/implementation.md`.

**Base note (process, not a finding on the implementation):** the worktree assigned to this
review (`.claude/worktrees/agent-afab5f7cbdd00061e`) was created from a stale/unrelated base
(`origin/HEAD`-ish, diverged from `feature/9k113-effectors` — neither commit was an ancestor of
the other). The expected tip `ce6a81babb47ac75fcf0ae0940360be684fe3d7d` could not be reached by
`git merge --ff-only` from that HEAD. A second worktree already existed at
`/Users/sg/Code/DCS-petrobrain-9k113-effectors`, checked out exactly at that tip on
`feature/9k113-effectors` with a clean tree — all verification below (reading, running checks,
mutation testing) was done there. This review file and this worktree's own commit are written
here, in the worktree I was given, per the handoff instructions.

## What was checked

- Full read of the plan, explore notes, security plan review (REJECTED on the allow-list finding,
  explicitly overridden by user Decision 4 — not re-litigated here), and the procedures-direction
  acceptance doc.
- Full diff read: `Export.lua` (new op, readback push, version bump), aircraft-layer
  schema/collector/API/tests, `body-layer/src/belief/sight_effector.py` (new),
  `body-layer/src/logger.py`'s poll-loop wiring, `crew_console.py`, `speech.py`,
  `audio-adapter/src/vocabulary.py` and its test changes, `tuning.py`/`defaults.toml`.
- Ran `ruff format --check`, `ruff check`, `mypy src` (from inside each subproject), and `pytest`
  for all three touched subprojects (aircraft-layer, body-layer, audio-adapter) against freshly
  built `.venv`s (none existed in either worktree) pinned to Python 3.12. All green, matching
  `implementation.md`'s own claims exactly (aircraft-layer 407 passed; body-layer 2383 passed, 4
  xfailed; audio-adapter 346 passed, 2 skipped).
- `luac5.1 -p Export.lua` (syntax) and `luac5.1 -l -p` + a `GETGLOBAL` scan (global-leak check) —
  clean; every `GETGLOBAL` resolves to an existing DCS/Lua API name or stdlib, none of the three
  new functions (`handle_cockpit_switch_command`, `push_cockpit_switch_state`,
  `extract_json_number_field`) leaks a name.
- Verified the rendered `body-layer/config/defaults.toml` entry for
  `GUIDANCE_UNIT_SWITCH_DELAY_S` directly (not the source `#:` comment) — first sentence renders
  intact, status/range correct, no markup corruption, arithmetic matches the source constants.
- Verified by mutation, not just reading, per this role's standing instruction:
  - Construction-site grep tests (`test_guidance_unit_state_is_constructed_in_exactly_one_place_
    in_logger_py`, `test_sight_effector_never_constructs_guidance_unit_state_directly`) — read, not
    mutated (mechanical regex checks, low risk of a false guard).
  - `advance_power_up`'s retry-on-failure path — unit test exercises it correctly at the pure
    function level (confirmed by reading the fake clients and assertions, not separately mutated,
    since the security-plan-review finding 3 this answers is already a `replace()`-based idempotent
    design and the test shape is standard).
  - **The `_run_crew_text_poll_loop` integration wiring added for Stages 2-4** (takeoff rising-edge
    detection, `start_guidance_unit_power_up`/`advance_guidance_unit_power_up`/
    `refresh_cockpit_switch_readback` calls, the `sight_ready` refresh, `drain_guidance_unit_ready`,
    and the OBSERV/weapons-safety cockpit-write-through with its try/except) — mutated twice:
    1. Forced the takeoff rising-edge `if` to `False` (disabling the entire power-up trigger).
       Ran `pytest tests/test_logger.py` — **160/160 still passed.**
    2. Removed the `announced` guard from `CrewConsole.drain_guidance_unit_ready` (so "Guidance
       unit ready." would be spoken every poll once ready, not once). Ran the full body-layer
       suite — **2383/2383 still passed.**
    Both mutations were reverted; the worktree's tree is clean (confirmed below).
  - The three pre-existing `test_crew_console.py` tests the implementer modified
    (`test_non_look_command_on_ground_dispatches_normally`,
    `test_observ_on_signals_the_poll_loop_and_speaks`,
    `test_observ_transition_is_reset_at_the_top_of_every_dispatch`) — read in full; each addition
    (`console.sight_ready = True`) is the minimal, correctly-targeted change the Stage 3 readiness
    gate requires, and the two new tests
    (`test_observ_on_refused_when_guidance_unit_not_ready`/`test_observ_off_needs_no_readiness`)
    cover exactly the dimension the three predate.
  - Audio-adapter's "weapons"/"tanks" `VERB_FLOOR`-boundary claim — checked against
    `command_matcher.py`'s actual comparison (`if best_ratio < VERB_FLOOR:`, strict `<`), so a ratio
    exactly at `0.5` does anchor, matching the test's asserted `verb_anchored is True`. Confirmed,
    not just read.
- Queried `.claude/scripts/gq.sh` for prior practice on whether this project's poll-loop wiring
  needs an integration test beyond the effector module's own unit tests — turned up
  `test_observ_off_command_stops_the_sight_through_the_real_poll_loop` (this same file,
  pre-existing), whose own docstring states the precedent directly: *"the gap the review found was
  invisible precisely because no existing test drove this path end to end."* Also found
  `test_crew_text_poll_loop_resets_belief_on_mission_restart`/`...switches_theatre_on_mission_
  restart`, which do drive `_run_crew_text_poll_loop` on a real thread for a comparably
  wiring-shaped feature (BL-15). Neither precedent is honoured for this entry's own new wiring.

## Required Fixes

- **The `_run_crew_text_poll_loop` wiring for the entire guidance-unit power-up (takeoff
  detection → sequencer advance → readback refresh → `sight_ready` → "Guidance unit ready."
  spoken exactly once) and the OBSERV/weapons-safety cockpit-write-through has no test coverage at
  the point it is actually wired into the poll loop**, only at the pure-function level inside
  `sight_effector.py`/`crew_console.py` in isolation. This is not a theoretical gap: disabling the
  takeoff trigger outright, and separately breaking "spoken exactly once" into "spoken every poll
  once ready," both left the full body-layer suite green (160/160 and 2383/2383 respectively — see
  above). The implementation.md's own text claims the fake client's new
  `cockpit_switch_writes` recorder exists "so a test can assert on the guidance-unit power-up
  sequence's actual writes" — no test in the diff does. This is exactly the project's own stated
  failure mode for this file (`test_observ_off_command_stops_the_sight_through_the_real_poll_loop`'s
  docstring, quoted above), recurring on the same file in the same feature family. Two of the
  checklist items the task brief named directly — "takeoff detection edge cases" and
  "'Guidance unit ready' spoken exactly once" — are unverifiable from the test suite as it stands.
  **Fix**: add at least one test that drives the real poll-loop path (either on a thread, per
  `test_crew_text_poll_loop_resets_belief_on_mission_restart`'s pattern, or reproduced verbatim per
  `test_observ_off_command_stops_the_sight_through_the_real_poll_loop`'s pattern) across an
  on-ground→airborne transition, asserting: the four switches are written in order via
  `cockpit_switch_writes`/the fake's recorder; `sight_ready` becomes `True` only after the fourth;
  "Guidance unit ready." is printed exactly once across several subsequent polls, not once per
  poll. A second, smaller test should exercise the OBSERV-on/weapons-armed write-through
  (`write_observ_switch`/`write_weapon_safety_switch` actually firing from an accepted transition
  inside the loop, not just from the handler that sets the transition field).

No other required fixes. The security-plan-review's rejection (missing allow-list) is addressed by
an explicit, named user override (plan Decision 4), not silently dropped — correctly not treated as
outstanding.

## Optional Refinements

- `test_logger.py`'s `FakeConsoleAircraftClient.get_cockpit_switch_state_latest` always returns
  `None`. Once the required fix above adds a real driving test, consider letting it also return a
  synthesized `CockpitSwitchState`-shaped dict after the sequence completes, so `refresh_readback`'s
  wiring (currently only unit-tested in isolation) gets at least one integration-level exercise too.
  Optional — `refresh_readback`'s result is explicitly unread by this entry (plan §3, carried for
  `BL-B67`), so this is a nice-to-have, not a gap in anything this entry's own behaviour depends on.
- The `870`/`956`/`L166V POWER` naming cross-check in `implementation.md`'s Deviations §1 (device/
  cmd numbers resolved from three separate research docs rather than one table) would be cheaper to
  verify for a future reader if `sight_effector.py`'s own `_POWER_UP_SWITCHES` comment named the
  source document inline next to each row, not just at the top of the block — it already does
  this reasonably well; a line-by-line citation would be marginally better. Cosmetic.

## Verdict

**NEEDS REVISION** — one required fix (test coverage for the poll-loop integration wiring,
Stages 2-4). Everything else — scope fit, module boundaries (`sight_effector.py`'s single
device/arg-number boundary), the construction-site discipline, the tuning pattern and its rendered
output, the deliberate no-allow-list departure, the ARMED-never-automatic invariant, the voice-phrase
false-anchor mitigation and its own test, and all format/lint/type/test gates across all three
touched subprojects — is sound and needs no change.

## Review Confidence

Full read of the diff and all five linked plan/explore/security/acceptance/implementation
documents; all three subprojects' format/lint/type/test commands run directly (not taken on
report); the one required fix was confirmed by actual mutation + re-run, not by inspection alone.

---

## Re-review, 2026-10-21 — (a) review-fix tests, (b) Stage 4b slew telemetry logging

Fast-forwarded cleanly from `main` to `7feecd1a5df69bd5b1527e900cf86497034e8033` (strict
ancestor, clean tree); no stale-base handling needed this time. Reviewed `a85ae0a3..d5010d5d`
(review fix) and `11f504b0..7feecd1a` (Stage 4b; the commit between, `11f504b0`, is plan/roadmap
text only) against `plans/9k113-effectors/plan.md`'s Stage 4b paragraph,
`implementation.md`'s "Review fix" and "Stage 4b" sections, and `body-layer/ROADMAP/BL-B80.md`.

### (a) Review-fix tests — confirmed sound, by mutation, not just reading

Read all three new tests in `body-layer/tests/test_logger.py`
(`test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop`,
`test_second_takeoff_in_the_same_mission_does_not_rerun_the_power_up`,
`test_observ_and_weapons_safety_write_through_the_real_poll_loop`), then re-ran both of the
original review's mutations myself, independently of the implementer's own re-run claim in
`implementation.md`:

- Disabled the takeoff rising-edge `if` in `logger.py` (prefixed with `False and`) →
  `test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop` fails
  (`cockpit_switch_writes == []`, expected four writes). Reverted; `git status --porcelain` on
  `logger.py` clean afterward.
- Removed the `announced` guard from `CrewConsole.drain_guidance_unit_ready` (`if not ready:`
  instead of `if announced or not ready:`) → the same test fails ("Guidance unit ready."
  spoken 21 times instead of 1). Reverted; clean.

Both mutations land exactly where the review said they would. The three tests do guard takeoff
trigger order (writes asserted as an exact ordered list), `sight_ready` timing (checked `False`
on every partial count 1-3, not just before/after), "Guidance unit ready" exactly once (the
`count(...) == 1` assertion the second mutation breaks), and OBSERV/weapons write-through (both
pre-ready refusal with no write, and post-ready writes for OBSERV-on/weapons-armed/weapons-safe,
each confirmed present in `cockpit_switch_writes`). **No further required fix on (a).**

### (b) Stage 4b slew telemetry logging

Read `Export.lua`'s new `push_slew_trace`/flag/buffer machinery, `schema/cockpit_switch.py`'s
optional `sight_az`/`sight_elev` fields and their parse contract, `collector/server.py`'s version
bump, `sight_effector.py`'s readback fields and `sight_azimuth_raw_to_deg`, the new
`sight_trace_writer.py` in full, `logger.py`'s `--slew-trace` wiring end to end (CLI flag,
validation, `_resolve_slew_trace_log_path`, `_reroll_run_logs`'s widened 3-tuple return and both
call sites, the `_run_crew_text_poll_loop` write-site placement), the reroll and wiring tests, and
the `sortie-log-triage` skill's new `slew_report`/`body_slew_report` and `SKILL.md` sections.

Checked against the open question `BL-B80.md` actually states (quantised vs. lagged vs. stepped
readback, needing per-frame samples because body-layer's 1 Hz poll cannot distinguish them):

- **Per-frame sampling, precise timestamps, raw values kept**: `push_slew_trace` runs from
  `LuaExportAfterNextFrame`, logs `t`/raw `az`/raw `elev`/`observe` every frame OBSERV is on (plus
  a `SLEW_TRACE_TAIL_S` tail), with 5-decimal formatting (`fmt_num_or_null`) — this *can* answer
  the quantised/lagged/stepped question from a ~2 min hand-slew: a genuinely stepped readback
  shows flat runs then discrete jumps at frame resolution; a lagged one shows a time offset
  against whatever drove it (though there is nothing commanded-side to lag against yet, see
  below); a quantised one shows the step floor the triage script's "smallest observed non-zero
  step" line reports. Sound.
- **Desired vs. actual and `_source` correct**: verified by reading `sight_trace_writer._row`
  line by line — `actual_azimuth_source` is `"readback"` only when `sight_az_raw is not None`,
  `"model"` when a model value exists, `None` otherwise; elevation is hard-coded to never report
  `"readback"` (876's calibration is unmeasured), matching the module's own docstring and the
  plan's "Raw arg values are logged alongside any degree conversion" sentence exactly. The one new
  wiring test (`test_slew_trace_is_written_from_the_real_poll_loop`) drives a real readback value
  (`sight_az=0.16500`) through the real poll loop and asserts the converted degrees
  (`22.5 == 0.165 * 60/0.44`, confirmed by hand) land in the written row with `_source ==
  "readback"` and elevation's `_source != "readback"` on the same row. I re-ran this test and then
  mutated the write-call site (`if slew_trace_writer is not None and False:`) — the test fails
  (`0 rows` against the asserted `>= 2`) — reverted, `git status --porcelain` clean on
  `logger.py` afterward. A real regression guard, not green-by-construction.
- **The Export.lua per-frame path is cheap and can't break the export loop**: every DCS API call
  inside `push_slew_trace` (`GetDevice(0):get_argument_value(...)`) goes through `safe_call`, same
  as every other read in this file; the fast path when `SLEW_DEBUG` is `false` is an immediate
  `return` before any of that runs, so the flag-off cost is one boolean check per frame, matching
  the plan's own "tiny per-frame cost" framing. The file write is buffered
  (`SLEW_LOG_FLUSH_EVERY_N_LINES = 25`, one `write`+`flush` per 25 lines, not per frame) and
  `io.open` itself is `pcall`-guarded with a drop-rather-than-grow-unbounded fallback
  (`slew_log_buffer = {}`) if the file can't be opened — no unguarded call that could raise and
  take down `LuaExportAfterNextFrame` (and therefore the whole export/telemetry loop) with it.
  `LuaExportStop` flushes and closes. Sound.
- **`EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` bump consistent**: both sides read
  `"2026-10-21b"` (`Export.lua` line ~147, `collector/server.py`'s `EXPECTED_EXPORT_VERSION`),
  confirmed by direct diff read, not by trusting the changelog comment.
- **The sixth run-log reroll wired like the others**: confirmed by reading `_reroll_run_logs`'s
  diff directly — `slew_trace_writer`/`slew_trace_base` follow the identical
  "`_reroll_one`, close-old-if-new, construct-new" shape as `trace_writer`/`belief_truth_writer`
  immediately above it in the same function, the 3-tuple return is consumed correctly at both call
  sites (`_run_console_poll_loop` discards the third element with `_`, `_run_crew_text_poll_loop`
  keeps it), and the new `test_reroll_closes_the_old_slew_trace_writer_and_opens_a_new_one` test
  mirrors the pre-existing detection-trace reroll test's assertions one-for-one (old file closed,
  new path differs, new file exists). Ran it directly: passes.
- **`sortie-log-triage` slew section computes what it claims, says "not computed" rather than
  inventing lag**: read `slew_report`/`body_slew_report` line by line. The smallest-non-zero-step
  calculation is a real `min` over consecutive non-zero deltas (not a guess), the monotonic-run
  rate is a real endpoint-to-endpoint deg/s calculation over the longest same-direction run (not a
  placeholder), and the lag line is a hardcoded, correctly-reasoned refusal
  (`slew_cmd_az`/`slew_cmd_el` are always `null` in this entry, so there is no commanded-side
  timestamp to lag against) rather than a fabricated number — matches the task brief's own framing
  of what this check should find. No arithmetic bug found in either function on a hand read (the
  monotonic-run tracker correctly treats a zero-delta sample as continuing the current run rather
  than breaking it, and correctly resets `direction` only when a nonzero delta sets it).
- **Enable instructions in `implementation.md` are correct and complete**: cross-checked each of
  the four numbered steps against the actual code — the flag path
  (`Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag`) matches the Lua `do` block's
  `lfs.writedir() .. "Scripts\\aircraft_layer_slew_debug.flag"`; "checked once at load" is correct
  (the `do...end` block runs at `Export.lua` load, not per-frame); "writes nothing while OBSERV is
  off" is correct (`push_slew_trace`'s own OBSERV + tail-window gate); the `--slew-trace` flag's
  `--crew-text` requirement and `parser.error` on `--console` are both present in `main()` exactly
  as described; the output filename being the *stamped* path (not the one passed on the command
  line) is correctly called out and matches `_resolve_slew_trace_log_path`'s behavior. Complete
  and correct.
- **Logging-only constants left out of `tuning.py`**: **agree.** Verified
  `config/defaults.toml` is untouched in this range (`git diff 11f504b0..3ee32659 --
  body-layer/config/defaults.toml` is empty) and the staleness test
  (`test_tuning_defaults_toml.py`) still passes. Applying root `CLAUDE.md`'s own inclusion test
  ("A new constant that changes what Petrovich does — what he sees, says, remembers, or how long
  he waits") to each candidate: `SIGHT_POS_EPSILON`, `SLEW_TRACE_TAIL_S`, and
  `SLEW_LOG_FLUSH_EVERY_N_LINES` (all Lua-side) and `SightTraceWriter.DEFAULT_FLUSH_EVERY_N_POLLS`
  (Python-side) all govern *what gets written to a debug log*, never a cockpit action, a spoken
  line, or a wait the pilot experiences — none of them is reachable from anything Petrovich does
  or says. This is the exact category `detection_trace_writer.DetectionTraceWriter.DEFAULT_
  FLUSH_EVERY_N_POLLS` already sits in as precedent, cited correctly in `implementation.md`.
  `_SIGHT_AZIMUTH_DEG_PER_RAW_UNIT` is a measured physical calibration, not a design choice with a
  tunable range — the same category arg 761's own plain-literal treatment already established
  elsewhere in this codebase; a tuning key implies a legitimate range of correct values, and there
  isn't one here, there is one measured fact. Correctly excluded on both counts.

**No required fix found in either (a) or (b).** Everything claimed in `implementation.md` for
both the review fix and Stage 4b was independently confirmed: by direct diff read, by running the
full checks myself (not taken on report) across both touched subprojects, and by mutation on the
two load-bearing write paths (the review-fix wiring's four-switch sequence/announce-once guard,
and Stage 4b's own `write_poll` call site).

### Checks re-run directly (not taken on report)

**body-layer** (fresh `.venv`, Python 3.12, `pyproj`/`numpy<2.5`/`pytest`/`ruff`/`mypy` per
`pyproject.toml`): `ruff format --check src tests` pass (160 files); `ruff check src tests` pass;
`cd body-layer && .venv/bin/mypy src` pass, no issues (70 source files); `pytest tests -q` —
**2401 passed, 4 xfailed**, matching `implementation.md`'s own claim exactly.

**aircraft-layer** (fresh `.venv`, same Python): `ruff format --check src tests` pass (69 files);
`ruff check src tests` pass; `mypy src` pass (26 source files); `pytest -q` — **409 passed**,
matching `implementation.md`'s claim exactly. `luac5.1 -p Export.lua` (syntax): pass. Bytecode
`GETGLOBAL` scan (`luac5.1 -l -p`): every global resolves to a real DCS/Lua API or stdlib name
(`GetDevice`, `safe_call`, `pcall`, `io`, `lfs`, `math`, `string`, `table`, `tostring`, `type`,
`LoGet*`, etc.) — no new Stage 4b helper (`push_slew_trace`, `slew_log_flush`,
`fmt_num_or_null`) leaks as a global.

audio-adapter was not touched by either range (confirmed: `git diff a85ae0a3..7feecd1a --stat --
audio-adapter/` is empty) — no checks owed there for this re-review.

### Verdict (re-review)

**APPROVED.** The required fix from the first pass is resolved and confirmed by independent
mutation; Stage 4b is sound, correctly scoped to logging only, answers `BL-B80`'s stated open
question from the data it will actually collect, and introduces no new tuning gap, no export-loop
risk, and no test gap at the wiring level (the same class of gap the first pass's required fix was
about). No outstanding required or optional items beyond the first pass's own (already-resolved)
optional refinements, which remain optional and unaffected by this work.

### Review Confidence (re-review)

Full read of both diffs in this re-review's scope; all format/lint/type/test commands for both
touched subprojects run directly against a freshly built `.venv` each, not taken on report; both
load-bearing write paths (review-fix wiring, Stage 4b `write_poll` call site) confirmed by actual
mutation + revert, not by inspection alone.
