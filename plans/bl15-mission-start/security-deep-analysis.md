## Security Deep Analysis: bl15-mission-start (BL-15 Stage 1 batch)

Scope: the whole batch merged to `feature/bl15-mission-start` tip `ea5f77fc`, diff base `eab86662`
(this role's own Mode 1 plan-review commit) — all three implementation batches and both Reviewer
passes (Batch 1 APPROVED, Batch 2 APPROVED WITH MINOR FIXES, Batch 3 addressing that required fix
plus the `fired_on_tracker` refinement). This is the one security pass for the batch, per root
`CLAUDE.md`'s "once per batch of stages actually executed together" rule.

Branch address verified first: worktree `HEAD` (`89ca6c2a`) was a strict ancestor of the named tip;
`git merge --ff-only ea5f77fc1f7791fdad88c9ef406cd1156b9a9d76` fast-forwarded cleanly, tree clean.
All five named input documents read in full, plus `aircraft-layer/CLAUDE.md`'s channel-inventory
addition and `body-layer/CLAUDE.md`'s new BL-15 block.

### Dependency Status

No dependency change. Confirmed by the diff stat: every new/changed file is in `aircraft-layer/src`,
`aircraft-layer/dcs-export`, `aircraft-layer/tests`, `body-layer/src`, `body-layer/tests`, `.claude/`,
or `plans/` — nothing touches either subproject's `pyproject.toml`, and the plan review's "no
dependency statement" finding is still accurate for the full implemented diff, not just the plan.

### Carried-Forward Verification (Mode 1 → Mode 2)

**(a) `THEATRE_PROJECTIONS` membership check strictly before path build / `open_world_model`.**
Confirmed by reading `_maybe_switch_theatre` (`body-layer/src/logger.py:1684-1826`): the
`event_theatre not in THEATRE_PROJECTIONS` check (line 1759) runs and returns via
`_enter_refusal_mode` *before* `candidate_db = world_model_dir / f"{event_theatre.lower()}-full.
sqlite"` is constructed (line 1768) and before `open_world_model` is called (line 1770) — same
ordering `main()`'s own startup guard already uses (`logger.py:3634-3640`, unchanged by this
feature). Both Reviewer batches independently confirmed this by reading the control flow (an
ordering property is not mutation-testable — the right instrument is reading, not running — and
the Reviewer said so explicitly rather than claiming a test proved it). I re-read the same code
directly rather than trusting either account; it holds.

**(b) `schema/mission_start.py` rejects malformed/wrongly-typed payloads before enqueueing.**
Confirmed: `MissionStartEvent.from_dict` (`aircraft-layer/src/schema/mission_start.py`) rejects a
missing/non-int `sequence`, a `bool` masquerading as `int` (the same `isinstance(x, bool)` guard
`F10CommandEvent.from_dict` uses, not just an `isinstance(x, int)` check that `bool` would pass
silently since `bool` is an `int` subclass in Python), and a non-string, non-`None` `theatre`.
`MissionStartReceiver._handle_datagram` drops non-JSON, non-dict, and schema-rejected payloads at
debug level and never crashes the receive loop — read directly in
`aircraft-layer/src/collector/mission_start_receiver.py`, matching
`F10CommandReceiver._handle_datagram`'s posture exactly. 8 schema test cases and the receiver's own
tests exercise this. Holds.

### Additional Checks Named in the Dispatching Brief

- **Receiver bind address**: `MissionStartReceiver.DEFAULT_HOST = "127.0.0.1"` — loopback only, same
  as every other collector-side UDP receiver in this codebase (`F10CommandReceiver`,
  `UnitVelocityReceiver`, `LineOfSightReceiver`, `FiringReceiver`). No change to this project's
  accepted trust boundary.
- **The Lua Hook's `net.dostring_in` expression**: `petrobrain-mission-start-hook.lua`'s
  `resolveTheatre()` runs the hardcoded literal `"return env.mission.theatre"` — never built by
  string interpolation from network input, mission data, or any runtime value. Matches this
  project's standing "only hard-coded strings ever cross `net.dostring_in`" posture
  (`aircraft-layer/CLAUDE.md`; agent memory `feedback_lua_dostring_in_snippet_must_be_self_contained.md`,
  `project_dostring_in_numeric_splice_naN_clamp_gap.md` — neither applies here, since this call
  splices nothing). No injection surface.
- **Log re-roll filenames — any DCS-derived string in a path?** No. Read `_reroll_run_logs`
  (`body-layer/src/logger.py:1916-2037`) and `run_log_paths.per_run_log_path`
  (`body-layer/src/run_log_paths.py`): the stamp inserted into each filename is
  `time.strftime(RUN_STAMP_FORMAT, time.localtime(when))` — wall-clock only, `when` defaulting to
  `time.time()`. The `*_base` paths rerolled are the same fixed, CLI-supplied `Path` objects
  `main()` already resolved at startup (`detection_trace_base`, `belief_truth_log_base`,
  `speech_log_base`, `group_trace_base`, `mission_memory_base`) — none of them incorporates
  `event_theatre`, `MissionStartEvent.sequence`, or any other value that arrived over the new UDP
  channel. A forged or malicious mission-start datagram cannot influence a log path at all; it can
  only trigger *when* a reroll happens, not *where* to.
