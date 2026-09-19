"""Render sample crew callouts and, optionally, speak them aloud.

Acceptance aid for anything that changes `belief/speech.py`. It exists because
the obvious way to accept a speech change -- run the real `logger --crew-text`
pipeline and listen -- needs a live aircraft layer, and therefore DCS and the
Windows box. That gates a phrasing judgement on hardware access, which is the
wrong dependency: the thing being judged is how a sentence sounds, and the
sentence can be produced without a simulator.

So this drives `speech.py`'s real rendering functions over hand-built `facts`
dicts, prints the exact text, and can POST each line to a running
`srs-adapter --target local` so it is heard rather than read.

Deliberately not a test. It asserts nothing -- it exists so a human can judge
phrasing, which is the one thing the test suite structurally cannot do.

Run from `body-layer/`. Both paths on `PYTHONPATH` and this subproject's own
interpreter are required, not optional: `perception.geometry` imports the
world-model seam, and that pulls in `pyproj`, which only exists in
`body-layer/.venv` (see `body-layer/CLAUDE.md`, "Running the live logger").

    # print the table
    PYTHONPATH=src:../world-model/src .venv/bin/python tools/speak_samples.py

    # print and speak (srs-adapter must be running on --target local)
    PYTHONPATH=src:../world-model/src .venv/bin/python tools/speak_samples.py --speak

Stdlib only, like the rest of this subproject.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request

from belief.speech import _contact_report_text

DEFAULT_ADAPTER_URL = "http://127.0.0.1:7795"

#: (label, classification value, level, cardinality or None). `None`
#: cardinality is the lattice root -- the absent-fact route through the
#: regression guard, which must render identically to an explicit (1, 1).
SAMPLES: tuple[tuple[str, str, str, tuple[int, float] | None], ...] = (
    ("singular, type (REGRESSION GUARD)", "T-72", "type", (1, 1)),
    ("singular, no cardinality fact", "T-72", "type", None),
    ("singular, class", "OP_ARMORED", "class", (1, 1)),
    ("singular, presence", "OP_GROUPSOMETHING", "presence", (1, 1)),
    ("two", "OP_ARMORED", "class", (2, 2)),
    ("three", "OP_ARMORED", "class", (3, 3)),
    ("four to five", "OP_TRUCK", "class", (4, 5)),
    ("fold-derived 4-7 (no named bucket)", "OP_TRUCK", "class", (4, 7)),
    ("eight to ten", "OP_ARMORED", "class", (8, 10)),
    ("sixteen or more", "OP_GROUPSOMETHING", "presence", (16, math.inf)),
    ("plural at type level", "T-72", "type", (3, 3)),
)

#: Attention earns precision: the same contacts, marked `watch`. An exact
#: interval speaks its number; an inexact one keeps the hedge, because
#: attention buys disclosure of precision already held, never manufactured
#: precision.
WATCHED_SAMPLES: tuple[tuple[str, str, str, tuple[int, float] | None], ...] = (
    ("WATCHED two", "OP_ARMORED", "class", (2, 2)),
    ("WATCHED three, type level", "T-72", "type", (3, 3)),
    ("WATCHED four to five (inexact)", "OP_TRUCK", "class", (4, 5)),
    ("WATCHED eight", "OP_ARMORED", "class", (8, 8)),
    ("WATCHED sixteen (beyond spoken range)", "OP_ARMORED", "class", (16, 16)),
    ("WATCHED singular", "T-72", "type", (1, 1)),
)

#: (label, facts) -- the 2026-09-19 "Contact report fine tuning" roadmap
#: item's cheap wording changes: spelled-out units, "very close" under
#: half a kilometre, per-token TTS respelling (a known designation, and the
#: "SAM" exception), and `enrichment.py`'s new "on"/"next to" short-range
#: feature wording (both bare, from a raw `SemanticFact.text`, and rounded
#: for the pre-existing "near X (Nm)" shape once past those two bands).
#: `build_facts` can't express clock/range/semantic fragments (its tuple
#: shape is cardinality-only), so these are hand-built `facts` dicts
#: instead, exercised through the same `_contact_report_text` every other
#: row here goes through.
WORDING_SAMPLES: tuple[tuple[str, dict[str, object]], ...] = (
    (
        "range spelled out",
        {
            "classification": {"value": "OP_ARMORED", "level": "class"},
            "relative_now": {"clock_position": 3, "range_m": 3000.0},
        },
    ),
    (
        "very close (under 0.5 km)",
        {
            "classification": {"value": "OP_TRUCK", "level": "class"},
            "relative_now": {"clock_position": 12, "range_m": 200.0},
        },
    ),
    (
        "known designation respelled (Mi-8)",
        {"classification": {"value": "Mi-8", "level": "type"}},
    ),
    (
        "SAM is NOT respelled (the roadmap's named exception)",
        {"classification": {"value": "OP_SRSAM", "level": "class"}},
    ),
    (
        "semantic fragment distance rounded and spelled",
        {
            "classification": {"value": "OP_ARMORED", "level": "class"},
            "semantic": [
                {
                    "text": "near a road (439m)",
                    "confidence": 1.0,
                    "provenance": "osm",
                    "feature_id": "road:sample",
                }
            ],
        },
    ),
    (
        "on the road (zero distance)",
        {
            "classification": {"value": "OP_ARMORED", "level": "class"},
            "semantic": [
                {
                    "text": "on a road",
                    "confidence": 1.0,
                    "provenance": "osm",
                    "feature_id": "road:sample",
                }
            ],
        },
    ),
    (
        "next to the road (~10-100 m)",
        {
            "classification": {"value": "OP_ARMORED", "level": "class"},
            "semantic": [
                {
                    "text": "next to a road",
                    "confidence": 1.0,
                    "provenance": "osm",
                    "feature_id": "road:sample",
                }
            ],
        },
    ),
)


def build_facts(
    value: str, level: str, card: tuple[int, float] | None, attention: str = "normal"
) -> dict[str, object]:
    facts: dict[str, object] = {
        "classification": {"value": value, "level": level},
        "attention": attention,
    }
    if card is not None:
        facts["cardinality"] = {"lo": card[0], "hi": card[1], "confidence": 1.0}
    return facts


def speak(url: str, text: str) -> str:
    body = json.dumps({"text": text, "urgent": False}).encode()
    req = urllib.request.Request(
        url.rstrip("/") + "/speak",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return f"spoken ({resp.status})"
    except urllib.error.URLError as exc:
        return f"NOT SPOKEN: {exc}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--speak", action="store_true", help="POST each line to a running srs-adapter"
    )
    parser.add_argument("--adapter-url", default=DEFAULT_ADAPTER_URL)
    parser.add_argument(
        "--pause",
        type=float,
        default=1.5,
        help="seconds between spoken lines, so they do not queue into one blur",
    )
    args = parser.parse_args()

    rows = [(lbl, v, lv, c, "normal") for lbl, v, lv, c in SAMPLES] + [
        (lbl, v, lv, c, "watch") for lbl, v, lv, c in WATCHED_SAMPLES
    ]
    width = max(len(label) for label, *_ in rows)
    guard_texts = []

    for label, value, level, card, attention in rows:
        text = _contact_report_text(build_facts(value, level, card, attention))
        line = f"{label:<{width}}  |  {text}"
        if args.speak:
            status = speak(args.adapter_url, text)
            line += f"   [{status}]"
        print(line)
        if args.speak:
            time.sleep(args.pause)
        if label.startswith("singular"):
            guard_texts.append((label, text))

    print()
    same = len({t for _, t in guard_texts[:2]}) == 1
    print(
        "regression guard: explicit (1,1) and absent-cardinality render "
        + ("IDENTICALLY -- correct." if same else "DIFFERENTLY -- investigate.")
    )

    print()
    wording_width = max(len(label) for label, _ in WORDING_SAMPLES)
    for label, facts in WORDING_SAMPLES:
        text = _contact_report_text(facts)
        line = f"{label:<{wording_width}}  |  {text}"
        if args.speak:
            status = speak(args.adapter_url, text)
            line += f"   [{status}]"
        print(line)
        if args.speak:
            time.sleep(args.pause)

    return 0


if __name__ == "__main__":
    sys.exit(main())
