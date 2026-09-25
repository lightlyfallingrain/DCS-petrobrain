"""Tests for `prompts.py`'s two render functions -- the base branch had
none of its own (parsing of a model's raw reply is tested against
`decider._parse_discriminate_reply`/`_parse_classify_reply` in
`test_decider.py`, since that is where parsing actually lives in this
branch's structure; this file covers only prompt construction)."""

from __future__ import annotations

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
