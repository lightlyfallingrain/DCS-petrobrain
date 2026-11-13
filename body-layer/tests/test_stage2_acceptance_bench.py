"""An offline acceptance bench, per `plans/brain-tool-calls/plan.md`
Stage 2 ("The acceptance bench runs offline on the Mac"): replays
`brain-layer/tools/stage0_cases.json`'s 15 cases through the **real**
body-side pieces -- `belief.tool_api.BRAIN_TOOLS_BY_NAME` and `belief.
brain_reply.validate_turn_final` -- with **no Ollama and no brain-layer
process involved**. Each case's own `expected.final` dict (what Stage 0
measured a real model answering) is validated as if a `ToolLoopDecider`
had actually produced it, against a `belief.crew_console.BrainTurn`
seeded from that same case's own canned `observations` (every handle/
candidate the fixture says a tool call would have offered this turn).

**What this proves, and what it does not.** This confirms the acceptance
set's own expected finals are legal under Stage 2's real D3 validator --
catching, for instance, a fixture final that names a ref nothing in that
case's observations ever offered. It does **not** re-run a model (that
is the probe's own job, already done -- `brain-layer/research/
2026-11-12-tool-call-form.md`), and it does not validate the fixture's
own `args_hint` values against `BrainTool.params` (several do not match
Stage 2's real `ParamSpec`s -- see `test_stage0_fixture_discrepancies`
below, which records rather than hides that gap)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from belief.brain_reply import validate_turn_final
from belief.crew_console import BrainTurn
from belief.escalation import BrainReply
from belief.tool_api import BRAIN_TOOLS_BY_NAME
from belief.utterance import PartialParse

_CASES_PATH = (
    Path(__file__).resolve().parents[2] / "brain-layer" / "tools" / "stage0_cases.json"
)

#: **Naming discrepancy, found by this bench, not papered over.**
#: Stage 0's fixture (`brain-layer/tools/stage0_cases.json`) names this
#: tool `list_contacts`, following D5's own illustrative prose. BR-2
#: Stage 2 (this module's own implementation decision, made after
#: Stage 0 shipped) names every `BrainTool` after the `TOOL_SET` entry
#: it wraps instead ("names test-enforced to equal TOOL_SET names") --
#: `tools.get_contacts`'s own registered name, `get_contacts`, not D5's
#: label. Translated here rather than silently; `stage0_cases.json`
#: itself is not edited (it is brain-layer's Stage 0 artifact, already
#: measured against, not this plan's to rewrite).
_FIXTURE_TOOL_NAME_TO_REAL: dict[str, str] = {"list_contacts": "get_contacts"}


def _real_tool_name(fixture_name: str) -> str:
    return _FIXTURE_TOOL_NAME_TO_REAL.get(fixture_name, fixture_name)


#: Cases whose fixture-expected final is `kind == "command"` -- Stage 2
#: has no `BRAIN_COMMANDS` yet (Stage 3's job, `belief.brain_reply.
#: _validate_turn_command`'s own docstring), so every one of these
#: degrades to `unable CANNOT_ANSWER` today, not the command Stage 0
#: measured the model producing. Listed explicitly rather than inferred
#: from `expected.final.kind == "command"` at test time, so a reader
#: sees the whole list in one place.
_EXPECTED_COMMAND_DEGRADES = {
    "A1_where_one_shilka",
    "A1_where_two_shilkas_discriminated",
    "A1_where_shilka_lost_four_minutes",
    "A2_referent_where_is_it",
    "A5_keep_an_eye_on_the_tank_by_the_village",
}


def _load_cases() -> list[dict[str, Any]]:
    data = json.loads(_CASES_PATH.read_text())
    cases = data["cases"]
    assert isinstance(cases, list)
    return cases


def _empty_parse() -> PartialParse:
    return PartialParse(matched_intent=None, confidence=0.0, disposition="escalated")


def _turn_from_case(case: dict[str, Any]) -> BrainTurn:
    """Seeds a `BrainTurn`'s `offered`/`candidate_sets` from every
    handle/candidate the case's own `observations` list carries -- as if
    every one of those tool calls had already happened this turn, which
    is the state the fixture's `expected.final` was measured against."""
    turn = BrainTurn(
        started_sim=0.0, transcript=case["utterance"], parse=_empty_parse(), addressed=True
    )
    for entry in case.get("observations", []):
        observation = entry["observation"]
        handles = observation.get("handles", [])
        turn.offered.update(handles)
        candidates = observation.get("candidates") or observation.get("places") or []
        if len(candidates) >= 2:
            texts = tuple(
                (c["ref"], c.get("class") or c.get("name") or c["ref"]) for c in candidates
            )
            turn.candidate_sets.append(texts)
    return turn


