"""Text-to-speech synthesis for `audio-adapter`
(`plans/audio-adapter-os-independent/plan.md`).

`TTSEngine` is a small `Protocol` -- one method, `synthesize(text) -> bytes`
returning a WAV file's raw bytes -- so `server.py` never has to know which
engine is behind it.

`PiperEngine` is this slice's only implementation: an HTTP client for
Piper's own `piper.http_server`, a long-lived process started by its own
`run-piper-*.sh` script (plan Decision 1) -- structurally identical to
`brain-layer/src/ollama_client.py`'s `OllamaClient` talking to an
independently-started Ollama server. `audio-adapter` never spawns,
supervises, or health-checks that process; a Piper outage or a non-200
response simply fails the next `/speak` call (`TTSSynthesisError`, mapped to
`503` same as any other synthesis failure).

`MacSayEngine` (macOS `say`) is removed entirely, not kept behind a flag
(plan "Settled context"): Piper runs on both OSes with the same voice and
the same behaviour."""

from __future__ import annotations

import json
import logging
import threading
import urllib.error
import urllib.request
from typing import Protocol

logger = logging.getLogger(__name__)

#: Piper's own `piper.http_server`, started independently by
#: `run-scripts/run-piper-mac.sh`/`run-piper-windows.sh` (plan Decision 1) --
#: 7800 is unused elsewhere in this repo (aircraft-layer's collector uses
#: 7790/7792-7799; see `plans/audio-adapter-os-independent/plan.md` Decision 4).
DEFAULT_PIPER_URL = "http://127.0.0.1:7800"

#: User-decided voice (2026-10-19), after the five-voice sample set and the
#: official Piper samples page -- 22050 Hz, mono, 16-bit. Sent as the
#: `"voice"` field on every `/synthesize` POST, which is also the hook
#: AA-B1 (a Russian-accented character voice) will use later, free of
#: charge once this lands.
DEFAULT_PIPER_VOICE = "en_GB-northern_english_male-medium"

_SYNTHESIS_PATH = "/synthesize"

#: Piper's own HTTP request should never hang the server indefinitely.
#: The measured warm case is 0.054-0.098s (recon addendum 2), but "`voice`
#: per request... loaded on first use" means the *first* request for a
#: given voice pays an unmeasured model-load cost in the same order as the
#: ~2s figures seen in the CLI/in-process benchmarks -- this stays generous
#: headroom over that, not a tight budget re-derived from the warm number
#: alone (plan Decision 7).
_SYNTHESIS_TIMEOUT_S = 10.0


class TTSSynthesisError(RuntimeError):
    """Raised when a `TTSEngine` cannot produce audio for the given text
    (unreachable server, non-2xx response, empty/missing body)."""


class TTSEngine(Protocol):
    def synthesize(self, text: str) -> bytes:
        """Return WAV file bytes for `text`. Raises `TTSSynthesisError` on
        any failure -- never returns empty/partial bytes silently."""
        ...


class PiperEngine:
    """`TTSEngine` backed by Piper's `piper.http_server`
    (`plans/audio-adapter-os-independent/plan.md` Decision 1).

    Each call POSTs `{"text", "voice"}` to `<base_url>/synthesize` and
    returns the raw WAV bytes in the response body -- Piper's HTTP server
    returns audio directly, no base64/JSON wrapping. No readiness check and
    no retry: a connection failure, a non-200 response, or an empty body
    all raise `TTSSynthesisError`, which `server.py` maps to `503` exactly
    like `MacSayEngine` used to for a missing `say` binary (plan Decision 3).

    **Outage announcement (Decision 3's amendment).** A Piper outage is not
    "one missed line" -- every `/speak` fails until Piper is restarted, so
    Petrovich goes silent for the rest of the sortie with nothing saying
    why. This class tracks a small `healthy`/`down` state (`self._down`,
    guarded by `self._lock` since `TTSAdapterServer` runs a
    `ThreadingHTTPServer` and two `/speak` calls can fail at once):

    - The first failure after a success (or the very first call ever, if
      Piper was never reachable) logs one line at `WARNING`.
    - Every subsequent failure in the same outage logs at `DEBUG` only, so
      a sortie's worth of callouts does not bury the one line that matters.
    - The first success after an outage logs one `WARNING` recovery line.

    Recovery is automatic: every call still tries Piper, so restarting
    Piper is all the pilot does -- no adapter restart."""

    def __init__(
        self,
        base_url: str = DEFAULT_PIPER_URL,
        voice: str = DEFAULT_PIPER_VOICE,
        timeout_s: float = _SYNTHESIS_TIMEOUT_S,
    ) -> None:
        self._base_url = base_url
        self._voice = voice
        self._timeout_s = timeout_s
        self._lock = threading.Lock()
        self._down = False

    def synthesize(self, text: str) -> bytes:
        if not text.strip():
            raise TTSSynthesisError("cannot synthesize empty text")

        url = f"{self._base_url}{_SYNTHESIS_PATH}"
        body = json.dumps({"text": text, "voice": self._voice}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                audio: bytes = response.read()
        except urllib.error.HTTPError as exc:
            excerpt = exc.read()[:200].decode("utf-8", errors="replace")
            self._report_failure(
                f"Piper at {url} returned {exc.code} -- Petrovich is silent "
                f"until it is back (start run-piper-*.sh): {excerpt.strip()}"
            )
            raise TTSSynthesisError(
                f"Piper returned {exc.code}: {excerpt.strip()}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            self._report_failure(
                f"Piper unreachable at {self._base_url} -- Petrovich is "
                f"silent until it is back (start run-piper-*.sh): {exc}"
            )
            raise TTSSynthesisError(f"Piper request to {url} failed: {exc}") from exc

        if not audio:
            self._report_failure(f"Piper at {url} returned an empty response")
            raise TTSSynthesisError("Piper returned an empty WAV response")

        self._report_success()
        return audio

    def _report_failure(self, message: str) -> None:
        with self._lock:
            was_down = self._down
            self._down = True
        if not was_down:
            logger.warning(message)
        else:
            logger.debug(message)

    def _report_success(self) -> None:
        with self._lock:
            was_down = self._down
            self._down = False
        if was_down:
            logger.warning("Piper back at %s -- speech restored", self._base_url)
