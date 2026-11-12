"""`SpeechWorker`: moves `CrewConsole._print`'s synchronous `push_speech`
call off body-layer's poll thread (`[[BL-B106]]`, `plans/async-speech/
plan.md`), so Petrovich's mouth (Piper synthesis, or full playback under
`--target local`, both measured in seconds) can never stall his eyes and
arms -- the same poll thread that also does perception ingest, F10/
transcript dispatch, and `post_look_direction`.

**Mirrors `aircraft-layer/src/collector/audio_sender.py`'s
`AudioPlaybackSender` shape exactly** (plan Decision 1), not
`belief.brain_client.BrainLayerClient`'s single-slot newest-wins worker:
speech must preserve order and must not silently drop an intermediate
reply just because a later one arrived -- "one mouth... never spoken over
each other" is an ordering/no-skip requirement, unlike brain escalation's
deliberate "the newest question is the only one worth answering"
semantics. So: a bounded FIFO `queue.Queue` plus one background daemon
thread, `open()`/`close()` lifecycle, drop-oldest-on-overflow, and an
`interrupt()` that clears the queue and stops in-flight audio -- the
*queue* here holds speech lines instead of temp `.wav` paths, but the
shape is the same.

**Overflow policy deliberately does *not* copy `AudioPlaybackSender.
_enqueue`'s warn-on-every-drop.** It mirrors `BL-B87`'s
`_pending_positional_replies` instead (`crew_console.
_positional_reply_overflow_warned`): exactly one `WARNING`, on the first
drop, never again for the life of this instance -- per plan Stage 4,
"drop-oldest + exactly one rate-limited WARNING despite multiple drops."
A sustained flood would otherwise flood the log for the rest of the
sortie.

**The worker thread times the `push_speech` call and reports connection
state, but never calls `CrewConsole.speech_log_sink` itself** (plan
Decision 2). `_speech_log_sink`'s closure (`body.py`) reads `runner.
last_t_sim`/`runner.scan_plan`/`runner.last_ownship_state` **live**, by
design -- safe only when called from the poll thread that mutates those
fields. A worker thread calling it directly would be a real cross-thread
data race, not a style nit. So each completed push becomes a
`_SpeechResult` deposited on this worker's own results list; `CrewConsole.
drain_speech_results` (called once per poll, same spot as `drain_events`/
`drain_brain`) pops them and calls `speech_log_sink` **on the poll
thread**, exactly where that closure already assumes it runs.

**`interrupt()` calls `client.stop()` synchronously, on whichever thread
calls it** -- a deliberate, narrow exception to "don't block," matching
`AudioPlaybackSender.play_audio`'s own precedent of calling
`self.interrupt()` inline before enqueueing an urgent line: an interrupt
that itself waits in a queue is not an interrupt. `audio-adapter`'s
server is already `ThreadingHTTPServer` (confirmed, `audio-adapter/src/
server.py:58,501`), so `POST /stop` is already safe to call while a
`POST /speak` is in flight on another connection -- this costs at most
one small round trip, never seconds."""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from belief.audio_client import AudioAdapterError
from connection_reporter import ConnectionReporter

logger = logging.getLogger(__name__)

#: Same value and reasoning as `AudioPlaybackSender._MAX_QUEUE_LEN`/
#: `F10CommandQueue`/`_pending_positional_replies`'s identical cap --
#: generous relative to any plausible callout rate (seconds of speech per
#: line), so this is insurance against a producer bug, not a limit ever
#: expected to bind in normal use. Not a behaviour-affecting tunable
#: (plan Decision/Risks: "the queue bound is a defensive literal"), so it
#: stays an ordinary module literal, no `tuning.py` entry.
_MAX_QUEUE_LEN = 64


class SpeechClient(Protocol):
    """The subset of `belief.audio_client.AudioAdapterClient`'s interface
    this worker needs -- a `Protocol` so a test double (e.g. test_crew_
    console.py's `FakeSpeechClient`) can stand in without inheriting
    from the real client."""

    def push_speech(
        self, text: str, urgent: bool, correlation_id: str | None = None
    ) -> None: ...

    def stop(self) -> None: ...


@dataclass(frozen=True, slots=True)
class _SpeechItem:
    """One queued line, exactly the arguments `CrewConsole._print` has
    on hand at enqueue time."""

    line: str
    bypass_gate: bool
    correlation_id: str | None
    attack_run_fields: dict[str, object] | None


@dataclass(frozen=True, slots=True)
class _SpeechResult:
    """What `_run` deposits once a queued line's `push_speech` call has
    completed (successfully or not) -- everything `CrewConsole.
    drain_speech_results` needs to call `speech_log_sink` with the real
    timings, on the poll thread, after the fact.

    `push_duration_s` is always a real measured value, never `None` --
    matching `CrewConsole._print`'s own existing fallback-path semantics
    (`time.monotonic() - t0` is computed unconditionally after the
    `push_speech` try/except, win or lose), not the plan sketch's
    illustrative "`None` iff `push_speech` raised": the fallback path
    computes a duration on a failed push too, and the two paths should
    agree on what a failed push's row looks like."""

    line: str
    bypass_gate: bool
    correlation_id: str | None
    attack_run_fields: dict[str, object] | None
    push_sent_wall: float
    push_acked_wall: float
    push_duration_s: float


#: Sentinel put on the queue by `close()` to unblock the worker thread's
#: blocking `queue.get()` call -- same mechanism as `AudioPlaybackSender`.
_SENTINEL: _SpeechItem | None = None


