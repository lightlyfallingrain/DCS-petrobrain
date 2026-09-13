### Review Summary

Reviewed `feature/f10-crew-commands` (HEAD `984da0c`) against `plans/f10-crew-commands/plan.md`
and `plans/f10-crew-commands/implementation.md`, diff base `main` (`git diff main...HEAD`,
23 files, +1935/-16). Stages 1-3 (collector-side inbound channel, body-layer consumption, the Hook
script) are in scope; Stage 4 (live DCS acceptance) is correctly left to the user.

Scope matches the plan closely — no drift found. Module boundaries are respected: coordinate/DCS
internals stay in `aircraft-layer`, dispatch stays inside `CrewConsole`'s existing `_print` funnel,
no new cross-subproject coupling. Provenance is handled correctly (wall-clock-only is disclosed as
a deliberate, stated exception, not a silent gap). The Hook script's mechanism matches the
live-confirmed research findings exactly: `"scripting"` state (never `"mission"`/`a_do_script`),
the same `(result, success)` interpretation the probe used, fixed string literals only, the same
`package.path`/`cpath` extension as `petrobrain-overlay-hook.lua`, poll gating tied to
`onSimulationStart`/`onSimulationStop` with the timer reset, and a documented (not silently
assumed) idempotent-registration approach. Wire format agreement between the Hook script and
`F10CommandReceiver` is exact (`{"command": "<token>"}`, no trailing-newline dependency either
side). Test coverage for the new body-layer/aircraft-layer logic is thorough and exercises real
sockets/servers rather than mocks, matching this project's existing testing conventions.

One required fix: a genuinely broken automated test (not a Hook/DCS-only gap) that fails
deterministically in this review's environment, 4/4 runs, with a different observed order each
run — this is exactly the class of thing Reviewer is meant to catch before it reaches DoD.

### Required Fixes

- **`aircraft-layer/tests/test_f10_command_receiver.py:53-64`
  (`test_all_allowed_commands_are_enqueued`) fails deterministically in this review environment —
  reproduced 4/4 runs, `pytest aircraft-layer/tests -q` via `body-layer/.venv`'s interpreter,
  `108 passed, 1 failed` every time, with a *different* received order each run (`cancel_task`
  first, then `scan_forward` first, etc.). The test asserts the three drained tokens come back in
  send order (`assert drained == list(ALLOWED_COMMANDS)`), but `_send` (lines 18-23) opens a brand
  new `socket.socket(...)`/`sendto`/`close()` for every datagram instead of reusing one socket
  across the loop at lines 59-60. UDP delivery order across independently-created sockets is not
  guaranteed by the OS even on loopback, and this environment reorders them reliably. This is not
  a bug in `F10CommandQueue`/`F10CommandReceiver` themselves — `test_f10_commands_poll_drains_queue_
  oldest_first` in `test_f10_command_api.py` proves the queue's own FIFO ordering directly via
  `queue.push()`, no sockets involved, and that test passes every run. It is also not representative
  of the real Hook script: `petrobrain-f10-commands-hook.lua`'s `sendToken` (lines 178-187) opens
  `sendSocket` once (`if sendSocket == nil then sendSocket = socket.udp() end`) and reuses it for
  every token sent from one `pollAndForward` call, which is a materially different, much
  more order-preserving pattern than the test's one-socket-per-datagram loop. Fix by having `_send`
  accept (or the test construct) one shared socket reused across the three sends — mirroring the
  real Hook script's own socket lifecycle — or by asserting the drained set/order-independent
  equality instead of relying on cross-socket UDP delivery order. This is a required fix under the
  project's own Definition of Done ("All checks pass") and this review's explicit instruction to
  run checks itself rather than trust the implementer's reported numbers.

### Optional Refinements

- `petrobrain-f10-commands-hook.lua`'s `onSimulationStart` (lines 199-204) calls `registerF10Menu()`
  without wrapping it in its own `pcall`, unlike `onSimulationFrame`'s `pollAndForward` (line 215),
  even though `dostring_in`'s own internal `pcall` (in the shared `dostring` helper, lines 165-171)
  means this is very unlikely to raise in practice. Wrapping it the same way `onSimulationFrame`
  already does would be pure defense-in-depth consistency, not a fix for an identified failure mode
  (optional).
- The plan's Risks note suggested a `PB_F10_REGISTERED` flag guard for idempotent registration; the
  implementation instead uses `missionCommands.removeItem({"Petrovich"})` (wrapped in `pcall`)
  before re-adding. This is a reasonable, arguably more robust alternative (it also recovers from
  any external mutation of the menu, not just a double `onSimulationStart`), and it is disclosed
  clearly in both the Hook file's own header comment and `implementation.md`'s "Notable
  Discoveries" — not a silent deviation. Not a required fix, but worth confirming during Stage 4's
  live "mission-restart check" specifically, since `removeItem`'s non-`ForGroup` form was not
  independently live-probed by the research doc (already flagged as a Risk in the plan itself).

### Check Results

