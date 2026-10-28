# Review: fix/mission-start-first-event

Commit reviewed: `eb177d52` ("Fire mission-start triggers on the first mission seen arriving"),
one commit on local `main` (`faf29212`). No Architect plan exists for this directory (bug-fix flow,
per `AGENTS.md`'s Debugger → Reviewer → ... sequence) — reviewed against the commit message's own
stated user decision and `body-layer/CLAUDE.md`'s updated section.

### Review Summary

The fix adds `ConsolePerceptionRunner.mission_start_absent_seen`: `_check_for_new_mission` now
treats a mission-start event that first appears *after* the collector was polled and reported
none (while `last_mission_start_sequence` was still `None`) as a genuine start, instead of
silently baselining it as before. An event already present at the very first poll (body-layer
started mid-mission) still baselines silently, unchanged. This correctly fixes the reported bug
(usual launch order — body-layer up, then mission started — never fired `mission-start`/
`mission-start-in-air`).

The new branch reuses the existing reset/arm/theatre-switch/log-reroll machinery unchanged
(`_reset_mission_state`, `_maybe_switch_theatre`, `pending_mission_start_fire`/
`pending_mission_start_in_air_check`, `mission_start_fresh_sample_baseline_t_sim`) — there is no
separate code path for "first arrival" beyond the admission decision itself, which keeps the
change small and avoids a second mechanism.

Specific points from the task brief:

- **`pre_reset_t_sim`/`mission_start_fresh_sample_baseline_t_sim` on the first-arrival path.**
  Traced both sub-cases. (a) No telemetry ever flowed before the event arrives: `last_t_sim` is
  still `None`, so `pre_reset_t_sim` is `None`, and the poll block's `baseline is None or
  last_ownship_state.t_sim != baseline` (line ~3539) short-circuits `True` on `baseline is None` —
  the very first real sample resolves immediately, correctly. (b) Telemetry already flowed before
  the event arrives (plausible: `_check_for_new_mission` runs before `run_once()` each poll, so a
  poll can see the collector still empty while that same poll's telemetry call already succeeds;
  "body-layer up, mission started" is exactly the launch order where this can happen for a poll or
  two around the real mission start): `pre_reset_t_sim` holds a real `t_sim` from *this* mission
  (there is no other mission it could be from, since this is the first-ever event), so it is never
  "a sample from before this mission." Using it as the baseline costs at most one extra poll
  before `MISSION_START_IN_AIR` resolves (the next poll's `t_sim` must differ from it, same `!=`
  logic and same bounded-fallback backstop already used for genuine restarts) — conservative, not
  incorrect.
  **Gap**: this composite scenario (absent → telemetry flowing → event arrives) is not exercised
  by any test. The three new unit tests in `test_mission_start_reset.py` call
  `_check_for_new_mission` with `crew_console=None` and never touch `run_once()`/`last_t_sim`, so
  `last_t_sim` is always `None` in them regardless; the poll-loop integration tests in
  `test_body.py` (`test_ground_mission_start_fires_mission_start_only`,
  `test_air_mission_start_fires_both_mission_start_triggers_not_takeoff`, etc.) all use
  `_settled_mission_start_runner`, which hand-sets `last_mission_start_sequence = 1` directly and
  so never exercises the `mission_start_absent_seen` branch at all. I confirmed by mutation that
  the branch's own admission logic (`and not runner.mission_start_absent_seen`, and the
  `mission_start_absent_seen = True` assignment) is each defended by
  `test_check_for_new_mission_fires_on_the_first_event_seen_arriving` — both mutations fail that
  test. What is *not* independently defended is the "first-arrival + telemetry already flowing"
  composite at the real poll-loop level, i.e. a regression that broke only that composite (as
  opposed to the admission decision itself, or the shared downstream baseline/reset code, both of
  which already have coverage) could land unnoticed. Listed as optional below rather than required
  because the downstream code it would need to break is the same code the restart tests already
  cover by mutation.

- **`crew_console.on_ground` on the resolving poll.** Unchanged by this diff — `on_ground` is
  recomputed from `runner.last_ownship_state` unconditionally inside the
  `if runner.last_t_sim is not None: ... if runner.last_ownship_state is not None:` block, *before*
  the `mission_start_resolving` block reads it. Correct on both the first-arrival and genuine-
  restart paths, same code either way.

- **`mission_start_absent_seen` not in `reset_for_new_mission`'s preserved-field docstring list.**
  Confirmed harmless two ways: (1) it is an ordinary `init=True` dataclass field with a plain
  default (`False`), not passed as a constructor kwarg by `reset_for_new_mission`'s re-invoked
  `__init__`, so it resets to `False` automatically, same mechanism `last_mission_start_sequence`
  already relies on; (2) this is not just reasoning — `test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest`
  enumerates `dataclasses.fields()` mechanically and poisons/checks every non-preserved field,
  so `mission_start_absent_seen` is covered by that test automatically, and it passes. The
  docstring's own enumerated "everything else" list is just missing the name — a documentation
  completeness nit, not a correctness gap (optional below).

- **Log format `%d` → `%s`.** Necessary, not cosmetic: on the first-arrival path the log line is
  reached with `runner.last_mission_start_sequence` still `None` (the `sequence == None` equality
  check is `False`, so execution falls through to the log call before the field is reassigned a
  few lines later). Reproduced directly: `logger.info("... %d -> %d", None, 1)` raises
  `TypeError: %d format: a real number is required, not NoneType` inside `logging`'s own
  `getMessage()` — swallowed by `logging`'s default error handler (prints "--- Logging error ---"
  to stderr, does not crash the process), but it would have meant this exact log line silently
  never explains itself on the very scenario this fix exists for. `%s` is correct.

- **Log reroll / theatre switch on this path.** Both run through the same post-reset code
  (`_reroll_run_logs` is called by the caller whenever `_check_for_new_mission` returns `True`;
  `_maybe_switch_theatre` is called unconditionally inside it after a reset). No special-casing
  needed or present. Rerolling on the very first mission is actually the desired behaviour here,
  not a surprise: it closes out whatever log stamp `main()` opened at process start (before any
  mission existed) and opens a fresh one stamped at the real mission start, consistent with user
  decision 5's "per mission" framing. The theatre switch is a no-op in the overwhelmingly common
  case (mission theatre already matches the CLI-supplied `--theatre`), and behaves identically to
  the restart case otherwise — no asymmetry.

- **Tests.** 28/28 pass in `test_mission_start_reset.py`; full suite 2702 passed, 4 xfailed (one
  pre-existing flaky test per the task brief, `test_check_for_new_mission_keeps_the_traceback_for_a_non_connection_failure`,
  did not flake this run). Mutation-verified the two lines that implement the fix's actual decision
  (dropping `and not runner.mission_start_absent_seen` from the admission guard, and deleting the
  `mission_start_absent_seen = True` assignment) — both independently fail
  `test_check_for_new_mission_fires_on_the_first_event_seen_arriving`. The "event already present
  at first check still baselines" case and "absent seen only *after* the baseline is taken (mid-
  mission collector restart) does not retroactively arm" case are both covered by dedicated tests.

- **Docs.** `body-layer/CLAUDE.md`'s mission-start paragraph is updated accurately — including a
  side fix of an already-stale sentence ("No sequence file ships for either new trigger this cut")
  to reflect `97bad8fd`'s `mission-start-in-air.md`; confirmed that file exists at
  `body-layer/config/sequences/mi-24p/mission-start-in-air.md`. No new citation to a
  `plans/<feature>/plan.md` that doesn't exist (checked per prior review finding on this exact
  failure mode) — the diff's only `plans/` reference is the pre-existing, unchanged
  `plans/effector-sequences/explore-notes.md` citation, which exists.

- **Invariants / scope.** No DCS-internals claim added, no new tunable constant (no new
  behaviour-affecting literal — `mission_start_absent_seen` is state, not a tunable magnitude), no
  coordinate math, no writes to the DCS install, no new vocabulary. Nothing staged or left
  uncommitted (`git status` clean in the feature worktree). Change is confined to `body.py`,
  its own test file, and `CLAUDE.md` — correct module, no scope drift, no unnecessary abstraction
  (the fix is one new field, one new conditional, no second mechanism).

### Required Fixes

None.

### Optional Refinements

- Add one poll-loop-level test (`test_body.py`, alongside `test_ground_mission_start_fires_mission_start_only`/
  `test_air_mission_start_fires_both_mission_start_triggers_not_takeoff`) that starts a runner with
  `last_mission_start_sequence` still `None` and `mission_start_sequence = None` on the fake
  aircraft client, lets a telemetry poll or two land first, then sets `mission_start_sequence = 1`
  and `altitude_agl_m` airborne — asserting `MISSION_START_IN_AIR` actually fires. This is the
  literal scenario the user reported broken; the current tests prove the admission decision and
  prove the shared downstream machinery (via the restart tests), but nothing exercises the two
  composed end-to-end from a cold `ConsolePerceptionRunner`. Not required because every line
  involved is independently covered by mutation-tested tests elsewhere in the suite.
- Add `mission_start_absent_seen` to `reset_for_new_mission`'s docstring's "Everything else ...
  resets to its declared default" enumerated field list. Purely a documentation completeness nit —
  the field is in fact covered by `test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest`,
  which enumerates `dataclasses.fields()` rather than the docstring's hand list, so nothing is
  actually unverified; the docstring just reads as exhaustive when it currently is not.

### Verdict
APPROVED

### Review Confidence
Full read — diff is small (3 files, ~108 lines). Read `_check_for_new_mission`,
`_maybe_switch_theatre`, `_reroll_run_logs`, and the relevant poll-loop block
(`_run_crew_text_poll_loop`'s mission-start-resolving section) in full, not just the diff hunks.
Confirmed `ConsolePerceptionRunner`'s reset completeness mechanically (ran the existing
`dataclasses.fields()`-enumerating test, which already covers the new field) rather than by
reasoning alone. Mutation-tested the two lines that implement the actual fix decision, both caught
by the existing test suite. Ran `ruff format --check`, `ruff check`, `mypy --strict` (via
`cd body-layer && mypy src`), and the full `pytest` suite from `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`
against the feature worktree — all clean (2702 passed, 4 xfailed, no flake this run).