class SpeechWorker:
    """Owns a background worker thread + bounded `queue.Queue` of
    `_SpeechItem`s, pushing each one to `client.push_speech` in order.
    See module docstring for the shape and why it mirrors
    `AudioPlaybackSender` rather than `BrainLayerClient`."""

    def __init__(
        self, client: SpeechClient, reporter: ConnectionReporter | None = None
    ) -> None:
        self._client = client
        self._reporter = reporter
        self._queue: queue.Queue[_SpeechItem | None] = queue.Queue(
            maxsize=_MAX_QUEUE_LEN
        )
        self._results: list[_SpeechResult] = []
        self._results_lock = threading.Lock()
        self._worker: threading.Thread | None = None
        #: Set once the first overflow drop has been logged -- see module
        #: docstring's "exactly one `WARNING`" policy. Only ever written
        #: from whichever thread calls `enqueue()` (the poll thread or the
        #: REPL thread, both of which may call `CrewConsole._print`); a
        #: race between the two could in principle log twice instead of
        #: once, which is a cosmetic risk, not a correctness one.
        self._overflow_warned = False

    def open(self) -> None:
        """Starts the background worker thread. Call once, before the
        first `enqueue()` -- mirrors `AudioPlaybackSender.open`."""
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def close(self) -> None:
        """Unblocks and joins the worker thread. Never raises."""
        self._queue.put(_SENTINEL)
        if self._worker is not None:
            self._worker.join(timeout=5)
            self._worker = None

    def enqueue(
        self,
        line: str,
        bypass_gate: bool,
        correlation_id: str | None,
        attack_run_fields: dict[str, object] | None,
    ) -> None:
        """Queues `line` for the worker thread to push, returning
        immediately. `bypass_gate=True` (an injected urgent call) first
        calls `self.interrupt()` -- clearing whatever is queued and
        stopping whatever is in flight -- before its own line joins the
        (now-empty) queue, mirroring `AudioPlaybackSender.play_audio`'s
        own `urgent` branch exactly."""
        if bypass_gate:
            self.interrupt()
        item = _SpeechItem(
            line=line,
            bypass_gate=bypass_gate,
            correlation_id=correlation_id,
            attack_run_fields=attack_run_fields,
        )
        self._put(item)

    def _put(self, item: _SpeechItem) -> None:
        """Enqueues `item`, dropping the **oldest** queued (not-yet-
        pushed) item if the queue is already at `_MAX_QUEUE_LEN` -- a
        stale queued line is worth less than a fresh one, and the
        alternative (a blocking `put`) would stall whichever thread calls
        `enqueue()`, defeating the whole point of this class."""
        while True:
            try:
                self._queue.put_nowait(item)
                return
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    continue
                if not self._overflow_warned:
                    self._overflow_warned = True
                    logger.warning(
                        "speech worker queue full (%d) -- dropping oldest queued line",
                        _MAX_QUEUE_LEN,
                    )

    def interrupt(self) -> None:
        """Drops everything queued and stops whatever is currently
        playing, synchronously, on whichever thread calls this -- see
        module docstring's "narrow exception to don't block." Never
        raises: a failure to interrupt degrades to a logged warning, same
        posture as `AudioPlaybackSender._interrupt_playback`."""
        self._clear_queue()
        try:
            self._client.stop()
        except Exception:
            logger.warning("failed to interrupt in-flight speech", exc_info=True)

    def _clear_queue(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def drain_results(self) -> list[_SpeechResult]:
        """Pops and returns every result deposited since the last drain,
        oldest first. Safe to call from any thread; `CrewConsole.
        drain_speech_results` is this worker's one caller, from the poll
        thread, once per poll."""
        with self._results_lock:
            drained, self._results = self._results, []
            return drained

    def _run(self) -> None:
        while True:
            item = self._queue.get()
            if item is None:
                return
            try:
                self._process(item)
            except Exception:
                # Defense in depth: nothing inside `_process` is expected
                # to raise outside the `AudioAdapterError` it already
                # catches, but an uncaught exception here would silently
                # kill this daemon thread for the rest of the sortie --
                # the same "a future unguarded path must not be able to
                # kill the worker thread" posture `audio_sender.py`'s own
                # SPU-8 volume scaling was hardened with.
                logger.warning(
                    "speech worker: unexpected failure processing queued "
                    "line (continuing)",
                    exc_info=True,
                )

    def _process(self, item: _SpeechItem) -> None:
        push_sent_wall = time.time()
        t0 = time.monotonic()
        try:
            self._client.push_speech(
                item.line, urgent=item.bypass_gate, correlation_id=item.correlation_id
            )
        except AudioAdapterError as exc:
            if self._reporter is not None:
                self._reporter.report_failure(exc)
            else:
                logger.warning(
                    "speech push failed for crew-text line (continuing)",
                    exc_info=True,
                )
        else:
            if self._reporter is not None:
                self._reporter.report_success()
        push_duration_s = time.monotonic() - t0
        push_acked_wall = time.time()
        result = _SpeechResult(
            line=item.line,
            bypass_gate=item.bypass_gate,
            correlation_id=item.correlation_id,
            attack_run_fields=item.attack_run_fields,
            push_sent_wall=push_sent_wall,
            push_acked_wall=push_acked_wall,
            push_duration_s=push_duration_s,
        )
        with self._results_lock:
            self._results.append(result)
