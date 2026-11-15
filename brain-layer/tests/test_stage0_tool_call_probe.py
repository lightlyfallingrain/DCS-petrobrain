"""Tests for `tools/stage0_tool_call_probe.py` -- `plans/brain-tool-calls/
plan.md` Stage 0. Loaded dynamically via `importlib` (mirroring `body-
layer/tests/test_generate_effector_registry.py`'s own pattern for a
`tools/` script) since `tools/` is not on this subproject's `pythonpath`
(`pyproject.toml`'s `[tool.pytest.ini_options]` only lists `src`).

No live Ollama daemon anywhere here (per `brain-layer/CLAUDE.md`'s
"Testing" section and the module's own posture) -- the round loop is
driven by `_FakeGrammarClient`/`_FakeNativeClient`, scripted dataclasses
standing in for `ollama_client.OllamaClient`, mirroring `test_decider.
py`'s own `_FakeOllamaClient` shape."""

from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from ollama_client import ChatResult, OllamaUsage, ToolCall

_BRAIN_LAYER_ROOT = Path(__file__).resolve().parent.parent


def _load_probe() -> ModuleType:
    path = _BRAIN_LAYER_ROOT / "tools" / "stage0_tool_call_probe.py"
    spec = importlib.util.spec_from_file_location("stage0_tool_call_probe", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["stage0_tool_call_probe"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def probe() -> ModuleType:
    return _load_probe()


# --- grammar parsing -------------------------------------------------------


def test_parse_grammar_line_call(probe: ModuleType) -> None:
    parsed = probe.parse_grammar_line('CALL find_contact {"text": "shilka"}')
    assert parsed.kind == "call"
    assert parsed.tool == "find_contact"
    assert parsed.args == {"text": "shilka"}


def test_parse_grammar_line_call_is_case_insensitive_on_keyword(
    probe: ModuleType,
) -> None:
    parsed = probe.parse_grammar_line('call find_contact {"text": "shilka"}')
    assert parsed.kind == "call"


def test_parse_grammar_line_call_malformed_json_degrades(probe: ModuleType) -> None:
    parsed = probe.parse_grammar_line("CALL find_contact {not json}")
    assert parsed.kind == "malformed"


def test_parse_grammar_line_final_command(probe: ModuleType) -> None:
    parsed = probe.parse_grammar_line(
        'FINAL command where_is_it {"target": "CONTACT_1"}'
    )
    assert parsed.kind == "final_command"
    assert parsed.token == "where_is_it"
    assert parsed.slots == {"target": "CONTACT_1"}


def test_parse_grammar_line_final_answer(probe: ModuleType) -> None:
    parsed = probe.parse_grammar_line(
        'FINAL answer contacts ["CONTACT_1", "CONTACT_2"]'
    )
    assert parsed.kind == "final_answer"
    assert parsed.form == "contacts"
    assert parsed.refs == ["CONTACT_1", "CONTACT_2"]


def test_parse_grammar_line_final_ask(probe: ModuleType) -> None:
    parsed = probe.parse_grammar_line('FINAL ask ["CONTACT_1", "CONTACT_2"]')
    assert parsed.kind == "final_ask"
    assert parsed.refs == ["CONTACT_1", "CONTACT_2"]


def test_parse_grammar_line_final_unable(probe: ModuleType) -> None:
    parsed = probe.parse_grammar_line("FINAL unable NO_PLACE")
    assert parsed.kind == "final_unable"
    assert parsed.reason == "NO_PLACE"


def test_parse_grammar_line_malformed_free_text(probe: ModuleType) -> None:
    assert probe.parse_grammar_line("I think it's near the village").kind == "malformed"
    assert probe.parse_grammar_line("").kind == "malformed"


# --- native tool_call extraction -------------------------------------------


def test_interpret_native_result_single_tool_call_is_well_formed(
    probe: ModuleType,
) -> None:
    result = ChatResult(
        content="",
        tool_calls=(ToolCall(name="find_contact", arguments={"text": "shilka"}),),
        usage=OllamaUsage(prompt_tokens=100, eval_tokens=10),
    )
    parsed, well_formed, raw = probe._interpret_native_result(result)
    assert parsed.kind == "call"
    assert parsed.tool == "find_contact"
    assert parsed.args == {"text": "shilka"}
    assert well_formed is True
    assert "find_contact" in raw


def test_interpret_native_result_multiple_tool_calls_is_not_well_formed(
    probe: ModuleType,
) -> None:
    result = ChatResult(
        content="",
        tool_calls=(
            ToolCall(name="find_contact", arguments={"text": "shilka"}),
            ToolCall(name="find_place", arguments={"text": "gemerek"}),
        ),
        usage=OllamaUsage(),
    )
    parsed, well_formed, _raw = probe._interpret_native_result(result)
    assert parsed.kind == "call"
    assert well_formed is False


def test_interpret_native_result_final_content_line(probe: ModuleType) -> None:
    result = ChatResult(
        content="FINAL unable CANNOT_ANSWER",
        tool_calls=(),
        usage=OllamaUsage(),
    )
    parsed, well_formed, raw = probe._interpret_native_result(result)
    assert parsed.kind == "final_unable"
    assert parsed.reason == "CANNOT_ANSWER"
    assert well_formed is True
    assert raw == "FINAL unable CANNOT_ANSWER"


def test_interpret_native_result_malformed_content_is_not_well_formed(
    probe: ModuleType,
) -> None:
    result = ChatResult(content="I'm not sure", tool_calls=(), usage=OllamaUsage())
    parsed, well_formed, _raw = probe._interpret_native_result(result)
    assert parsed.kind == "malformed"
    assert well_formed is False


# --- case loader ------------------------------------------------------------


_FIXTURE_JSON: dict[str, Any] = {
    "tools": [
        {
            "name": "find_contact",
            "description": "find a contact",
            "params": [
                {"name": "text", "kind": "str", "required": True, "max_len": 40}
            ],
        },
        {"name": "describe_our_position", "description": "where we are", "params": []},
    ],
    "commands": ["where_is_it", "report_all"],
    "cases": [
        {
            "id": "T1",
            "category": "test",
            "utterance": "Petrovich, where's the Shilka?",
            "header": {"contacts": [], "places": [], "marks": []},
            "observations": [
                {
                    "tool": "find_contact",
                    "args_hint": {"text": "shilka"},
                    "observation": {"summary": "one match", "handles": ["CONTACT_1"]},
                }
            ],
            "expected": {
                "steps": [{"tool": "find_contact"}],
                "final": {
                    "kind": "command",
                    "token": "where_is_it",
                    "target": "CONTACT_1",
                },
            },
        }
    ],
}


def test_load_case_file_parses_tools_commands_and_cases(
    probe: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(_FIXTURE_JSON))

    case_file = probe.load_case_file(path)

    assert [t.name for t in case_file.tools] == [
        "find_contact",
        "describe_our_position",
    ]
    assert case_file.tools[0].params[0].name == "text"
    assert case_file.tools[0].params[0].required is True
    assert case_file.commands == ("where_is_it", "report_all")
    assert len(case_file.cases) == 1
    case = case_file.cases[0]
    assert case.id == "T1"
    assert case.utterance == "Petrovich, where's the Shilka?"
    assert len(case.observations) == 1
    assert case.observations[0].tool == "find_contact"
    assert case.expected["final"]["token"] == "where_is_it"


def test_shipped_stage0_cases_file_loads(probe: ModuleType) -> None:
    """The actual fixture this stage ships, not a copy -- a parse failure
    here means the shipped file and the loader have drifted apart."""
    case_file = probe.load_case_file(_BRAIN_LAYER_ROOT / "tools" / "stage0_cases.json")
    assert len(case_file.tools) == 7
    # 15: every bullet of the plan's acceptance-set section, counting "anything
    # near Gemerek" / "...report south of Gemerek" and "arm the weapons" /
    # "turn left" as the two separate utterances each pair's bullet lists.
    assert len(case_file.cases) == 15
    fixed_command_only = [
        c
        for c in case_file.cases
        if c.expected.get("final", {}).get("reason") == "FIXED_COMMAND_ONLY"
    ]
    cannot_answer = [
        c
        for c in case_file.cases
        if c.expected.get("final", {}).get("reason") == "CANNOT_ANSWER"
    ]
    assert len(fixed_command_only) == 2
    assert len(cannot_answer) == 1


# --- find_observation --------------------------------------------------


def test_find_observation_matches_by_tool_name(
    probe: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(_FIXTURE_JSON))
    case = probe.load_case_file(path).cases[0]

    observation, matched = probe.find_observation(
        case, "find_contact", {"text": "the shilka"}
    )
    assert matched is True
    assert observation["summary"] == "one match"


def test_find_observation_no_canned_entry_for_tool(
    probe: ModuleType, tmp_path: Path
) -> None:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(_FIXTURE_JSON))
    case = probe.load_case_file(path).cases[0]

    observation, matched = probe.find_observation(case, "describe_our_position", {})
    assert matched is False
    assert "error" in observation


# --- round loop, driven by a fake client -----------------------------------


@dataclass
class _FakeGrammarClient:
    """Stands in for `ollama_client.OllamaClient` for the grammar form --
    `generate_with_usage` scripted to return one reply per call, in
    order."""

    scripted: list[str]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def generate_with_usage(
        self, model: str, prompt: str, num_ctx: int, num_predict: int
    ) -> tuple[str, OllamaUsage]:
        self.calls.append(
            {
                "model": model,
                "prompt": prompt,
                "num_ctx": num_ctx,
                "num_predict": num_predict,
            }
        )
        text = self.scripted[len(self.calls) - 1]
        return text, OllamaUsage(prompt_tokens=50 * len(self.calls), eval_tokens=5)


@dataclass
class _FakeNativeClient:
    """Stands in for `ollama_client.OllamaClient` for the native form --
    `chat` scripted to return one `ChatResult` per call, in order."""

    scripted: list[ChatResult]
    calls: list[dict[str, Any]] = field(default_factory=list)

    def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        num_ctx: int,
        num_predict: int,
    ) -> ChatResult:
        self.calls.append({"model": model, "messages": messages, "tools": tools})
        return self.scripted[len(self.calls) - 1]


