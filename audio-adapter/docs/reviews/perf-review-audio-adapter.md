# Performance Review — audio-adapter (whole-subproject sweep)

**Date:** 2026-09-26 · **Branch:** main @ bd28563 · **Scope:** `audio-adapter/src/`, `audio-adapter/tools/`
**Reviewed against:** `audio-adapter/CLAUDE.md`, `audio-adapter/ROADMAP.md`, `plans/tts-voice-output/plan.md`,
`plans/inbound-speech/plan.md`, `research/2026-09-19-whisper-model-sweep.md`

No hard real-time budget applies yet (Petrobrain Runtime has not started), but this subproject
already has a genuine speak-to-response path the player feels, and Stage 5 (DCS-trigger PTT) is
**flown and in regular use**, not scaffolding. That changes the bar: things that run continuously
during a live sortie are reviewed as live paths, not as dev conveniences.

## Findings

### 1. `DcsPTT` polls the collector twice as fast as the code says it should — REQUIRED FIX

- **Location:** `src/ptt_source.py:371` (`DEFAULT_DCS_POLL_HZ = 30.0`) vs.
  `src/audio_adapter/capture.py:60,115,193` (`DEFAULT_POLL_HZ = 60.0`, used for every `--ptt` mode).
- **Mechanism:** `DEFAULT_DCS_POLL_HZ` is dead code — grepped across `src/` and `tests/`, it is
  defined once and never read. `CaptureLoop.tick()` calls `ptt.is_down()` on every iteration
  regardless of source, and for `--ptt dcs` that is `DcsPTT._read()`: a full
  `urllib.request.urlopen()` round trip to the collector's `GET /ptt/state` (`src/ptt_source.py:415-430`).
  Every poll is a fresh, non-keep-alive HTTP request — new socket, new `ThreadingHTTPServer` handler
  thread on the collector side (aircraft-layer's `_PTT_STATE_PATH` handler is a cheap cache read;
  `aircraft-layer/src/schema/ptt.py`/`api/server.py` confirm this is O(1), not the concern), plus
  JSON encode/decode of a tiny payload — 60 times a second, continuously, for as long as capture
  runs. The `ptt_source.py` docstring for `DEFAULT_DCS_POLL_HZ` states the design intent explicitly:
  *"fast enough... slow enough not to hammer a `ThreadingHTTPServer` sharing a box with DCS"* — the
  constant exists because 30 Hz was judged the right tradeoff, but nothing wires it in, so the
  capture process actually runs at double that on the one box (Windows, running DCS itself) where
  the tradeoff was written to matter.
- **Risk:** This is not hypothetical — Stage 5 was flown and accepted 2026-09-23 and is the live
  mechanism now, not a future one. The concrete harm is CPU/socket churn competing with DCS's own
  frame budget and the Export.lua/collector pipeline on the same Windows box, at exactly double the
  rate the subproject's own author judged acceptable. I have not measured a frame-time or CPU
  regression from this — no such measurement exists in `docs/acceptance/2026-09-23-voice-command-sortie.md`
  or elsewhere — so I cannot claim it is currently *causing* a felt problem. What is certain is the
  mismatch between documented intent and actual behavior, and that the fix is nearly free.
- **Mitigation:** Wire `DEFAULT_DCS_POLL_HZ` into `capture.py`'s argument defaults — pick the default
  `--poll-hz` based on `--ptt` (30.0 for `dcs`, keep 60.0 for `key`/`joystick`, which are local calls
  with no network round trip), or simply have `_build_parser` default `--poll-hz` to `None` and
  resolve it per-source at the top of `main()`. A few lines; no behavior change for joystick/key mode.

### 2. `DcsPTT` opens a new TCP connection every poll — OBSERVATION / LATER

- **Location:** `src/ptt_source.py:415-420`, `_read()`.
- **Mechanism:** `urllib.request.urlopen` does not reuse connections across calls; each poll pays a
  fresh `connect()` even though it is loopback to the same collector every time.
- **Risk:** Loopback connect cost is small (sub-millisecond, typically), and this compounds finding
  1 rather than standing alone. Not worth a dedicated fix at today's scale — fixing finding 1 already
  halves this cost, and single-user LAN scope makes a persistent `http.client.HTTPConnection` not
  worth the added statefulness (reconnect-on-drop handling) unless finding 1's fix is judged
  insufficient after a real flight with CPU/frame-time telemetry.
- **Action:** LATER — revisit only if a flight surfaces an actual frame-time symptom.

### 3. Per-utterance subprocess spawn cost (TTS `say`, STT `whisper-cli`, `sox` header repair) — OBSERVATION, already tracked

