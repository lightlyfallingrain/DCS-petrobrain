### Performance Review

Scope: AA-6 Stages 1-3 on `feature/audio-adapter-os-independent` (batch run after Stage 3, per
root `CLAUDE.md`'s batch cadence), tip `eb06586b587fa8f1edd2766528b50753f4b9a07b`. No hard
real-time budget applies — that starts with Petrobrain Runtime. This is a single-player, LAN-only
adapter for Petrovich's spoken callouts: call rate is bounded by human speech cadence (at most a
handful of lines per minute), never a per-tick or per-poll hot path. Scaled findings accordingly —
the question is "does any line ever notice", not "does this survive 1000 req/s".

Files read: `audio-adapter/src/tts_engine.py` (`PiperEngine`, outage state machine),
`audio-adapter/src/local_playback.py` (`_WinsoundLocalSink`, `_InFlightTracker`,
`LocalPlaybackSink`), `audio-adapter/src/server.py` (`TTSAdapterServer`, `ThreadingHTTPServer`
wiring), `body-layer/src/belief/crew_console.py` (`_print`'s `push_speech` call site, to confirm
whether the blocking shape changed — it did not).

### Findings

#### PiperEngine: new HTTP connection per `/speak` call
- **Location:** `tts_engine.py:108-144`, `PiperEngine.synthesize` — `urllib.request.urlopen(request,
  timeout=self._timeout_s)` opens a fresh TCP connection each call; no `http.client.HTTPConnection`
  kept alive, no session/pool.
- **Risk:** connection setup cost on top of Piper's own measured warm-request time (0.054-0.098s,
  the recon's own number, which is almost certainly the full connect+request+response figure since
  that is what `urllib.request.urlopen` measures end to end). At single-pilot speech cadence
  (seconds between lines, never back-to-back saturation) this cost is invisible — loopback TCP
  handshake is sub-millisecond. This would only matter if call rate rose by orders of magnitude,
  which is not this phase's shape and not a plausible one for spoken crew callouts.
- **Action:** MONITOR
- **Mitigation (if it ever becomes NOW):** replace the per-call `urlopen` with a persistent
  `http.client.HTTPConnection` reused across calls — same shape `OllamaClient` would want if it
  ever needed it. Not worth building now: no measurement motivates it, and the plan's own Stage 4
  live-verification step already measures the real end-to-end `/speak` latency on both machines,
  which is the number that would actually show whether this matters.

#### Outage state machine lock (`PiperEngine._report_failure`/`_report_success`)
- **Location:** `tts_engine.py:146-160`.
- **Risk:** none credible. The critical section is a single boolean read-and-set under
  `threading.Lock`, held for microseconds, never around the network call itself (the lock is taken
  only in `_report_failure`/`_report_success`, after `urlopen` has already returned or raised).
  `ThreadingHTTPServer` gives each `/speak` call its own thread, but contention on this lock at
  single-pilot call rates is non-existent — two synthesis failures landing in the same microsecond
  window is not a scenario this system produces.
- **Action:** MONITOR (no mitigation needed; recorded so a future reader doesn't re-flag it as new)

#### First-use-of-a-voice model-load cost, unmeasured
- **Location:** `tts_engine.py:47-54`, `_SYNTHESIS_TIMEOUT_S = 10.0`; plan Decision 7, Risks &
  Unknowns.
- **Risk:** Piper's own first request for a given voice pays a model-load cost inferred (not
  measured) to be in the same order as the ~2s CLI/in-process figures already seen. If that
  estimate is wrong by a wide margin, the first callout of a sortie could stall past the 10s
  timeout and 503. This is exactly the kind of reasoned-count risk this role's own memory warns
  against trusting without measurement (`.claude/agent-memory/performance-reviewer/` — "Measure n
  before scaling anything by n" applies here to a reasoned latency figure, not a count, but the
  same discipline: a number nobody measured is the one most likely to be wrong).
- **Action:** MONITOR — already correctly flagged in the plan's own "Risks & Unknowns" and
  explicitly deferred to Stage 4 live verification ("a live measurement during Stage 4 would
  tighten or confirm that number"). Nothing to add here that the plan doesn't already own; this
  review confirms the implementation matches that stated posture (generous timeout, not a tight
  budget) rather than silently assuming the number.
- **Mitigation:** none needed now. If Stage 4 measures a load cost that blows through 10s, raise
  the timeout or pre-warm the voice at Piper startup (e.g. the run script sends one throwaway
  `/synthesize` after boot) — a cheap fix to apply once the real number exists, not before.

#### `ThreadingHTTPServer`: one thread per request, no bound
- **Location:** `server.py:352-358`, `TTSAdapterServer.open()`.
- **Risk:** unbounded thread creation under load is a real pattern to flag in general, but at this
  call rate (one pilot, one speech line at a time, occasional overlap only between a routine line
  and an injected urgent one) there is no realistic path to thread exhaustion. This mirrors
  `aircraft-layer`'s own `TelemetryAPIServer` shape, an established precedent in this codebase for
  the same reason.
- **Action:** MONITOR (not a regression introduced here, not scoped to this batch)

#### Windows sink: per-`deliver()` temp file + WAV header read
- **Location:** `local_playback.py:396-425`, `_WinsoundLocalSink.deliver`; `_wav_duration_s`
  (`local_playback.py:284-297`).
- **Risk:** none. One `tempfile.mkstemp`, one file write, one `wave.open` header read, one
  `winsound.PlaySound` call per spoken line — all one-shot, bounded-size work (a WAV for one
  sentence, not a dataset), not iterated or repeated. This is precomputation-shaped already: the
  duration is read once per line to size a single `Event.wait`, not polled.
- **Action:** none (no finding; recorded that it was checked)

#### Blocking shape: `/speak` blocks the handler thread for the full playback duration (pre-existing, unchanged by this batch)
- **Location:** `server.py:196-201` (`_handle_speak` calls `sink.deliver` synchronously);
  `crew_console.py:3856` (`self.speech_client.push_speech(line, urgent=bypass_gate)`, called
  synchronously from `CrewConsole._print`).
- **Risk:** `push_speech` blocks body-layer's calling thread until the adapter's HTTP response
  returns, which for `--target local` only happens after `afplay`/`winsound` finishes playing the
  whole line (several seconds for a long callout). This was true before AA-6 (the old
  `MacSayEngine` + `LocalPlaybackSink` path blocked exactly the same way via `subprocess.
  communicate()`) — AA-6 changes which engine/sink does the blocking, not whether blocking happens.
  Not a finding against this batch; recorded so it isn't mistaken for something this diff
  introduced. Out of scope to fix here — it would be an architecture change (async delivery,
  fire-and-forget `/speak`) affecting `CrewConsole`'s own call site, not an audio-adapter change,
  and the plan never proposed one.
- **Action:** none for this batch (pre-existing, unaffected by this diff)

### Verdict
APPROVED — MONITOR
