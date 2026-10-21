#!/usr/bin/env python3
"""Is the Petrovich command map current with the spoken vocabulary?

The map (`docs/status/petrovich-commands.html`, published as an artifact) is a
hand-drawn view of `audio-adapter/src/vocabulary.py`. Drawing it needs
judgement -- grouping, slots, which parts are optional -- so it is regenerated
by the main loop (`/command-map`), not by a script. What a script *can* do is
say, mechanically, when it has fallen behind. That is this file.

The page carries a JSON manifest:

    <script type="application/json" id="command-map-manifest">
    {"vocabulary_sha256": "...", "cards": {"scan_ahead": 3, ...}}
    </script>

`cards` maps every token the page claims to show to the card it is on. Stale
means any of:

  1. vocabulary.py's hash differs from the stamped one (a phrase, slot word
     or token changed -- the map may or may not need a redraw, a human looks);
  2. a token in `TOKENS` is not in `cards` (a command the map does not show);
  3. a token in `cards` is no longer in `TOKENS` (the map shows a dead command).

Exit 0 current, 1 stale (reasons printed), 2 the check itself could not run.

`--stamp` rewrites the hash after a redraw -- and refuses while 2 or 3 holds,
so the stamp cannot paper over a token the redraw missed. Stamping is the
regenerator saying "I looked"; the token lists are what keep that honest.

vocabulary.py is stdlib-only, so it is loaded straight from its path and this
runs without audio-adapter's venv.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
VOCAB = REPO / "audio-adapter" / "src" / "vocabulary.py"
PAGE = REPO / "docs" / "status" / "petrovich-commands.html"
MANIFEST_RE = re.compile(
    r'(<script type="application/json" id="command-map-manifest">)(.*?)(</script>)',
    re.DOTALL,
)


def load_tokens() -> tuple[str, ...]:
    spec = importlib.util.spec_from_file_location("_vocabulary", VOCAB)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VOCAB}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.TOKENS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--stamp", action="store_true", help="record the current vocabulary hash")
    args = parser.parse_args()

    try:
        tokens = load_tokens()
        vocab_hash = hashlib.sha256(VOCAB.read_bytes()).hexdigest()
        page = PAGE.read_text(encoding="utf-8")
        match = MANIFEST_RE.search(page)
        if match is None:
            raise RuntimeError(f"no command-map-manifest block in {PAGE}")
        manifest = json.loads(match.group(2))
        cards: dict[str, int] = manifest["cards"]
    except Exception as exc:  # noqa: BLE001 -- any failure here means "could not check"
        print(f"command-map-check: could not run: {exc}", file=sys.stderr)
        return 2

    missing = [t for t in tokens if t not in cards]
    dead = sorted(set(cards) - set(tokens))
    hash_changed = manifest.get("vocabulary_sha256") != vocab_hash

    if args.stamp:
        if missing or dead:
            print("refusing to stamp: the token lists disagree -- fix the page first")
        else:
            manifest["vocabulary_sha256"] = vocab_hash
            body = "\n" + json.dumps(manifest, indent=1) + "\n"
            PAGE.write_text(
                page[: match.start(2)] + body + page[match.end(2) :], encoding="utf-8"
            )
            print(f"stamped {PAGE.relative_to(REPO)} with vocabulary {vocab_hash[:12]}")
            return 0

    if missing:
        print("not on the map:", ", ".join(missing))
    if dead:
        print("on the map but no longer in TOKENS:", ", ".join(dead))
    if hash_changed and not (missing or dead):
        print("vocabulary.py changed since the map was stamped -- check phrases and slot words")
    if missing or dead or hash_changed:
        print("command map STALE -- run /command-map")
        return 1
    print(f"command map current ({len(tokens)} tokens)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
