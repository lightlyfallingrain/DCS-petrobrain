"""Tests for `decider.ToolLoopDecider` -- `plans/brain-tool-calls/plan.md`
BR-2 Stage 2's `Decider` for `mode == "addressed"`. Reuses `test_ollama_
client.py`'s own fake Ollama HTTP server (`_FakeOllamaServer`) rather
than a live Ollama daemon -- same "a small fake HTTP server standing in
for Ollama" posture that module's docstring states, applied here to the
decider sitting one layer above `OllamaClient` instead of to the client
itself. One round in, one round out -- continuation round handling
(round 2+ carrying `steps`) is exercised the same way the real
`belief.crew_console` would drive it: by calling `decide()` again with a
payload whose `steps`/`round` have grown."""

from __future__ import annotations

from typing import Any

from test_ollama_client import _FakeOllamaServer, fake_ollama  # noqa: F401 -- fixture

from decider import ToolLoopDecider
from ollama_client import OllamaClient

_TOOLS: tuple[dict[str, Any], ...] = (
    {
        "name": "find_contact",
        "params": [{"name": "text", "kind": "str", "required": True, "max_len": 40}],
    },
)


def _payload(
    *,
    transcript: str = "Petrovich, where's the Shilka?",
    steps: tuple[dict[str, Any], ...] = (),
    round_: int = 0,
) -> dict[str, Any]:
    return {
        "utterance_id": "U1",
        "transcript": transcript,
        "t_sim": 0.0,
        "mode": "addressed",
        "round": round_,
        "steps": list(steps),
        "tools": list(_TOOLS),
        "commands": [],
        "situational_header": {"contact_counts": 0, "estimated_units": 0},
    }


def test_native_tool_call_reply_becomes_tool_call_dict(
    fake_ollama: _FakeOllamaServer,  # noqa: F811
) -> None:
    """Ollama's native `tool_calls` field -> `{"kind": "tool_call", ...}`
    -- D1's measured form (Stage 0 conclusion 1)."""
    fake_ollama.chat_message = {
        "content": "",
        "tool_calls": [
            {"function": {"name": "find_contact", "arguments": {"text": "shilka"}}}
        ],
    }
    decider = ToolLoopDecider(
        model="qwen3:4b-instruct-2507-q4_K_M",
        ollama_client=OllamaClient(base_url=fake_ollama.base_url),
    )
    result = decider.decide(_payload())
    assert result == {
        "kind": "tool_call",
        "tool": "find_contact",
        "args": {"text": "shilka"},
    }


def test_multiple_native_tool_calls_degrades_to_ask(
    fake_ollama: _FakeOllamaServer,  # noqa: F811
) -> None:
    """D3's "one round, one tool" has no native-API equivalent -- more
    than one `tool_calls` entry in a single reply is not well-formed and
    degrades to a bare `ask`, never acted on as if the first one were
    the only one."""
    fake_ollama.chat_message = {
        "content": "",
        "tool_calls": [
            {"function": {"name": "find_contact", "arguments": {"text": "shilka"}}},
            {"function": {"name": "find_contact", "arguments": {"text": "bmp"}}},
        ],
    }
    decider = ToolLoopDecider(
        model="m", ollama_client=OllamaClient(base_url=fake_ollama.base_url)
    )
    assert decider.decide(_payload()) == {"kind": "ask"}


def test_final_answer_line_becomes_answer_dict(
    fake_ollama: _FakeOllamaServer,  # noqa: F811
) -> None:
    fake_ollama.chat_message = {
        "content": 'FINAL answer contacts ["CONTACT_1"]',
        "tool_calls": [],
    }
    decider = ToolLoopDecider(
        model="m", ollama_client=OllamaClient(base_url=fake_ollama.base_url)
    )
    result = decider.decide(_payload(round_=1))
    assert result == {"kind": "answer", "form": "contacts", "refs": ["CONTACT_1"]}


