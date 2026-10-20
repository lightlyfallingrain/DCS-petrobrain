## Security Deep Analysis: voice-latency-instrumentation

Reviewed at tip `4ac44e29d1feb997bc29b7b2cf32d2f44b0c70f6` (batch: `97e78060` instrumentation +
`4d5ecbdc` review commit + `4ac44e29` review-required-fix, `git diff e14d865d..4ac44e29`, 35 files
across audio-adapter/aircraft-layer/body-layer) against `plans/voice-latency-instrumentation/
{plan,implementation,review,security-plan-review}.md`.

### Dependency Status

No dependency change. Confirmed: every new symbol across all three subprojects is stdlib
(`uuid`, `time`, `json`, `pathlib`) or an existing in-repo client/writer shape, matching the plan
review's own check.

### Verification of the plan review's one open item

The plan review flagged (not blocking): *"validate `correlation_id`/`t_ptt_release_wall` with the
same `isinstance` pattern every sibling field already uses... and cap `correlation_id` length."*
Confirmed applied and tested on all three HTTP boundaries:

- `audio-adapter/src/server.py`: `_validate_correlation_id` (type + `_MAX_CORRELATION_ID_LEN = 128`)
  on both `/speak` and `/transcribe`; `t_ptt_release_wall` separately checked `isinstance(..., (int,
  float))` with an explicit `bool` exclusion (a `bool` is an `int` subclass in Python — this
  exclusion is correct and easy to get wrong silently).
- `aircraft-layer/src/api/server.py`: `/audio/play` duplicates the same check and the same 128
  constant (module independence — duplicated, not imported, consistent with this project's stated
  policy).
- `body-layer/src/logger.py`'s `_poll_transcripts`: rejects (skips) a non-string `correlation_id_raw`
  off the polled dict before threading it onward.

Tests exist and pass for the negative cases on both HTTP servers
(`test_speak_non_string_correlation_id_returns_400`, `test_speak_oversized_correlation_id_returns_400`
and their `/transcribe`/`/audio/play` equivalents) — spot-checked directly, not taken on the
implementer's word.

### Checked per this task's specific list

