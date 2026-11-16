### Performance Review

Scope: commits `5151e837`..`28d97c3d` (feature/effector-says, base `110067d0`) against body-layer's
poll path. Target: no hard real-time budget yet declared for this phase, but body-layer's poll
loop is an existing, actively-measured runtime hot path (`project_body_layer_poll_loop_diagnosis`
memory: default 1 Hz poll, measured median ~330 ms/poll, dominated by `group_salience`/callout
scheduling) — "no per-request allocations on hot paths" and "prefer batching" apply to it.

### Findings

#### `EffectorRunState.spoken` — new list allocation in `advance()`, every poll
- **Location:** `belief/effector_engine.py::advance`, `spoken: list[str] = []` (new line) plus
  `spoken=tuple(spoken)` on the returned `replace(state, ...)`.
- **Risk:** none credible. `advance()` already rebuilds four other containers
  (`runs`/`pending`/`commanded_values`/`assumed_writes` dict copies) and returns a new frozen
  dataclass via `replace()` on **every** call, idle or not — this is the module's pre-existing,
  documented discipline ("the same `replace()`-only discipline as every other field here"), not
  something this change introduces. The added list is empty when idle (no trigger running — the
  documented "true no-op" case) and bounded by sequence row count otherwise (every shipped
  speaking sequence is single-row per the review's own check, so at most 1-2 small string appends
  per poll even when busy). `tuple([])` returns the interned empty-tuple singleton, so the idle
  case is effectively allocation-free beyond the list object itself.
- **Action:** MONITOR. Not a new cost class; marginal versus the existing per-poll container
  rebuild this function already does. Worth re-checking only if a future sequence (the plan's own
  "step by step" direction) grows to many rows with non-empty `petrovich-says` cells per trigger.

#### `crew_console.drain_effector_speech` — `list(spoken)` every poll
- **Location:** `belief/crew_console.py::drain_effector_speech`, `self._print(list(spoken), now_sim)`.
- **Risk:** none credible. Converts the tuple to a list once per poll, including the idle case
  (small, single-object allocation — not the interned empty-tuple path `tuple()` gets, but still
  O(1) and unconditional only in the trivial sense that the call itself is unconditional).
  `_print` on an empty `lines` list is a verified no-op: `if lines and mentions:` short-circuits
  false, and `for line in lines:` iterates zero times — no speech-client call, no scheduler call,
  no logging. Confirmed by reading `_print`'s body (`crew_console.py:6163-6166`), not just its
  docstring's claim that this is "already a no-op."
- **Action:** MONITOR. Same shape as the sibling `drain_config_error` call right above it in
  `body.py`'s poll block, which the review notes follows "same 'every poll' shape." Established
  pattern in this module, not a new risk.

#### Row-completion work (`_speak_text`) — only runs when a row actually completes
- **Location:** `belief/effector_engine.py::_speak_text`, called from the two completion sites
  (R12 self-check match, successful write).
- **Risk:** none. Pure string slicing/concatenation on one short cell per completed row, fired by a
  player-issued command (observ on/off, weapons armed/safe) — a human-paced event, not a per-poll
  recomputation. No I/O, no loop over unrelated data.
- **Action:** MONITOR (no action needed; included for completeness).

#### Parse-time quote stripping (`_strip_petrovich_says`)
- **Location:** `belief/effector_sequences.py::_strip_petrovich_says`, called once per row at
  `load_sequences` time.
- **Risk:** none — off the poll path entirely, runs once at startup per the plan's own framing
  ("once at load").
- **Action:** MONITOR (no action needed).

### Verdict
APPROVED
