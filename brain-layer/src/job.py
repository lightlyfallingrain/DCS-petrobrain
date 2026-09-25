"""The brain's single-slot job holder and newest-wins replacement policy
(`plans/brain-layer/plan.md` D3: "The brain holds at most one job. A new
escalation arriving while one is in flight replaces it; the abandoned
job's reply is discarded by `utterance_id` when it lands.")

**Not a queue.** D3 is explicit that FIFO is the wrong shape here -- the
second utterance is usually the more important one ("no, the other one"),
and answering a stale question after the pilot has moved on is worse than
not answering it. `JobSlot` therefore tracks only a generation counter: a
worker started for generation N checks `is_current(n)` immediately before
publishing its result, so a superseded job's (possibly still-running)
decider call never has its answer delivered -- `server.py`'s `_run_job` is
where that check happens.

**D3's `awaiting_reply_to` exception is deliberately not implemented
here.** D3: "an utterance whose `awaiting_reply_to` matches the
currently-open question is the answer to it, not a replacement." Nothing
in Stage 1 ever sets `awaiting_reply_to` on an outgoing payload -- that is
Stage 3's job (`plans/brain-layer/plan.md` Stage 3, wiring
`awaiting_reply_id`/`awaiting_reply_to`). Building the exception now would
be untestable dead code; `submit` always bumps the generation, which is
the correct (and only reachable) behaviour until Stage 3 lands."""

from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Job:
    """One escalation, as received by `POST /escalate` -- `payload` is the
    raw JSON body (`belief.escalation.EscalationPayload`, serialised by
    `belief.brain_client.BrainLayerClient`), kept as a plain dict since
    this process has no reason to import body-layer's dataclasses (module
    independence -- the seam is HTTP/JSON, per root `CLAUDE.md`)."""

    utterance_id: str
    payload: dict[str, Any]


class JobSlot:
    """The brain's one in-flight job. Thread-safe: `submit` is called from
    the HTTP handler thread, `is_current` from whichever worker thread is
    running that job's `Decider.decide` call."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generation = 0

    def submit(self, job: Job) -> int:
        """Registers `job` as the current job, superseding whatever was
        previously in flight, and returns this job's generation number --
        the worker started for `job` must present this back to
        `is_current` before publishing its result (see module
        docstring)."""
        with self._lock:
            self._generation += 1
            return self._generation

    def is_current(self, generation: int) -> bool:
        """Whether `generation` (as returned by an earlier `submit`) is
        still the most recently submitted job -- `False` once a later
        `submit` has run, meaning that job's result must be discarded
        rather than published."""
        with self._lock:
            return generation == self._generation


#: Bounded so a pathological flood (or a stuck poller) cannot grow this
#: queue unboundedly -- same reasoning as `audio-adapter/src/
#: transcript_queue.py`'s `_MAX_QUEUE_LEN`. Since `JobSlot` only ever
#: admits one decision at a time, this queue realistically holds 0-1
#: items; the bound is a defensive ceiling, not a sizing decision.
_MAX_REPLY_QUEUE_LEN = 64


class ReplyQueue:
    """Holds decided-but-not-yet-polled replies -- `push`/`drain_all`, the
    same bounded-FIFO shape as `audio-adapter/src/transcript_queue.py`'s
    `TranscriptQueue` (drain-on-GET, at-most-once delivery). `GET
    /replies/poll` (`server.py`) is this queue's one reader."""

    def __init__(self, maxlen: int = _MAX_REPLY_QUEUE_LEN) -> None:
        self._queue: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def push(self, reply: dict[str, Any]) -> None:
        self._queue.append(reply)

    def drain_all(self) -> list[dict[str, Any]]:
        """Remove and return every currently-queued reply, oldest first.
        Repeated `popleft()` rather than snapshot-then-clear, same
        race-safety reasoning as `TranscriptQueue.drain_all`."""
        drained: list[dict[str, Any]] = []
        while True:
            try:
                drained.append(self._queue.popleft())
            except IndexError:
                return drained
