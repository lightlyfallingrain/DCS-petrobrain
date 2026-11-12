"""Stdlib HTTP client for Ollama's `/api/generate` and `/api/chat`
endpoints (`plans/brain-layer/plan.md` Stage 2, D6) -- the only network
calls `OllamaDecider` (and, for Stage 0's tool-call-form measurement,
`brain-layer/tools/stage0_tool_call_probe.py`) make. `urllib.request`, no
dependency, matching this subproject's own stdlib-only policy
(`brain-layer/CLAUDE.md`).

**`chat()` and `generate_with_usage()` added for `plans/brain-tool-calls/
plan.md` Stage 0**, which needs two things `generate()` alone cannot
give it: Ollama's *native* `tools` calling convention (one of the two
forms Stage 0 measures against the closed one-line grammar), and the
per-round `prompt_eval_count`/`eval_count` token usage Ollama returns
alongside the text, which `generate()` has always discarded. `generate()`
itself is unchanged -- both additions share its request/response
handling via `_post_json` rather than duplicating it.

**`chat()` reproduces `generate()`'s own unbounded `response.read()`**
(`[[BR-B3]]`, filed against this module's existing `/api/generate` call
and still open) rather than fixing it here: Stage 0 is a one-off,
user-run measurement against a local model the pilot started, not the
Stage 2 traffic BR-2's own U4 asks to fold the fix into. Flagged in the
Stage 0 implementation report rather than silently carried.

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
from typing import Any

#: Per network round trip. Deliberately shorter than `server.py`'s
#: `_DEFAULT_DECIDE_TIMEOUT_S` (12.0s) -- `OllamaDecider.decide()` makes
#: at most two sequential calls (D5's classify/discriminate split), so
#: two of these plus overhead must still fit inside that outer bound.
DEFAULT_TIMEOUT_S = 5.0


class OllamaRequestError(RuntimeError):
    """Raised on any transport failure, non-2xx response, or malformed
    JSON from Ollama's `/api/generate` or `/api/chat`. `OllamaDecider.
    decide()` treats this exactly like any other `Decider` failure --
    `server.py`'s `_run_job` already logs and drops the job for any
    exception."""


@dataclass(frozen=True, slots=True)
class OllamaUsage:
    """`prompt_eval_count`/`eval_count` from an Ollama reply -- absent or
    non-integer in the response is read as `0`, never raised: usage is a
    measurement extra a caller instruments with, not a field any decider
    logic depends on."""

    prompt_tokens: int = 0
    eval_tokens: int = 0


@dataclass(frozen=True, slots=True)
class ToolCall:
    """One entry of Ollama's native `message.tool_calls` array
    (`/api/chat` with `tools`), already unwrapped from its
    `{"function": {"name": ..., "arguments": ...}}` nesting."""

    name: str
    arguments: dict[str, object]


@dataclass(frozen=True, slots=True)
class ChatResult:
    """`/api/chat`'s reply: the assistant message's `content` (empty
    when the model instead chose to call a tool) plus any `tool_calls`,
    and this call's token usage."""

    content: str
    tool_calls: tuple[ToolCall, ...]
    usage: OllamaUsage


@dataclass(frozen=True, slots=True)
class OllamaClient:
    """Thin client for one Ollama daemon instance. `base_url` has no
    trailing slash, e.g. `"http://127.0.0.1:11434"` (Ollama's own
    default)."""

    base_url: str = "http://127.0.0.1:11434"
    timeout_s: float = DEFAULT_TIMEOUT_S

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """Shared request/response handling for every endpoint this
        client calls: `POST <path>` with a JSON body, returning the
        decoded JSON object. Raises `OllamaRequestError` on any
        transport failure or non-object/non-JSON response -- callers own
        validating the fields they each need from the result."""
        url = f"{self.base_url}{path}"
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
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
        if not isinstance(result, dict):
            raise OllamaRequestError(
                f"expected a JSON object from {url}, got {result!r}"
            )
        return result

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
        text, _usage = self.generate_with_usage(
            model=model, prompt=prompt, num_ctx=num_ctx, num_predict=num_predict
        )
        return text

    def generate_with_usage(
        self,
        model: str,
        prompt: str,
        num_ctx: int,
        num_predict: int,
    ) -> tuple[str, OllamaUsage]:
        """`generate()`'s own request, plus the token usage Ollama
        reports alongside the text -- the Stage 0 probe's per-round
        measurement needs both; nothing in `decider.py` needs the
        second, which is why `generate()` stays the thin wrapper."""
        url = "/api/generate"
        result = self._post_json(
            url,
            {
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"num_ctx": num_ctx, "num_predict": num_predict},
            },
        )
        if not isinstance(result.get("response"), str):
            raise OllamaRequestError(
                f"expected a JSON object with a string 'response' from "
                f"{self.base_url}{url}, got {result!r}"
            )
        text: str = result["response"]
        return text, _usage_from_result(result)

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        num_ctx: int,
        num_predict: int,
    ) -> ChatResult:
        """`POST /api/chat` with `stream: false` and a native `tools`
        list, for Stage 0's "native" tool-call form
        (`plans/brain-tool-calls/plan.md` Stage 0). Raises
        `OllamaRequestError` on any failure, including a malformed
        `message` or `tool_calls` shape -- a caller never has to guess
        whether a missing field means "the model chose not to call a
        tool" versus "Ollama's reply was not shaped the way this client
        expects."""
        url = "/api/chat"
        result = self._post_json(
            url,
            {
                "model": model,
                "messages": messages,
                "tools": tools,
                "stream": False,
                "options": {"num_ctx": num_ctx, "num_predict": num_predict},
            },
        )
        message = result.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise OllamaRequestError(
                f"expected a JSON object with a 'message.content' string from "
                f"{self.base_url}{url}, got {result!r}"
            )
        raw_tool_calls = message.get("tool_calls") or []
        if not isinstance(raw_tool_calls, list):
            raise OllamaRequestError(f"malformed 'message.tool_calls' in {result!r}")
        tool_calls = tuple(_parse_tool_call(entry) for entry in raw_tool_calls)
        return ChatResult(
            content=message["content"],
            tool_calls=tool_calls,
            usage=_usage_from_result(result),
        )

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


def _usage_from_result(result: dict[str, Any]) -> OllamaUsage:
    """`OllamaUsage.prompt_tokens`/`.eval_tokens` default to `0` when
    Ollama's reply omits either count (older server versions, or a
    non-2xx-but-parseable edge case) -- see `OllamaUsage`'s own
    docstring for why that is a silent default rather than a raise."""
    prompt_tokens = result.get("prompt_eval_count")
    eval_tokens = result.get("eval_count")
    return OllamaUsage(
        prompt_tokens=prompt_tokens if isinstance(prompt_tokens, int) else 0,
        eval_tokens=eval_tokens if isinstance(eval_tokens, int) else 0,
    )


def _parse_tool_call(entry: Any) -> ToolCall:
    """One `message.tool_calls[i]` entry, unwrapped. Raises
    `OllamaRequestError` -- not degraded to a sentinel -- because an
    unparseable native tool call is a transport-shape failure the Stage
    0 probe must count as `well_formed=False` at the call site, not
    something this client silently repairs."""
    function = entry.get("function") if isinstance(entry, dict) else None
    if not isinstance(function, dict):
        raise OllamaRequestError(f"malformed tool_call entry: {entry!r}")
    name = function.get("name")
    arguments = function.get("arguments")
    if not isinstance(name, str) or not isinstance(arguments, dict):
        raise OllamaRequestError(f"malformed tool_call function: {function!r}")
    return ToolCall(name=name, arguments=arguments)


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "ChatResult",
    "OllamaClient",
    "OllamaRequestError",
    "OllamaUsage",
    "ToolCall",
]
