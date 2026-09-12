"""HTTP client for a local Ollama daemon's `/api/chat` endpoint
(`plans/mi4-capable-model-synthesis/plan.md`).

Mirrors `world_enrich/world_model_client.py`'s shape: stdlib
`urllib.request` only, a frozen/slots dataclass wrapping `base_url`/
`model`/`timeout_s`, one method per call.

**Two distinct exception types, not one** -- unlike `WorldModelClient`'s
single `WorldModelClientError`, this client's two failure modes need
different caller-facing handling:

- `OllamaUnavailableError`: the daemon itself could not be reached at all
  (connection refused/timeout/DNS failure). This is an environment problem
  the user fixes (start Ollama, check the port) -- not something
  `synth/synthesize.py` should try to paper over.
- `OllamaOutputError`: the daemon responded (including a non-2xx HTTP
  status, which still means it is reachable and running), but the body
  isn't valid JSON, or the model's own JSON output isn't valid JSON, or
  doesn't parse to the object shape this client expects. This is a
  prompt/model-quality problem `synthesize.py` degrades on (leaves the
  affected field unpopulated) rather than treating as fatal.

Both subclass `OllamaClientError` for callers that don't need the
distinction.

**Structured-output request shape (`format` + `think: false`) is designed
against Ollama's documented `/api/chat` API, not confirmed live against
the specific installed daemon version or `qwen3:14b`** -- `qwen3:14b` is
not pulled locally yet, and this implementation session had no outbound
network access to double-check the request/response shape against the
running daemon (see the plan's "Prerequisite check" and Risks section).
Treat `chat_json`'s exact request/response parsing as a real thing to
re-verify once the model is pulled and a live call can be made -- if the
daemon's actual behavior differs (e.g. `format` or `think` is silently
ignored, or the response envelope differs), that is a finding to design
around, not an assumption this module gets to keep unexamined.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

_DEFAULT_BASE_URL = "http://127.0.0.1:11434"
_DEFAULT_TIMEOUT_S = 120.0


class OllamaClientError(RuntimeError):
    """Base class for both Ollama client failure modes -- see this
    module's docstring for why they're kept distinct."""


class OllamaUnavailableError(OllamaClientError):
    """The Ollama daemon could not be reached at all (connection refused,
    timeout, DNS failure)."""


class OllamaOutputError(OllamaClientError):
    """The daemon responded, but its body -- or the model's own JSON
    output nested inside it -- isn't valid JSON, or isn't the expected
    shape."""


@dataclass(frozen=True, slots=True)
class OllamaClient:
    """One Ollama daemon + model binding. `base_url` has no trailing
    slash, e.g. `"http://127.0.0.1:11434"` (Ollama's default port)."""

    model: str
    base_url: str = _DEFAULT_BASE_URL
    timeout_s: float = _DEFAULT_TIMEOUT_S

    def chat_json(
        self, messages: list[dict[str, str]], json_schema: dict[str, Any]
    ) -> dict[str, Any]:
        """POST `/api/chat` requesting structured JSON output via Ollama's
        `format` parameter (a JSON Schema) and non-thinking mode
        (`think: false`) -- see this module's docstring for the
        not-live-verified caveat on this exact request shape.

        Returns the parsed JSON object found in the response envelope's
        `message.content`. Raises `OllamaUnavailableError` if the daemon
        cannot be reached, `OllamaOutputError` for every other failure to
        produce a well-shaped JSON object (non-2xx status, invalid JSON at
        either the envelope or `message.content` level, or a
        `message.content` that isn't a JSON object)."""
        payload = {
            "model": self.model,
            "messages": messages,
            "format": json_schema,
            "stream": False,
            "think": False,
        }
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                response_body = response.read()
        except urllib.error.HTTPError as exc:
            # The daemon is reachable and responded -- just not with a
            # usable answer. Treated as an output problem, not an
            # unavailable-daemon problem.
            raise OllamaOutputError(
                f"Ollama returned HTTP {exc.code} from {self.base_url}: {exc}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            raise OllamaUnavailableError(
                f"could not reach Ollama at {self.base_url}: {exc}"
            ) from exc

        try:
            envelope = json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise OllamaOutputError(
                f"Ollama's response body was not valid JSON: {exc}"
            ) from exc

        content = _extract_message_content(envelope)
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OllamaOutputError(
                f"Ollama's message.content was not valid JSON: {exc}"
            ) from exc
        if not isinstance(parsed, dict):
            raise OllamaOutputError(
                f"expected a JSON object from Ollama's message.content, "
                f"got {type(parsed).__name__}"
            )
        return parsed


def _extract_message_content(envelope: Any) -> str:
    if not isinstance(envelope, dict):
        raise OllamaOutputError(
            f"expected a JSON object response envelope, got {type(envelope).__name__}"
        )
    message = envelope.get("message")
    if not isinstance(message, dict):
        raise OllamaOutputError("Ollama response envelope missing 'message' object")
    content = message.get("content")
    if not isinstance(content, str):
        raise OllamaOutputError(
            "Ollama response envelope missing 'message.content' string"
        )
    return content
