"""HTTP client for `brain-layer`'s `POST /escalate` / `GET /replies/poll`
(`plans/brain-layer/plan.md` D1/D2) -- `BrainLayerClient`, the first real
(non-stand-in) implementation of `belief.escalation.BrainClient`.

Mirrors `aircraft_client.AircraftLayerClient`/`belief.audio_client.
AudioAdapterClient`'s shape (stdlib `urllib.request`, this subproject's
own independent copy rather than an import of anything in `brain-layer/`
-- module independence, the world-model seam is the sole sanctioned
in-process exception) with one structural difference: `handle()` must
**never block the caller**, even briefly (D2's user constraint: "the
game world moves on"). A synchronous `urlopen` call -- even a fast one --
sits on `logger.py`'s 5 Hz poll thread if called directly, so `handle()`
instead hands the payload to a **single-slot background worker thread**
and returns in microseconds; the worker does the actual POST.

**The single slot is this client's own local newest-wins mirror of
`brain-layer`'s server-side `job.JobSlot` (D3).** If `handle()` is called
again while the worker is still mid-POST (the brain is slow or wedged),
the new payload simply overwrites the slot -- the worker, once free,
posts only the most recently handed-over payload. This is deliberate and
cheap, not a queue: D3 already establishes that the newest utterance is
the one worth answering, and a client-side queue would just relocate the
staleness problem D3 solves server-side to the network hop.

**`poll_replies()` no longer performs its own network call on the
caller's thread** (`plans/brain-layer/plan.md`'s pre-Stage-2 prerequisite
1, `plans/brain-layer/performance-review.md`). It used to be a plain
synchronous GET, bounded only by `poll_timeout_s` (5.0s) -- fine against a
down brain (a fast connection-refused, measured 13.4ms) but not against a
*wedged* one (TCP-accepted, never answering): measured at exactly
`poll_timeout_s`, every single poll, with no backoff, degrading the
shared crew-text poll thread's cycle by ~83% at its 1s default interval
and taking perception/F10/transcripts/gaze down with it -- because
nothing else on that thread runs until this one 5s call returns.

The fix mirrors `handle()`'s own shape exactly, per the user's own
2026-09-25 direction ("brain must not block any other functionality...
if thinking takes time, other things happen meanwhile"): a **persistent
background thread**, started lazily on first `poll_replies()` call, loops
forever doing the actual `GET /replies/poll` round trip and depositing
whatever it receives into a small internal buffer. `poll_replies()`
itself never touches the network at all -- it only drains that buffer
under a lock and returns, in microseconds, regardless of whether the far
side is healthy, down, or wedged. A wedged brain therefore degrades this
client's own *reply latency* (replies simply stop arriving in the buffer
until the background thread's in-flight call eventually times out and
retries), never the crew-text poll thread's tick rate -- proven directly
in `tests/test_crew_console.py`'s
`test_drain_brain_tick_rate_unaffected_by_a_wedged_brain` and at this
client's own level in `test_brain_client.py`."""

from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from belief.escalation import BrainReply, EscalationPayload
from belief.utterance import PartialParse

logger = logging.getLogger(__name__)

#: D2: "a short timeout (0.5s)" -- the POST itself must not sit on the
#: worker thread any longer than this even when the brain is wedged,
#: since a wedged POST would delay every *subsequent* utterance from
#: reaching the worker's single slot (the slot cannot be overwritten
#: while a POST using it is still in flight).
_ESCALATE_TIMEOUT_S = 0.5

#: Per network round trip inside the background poll thread's own loop
#: (module docstring) -- generous, matching every other client's own
#: default. This is no longer a bound on anything the crew-text poll
#: thread waits for; it only bounds how long one background-thread
#: iteration can take before it gives up and retries.
_POLL_TIMEOUT_S = 5.0

#: How long the background poll thread sleeps between successful (or
#: fast-failing, e.g. connection-refused) rounds -- keeps it from
#: hammering a healthy `brain-layer` instance with back-to-back requests
#: (measured at 0.306ms/call empty, per the performance review, so this
#: is about network/CPU courtesy, not correctness).
_POLL_LOOP_INTERVAL_S = 0.2

#: After a failed round (a real wedge, or the process simply not running
#: yet), back off before retrying rather than immediately re-attempting --
#: avoids a tight retry loop against a down/wedged server. Independent of
#: `_POLL_TIMEOUT_S`: a wedged call already costs up to that much time on
#: its own before this backoff ever applies.
_POLL_RETRY_BACKOFF_S = 1.0


