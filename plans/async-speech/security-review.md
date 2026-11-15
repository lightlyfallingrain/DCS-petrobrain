## Security Deep Analysis: async-speech (BL-B106)

Branch `feature/async-speech-impl`, tip `12f9d1888c9973e95b57ab1adc56b6e3f31d24c7` (fast-forwarded
into this worktree from `f480cf71`, a strict ancestor; tree was clean). Diff reviewed:
`72fd46e7..12f9d188` (implementation `4387203a`, implementer memory `868b5418`, review `12f9d188`).

Scope per the dispatch prompt: thread-safety of shared state across the poll/worker threads,
queue overflow handling and the rate-limited warning, exception containment in the worker, daemon
thread shutdown, the plan's flagged risk that a dropped line gets no `speech_log_sink` row, and
dependency status. Single-user, LAN-only threat model (malicious dependency code, or an infected
LAN machine port-scanning/connecting) — scoped accordingly, not to player-experience correctness
(Reviewer's remit, already passed).

### Dependency Status

No new dependency. `body-layer/pyproject.toml` is untouched by this diff; `speech_worker.py` and
the touched files import only stdlib (`logging`, `queue`, `threading`, `time`, `dataclasses`,
`typing.Protocol`) plus this project's own `belief.audio_client`/`connection_reporter` modules.
Confirmed by reading the diff's import lines directly, not inferred from the plan's claim.

### What a LAN port scanner / malicious-dependency threat model actually touches here

- **No new listening socket.** `body-layer` remains a pure HTTP *client* of `audio-adapter`
  throughout this change (`grep -n "bind\|listen\|socket.socket"` over the diff's files returns
  nothing but comment text). `SpeechWorker` does not open any socket itself — it calls the
  existing `AudioAdapterClient.push_speech`/`.stop()`, which already carries a `timeout_s`
  (`audio_client.py:59`, pre-existing, unchanged here) on every `urlopen` call. A misbehaving or
  hostile LAN peer answering slowly, not at all, or with garbage therefore cannot wedge this
  worker thread beyond that existing timeout — this is the same protection the poll thread already
  relied on before this change; moving the call to a worker thread does not weaken it, and is in
  fact the point of the change (a wedge there used to stall perception/arms too, now it only
  delays speech).
- **No arbitrary-code-execution surface.** No `eval`/`exec`/deserialization of network data; `line`
  text flows straight into an HTTP POST body and TTS, never into a shell or interpreter. No new
  file paths are built from external data.
- **No secrets** introduced or touched.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `speech_worker.py` `_run`/`_process` | broad `except Exception` wrapping each queued item (`_run`, lines ~235-249) | Prevents an unexpected exception from silently killing the daemon worker thread for the rest of the sortie — the exact failure mode ("Petrovich mute for the sortie") the dispatch prompt flags. Catches `Exception`, not `BaseException`, so it does not mask `SystemExit`/`KeyboardInterrupt` on this (non-main) thread, which is the correct scope. | None — this is the fix, not a gap. |
| `speech_worker.py` `SpeechWorker.__init__`/`_put`/`drain_results` | shared mutable state (`_queue`, `_results`, `_overflow_warned`) across the enqueuing thread(s) and the worker thread | `_queue` is a `queue.Queue`, internally synchronized. `_results` is guarded by `self._results_lock` on both the append (`_process`) and the drain (`drain_results`) side — correct, symmetric locking. `_overflow_warned` is written unlocked from whichever thread calls `enqueue()` (poll thread or REPL thread) with no lock; the module's own docstring names this and calls it "a cosmetic risk, not a correctness one" — correct: the race's only consequence is at most one duplicate `WARNING` line, never a lost/corrupted result or a crash. | None — acceptable, and the risk is already named in the code's own comment rather than silently present. |
| `connection_reporter.py` `report_failure`/`report_success` | read-modify-write of `self._connected` now has two thread callers (`SpeechWorker`'s worker thread, `body._poll_transcripts` on the poll thread) | Fixed with a `threading.Lock` around both methods' bodies, added in this diff specifically for this reason. Verified the lock is acquired before the check-then-set and released (via `with`) before the one `logger` call outside it — the log call itself can duplicate under a race (both threads transition in the same instant) but `_connected` itself cannot land in an inconsistent state. Matches the stated "benign race, lock removes the question" framing. | None. |
| `speech_worker.py` `_put` (queue overflow) | bounded `queue.Queue(maxsize=_MAX_QUEUE_LEN=64)`, drop-oldest via `get_nowait()` on `queue.Full`, exactly one rate-limited `WARNING` (`_overflow_warned` latch, never reset) | Matches the established precedent (`AudioPlaybackSender`/`F10CommandQueue`/`_pending_positional_replies`) this project already accepted for the same risk class — a producer bug cannot grow memory unboundedly, and a sustained overflow cannot flood the log for the rest of the sortie. No new overflow-handling pattern introduced; reusing one already reviewed. | None. |
| `speech_worker.py` `close()` | `self._queue.put(_SENTINEL)` then `self._worker.join(timeout=5)` | A bounded join — if the worker is wedged inside a `push_speech` call past `audio_client`'s own `timeout_s`, `close()` returns anyway after 5s rather than hanging the whole process shutdown. The thread is daemon (`threading.Thread(..., daemon=True)`), so even if it never actually exits, process termination is not blocked by it. No shutdown hang possible from this change. | None. |
| `crew_console.py` `drain_speech_results` | `self.speech_log_sink(...)` wrapped in its own `try`/`except Exception` (continues, logs) | Correctly isolates a sink failure (a debug-logging concern) from speech continuing to work — matches `_print`'s own existing posture for the same call. | None. |
| plan's flagged risk: a dropped (overflow) line gets no `speech_log_sink` row | `speech_worker.py` `_put` | Confirmed in the code: a line dropped by `_put` never becomes a `_SpeechItem` that reaches `_process`, so no `_SpeechResult` is ever produced for it — only the one rate-limited `WARNING` marks the event. This is a logging/observability gap, not a security one: nothing is executed, written, or exposed as a result of the drop: it is a silent loss of one debug-telemetry row for an already-bounded, already-accepted drop-oldest policy that (per the plan's own reasoning and the human-paced production rate of speech lines) is not expected to bind in practice. Already matches the precedent of every other bounded-drop queue in this codebase. Out of scope for a security blocker; it is a correctness/observability nuance Reviewer and the plan's own Risks section already surfaced and accepted. | **Not filed as a new backlog item** — it is the plan's own named, accepted risk (`plan.md` "Risks & Unknowns"), already on record there; no new tracking needed. |

### Assessment against this project's recurring finding classes (memory check)

Checked agent memory for recurring patterns before this analysis
(`aircraft-layer` full audit: "unsupervised daemon threads" as the recurring gap; `body-layer` full
audit 2026-10-05; the SPU-8 `audio_sender.py` unguarded-`frombytes` finding). `SpeechWorker`
explicitly avoids the "unsupervised daemon thread" class flagged for `aircraft-layer/collector`'s
threads: it has an `open()`/`close()` lifecycle with a bounded `join()`, and (per the row above) a
defensive `except Exception` around its own processing loop so an unexpected failure cannot kill
it silently — the implementer's own stated reasoning cites the SPU-8 hardening precedent directly,
and that reasoning checks out against the code.

### Verdict
APPROVED

### Required Fixes
None.