def test_final_unable_line_becomes_unable_dict(
    fake_ollama: _FakeOllamaServer,  # noqa: F811
) -> None:
    fake_ollama.chat_message = {
        "content": "FINAL unable CANNOT_ANSWER",
        "tool_calls": [],
    }
    decider = ToolLoopDecider(
        model="m", ollama_client=OllamaClient(base_url=fake_ollama.base_url)
    )
    assert decider.decide(_payload()) == {"kind": "unable", "reason": "CANNOT_ANSWER"}


def test_malformed_content_degrades_to_ask(
    fake_ollama: _FakeOllamaServer,  # noqa: F811
) -> None:
    """Free text that is neither a tool call nor a `FINAL ...` line --
    unparseable degrades to `ask`, never invents a reply (`final_reply.
    parse_final_text`'s own posture)."""
    fake_ollama.chat_message = {
        "content": "I think it's near the village",
        "tool_calls": [],
    }
    decider = ToolLoopDecider(
        model="m", ollama_client=OllamaClient(base_url=fake_ollama.base_url)
    )
    assert decider.decide(_payload()) == {"kind": "ask"}


def test_transport_failure_degrades_to_unable_no_brain() -> None:
    """D4's own wording for this exact case: "If brain-layer is up but
    Ollama is not, brain-layer replies `unable NO_BRAIN`." An
    unreachable Ollama (no server listening at all) is the simplest way
    to force `OllamaRequestError` without a live daemon."""
    decider = ToolLoopDecider(
        model="m", ollama_client=OllamaClient(base_url="http://127.0.0.1:1")
    )
    assert decider.decide(_payload()) == {"kind": "unable", "reason": "NO_BRAIN"}


def test_continuation_round_sends_the_grown_steps_block(
    fake_ollama: _FakeOllamaServer,  # noqa: F811
) -> None:
    """Round 2's own user message carries round 1's `(tool, args,
    observation)` step -- the whole point of `tool_loop_prompts.
    build_user_message`'s "So far this turn" block, and of D1's
    "brain-layer is stateless across rounds, body resends the full
    record every POST." Checked by reading the actual request body the
    fake server received, not by trusting the decider's return value."""
    fake_ollama.chat_message = {
        "content": "FINAL unable CANNOT_ANSWER",
        "tool_calls": [],
    }
    decider = ToolLoopDecider(
        model="m", ollama_client=OllamaClient(base_url=fake_ollama.base_url)
    )
    steps = (
        {
            "tool": "find_contact",
            "args": {"text": "shilka"},
            "observation": "no matching contacts",
        },
    )
    decider.decide(_payload(steps=steps, round_=1))

    assert len(fake_ollama.received) == 1
    messages = fake_ollama.received[0]["messages"]
    assert isinstance(messages, list)
    user_message = messages[-1]["content"]
    assert "So far this turn" in user_message
    assert "find_contact" in user_message
    assert "no matching contacts" in user_message


def test_system_prompt_is_identical_across_rounds(
    fake_ollama: _FakeOllamaServer,  # noqa: F811
) -> None:
    """R3: the system prompt (tools/commands block) must be byte-stable
    across a turn's rounds, so Ollama's own KV cache can be reused --
    only the user message's steps block should differ."""
    fake_ollama.chat_message = {
        "content": "FINAL unable CANNOT_ANSWER",
        "tool_calls": [],
    }
    decider = ToolLoopDecider(
        model="m", ollama_client=OllamaClient(base_url=fake_ollama.base_url)
    )
    decider.decide(_payload(round_=0))
    decider.decide(
        _payload(
            round_=1,
            steps=(
                {"tool": "find_contact", "args": {"text": "x"}, "observation": "ok"},
            ),
        )
    )
    system_prompts = [
        next(m["content"] for m in req["messages"] if m["role"] == "system")
        for req in fake_ollama.received
    ]
    assert system_prompts[0] == system_prompts[1]
