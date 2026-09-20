"""HTTP client for `audio-adapter`'s `POST /speak` endpoint (BL-10 first
slice, `plans/tts-voice-output/plan.md` stage 4).

Mirrors `aircraft_client.AircraftLayerClient`'s shape (stdlib
`urllib.request`, one write call) -- this is body-layer's own, independent
copy rather than an import of anything in `audio-adapter/`: `audio-adapter`
must stand alone (root `CLAUDE.md`'s module-independence rule), and the
world-model<->body-layer in-process import is the sole sanctioned
cross-subproject exception, not a precedent to extend here. The seam is
HTTP end to end, same as the aircraft-layer seam.

`push_speech` **raises** `AudioAdapterError` on any transport failure,
mirroring `AircraftLayerClient.push_text_line`'s raise-and-let-the-caller-
catch contract, not a swallow-internally one -- `CrewConsole._print`'s own
`try`/`except` (the same funnel `overlay_client`/`aircraft_client` already
go through) is where that failure is meant to be caught, per plan
Decision 5's "swallow at every hop, but each hop's own client call still
raises so its caller decides how to degrade" shape."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

_DEFAULT_TIMEOUT_S = 5.0


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

    def push_speech(self, text: str, urgent: bool) -> None:
        """`POST /speak` with `{"text": text, "urgent": urgent}`. Raises
        `AudioAdapterError` on any failure -- see the module docstring for
        why this call, unlike a swallow-internally design, does not catch
        its own failure."""
        url = f"{self.base_url}/speak"
        data = json.dumps({"text": text, "urgent": urgent}).encode("utf-8")
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