- **New CLI flag handling**: `--world-model-dir` becomes valid alongside an explicit
  `--theatre`/`--world-model-db` pair (previously only paired with `--mission-understanding`). Pure
  additive widening — `argparse` default `None`, a true no-op unless given, `type=Path` with no
  special parsing. No new validation surface: the string that ends up in a path
  (`event_theatre`/`theatre`) is still gated by the same `THEATRE_PROJECTIONS` membership check
  checked at (a) above, regardless of which CLI mode supplied the initial value. Confirmed by
  reading the full `main()` theatre-resolution block (`logger.py:3605-3654`) — unchanged in its
  security-relevant ordering by this feature; the only change is which startup mode is allowed to
  additionally populate `args.world_model_dir`.

### Forged-Datagram Belief Wipe — Accepted, Not Re-Raised

Per the dispatching brief and `stage1-decisions.md`: the user explicitly accepted this risk
("Accept the risk, it's not like there's anything else sending DCS or Petrobrain signals on my
computer"). Not re-litigated here. One scope note for completeness: Stage 3 now makes a forged
datagram's *blast radius* larger than Stage 1-2 alone would have — a forged `{"sequence": N,
"theatre": "<unknown-string>"}` can now also drive `_enter_refusal_mode` (stop perception, refuse
every player command) rather than only wiping belief/mission memory. This is still the same accepted
trust boundary ("any local process" — the capability required is unchanged), and self-healing the
same way (the next genuine `onSimulationStart` resolves it), so it does not change the acceptance;
noted so the acceptance is read against what Stage 3 actually added, not just what Stage 1-2 shipped
with when it was given.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft-layer/src/schema/mission_start.py` | externally-sourced payload parsing | Rejects wrong-typed/missing fields before constructing the dataclass; `bool`-as-`int` explicitly guarded | None |
| `aircraft-layer/src/collector/mission_start_receiver.py` | UDP receive loop, loopback bind | Matches existing receiver pattern; malformed datagrams dropped, never crash the loop | None |
| `aircraft-layer/dcs-export/petrobrain-mission-start-hook.lua` | `net.dostring_in` bridge call | Hardcoded expression only; failure degrades to `theatre: null`, never blocks the signal | None |
| `body-layer/src/logger.py:1759,1768,1770` | `theatre` string → path → sqlite URI | `THEATRE_PROJECTIONS` membership check strictly precedes path construction and `open_world_model` | None |
| `body-layer/src/logger.py:1270-1350` (`CrewConsole.drain_events`/`drain_brain`) | proactive speech while refused | Reviewer's Batch 2 required fix (`if self.refused: return []`) present in both methods, mutation-tested by Reviewer and independently re-read here | None |
| `body-layer/src/mission_memory/admission.py` (`FiredOnTracker.reset_for_new_mission`) | per-mission state surviving a restart | Reviewer's Batch 2 optional refinement, closed in Batch 3; `events[_scanned_event_count:]` index staleness fixed | None |
| `body-layer/src/logger.py:1916-2037` (`_reroll_run_logs`) | log filename construction | No DCS-derived string reaches a path; stamp is wall-clock only, base paths are fixed CLI values | None |
| `body-layer/src/logger.py:3620-3645` (`main()` theatre resolution) | CLI-sourced `theatre` string → path | Unchanged ordering, already-approved guard; `--world-model-dir`'s widened eligibility does not bypass it | None |

### Verdict

APPROVED

No new dependency, no exploitable vulnerability introduced by this batch's diff. Both items carried
forward from the Mode 1 plan review are independently verified by reading the implemented code
(not by trusting either the Implementer's notes or the Reviewer's account alone), both Reviewer
passes' required fixes are confirmed present and functioning, and every additional check named in
the dispatching brief (bind address, `dostring_in` expression, log-path provenance, new CLI flag)
is clean. The one previously-accepted risk (forged local datagram) is unchanged in kind and is not
re-raised, with a one-line scope note on how Stage 3 widened its blast radius for the record.

### Not Filed (intentionally)

No new backlog-worthy finding came out of this pass — every item checked either traces to an
already-filed/already-fixed mechanism (the Mode 1 carry-forwards, the Reviewer's Batch 2 required
fix) or resolved clean with no residual risk worth tracking (bind address, `dostring_in`, log-path
provenance, CLI widening). The Reviewer's own remaining optional-refinement note (no wiring-level
test for `_run_console_poll_loop`'s theatre-switch path, `review.md` Batch 2) is a test-coverage
gap, not a security finding, and is the Reviewer's own backlog item to file if they choose —
leaving it there rather than duplicating it here as a security finding it is not.