class BrainLayerError(RuntimeError):
    """Raised internally, inside the background poll thread's own loop,
    when one `GET /replies/poll` round trip fails (unreachable, timed
    out, or a malformed response) -- caught there, logged, and retried
    after `_POLL_RETRY_BACKOFF_S`. **`poll_replies()` itself never raises
    this** (a behaviour change from Stage 1's synchronous version): a
    background-thread failure has no synchronous caller to raise to, and
    "the game world moves on" applies here exactly as it already does to
    `handle()`. Kept as a public name since tests and callers may still
    want to catch it around the rare case of constructing/using this
    client incorrectly."""


def _partial_parse_to_dict(parse: PartialParse) -> dict[str, Any]:
    """Serialises `belief.utterance.PartialParse` across the wire --
    `plans/brain-layer/plan.md`'s affected-files note: "`EscalationPayload`
    gains the candidate list the brain needs -- it is already in
    `partial_parse`, so this is serialisation, not new belief." No field
    here is derived from ground truth; every value already existed in
    body's own belief-derived `PartialParse`/`ReferenceCandidate`
    (`belief.utterance`), which itself is built from `belief.tools.
    find_contact`'s summary text, not from any DCS object id or raw
    position (the identity invariant `belief.tools`' own docstring
    states)."""
    return {
        "matched_intent": parse.matched_intent,
        "confidence": parse.confidence,
        "disposition": parse.disposition,
        "reason_escalated": parse.reason_escalated,
        "attention_level": parse.attention_level,
        "referenced_contact_id": parse.referenced_contact_id,
        "referenced_contact_candidates": [
            {"id": candidate.id, "why": candidate.why}
            for candidate in parse.referenced_contact_candidates
        ],
    }


def _payload_to_dict(payload: EscalationPayload) -> dict[str, Any]:
    return {
        "utterance_id": payload.utterance_id,
        "transcript": payload.transcript,
        "transcript_confidence": payload.transcript_confidence,
        "t_sim": payload.t_sim,
        "partial_parse": _partial_parse_to_dict(payload.partial_parse),
        "situational_header": payload.situational_header,
        "awaiting_reply_to": payload.awaiting_reply_to,
    }


def _reply_from_dict(data: dict[str, Any]) -> BrainReply | None:
    """Defensive structural parse of one `GET /replies/poll` item -- `None`
    (skip, not raise) on anything malformed, the same "schema mismatch is
    skipped, not fatal" posture `logger._poll_transcripts` already applies
    to its own drain-on-poll payload. This is *not* D10's validator (that
    checks a reply's *semantic* legality -- a `PICK`'s id was actually
    offered, a `BECAUSE` clause's words actually appear in the transcript
    -- against the original payload; Stage 2's job, once a real model can
    produce a malformed answer at all). `StubDecider` never emits anything
    this structural check would reject."""
    utterance_id = data.get("utterance_id")
    kind = data.get("kind")
    if not isinstance(utterance_id, str) or not utterance_id:
        return None
    if kind not in ("pick", "ask", "confirm", "unable"):
        return None
    t_sim = data.get("t_sim")
    if t_sim is not None and not isinstance(t_sim, (int, float)):
        return None
    contact_id = data.get("contact_id")
    because = data.get("because")
    token = data.get("token")
    reason = data.get("reason")
    for value in (contact_id, because, token, reason):
        if value is not None and not isinstance(value, str):
            return None
    return BrainReply(
        utterance_id=utterance_id,
        kind=kind,
        t_sim=float(t_sim) if t_sim is not None else None,
        contact_id=contact_id,
        because=because,
        token=token,
        reason=reason,
    )


