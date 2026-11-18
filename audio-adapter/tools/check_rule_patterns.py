"""Offline half of the rule checker (`[[BL-17]]`, "Rule checker, without
flying"): reads the rules body-layer loaded -- a JSON list of
`{"id", "pattern", "category"}` on stdin -- and runs the same
`compile_rules` collision check `PUT /rules` runs, with no server and no
whisper. Also expands every accepted rule's pattern into concrete sample
utterances (each word-set alternative, optional groups in and out) and
matches them back through the real grammar, so body-layer can dry-run each
handler with real slot values.

Writes one JSON object to stdout:

    {"rejected": [{"id": ..., "reason": ...}],
     "samples": {rule_id: [{"utterance": ..., "slots": {...}}, ...]}}

Run (body-layer's `tools/check_rules.py` does this for you):

    PYTHONPATH=src .venv/bin/python tools/check_rule_patterns.py < rules.json
"""

from __future__ import annotations

import itertools
import json
import sys
from typing import Any

import vocabulary
from command_matcher import match_transcript
from rule_patterns import (
    SLOT_TYPES,
    CompiledRule,
    Element,
    LegacyProbeResult,
    LiteralElement,
    OptionalElement,
    SlotElement,
    WordSetElement,
    compile_rules,
    match_pattern,
)

#: Extra spoken forms per slot type, beyond `SlotType.sample()`, so a
#: handler's other branches get exercised too (`speed_target`'s "max").
_EXTRA_SLOT_SAMPLES: dict[str, tuple[str, ...]] = {
    "speed_target": ("max",),
}

#: Bound on samples per rule -- a pattern with several word-sets and
#: optionals multiplies quickly, and a few dozen cover every branch a
#: shipped rule has.
_MAX_SAMPLES_PER_RULE = 32


def _legacy_probe(text: str) -> LegacyProbeResult:
    # Same as `server._legacy_probe`, without importing the server.
    result = match_transcript(text)
    return LegacyProbeResult(
        token=result.token,
        verb_anchored=result.verb_anchored,
        match_ratio=result.match_ratio,
    )


def _expand(elements: tuple[Element, ...]) -> list[list[str]]:
    """Every word sequence the elements can produce, one alternative per
    word-set position and slot sample, optional groups both in and out."""
    choices: list[list[list[str]]] = []
    for element in elements:
        if isinstance(element, LiteralElement):
            choices.append([[element.word]])
        elif isinstance(element, WordSetElement):
            choices.append([[word] for word in element.words])
        elif isinstance(element, SlotElement):
            slot_type = SLOT_TYPES[element.type_name]
            forms = (
                slot_type.sample(),
                *_EXTRA_SLOT_SAMPLES.get(element.type_name, ()),
            )
            choices.append([form.split() for form in forms])
        elif isinstance(element, OptionalElement):
            choices.append([[], *_expand(element.elements)])
    return [
        [word for part in combo for word in part]
        for combo in itertools.product(*choices)
    ]


def _samples(rule: CompiledRule) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for words in _expand(rule.elements):
        utterance = " ".join(words)
        if not utterance or utterance in seen:
            continue
        seen.add(utterance)
        slots = match_pattern(rule.elements, words)
        if slots is None:
            continue
        out.append({"utterance": utterance, "slots": slots})
        if len(out) >= _MAX_SAMPLES_PER_RULE:
            break
    return out


def main() -> int:
    raw = json.load(sys.stdin)
    pairs = [(str(item["id"]), str(item["pattern"])) for item in raw]
    accepted, rejected = compile_rules(
        pairs,
        legacy_probe=_legacy_probe,
        free_speech_guard=vocabulary.FREE_SPEECH_GUARD,
    )
    result = {
        "rejected": [{"id": r.id, "reason": r.reason} for r in rejected],
        "samples": {rule.id: _samples(rule) for rule in accepted},
    }
    json.dump(result, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
