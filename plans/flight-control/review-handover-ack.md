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

---

### Re-review

Branch `fix/handover-ack-seq`, re-reviewed at `9bf108618c942107731951a9f6e7f9d169810919`
(one commit on top of `5487ff0f`, fixing this file's Required Fix above). Scope: that one
commit's diff (`body-layer/src/belief/crew_console.py`, `body-layer/src/body.py`, and the two
touched test files) only.

**The Required Fix is correctly addressed.** The ack-timeout's self-queued release now lives on
its own field, `CrewConsole.flight_control_system_release_pending: bool`, which
`_reset_one_shot_command_state` (the preamble every `handle_command` dispatch runs, including for
a command unrelated to flight control — a broader hazard than the original finding's own
`take_controls`/`release_controls` framing, since *any* recognised command this same poll would
have cleared the old field) never touches. `_apply_flight_control` checks it first: when set, it
sends `"release"` alone and leaves `flight_control_transition` untouched (deferred, not
discarded) rather than send both transition-class messages in the same poll. Confirmed by
mutation, not just reading: reverted `crew_console.py`/`body.py` to `e6eaed94` (this file's own
reviewed-at commit) with the new test files in place —
`test_flight_control.py::TestDrainFlightControlSendsReleaseOnAckTimeout::
test_a_same_poll_take_does_not_clobber_the_queued_release` and
`test_body_flight_control.py::TestApplyFlightControl::
test_a_system_release_is_sent_alone_and_a_queued_take_is_deferred` both fail on the old code with
exactly the symptom this fix closes (`AttributeError` — the field didn't exist yet; then `take`
sent instead of `release`), and both pass on `9bf10861`. Files restored afterwards, confirmed by a
clean `git status --porcelain`.

#### Required Fix (new, documentation-only — no behaviour change needed)

- **The comment justifying the deferral (not the deferral itself) states a wire mechanism that
  does not exist.** `_apply_flight_control`'s docstring (`body.py:3690-3692`) and this commit's
  own message both say the reason to send the release alone and defer the take is "Lua's own
  single most-recent-command slot" — i.e., implying Export.lua only ever acts on the latest
  datagram and an earlier one would be overwritten/lost. Checked against the actual mechanism
  (the brief's check (1)): `Petrobrain/commands.lua`'s `poll_command_socket`
  (`commands.lua:101-135`) drains **every** queued UDP datagram each frame in a `while true do
  local data, _err = command_socket:receivefrom() ... end` loop and dispatches each one through
  its own handler in receipt order — there is no slot, no overwrite, no "most recent wins."
  `flight_control.lua`'s own per-message dedup (`handle_flight_control_command`,
  `if seq <= fc_last_cmd_seq then return end`) is an ordinary monotonic-seq guard against a
  stale/duplicate/out-of-order datagram, not a single-command buffer — and if a `"release"`
  (seq N) and a `"take"` (seq N+1) actually arrived in that order, both would be applied
  correctly: `"release"` unconditionally sets `fc_mode = "off"` (`flight_control.lua:1313-1338`),
  and the following `"take"` would then see `fc_mode == "off"` and transition normally
  (`flight_control.lua:1340-1353`) — the no-op guard on `"take"` only fires when `fc_mode` is
  already `"active"`/`"taking"`, which a preceding `"release"` just cleared. The real (and still
  legitimate) risk the deferral guards against is **UDP datagram reordering between two
  back-to-back `write_flight_control` round trips** (body-layer → collector HTTP → collector →
  Export.lua loopback UDP, two separate sends) arriving out of order at Export.lua — if the
  `"take"` somehow arrived first, it would be silently ignored as the no-op case and the
  following `"release"` would then release a take that was never actually accepted, which is a
  real (if narrow) failure mode on an unordered transport. The chosen fix (defer one poll) is
  still the right, conservative call either way — this is not a request to change behaviour —
  but the comment should name the actual risk (datagram-ordering risk across two separate sends
  on an unordered transport) rather than a "single most-recent-command slot" that `commands.lua`
  does not implement. Left as-is, a future reader trusts a fabricated mechanism and may reason
  from it the next time this code is touched — exactly the "X, so Y" docstring risk the
  Reviewer's own checklist calls out. One-line fix: reword `body.py:3689-3692` (and, optionally,
  the commit's own rationale is already landed and does not need a new commit by itself, but the
  next touch to this area should carry the correction).