def _reply_from_expected(case_id: str, final: dict[str, Any]) -> BrainReply:
    kind = final["kind"]
    if kind == "command":
        return BrainReply(
            utterance_id=case_id,
            kind="command",
            t_sim=0.0,
            token=final.get("token"),
            target=final.get("target"),
            slots={},
        )
    if kind == "answer":
        refs = tuple(final.get("refs", []))
        return BrainReply(
            utterance_id=case_id, kind="answer", t_sim=0.0, form=final.get("form"), refs=refs
        )
    if kind == "ask":
        return BrainReply(
            utterance_id=case_id, kind="ask", t_sim=0.0, refs=tuple(final.get("refs", []))
        )
    assert kind == "unable"
    return BrainReply(utterance_id=case_id, kind="unable", t_sim=0.0, reason=final.get("reason"))


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["id"])
def test_stage0_case_tool_names_are_real_brain_tools(case: dict[str, Any]) -> None:
    """Every tool name Stage 0's fixture calls is one of Stage 2's own
    seven (`belief.tool_api.BRAIN_TOOLS_BY_NAME`), after translating
    `list_contacts` -> `get_contacts` (see `_FIXTURE_TOOL_NAME_TO_REAL`'s
    own docstring for why that one name differs) -- the acceptance set's
    tool roster and the shipped roster must otherwise agree."""
    for step in case["expected"]["steps"]:
        real_name = _real_tool_name(step["tool"])
        assert real_name in BRAIN_TOOLS_BY_NAME, (
            f"{case['id']}: tool {step['tool']!r} ({real_name!r}) is not a real "
            "BRAIN_TOOLS entry"
        )


@pytest.mark.parametrize("case", _load_cases(), ids=lambda case: case["id"])
def test_stage0_expected_final_validates_or_degrades_as_documented(
    case: dict[str, Any],
) -> None:
    """The case's own `expected.final`, replayed against the real D3
    validator over a turn seeded with that case's own offered handles:
    an `answer`/`ask`/`unable` final must validate unchanged (it was
    legal then, it is legal now -- D3's rules did not move under it),
    and a `command` final must degrade to `unable CANNOT_ANSWER` (Stage
    3 is not built, `_EXPECTED_COMMAND_DEGRADES` above)."""
    final = case["expected"]["final"]
    reply = _reply_from_expected(case["id"], final)
    turn = _turn_from_case(case)
    validated = validate_turn_final(reply, turn, case["utterance"])

    if case["id"] in _EXPECTED_COMMAND_DEGRADES:
        assert final["kind"] == "command"
        assert validated.kind == "unable"
        assert validated.reason == "CANNOT_ANSWER"
        return

    assert final["kind"] != "command", (
        f"{case['id']} is not in _EXPECTED_COMMAND_DEGRADES but expects a command final"
    )
    assert validated.kind == final["kind"]
    if final["kind"] == "answer":
        assert validated.form == final.get("form")
        assert set(validated.refs or ()) == set(final.get("refs", []))
    elif final["kind"] == "unable":
        assert validated.reason == final.get("reason")


def test_stage0_fixture_discrepancies_are_recorded() -> None:
    """**Known, not hidden**: `A2_anything_near_gemerek`'s second step
    (fixture name `list_contacts`, real name `get_contacts` --
    `_FIXTURE_TOOL_NAME_TO_REAL`) is called with `{"filter": "near
    PLACE_1"}`, which does not match Stage 2's real `ParamSpec` for
    `get_contacts`'s `filter` (`enum` of `"all"`/`"visible"`/`"watched"`
    only, `belief.tool_api.BRAIN_TOOLS`) -- the Stage 0 probe measured
    the model producing a filter syntax ("near a place handle") Stage 2
    does not implement. Asserted here so the gap is a tracked fact, not
    something the bench above silently worked around by never checking
    tool-call *args* at all."""
    from belief.brain_reply import validate_tool_call

    cases = {case["id"]: case for case in _load_cases()}
    case = cases["A2_anything_near_gemerek"]
    args_hint = case["observations"][1]["args_hint"]
    assert args_hint == {"filter": "near PLACE_1"}

    turn = _turn_from_case(case)
    result = validate_tool_call("get_contacts", args_hint, turn)
    assert isinstance(result, str), (
        "expected this fixture args_hint to be rejected by the real ParamSpec -- "
        "if this now passes, Stage 2 grew a 'near <place>' filter and this test "
        "(and its docstring) are the stale half"
    )
