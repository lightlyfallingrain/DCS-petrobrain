"""Tests for `tool_loop_prompts.py`'s BR-2 Stage 3 additions -- the
command-notes block rendered from `belief.tool_api.BRAIN_COMMAND_SPECS`'s
own wire shape (`{"token", "takes_target", "meaning"}`, module
independence: this subproject never imports body-layer's `tool_api`, so
the fixtures below are hand-written to match that shape, the same
convention `test_ollama_client.py`'s fake server payloads already
follow) and the header's new `recent_contacts` rendering (D4)."""

from __future__ import annotations

from tool_loop_prompts import build_system_prompt, build_user_message

_NO_TARGET_COMMAND = {
    "token": "report_all",
    "takes_target": False,
    "meaning": "report everything",
}
_TARGET_COMMAND = {
    "token": "follow",
    "takes_target": True,
    "meaning": "watch a resolved target (binoculars up)",
}


def test_no_commands_yet_renders_the_stage2_sentence() -> None:
    """Stage 2's own no-commands sentence still renders when `commands`
    is empty -- `_command_block`'s per-roster text (`FIXED_COMMAND_ONLY`,
    a token line) stays absent; the fixed `FINAL command <token> ...`
    grammar line is unaffected either way (next test)."""
    prompt = build_system_prompt((), ())
    assert "You have no commands yet" in prompt
    assert "Commands you may issue" not in prompt
    assert "report_all" not in prompt


def test_command_block_lists_token_target_shape_and_meaning() -> None:
    prompt = build_system_prompt((), (_NO_TARGET_COMMAND, _TARGET_COMMAND))
    assert "- report_all -- report everything" in prompt
    assert '- follow {"target": <ref>} -- watch a resolved target' in prompt
    # The roster replaces the "no commands yet" sentence, not both present.
    assert "You have no commands yet" not in prompt


def test_command_block_names_fixed_command_only_for_anything_else() -> None:
    """`_command_block`'s own roster sentence (not the fixed grammar
    block's generic reason list, present either way) states the
    FIXED_COMMAND_ONLY policy once a real roster exists."""
    prompt = build_system_prompt((), (_NO_TARGET_COMMAND,))
    assert "and no others -- a request for any other action is FINAL unable " in prompt


def test_final_grammar_block_always_carries_the_command_form() -> None:
    """The `FINAL command ...` grammar line itself is part of the closed
    vocabulary regardless of whether any command happens to be offered
    this process (contrast `_command_block`'s own per-roster text)."""
    prompt = build_system_prompt((), ())
    assert "FINAL command <token> <json object>" in prompt


def test_system_prompt_is_byte_stable_for_the_same_commands() -> None:
    """R3: the system prompt depends only on `tools`/`commands`, both
    fixed for the whole process -- two calls with the same arguments
    produce byte-identical text."""
    first = build_system_prompt((), (_TARGET_COMMAND,))
    second = build_system_prompt((), (_TARGET_COMMAND,))
    assert first == second


def test_user_message_renders_recent_contacts_as_offered_refs() -> None:
    """D4's header refs: a `recent_contacts` entry is rendered by its own
    handle, under a line that says it is already offered -- this is what
    lets the model name it in a final with no tool call first."""
    header = {
        "contact_counts": 1,
        "estimated_units": 1,
        "recent_contacts": [{"id": "CONTACT_5", "summary": "BMP, observed."}],
    }
    message = build_user_message("Petrovich, where is it?", header, ())
    assert "CONTACT_5: BMP, observed." in message
    assert "already offered" in message


def test_user_message_without_recent_contacts_omits_the_section() -> None:
    header = {"contact_counts": 0, "estimated_units": 0}
    message = build_user_message("Petrovich, where are we?", header, ())
    assert "Recently mentioned" not in message
    assert "CONTACT_" not in message
