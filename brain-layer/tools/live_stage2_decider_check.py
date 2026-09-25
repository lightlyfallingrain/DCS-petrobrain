"""Cross-process BR-1 Stage 2 check -- a dev acceptance aid, not a test.
Mirrors `live_cross_process_check.py`'s own shape (Stage 1's async round
trip) but drives a real `brain-layer` server running `OllamaDecider`
against a real Ollama daemon, exercising both prompt shapes end to end:
the discriminate call (ambiguous vs. discriminating "that tank") and the
classify call (a paraphrased known command vs. genuine nonsense).

Assertion-free by design, same posture as `live_cross_process_check.py`/
`body-layer/tools/speak_samples.py` -- it prints numbers and replies for a
human to judge. This is the instrument for the one verification gap this
stage's implementation could not close in-sandbox: no test here runs a
real Ollama daemon, so nothing here can prove a real model's own quoting/
deliberation habits against the live prompts short of running this.

Run it with the server up:

    cd brain-layer && PYTHONPATH=src .venv/bin/python -m brain_layer \\
        --host 127.0.0.1 --decider ollama \\
        --brain-model qwen3:4b-instruct-2507-q4_K_M &
    .venv/bin/python brain-layer/tools/live_stage2_decider_check.py
"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any

URL = "http://127.0.0.1:7796"


def _post(path: str, body: dict[str, Any]) -> None:
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        f"{URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        response.read()


def _get(path: str) -> Any:
    with urllib.request.urlopen(f"{URL}{path}", timeout=5) as response:
        return json.loads(response.read())


def _escalate_and_wait(
    payload: dict[str, Any], timeout_s: float = 15.0
) -> tuple[float, float | None, dict[str, Any] | None]:
    t0 = time.monotonic()
    _post("/escalate", payload)
    handoff = time.monotonic() - t0
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        replies = _get("/replies/poll")
        if replies:
            return handoff, time.monotonic() - t0, replies[0]
        time.sleep(0.05)
    return handoff, None, None


_DISCRIMINATE_BASE: dict[str, Any] = {
    "utterance_id": "U_DISCRIMINATE",
    "transcript": "keep an eye on that tank",
    "t_sim": 100.0,
    "partial_parse": {
        "matched_intent": "set_attention",
        "referenced_contact_candidates": [
            {"id": "CONTACT_7", "why": "T-72, 2.1 km, near Gemerek village"},
            {"id": "CONTACT_12", "why": "T-72, 3.4 km, on the road"},
        ],
    },
}


def main() -> None:
    ambiguous = dict(_DISCRIMINATE_BASE, utterance_id="U1")
    handoff, elapsed, reply = _escalate_and_wait(ambiguous)
    print(
        f"1. discriminate, genuinely ambiguous: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")

    discriminating = dict(_DISCRIMINATE_BASE)
    discriminating["utterance_id"] = "U2"
    discriminating["transcript"] = "keep an eye on that tank near the village"
    handoff, elapsed, reply = _escalate_and_wait(discriminating)
    print(
        f"2. discriminate, has a discriminating word: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")

    classify_paraphrase = {
        "utterance_id": "U3",
        "transcript": "go take a look up north",
        "t_sim": 100.0,
        "partial_parse": {"matched_intent": None, "referenced_contact_candidates": []},
    }
    handoff, elapsed, reply = _escalate_and_wait(classify_paraphrase)
    print(
        f"3. classify, paraphrased known command: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")

    classify_nonsense = {
        "utterance_id": "U4",
        "transcript": "the grass over there is looking rather brown today",
        "t_sim": 100.0,
        "partial_parse": {"matched_intent": None, "referenced_contact_candidates": []},
    }
    handoff, elapsed, reply = _escalate_and_wait(classify_nonsense)
    print(
        f"4. classify, genuine nonsense: handoff={handoff * 1000:.1f}ms elapsed={elapsed}"
    )
    print(f"   reply = {reply}")


if __name__ == "__main__":
    main()
