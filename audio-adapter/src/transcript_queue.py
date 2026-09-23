"""The inbound-speech counterpart to `server.py`'s outbound `/speak` path
(`plans/inbound-speech/plan.md` Stage 3) -- a **bounded FIFO event queue**,
not a "latest" cache, mirroring `aircraft-layer/src/collector/cache.py`'s
`F10CommandQueue` shape and its own reasoning almost exactly: two spoken
transmissions landing inside one body-layer poll interval must both
survive, and a single-slot cache would silently collapse them into one --
a real behavioral loss for discrete commands in the same way it would be
for F10 selections.

`POST /transcribe` (`server.py`) pushes one `TranscriptEvent` per
recognised clip; `GET /transcripts/poll` drains all of them, oldest first,
mutating this queue's state on every call (drain-on-GET, at-most-once
delivery, same contract `F10CommandQueue.drain_all`/`GET /f10_commands/
poll` already established) -- consistent with the plan's own "two-poller
load on the collector" risk note: body-layer is the only poller of this
endpoint, so `/f10_commands/poll`'s single-poller caveat is not violated
by adding a second, differently-named drain-on-GET endpoint.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

#: Bounded so a pathological flood of transcribed clips (or a stuck
#: poller) cannot grow this queue unboundedly -- same generous-relative-to-
#: plausible-rate reasoning as `F10CommandQueue`'s own bound: a player can
#: only press PTT so many times per second.
_MAX_QUEUE_LEN = 64


@dataclass(frozen=True)
class TranscriptEvent:
    """One recognised-and-matched transcript, exactly the eight fields
    `plans/inbound-speech/plan.md` Decision 6's `GET /transcripts/poll` row
    names, extended by `plans/voice-command-completeness/plan.md` Stage 3 --
    text and match metadata only, **never** audio bytes, a WAV path, or
    which engine ran (the plan's "body-layer never sees audio" invariant).
    `token`/`match_ratio`/`verb_anchored`/`ambiguous`/`bearing_degrees` are
    `command_matcher.MatchResult`'s own fields, carried through unchanged
    -- see that dataclass's docstring for why `token`/`match_ratio`/
    `verb_anchored`/`ambiguous` are all required rather than `token`/
    `match_ratio` alone: `token=None` cannot by itself distinguish "not a
    command attempt" from "verb-anchored but unresolved" from "ambiguous",
    three behaviourally distinct outcomes. `bearing_degrees` was
    previously computed by `command_matcher.match_transcript` and then
    dropped at this exact wire -- `TranscriptEvent` carried only seven
    fields, so a perfectly recognised "scan bearing three two zero" arrived
    at body-layer as a bare token with no number; this field is the fix.
    `t_wall` is `time.time()` at the moment `POST /transcribe` recognised
    the clip, not when body-layer eventually polls it."""

    transcript: str
    confidence: float
    token: str | None
    match_ratio: float
    verb_anchored: bool
    ambiguous: bool
    t_wall: float
    bearing_degrees: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "transcript": self.transcript,
            "confidence": self.confidence,
            "token": self.token,
            "match_ratio": self.match_ratio,
            "verb_anchored": self.verb_anchored,
            "ambiguous": self.ambiguous,
            "t_wall": self.t_wall,
            "bearing_degrees": self.bearing_degrees,
        }


class TranscriptQueue:
    """Holds pending recognised transcripts -- `push`/`drain_all`, the same
    two-method shape as `F10CommandQueue` (see this module's own docstring
    for why a FIFO rather than a latest-value cache)."""

    def __init__(self, maxlen: int = _MAX_QUEUE_LEN) -> None:
        self._queue: deque[TranscriptEvent] = deque(maxlen=maxlen)

    def push(self, event: TranscriptEvent) -> None:
        """Enqueue one newly-recognised transcript. If the queue is
        already at `maxlen`, the oldest pending event is silently dropped
        (deque's own overflow behavior) -- an accepted, at-most-once-class
        loss, only reachable at a pathological transcription rate."""
        self._queue.append(event)

    def drain_all(self) -> list[TranscriptEvent]:
        """Remove and return every currently-queued event, oldest first.
        Uses repeated `popleft()` rather than a snapshot-then-clear so a
        `push` racing this call is never silently dropped by a `clear()`
        that fires after the snapshot was taken -- each `popleft()` is
        itself atomic under the GIL (same reasoning as `F10CommandQueue.
        drain_all`)."""
        drained: list[TranscriptEvent] = []
        while True:
            try:
                drained.append(self._queue.popleft())
            except IndexError:
                return drained
