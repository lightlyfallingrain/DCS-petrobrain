## Security Deep Analysis: BL-B133 (PTT speech hold)

Method: worked in `/Users/sg/Code/DCS-petrobrain-ptthold` (branch `feature/bl-b133-ptt-speech-hold`),
`git rev-parse HEAD` confirmed `aa14572c536e3a1a5bd5eb9794c3c363df08aeca` (the expected tip, no fetch
needed). Diff reviewed: `c3ed21b4..aa14572c` (13 files, +1715/-13).

### Dependency Status

No dependency change. No new package, no new import outside this project's own modules
(`tuning`, `aircraft_client`, `connection_reporter` — all pre-existing).

### What this feature adds, as an attack surface

A new LAN-facing read: `AircraftLayerClient.get_ptt_state_latest()` → `GET /ptt/state` on the
aircraft-layer collector, consumed by a new `belief/ptt_hold.PttHoldGate`, which gates the start of
a routine `SpeechWorker` item on a background thread. No new listening socket is added by this
feature — body-layer remains a client here, not a server; the LAN-port-scanner angle this project's
scope statement calls out does not gain a new target from this diff.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `aircraft_client.py:409-423` `get_ptt_state_latest` | Untrusted JSON parsed off a LAN HTTP GET | Validated: `_get_json` raises `AircraftLayerError` on bad JSON/transport failure; the method itself type-checks the top-level result is a `dict` (or `None`) and raises `AircraftLayerError` otherwise — same "not an error, empty cache" posture as every sibling `get_*`. No `eval`/deserialization of code, bounded by the shared `_get_json` helper. | None |
| `ptt_hold.py:179-200` `PttHoldGate.is_held` | Fields read from the untrusted dict (`payload.get("intercom")`, `payload.get("radio")`) | `bool(...)` on an arbitrary JSON value never raises regardless of type (missing key, wrong type, nested object) — can't be used to crash or hang the gate. A malicious value like the *string* `"false"` coerces to `True` via Python truthiness, but that only ever pushes the gate toward "held" (mute), which is this feature's own fail-safe direction, not an escalation. | None (false positive as an exploit; noted for completeness) |
| `ptt_hold.py:179-189` exception handling | `AircraftLayerError` from a dead/unreachable collector | Caught, resolves to `False` (released) — matches the documented fail-open-to-released posture (never fails closed into a permanent mute from a transport error). Logged via `ConnectionReporter`'s transition-only mechanism (or a single `logger.warning` fallback) — no per-poll log flooding. | None |
| `ptt_hold.py:243-258` `_is_stale`, `body.py:966-970` `received_wall_clock_s` parse | `isinstance(x, (int, float)) and not isinstance(x, bool)` guard on a value parsed from `GET /telemetry/latest` JSON, then used in a float comparison (`wall_clock() - received > bound`) | **Finding 1 (low/low, not blocking).** `json.loads` accepts `NaN`/`Infinity`/`-Infinity` by default; both pass this `isinstance` guard. Unlike the `int()`-conversion shape of this gap already in agent memory (`BL-B104`), this one never raises — `Infinity` (or `NaN`) silently makes `_is_stale()` report "not stale" forever, so a `held=True` PTT reading cached from a collector that has gone silent (or a LAN host impersonating it) is trusted past `PTT_FEED_STALE_AFTER_S` and Petrovich stays muted until the next genuine DCS mission (re)start. No crash, no code-exec, no data exposure — denial of routine speech only, self-healing. The identical gap (same `isinstance` guard, no `math.isfinite`) already exists pre-existing on `last_ias_kmh` two lines above in the same function; this feature reuses that exact pattern rather than introducing a new one. Filed as `[[BL-B135]]` rather than blocking this feature. |
| `aircraft_client.py:696-697` `_get_json`'s `response.read()` | Unbounded read of the HTTP response body | Pre-existing (every `get_*` method shares this helper; not touched by this diff). The `/ptt/state` payload shape is a small fixed-field object server-side, not attacker-sized by design, but the client itself places no cap. Not this feature's finding — same helper, same gap, on every other endpoint already. | None (pre-existing, not blocking) |
| `speech_worker.py` `_wait_for_ptt_release`/`_gate_lock`/`_gate_wait_superseded` | New locking around a blocking wait on the worker's own background thread | Reviewed for deadlock/thread-safety: `_gate_lock` is held only for short, non-blocking sections (flag reads/writes) in both `interrupt()` and `_run`/`_wait_for_ptt_release`; the actual blocking wait (`self._ptt_wait_abort.wait(timeout=...)`) happens outside the lock. No nested lock acquisition, no call into code that could re-enter the lock. The lost-wakeup race this replaces (bare `Event.clear()` racing `interrupt()`) is the one `review.md`'s "review fix 2" already fixed and this analysis confirms the fix is sound: the `_gate_wait_active`/`_gate_wait_superseded` pair, not the `Event`, is the source of truth, and both are only ever read/written under the lock. | None |
| `speech_worker.py` `_wait_for_ptt_release` loop | A malicious/impersonating LAN host could serve `held=True` forever | This blocks the speech worker's routine-item processing indefinitely — but muting Petrovich's routine speech while PTT reads held is this feature's entire stated purpose, not a new failure mode it introduces; the queue stays bounded (`_MAX_QUEUE_LEN`, pre-existing cap) so no unbounded memory growth results, and urgent items still preempt immediately via `interrupt()`. Not a security finding distinct from the feature's own design. | None |
| `body.py` `_reset_mission_state`/`_check_for_new_mission` | `speech_worker: SpeechWorker | None = None` threaded through, optional-collaborator shape | Matches the existing `fired_on_tracker`/`lost_contact_tracker` pattern already in this function; no new file-system or process-execution path introduced. | None |
| `defaults.toml`/`tuning.py` wiring | New tunables `PTT_RELEASE_DEBOUNCE_S`, `PTT_FEED_STALE_AFTER_S` | Plain floats with `lo`/`hi` bounds enforced by `tuning.real`; not secrets, not reachable from untrusted input (local config file only). | None |

No `eval`/`exec`/`loadstring`/`dostring`, no shell-out, no new file path built from received data, no
secret/credential introduced, no new listener. No LLM prompt-injection surface — this feature does
not touch anything an LLM reads (PTT state is a boolean gate, never surfaced as text to a model).

### Verdict

**PASS**

The one finding (Finding 1, non-finite float at a wire-boundary comparison) is low probability
(requires a rogue or impersonating host on this project's LAN) and low impact (denial of routine
speech only, self-heals on mission restart, no crash/code-exec/data-exposure) — filed as
`[[BL-B135]]`, not required before this feature proceeds, consistent with this role's "do not flag
pre-existing issues as blockers" rule (the identical gap already exists, pre-existing, on
`last_ias_kmh` two lines above the new code in the same function).

### Findings filed

- Finding 1 (non-finite float at `received_wall_clock_s`/`PttHoldGate._is_stale`) → filed as
  `body-layer/ROADMAP/BL-B135.md`, indexed in `body-layer/ROADMAP/body-layer-backlog.md`.
- All other items in the Code Findings table above resolved to "None" (false positive or
  pre-existing/not-this-feature's-finding) — no further tracked item owed.

### Passed to Reviewer

(none observed — no player-experience/correctness-shaped issue noticed outside this role's scope
during this pass)
