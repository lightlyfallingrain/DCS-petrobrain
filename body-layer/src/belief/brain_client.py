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

**`poll_replies()` is a plain synchronous GET**, unlike `handle()` --
called once per poll from `belief.crew_console.CrewConsole.drain_brain`,
the same drain-on-poll shape `AudioAdapterClient.get_transcripts`/
`AircraftLayerClient.get_f10_commands` already use. A slow poll here is
bounded by `timeout_s` and, worst case, costs one poll's worth of
latency -- unlike `handle()`, there is no reply to lose by waiting for
this call, since the replies are already sitting in `brain-layer`'s own
queue regardless of when body asks for them."""

from __future__ import annotations

import json
import logging
import threading
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

#: `poll_replies()` has no equivalent urgency constraint (module
#: docstring) -- generous, matching every other client's own default.
_POLL_TIMEOUT_S = 5.0


class BrainLayerError(RuntimeError):
    """Raised by `poll_replies()` when `brain-layer` is unreachable, times
    out, or returns a malformed response. `handle()` never raises -- see
    its own docstring; any transport failure there is logged and
    dropped, mirroring "the game world moves on"."""


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
        """`GET /replies/poll` -> every reply decided since the last poll,
        oldest first. Raises `BrainLayerError` on any transport/parse
        failure -- `belief.crew_console.CrewConsole.drain_brain` is where
        that failure is meant to be caught (log-and-continue, the same
        division `_poll_f10_commands`/`_poll_transcripts` already draw
        against their own clients)."""
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
