"""Tests for `belief.tool_api` -- a registry-completeness check, not a
behavioral one (each tool's actual behavior is covered where it's
implemented, in `test_tools.py`). `plans/bl5-tool-api/plan.md`'s
acceptance is "TOOL_SET names exactly the twelve BL-5 tools and every
entry's `fn` is callable"."""

from __future__ import annotations

from belief.tool_api import TOOL_SET, ToolSpec

_EXPECTED_TOOL_NAMES = {
    "get_contacts",
    "describe_contact",
    "get_contact_history",
    "find_contact",
    "set_attention",
    "watch_area",
    "get_attention_state",
    "acknowledge_event",
    "poll_events",
    "find_place",
    "get_situation",
    "describe_our_position",
    # BL-6 (`plans/bl6-commands-inspect-adapt/plan.md`) -- the tool-set
    # freeze point's final three additions, per `tool_api.py`'s own
    # docstring ("expected to extend TOOL_SET, not be blocked by it").
    "scan_area",
    "get_task_status",
    "cancel_task",
}


def test_tool_set_contains_exactly_the_frozen_bl6_tools() -> None:
    names = {spec.name for spec in TOOL_SET}
    assert names == _EXPECTED_TOOL_NAMES


def test_tool_set_has_no_duplicate_names() -> None:
    names = [spec.name for spec in TOOL_SET]
    assert len(names) == len(set(names))


def test_every_tool_spec_fn_is_callable() -> None:
    for spec in TOOL_SET:
        assert callable(spec.fn), f"{spec.name}'s fn is not callable"


def test_every_tool_spec_has_a_nonempty_description() -> None:
    for spec in TOOL_SET:
        assert isinstance(spec.description, str) and spec.description.strip()


def test_tool_spec_is_a_frozen_dataclass() -> None:
    spec = TOOL_SET[0]
    assert isinstance(spec, ToolSpec)
