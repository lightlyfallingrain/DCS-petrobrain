### Review Summary

Reviewed `fix/guidance-ready-edge` at tip `a5205b1d28c39312a4e23d619da8b6a6cb87ac5e` (one commit on
`main` `6dfece18`), against `plans/9k113-sight-pointing/plan.md` decision 2 ("only on change") and
`explore-notes.md` (~line 204, 2026-10-22 pilot direction).

The fix replaces `GuidanceUnitState.guidance_unit_ready_announced: bool` (a one-shot latch that
spoke on the first poll the lamp ever read lit, including a warm air start's very first sample,
and never spoke again) with `guidance_unit_ready_prev_observed: bool | None`, carrying the real
960 lamp's own previous-poll value. `CrewConsole.drain_guidance_unit_ready` now speaks exactly on
`previously_observed is False and ready_observed is True`; `None` (no prior observation) is
deliberately not treated as `False`, so a warm air start stays silent and a power cycle
re-announces.

**Traced the full chain, not just the diff:**
- `refresh_cockpit_switch_readback` (sight_effector.py:352-353) runs *before* the drain call each
  poll and is sticky on a missing sample (`ready_lamp if isinstance(ready_lamp, bool) else
  state.ready_observed`) — a poll with no lamp readback never resets `ready_observed` to `None`
  and so cannot manufacture a false edge or swallow a real one. Call order in `logger.py` (refresh
  at 3305, `is_sight_ready` at 3309, drain at 3324) confirms the drain reads the just-refreshed
  value, not a stale one.
- The call site moved out of `if is_sight_ready:` to run every poll, unconditionally — necessary
  and correctly justified: without it, an observed power-down (lamp false) would never update
  `guidance_unit_ready_prev_observed`, and the later rise would not register as an edge. `OBSERV`
  gating (`crew_console.sight_ready = is_sight_ready`) is untouched and still runs every poll as
  before — no change to that gate's timing.
- `reset_for_new_mission` re-invokes `__init__`, which resets `guidance_unit_state` to its declared
  default (`GuidanceUnitState()` → `ready_observed=None`, `guidance_unit_ready_prev_observed=None`).
  A mission restart into a cold cockpit therefore announces correctly on the real edge; a restart
  into a warm cockpit stays silent (first sample already lit, `previously_observed is None`).

**Mutation check (not just reading):** checked out the pre-fix versions of `crew_console.py`,
`sight_effector.py`, `logger.py` on top of the new tests and re-ran. Both new tests fail against
old code — the warm-air-start test fails on its real assertion ("Guidance unit ready." *is* spoken,
contradicting the fix's whole point); the power-cycle test fails because the old `GuidanceUnitState`
has no `guidance_unit_ready_prev_observed` field at all, so the fixture itself cannot construct
under the old API. The modified `test_takeoff_runs_the_guidance_unit_power_up_sequence_...` test
also fails against old code for the same reason. Restored the fix afterward; `git status
--porcelain` on the worktree confirms no residue. All three tests drive the real
`_run_crew_text_poll_loop` via the established fake-client/background-thread technique, not the
pure function in isolation.

Scope matches `plans/guidance-ready-edge/implementation.md` exactly: `sight_effector.py`,
`crew_console.py`, `logger.py`, `test_logger.py`, nothing else. No BL-B80 pointing, `sight_ready()`
semantics (still reads the real lamp), or OBSERV-gate change. No new behaviour-affecting constant,
so the tuning mechanism doesn't apply here. The spoken phrase itself ("Guidance unit ready.") is
unchanged crew output, not a new pilot-spoken STT vocabulary item, so `vocabulary.py` sync doesn't
apply. No durable dated/verbatim line was dropped from the comments touched — the old docstrings'
references to the originating plan/explore-notes point are preserved and the new ones correctly
state the bug being replaced and its date context.

### Required Fixes

None.

### Optional Refinements

- The pre-existing `test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` flake
  under `pytest-randomly` default ordering is confirmed unrelated: it lives in a different test
  function, in no file this diff touches, and git blame shows its own content predates this branch
  (`a5def59e`). Worth a `todo/backlog` entry if the implementer hasn't already filed one — it is
  outside this fix's scope either way. (Optional — not a blocker for this fix.)

### Verdict
APPROVED

### Review Confidence
Full read — all three changed production files and the full test diff read in full; checks run
(`ruff format --check`, `ruff check`, `mypy --strict`, full `pytest -q -p no:randomly` suite:
2445 passed, 4 xfailed, matching the implementer's own report); mutation-tested both new tests and
the modified existing test against the pre-fix code to confirm they actually exercise the bug
rather than passing vacuously.