- **Log injection**: all three JSONL sinks this plan writes into
  (`latency_log.LatencyLogWriter.write`, `belief_truth_log.BeliefTruthLogWriter.write_speech`,
  `speech_log`'s existing `write`) serialize via `json.dumps`. An adversarial `correlation_id`
  (quotes, newlines, control characters, even literal `%s`-shaped content used later in a
  `logger.info("...%s...", correlation_id)` call in `audio_sender.py`) cannot break JSONL structure
  or forge a sibling row, and cannot act as a format-string template since it is always substituted
  as a value, never as the format string itself. No finding.
- **File-path handling of `--latency-log`**: CLI-supplied only (`audio_adapter.capture`/
  `audio_adapter.__main__`), never derived from network input, same posture as every existing
  `--*-log` flag. No new write path outside an operator-chosen location; nothing writes into the
  DCS installation. No finding.
- **Secrets in logs**: none of the new fields are secret-shaped (`correlation_id`, wall-clock
  stamps, durations, outcome strings, command tokens). No finding.
- **Can a logging failure break `/speak`, `/transcribe`, playback, or the poll loop? Traced
  through every call site — no.**
  - `server.py`'s `_log_latency` → `LatencyLogWriter.write`: catches `OSError` internally and
    disables itself after the first failure (same "report once, then give up" policy already used
    by `SpeechLogWriter`/`DetectionTraceWriter`/`BeliefTruthLogWriter`). `json.dumps(..., default=
    str)` means a non-serializable field is stringified rather than raising.
  - `audio_adapter/capture.py`'s `_run()` calls `latency_log.write(...)` directly, not wrapped in
    its own `try/except` at the call site — but `write()`'s own internals make this safe in
    practice for the same reason above; this mirrors the capture loop's existing exception posture
    (`CaptureLoop.tick()`'s own broad `except Exception` already covers capture/send failures
    elsewhere in this same file).
  - `aircraft-layer/src/collector/audio_sender.py`'s worker thread: the three new `logger.info(...)`
    calls (enqueue/playback-start/playback-finish) are bare, unwrapped stdlib logging calls — the
    same posture every pre-existing `logger.warning` call in this exact method already has.
    Python's `logging` module itself swallows formatting/handler errors internally
    (`Handler.handleError`) rather than propagating them, so this does not reintroduce the
    `scale_wav_volume`/`frombytes()` class of defect from `.claude/agent-memory/security/
    project_spu8_scale_wav_volume_unguarded_frombytes.md` (an unguarded call *after* a guarded
    block, killing the worker thread) — checked specifically because that memory is exactly this
    shape of risk, in this exact file. No finding.
  - `crew_console.py`'s `_print`: the `speech_log_sink` call remains wrapped in its pre-existing
    broad `except Exception` (moved after the `speech_client` block, same guard). No finding.
- **Thread safety of the playback worker's new logging**: the three new `logger.info` calls run on
  the existing single worker thread (`AudioPlaybackSender._run`); `play_audio`/`_enqueue` (HTTP
  handler threads, via `ThreadingHTTPServer`) only touch the already-thread-safe `queue.Queue`. No
  new shared mutable state introduced. No finding.
- **`join_voice_latency.py` and malformed log lines: confirmed unsafe, not safe.** `_iter_jsonl`
  calls `json.loads(line)` with no `try/except`. Reproduced directly (not inferred): a file with one
  well-formed row followed by one truncated row raises `json.decoder.JSONDecodeError` straight out
  of `main()`, losing every row from every file in the invocation, not just the bad line. No test in
  this diff exercises this path. See **Finding 2** below — filed as `BL-B88`.
- **Stage 6 deferral unbounded growth: confirmed, not a false concern.** `_pending_positional_
  replies` has no size cap anywhere (`grep` for `_MAX_PENDING`/similar next to it: none), unlike
  `TranscriptQueue` (`_MAX_QUEUE_LEN = 64`, drop-oldest) and `aircraft-layer`'s `F10CommandQueue`,
  both of which bound themselves for exactly this reason by their own comments. Traced the drain
  rate: `note_reply` extends `scheduler.busy_until_sim` by the spoken text's own estimated duration
  each time an entry is drained, so at most roughly one entry drains per ~2-5s window
  (`drain_pending_positional_replies` re-checks `busy_until_sim` fresh per entry, by design, so nothing
  forces more than one out per poll once the first re-claims the channel) — while up to 64 new
  transcript-driven dispatches can enter **per poll** (~1s) via the network-reachable `POST
  /transcribe` → `GET /transcripts/poll` path if every posted clip's recognised text happens to
  match a positional-readback token. See **Finding 1** below — filed as `BL-B87`.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `audio-adapter/src/server.py` (`_validate_correlation_id`, `_handle_speak`/`_handle_transcribe`) | new field validation | Type + length cap applied and tested, per plan review | None |
| `aircraft-layer/src/api/server.py` (`/audio/play`) | new field validation | Same cap/pattern duplicated correctly | None |
| `body-layer/src/logger.py` (`_poll_transcripts`) | new field validation | Non-string rejected before threading | None |
| `audio-adapter/src/latency_log.py`, `body-layer/src/belief_truth_log.py` | JSONL serialization | `json.dumps` throughout; no log-structure injection | None |
| `aircraft-layer/src/collector/audio_sender.py` (`_run`, enqueue/playback-start/playback-finish logging) | logging on a worker thread | Bare `logger.info`, matches this file's own pre-existing pattern; does not reintroduce the `frombytes()`-class defect from agent memory | None |
| `body-layer/src/belief/crew_console.py` (`_pending_positional_replies`, `_speak_or_defer`, `drain_pending_positional_replies`) | unbounded in-memory queue | No cap, unlike every sibling queue in this codebase; network-reachable growth path via `/transcribe` | **Low-risk, filed: `BL-B87`** |
| `body-layer/tools/join_voice_latency.py` (`_iter_jsonl`) | unguarded `json.loads` per line | Confirmed by execution: one malformed line aborts the whole reducer | **Low-risk, filed: `BL-B88`** |

### Risk Communication

**Finding 1 — `_pending_positional_replies` has no size bound**
**Location:** `body-layer/src/belief/crew_console.py` (`_speak_or_defer`,
`drain_pending_positional_replies`, `_pending_positional_replies` field).
**Probability:** low in the healthy/steady-state case — ordinary single-player voice/F10 command
rate never comes close. Requires a sustained flood of recognisable-command audio against the
network-reachable `/transcribe` endpoint (a misbehaving peer, a stuck capture loop, or a malicious
LAN peer) to manifest at all.
**Impact:** medium — unlike the plan review's already-accepted "oversized `correlation_id` grows a
log file" risk, this grows the **live `CrewConsole` process's own memory**, for the whole sortie,
with no operator recourse short of restarting; that process is Petrovich's entire belief/command
state, so a crash there is a flight-ending event, not a deletable file.
**Recommended action:** bound the list the same way `TranscriptQueue`/`F10CommandQueue` already do
— fixed cap, drop-oldest (or reject-new), with a `logger.warning` on the drop.

Options:
  (A) Ignore — I'll document acceptance of this risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — I'll address it before continuing
  (D) Stop — do not proceed until this is resolved

**Filed as `BL-B87`** (`body-layer/ROADMAP/BL-B87.md`) rather than defaulting to (A)/(B)/(C) myself
— the ID exists so the user's choice has somewhere to land; recommend (B) given this batch's own
scope (instrumentation + one already-fixed correctness bug) and the low steady-state probability,
but it is the user's call.

**Finding 2 — `join_voice_latency.py` crashes whole on one malformed JSONL line**
**Location:** `body-layer/tools/join_voice_latency.py` (`_iter_jsonl`).
**Probability:** medium — not rare. The realistic trigger (a process killed mid-write: a DCS crash,
a mission reload, a Windows box power-cycling) is a known, recurring event class this project
already builds mission-restart handling (`BL-15`) and per-mission log-rolling around. The tool is
most likely to be reached for immediately after exactly the kind of event that can produce a
truncated last line.
**Impact:** low — no security impact (not an unsafe deserializer, no injection, no data loss beyond
the log file's own last line); the whole reducer run aborts with a traceback instead of skipping one
bad row, which is an availability/robustness annoyance for whoever is triaging a flight, at the
worst possible moment to have a tool fail.
**Recommended action:** wrap `json.loads(line)` per line in a `try/except json.JSONDecodeError`,
warn with file/line number, skip, continue — matching this project's own "one bad item costs one
item, not the batch" posture already applied to capture clips and queued audio lines elsewhere in
this exact diff.

Options:
  (A) Ignore — I'll document acceptance of this risk
  (B) Add to todo.md — fix in a future session
  (C) Fix now — I'll address it before continuing
  (D) Stop — do not proceed until this is resolved

**Filed as `BL-B88`** (`body-layer/ROADMAP/BL-B88.md`). Recommend (C) if cheap — the fix is a
four-line `try/except` around one call — but filed either way rather than left in prose alone, per
this role's own closing-step rule.

### Verdict

**APPROVED**

No dependency change, no known CVE, no log-structure injection, no path manipulation, no secrets
in logs, no change to network bind posture, no DCS-install write path, no way for a logging failure
to break `/speak`/`/transcribe`/playback/the poll loop, and the plan review's one open item
(`correlation_id`/`t_ptt_release_wall` validation) is correctly applied and tested on all three HTTP
boundaries. Two low-risk findings (unbounded in-memory queue growth under sustained network-driven
flooding; a reducer-tool robustness gap on malformed log lines) are real, confirmed by direct
inspection/execution rather than inferred, and filed as `BL-B87`/`BL-B88` — neither is exploitable
in the security sense, neither expands this project's accepted LAN-trust posture beyond precedent
already set in this feature's own plan review, and neither blocks proceeding to DoD.