#### Verification of the brief's remaining checks

2. **Deferred take's `took_at_sim`/ack-timeout clock** — `take_controls` sets `took_at_sim` at
   decision time (the poll the player's "take" is recognised), not at actual wire-send time. In
   the interleaving this fix handles, the wire send is deferred by one additional poll beyond the
   ordinary one-poll lag (`take_controls` happens mid-poll N after `drain_flight_control`; the
   queued release consumes poll N+1's `_apply_flight_control`; the take itself is finally sent at
   poll N+2) — so the ack-timeout clock (`HANDOVER_ACK_TIMEOUT_S`, 2 s) starts up to ~2 polls
   earlier relative to when Lua actually sees the take than it otherwise would. At any ordinary
   poll cadence this is negligible against a 2 s window; not a defect, not required, and already
   effectively covered by this file's original Optional Refinements on the same clock.
3. **A deferred player "release" after a system release** — still harmless. If
   `release_controls` is also called this same poll (e.g., a redundant "I have controls"/
   "release" immediately after the ack timeout), it writes `flight_control_transition =
   "release"` on the untouched field, same as before; the next poll sends the system release
   alone (pending cleared) and leaves that queued `"release"` in place, which the poll after
   sends — Lua's own `"release"` handler is unconditional and idempotent regardless of current
   `fc_mode`, so this is at most a redundant no-op send, never a correctness issue. No change
   from this file's existing Optional Refinements analysis.
4. **Mission restart / `OVERLAY` clearing of the new flag** — both handled. The `OVERLAY` branch
   in `_apply_flight_control` now clears `flight_control_system_release_pending` alongside
   `flight_control_transition`/`flight_control_goal_transition` (all three, same block). A mission
   restart needs no special-case handling: `flight_control_system_release_pending` is a plain
   dataclass field, absent from `reset_for_new_mission`'s explicit pass-through list, so
   `CrewConsole.__init__` re-running resets it to its declared default (`False`) exactly like
   `flight_control_transition`/`flight_control_state` already do — confirmed by reading the field
   declaration and the pass-through list named in `reset_for_new_mission`'s own docstring.
5. **Does the new interleaving test fail on `e6eaed94`** — yes, confirmed by mutation above, not
   by reading.

#### Checks run

- `body-layer`: `ruff format --check src tests` (227 files, already formatted), `ruff check src
  tests` (all checks passed), `mypy src` (run from `body-layer/`, strict, success — 92 source
  files), targeted tests (`test_flight_control.py`, `test_body_flight_control.py`,
  `test_crew_console.py`, `test_body.py` — 591 passed), full suite (`pytest tests -q -m "not
  slow" -p xdist -n auto`) — **3669 passed, 4 xfailed** (2 more passing than the prior review's
  3667, exactly the two new tests this commit adds; same 4 pre-existing xfails).
- `aircraft-layer` untouched by this commit (confirmed by the diff stat) — not re-run.

#### Verdict

**APPROVED WITH MINOR FIXES** — the original Required Fix is correctly and completely addressed,
verified by mutation. One new, documentation-only required fix: correct the "single
most-recent-command slot" claim in `body.py`'s `_apply_flight_control` docstring (and the parallel
claim in this commit's own message) to name the actual risk (UDP datagram-ordering between two
back-to-back sends on an unordered transport), which is checkable directly against
`commands.lua`'s `poll_command_socket` and does not exist as described. No behaviour change is
needed — the deferral itself is the right, conservative choice regardless of which risk motivates
it.

#### Review Confidence

Full read — the one-commit diff read in full against this file's own Required Fix and the
brief's five numbered checks; the fix's correctness was verified by mutation (reverted
`crew_console.py`/`body.py` to `e6eaed94` with the new tests in place, confirmed both new tests
fail with the exact pre-fix symptom, restored and confirmed clean `git status --porcelain`); the
single-most-recent-command-slot claim was checked directly against `Petrobrain/commands.lua`'s
`poll_command_socket` and `Petrobrain/flight_control.lua`'s `handle_flight_control_command`, not
taken on the commit message's word.
