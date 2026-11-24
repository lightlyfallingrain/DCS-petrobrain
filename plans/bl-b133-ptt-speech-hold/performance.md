### Performance Review

Scope: `body-layer/src/belief/ptt_hold.py` (`PttHoldGate`) and its one caller,
`body-layer/src/belief/speech_worker.py` (`SpeechWorker._wait_for_ptt_release`/`_run`), as of
`feature/bl-b133-ptt-speech-hold` @ `aa14572c`. Target: body-layer is the Petrobrain Runtime
(per-poll) layer, so the real-time-adjacent posture applies even though no hard budget is
declared yet — "no per-request allocations on hot paths," "offload heavy work asynchronously,"
"prefer batching" (root `CLAUDE.md`). Main poll loop runs at `_DEFAULT_POLL_INTERVAL_S = 1.0 s`
(`body.py:3035`); `SpeechWorker` runs on its own daemon thread, independent of that loop.

### Findings

#### PTT gate poll runs only while a routine line is actually waiting
- **Location:** `SpeechWorker._run` (speech_worker.py:313-317) only enters
  `_wait_for_ptt_release` when a dequeued item has `bypass_gate=False` *and* a gate is
  configured; `_wait_for_ptt_release` (speech_worker.py:345-368) loops only while
  `self._ptt_gate.is_held()` is true.
- **Risk:** none credible — confirmed no background/idle polling of `/ptt/state` when the
  speech queue is empty or every item is urgent. This answers the brief's "does the gate ever
  call HTTP when no line is waiting" — no.
- **Action:** MONITOR (nothing to fix; recorded as a confirmed-absent risk).

#### One HTTP round-trip added to every routine line's start latency
- **Location:** `_wait_for_ptt_release`'s `while self._ptt_gate.is_held():` condition
  (speech_worker.py:357) always calls `is_held()` at least once, which calls
  `client.get_ptt_state_latest()` → `AircraftLayerClient._get_json("/ptt/state")`
  (aircraft_client.py:418, 693-717) — a fresh `urllib.request.urlopen` call, no connection
  reuse — even when the trigger is not held and the loop exits immediately.
- **Risk:** every routine utterance now pays one LAN HTTP round-trip (sub-10 ms on a healthy
  LAN, up to `_DEFAULT_TIMEOUT_S = 2.0 s` if aircraft-layer is slow/unreachable) before
  `_process`/`push_speech` starts. This runs on `SpeechWorker`'s own thread, never the main
  poll thread, and speech synthesis/playback itself is already measured in seconds (module
  docstring), so this one round-trip is noise against the existing latency budget for a
  *routine* line. Not credible as a budget violation.
- **Action:** MONITOR.

#### Sustained ~20 Hz polling, one TCP connection per poll, while the trigger is held
- **Location:** `_wait_for_ptt_release`'s loop re-checks `is_held()` every
  `_PTT_WAIT_POLL_INTERVAL_S = 0.05 s` (speech_worker.py:97, 364) while held; each check is a
  new, non-pooled `urllib.request.urlopen("/ptt/state")` (aircraft_client.py's `_get_json`
  pattern, shared by every `get_*` method on this client — not something this feature
  introduced).
- **Risk:** a long PTT hold (a multi-minute radio call is plausible for this aircraft) produces
  on the order of 1,000+ short-lived HTTP requests to aircraft-layer over its duration. Each
  request is a small JSON GET against an already-running `ThreadingHTTPServer`-style collector
  on the same LAN; comparable in order of magnitude to `audio-adapter/src/ptt_source.py`'s own
  `DEFAULT_DCS_POLL_HZ = 30.0` DCS-side poll that already produces this trigger's cached sample.
  This runs entirely on `SpeechWorker`'s dedicated background thread — confirmed no effect on
  the 1 Hz main poll loop, and no blocking of `_print`'s synchronous `enqueue` (module docstring
  design intent, verified in code, not just asserted). The real cost is a steady trickle of
  socket churn (connect/request/close) on a single-user LAN system, which is the kind of thing
  that becomes a problem only if aircraft-layer itself were under load from many such pollers —
  it is not, today.
- **Action:** MONITOR, not NOW. No evidence of a current budget violation; flag if a future
  feature adds more independent sub-second HTTP pollers against aircraft-layer, since those
  would compound on the same unpooled-connection pattern.
- **Mitigation (if ever promoted to NOW):** reuse a single `http.client.HTTPConnection`
  (keep-alive) for this poll instead of a fresh `urlopen` per call, or raise
  `_PTT_WAIT_POLL_INTERVAL_S` — both are local, reversible changes that would not need an
  architecture review.

#### No per-request allocation or full-dataset iteration risk found
- **Location:** `PttHoldGate.is_held()`/`_is_stale()` — fixed small dict payload, a handful of
  float/bool comparisons, no collections scaled by mission/world-object count.
- **Risk:** none. Not scaled by anything that grows with scenario size.
- **Action:** MONITOR (recorded as checked, not a free pass to skip next time).

### Verdict
APPROVED — MONITOR