- **Location:** `src/tts_engine.py` (`MacSayEngine.synthesize`), `src/stt_engine.py`
  (`WhisperCliEngine.transcribe`), `src/audio_capture.py` (`_repair_truncated_wav`, called from
  every `SoxRecorder.stop()`).
- **Mechanism:** Every spoken line and every recognized clip spawns a fresh external process. For
  whisper.cpp in particular, this means the `small.en` model (465 MB) is loaded fresh on every
  invocation — `research/2026-09-19-whisper-model-sweep.md` measured 0.50 s median / 1.46 s p90 /
  1.68 s max latency for `small.en`, which very likely includes that load cost, though the sweep
  does not break load-time out from decode time.
- **Risk:** Real, and already the subject of `ROADMAP.md`'s open item **"Press-to-readback is ~3 s,
  and that is the next real problem"** — which explicitly calls out measuring each hop (including
  whisper itself and `say`'s synthesis) before optimizing, and explicitly proposes caching
  synthesized readbacks (the fixed small vocabulary of confirmation lines) as a candidate fix. I
  agree with that plan and have nothing to add beyond confirming, from reading the code, that a
  cache keyed on readback text in front of `MacSayEngine.synthesize` would be a clean, low-risk
  precomputation — the design decision to keep TTS/STT as external-binary calls (not persistent
  server processes) is `CLAUDE.md`'s own explicit tech-stack choice, not something to relitigate
  here.
- **Action:** No new action from this review — already owned by the roadmap item. Flagging here only
  to confirm it is real and that the proposed fix (readback caching) is the right shape.

### 4. `LocalPlaybackSink` does not serialize concurrent `/speak` calls — OBSERVATION, dev-only path

- **Location:** `src/local_playback.py`, class docstring and `deliver()`.
- **Mechanism:** Each `/speak` call spawns its own `afplay` process; `ThreadingHTTPServer` gives each
  request its own thread, so two overlapping calls genuinely play concurrently rather than queueing.
  This is explicitly documented and was a deliberate, reviewed tradeoff (2026-09-20) for the
  `--target local` dev path only — `--target aircraft-layer`'s `AudioPlaybackSender` (aircraft-layer
  side, out of this review's scope) is the one with real FIFO/interrupt queueing for the actual
  flight target.
- **Risk:** None for the target that matters in flight. `--target local` is a dev/audition
  convenience; two callouts briefly overlapping there is a non-issue.
- **Action:** None. Correctly scoped already.

### 5. Bounded queues, no unbounded growth found — CONFIRMED CLEAN

- **Location:** `src/transcript_queue.py` (`TranscriptQueue`, `maxlen=64`), `_InFlightTracker` in
  `src/local_playback.py` (entries removed on `finish()`, cannot grow across a session).
- Checked directly because an unbounded audio queue was a real defect found in aircraft-layer this
  week (per the task brief). `TranscriptQueue` is explicitly bounded and modeled on
  `aircraft-layer`'s already-fixed `F10CommandQueue` shape. No analogous defect here.

### 6. No busy-waits, no per-frame allocation of note

- `CaptureLoop.tick()` runs on a `time.sleep(interval)` cadence, not a busy loop; per-tick allocation
  is a short-lived `list[CaptureEvent]` (usually empty) — negligible.
- `command_matcher.py`'s `VERB_ANCHOR_WORDS`, `_PHRASE_INDEX`, and `_PHRASE_WORDS` are computed once
  at import time and explicitly comment on why (citing this project's own prior lesson from
  `world-model/coordinates.py`'s Transformer cost) — this is the right pattern already in place, not
  a finding.
- `wav_peak_and_duration` (the clip-gate loudness check) is deliberately pure-Python/`array`-based
  rather than shelling out to `sox stat`, precisely to avoid spawning a process on the capture
  hot path — also already correct, noted in its own docstring.

## Verdict

**APPROVED — MONITOR**, contingent on finding 1.

Finding 1 is the only REQUIRED FIX: a live, flown, continuously-running path (Stage 5's DCS PTT
polling) runs at double its own documented design rate due to a dead constant, on the one machine
where the tradeoff was written to matter. The fix is a few lines and carries no behavior change
for the other two PTT sources. No other finding rises above OBSERVATION — the subprojects's queues
are bounded, its caches are already precomputed at import time, and its remaining latency
(subprocess spawn cost, whisper model load) is real but already correctly owned by
`ROADMAP.md`'s "press-to-readback is ~3 s" item with a sound proposed fix (readback caching) that
this review concurs with rather than duplicates.
