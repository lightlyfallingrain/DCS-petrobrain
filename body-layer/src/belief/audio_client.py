"""HTTP client for `audio-adapter`'s `POST /speak` endpoint (BL-10 first
slice, `plans/tts-voice-output/plan.md` stage 4).

Mirrors `aircraft_client.AircraftLayerClient`'s shape (stdlib
`urllib.request`, one write call) -- this is body-layer's own, independent
copy rather than an import of anything in `audio-adapter/`: `audio-adapter`
must stand alone (root `CLAUDE.md`'s module-independence rule), and the
world-model<->body-layer in-process import is the sole sanctioned
cross-subproject exception, not a precedent to extend here. The seam is
HTTP end to end, same as the aircraft-layer seam.

`push_speech` **raises** `AudioAdapterError` on any transport failure --
a raise-and-let-the-caller-catch contract, not a swallow-internally one --
`CrewConsole._print`'s own `try`/`except` is where that failure is meant
to be caught, per plan Decision 5's "swallow at every hop, but each hop's
own client call still raises so its caller decides how to degrade" shape.

`get_transcripts` (`plans/inbound-speech/plan.md` Stage 3) is this
seam's first *inbound* read -- `GET /transcripts/poll` drains
`audio-adapter`'s `TranscriptQueue`, so its empty state is `[]`, not
`None` (the response is always a JSON list, never `null`). It still
raises `AudioAdapterError` on transport/parse failure, the same posture
as `push_speech` -- **not** a swallow-and-return-`[]` posture, since
`body.py`'s poll loop is the place that decides to log-and-continue, not
this client.

`put_rules`/`get_transcripts`'s added `X-Rules-Version` return value
(`plans/speech-rules/plan.md` D1/D2, `[[BL-17]]`) are this seam's own
rule-push/version mechanism: `body.py` pushes `(id, pattern)` pairs once
at startup and again at every mission (re)start reload, and reads the
version header off every poll to detect an adapter restart (absent/
differing version -> re-push, D2).

`stop()` has its own, separately bounded `stop_timeout_s` rather than
sharing `timeout_s` with `push_speech`/`get_transcripts`
(`plans/async-speech/performance-review.md`'s NOW finding): `/stop` is
reached synchronously from `SpeechWorker.interrupt()`
(`plans/async-speech/plan.md` Decision 3), on the poll thread itself via
`stop_talking` and mission-restart detection, so its timeout bounds a
poll-thread stall directly. `push_speech`'s own `timeout_s` has to cover
Piper synthesis (seconds, by design); `/stop`'s round trip has no
synthesis to wait out, so bounding it separately, and short, keeps a
wedged (not merely down) audio-adapter from stalling the interrupt path
for the full synthesis-sized budget."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

_DEFAULT_TIMEOUT_S = 5.0

#: `/stop` is payload-less and does no synthesis, so it never needs
#: anywhere near `push_speech`'s synthesis-sized budget; this bounds a
#: wedged audio-adapter's worst-case stall on `SpeechWorker.interrupt()`'s
#: synchronous call, reached from the poll thread via `stop_talking` and
#: mission-restart detection. A protocol/network timeout, not a choice
#: Petrovich makes, so an ordinary literal rather than a `tuning.py` entry
#: (same reasoning as `speech_worker._MAX_QUEUE_LEN`).
_DEFAULT_STOP_TIMEOUT_S = 1.0

#: A tilde before a figure is spoken as "about" -- Piper reads "~800" as
#: "tilde 800" (2026-10-20 sortie, user: *"replace "~" with "about" in all
#: speech"*). Applied here, at the one place speech leaves body-layer, so
#: it also covers text no template controls, such as a brain reply.
_TILDE_RE = re.compile(r"~\s*")


class AudioAdapterError(RuntimeError):
    """Raised when `audio-adapter`'s `POST /speak` is unreachable, times out,
    or returns a non-2xx response."""


@dataclass(frozen=True, slots=True)
class AudioAdapterClient:
    """Thin JSON POST client for one `audio-adapter` instance.

    `base_url` has no trailing slash, e.g. `"http://127.0.0.1:7795"` (
    `audio-adapter`'s `POST /speak` default port, see `audio-adapter/src/
    server.py`'s `DEFAULT_PORT`)."""

    base_url: str
    timeout_s: float = _DEFAULT_TIMEOUT_S
    stop_timeout_s: float = _DEFAULT_STOP_TIMEOUT_S

    def push_speech(
        self, text: str, urgent: bool, correlation_id: str | None = None
    ) -> None:
        """`POST /speak` with `{"text": text, "urgent": urgent}`, plus an
        optional `correlation_id` (`plans/voice-latency-instrumentation/
        plan.md` Stage 3) so audio-adapter's own `--latency-log` can be
        joined back to this utterance. Raises `AudioAdapterError` on any
        failure -- see the module docstring for why this call, unlike a
        swallow-internally design, does not catch its own failure."""
        url = f"{self.base_url}/speak"
        text = _TILDE_RE.sub("about ", text)
        body: dict[str, object] = {"text": text, "urgent": urgent}
        if correlation_id is not None:
            body["correlation_id"] = correlation_id
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AudioAdapterError(f"request to {url} failed: {exc}") from exc

    def stop(self) -> None:
        """`POST /stop` (`plans/inbound-speech/plan.md` Stage 3 follow-up)
        -- the interrupt-only counterpart to `push_speech`: no text, no
        `urgent` flag, just a bare request that reaches `audio-adapter`'s
        `AudioSink.interrupt()` directly. Unlike `push_speech`, this never
        synthesizes or delivers any audio -- it exists specifically for
        `stop_talking`, a stated exception to this project's usual
        readback/confirm rule (`crew_console.CrewConsole.
        _handle_stop_talking`'s own docstring), which must interrupt
        playback and say nothing. Raises `AudioAdapterError` on any
        failure, same posture as `push_speech`. Uses `stop_timeout_s`,
        not `timeout_s` -- see the module docstring for why `/stop`'s
        timeout is bounded separately from `push_speech`'s."""
        url = f"{self.base_url}/stop"
        request = urllib.request.Request(
            url,
            data=b"",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self.stop_timeout_s
            ) as response:
                response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AudioAdapterError(f"request to {url} failed: {exc}") from exc

    def get_transcripts(self) -> tuple[list[dict[str, Any]], str | None]:
        """`GET /transcripts/poll` -> drains `audio-adapter`'s recognised-
        speech queue (`audio-adapter/src/transcript_queue.py`,
        `plans/inbound-speech/plan.md` Stage 3), returning every pending
        transcript as a list of dicts (`transcript_queue.TranscriptEvent.
        to_dict`, i.e. `{"transcript", "confidence", "token", "match_ratio",
        "verb_anchored", "ambiguous", "t_wall", "slots", "correlation_id"}`),
        oldest first, plus the `X-Rules-Version` header's value (`[[BL-17]]`
        D2) -- `None` when the header is absent (every adapter before this
        plan, or one that has not yet had a successful `put_rules` call,
        e.g. right after its own restart). Returns `([], ...)` when nothing
        is pending -- see the module docstring for why `[]`, not `None`.
        Raises `AudioAdapterError` on any transport/parse failure, same as
        `push_speech`."""
        url = f"{self.base_url}/transcripts/poll"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout_s) as response:
                body = response.read()
                rules_version = response.headers.get("X-Rules-Version")
        except (urllib.error.URLError, OSError) as exc:
            raise AudioAdapterError(f"request to {url} failed: {exc}") from exc
        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise AudioAdapterError(f"invalid JSON from {url}: {exc}") from exc
        if not isinstance(result, list):
            raise AudioAdapterError(
                f"expected a JSON list from /transcripts/poll, got {type(result).__name__}"
            )
        return result, rules_version

    def put_rules(self, version: str, rules: list[tuple[str, str]]) -> PutRulesResult:
        """`PUT /rules` (`{"version": version, "rules": [{"id", "pattern"},
        ...]}`, D1/D2) -- pushes the full `(id, pattern)` set this process
        currently has loaded. `rules` is unordered; `audio-adapter` sorts
        as needed for its own collision check. Raises `AudioAdapterError`
        on any transport/parse failure, same posture as every other call
        on this client -- `body.py`'s caller decides how to log/retry a
        failed push, this method never swallows one."""
        url = f"{self.base_url}/rules"
        payload = {
            "version": version,
            "rules": [
                {"id": rule_id, "pattern": pattern} for rule_id, pattern in rules
            ],
        }
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="PUT",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                body = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise AudioAdapterError(f"request to {url} failed: {exc}") from exc
        try:
            result = json.loads(body)
        except json.JSONDecodeError as exc:
            raise AudioAdapterError(f"invalid JSON from {url}: {exc}") from exc
        if not isinstance(result, dict):
            raise AudioAdapterError(
                f"expected a JSON object from PUT /rules, got {type(result).__name__}"
            )
        accepted = result.get("accepted", [])
        rejected = result.get("rejected", [])
        if not isinstance(accepted, list) or not isinstance(rejected, list):
            raise AudioAdapterError(
                f"malformed PUT /rules response from {url}: {result!r}"
            )
        return PutRulesResult(
            version=str(result.get("version", version)),
            accepted=tuple(str(rid) for rid in accepted),
            rejected=tuple(
                (str(entry.get("id", "")), str(entry.get("reason", "")))
                for entry in rejected
                if isinstance(entry, dict)
            ),
        )


@dataclass(frozen=True)
class PutRulesResult:
    """`PUT /rules`'s own response, parsed. `rejected` is `(id, reason)`
    pairs -- a rule the adapter would not accept (bad grammar, unknown
    slot type, a collision check hit, D9)."""

    version: str
    accepted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