**aircraft-layer/** (via `body-layer/.venv`'s interpreter, stdlib-only subproject so no dependency
conflict — no `aircraft-layer/.venv` exists, matching the implementer's own noted finding):
- `ruff format --check`: pass (33 files already formatted)
- `ruff check`: pass
- `mypy src` (strict): pass, 14 source files, no issues
- `pytest -q`: **1 failed, 108 passed** — see Required Fixes above (reproduced 4/4 runs)
- `luac5.1 -p` (Lua 5.1.5) on all 11 `dcs-export/*.lua` files, including
  `petrobrain-f10-commands-hook.lua`: pass

**body-layer/** (`.venv`, run from inside `body-layer/` per its CLAUDE.md CWD note):
- `ruff format --check`: pass (64 files already formatted)
- `ruff check`: pass
- `mypy src` (strict): pass, 30 source files, no issues
- `pytest -q`: pass, 488 passed

### Deep-dive findings (per the orchestrator's specific asks)

1. **Hook script vs. the working probe** — `"scripting"` state used throughout (never
   `"mission"`/`a_do_script`); `dostring`'s `(callOk, result, success) -> (success ~= false,
   result)` interpretation is byte-identical to the probe's; `REGISTRATION_CODE`/`POLL_CODE` are
   both fixed string literals with no interpolation from any runtime value; `package.path`/`cpath`
   extension is copied verbatim from `petrobrain-overlay-hook.lua`; polling is gated by
   `simulationRunning` (set `true`/`false` in `onSimulationStart`/`onSimulationStop`) with
   `nextPollAt` reset to `0` at `onSimulationStart`; registration idempotency uses `removeItem`
   before `addSubMenu`/`addCommand` (unverified live, disclosed — see Optional Refinements above);
   nothing in the callback chain appears able to raise uncaught into a DCS callback (see the one
   Optional Refinement above for the one spot without a redundant `pcall`).
2. **Wire format** — Hook sends `JSON:encode({command = token})` as one UDP datagram, no trailing
   newline; `F10CommandReceiver._handle_datagram` does `json.loads(data.decode("utf-8"))` directly
   on the raw datagram bytes, no newline-delimiting assumption on either side. Confirmed matching.
3. **Receiver thread lifecycle / queue bound / drain-once** — `F10CommandReceiver.serve_forever`
   blocks on `recvfrom`; `close()` closes the socket, which raises `OSError` inside the blocked
   `recvfrom` and ends the loop cleanly — the same shutdown shape as `CollectorServer`. `__main__.py`
   opens it before starting its thread and closes it in the `finally` block alongside the other
   senders/servers. `F10CommandQueue` is bounded (`_MAX_QUEUE_LEN = 64`, deque `maxlen`), and
   `drain_all` uses repeated `popleft()` (not snapshot-then-clear) so a concurrent `push` from the
   receiver thread can't be dropped between snapshot and clear. `/f10_commands/poll`'s drain-once
   semantics are directly tested (`test_f10_commands_poll_drains_only_once`) and documented as an
   explicit exception to every other endpoint's idempotent-read contract, both in `api/server.py`'s
   docstring and `WORKFLOW.md`.
4. **body-layer dispatch** — `handle_f10_command` routes all three tokens through the same `_print`
   funnel `handle_line`/`drain_events` already use, confirmed by
   `test_handle_f10_command_pushes_to_overlay_via_the_print_funnel`. `scan_forward` really reaches
   `trigger_petrovich_search("forward")` in `--crew-text` mode — confirmed by reading `logger.py`'s
   `--crew-text` branch (`CrewConsole(..., aircraft_client=aircraft_client, ...)` is unconditional,
   not gated on `--f10-commands`) and by `test_scan_forward_triggers_a_live_search_via_aircraft_
   client`. `--f10-commands` without `--crew-text` is unreachable by construction — the flag is only
   read inside `main()`'s `if args.crew_text:` branch (`_run_crew_text_poll_loop`'s
   `f10_commands_enabled` parameter), so passing it alongside `--console` or neither is a silent
   no-op rather than an error; this matches `--overlay`'s own established "meaningless without
   --console/--crew-text" posture in this codebase, not a new inconsistency. Poll failures are
   isolated via `_poll_f10_commands`'s own `try/except AircraftLayerError` (log-and-continue),
   mirroring the BL-2.5 overlay-push loop's per-call isolation shape.
5. **Docs** — `aircraft-layer/CLAUDE.md`, `body-layer/CLAUDE.md`, and `aircraft-layer/WORKFLOW.md`
   all correctly describe F10 as a second inbound/write-adjacent path, not the sole one; the
   Stage 4 deploy steps (autoexec.cfg opt-in, port 7794, the no-DCS-required manual `python3 -c`
   UDP-send check) are internally consistent with the actual receiver/port/schema. The one gap
   found (`--crew-text --f10-commands` never appears as one fully-composed example command in
   `body-layer/CLAUDE.md`, only as prose "Add `--f10-commands` alongside `--crew-text`") is not a
   defect introduced by this feature — `--console`/`--overlay` follow the exact same
   prose-only-addition documentation convention already, so this is consistent with existing style,
   not a new gap.

### Verdict
APPROVED WITH MINOR FIXES

The one required fix is a test-only reliability defect (not a production code or Hook-script bug)
and is small and mechanical to fix (reuse one socket across the three sends, or assert an
order-independent equality). Nothing else in Stages 1-3 needs rework; Stage 4 remains correctly
deferred to the user's live DCS session.

### Review Confidence
Full read — every changed file was read in full (both Hook scripts including the throwaway probe
for comparison, all new/changed Python source and tests in both subprojects, both `CLAUDE.md`
diffs, `WORKFLOW.md`'s new section, the plan, implementation.md, and the research doc's Findings
7-11). All four touched-subproject check commands were run directly by this review, not taken from
the implementer's reported numbers — which is how the required-fix test failure was found.
