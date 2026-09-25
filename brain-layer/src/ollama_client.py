"""Stdlib HTTP client for Ollama's `/api/generate` endpoint
(`plans/brain-layer/plan.md` Stage 2, D6) -- the only network call
`OllamaDecider` makes. `urllib.request`, no dependency, matching this
subproject's own stdlib-only policy (`brain-layer/CLAUDE.md`).

**`stream=false`, a small `num_predict`, and an explicit `num_ctx`** --
D5/D6: the model's entire output is one short line drawn from a closed
vocabulary (measured at six tokens), so there is nothing to stream, and
D6 measured the *default* 32k context costing 4.6GB of KV cache this
layer never touches against BR-1's own ~155-token prompts -- `num_ctx`
is always passed explicitly by the caller, never left to Ollama's own
default.

**The per-request timeout here is the real fix for a hung Ollama
daemon** (`plans/brain-layer/performance-review.md`'s second finding,
`server.py`'s own docstring on why its `DEFAULT_DECIDE_TIMEOUT_S`
wrapper is a decider-agnostic backstop, not the primary mechanism): a
bounded `urllib.request.urlopen(..., timeout=...)` call means
`Decider.decide()` reliably returns -- successfully or via
`OllamaRequestError` -- well inside `server.py`'s own bound, rather than
depending on that bound to ever notice a still-blocked thread."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

#: Per network round trip. Deliberately shorter than `server.py`'s
#: `_DEFAULT_DECIDE_TIMEOUT_S` (12.0s) -- `OllamaDecider.decide()` makes
#: at most two sequential calls (D5's classify/discriminate split), so
#: two of these plus overhead must still fit inside that outer bound.
DEFAULT_TIMEOUT_S = 5.0


class OllamaRequestError(RuntimeError):
    """Raised on any transport failure, non-2xx response, or malformed
    JSON from Ollama's `/api/generate`. `OllamaDecider.decide()` treats
    this exactly like any other `Decider` failure -- `server.py`'s
    `_run_job` already logs and drops the job for any exception."""


@dataclass(frozen=True, slots=True)
class OllamaClient:
    """Thin client for one Ollama daemon instance. `base_url` has no
    trailing slash, e.g. `"http://127.0.0.1:11434"` (Ollama's own
    default)."""

    base_url: str = "http://127.0.0.1:11434"
    timeout_s: float = DEFAULT_TIMEOUT_S

    def generate(
        self,
        model: str,
        prompt: str,
        num_ctx: int,
        num_predict: int,
    ) -> str:
        """`POST /api/generate` with `stream: false`, returning the
        model's raw `response` text (untrimmed -- callers own their own
        parsing, per `decider.py`'s prompt-shape functions). Raises
        `OllamaRequestError` on any failure."""
        url = f"{self.base_url}/api/generate"
        body = json.dumps(
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": num_ctx, "num_predict": num_predict},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                raw = response.read()
        except (urllib.error.URLError, OSError) as exc:
            raise OllamaRequestError(f"request to {url} failed: {exc}") from exc
        try:
            result = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise OllamaRequestError(f"invalid JSON from {url}: {exc}") from exc
        if not isinstance(result, dict) or not isinstance(result.get("response"), str):
            raise OllamaRequestError(
                f"expected a JSON object with a string 'response' from {url}, "
                f"got {result!r}"
            )
        text: str = result["response"]
        return text

    def warm_up(self, model: str, num_ctx: int) -> None:
        """One throwaway generation, called once at startup
        (`plans/brain-layer/plan.md` D8's mitigation: "issuing one
        throwaway warm-up generation when brain-layer starts" -- so the
        first real escalation never pays the 1.4-1.8s cold-load latency
        D8 measured). `num_predict=1` -- the point is loading the model
        into memory, not the answer. Raises `OllamaRequestError` on
        failure; `__main__.py` is where that is caught and logged rather
        than treated as fatal (Ollama may simply not be up yet)."""
        self.generate(model=model, prompt="ready?", num_ctx=num_ctx, num_predict=1)


__all__ = ["DEFAULT_TIMEOUT_S", "OllamaClient", "OllamaRequestError"]