def _one_shilka_case(probe: ModuleType, tmp_path: Path) -> Any:
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(_FIXTURE_JSON))
    return probe.load_case_file(path)


def test_run_case_once_grammar_form_call_then_final(
    probe: ModuleType, tmp_path: Path
) -> None:
    case_file = _one_shilka_case(probe, tmp_path)
    case = case_file.cases[0]
    fake = _FakeGrammarClient(
        scripted=[
            'CALL find_contact {"text": "shilka"}',
            'FINAL command where_is_it {"target": "CONTACT_1"}',
        ]
    )
    system_prompt = probe.build_system_prompt(
        case_file.tools, case_file.commands, "grammar"
    )

    result = probe.run_case_once(
        client=fake,  # type: ignore[arg-type]
        model="test-model",
        num_ctx=2048,
        num_predict=200,
        max_rounds=4,
        form="grammar",
        system_prompt=system_prompt,
        native_tool_schemas=[],
        case=case,
    )

    assert len(result.rounds) == 2
    assert result.rounds[0].kind == "tool_call"
    assert result.rounds[0].step_matched_expected is True
    assert result.rounds[1].kind == "final"
    # BR-2 Stage 3 (`final_reply.final_to_dict`): `target`/`because` are
    # popped out of the raw JSON object into their own dedicated fields
    # rather than left duplicated inside `slots` -- `slots` holds only
    # whatever else the model tried to fill (nothing, here).
    assert result.final == {
        "kind": "command",
        "token": "where_is_it",
        "slots": {},
        "target": "CONTACT_1",
        "because": None,
    }
    assert result.final_correct is True
    assert result.exceeded_rounds is False
    # The first round's prompt must carry the system prompt as a true
    # prefix (R3: KV-cache reuse depends on byte-stable prefixes).
    assert fake.calls[0]["prompt"].startswith(system_prompt)
    # The second round's prompt must carry the first round's own
    # observation back to the model.
    assert "CONTACT_1" in fake.calls[1]["prompt"]


