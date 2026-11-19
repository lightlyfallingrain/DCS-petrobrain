### Review Summary

Branch `fix/handover-ack-seq`, reviewed at `5487ff0f061079e1b7c3c1546c913e08e6be95b5` (two bug
fixes on top of `bba8d03b`, per `plans/flight-control/debug.md`):

- **88e0203e** — the take-ack never matches (`take_seq` compared the local per-take counter
  against Lua's own wire seq) and the ack timeout left Lua `active` with belief back at `PILOT`
  and no recovery.
- **5487ff0f** — `core.lua`'s `fmt_num_or_null` emitted every number (including sequence
  counters) as `%.5f`, so `fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq`/`apw_goal_seq`/
  `apw_cbtm_seq` went out as floats and were rejected whole by the strict-`int` schema fields —
  the actual reason both modes' telemetry was dropping silently.

Both fixes are correctly scoped, each addresses the diagnosis in
`docs/acceptance/2026-11-19-mode1-handover-feedback.md`, and both are backed by tests that fail
on the pre-fix code (verified by mutation below, not just read). All mechanical checks pass. One
required fix: fix (b)'s ack-timeout "release" can be silently discarded by a same-poll "take"/
"release" command, reproduced below.

### Required Fixes

- **The ack-timeout's self-queued `release` (fix b) can be clobbered by a player handover
  command recognised in the same poll's transcript batch, leaving Lua `active`/flying with no
  release ever reaching it.** `CrewConsole.drain_flight_control` (`crew_console.py:5603`) queues
  `self.flight_control_transition = "release"` on the `TAKING → PILOT` timeout; `CrewConsole.
  take_controls`/`release_controls` write the *same* one-shot field and are dispatched later in
  the *same* poll, from `_poll_transcripts` (`body.py:5915`), which runs after the flight-control
  block (`body.py:5262-5266`). `_apply_flight_control` only sends whatever is in that field at
  the *next* poll's top, so a "take"/"release" transcript processed this poll overwrites the
  queued release with no wire message ever carrying it. Reproduced directly against this
  worktree's code (not read-only):

  ```python
  console.flight_control_state = FlightControlState(
      phase="TAKING", take_seq=1, took_at_sim=0.0, pending_take_says="I have controls.",
      lua_mode="active", lua_take_seq=99,
  )
  console.drain_flight_control(100.0, parked_active=False)
  # -> phase=PILOT, flight_control_transition="release" (queued, not yet sent)
  console.take_controls("I have controls.")
  # -> flight_control_transition="take"  (the queued "release" is gone, never sent)
  ```
  Lua never received the release and is still "active" (or, concretely, `take_controls`'s own
  `cmd == "take"` handler — `flight_control.lua:1345` — is a no-op while `fc_mode == "active"`,
  so the *new* take is also silently ignored on the wire side, and belief re-times-out ~2 s
  later with a second confusing "Unable, not ready."). This directly reopens the symptom fix b
  was written to close ("Lua stays active flying the axes while belief says PILOT"), just in a
  narrower, same-poll window — exactly what the brief's check (1) asked about, and it is real,
  not merely a race in theory: two transcripts landing in one poll's batch (a quick retry, a
  backlog, or a near-simultaneous double utterance) are an ordinary occurrence for this
  surface. Fix b's own docstring claims this scenario is closed ("so belief and the aircraft
  never disagree about who flies for long") — that is only true when nothing else writes
  `flight_control_transition` before the next poll's send.

  No test exercises this interleaving (the two new test classes for fix b/c each isolate
  `drain_flight_control`/`release_controls` on their own, never alongside a same-poll `take_
  controls`/`release_controls` call). Recommend either: giving the system-queued release
  priority over a same-poll player transition (don't let `take_controls`/`release_controls`
  overwrite a transition `decide_flight_control` itself just queued this poll), or sending it
  synchronously inside `drain_flight_control` rather than via the shared one-shot field, plus a
  regression test for the interleaving above.

### Optional Refinements