@dataclass
class BrainLayerClient:
    """`belief.escalation.BrainClient` over HTTP against a running
    `brain-layer` instance. `base_url` has no trailing slash, e.g.
    `"http://127.0.0.1:7796"` (`brain-layer/src/server.py`'s
    `DEFAULT_PORT`)."""

    base_url: str
    escalate_timeout_s: float = _ESCALATE_TIMEOUT_S
    poll_timeout_s: float = _POLL_TIMEOUT_S
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _pending: dict[str, Any] | None = field(default=None, repr=False)
    _worker: threading.Thread | None = field(default=None, repr=False)
    #: `awaiting_reply_id()` is never non-`None` from this client in Stage
    #: 1 -- the A/B answer round trip that would set it is Stage 3's own
    #: addition (`plans/brain-layer/plan.md`), not built yet. Kept as a
    #: real field (not a hardcoded `None` return) so Stage 3 has
    #: somewhere to write it without changing this class's shape.
    _awaiting_reply_id: str | None = field(default=None, repr=False)
    #: Guards `_poll_buffer` and `_poll_worker` -- separate from `_lock`
    #: above (which guards the unrelated `handle()` slot) so a poll-thread
    #: iteration and a `handle()` call never contend on the same lock.
    _poll_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _poll_worker: threading.Thread | None = field(default=None, repr=False)
    #: Replies the background poll thread has received but `poll_replies()`
    #: has not yet drained. Almost always 0-1 items (mirrors
    #: `brain-layer`'s own `ReplyQueue`, which is drained on every
    #: successful background-thread round trip), never explicitly bounded
    #: since it is drained at least once per `_POLL_LOOP_INTERVAL_S`.
    _poll_buffer: list[BrainReply] = field(default_factory=list, repr=False)

    def handle(self, payload: EscalationPayload) -> None:
        """Hands `payload` to the single-slot background worker and
        returns immediately -- see module docstring. Never raises and
        never blocks on the network."""
        with self._lock:
            self._pending = _payload_to_dict(payload)
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(
                    target=self._drain_pending_loop, daemon=True
                )
                self._worker.start()

    def _drain_pending_loop(self) -> None:
        """Runs on the background worker thread: repeatedly take whatever
        is currently in the single slot and POST it, until the slot is
        empty. A `handle()` call that lands on `self._pending` while a
        POST is in flight is picked up by the *next* iteration, not lost
        -- but if two calls land before this thread reads the slot at
        all, only the newer one survives (module docstring's newest-wins
        mirror of D3)."""
        while True:
            with self._lock:
                data = self._pending
                self._pending = None
                if data is None:
                    return
            self._post_escalate(data)

    def _post_escalate(self, data: dict[str, Any]) -> None:
        url = f"{self.base_url}/escalate"
        body = json.dumps(data).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.escalate_timeout_s
            ) as response:
                response.read()
        except (urllib.error.URLError, OSError) as exc:
            # Per module docstring: "the game world moves on" -- a failed
            # escalation degrades to the same silence NullBrainClient
            # already documents as honest, never a raised exception on
            # the poll thread.
            logger.warning(
                "escalation POST to %s failed (continuing)", url, exc_info=exc
            )

    def awaiting_reply_id(self) -> str | None:
        return self._awaiting_reply_id

    def poll_replies(self) -> list[BrainReply]:
        """Starts the background poll thread on first call (lazily, like
        `handle()`'s own worker), then drains and returns whatever it has
        already received, oldest first. **Never touches the network and
        never blocks or raises** -- see module docstring. Safe to call
        from a hot 5Hz loop regardless of whether `brain-layer` is
        healthy, down, or wedged."""
        with self._poll_lock:
            if self._poll_worker is None or not self._poll_worker.is_alive():
                self._poll_worker = threading.Thread(
                    target=self._poll_loop, daemon=True
                )
                self._poll_worker.start()
            drained = self._poll_buffer
            self._poll_buffer = []
            return drained

    def _poll_loop(self) -> None:
        """Runs forever on the background poll thread (a daemon thread,
        same posture as `handle()`'s worker -- never joined, exits only
        when the process does): repeatedly perform the actual `GET
        /replies/poll` round trip and append whatever it returns to
        `_poll_buffer`. A failed round (unreachable or wedged) is logged
        and retried after `_POLL_RETRY_BACKOFF_S` -- this thread is the
        only place `BrainLayerError` is ever raised or caught in this
        client."""
        while True:
            try:
                replies = self._poll_once()
            except BrainLayerError:
                logger.warning(
                    "background brain reply poll failed (retrying)", exc_info=True
                )
                time.sleep(_POLL_RETRY_BACKOFF_S)
                continue
            if replies:
                with self._poll_lock:
                    self._poll_buffer.extend(replies)
            time.sleep(_POLL_LOOP_INTERVAL_S)

    def _poll_once(self) -> list[BrainReply]:
        """One `GET /replies/poll` round trip -> every reply decided
        since the last poll, oldest first. Raises `BrainLayerError` on
        any transport/parse failure -- only ever called from
        `_poll_loop`, on the background thread."""
        url = f"{self.base_url}/replies/poll"
        try:
            with urllib.request.urlopen(url, timeout=self.poll_timeout_s) as response:
                body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise BrainLayerError(f"request to {url} failed: {exc}") from exc
        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise BrainLayerError(f"invalid JSON from {url}: {exc}") from exc
        if not isinstance(result, list):
            raise BrainLayerError(
                f"expected a JSON list from /replies/poll, got {type(result).__name__}"
            )
        replies: list[BrainReply] = []
        for item in result:
            if not isinstance(item, dict):
                continue
            reply = _reply_from_dict(item)
            if reply is not None:
                replies.append(reply)
        return replies


__all__ = ["BrainLayerClient", "BrainLayerError"]