def test_run_case_once_grammar_form_malformed_reply_ends_turn(
    probe: ModuleType, tmp_path: Path
) -> None:
    case_file = _one_shilka_case(probe, tmp_path)
    case = case_file.cases[0]
    fake = _FakeGrammarClient(scripted=["I'm not sure what you mean"])
    system_prompt = probe.build_system_prompt(
        case_file.tools, case_file.commands, "grammar"
    )

    result = probe.run_case_once(
        client=fake,  # type: ignore[arg-type]
        model="test-model",
        num_ctx=2048,
        num_predict=200,
        max_rounds=4,
        form="grammar",
        system_prompt=system_prompt,
        native_tool_schemas=[],
        case=case,
    )

    assert len(result.rounds) == 1
    assert result.rounds[0].kind == "malformed"
    assert result.final is None
    assert result.final_correct is False


def test_run_case_once_grammar_form_exceeds_round_cap(
    probe: ModuleType, tmp_path: Path
) -> None:
    case_file = _one_shilka_case(probe, tmp_path)
    case = case_file.cases[0]
    # Keeps calling the same tool forever -- never reaches a FINAL line.
    fake = _FakeGrammarClient(
        scripted=['CALL find_contact {"text": "shilka"}'] * 3,
    )

    result = probe.run_case_once(
        client=fake,  # type: ignore[arg-type]
        model="test-model",
        num_ctx=2048,
        num_predict=200,
        max_rounds=2,
        form="grammar",
        system_prompt=probe.build_system_prompt(
            case_file.tools, case_file.commands, "grammar"
        ),
        native_tool_schemas=[],
        case=case,
    )

    assert result.exceeded_rounds is True
    assert result.final is None
    assert result.rounds[-1].kind == "round_cap_exceeded"
    # Two tool-call rounds executed (indices 0 and 1), the third call at
    # index == max_rounds is the one that gets rejected rather than run.
    assert len([r for r in result.rounds if r.kind == "tool_call"]) == 2