- **Fix (c) from `PILOT` with a stale `lua_mode` mirror can speak a redundant "You have
  controls."/send a redundant (harmless, idempotent on the Lua side) release** — checked
  specifically per the brief's item (2). The one real window is the ordinary one-poll
  eventual-consistency gap after any release (fix b's own, or an explicit "I have controls"):
  `release_controls` flips belief to `PILOT` immediately but `lua_mode` only updates on the next
  successful `advance_flight_control_state` readback, so a second "I have controls" uttered
  inside that single poll re-triggers `acted=True` and a second spoken line. Lua's own `cmd ==
  "release"` handler is unconditional (`flight_control.lua:1374`, sets `fc_mode = "off"`
  regardless of current mode), so the resend is a no-op on the wire — this is cosmetic
  (occasional double "You have controls."), not a correctness or safety issue, and a mission
  restart resets `lua_mode` to `None` alongside `phase` (`CrewConsole.reset_for_new_mission`
  re-runs `__init__`, `flight_control_state` is not in the pass-through list), so the mirror
  cannot go stale across a restart. Not required; worth a one-line note in `release_controls`'s
  docstring if the Implementer wants to pre-empt the next reader asking the same question.
- A readback outage (`AircraftLayerError` from `advance_flight_control_state`, a different HTTP
  verb than the `write_flight_control` POST fix (a)/(b) use) can leave `lua_mode` stuck stale for
  longer than one poll, which would let the same cosmetic double-speech happen further from the
  actual event — same analysis, same non-issue, already an accepted general degradation mode for
  every `lua_*` mirror in this module, not something this patch introduced.

### Verification of the brief's specific checks

1. **Late Lua ack after the timeout-queued release** — handled correctly *when nothing else
   writes `flight_control_transition` in between*: the next poll's `_apply_flight_control` runs
   before that poll's own `drain_flight_control`/transcript dispatch, so a release queued by the
   timeout is sent before a freshly-arrived ack could be mis-acted on. The only way this breaks
   is the interleaving-command clobber above (Required Fix).
2. **Fix c from `PILOT` with a stale `lua_mode` mirror** — benign, see Optional Refinements.
3. **Unpark-take path and `wire_seq` reconciliation after a body-layer restart** — consistent
   with fix (a). `_apply_flight_control`'s `wire_seq = max(wire_seq, lua_last_cmd_seq)`
   reconciliation (`body.py:3728-3731`, pre-existing, security-m1-m2.md Finding A) runs
   unconditionally *before* fix (a)'s `take_seq=next_seq` branch, so a restart is caught up
   first and fix (a) always computes from the reconciled `wire_seq`. The unpark-take path
   (`decide_flight_control`'s `OVERLAY → ACTIVE`) never goes through `_apply_flight_control`'s
   `"take"` branch at all — it adopts `state.lua_take_seq` directly — so fix (a) cannot touch it,
   confirmed by reading, matching the debug report's own claim.
4. **Any other Lua-module/schema pair with the same int/float mismatch, or `nan` from another
   encoder** — independently re-swept: `grep`'d every `fmt_num_or_null`/`fmt_int_or_null` call
   site across all five touched-and-untouched `.lua` modules against every strict-`int` schema
   field (`sight_servo.py`, `watched_args.py`, `petrovich_wheel.py` all tolerate `int | float`,
   confirmed by reading their own validators) — only the five fields the fix already changed are
   both `fmt_*`-formatted and `int`-strict. No other pair found.
5. **Would the new tests fail on the old code** — yes, confirmed by mutation, not by reading:
   temporarily restored `body-layer/src/belief/{flight_control,crew_console}.py` and `body.py` to
   their pre-fix (`bba8d03b`) content and re-ran the four new/changed assertions targeting fix
   (a)/(b)/(c) — all four failed exactly as the debug report describes (`take_seq` stayed 6
   instead of 3; `release_controls` from `PILOT` with `lua_mode="active"/"taking"` stayed a
   silent no-op; the ack-timeout queued no release). Files restored to the reviewed commit
   afterwards (confirmed by a clean `git status --porcelain`).

### Checks run

- `aircraft-layer`: `ruff format --check` (86 files), `ruff check` (clean), `mypy --strict`
  (28 source files, clean, run from `aircraft-layer/`), full `pytest tests -q` — **997 passed**
  (matches the debug report).
- `body-layer`: `ruff format --check` (227 files), `ruff check` (clean), `mypy --strict`
  (92 source files, clean, run from `body-layer/`), full suite (`pytest tests -q -m "not slow"
  -p xdist -n auto`) — **3667 passed, 4 xfailed** (matches the debug report; the 4 xfailed are
  pre-existing/unrelated, not newly introduced).
- `luac5.1 -p` on `core.lua`/`flight_control.lua`/`ai_pilot_wheel.lua` — all pass.
- `luac5.1 -l -p` GETGLOBAL sweep on the same three files — `fmt_int_or_null` reads as a bare
  global in `flight_control.lua`/`ai_pilot_wheel.lua` exactly like `fmt_num_or_null` already
  does (intentional cross-module `_G` access); no collision with a file-local of the same name.

### Verdict

**NEEDS REVISION** — one required fix (the same-poll `flight_control_transition` clobber above).
Everything else reviewed is sound: both root-cause diagnoses are correct, the fixes are scoped to
exactly what the diagnosis calls for, tests are real (verified failing on pre-fix code by
mutation, not merely read), all four subprojects' mechanical checks and the full test suites of
both touched subprojects pass, and the Lua-side sweep for the second bug's defect class is
independently confirmed exhaustive.

### Review Confidence

Full read — both commits' diffs read in full against the debug report and the plan's Decisions
13/22/24; the ack-timeout/take-clobber race was found and confirmed by direct mutation (editing
`FlightControlState` and calling the real methods), not by inspection alone; the "would the new
tests fail on old code" question was answered the same way (temporarily reverted the three
touched body-layer source files to `bba8d03b` and re-ran the new assertions). Mode 2's
`ai_pilot_wheel.py` Python side is genuinely untouched by this branch (confirmed by the diff
stat) and was not re-reviewed beyond that.
