"""Tests for `prompts.py`'s two render functions -- the base branch had
none of its own (parsing of a model's raw reply is tested against
`decider._parse_discriminate_reply`/`_parse_classify_reply` in
`test_decider.py`, since that is where parsing actually lives in this
branch's structure; this file covers only prompt construction)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from prompts import (
    CLASSIFY_COMMAND_VOCABULARY,
    CLASSIFY_PROMPT,
    DISCRIMINATE_PROMPT,
    render_classify_prompt,
    render_discriminate_prompt,
)


def test_render_discriminate_prompt_includes_transcript_and_candidates() -> None:
    prompt = render_discriminate_prompt(
        "keep an eye on that tank",
        [
            ("CONTACT_7", "T-72, 2.1 km, near Gemerek village"),
            ("CONTACT_12", "T-72, 3.4 km, on the road"),
        ],
    )
    assert 'Pilot said: "keep an eye on that tank"' in prompt
    assert "CONTACT_7: T-72, 2.1 km, near Gemerek village" in prompt
    assert "CONTACT_12: T-72, 3.4 km, on the road" in prompt
    # D6: the formatting instruction is what keeps a small model from
    # deliberating -- must survive in the rendered prompt, not just the
    # template constant.
    assert "EXACTLY ONE line" in prompt
    assert "step by step" not in prompt.lower()


def test_render_discriminate_prompt_forbids_quoting_the_whole_sentence() -> None:
    """The second half of the quote-handling fix (`plans/brain-layer/
    review.md`'s Stage 2 required fix, `bee408b` precedent): the prompt
    itself must steer the model toward a short discriminating phrase, not
    just rely on `decider._unquote` to clean up after the fact -- an
    unquoted full-sentence echo would still fail D10's "must not be
    equally true of another candidate" check, since a whole sentence is
    never grounded in one candidate's own `why` text alone."""
    prompt = render_discriminate_prompt(
        "keep an eye on that tank", [("CONTACT_7", "x")]
    )
    assert "NEVER quote the whole sentence" in prompt


def test_render_classify_prompt_lists_vocabulary_and_transcript() -> None:
    prompt = render_classify_prompt("go take a look up north")
    assert 'Pilot said: "go take a look up north"' in prompt
    for token in CLASSIFY_COMMAND_VOCABULARY:
        assert token in prompt
    assert "EXACTLY ONE line" in prompt


def test_prompt_constants_are_str_format_templates_not_rendered_text() -> None:
    """The module docstring's own claim: both prompts are plain
    `str.format` templates, not pre-rendered -- `{transcript}` must still
    be a literal placeholder on the constants themselves."""
    assert "{transcript}" in DISCRIMINATE_PROMPT
    assert "{candidates}" in DISCRIMINATE_PROMPT
    assert "{transcript}" in CLASSIFY_PROMPT
    assert "{commands}" in CLASSIFY_PROMPT


#: body-layer's mirror of `CLASSIFY_COMMAND_VOCABULARY`, as a source path
#: rather than an import. Module independence forbids brain-layer
#: importing body-layer (root `CLAUDE.md`: HTTP/JSON is the only
#: sanctioned seam between subprojects, and the body-layer<->world-model
#: import is the sole exception) -- but *reading a sibling file as text*
#: is not an import, creates no runtime coupling, and leaves this
#: subproject standalone: when the sibling is absent, the test skips.
_BODY_LAYER_BRAIN_REPLY = (
    Path(__file__).resolve().parents[2]
    / "body-layer"
    / "src"
    / "belief"
    / "brain_reply.py"
)


def _literal_string_set(source: str, name: str) -> frozenset[str]:
    """Read one module-level assignment's literal string members without
    importing the module. `ast.literal_eval` on the assigned value keeps
    this honest: a computed or dynamic value raises rather than being
    silently skipped, which is the failure this test exists to catch."""
    tree = ast.parse(source)
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if not any(isinstance(t, ast.Name) and t.id == name for t in targets):
            continue
        value = node.value
        if value is None:
            break
        # frozenset({...}) / set(...) / tuple literal all reduce the same way.
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
            if not value.args:
                break
            value = value.args[0]
        members = ast.literal_eval(value)
        return frozenset(str(m) for m in members)
    raise AssertionError(f"no module-level literal assignment named {name!r} found")


def test_offered_confirm_vocabulary_matches_body_layers_mirror() -> None:
    """The two lists must be edited together, and nothing else enforces it.

    body-layer validates a `CONFIRM` reply against its own copy of this
    vocabulary (`belief.brain_reply.OFFERED_CONFIRM_VOCABULARY`), because
    the classify offer list is call-invariant and so is not worth
    serialising onto every escalation the way `PICK`'s genuinely
    per-escalation candidate list is. The cost of that choice is drift,
    and drift is **unsafe in one direction**: a token removed here but
    left in body's mirror stays dispatchable and so still validates,
    reopening the offered-vocabulary asymmetry the security pass closed
    (`plans/brain-layer/review.md`, review of `d51a25b`).

    A docstring reminder on each constant was the prior protection. This
    is the protection.
    """
    if not _BODY_LAYER_BRAIN_REPLY.exists():
        pytest.skip(
            "body-layer/ not checked out alongside brain-layer; "
            "the mirror cannot be compared from a standalone checkout"
        )
    mirror = _literal_string_set(
        _BODY_LAYER_BRAIN_REPLY.read_text(), "OFFERED_CONFIRM_VOCABULARY"
    )
    assert mirror == frozenset(CLASSIFY_COMMAND_VOCABULARY), (
        "brain-layer's CLASSIFY_COMMAND_VOCABULARY and body-layer's "
        "OFFERED_CONFIRM_VOCABULARY have drifted. Edit both, in the same "
        "commit: removing a token here while body still lists it lets the "
        "validator admit a token the model is no longer offered."
    )
