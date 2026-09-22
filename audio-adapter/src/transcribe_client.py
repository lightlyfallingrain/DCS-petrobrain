"""HTTP client for the adapter's own `POST /transcribe` endpoint.

`plans/inbound-speech/plan.md` Stage 4's transit. The audio direction
Slice 1 already built runs Mac -> Windows (`POST /audio/play`); this is
its inverse, and it deliberately looks like it rather than inventing a
second audio-transport idiom (settled point 3, user 2026-09-19): base64
WAV in a JSON body, stdlib `urllib`, raise on failure.

The capture process holds this client and nothing else about
recognition. It does not know which model runs, or whether the transcript
matched a command -- the answer comes back through body-layer's poll of
`GET /transcripts/poll`, not through this call's response. That is what
lets capture run on a box with no model on it.
"""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request

_DEFAULT_TIMEOUT_S = 30.0

_TRANSCRIBE_PATH = "/transcribe"


class TranscribeError(RuntimeError):
    """Raised when the adapter is unreachable, times out, or answers
    non-2xx. A `503` here is the normal, informative case: the adapter is
    running without `--whisper-model`, so no recogniser is configured."""


class TranscribeClient:
    """Thin JSON POST client for one adapter's `POST /transcribe`.

    `base_url` has no trailing slash, e.g. `"http://192.168.1.20:7795"`.

    The timeout is 30 s rather than the 5 s this subproject's other
    clients use, and that is deliberate: whisper runs synchronously
    inside the request, so the response waits for a real transcription
    rather than a queue push. A too-short timeout would report failures
    for clips that were in fact recognised fine.
    """

    def __init__(self, base_url: str, timeout_s: float = _DEFAULT_TIMEOUT_S) -> None:
        self._base_url = base_url
        self._timeout_s = timeout_s

    def transcribe(self, wav: bytes) -> None:
        """`POST /transcribe` with `{"wav_b64": <base64 WAV>}`.

        Returns nothing on success: the endpoint answers `{"ok": true}`
        and the recognised text lands in the adapter's transcript queue
        for body-layer to poll. Raises `TranscribeError` on any failure.
        """
        url = f"{self._base_url}{_TRANSCRIBE_PATH}"
        body = {"wav_b64": base64.b64encode(wav).decode("ascii")}
        request = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise TranscribeError(f"request to {url} failed: {exc}") from exc
