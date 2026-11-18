#!/usr/bin/env python3
"""Phrase-keyed recognition bench (testing aid, `[[BL-17]]` Stage 3c).

`stt_bench.py` scores clips against `vocabulary.TOKENS` directories; the
Stage 3c corpus is keyed by *phrase* (`<corpus-dir>/<phrase_slug>/*.wav`,
`record_corpus.py --phrases-file`). This scores each clip end to end the way
the adapter does -- whisper with a prompt, then `command_matcher.
match_transcript` with the real pushed rules -- against what the phrase
itself (slug, underscores to spaces) matches. Outcome per clip: `ok`,
`miss` (no token -> "say again"), `WRONG` (a different token or slots).

Prompts compared: `A_full` (today's `to_prompt` with every rule word),
`B_flight_first` (flight-category rule words first), `C_flight_only`
(out-of-state words removed). Results:
`research/2026-11-18-state-hint-bench.md`.

The rules JSON is `[[id, pattern, category], ...]` as body-layer pushes it
(`RuleSet.ids_and_patterns()`); dump it from `body-layer/`:

    PYTHONPATH=src:../world-model/src .venv/bin/python -c "import json; \
    from pathlib import Path; from belief.contacts import ContactStore; \
    from belief.crew_console import CrewConsole; \
    from rules.actions import ACTION_NAMESPACES, ActionContext; \
    from rules.engine import RuleSet; from rules.sandbox import RuleSandbox; \
    rs = RuleSet.load(Path('config/rules'), RuleSandbox(), ACTION_NAMESPACES, \
    ActionContext(console=CrewConsole(store=ContactStore()))); \
    print(json.dumps([list(t) for t in rs.ids_and_patterns()]))" > /tmp/rules.json

Then, from `audio-adapter/`:

    .venv/bin/python tools/phrase_bench.py --rules-json /tmp/rules.json \
        --corpus-dir data/corpus/bl17-stage3c \
        --whisper-model ~/whisper-models/ggml-small.en.bin --out bench.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import vocabulary
from command_matcher import match_transcript
from rule_patterns import compile_rules, rule_anchor_words, rule_words
from server import _legacy_probe
from stt_engine import WhisperCliEngine

HVRT_BARE = ["left", "right", "forward", "back", "hold", "up", "down", "move"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rules-json", required=True)
    parser.add_argument("--corpus-dir", required=True)
    parser.add_argument("--whisper-model", required=True)
    parser.add_argument("--whisper-binary", default="whisper-cli")
    parser.add_argument("--out", required=True)
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()

    with open(args.rules_json) as f:
        raw = json.load(f)
    category = {r[0]: r[2] for r in raw}
    compiled, rejected = compile_rules(
        [(r[0], r[1]) for r in raw],
        legacy_probe=_legacy_probe,
        free_speech_guard=vocabulary.FREE_SPEECH_GUARD,
    )
    if rejected:
        sys.exit(f"rules rejected: {rejected}")
    rules = tuple(compiled)
    anchors = rule_anchor_words(rules)

    all_words = [w for r in rules for w in rule_words(r)]
    flight = [w for r in rules if category[r.id] != "always" for w in rule_words(r)]
    always = [w for r in rules if category[r.id] == "always" for w in rule_words(r)]

    def fmt(words: list[str]) -> str:
        seen: set[str] = set()
        out: list[str] = []
        for w in words:
            if w not in seen:
                seen.add(w)
                out.append(vocabulary._PROMPT_DISPLAY_FORMS.get(w, w))
        return f"{vocabulary._PROMPT_FRAMING} {' '.join(out)}."

    priority = flight + HVRT_BARE + always
    prompts = {
        "A_full": vocabulary.to_prompt(all_words),
        "B_flight_first": fmt(priority + list(vocabulary.recognised_words(all_words))),
        "C_flight_only": fmt(priority),
    }

    def outcome(text: str) -> tuple[tuple[str | None, str | None], float]:
        m = match_transcript(text, rules=rules, anchor_words=anchors)
        slots = json.dumps(m.slots, sort_keys=True, default=str) if m.slots else None
        return (m.token, slots), m.match_ratio

    clips = sorted(glob.glob(os.path.join(args.corpus_dir, "*", "*.wav")))
    expected = {
        c: outcome(os.path.basename(os.path.dirname(c)).replace("_", " "))[0]
        for c in clips
    }

    def run(job: tuple[str, str]) -> dict[str, object]:
        cfg, clip = job
        engine = WhisperCliEngine(
            binary_path=args.whisper_binary,
            model_path=args.whisper_model,
            prompt=prompts[cfg],
        )
        with open(clip, "rb") as f:
            transcript = engine.transcribe(f.read())
        got, ratio = outcome(transcript.text)
        exp = expected[clip]
        kind = "ok" if got == exp else ("miss" if got[0] is None else "WRONG")
        return {
            "cfg": cfg,
            "clip": os.path.basename(clip)[:-4],
            "text": transcript.text,
            "conf": transcript.confidence,
            "exp": exp,
            "got": got,
            "ratio": ratio,
            "kind": kind,
        }

    jobs = [(cfg, c) for cfg in prompts for c in clips]
    with ThreadPoolExecutor(args.jobs) as pool:
        rows = list(pool.map(run, jobs))
    with open(args.out, "w") as f:
        json.dump({"prompts": prompts, "rows": rows}, f, indent=1, default=str)
    for cfg in prompts:
        sel = [r for r in rows if r["cfg"] == cfg]
        print(
            cfg, {k: sum(r["kind"] == k for r in sel) for k in ("ok", "miss", "WRONG")}
        )


if __name__ == "__main__":
    main()