def test_run_case_once_native_form_call_then_final(
    probe: ModuleType, tmp_path: Path
) -> None:
    case_file = _one_shilka_case(probe, tmp_path)
    case = case_file.cases[0]
    fake = _FakeNativeClient(
        scripted=[
            ChatResult(
                content="",
                tool_calls=(
                    ToolCall(name="find_contact", arguments={"text": "shilka"}),
                ),
                usage=OllamaUsage(prompt_tokens=80, eval_tokens=8),
            ),
            ChatResult(
                content='FINAL command where_is_it {"target": "CONTACT_1"}',
                tool_calls=(),
                usage=OllamaUsage(prompt_tokens=120, eval_tokens=12),
            ),
        ]
    )
    native_schemas = [probe.tool_to_json_schema(tool) for tool in case_file.tools]
    system_prompt = probe.build_system_prompt(
        case_file.tools, case_file.commands, "native"
    )

    result = probe.run_case_once(
        client=fake,  # type: ignore[arg-type]
        model="test-model",
        num_ctx=2048,
        num_predict=200,
        max_rounds=4,
        form="native",
        system_prompt=system_prompt,
        native_tool_schemas=native_schemas,
        case=case,
    )

    assert len(result.rounds) == 2
    assert result.rounds[0].kind == "tool_call"
    assert result.rounds[0].prompt_tokens == 80
    assert result.final_correct is True
    # The system message must be byte-identical across rounds.
    assert fake.calls[0]["messages"][0]["content"] == system_prompt
    assert fake.calls[1]["messages"][0]["content"] == system_prompt
    assert fake.calls[0]["tools"] == native_schemas


def test_run_case_once_native_form_transport_error_is_recorded(
    probe: ModuleType, tmp_path: Path
) -> None:
    from ollama_client import OllamaRequestError

    @dataclass
    class _RaisingClient:
        def chat(
            self,
            model: str,
            messages: list[dict[str, Any]],
            tools: list[dict[str, Any]],
            num_ctx: int,
            num_predict: int,
        ) -> ChatResult:
            raise OllamaRequestError("boom")

    case_file = _one_shilka_case(probe, tmp_path)
    case = case_file.cases[0]
    result = probe.run_case_once(
        client=_RaisingClient(),  # type: ignore[arg-type]
        model="test-model",
        num_ctx=2048,
        num_predict=200,
        max_rounds=4,
        form="native",
        system_prompt="system",
        native_tool_schemas=[],
        case=case,
    )

    assert result.error == "boom"
    assert result.rounds[0].kind == "transport_error"
    assert result.final is None
    assert result.final_correct is False
